"""
Clothing shop views for purchasing pet clothing and accessories.
"""

import time
import discord
from discord.ui import View, Button, Select
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, InventoryItem, GuildSettings

from ..database.petshop import SHOP_DATABASE
from ..common.models import InventoryItem


# =============================================================================
# CATEGORY MAPPING
# =============================================================================

# Maps dropdown display names to database category values
CATEGORY_MAPPING = {
    "Onesies": ["onesie"],
    "Hats": ["hat"],
    "Headbands": ["headband"],
    "Collars": ["collar"],
    "Eyepatches & Glasses": ["eyepatch", "glasses"],
    "Socks & Booties": ["socks", "booties"],
    "Tail Accessories": ["tail"],
    "Earrings": ["earring"],
    "Capes & Costumes": ["cape", "costume"],
}

# Emoji mapping for categories
CATEGORY_EMOJIS = {
    "Onesies": "👕",
    "Hats": "🎩",
    "Headbands": "🐱",
    "Collars": "🔴",
    "Eyepatches & Glasses": "😎",
    "Socks & Booties": "🧦",
    "Tail Accessories": "🎀",
    "Earrings": "💎",
    "Capes & Costumes": "🦸",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_items_for_category(category_name: str, owned_item_ids: List[str]) -> List[dict]:
    """Get purchasable items for a category (common/uncommon only, not owned).
    
    Args:
        category_name: Display name of the category (e.g., "Onesies")
        owned_item_ids: List of item IDs the user already owns
        
    Returns:
        List of item dicts with their IDs included
    """
    db_categories = CATEGORY_MAPPING.get(category_name, [])
    items = []
    
    for item_id, item_data in SHOP_DATABASE.items():
        # Skip if not in the requested category
        if item_data.get("category") not in db_categories:
            continue
        
        # Skip rare and legendary items (those are special)
        if item_data.get("rarity") in ["rare", "legendary"]:
            continue
        
        # Skip holiday items (those are in the Holiday Items section)
        if item_data.get("holiday"):
            continue
        
        # Skip if user already owns this item
        if item_id in owned_item_ids:
            continue
        
        items.append({"id": item_id, **item_data})
    
    # Sort by value (price)
    items.sort(key=lambda x: x.get("value", 0))
    
    return items


def get_owned_item_ids(user_data: "User") -> List[str]:
    """Get list of item IDs the user owns."""
    return [item.item_id for item in user_data.current_item_inventory]


# =============================================================================
# CLOTHING SHOP VIEW
# =============================================================================

class ClothingShopView(View):
    """Main view for the clothing shop with category selection."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        active_holiday: Optional[str] = None
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.active_holiday = active_holiday
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Category dropdown
        self.add_item(CategorySelect())
        
        # Row 1: Special category buttons
        # Disable legendary items button if user has no legendarycoins
        has_legendarycoin = user_data.legendarycoin > 0
        self.add_item(LegendaryItemsButton(disabled=not has_legendarycoin))
        self.add_item(HolidayItemsButton(active_holiday=active_holiday))
        
        # Daily Freebie button - check if already claimed
        from ..database.freebie import get_freebie_button_state
        disabled, label = get_freebie_button_state(user_data, guild_settings)
        self.add_item(DailyFreebieButton(disabled=disabled, label=label))
        
        # Row 2: Navigation buttons
        self.add_item(BackToShopButton())
        self.add_item(CloseClothingShopButton())

    def build_embed(self) -> discord.Embed:
        """Build the main clothing shop embed."""
        embed = discord.Embed(
            title="👕 Clothing Shop",
            description=(
                "Welcome to the Clothing Shop!\n\n"
                "Dress up your pets with stylish outfits and accessories.\n\n"
                "💰 **Your Petcoin:** {petcoin:,}\n"
                "✨ **Your Legendarycoin:** {legendarycoin:,}\n\n"
                "Select a category from the dropdown below to browse items."
            ).format(
                petcoin=self.user_data.current_petcoin,
                legendarycoin=self.user_data.legendarycoin
            ),
            color=discord.Color.blue()
        )
        
        # Show category overview
        owned_ids = get_owned_item_ids(self.user_data)
        category_info = []
        
        for cat_name in CATEGORY_MAPPING.keys():
            available_items = get_items_for_category(cat_name, owned_ids)
            emoji = CATEGORY_EMOJIS.get(cat_name, "📦")
            category_info.append(f"{emoji} **{cat_name}**: {len(available_items)} available")
        
        embed.add_field(
            name="📋 Categories",
            value="\n".join(category_info),
            inline=False
        )
        
        # Show inventory count
        embed.set_footer(text=f"🎒 Your Inventory: {len(self.user_data.current_item_inventory)} items")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


# =============================================================================
# CATEGORY SELECTION
# =============================================================================

class CategorySelect(Select):
    """Dropdown to select a clothing category."""

    def __init__(self):
        options = [
            discord.SelectOption(
                label=cat_name,
                value=cat_name,
                emoji=CATEGORY_EMOJIS.get(cat_name, "📦"),
                description=f"Browse {cat_name.lower()}"
            )
            for cat_name in CATEGORY_MAPPING.keys()
        ]
        
        super().__init__(
            placeholder="Select a category...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ClothingShopView = self.view
        category_name = self.values[0]
        
        # Get available items for this category
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_items_for_category(category_name, owned_ids)
        
        if not items:
            await interaction.response.send_message(
                f"You already own all available items in **{category_name}**! 🎉",
                ephemeral=True
            )
            return
        
        # Stop current view and create item selection view
        view.stop()
        
        item_view = ItemSelectionView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            category_name=category_name,
            items=items
        )
        
        embed = item_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=item_view)
        item_view.message = view.message


# =============================================================================
# ITEM SELECTION VIEW
# =============================================================================

class ItemSelectionView(View):
    """View for selecting an item to purchase within a category."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        category_name: str,
        items: List[dict]
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.category_name = category_name
        self.items = items
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Item dropdown
        self.add_item(ItemSelect(items))
        
        # Row 1: Navigation buttons
        self.add_item(BackToCategoriesButton())
        self.add_item(CloseClothingShopButton())

    def build_embed(self) -> discord.Embed:
        """Build the item selection embed."""
        emoji = CATEGORY_EMOJIS.get(self.category_name, "📦")
        
        embed = discord.Embed(
            title=f"{emoji} {self.category_name}",
            description=(
                f"Browse and purchase items from the **{self.category_name}** category.\n\n"
                f"💰 **Your Petcoin:** {self.user_data.current_petcoin:,}\n\n"
                "Select an item from the dropdown to view details and purchase."
            ),
            color=discord.Color.blue()
        )
        
        # Show available items preview
        items_preview = []
        for item in self.items[:10]:  # Show first 10
            rarity_emoji = {"common": "⚪", "uncommon": "🟢"}.get(item.get("rarity", "common"), "⚪")
            items_preview.append(
                f"{item.get('value'):,} 💰 {rarity_emoji} {item.get('emoji', '📦')} **{item.get('name')}**"
            )
        
        if len(self.items) > 10:
            items_preview.append(f"*...and {len(self.items) - 10} more*")
        
        embed.add_field(
            name=f"📋 Available Items ({len(self.items)})",
            value="\n".join(items_preview) if items_preview else "No items available",
            inline=False
        )
        
        embed.set_footer(text="⚪ Common | 🟢 Uncommon")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ItemSelect(Select):
    """Dropdown to select an item to purchase."""

    def __init__(self, items: List[dict]):
        options = []
        for item in items[:25]:  # Discord limit is 25 options
            rarity_emoji = {"common": "⚪", "uncommon": "🟢"}.get(item.get("rarity", "common"), "⚪")
            options.append(
                discord.SelectOption(
                    label=f"{item.get('name')} - {item.get('value'):,} 💰",
                    value=item.get("id"),
                    emoji=item.get("emoji", "📦"),
                    description=f"{rarity_emoji} {item.get('description', '')[:50]}"
                )
            )
        
        super().__init__(
            placeholder="Select an item to purchase...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ItemSelectionView = self.view
        item_id = self.values[0]
        
        # Get item data from database
        item_data = SHOP_DATABASE.get(item_id)
        if not item_data:
            await interaction.response.send_message(
                "That item no longer exists in the shop!",
                ephemeral=True
            )
            return
        
        # Check if user can afford it
        item_price = item_data.get("value", 0)
        
        if view.user_data.current_petcoin < item_price:
            await interaction.response.send_message(
                f"❌ **Insufficient Funds!**\n\n"
                f"**{item_data.get('name')}** costs **{item_price:,}** 💰\n"
                f"You only have **{view.user_data.current_petcoin:,}** 💰\n\n"
                f"You need **{item_price - view.user_data.current_petcoin:,}** more petcoin!",
                ephemeral=True
            )
            return
        
        # Stop current view and show purchase confirmation
        view.stop()
        
        confirm_view = PurchaseConfirmView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            category_name=view.category_name,
            item_id=item_id,
            item_data=item_data
        )
        
        embed = confirm_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)
        confirm_view.message = view.message


