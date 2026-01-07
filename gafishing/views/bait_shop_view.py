"""
Bait Shop view - Buy and sell fishing supplies.
"""

import discord
from typing import TYPE_CHECKING, Optional, List, Dict, Any

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView, BackToMenuMixin
from ..databases.items import (
    RODS_DATABASE, 
    LURES_DATABASE, 
    HATS_DATABASE, 
    COATS_DATABASE, 
    BOOTS_DATABASE
)


class BaitShopView(BackToMenuMixin, BaseView):
    """Main view for the bait shop."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member
    ):
        super().__init__(cog=cog, author=author)
    
    async def create_shop_embed(self) -> discord.Embed:
        """Create the bait shop embed."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        embed = discord.Embed(
            title="🏪 Bait & Tackle Shop",
            description=(
                "Welcome to the Greenacres Bait & Tackle Shop!\n"
                "Browse our selection of fishing gear and apparel.\n\n"
                f"💰 Your FishPoints: **{user_data.total_fishpoints:,}**\n"
                f"🏆 FishMaster Tokens: **{user_data.current_fishmaster_tokens}**"
            ),
            color=discord.Color.orange()
        )
        
        # Rods summary
        rod_count = len(RODS_DATABASE)
        rod_prices = [r["price"] for r in RODS_DATABASE.values()]
        embed.add_field(
            name="🎣 Rods",
            value=f"{rod_count} available\n{min(rod_prices):,} - {max(rod_prices):,} FP",
            inline=True
        )
        
        # Lures summary
        lure_count = len(LURES_DATABASE)
        lure_prices = [l["price"] for l in LURES_DATABASE.values()]
        embed.add_field(
            name="🐛 Lures & Bait",
            value=f"{lure_count} available\n{min(lure_prices):,} - {max(lure_prices):,} FP",
            inline=True
        )
        
        # Apparel summary
        apparel_count = len(HATS_DATABASE) + len(COATS_DATABASE) + len(BOOTS_DATABASE)
        embed.add_field(
            name="👕 Apparel",
            value=f"{apparel_count} available\nHats, Coats & Boots",
            inline=True
        )
        
        embed.set_footer(text="Select a category to browse items!")
        
        return embed
    
    @discord.ui.button(label="Rods", style=discord.ButtonStyle.primary, emoji="🎣", row=0)
    async def buy_rods(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Browse rods for purchase."""
        view = RodShopView(cog=self.cog, author=self.author)
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Lures & Bait", style=discord.ButtonStyle.primary, emoji="🐛", row=0)
    async def buy_lures(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Browse lures subcategories."""
        view = LuresCategoryView(cog=self.cog, author=self.author)
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Apparel", style=discord.ButtonStyle.primary, emoji="👕", row=0)
    async def buy_apparel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Browse apparel subcategories."""
        view = ApparelCategoryView(cog=self.cog, author=self.author)
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Sell Fish", style=discord.ButtonStyle.success, emoji="💰", row=1)
    async def sell_fish(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Sell your caught fish."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        fish_count = len(user_data.current_fish_inventory)
        if fish_count == 0:
            await interaction.response.send_message(
                "🐟 You don't have any fish to sell!",
                ephemeral=True
            )
        else:
            # Calculate total value - look up from database if not stored (backward compatibility)
            from ..databases.fish import FISH_DATABASE
            total_value = 0
            for f in user_data.current_fish_inventory:
                if "fishpoints" in f:
                    total_value += f["fishpoints"]
                else:
                    fish_data = FISH_DATABASE.get(f.get("fish_id", ""), {})
                    total_value += fish_data.get("base_fishpoints", 10)
            view = SellFishConfirmView(
                cog=self.cog, 
                author=self.author,
                fish_count=fish_count,
                total_value=total_value
            )
            embed = view.create_embed()
            await self.stop_and_update(interaction, view, embed)


class BackToShopMixin:
    """Mixin to add a Back to Shop button."""
    
    @discord.ui.button(label="Back to Shop", style=discord.ButtonStyle.secondary, emoji="🔙", row=4)
    async def back_to_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to the main bait shop."""
        view = BaitShopView(cog=self.cog, author=self.author)
        embed = await view.create_shop_embed()
        await self.stop_and_update(interaction, view, embed)


# ==================== LURES CATEGORY ====================

class LuresCategoryView(BackToShopMixin, BaseView):
    """View for selecting lure water type category."""
    
    def __init__(self, cog: "GreenacresFishing", author: discord.Member):
        super().__init__(cog=cog, author=author)
    
    async def create_embed(self) -> discord.Embed:
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        freshwater = {k: v for k, v in LURES_DATABASE.items() if v["water_type"] == "freshwater"}
        saltwater = {k: v for k, v in LURES_DATABASE.items() if v["water_type"] == "saltwater"}
        both = {k: v for k, v in LURES_DATABASE.items() if v["water_type"] == "both"}
        
        embed = discord.Embed(
            title="🐛 Lures & Bait",
            description=(
                "Select a water type to browse lures.\n\n"
                f"💰 Your FishPoints: **{user_data.total_fishpoints:,}**"
            ),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🏞️ Freshwater",
            value=f"{len(freshwater)} lures available",
            inline=True
        )
        embed.add_field(
            name="🌊 Saltwater",
            value=f"{len(saltwater)} lures available",
            inline=True
        )
        embed.add_field(
            name="♾️ Universal",
            value=f"{len(both)} lures available",
            inline=True
        )
        
        return embed
    
    @discord.ui.button(label="Freshwater", style=discord.ButtonStyle.primary, emoji="🏞️", row=0)
    async def freshwater_lures(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = {k: v for k, v in LURES_DATABASE.items() if v["water_type"] == "freshwater"}
        view = ItemShopView(cog=self.cog, author=self.author, items=items, category="Freshwater Lures", slot="lure")
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Saltwater", style=discord.ButtonStyle.primary, emoji="🌊", row=0)
    async def saltwater_lures(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = {k: v for k, v in LURES_DATABASE.items() if v["water_type"] == "saltwater"}
        view = ItemShopView(cog=self.cog, author=self.author, items=items, category="Saltwater Lures", slot="lure")
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Universal", style=discord.ButtonStyle.primary, emoji="♾️", row=0)
    async def universal_lures(self, interaction: discord.Interaction, button: discord.ui.Button):
        items = {k: v for k, v in LURES_DATABASE.items() if v["water_type"] == "both"}
        view = ItemShopView(cog=self.cog, author=self.author, items=items, category="Universal Lures", slot="lure")
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)


# ==================== APPAREL CATEGORY ====================

class ApparelCategoryView(BackToShopMixin, BaseView):
    """View for selecting apparel category."""
    
    def __init__(self, cog: "GreenacresFishing", author: discord.Member):
        super().__init__(cog=cog, author=author)
    
    async def create_embed(self) -> discord.Embed:
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        embed = discord.Embed(
            title="👕 Apparel",
            description=(
                "Select a category to browse apparel.\n\n"
                f"💰 Your FishPoints: **{user_data.total_fishpoints:,}**\n"
                f"🏆 FishMaster Tokens: **{user_data.current_fishmaster_tokens}**\n\n"
                "*FishMaster items require tokens to purchase!*"
            ),
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🧢 Hats",
            value=f"{len(HATS_DATABASE)} available",
            inline=True
        )
        embed.add_field(
            name="🧥 Coats",
            value=f"{len(COATS_DATABASE)} available",
            inline=True
        )
        embed.add_field(
            name="👢 Boots",
            value=f"{len(BOOTS_DATABASE)} available",
            inline=True
        )
        
        return embed
    
    @discord.ui.button(label="Hats", style=discord.ButtonStyle.primary, emoji="🧢", row=0)
    async def browse_hats(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ItemShopView(cog=self.cog, author=self.author, items=HATS_DATABASE, category="Hats", slot="hat")
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Coats", style=discord.ButtonStyle.primary, emoji="🧥", row=0)
    async def browse_coats(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ItemShopView(cog=self.cog, author=self.author, items=COATS_DATABASE, category="Coats", slot="coat")
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Boots", style=discord.ButtonStyle.primary, emoji="👢", row=0)
    async def browse_boots(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = ItemShopView(cog=self.cog, author=self.author, items=BOOTS_DATABASE, category="Boots", slot="boots")
        embed = await view.create_embed()
        await self.stop_and_update(interaction, view, embed)


# ==================== RODS SHOP ====================

class RodShopView(BackToShopMixin, BaseView):
    """View for browsing and purchasing rods."""
    
    def __init__(self, cog: "GreenacresFishing", author: discord.Member):
        super().__init__(cog=cog, author=author)
        self._add_rod_select()
    
    def _add_rod_select(self):
        """Add the rod selection dropdown."""
        options = []
        for rod_id, rod_data in RODS_DATABASE.items():
            price = rod_data["price"]
            price_str = "Free" if price == 0 else f"{price:,} FP"
            options.append(discord.SelectOption(
                label=rod_data["name"],
                value=rod_id,
                description=f"{price_str} | {rod_data['rarity'].title()}",
                emoji="🎣"
            ))
        
        select = discord.ui.Select(
            placeholder="Select a rod to purchase...",
            options=options,
            row=0
        )
        select.callback = self._rod_selected
        self.add_item(select)
    
    async def _rod_selected(self, interaction: discord.Interaction):
        """Handle rod selection."""
        rod_id = interaction.data["values"][0]
        rod_data = RODS_DATABASE[rod_id]
        
        # For rods, quantity is always 1
        view = PurchaseConfirmView(
            cog=self.cog,
            author=self.author,
            item_id=rod_id,
            item_data=rod_data,
            quantity=1,
            slot="rod"
        )
        embed = view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    async def create_embed(self) -> discord.Embed:
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        embed = discord.Embed(
            title="🎣 Rods",
            description=(
                "Select a rod from the dropdown below.\n\n"
                f"💰 Your FishPoints: **{user_data.total_fishpoints:,}**"
            ),
            color=discord.Color.green()
        )
        
        # List all rods with details
        for rod_id, rod_data in RODS_DATABASE.items():
            price = rod_data["price"]
            price_str = "Free" if price == 0 else f"{price:,} FP"
            embed.add_field(
                name=f"{rod_data['name']} ({rod_data['rarity'].title()})",
                value=(
                    f"💰 {price_str} | ⚙️ {rod_data['durability']} durability\n"
                    f"🌊 {rod_data['water_type'].replace('_', ' ').title()}\n"
                    f"*{rod_data['description']}*"
                ),
                inline=True
            )
        
        return embed


# ==================== GENERIC ITEM SHOP ====================

class ItemShopView(BackToShopMixin, BaseView):
    """Generic view for browsing items with a dropdown."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing", 
        author: discord.Member, 
        items: Dict[str, Any],
        category: str,
        slot: str
    ):
        super().__init__(cog=cog, author=author)
        self.items = items
        self.category = category
        self.slot = slot
        self._add_item_select()
    
    def _add_item_select(self):
        """Add the item selection dropdown."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        has_token = user_data.current_fishmaster_tokens > 0
        
        options = []
        for item_id, item_data in self.items.items():
            price = item_data["price"]
            requires_token = item_data.get("fishmaster_token_cost", 0) > 0
            
            # Build description
            if requires_token:
                desc = f"{price:,} FP + 🏆 Token | {item_data['rarity'].title()}"
            else:
                desc = f"{price:,} FP | {item_data['rarity'].title()}"
            
            # FishMaster items are greyed out if no tokens
            if requires_token and not has_token:
                options.append(discord.SelectOption(
                    label=f"🔒 {item_data['name']}",
                    value=f"locked_{item_id}",
                    description="Requires FishMaster Token!",
                    emoji="🏆"
                ))
            else:
                emoji = "🏆" if requires_token else "✨"
                options.append(discord.SelectOption(
                    label=item_data["name"],
                    value=item_id,
                    description=desc,
                    emoji=emoji
                ))
        
        select = discord.ui.Select(
            placeholder="Select an item to purchase...",
            options=options,
            row=0
        )
        select.callback = self._item_selected
        self.add_item(select)
    
    async def _item_selected(self, interaction: discord.Interaction):
        """Handle item selection."""
        item_id = interaction.data["values"][0]
        
        # Check if locked item
        if item_id.startswith("locked_"):
            await interaction.response.send_message(
                "🔒 This item requires a **FishMaster Token** to purchase!\n"
                "Earn tokens by catching record-breaking fish!",
                ephemeral=True
            )
            return
        
        item_data = self.items[item_id]
        
        # For lures, ask for quantity; for clothing, quantity is 1
        if self.slot == "lure":
            # Show quantity modal
            modal = QuantityModal(
                cog=self.cog,
                author=self.author,
                item_id=item_id,
                item_data=item_data,
                slot=self.slot,
                view=self
            )
            await interaction.response.send_modal(modal)
        else:
            # For clothing, quantity is always 1
            view = PurchaseConfirmView(
                cog=self.cog,
                author=self.author,
                item_id=item_id,
                item_data=item_data,
                quantity=1,
                slot=self.slot
            )
            embed = view.create_embed()
            await self.stop_and_update(interaction, view, embed)
    
    async def create_embed(self) -> discord.Embed:
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        has_token = user_data.current_fishmaster_tokens > 0
        
        embed = discord.Embed(
            title=f"🛒 {self.category}",
            description=(
                "Select an item from the dropdown below.\n\n"
                f"💰 Your FishPoints: **{user_data.total_fishpoints:,}**\n"
                f"🏆 FishMaster Tokens: **{user_data.current_fishmaster_tokens}**"
            ),
            color=discord.Color.gold()
        )
        
        # List all items with details
        for item_id, item_data in self.items.items():
            price = item_data["price"]
            requires_token = item_data.get("fishmaster_token_cost", 0) > 0
            
            # Format price
            if requires_token:
                price_str = f"{price:,} FP + 🏆 Token"
                if not has_token:
                    name = f"🔒 {item_data['name']} ({item_data['rarity'].title()})"
                else:
                    name = f"🏆 {item_data['name']} ({item_data['rarity'].title()})"
            else:
                price_str = f"{price:,} FP"
                name = f"{item_data['name']} ({item_data['rarity'].title()})"
            
            # Build value string
            value_parts = [f"💰 {price_str}"]
            if "luck_bonus" in item_data:
                value_parts.append(f"🍀 +{item_data['luck_bonus']} Luck")
            value_parts.append(f"*{item_data['description']}*")
            
            embed.add_field(
                name=name,
                value="\n".join(value_parts),
                inline=True
            )
        
        return embed


# ==================== QUANTITY MODAL ====================

class QuantityModal(discord.ui.Modal, title="Enter Quantity"):
    """Modal for entering purchase quantity."""
    
    quantity_input = discord.ui.TextInput(
        label="Quantity",
        placeholder="Enter a number (e.g., 10)",
        default="1",
        min_length=1,
        max_length=5
    )
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        item_id: str,
        item_data: Dict[str, Any],
        slot: str,
        view: BaseView
    ):
        super().__init__()
        self.cog = cog
        self.author = author
        self.item_id = item_id
        self.item_data = item_data
        self.slot = slot
        self.parent_view = view
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity = int(self.quantity_input.value)
            if quantity < 1:
                raise ValueError("Quantity must be at least 1")
            if quantity > 9999:
                raise ValueError("Maximum quantity is 9999")
        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Invalid quantity: {e}",
                ephemeral=True
            )
            return
        
        # Show purchase confirmation
        view = PurchaseConfirmView(
            cog=self.cog,
            author=self.author,
            item_id=self.item_id,
            item_data=self.item_data,
            quantity=quantity,
            slot=self.slot
        )
        embed = view.create_embed()
        
        self.parent_view.stop()
        view.message = self.parent_view.message
        await interaction.response.edit_message(embed=embed, view=view)


# ==================== PURCHASE CONFIRMATION ====================

class PurchaseConfirmView(BaseView):
    """View for confirming a purchase."""
    
    def __init__(
        self,
        cog: "GreenacresFishing",
        author: discord.Member,
        item_id: str,
        item_data: Dict[str, Any],
        quantity: int,
        slot: str
    ):
        super().__init__(cog=cog, author=author)
        self.item_id = item_id
        self.item_data = item_data
        self.quantity = quantity
        self.slot = slot
        self.total_cost = item_data["price"] * quantity
        self.token_cost = item_data.get("fishmaster_token_cost", 0)
    
    def create_embed(self) -> discord.Embed:
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        can_afford_fp = user_data.total_fishpoints >= self.total_cost
        can_afford_token = user_data.current_fishmaster_tokens >= self.token_cost
        can_afford = can_afford_fp and can_afford_token
        
        if can_afford:
            color = discord.Color.green()
            status = "✅ You can afford this purchase!"
        else:
            color = discord.Color.red()
            if not can_afford_fp:
                status = f"❌ Not enough FishPoints! You need {self.total_cost - user_data.total_fishpoints:,} more."
            else:
                status = "❌ Not enough FishMaster Tokens!"
        
        embed = discord.Embed(
            title="🛒 Confirm Purchase",
            description=status,
            color=color
        )
        
        # Item details
        embed.add_field(
            name="Item",
            value=f"**{self.item_data['name']}**\n*{self.item_data['description']}*",
            inline=False
        )
        
        embed.add_field(
            name="Quantity",
            value=str(self.quantity),
            inline=True
        )
        
        cost_str = f"{self.total_cost:,} FP"
        if self.token_cost > 0:
            cost_str += f" + {self.token_cost} 🏆 Token"
        embed.add_field(
            name="Total Cost",
            value=cost_str,
            inline=True
        )
        
        embed.add_field(
            name="Your Balance",
            value=f"💰 {user_data.total_fishpoints:,} FP\n🏆 {user_data.current_fishmaster_tokens} Tokens",
            inline=True
        )
        
        return embed
    
    @discord.ui.button(label="Confirm Purchase", style=discord.ButtonStyle.success, emoji="✅", row=0)
    async def confirm_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm and complete the purchase."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        # Final check for funds
        if user_data.total_fishpoints < self.total_cost:
            await interaction.response.send_message(
                f"❌ Not enough FishPoints! You need {self.total_cost:,} but only have {user_data.total_fishpoints:,}.",
                ephemeral=True
            )
            return
        
        if user_data.current_fishmaster_tokens < self.token_cost:
            await interaction.response.send_message(
                "❌ Not enough FishMaster Tokens!",
                ephemeral=True
            )
            return
        
        # Deduct cost
        user_data.total_fishpoints -= self.total_cost
        if self.token_cost > 0:
            user_data.current_fishmaster_tokens -= self.token_cost
        
        # Add item(s) to inventory
        if self.slot == "rod":
            # Add rod with full durability
            user_data.current_rod_inventory.append({
                "rod_id": self.item_id,
                "durability": self.item_data["durability"],
                "equipped": False
            })
        elif self.slot == "lure":
            # Check if we already have this lure and add to quantity
            existing = None
            for lure in user_data.current_lure_inventory:
                if lure.get("lure_id") == self.item_id:
                    existing = lure
                    break
            
            # Get lure info for uses
            from ..databases.items import LURES_DATABASE
            lure_info = LURES_DATABASE.get(self.item_id, {})
            uses_per_item = lure_info.get("uses", 1)
            
            if existing:
                existing["quantity"] = existing.get("quantity", 1) + self.quantity
                existing["remaining_uses"] = existing.get("remaining_uses", 0) + (self.quantity * uses_per_item)
                existing["uses_per_item"] = uses_per_item
            else:
                user_data.current_lure_inventory.append({
                    "lure_id": self.item_id,
                    "quantity": self.quantity,
                    "remaining_uses": self.quantity * uses_per_item,
                    "uses_per_item": uses_per_item,
                    "equipped": False
                })
        elif self.slot in ["hat", "coat", "boots"]:
            # Add clothing item
            user_data.current_clothing_inventory.append({
                "clothing_id": self.item_id,
                "slot": self.slot,
                "equipped": False
            })
        
        # Save changes
        self.cog.save()
        
        # Show success and return to shop
        cost_str = f"{self.total_cost:,} FP"
        if self.token_cost > 0:
            cost_str += f" + {self.token_cost} 🏆 Token"
        
        embed = discord.Embed(
            title="✅ Purchase Complete!",
            description=(
                f"You purchased **{self.quantity}x {self.item_data['name']}** for {cost_str}!\n\n"
                f"💰 Remaining FishPoints: **{user_data.total_fishpoints:,}**"
            ),
            color=discord.Color.green()
        )
        
        # Create new shop view
        view = BaitShopView(cog=self.cog, author=self.author)
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def cancel_purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the purchase and return to shop."""
        view = BaitShopView(cog=self.cog, author=self.author)
        embed = await view.create_shop_embed()
        await self.stop_and_update(interaction, view, embed)


# ==================== SELL FISH CONFIRMATION ====================

class SellFishConfirmView(BaseView):
    """View for confirming selling all fish."""
    
    def __init__(
        self,
        cog: "GreenacresFishing",
        author: discord.Member,
        fish_count: int,
        total_value: int
    ):
        super().__init__(cog=cog, author=author)
        self.fish_count = fish_count
        self.total_value = total_value
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="💰 Sell All Fish",
            description=(
                f"You have **{self.fish_count}** fish in your inventory.\n"
                f"Total value: **{self.total_value:,} FishPoints**\n\n"
                "Do you want to sell all your fish?"
            ),
            color=discord.Color.gold()
        )
        return embed
    
    @discord.ui.button(label="Sell All", style=discord.ButtonStyle.success, emoji="💰", row=0)
    async def confirm_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm and sell all fish."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        # Calculate value again (in case inventory changed)
        # Look up fishpoints from database if not stored in fish entry (backward compatibility)
        from ..databases.fish import FISH_DATABASE
        total_value = 0
        for f in user_data.current_fish_inventory:
            if "fishpoints" in f:
                total_value += f["fishpoints"]
            else:
                # Legacy fish without stored fishpoints - look up from database
                fish_data = FISH_DATABASE.get(f.get("fish_id", ""), {})
                total_value += fish_data.get("base_fishpoints", 10)
        fish_count = len(user_data.current_fish_inventory)
        
        if fish_count == 0:
            await interaction.response.send_message(
                "❌ You don't have any fish to sell!",
                ephemeral=True
            )
            return
        
        # Add FishPoints and clear inventory
        user_data.total_fishpoints += total_value
        user_data.total_fish_sold += fish_count
        
        # Update most fishpoints ever
        if user_data.total_fishpoints > user_data.most_fishpoints_ever:
            user_data.most_fishpoints_ever = user_data.total_fishpoints
        
        user_data.current_fish_inventory.clear()
        
        # Save changes
        self.cog.save()
        
        embed = discord.Embed(
            title="✅ Fish Sold!",
            description=(
                f"You sold **{fish_count}** fish for **{total_value:,} FishPoints**!\n\n"
                f"💰 New Balance: **{user_data.total_fishpoints:,} FP**"
            ),
            color=discord.Color.green()
        )
        
        # Return to shop
        view = BaitShopView(cog=self.cog, author=self.author)
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=0)
    async def cancel_sell(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel and return to shop."""
        view = BaitShopView(cog=self.cog, author=self.author)
        embed = await view.create_shop_embed()
        await self.stop_and_update(interaction, view, embed)
