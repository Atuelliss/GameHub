"""
Treats shop views for purchasing and using pet treats.
"""

import time
import discord
from discord.ui import View, Button, Select
from typing import TYPE_CHECKING, Optional, List, Dict

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings

from ..database.petshop import SHOP_TREATS, get_treat, get_treats_by_stat, get_all_treats
from ..common.constants import TREAT_MAX_STACK, SHOP_TREAT_COOLDOWN_HOURS

# Max stack for legendary Golden Ambrosia
AMBROSIA_MAX_STACK = 3


# =============================================================================
# STAT CATEGORIES FOR TREATS
# =============================================================================

TREAT_STAT_CATEGORIES = {
    "Hunger": {"stat": "hunger", "emoji": "🍖"},
    "Happiness": {"stat": "happiness", "emoji": "🎾"},
    "Cleanliness": {"stat": "cleanliness", "emoji": "✨"},
    "Energy": {"stat": "energy", "emoji": "💤"},
    "Health": {"stat": "health", "emoji": "❤️"},
}


# =============================================================================
# TREATS SHOP VIEW (from Supply Shop)
# =============================================================================

class TreatsShopView(View):
    """View for purchasing treats from the Supply Shop."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        author: discord.Member
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.author = author
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        self._setup_buttons()

    def _setup_buttons(self) -> None:
        """Set up the view buttons."""
        self.clear_items()
        
        # Row 0: Stat category dropdown
        self.add_item(TreatStatSelect())
        
        # Row 1: Navigation
        self.add_item(BackToSupplyShopButton())
        self.add_item(CloseTreatsShopButton())

        # Row 2: Legendary item
        self.add_item(BuyAmbrosiaButton(self.user_data))

    def build_embed(self) -> discord.Embed:
        """Build the main treats shop embed."""
        # Count treats owned
        total_owned = sum(self.user_data.current_treat_inventory.values())
        
        embed = discord.Embed(
            title="🍖 Treats Shop",
            description=(
                "Purchase treats to give your pet a stat boost!\n\n"
                "💰 **Your Petcoin:** {petcoin:,}\n"
                "🎒 **Treats Owned:** {treats_owned}\n\n"
                "**All treats also give +5 Bond!**\n\n"
                "Select a stat category below to browse treats."
            ).format(
                petcoin=self.user_data.current_petcoin,
                treats_owned=total_owned
            ),
            color=discord.Color.orange()
        )
        
        # Show categories with preview
        for cat_name, cat_info in TREAT_STAT_CATEGORIES.items():
            stat = cat_info["stat"]
            emoji = cat_info["emoji"]
            treats = get_treats_by_stat(stat)
            
            # Get owned count for this stat
            owned_count = sum(
                self.user_data.current_treat_inventory.get(t["id"], 0)
                for t in treats
            )
            
            # Build price range
            costs = [t["cost"] for t in treats]
            price_range = f"{min(costs)}-{max(costs)} 💰"
            
            embed.add_field(
                name=f"{emoji} {cat_name}",
                value=f"Owned: {owned_count} | {price_range}",
                inline=True
            )
        
        embed.set_footer(text=f"Max {TREAT_MAX_STACK} of each treat type")

        # Legendary section
        ambrosia = SHOP_TREATS.get("golden_ambrosia")
        if ambrosia:
            owned = self.user_data.current_treat_inventory.get("golden_ambrosia", 0)
            at_max = owned >= AMBROSIA_MAX_STACK
            stock_str = f"Owned: {owned}/{AMBROSIA_MAX_STACK}" + (" *(MAX)*" if at_max else "")
            embed.add_field(
                name="🍯 Golden Ambrosia — ✨ Legendary",
                value=(
                    f"*{ambrosia['description']}*\n"
                    f"**Cost:** {ambrosia['cost']:,} 💰 | **{stock_str}**"
                ),
                inline=False
            )

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


class TreatStatSelect(Select):
    """Dropdown to select which stat's treats to view."""

    def __init__(self):
        options = []
        for cat_name, cat_info in TREAT_STAT_CATEGORIES.items():
            options.append(discord.SelectOption(
                label=cat_name,
                emoji=cat_info["emoji"],
                description=f"Browse {cat_name.lower()} treats",
                value=cat_info["stat"]
            ))
        
        super().__init__(
            placeholder="Select a stat category...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TreatsShopView = self.view
        selected_stat = self.values[0]
        
        # Create stat-specific view
        view.stop()
        
        stat_view = TreatStatShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            author=view.author,
            stat=selected_stat
        )
        
        embed = stat_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=stat_view)
        stat_view.message = view.message