# =============================================================================
# PURCHASE CONFIRMATION VIEW
# =============================================================================

class PurchaseConfirmView(View):
    """View for confirming a purchase."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        category_name: str,
        item_id: str,
        item_data: dict
    ) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.category_name = category_name
        self.item_id = item_id
        self.item_data = item_data
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Confirm/Cancel buttons
        self.add_item(ConfirmPurchaseButton())
        self.add_item(CancelPurchaseButton())

    def build_embed(self) -> discord.Embed:
        """Build the purchase confirmation embed."""
        item_price = self.item_data.get("value", 0)
        remaining = self.user_data.current_petcoin - item_price
        rarity_display = {
            "common": "⚪ Common",
            "uncommon": "🟢 Uncommon"
        }.get(self.item_data.get("rarity", "common"), "⚪ Common")
        
        embed = discord.Embed(
            title="🛒 Confirm Purchase",
            description=(
                f"Are you sure you want to purchase this item?\n\n"
                f"{self.item_data.get('emoji', '📦')} **{self.item_data.get('name')}**\n"
                f"*{self.item_data.get('description', 'No description')}*\n\n"
                f"**Rarity:** {rarity_display}\n"
                f"**Price:** {item_price:,} 💰\n\n"
                f"💰 Your Balance: **{self.user_data.current_petcoin:,}**\n"
                f"💰 After Purchase: **{remaining:,}**"
            ),
            color=discord.Color.gold()
        )
        
        embed.set_footer(text="This purchase cannot be undone!")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ConfirmPurchaseButton(Button):
    """Button to confirm the purchase."""

    def __init__(self):
        super().__init__(
            label="Confirm Purchase",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PurchaseConfirmView = self.view
        item_price = view.item_data.get("value", 0)
        
        # Double-check user can still afford it
        if view.user_data.current_petcoin < item_price:
            await interaction.response.send_message(
                "❌ You no longer have enough petcoin for this purchase!",
                ephemeral=True
            )
            return
        
        # Double-check user doesn't already own it
        owned_ids = get_owned_item_ids(view.user_data)
        if view.item_id in owned_ids:
            await interaction.response.send_message(
                "❌ You already own this item!",
                ephemeral=True
            )
            return
        
        # Process the purchase
        view.user_data.current_petcoin -= item_price
        
        # Add item to inventory
        new_item = InventoryItem(
            item_id=view.item_id,
            acquired_timestamp=time.time(),
            acquired_via="purchase"
        )
        view.user_data.current_item_inventory.append(new_item)
        
        # Save
        view.cog.schedule_save()
        
        # Stop view
        view.stop()
        
        # Show success and return to clothing shop
        embed = discord.Embed(
            title="✅ Purchase Successful!",
            description=(
                f"You purchased {view.item_data.get('emoji', '📦')} **{view.item_data.get('name')}**!\n\n"
                f"💰 Spent: **{item_price:,}** petcoin\n"
                f"💰 Remaining: **{view.user_data.current_petcoin:,}** petcoin\n\n"
                f"🎒 The item has been added to your inventory!"
            ),
            color=discord.Color.green()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        # Create a view to return to shopping
        return_view = PostPurchaseView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            category_name=view.category_name
        )
        
        await interaction.response.edit_message(embed=embed, view=return_view)
        return_view.message = view.message


class CancelPurchaseButton(Button):
    """Button to cancel the purchase."""

    def __init__(self):
        super().__init__(
            label="Cancel",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PurchaseConfirmView = self.view
        
        # Return to item selection
        view.stop()
        
        # Get updated items for category
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_items_for_category(view.category_name, owned_ids)
        
        if not items:
            # All items owned, go back to categories
            conf = view.cog.db.get_conf(interaction.guild)
            clothing_view = ClothingShopView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                active_holiday=conf.active_holiday
            )
            embed = clothing_view.build_embed()
        else:
            clothing_view = ItemSelectionView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                category_name=view.category_name,
                items=items
            )
            embed = clothing_view.build_embed()
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=clothing_view)
        clothing_view.message = view.message


# =============================================================================
# POST-PURCHASE VIEW
# =============================================================================

class PostPurchaseView(View):
    """View shown after a successful purchase."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        category_name: str
    ) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.category_name = category_name
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Continue shopping options
        self.add_item(ContinueShoppingButton())
        self.add_item(BackToShopButton())
        self.add_item(CloseClothingShopButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ContinueShoppingButton(Button):
    """Button to continue shopping in the same category."""

    def __init__(self):
        super().__init__(
            label="Continue Shopping",
            emoji="🛒",
            style=discord.ButtonStyle.primary,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: PostPurchaseView = self.view
        view.stop()
        
        # Get updated items for category
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_items_for_category(view.category_name, owned_ids)
        
        if not items:
            # All items owned, go to categories
            await interaction.response.send_message(
                f"You already own all available items in **{view.category_name}**! 🎉",
                ephemeral=True
            )
            
            conf = view.cog.db.get_conf(interaction.guild)
            clothing_view = ClothingShopView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                active_holiday=conf.active_holiday
            )
            embed = clothing_view.build_embed()
        else:
            clothing_view = ItemSelectionView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                category_name=view.category_name,
                items=items
            )
            embed = clothing_view.build_embed()
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=clothing_view)
        clothing_view.message = view.message


# =============================================================================
# LEGENDARY ITEMS BUTTON AND VIEW
# =============================================================================

def get_legendary_items(owned_item_ids: List[str]) -> List[dict]:
    """Get all legendary items that the user doesn't own.
    
    Args:
        owned_item_ids: List of item IDs the user already owns
        
    Returns:
        List of legendary item dicts with their IDs included
    """
    items = []
    
    for item_id, item_data in SHOP_DATABASE.items():
        # Only legendary items
        if item_data.get("rarity") != "legendary":
            continue
        
        # Skip if user already owns this item
        if item_id in owned_item_ids:
            continue
        
        items.append({"id": item_id, **item_data})
    
    # Sort by name
    items.sort(key=lambda x: x.get("name", ""))
    
    return items


class LegendaryItemsButton(Button):
    """Button for legendary items."""

    def __init__(self, disabled: bool = False):
        super().__init__(
            label="Legendary Items",
            emoji="✨",
            style=discord.ButtonStyle.secondary if not disabled else discord.ButtonStyle.secondary,
            row=1,
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ClothingShopView = self.view
        
        # Get available legendary items
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_legendary_items(owned_ids)
        
        if not items:
            await interaction.response.send_message(
                "✨ You already own all Legendary Items! Amazing! 🎉",
                ephemeral=True
            )
            return
        
        # Stop current view and create legendary items view
        view.stop()
        
        legendary_view = LegendaryItemsView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            items=items
        )
        
        embed = legendary_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=legendary_view)
        legendary_view.message = view.message