class BackToSupplyShopButton(Button):
    """Button to return to Supply Shop."""

    def __init__(self):
        super().__init__(
            label="Back to Shop",
            emoji="🛒",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TreatsShopView = self.view
        view.stop()
        
        from .home_views import SupplyShopView
        
        shop_view = SupplyShopView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            guild_settings=view.guild_settings,
            author=view.author
        )
        
        embed = shop_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=shop_view)
        shop_view.message = view.message


class CloseTreatsShopButton(Button):
    """Button to close the treats shop."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TreatsShopView = self.view
        view.stop()
        await interaction.response.edit_message(view=None)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


# =============================================================================
# STAT-SPECIFIC TREAT SHOP VIEW
# =============================================================================

class TreatStatShopView(View):
    """View for browsing treats of a specific stat."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        author: discord.Member,
        stat: str
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.author = author
        self.stat = stat
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        self._setup_buttons()

    def _setup_buttons(self) -> None:
        """Set up the view buttons."""
        self.clear_items()
        
        # Row 0: Treat selection dropdown
        self.add_item(TreatSelect(self.stat, self.user_data))
        
        # Row 1: Navigation
        self.add_item(BackToTreatsShopButton())
        self.add_item(CloseTreatsShopButton())

    def build_embed(self) -> discord.Embed:
        """Build the stat-specific treats embed."""
        # Get stat display info
        stat_info = None
        stat_display = self.stat.title()
        stat_emoji = "🍖"
        for cat_name, info in TREAT_STAT_CATEGORIES.items():
            if info["stat"] == self.stat:
                stat_display = cat_name
                stat_emoji = info["emoji"]
                break
        
        treats = get_treats_by_stat(self.stat)
        
        embed = discord.Embed(
            title=f"{stat_emoji} {stat_display} Treats",
            description=(
                f"💰 **Your Petcoin:** {self.user_data.current_petcoin:,}\n\n"
                "Select a treat from the dropdown to purchase.\n"
                "**All treats also give +5 Bond!**"
            ),
            color=discord.Color.orange()
        )
        
        # Sort by tier order
        tier_order = {"low": 0, "medium": 1, "high": 2}
        treats.sort(key=lambda t: tier_order.get(t["tier"], 99))
        
        for treat in treats:
            treat_id = treat["id"]
            owned = self.user_data.current_treat_inventory.get(treat_id, 0)
            
            # Build value string
            tier_display = treat["tier"].title()
            effect_display = f"+{treat['effect']} {stat_display}"
            
            # Check if at max stack
            at_max = owned >= TREAT_MAX_STACK
            stock_status = f"Owned: {owned}/{TREAT_MAX_STACK}" + (" (MAX)" if at_max else "")
            
            embed.add_field(
                name=f"{treat['emoji']} {treat['name']} ({tier_display})",
                value=(
                    f"**Effect:** {effect_display} (+5 Bond)\n"
                    f"**Cost:** {treat['cost']} 💰\n"
                    f"**{stock_status}**"
                ),
                inline=True
            )
        
        embed.set_footer(text=f"Max {TREAT_MAX_STACK} of each treat type")
        
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