class LegendaryItemsView(View):
    """View for browsing and purchasing legendary items."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        items: List[dict]
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.items = items
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Item dropdown
        self.add_item(LegendaryItemSelect(items))
        
        # Row 1: Navigation buttons
        self.add_item(BackToCategoriesButton())
        self.add_item(CloseClothingShopButton())

    def build_embed(self) -> discord.Embed:
        """Build the legendary items embed."""
        embed = discord.Embed(
            title="✨ Legendary Items",
            description=(
                "The rarest and most exclusive items in the shop!\n\n"
                "✨ **Your Legendarycoin:** {legendarycoin:,}\n"
                "💰 **Cost:** 1 Legendarycoin each\n\n"
                "Select an item from the dropdown to view details and purchase."
            ).format(legendarycoin=self.user_data.legendarycoin),
            color=discord.Color.gold()
        )
        
        # Show available items preview
        items_preview = []
        for item in self.items:
            # Build restriction note
            restrictions = []
            if item.get("category_restricted"):
                restrictions.append(f"{', '.join(item['category_restricted']).title()} pets only")
            if item.get("species_restricted"):
                restrictions.append(f"{', '.join(item['species_restricted']).title()} only")
            
            restriction_text = f" *({'; '.join(restrictions)})*" if restrictions else ""
            
            items_preview.append(
                f"{item.get('emoji', '📦')} **{item.get('name')}**{restriction_text}"
            )
        
        embed.add_field(
            name=f"📋 Available Items ({len(self.items)})",
            value="\n".join(items_preview) if items_preview else "No items available",
            inline=False
        )
        
        embed.set_footer(text="Earn Legendarycoins by graduating 5 pets!")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class LegendaryItemSelect(Select):
    """Dropdown to select a legendary item to purchase."""

    def __init__(self, items: List[dict]):
        options = []
        for item in items[:25]:  # Discord limit is 25 options
            # Build restriction note for description
            restrictions = []
            if item.get("category_restricted"):
                restrictions.append(f"{', '.join(item['category_restricted']).title()} pets only")
            if item.get("species_restricted"):
                restrictions.append(f"{', '.join(item['species_restricted']).title()} only")
            
            description = item.get('description', '')[:50]
            if restrictions:
                restriction_text = f" [{'; '.join(restrictions)}]"
                # Truncate description to fit restriction note
                max_desc_len = 100 - len(restriction_text)
                description = description[:max_desc_len] + restriction_text
            
            options.append(
                discord.SelectOption(
                    label=item.get('name'),
                    value=item.get("id"),
                    emoji=item.get("emoji", "📦"),
                    description=description[:100]  # Discord limit
                )
            )
        
        super().__init__(
            placeholder="Select a legendary item...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: LegendaryItemsView = self.view
        item_id = self.values[0]
        
        # Get item data from database
        item_data = SHOP_DATABASE.get(item_id)
        if not item_data:
            await interaction.response.send_message(
                "That item no longer exists in the shop!",
                ephemeral=True
            )
            return
        
        # Check if user can afford it (1 legendarycoin)
        if view.user_data.legendarycoin < 1:
            await interaction.response.send_message(
                f"❌ **Insufficient Funds!**\n\n"
                f"**{item_data.get('name')}** costs **1** ✨ Legendarycoin\n"
                f"You have **{view.user_data.legendarycoin}** ✨ Legendarycoins\n\n"
                f"Earn Legendarycoins by graduating 5 pets!",
                ephemeral=True
            )
            return
        
        # Stop current view and show purchase confirmation
        view.stop()
        
        confirm_view = LegendaryPurchaseConfirmView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            item_id=item_id,
            item_data=item_data
        )
        
        embed = confirm_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)
        confirm_view.message = view.message


class LegendaryPurchaseConfirmView(View):
    """View for confirming a legendary item purchase."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        item_id: str,
        item_data: dict
    ) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.item_id = item_id
        self.item_data = item_data
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Confirm/Cancel buttons
        self.add_item(ConfirmLegendaryPurchaseButton())
        self.add_item(CancelLegendaryPurchaseButton())

    def build_embed(self) -> discord.Embed:
        """Build the purchase confirmation embed."""
        remaining = self.user_data.legendarycoin - 1
        
        # Build restriction note
        restrictions = []
        if self.item_data.get("category_restricted"):
            restrictions.append(f"{', '.join(self.item_data['category_restricted']).title()} pets only")
        if self.item_data.get("species_restricted"):
            restrictions.append(f"{', '.join(self.item_data['species_restricted']).title()} only")
        
        restriction_text = f"\n⚠️ **Restrictions:** {'; '.join(restrictions)}" if restrictions else ""
        
        embed = discord.Embed(
            title="✨ Confirm Legendary Purchase",
            description=(
                f"Are you sure you want to purchase this legendary item?\n\n"
                f"{self.item_data.get('emoji', '📦')} **{self.item_data.get('name')}**\n"
                f"*{self.item_data.get('description', 'No description')}*\n"
                f"{restriction_text}\n\n"
                f"**Price:** 1 ✨ Legendarycoin\n\n"
                f"✨ Your Balance: **{self.user_data.legendarycoin}**\n"
                f"✨ After Purchase: **{remaining}**"
            ),
            color=discord.Color.gold()
        )
        
        embed.set_footer(text="This purchase cannot be undone!")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ConfirmLegendaryPurchaseButton(Button):
    """Button to confirm the legendary purchase."""

    def __init__(self):
        super().__init__(
            label="Confirm Purchase",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: LegendaryPurchaseConfirmView = self.view
        
        # Double-check user can still afford it
        if view.user_data.legendarycoin < 1:
            await interaction.response.send_message(
                "❌ You no longer have enough Legendarycoins for this purchase!",
                ephemeral=True
            )
            return
        
        # Double-check user doesn't already own it
        owned_ids = get_owned_item_ids(view.user_data)
        if view.item_id in owned_ids:
            await interaction.response.send_message(
                "❌ You already own this item!",
                ephemeral=True
            )
            return
        
        # Process the purchase
        view.user_data.legendarycoin -= 1
        
        # Add item to inventory
        new_item = InventoryItem(
            item_id=view.item_id,
            acquired_timestamp=time.time(),
            acquired_via="legendary_reward"
        )
        view.user_data.current_item_inventory.append(new_item)
        
        # Save
        view.cog.schedule_save()
        
        # Stop view
        view.stop()
        
        # Show success and return to legendary items
        embed = discord.Embed(
            title="✨ Legendary Purchase Successful!",
            description=(
                f"You purchased {view.item_data.get('emoji', '📦')} **{view.item_data.get('name')}**!\n\n"
                f"✨ Spent: **1** Legendarycoin\n"
                f"✨ Remaining: **{view.user_data.legendarycoin}** Legendarycoins\n\n"
                f"🎒 The item has been added to your inventory!"
            ),
            color=discord.Color.gold()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        # Create a view to return to shopping
        return_view = LegendaryPostPurchaseView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id
        )
        
        await interaction.response.edit_message(embed=embed, view=return_view)
        return_view.message = view.message


class CancelLegendaryPurchaseButton(Button):
    """Button to cancel the legendary purchase."""

    def __init__(self):
        super().__init__(
            label="Cancel",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: LegendaryPurchaseConfirmView = self.view
        
        # Return to legendary items selection
        view.stop()
        
        # Get updated items
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_legendary_items(owned_ids)
        
        if not items:
            # All items owned, go back to categories
            conf = view.cog.db.get_conf(interaction.guild)
            clothing_view = ClothingShopView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                active_holiday=conf.active_holiday
            )
            embed = clothing_view.build_embed()
        else:
            clothing_view = LegendaryItemsView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                items=items
            )
            embed = clothing_view.build_embed()
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=clothing_view)
        clothing_view.message = view.message


class LegendaryPostPurchaseView(View):
    """View shown after a successful legendary purchase."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int
    ) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Continue shopping options
        self.add_item(ContinueLegendaryShoppingButton())
        self.add_item(BackToCategoriesButton())
        self.add_item(CloseClothingShopButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ContinueLegendaryShoppingButton(Button):
    """Button to continue shopping legendary items."""

    def __init__(self):
        super().__init__(
            label="More Legendary Items",
            emoji="✨",
            style=discord.ButtonStyle.primary,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: LegendaryPostPurchaseView = self.view
        view.stop()
        
        # Get updated legendary items
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_legendary_items(owned_ids)
        
        if not items:
            # All items owned, go to categories
            await interaction.response.send_message(
                "✨ You already own all Legendary Items! Amazing! 🎉",
                ephemeral=True
            )
            
            conf = view.cog.db.get_conf(interaction.guild)
            clothing_view = ClothingShopView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                active_holiday=conf.active_holiday
            )
            embed = clothing_view.build_embed()
        else:
            clothing_view = LegendaryItemsView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                items=items
            )
            embed = clothing_view.build_embed()
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=clothing_view)
        clothing_view.message = view.message


# =============================================================================
# HOLIDAY ITEMS BUTTON AND VIEW
# =============================================================================

# Holiday display names and emojis
HOLIDAY_DISPLAY = {
    "christmas": {"name": "Christmas", "emoji": "🎄"},
    "halloween": {"name": "Halloween", "emoji": "🎃"},
    "easter": {"name": "Easter", "emoji": "🐰"},
    "valentines": {"name": "Valentine's Day", "emoji": "💕"},
    "stpatricks": {"name": "St. Patrick's Day", "emoji": "☘️"},
    "thanksgiving": {"name": "Thanksgiving", "emoji": "🦃"},
    "newyear": {"name": "New Year's", "emoji": "🎉"},
    "july4": {"name": "4th of July", "emoji": "🎆"},
    "mardigras": {"name": "Mardi Gras", "emoji": "🎭"},
}


def get_holiday_items(holiday: str, owned_item_ids: List[str]) -> List[dict]:
    """Get all holiday items for a specific holiday that the user doesn't own.
    
    Args:
        holiday: The holiday key (christmas, halloween, easter, valentines)
        owned_item_ids: List of item IDs the user already owns
        
    Returns:
        List of holiday item dicts with their IDs included
    """
    items = []
    
    for item_id, item_data in SHOP_DATABASE.items():
        # Only items for this holiday
        if item_data.get("holiday") != holiday:
            continue
        
        # Skip if user already owns this item
        if item_id in owned_item_ids:
            continue
        
        items.append({"id": item_id, **item_data})
    
    # Sort by value (price)
    items.sort(key=lambda x: x.get("value", 0))
    
    return items


class HolidayItemsButton(Button):
    """Button for holiday items."""

    def __init__(self, active_holiday: Optional[str] = None):
        self.active_holiday = active_holiday
        
        # Get emoji based on active holiday
        holiday_emoji = "🎄"  # Default
        if active_holiday:
            holiday_emoji = HOLIDAY_DISPLAY.get(active_holiday, {}).get("emoji", "🎄")
        
        super().__init__(
            label="Holiday Items",
            emoji=holiday_emoji,
            style=discord.ButtonStyle.secondary,
            row=1,
            disabled=(active_holiday is None)  # Disabled when no holiday active
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: ClothingShopView = self.view
        active_holiday = self.active_holiday
        
        # Double-check (shouldn't happen since button is disabled)
        if not active_holiday:
            await interaction.response.send_message(
                "🎄 **No Holiday Active!**\n\n"
                "There is no holiday event currently running.\n"
                "Check back during special holiday seasons!",
                ephemeral=True
            )
            return
        
        # Validate it's a known holiday
        if active_holiday not in HOLIDAY_DISPLAY:
            await interaction.response.send_message(
                f"⚠️ Unknown holiday: {active_holiday}",
                ephemeral=True
            )
            return
        
        # Get available holiday items
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_holiday_items(active_holiday, owned_ids)
        
        if not items:
            holiday_name = HOLIDAY_DISPLAY[active_holiday]["name"]
            await interaction.response.send_message(
                f"🎉 You already own all **{holiday_name}** items! Amazing!",
                ephemeral=True
            )
            return
        
        # Stop current view and create holiday items view
        view.stop()
        
        holiday_view = HolidayItemsView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            holiday=active_holiday,
            items=items
        )
        
        embed = holiday_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=holiday_view)
        holiday_view.message = view.message


class HolidayItemsView(View):
    """View for browsing and purchasing holiday items."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        holiday: str,
        items: List[dict]
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.holiday = holiday
        self.items = items
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Item dropdown
        self.add_item(HolidayItemSelect(items))
        
        # Row 1: Navigation buttons
        self.add_item(BackToCategoriesButton())
        self.add_item(CloseClothingShopButton())

    def build_embed(self) -> discord.Embed:
        """Build the holiday items embed."""
        holiday_info = HOLIDAY_DISPLAY.get(self.holiday, {"name": self.holiday.title(), "emoji": "🎄"})
        
        embed = discord.Embed(
            title=f"{holiday_info['emoji']} {holiday_info['name']} Items",
            description=(
                f"Limited time **{holiday_info['name']}** items!\n\n"
                f"💰 **Your Petcoin:** {self.user_data.current_petcoin:,}\n\n"
                "Select an item from the dropdown to view details and purchase."
            ),
            color=discord.Color.red() if self.holiday == "christmas" else 
                  discord.Color.orange() if self.holiday == "halloween" else
                  discord.Color.pink() if self.holiday in ["easter", "valentines"] else
                  discord.Color.blue()
        )
        
        # Show available items preview
        items_preview = []
        for item in self.items:
            rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵"}.get(item.get("rarity", "common"), "⚪")
            items_preview.append(
                f"{item.get('value'):,} 💰 {rarity_emoji} {item.get('emoji', '📦')} **{item.get('name')}**"
            )
        
        embed.add_field(
            name=f"📋 Available Items ({len(self.items)})",
            value="\n".join(items_preview) if items_preview else "No items available",
            inline=False
        )
        
        embed.set_footer(text=f"⚪ Common | 🟢 Uncommon | 🔵 Rare • Limited time only!")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class HolidayItemSelect(Select):
    """Dropdown to select a holiday item to purchase."""

    def __init__(self, items: List[dict]):
        options = []
        for item in items[:25]:  # Discord limit is 25 options
            rarity_emoji = {"common": "⚪", "uncommon": "🟢", "rare": "🔵"}.get(item.get("rarity", "common"), "⚪")
            options.append(
                discord.SelectOption(
                    label=f"{item.get('name')} - {item.get('value'):,} 💰",
                    value=item.get("id"),
                    emoji=item.get("emoji", "📦"),
                    description=f"{rarity_emoji} {item.get('description', '')[:50]}"
                )
            )
        
        super().__init__(
            placeholder="Select a holiday item...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HolidayItemsView = self.view
        item_id = self.values[0]
        
        # Get item data from database
        item_data = SHOP_DATABASE.get(item_id)
        if not item_data:
            await interaction.response.send_message(
                "That item no longer exists in the shop!",
                ephemeral=True
            )
            return
        
        # Check if user can afford it
        item_price = item_data.get("value", 0)
        
        if view.user_data.current_petcoin < item_price:
            await interaction.response.send_message(
                f"❌ **Insufficient Funds!**\n\n"
                f"**{item_data.get('name')}** costs **{item_price:,}** 💰\n"
                f"You only have **{view.user_data.current_petcoin:,}** 💰\n\n"
                f"You need **{item_price - view.user_data.current_petcoin:,}** more petcoin!",
                ephemeral=True
            )
            return
        
        # Stop current view and show purchase confirmation
        view.stop()
        
        confirm_view = HolidayPurchaseConfirmView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            holiday=view.holiday,
            item_id=item_id,
            item_data=item_data
        )
        
        embed = confirm_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)
        confirm_view.message = view.message