class TreatSelect(Select):
    """Dropdown to select a treat to purchase."""

    def __init__(self, stat: str, user_data: "User"):
        self.stat = stat
        treats = get_treats_by_stat(stat)
        
        # Sort by tier order
        tier_order = {"low": 0, "medium": 1, "high": 2}
        treats.sort(key=lambda t: tier_order.get(t["tier"], 99))
        
        options = []
        for treat in treats:
            treat_id = treat["id"]
            owned = user_data.current_treat_inventory.get(treat_id, 0)
            at_max = owned >= TREAT_MAX_STACK
            
            options.append(discord.SelectOption(
                label=f"{treat['name']} ({treat['tier'].title()})",
                emoji=treat["emoji"],
                description=f"+{treat['effect']} {stat.title()} | {treat['cost']} 💰 | Owned: {owned}",
                value=treat_id,
                default=False
            ))
        
        super().__init__(
            placeholder="Select a treat to purchase...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TreatStatShopView = self.view
        treat_id = self.values[0]
        
        treat = get_treat(treat_id)
        if not treat:
            await interaction.response.send_message(
                "❌ Treat not found!",
                ephemeral=True
            )
            return
        
        # Check if at max stack
        owned = view.user_data.current_treat_inventory.get(treat_id, 0)
        if owned >= TREAT_MAX_STACK:
            await interaction.response.send_message(
                f"❌ You already have the maximum ({TREAT_MAX_STACK}) of this treat!",
                ephemeral=True
            )
            return
        
        # Check if user has enough petcoin
        if view.user_data.current_petcoin < treat["cost"]:
            await interaction.response.send_message(
                f"❌ Not enough Petcoin! You need {treat['cost']} 💰 but only have {view.user_data.current_petcoin:,} 💰",
                ephemeral=True
            )
            return
        
        # Show purchase confirmation
        confirm_view = TreatPurchaseConfirmView(
            parent_view=view,
            treat=treat
        )
        
        await interaction.response.send_message(
            f"🛒 **Purchase Confirmation**\n\n"
            f"{treat['emoji']} **{treat['name']}**\n"
            f"Effect: +{treat['effect']} {treat['stat'].title()} (+5 Bond)\n"
            f"Cost: **{treat['cost']}** 💰\n\n"
            f"Current balance: {view.user_data.current_petcoin:,} 💰\n"
            f"After purchase: {view.user_data.current_petcoin - treat['cost']:,} 💰\n\n"
            f"Confirm purchase?",
            view=confirm_view,
            ephemeral=True
        )


class BackToTreatsShopButton(Button):
    """Button to return to main treats shop."""

    def __init__(self):
        super().__init__(
            label="Back",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TreatStatShopView = self.view
        view.stop()
        
        treats_view = TreatsShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            author=view.author
        )
        
        embed = treats_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=treats_view)
        treats_view.message = view.message


# =============================================================================
# PURCHASE CONFIRMATION VIEW
# =============================================================================