class HolidayPurchaseConfirmView(View):
    """View for confirming a holiday item purchase."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        holiday: str,
        item_id: str,
        item_data: dict
    ) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.holiday = holiday
        self.item_id = item_id
        self.item_data = item_data
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Confirm/Cancel buttons
        self.add_item(ConfirmHolidayPurchaseButton())
        self.add_item(CancelHolidayPurchaseButton())

    def build_embed(self) -> discord.Embed:
        """Build the purchase confirmation embed."""
        item_price = self.item_data.get("value", 0)
        remaining = self.user_data.current_petcoin - item_price
        rarity_display = {
            "common": "⚪ Common",
            "uncommon": "🟢 Uncommon",
            "rare": "🔵 Rare"
        }.get(self.item_data.get("rarity", "common"), "⚪ Common")
        
        holiday_info = HOLIDAY_DISPLAY.get(self.holiday, {"name": self.holiday.title(), "emoji": "🎄"})
        
        embed = discord.Embed(
            title=f"{holiday_info['emoji']} Confirm Purchase",
            description=(
                f"Are you sure you want to purchase this {holiday_info['name']} item?\n\n"
                f"{self.item_data.get('emoji', '📦')} **{self.item_data.get('name')}**\n"
                f"*{self.item_data.get('description', 'No description')}*\n\n"
                f"**Rarity:** {rarity_display}\n"
                f"**Price:** {item_price:,} 💰\n\n"
                f"💰 Your Balance: **{self.user_data.current_petcoin:,}**\n"
                f"💰 After Purchase: **{remaining:,}**"
            ),
            color=discord.Color.gold()
        )
        
        embed.set_footer(text="This purchase cannot be undone!")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ConfirmHolidayPurchaseButton(Button):
    """Button to confirm the holiday purchase."""

    def __init__(self):
        super().__init__(
            label="Confirm Purchase",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HolidayPurchaseConfirmView = self.view
        item_price = view.item_data.get("value", 0)
        
        # Double-check user can still afford it
        if view.user_data.current_petcoin < item_price:
            await interaction.response.send_message(
                "❌ You no longer have enough petcoin for this purchase!",
                ephemeral=True
            )
            return
        
        # Double-check user doesn't already own it
        owned_ids = get_owned_item_ids(view.user_data)
        if view.item_id in owned_ids:
            await interaction.response.send_message(
                "❌ You already own this item!",
                ephemeral=True
            )
            return
        
        # Process the purchase
        view.user_data.current_petcoin -= item_price
        
        # Add item to inventory
        new_item = InventoryItem(
            item_id=view.item_id,
            acquired_timestamp=time.time(),
            acquired_via="purchase"
        )
        view.user_data.current_item_inventory.append(new_item)
        
        # Save
        view.cog.schedule_save()
        
        # Stop view
        view.stop()
        
        holiday_info = HOLIDAY_DISPLAY.get(view.holiday, {"name": view.holiday.title(), "emoji": "🎄"})
        
        # Show success and return to holiday items
        embed = discord.Embed(
            title=f"{holiday_info['emoji']} Purchase Successful!",
            description=(
                f"You purchased {view.item_data.get('emoji', '📦')} **{view.item_data.get('name')}**!\n\n"
                f"💰 Spent: **{item_price:,}** petcoin\n"
                f"💰 Remaining: **{view.user_data.current_petcoin:,}** petcoin\n\n"
                f"🎒 The item has been added to your inventory!"
            ),
            color=discord.Color.green()
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        # Create a view to return to shopping
        return_view = HolidayPostPurchaseView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            holiday=view.holiday
        )
        
        await interaction.response.edit_message(embed=embed, view=return_view)
        return_view.message = view.message


class CancelHolidayPurchaseButton(Button):
    """Button to cancel the holiday purchase."""

    def __init__(self):
        super().__init__(
            label="Cancel",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HolidayPurchaseConfirmView = self.view
        
        # Return to holiday items selection
        view.stop()
        
        # Get updated items
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_holiday_items(view.holiday, owned_ids)
        
        if not items:
            # All items owned, go back to categories
            conf = view.cog.db.get_conf(interaction.guild)
            clothing_view = ClothingShopView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                active_holiday=conf.active_holiday
            )
            embed = clothing_view.build_embed()
        else:
            clothing_view = HolidayItemsView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                holiday=view.holiday,
                items=items
            )
            embed = clothing_view.build_embed()
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=clothing_view)
        clothing_view.message = view.message


class HolidayPostPurchaseView(View):
    """View shown after a successful holiday purchase."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        holiday: str
    ) -> None:
        super().__init__(timeout=60)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.holiday = holiday
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Continue shopping options
        self.add_item(ContinueHolidayShoppingButton())
        self.add_item(BackToCategoriesButton())
        self.add_item(CloseClothingShopButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ContinueHolidayShoppingButton(Button):
    """Button to continue shopping holiday items."""

    def __init__(self):
        super().__init__(
            label="More Holiday Items",
            emoji="🎄",
            style=discord.ButtonStyle.primary,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HolidayPostPurchaseView = self.view
        view.stop()
        
        # Get updated holiday items
        owned_ids = get_owned_item_ids(view.user_data)
        items = get_holiday_items(view.holiday, owned_ids)
        
        holiday_info = HOLIDAY_DISPLAY.get(view.holiday, {"name": view.holiday.title(), "emoji": "🎄"})
        
        if not items:
            # All items owned, go to categories
            await interaction.response.send_message(
                f"🎉 You already own all **{holiday_info['name']}** items! Amazing!",
                ephemeral=True
            )
            
            conf = view.cog.db.get_conf(interaction.guild)
            clothing_view = ClothingShopView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                active_holiday=conf.active_holiday
            )
            embed = clothing_view.build_embed()
        else:
            clothing_view = HolidayItemsView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                holiday=view.holiday,
                items=items
            )
            embed = clothing_view.build_embed()
        
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=clothing_view)
        clothing_view.message = view.message