class TreatPurchaseConfirmView(View):
    """Confirmation view for treat purchase."""

    def __init__(self, parent_view: TreatStatShopView, treat: dict, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.treat = treat

    @discord.ui.button(label="Purchase", emoji="✅", style=discord.ButtonStyle.success)
    async def purchase_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Confirm purchase."""
        treat = self.treat
        user_data = self.parent_view.user_data
        treat_id = treat["id"]
        
        # Re-check conditions
        owned = user_data.current_treat_inventory.get(treat_id, 0)
        if owned >= TREAT_MAX_STACK:
            await interaction.response.edit_message(
                content=f"❌ You already have the maximum ({TREAT_MAX_STACK}) of this treat!",
                view=None
            )
            return
        
        if user_data.current_petcoin < treat["cost"]:
            await interaction.response.edit_message(
                content=f"❌ Not enough Petcoin!",
                view=None
            )
            return
        
        # Process purchase
        user_data.current_petcoin -= treat["cost"]
        user_data.current_treat_inventory[treat_id] = owned + 1
        
        # Save
        self.parent_view.cog.schedule_save()
        
        # Show success
        new_owned = user_data.current_treat_inventory.get(treat_id, 1)
        await interaction.response.edit_message(
            content=(
                f"✅ **Purchase Successful!**\n\n"
                f"{treat['emoji']} **{treat['name']}** added to inventory!\n"
                f"You now own {new_owned}/{TREAT_MAX_STACK} of this treat.\n"
                f"Remaining balance: {user_data.current_petcoin:,} 💰"
            ),
            view=None
        )
        
        # Refresh the parent view
        self.parent_view._setup_buttons()
        embed = self.parent_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        try:
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)
        except Exception:
            pass
        
        self.stop()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Cancel purchase."""
        await interaction.response.edit_message(
            content="❌ Purchase cancelled.",
            view=None
        )
        self.stop()


# =============================================================================
# INVENTORY TREATS VIEW (for using treats)
# =============================================================================

class InventoryTreatsView(View):
    """View for managing and using owned treats from inventory."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        author: discord.Member
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.author = author
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        self._setup_buttons()

    def _get_owned_treats(self) -> List[dict]:
        """Get list of treats the user owns (with counts)."""
        owned = []
        for treat_id, count in self.user_data.current_treat_inventory.items():
            if count > 0:
                treat = get_treat(treat_id)
                if treat and treat.get("treat_type") != "immortality":
                    treat["owned"] = count
                    owned.append(treat)
        
        # Sort by stat, then tier
        stat_order = {"hunger": 0, "happiness": 1, "cleanliness": 2, "energy": 3, "health": 4}
        tier_order = {"low": 0, "medium": 1, "high": 2}
        owned.sort(key=lambda t: (stat_order.get(t["stat"], 99), tier_order.get(t["tier"], 99)))
        
        return owned

    def _setup_buttons(self) -> None:
        """Set up the view buttons."""
        self.clear_items()
        
        owned_treats = self._get_owned_treats()
        
        # Row 0: Treat selection dropdown (if has treats)
        if owned_treats:
            self.add_item(UseTreatSelect(owned_treats, self.user_data))
        
        # Row 1: Navigation
        self.add_item(BackToInventoryButton())
        self.add_item(CloseTreatsButton())

        # Row 2: Special items
        ambrosia_count = self.user_data.current_treat_inventory.get("golden_ambrosia", 0)
        if ambrosia_count > 0:
            self.add_item(UseAmbrosiaButton(ambrosia_count))

    def build_embed(self) -> discord.Embed:
        """Build the inventory treats embed."""
        owned_treats = self._get_owned_treats()
        total_owned = sum(t["owned"] for t in owned_treats)
        
        # Check cooldown
        current_time = time.time()
        cooldown_remaining = 0
        on_cooldown = False
        
        if self.user_data.last_shoptreat_used > 0:
            cooldown_end = self.user_data.last_shoptreat_used + (SHOP_TREAT_COOLDOWN_HOURS * 3600)
            if current_time < cooldown_end:
                on_cooldown = True
                cooldown_remaining = int(cooldown_end - current_time)
        
        # Format cooldown
        if on_cooldown:
            hours, remainder = divmod(cooldown_remaining, 3600)
            minutes, _ = divmod(remainder, 60)
            if hours > 0:
                cooldown_str = f"⏳ Cooldown: **{hours}h {minutes}m**"
            else:
                cooldown_str = f"⏳ Cooldown: **{minutes}m**"
        else:
            cooldown_str = "✅ Ready to use a treat!"
        
        embed = discord.Embed(
            title="🍖 Your Treats",
            description=(
                f"**Treats Owned:** {total_owned}\n"
                f"{cooldown_str}\n\n"
                "Select a treat below to give to your pet."
            ),
            color=discord.Color.orange()
        )
        
        # Golden Ambrosia legendary banner (shown above regular treats if owned)
        ambrosia_count = self.user_data.current_treat_inventory.get("golden_ambrosia", 0)
        if ambrosia_count > 0:
            embed.add_field(
                name="🍯 Golden Ambrosia — ✨ Legendary",
                value=(
                    f"**Owned: {ambrosia_count}/{AMBROSIA_MAX_STACK}**\n"
                    "Grant a home pet **Immortality** — they will never die of old age.\n"
                    "Use the **Use Ambrosia** button below to select a home pet."
                ),
                inline=False
            )

        if not owned_treats:
            if ambrosia_count == 0:
                embed.add_field(
                    name="No Treats",
                    value="You don't own any treats yet!\nVisit the Supply Shop to purchase some.",
                    inline=False
                )
        else:
            # Group by stat
            by_stat: Dict[str, List[dict]] = {}
            for treat in owned_treats:
                stat = treat["stat"]
                if stat not in by_stat:
                    by_stat[stat] = []
                by_stat[stat].append(treat)
            
            # Display each stat group
            for stat, treats in by_stat.items():
                emoji = "🍖"
                for cat_name, info in TREAT_STAT_CATEGORIES.items():
                    if info["stat"] == stat:
                        emoji = info["emoji"]
                        break
                
                lines = []
                for treat in treats:
                    lines.append(
                        f"{treat['emoji']} {treat['name']} x{treat['owned']} "
                        f"(+{treat['effect']} {stat.title()})"
                    )
                
                embed.add_field(
                    name=f"{emoji} {stat.title()}",
                    value="\n".join(lines),
                    inline=True
                )
        
        # Footer
        if owned_treats and not self.user_data.current_pet:
            embed.set_footer(text="⚠️ You need an active pet to use regular treats!")
        elif owned_treats and on_cooldown:
            embed.set_footer(text=f"You can use another treat in {hours}h {minutes}m")
        else:
            embed.set_footer(text="Regular treats also give +5 Bond!")

        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your treats menu! Use the `petcord` command to open yours.",
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


class UseTreatSelect(Select):
    """Dropdown to select a treat to use."""

    def __init__(self, owned_treats: List[dict], user_data: "User"):
        options = []
        for treat in owned_treats[:25]:  # Discord limit
            options.append(discord.SelectOption(
                label=f"{treat['name']} (x{treat['owned']})",
                emoji=treat["emoji"],
                description=f"+{treat['effect']} {treat['stat'].title()} (+5 Bond)",
                value=treat["id"]
            ))
        
        super().__init__(
            placeholder="Select a treat to give your pet...",
            options=options if options else [discord.SelectOption(label="No treats", value="none")],
            disabled=not options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryTreatsView = self.view
        treat_id = self.values[0]
        
        if treat_id == "none":
            return
        
        # Check if user has a pet
        if not view.user_data.current_pet:
            await interaction.response.send_message(
                "❌ You need an active pet to use treats!",
                ephemeral=True
            )
            return
        
        # Check cooldown
        current_time = time.time()
        if view.user_data.last_shoptreat_used > 0:
            cooldown_end = view.user_data.last_shoptreat_used + (SHOP_TREAT_COOLDOWN_HOURS * 3600)
            if current_time < cooldown_end:
                remaining = int(cooldown_end - current_time)
                hours, remainder = divmod(remaining, 3600)
                minutes, _ = divmod(remainder, 60)
                time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                
                await interaction.response.send_message(
                    f"⏳ You need to wait **{time_str}** before using another treat!",
                    ephemeral=True
                )
                return
        
        treat = get_treat(treat_id)
        if not treat:
            await interaction.response.send_message(
                "❌ Treat not found!",
                ephemeral=True
            )
            return
        
        # Check if user owns this treat
        owned = view.user_data.current_treat_inventory.get(treat_id, 0)
        if owned <= 0:
            await interaction.response.send_message(
                "❌ You don't own this treat!",
                ephemeral=True
            )
            return
        
        # Show confirmation
        confirm_view = UseTreatConfirmView(
            parent_view=view,
            treat=treat
        )
        
        pet = view.user_data.current_pet
        stat = treat["stat"]
        current_stat = getattr(pet, stat, 0)
        new_stat = min(100, current_stat + treat["effect"])
        current_bond = pet.bond
        new_bond = current_bond + 5
        
        await interaction.response.send_message(
            f"🍖 **Use Treat Confirmation**\n\n"
            f"{treat['emoji']} **{treat['name']}**\n\n"
            f"**Effect on {pet.name}:**\n"
            f"• {stat.title()}: {int(current_stat)} → {int(new_stat)} (+{treat['effect']})\n"
            f"• Bond: {int(current_bond)} → {int(new_bond)} (+5)\n\n"
            f"⚠️ **Warning:** You won't be able to use another treat for **{SHOP_TREAT_COOLDOWN_HOURS} hours**!\n\n"
            f"Do you want to give this treat to {pet.name}?",
            view=confirm_view,
            ephemeral=True
        )


class UseTreatConfirmView(View):
    """Confirmation view for using a treat."""

    def __init__(self, parent_view: InventoryTreatsView, treat: dict, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.treat = treat

    @discord.ui.button(label="Use Treat", emoji="🍖", style=discord.ButtonStyle.success)
    async def use_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Use the treat."""
        treat = self.treat
        user_data = self.parent_view.user_data
        treat_id = treat["id"]
        pet = user_data.current_pet
        
        # Re-check conditions
        if not pet:
            await interaction.response.edit_message(
                content="❌ You don't have an active pet!",
                view=None
            )
            return
        
        owned = user_data.current_treat_inventory.get(treat_id, 0)
        if owned <= 0:
            await interaction.response.edit_message(
                content="❌ You don't own this treat anymore!",
                view=None
            )
            return
        
        # Check cooldown again
        current_time = time.time()
        if user_data.last_shoptreat_used > 0:
            cooldown_end = user_data.last_shoptreat_used + (SHOP_TREAT_COOLDOWN_HOURS * 3600)
            if current_time < cooldown_end:
                await interaction.response.edit_message(
                    content="❌ You're still on cooldown!",
                    view=None
                )
                return
        
        # Apply treat effect
        stat = treat["stat"]
        current_stat = getattr(pet, stat, 0)
        new_stat = min(100, current_stat + treat["effect"])
        setattr(pet, stat, new_stat)
        
        # Add bond
        pet.bond += 5
        
        # Remove treat from inventory
        user_data.current_treat_inventory[treat_id] = owned - 1
        if user_data.current_treat_inventory[treat_id] <= 0:
            del user_data.current_treat_inventory[treat_id]
        
        # Set cooldown
        user_data.last_shoptreat_used = current_time
        
        # Track statistics
        user_data.total_treats_given += 1
        
        # Save
        self.parent_view.cog.schedule_save()
        
        # Show success
        await interaction.response.edit_message(
            content=(
                f"✅ **Treat Given!**\n\n"
                f"{treat['emoji']} **{pet.name}** enjoyed the {treat['name']}!\n\n"
                f"• {stat.title()}: {int(current_stat)} → {int(new_stat)} (+{treat['effect']})\n"
                f"• Bond: +5\n\n"
                f"⏳ You can use another treat in **{SHOP_TREAT_COOLDOWN_HOURS} hours**."
            ),
            view=None
        )
        
        # Refresh the parent view
        self.parent_view._setup_buttons()
        embed = self.parent_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        try:
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)
        except Exception:
            pass
        
        self.stop()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Cancel using treat."""
        await interaction.response.edit_message(
            content="❌ Cancelled.",
            view=None
        )
        self.stop()


class BackToInventoryButton(Button):
    """Button to return to inventory."""

    def __init__(self):
        super().__init__(
            label="Back to Inventory",
            emoji="🎒",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryTreatsView = self.view
        view.stop()
        
        from .home_views import InventoryView
        
        inv_view = InventoryView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            category="All Items",
            page=0
        )
        
        embed = inv_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=inv_view)
        inv_view.message = view.message


class CloseTreatsButton(Button):
    """Button to close the treats view."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryTreatsView = self.view
        view.stop()
        await interaction.response.edit_message(view=None)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