# =============================================================================
# DAILY FREEBIE BUTTON
# =============================================================================

class DailyFreebieButton(Button):
    """Button to claim daily free clothing item."""

    def __init__(self, disabled: bool = False, label: str = "Daily Freebie"):
        super().__init__(
            label=label,
            emoji="🎁",
            style=discord.ButtonStyle.success if not disabled else discord.ButtonStyle.secondary,
            row=1,
            disabled=disabled
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        from ..database.freebie import claim_daily_freebie, get_freebie_button_state
        
        view: ClothingShopView = self.view
        
        # Attempt to claim the daily freebie
        success, message, item_data, petcoin_awarded = claim_daily_freebie(
            view.user_data,
            view.guild_settings
        )
        
        if not success:
            # Already claimed or error
            await interaction.response.send_message(
                f"🎁 {message}",
                ephemeral=True
            )
            return
        
        # Successful claim - save and build response
        view.cog.schedule_save()
        
        # Build result embed
        if petcoin_awarded > 0:
            # Duplicate item - got petcoins
            embed = discord.Embed(
                title="🎁 Daily Freebie - Duplicate!",
                description=message,
                color=discord.Color.gold()
            )
            embed.add_field(
                name="💰 Petcoin Balance",
                value=f"**{view.user_data.current_petcoin:,}** Petcoins",
                inline=False
            )
        else:
            # New item received
            embed = discord.Embed(
                title="🎁 Daily Freebie Claimed!",
                description=message,
                color=discord.Color.green()
            )
            if item_data:
                embed.add_field(
                    name="📦 Item Details",
                    value=f"Category: {item_data.get('category', 'Unknown').title()}\n"
                          f"Value: **{item_data.get('value', 0):,}** Petcoins",
                    inline=False
                )
        
        total_freebies = getattr(view.user_data, 'total_freebies_claimed', 0)
        embed.set_footer(text=f"Total freebies claimed: {total_freebies}")
        
        # Add user info to embed since it's public
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Update button state to disabled
        disabled, label = get_freebie_button_state(view.user_data, view.guild_settings)
        self.disabled = disabled
        self.label = label
        self.style = discord.ButtonStyle.secondary
        
        # Update the view message
        if view.message:
            try:
                shop_embed = view.build_embed()
                shop_embed.set_author(
                    name=interaction.user.display_name,
                    icon_url=interaction.user.display_avatar.url
                )
                await view.message.edit(embed=shop_embed, view=view)
            except discord.NotFound:
                pass


# =============================================================================
# NAVIGATION BUTTONS
# =============================================================================

class BackToShopButton(Button):
    """Button to return to the main supply shop."""

    def __init__(self):
        super().__init__(
            label="Back to Shop",
            emoji="🛒",
            style=discord.ButtonStyle.secondary,
            row=2
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: View = self.view
        view.stop()
        
        # Import here to avoid circular imports
        from .home_views import SupplyShopView
        
        shop_view = SupplyShopView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id
        )
        
        embed = shop_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        try:
            await interaction.response.edit_message(embed=embed, view=shop_view)
            shop_view.message = view.message
        except discord.NotFound:
            pass  # Interaction expired or message deleted


class BackToCategoriesButton(Button):
    """Button to return to category selection."""

    def __init__(self):
        super().__init__(
            label="Back to Categories",
            emoji="📋",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: View = self.view
        view.stop()
        
        conf = view.cog.db.get_conf(interaction.guild)
        clothing_view = ClothingShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=conf,
            author_id=view.author_id,
            active_holiday=conf.active_holiday
        )
        
        embed = clothing_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        try:
            await interaction.response.edit_message(embed=embed, view=clothing_view)
            clothing_view.message = view.message
        except discord.NotFound:
            pass  # Interaction expired or message deleted


class CloseClothingShopButton(Button):
    """Button to close the clothing shop view."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=2
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: View = self.view
        view.stop()
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)