# =============================================================================
# GOLDEN AMBROSIA — LEGENDARY ITEM
# =============================================================================

class BuyAmbrosiaButton(Button):
    """Button to purchase Golden Ambrosia from the Treats Shop."""

    def __init__(self, user_data: "User"):
        owned = user_data.current_treat_inventory.get("golden_ambrosia", 0)
        at_max = owned >= AMBROSIA_MAX_STACK

        super().__init__(
            label=f"Buy Ambrosia ({owned}/{AMBROSIA_MAX_STACK})" if not at_max else "Ambrosia (MAX)",
            emoji="🍯",
            style=discord.ButtonStyle.success if not at_max else discord.ButtonStyle.secondary,
            disabled=at_max,
            row=2
        )
        self.user_data = user_data

    async def callback(self, interaction: discord.Interaction) -> None:
        view: TreatsShopView = self.view
        ambrosia = SHOP_TREATS.get("golden_ambrosia")
        if not ambrosia:
            await interaction.response.send_message("❌ Item not found!", ephemeral=True)
            return

        owned = view.user_data.current_treat_inventory.get("golden_ambrosia", 0)
        if owned >= AMBROSIA_MAX_STACK:
            await interaction.response.send_message(
                f"❌ You already own the maximum ({AMBROSIA_MAX_STACK}) Golden Ambrosia!",
                ephemeral=True
            )
            return

        cost = ambrosia["cost"]
        if view.user_data.current_petcoin < cost:
            await interaction.response.send_message(
                f"❌ Not enough Petcoin! You need **{cost:,} 💰** but only have **{view.user_data.current_petcoin:,} 💰**.",
                ephemeral=True
            )
            return

        confirm_view = BuyAmbrosiaConfirmView(parent_view=view, ambrosia=ambrosia)
        await interaction.response.send_message(
            f"🍯 **Purchase Confirmation**\n\n"
            f"✨ **Golden Ambrosia** *(Legendary)*\n"
            f"*{ambrosia['description']}*\n\n"
            f"**Cost:** {cost:,} 💰\n"
            f"**Your balance:** {view.user_data.current_petcoin:,} 💰\n"
            f"**After purchase:** {view.user_data.current_petcoin - cost:,} 💰\n\n"
            f"You currently own **{owned}/{AMBROSIA_MAX_STACK}** Golden Ambrosia.\n\n"
            f"Confirm purchase?",
            view=confirm_view,
            ephemeral=True
        )


class BuyAmbrosiaConfirmView(View):
    """Confirmation view for purchasing Golden Ambrosia."""

    def __init__(self, parent_view: TreatsShopView, ambrosia: dict, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.ambrosia = ambrosia

    @discord.ui.button(label="Purchase", emoji="✅", style=discord.ButtonStyle.success)
    async def purchase_button(self, interaction: discord.Interaction, button: Button) -> None:
        user_data = self.parent_view.user_data
        cost = self.ambrosia["cost"]

        # Re-check conditions
        owned = user_data.current_treat_inventory.get("golden_ambrosia", 0)
        if owned >= AMBROSIA_MAX_STACK:
            await interaction.response.edit_message(
                content=f"❌ You already own the maximum ({AMBROSIA_MAX_STACK}) Golden Ambrosia!",
                view=None
            )
            return

        if user_data.current_petcoin < cost:
            await interaction.response.edit_message(
                content="❌ Not enough Petcoin!",
                view=None
            )
            return

        # Process purchase
        user_data.current_petcoin -= cost
        user_data.current_treat_inventory["golden_ambrosia"] = owned + 1

        # Save
        self.parent_view.cog.schedule_save()

        new_owned = user_data.current_treat_inventory["golden_ambrosia"]
        await interaction.response.edit_message(
            content=(
                f"✅ **Purchase Successful!**\n\n"
                f"🍯 **Golden Ambrosia** added to your inventory!\n"
                f"You now own **{new_owned}/{AMBROSIA_MAX_STACK}**.\n"
                f"Remaining balance: {user_data.current_petcoin:,} 💰\n\n"
                f"Use it from **Inventory → Shop Treats** to grant a home pet Immortality!"
            ),
            view=None
        )

        # Refresh parent view
        self.parent_view._setup_buttons()
        embed = self.parent_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        try:
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)
        except Exception:
            pass

        self.stop()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.edit_message(content="❌ Purchase cancelled.", view=None)
        self.stop()


class UseAmbrosiaButton(Button):
    """Button to use Golden Ambrosia on a home pet."""

    def __init__(self, owned_count: int):
        super().__init__(
            label=f"Use Ambrosia (x{owned_count})",
            emoji="🍯",
            style=discord.ButtonStyle.success,
            row=2
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryTreatsView = self.view
        user_data = view.user_data

        # Get eligible home pets (not already immortal)
        eligible_pets = [
            (i, pet) for i, pet in enumerate(user_data.home_pets)
            if not pet.is_immortal
        ]

        if not eligible_pets:
            if not user_data.home_pets:
                msg = "❌ You don't have any home pets! Graduate a pet to your Home first."
            else:
                msg = "✨ All of your home pets are already Immortal!"
            await interaction.response.send_message(msg, ephemeral=True)
            return

        picker_view = HomePetPickerView(parent_view=view, eligible_pets=eligible_pets)
        await interaction.response.send_message(
            "🍯 **Golden Ambrosia**\n\n"
            "Select a home pet to grant **Immortality** to.\n"
            "They will never die of old age.\n\n"
            "⚠️ **This is permanent and cannot be undone!**",
            view=picker_view,
            ephemeral=True
        )


class HomePetPickerView(View):
    """View for selecting which home pet receives immortality."""

    def __init__(self, parent_view: "InventoryTreatsView", eligible_pets: list, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.eligible_pets = eligible_pets
        self.add_item(HomePetPickerSelect(eligible_pets))

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.edit_message(content="❌ Cancelled.", view=None)
        self.stop()


class HomePetPickerSelect(Select):
    """Dropdown to choose which home pet to grant immortality."""

    def __init__(self, eligible_pets: list):
        from ..database.species import get_species

        options = []
        for i, pet in eligible_pets[:25]:
            species = get_species(pet.species_id)
            species_emoji = species.emoji if species else "🐾"
            medal_display = f" · {pet.medal.title()} Medal" if pet.medal else ""
            options.append(discord.SelectOption(
                label=pet.name,
                emoji=species_emoji,
                description=f"{pet.life_stage.title()}{medal_display} · Age {int(pet.age_days)}d",
                value=str(i)
            ))

        super().__init__(
            placeholder="Choose a home pet to bless...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        picker_view: HomePetPickerView = self.view
        pet_index = int(self.values[0])
        user_data = picker_view.parent_view.user_data

        # Re-check pet still exists and isn't immortal
        if pet_index >= len(user_data.home_pets):
            await interaction.response.edit_message(content="❌ Pet not found!", view=None)
            return

        pet = user_data.home_pets[pet_index]
        if pet.is_immortal:
            await interaction.response.edit_message(
                content="✨ This pet is already Immortal!", view=None
            )
            return

        from ..database.species import get_species
        species = get_species(pet.species_id)
        species_name = species.name if species else pet.species_id

        confirm_view = AmbrosiaConfirmView(
            parent_view=picker_view.parent_view,
            pet=pet,
            pet_index=pet_index,
            species_name=species_name
        )

        await interaction.response.edit_message(
            content=(
                f"🍯 **Final Confirmation**\n\n"
                f"Grant **Immortality** to **{pet.name}** ({species_name})?\n\n"
                f"• They will **never die of old age**\n"
                f"• **1 Golden Ambrosia** will be consumed\n"
                f"• This **cannot be undone**\n\n"
                f"Are you sure?"
            ),
            view=confirm_view
        )
        picker_view.stop()


class AmbrosiaConfirmView(View):
    """Final confirmation before granting immortality to a home pet."""

    def __init__(
        self,
        parent_view: "InventoryTreatsView",
        pet,
        pet_index: int,
        species_name: str,
        timeout: float = 60
    ):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.pet = pet
        self.pet_index = pet_index
        self.species_name = species_name

    @discord.ui.button(label="Grant Immortality", emoji="🍯", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: Button) -> None:
        user_data = self.parent_view.user_data

        # Re-check ambrosia in inventory
        owned = user_data.current_treat_inventory.get("golden_ambrosia", 0)
        if owned <= 0:
            await interaction.response.edit_message(
                content="❌ You no longer have a Golden Ambrosia!", view=None
            )
            return

        # Re-check pet still exists and isn't immortal
        if self.pet_index >= len(user_data.home_pets):
            await interaction.response.edit_message(content="❌ Pet not found!", view=None)
            return

        pet = user_data.home_pets[self.pet_index]
        if pet.is_immortal:
            await interaction.response.edit_message(
                content="✨ This pet is already Immortal!", view=None
            )
            return

        # Grant immortality
        pet.is_immortal = True

        # Consume ambrosia
        user_data.current_treat_inventory["golden_ambrosia"] = owned - 1
        if user_data.current_treat_inventory["golden_ambrosia"] <= 0:
            del user_data.current_treat_inventory["golden_ambrosia"]

        # Save
        self.parent_view.cog.schedule_save()

        await interaction.response.edit_message(
            content=(
                f"✨ **Immortality Granted!**\n\n"
                f"🍯 **{pet.name}** has consumed the Golden Ambrosia!\n\n"
                f"They are now **Immortal** and will live forever in your home.\n"
                f"Look for the ✨ beside their name in your Home."
            ),
            view=None
        )

        # Refresh the inventory treats view
        self.parent_view._setup_buttons()
        embed = self.parent_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        try:
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)
        except Exception:
            pass

        self.stop()

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button) -> None:
        await interaction.response.edit_message(content="❌ Cancelled.", view=None)
        self.stop()
