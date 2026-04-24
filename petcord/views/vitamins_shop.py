"""
Vitamins shop views for purchasing player cooldown-reduction vitamins.
"""

import discord
from discord.ui import View, Button, Select
from typing import TYPE_CHECKING, Optional, List, Dict

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings

from ..database.petshop import SHOP_VITAMINS, get_vitamin, get_vitamins_by_cooldown_type, get_all_vitamins
from ..common.constants import VITAMIN_MAX_STACK


# =============================================================================
# COOLDOWN CATEGORIES FOR VITAMINS
# =============================================================================

VITAMIN_COOLDOWN_CATEGORIES = {
    "Feed": {"cooldown_type": "feed", "emoji": "🍖", "description": "Reduce feed cooldown"},
    "Play": {"cooldown_type": "play", "emoji": "🎾", "description": "Reduce play cooldown"},
    "Groom": {"cooldown_type": "groom", "emoji": "✨", "description": "Reduce groom cooldown"},
    "Rest": {"cooldown_type": "rest", "emoji": "💤", "description": "Reduce rest cooldown"},
    "Treat": {"cooldown_type": "treat", "emoji": "🍬", "description": "Reduce treat cooldown"},
    "Pet": {"cooldown_type": "pet", "emoji": "🤗", "description": "Reduce pet cooldown"},
}


# =============================================================================
# VITAMINS SHOP VIEW (from Supply Shop)
# =============================================================================

class VitaminsShopView(View):
    """View for purchasing vitamins from the Supply Shop."""

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

        # Row 0: Cooldown category dropdown
        self.add_item(VitaminCooldownTypeSelect())

        # Row 1: Navigation
        self.add_item(BackToSupplyShopButton())
        self.add_item(CloseVitaminsShopButton())

    def build_embed(self) -> discord.Embed:
        """Build the main vitamins shop embed."""
        total_owned = sum(self.user_data.current_vitamin_inventory.values())

        embed = discord.Embed(
            title="💊 Vitamins Shop",
            description=(
                "Purchase vitamins to reduce your action cooldowns!\n\n"
                "💰 **Your Petcoin:** {petcoin:,}\n"
                "🎒 **Vitamins Owned:** {vitamins_owned}\n\n"
                "Vitamins reduce the time before you can perform an action again.\n\n"
                "Select a cooldown category below to browse vitamins."
            ).format(
                petcoin=self.user_data.current_petcoin,
                vitamins_owned=total_owned
            ),
            color=discord.Color.purple()
        )

        for cat_name, cat_info in VITAMIN_COOLDOWN_CATEGORIES.items():
            cooldown_type = cat_info["cooldown_type"]
            emoji = cat_info["emoji"]
            vitamins = get_vitamins_by_cooldown_type(cooldown_type)

            owned_count = sum(
                self.user_data.current_vitamin_inventory.get(v["id"], 0)
                for v in vitamins
            )

            costs = [v["cost"] for v in vitamins]
            price_range = f"{min(costs)}-{max(costs)} 💰"

            embed.add_field(
                name=f"{emoji} {cat_name}",
                value=f"Owned: {owned_count} | {price_range}",
                inline=True
            )

        embed.set_footer(text=f"Max {VITAMIN_MAX_STACK} of each vitamin type")

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
            if hasattr(item, "disabled"):
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


class VitaminCooldownTypeSelect(Select):
    """Dropdown to select which cooldown type's vitamins to view."""

    def __init__(self):
        options = []
        for cat_name, cat_info in VITAMIN_COOLDOWN_CATEGORIES.items():
            options.append(discord.SelectOption(
                label=cat_name,
                emoji=cat_info["emoji"],
                description=cat_info["description"],
                value=cat_info["cooldown_type"]
            ))

        super().__init__(
            placeholder="Select a cooldown category...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VitaminsShopView = self.view
        selected_type = self.values[0]

        view.stop()

        type_view = VitaminCooldownShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            author=view.author,
            cooldown_type=selected_type
        )

        embed = type_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=type_view)
        type_view.message = view.message


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
        view: VitaminsShopView = self.view
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


class CloseVitaminsShopButton(Button):
    """Button to close the vitamins shop."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VitaminsShopView = self.view
        view.stop()
        await interaction.response.edit_message(view=None)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


# =============================================================================
# COOLDOWN-TYPE-SPECIFIC VITAMIN SHOP VIEW
# =============================================================================

class VitaminCooldownShopView(View):
    """View for browsing vitamins of a specific cooldown type."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        author: discord.Member,
        cooldown_type: str
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.author = author
        self.cooldown_type = cooldown_type
        self.message: Optional[discord.Message] = None

        # Register with cog for cleanup
        self.cog._active_views.add(self)

        self._setup_buttons()

    def _setup_buttons(self) -> None:
        """Set up the view buttons."""
        self.clear_items()

        # Row 0: Vitamin selection dropdown
        self.add_item(VitaminSelect(self.cooldown_type, self.user_data))

        # Row 1: Navigation
        self.add_item(BackToVitaminsShopButton())
        self.add_item(CloseVitaminCooldownShopButton())

    def _get_category_display(self) -> tuple[str, str]:
        """Return (display_name, emoji) for the current cooldown type."""
        for cat_name, cat_info in VITAMIN_COOLDOWN_CATEGORIES.items():
            if cat_info["cooldown_type"] == self.cooldown_type:
                return cat_name, cat_info["emoji"]
        return self.cooldown_type.title(), "💊"

    def build_embed(self) -> discord.Embed:
        """Build the cooldown-type-specific vitamins embed."""
        cat_name, cat_emoji = self._get_category_display()
        vitamins = get_vitamins_by_cooldown_type(self.cooldown_type)

        embed = discord.Embed(
            title=f"{cat_emoji} {cat_name} Vitamins",
            description=(
                f"💰 **Your Petcoin:** {self.user_data.current_petcoin:,}\n\n"
                "Select a vitamin from the dropdown to purchase.\n"
                "Vitamins reduce the cooldown for this action."
            ),
            color=discord.Color.purple()
        )

        tier_order = {"low": 0, "medium": 1, "high": 2}
        vitamins.sort(key=lambda v: tier_order.get(v["tier"], 99))

        for vitamin in vitamins:
            vitamin_id = vitamin["id"]
            owned = self.user_data.current_vitamin_inventory.get(vitamin_id, 0)
            at_max = owned >= VITAMIN_MAX_STACK

            minutes = vitamin["effect"] // 60
            hours = minutes // 60
            if hours >= 1 and minutes % 60 == 0:
                effect_display = f"-{hours}h cooldown"
            elif hours >= 1:
                effect_display = f"-{hours}h {minutes % 60}m cooldown"
            else:
                effect_display = f"-{minutes}m cooldown"

            tier_display = vitamin["tier"].title()
            stock_status = f"Owned: {owned}/{VITAMIN_MAX_STACK}" + (" **(MAX)**" if at_max else "")

            embed.add_field(
                name=f"{vitamin['emoji']} {vitamin['name']} ({tier_display})",
                value=(
                    f"**Effect:** {effect_display}\n"
                    f"**Cost:** {vitamin['cost']} 💰\n"
                    f"**{stock_status}**\n"
                    f"*{vitamin['description']}*"
                ),
                inline=True
            )

        embed.set_footer(text=f"Max {VITAMIN_MAX_STACK} of each vitamin type")

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
            if hasattr(item, "disabled"):
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


class VitaminSelect(Select):
    """Dropdown to select a vitamin to purchase."""

    def __init__(self, cooldown_type: str, user_data: "User"):
        self.cooldown_type = cooldown_type
        vitamins = get_vitamins_by_cooldown_type(cooldown_type)

        tier_order = {"low": 0, "medium": 1, "high": 2}
        vitamins.sort(key=lambda v: tier_order.get(v["tier"], 99))

        options = []
        for vitamin in vitamins:
            vitamin_id = vitamin["id"]
            owned = user_data.current_vitamin_inventory.get(vitamin_id, 0)

            minutes = vitamin["effect"] // 60
            hours = minutes // 60
            if hours >= 1 and minutes % 60 == 0:
                effect_str = f"-{hours}h"
            elif hours >= 1:
                effect_str = f"-{hours}h {minutes % 60}m"
            else:
                effect_str = f"-{minutes}m"

            options.append(discord.SelectOption(
                label=f"{vitamin['name']} ({vitamin['tier'].title()})",
                emoji=vitamin["emoji"],
                description=f"{effect_str} cooldown | {vitamin['cost']} 💰 | Owned: {owned}/{VITAMIN_MAX_STACK}",
                value=vitamin_id
            ))

        super().__init__(
            placeholder="Select a vitamin to purchase...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VitaminCooldownShopView = self.view
        vitamin_id = self.values[0]

        vitamin = get_vitamin(vitamin_id)
        if not vitamin:
            await interaction.response.send_message(
                "❌ Vitamin not found!",
                ephemeral=True
            )
            return

        owned = view.user_data.current_vitamin_inventory.get(vitamin_id, 0)
        if owned >= VITAMIN_MAX_STACK:
            await interaction.response.send_message(
                f"❌ You already have the maximum ({VITAMIN_MAX_STACK}) of this vitamin!",
                ephemeral=True
            )
            return

        if view.user_data.current_petcoin < vitamin["cost"]:
            await interaction.response.send_message(
                f"❌ Not enough Petcoin! You need {vitamin['cost']} 💰 but only have "
                f"{view.user_data.current_petcoin:,} 💰.",
                ephemeral=True
            )
            return

        # Build effect display for confirmation
        minutes = vitamin["effect"] // 60
        hours = minutes // 60
        if hours >= 1 and minutes % 60 == 0:
            effect_display = f"-{hours}h cooldown"
        elif hours >= 1:
            effect_display = f"-{hours}h {minutes % 60}m cooldown"
        else:
            effect_display = f"-{minutes}m cooldown"

        confirm_view = VitaminPurchaseConfirmView(
            parent_view=view,
            vitamin=vitamin
        )

        await interaction.response.send_message(
            f"🛒 **Purchase Confirmation**\n\n"
            f"{vitamin['emoji']} **{vitamin['name']}**\n"
            f"Effect: {effect_display}\n"
            f"Cost: **{vitamin['cost']}** 💰\n\n"
            f"Current balance: {view.user_data.current_petcoin:,} 💰\n"
            f"After purchase: {view.user_data.current_petcoin - vitamin['cost']:,} 💰\n\n"
            f"Confirm purchase?",
            view=confirm_view,
            ephemeral=True
        )


class BackToVitaminsShopButton(Button):
    """Button to return to the main vitamins shop."""

    def __init__(self):
        super().__init__(
            label="Back",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VitaminCooldownShopView = self.view
        view.stop()

        vitamins_view = VitaminsShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            author=view.author
        )

        embed = vitamins_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=vitamins_view)
        vitamins_view.message = view.message


class CloseVitaminCooldownShopButton(Button):
    """Button to close the vitamin shop."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: VitaminCooldownShopView = self.view
        view.stop()
        await interaction.response.edit_message(view=None)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass


# =============================================================================
# PURCHASE CONFIRMATION VIEW
# =============================================================================

class VitaminPurchaseConfirmView(View):
    """Confirmation view for vitamin purchase."""

    def __init__(self, parent_view: VitaminCooldownShopView, vitamin: dict, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.vitamin = vitamin

    @discord.ui.button(label="Purchase", emoji="✅", style=discord.ButtonStyle.success)
    async def purchase_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Confirm purchase."""
        vitamin = self.vitamin
        user_data = self.parent_view.user_data
        vitamin_id = vitamin["id"]

        # Re-check conditions
        owned = user_data.current_vitamin_inventory.get(vitamin_id, 0)
        if owned >= VITAMIN_MAX_STACK:
            await interaction.response.edit_message(
                content=f"❌ You already have the maximum ({VITAMIN_MAX_STACK}) of this vitamin!",
                view=None
            )
            return

        if user_data.current_petcoin < vitamin["cost"]:
            await interaction.response.edit_message(
                content="❌ Not enough Petcoin!",
                view=None
            )
            return

        # Process purchase
        user_data.current_petcoin -= vitamin["cost"]
        user_data.current_vitamin_inventory[vitamin_id] = owned + 1

        # Save
        self.parent_view.cog.schedule_save()

        new_owned = user_data.current_vitamin_inventory[vitamin_id]
        await interaction.response.edit_message(
            content=(
                f"✅ **Purchase Successful!**\n\n"
                f"{vitamin['emoji']} **{vitamin['name']}** added to inventory!\n"
                f"You now own {new_owned}/{VITAMIN_MAX_STACK} of this vitamin.\n"
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
# INVENTORY VITAMINS VIEW (for using owned vitamins)
# =============================================================================

# Maps cooldown_type -> pet attribute name
COOLDOWN_TYPE_TO_FIELD = {
    "feed": "last_fed",
    "play": "last_played",
    "groom": "last_groomed",
    "rest": "last_rested",
    "treat": "last_treated",
    "pet": "last_petted",
}


class InventoryVitaminsView(View):
    """View for managing and using owned vitamins from inventory."""

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

    def _get_owned_vitamins(self) -> List[dict]:
        """Get list of vitamins the user owns (with counts)."""
        owned = []
        for vitamin_id, count in self.user_data.current_vitamin_inventory.items():
            if count > 0:
                vitamin = get_vitamin(vitamin_id)
                if vitamin:
                    vitamin["owned"] = count
                    owned.append(vitamin)

        # Sort by cooldown_type order, then tier
        type_order = {"feed": 0, "play": 1, "groom": 2, "rest": 3, "treat": 4, "pet": 5}
        tier_order = {"low": 0, "medium": 1, "high": 2}
        owned.sort(key=lambda v: (
            type_order.get(v["cooldown_type"], 99),
            tier_order.get(v["tier"], 99)
        ))
        return owned

    def _setup_buttons(self) -> None:
        """Set up the view buttons."""
        self.clear_items()

        owned_vitamins = self._get_owned_vitamins()

        # Row 0: Vitamin selection dropdown (if has vitamins)
        if owned_vitamins:
            self.add_item(UseVitaminSelect(owned_vitamins))

        # Row 1: Navigation
        self.add_item(BackToInventoryFromVitaminsButton())
        self.add_item(CloseInventoryVitaminsButton())

    def build_embed(self) -> discord.Embed:
        """Build the inventory vitamins embed."""
        owned_vitamins = self._get_owned_vitamins()
        total_owned = sum(v["owned"] for v in owned_vitamins)

        embed = discord.Embed(
            title="💊 Your Vitamins",
            description=(
                f"**Vitamins Owned:** {total_owned}\n\n"
                "Select a vitamin below to use it and reduce an action cooldown.\n"
                "Vitamins apply immediately — no pet required!"
            ),
            color=discord.Color.purple()
        )

        if not owned_vitamins:
            embed.add_field(
                name="No Vitamins",
                value="You don't own any vitamins yet!\nVisit the Supply Shop to purchase some.",
                inline=False
            )
        else:
            # Group by cooldown type
            by_type: Dict[str, List[dict]] = {}
            for vitamin in owned_vitamins:
                ct = vitamin["cooldown_type"]
                if ct not in by_type:
                    by_type[ct] = []
                by_type[ct].append(vitamin)

            for ct, vitamins in by_type.items():
                emoji = "💊"
                label = ct.title()
                for cat_name, info in VITAMIN_COOLDOWN_CATEGORIES.items():
                    if info["cooldown_type"] == ct:
                        emoji = info["emoji"]
                        label = cat_name
                        break

                lines = []
                for v in vitamins:
                    minutes = v["effect"] // 60
                    hours = minutes // 60
                    if hours >= 1 and minutes % 60 == 0:
                        effect_str = f"-{hours}h"
                    elif hours >= 1:
                        effect_str = f"-{hours}h {minutes % 60}m"
                    else:
                        effect_str = f"-{minutes}m"
                    lines.append(f"{v['emoji']} {v['name']} x{v['owned']} ({effect_str})")

                embed.add_field(
                    name=f"{emoji} {label}",
                    value="\n".join(lines),
                    inline=True
                )

        embed.set_footer(text="Vitamins reduce the time before you can perform an action again.")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your vitamins menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        self.cog._active_views.discard(self)
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        self.cog._active_views.discard(self)
        super().stop()


class UseVitaminSelect(Select):
    """Dropdown to select a vitamin to use."""

    def __init__(self, owned_vitamins: List[dict]):
        options = []
        for vitamin in owned_vitamins[:25]:  # Discord limit
            minutes = vitamin["effect"] // 60
            hours = minutes // 60
            if hours >= 1 and minutes % 60 == 0:
                effect_str = f"-{hours}h cooldown"
            elif hours >= 1:
                effect_str = f"-{hours}h {minutes % 60}m cooldown"
            else:
                effect_str = f"-{minutes}m cooldown"

            options.append(discord.SelectOption(
                label=f"{vitamin['name']} (x{vitamin['owned']})",
                emoji=vitamin["emoji"],
                description=f"{effect_str} | {vitamin['cooldown_type'].title()} action",
                value=vitamin["id"]
            ))

        super().__init__(
            placeholder="Select a vitamin to use...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        import time as _time
        view: InventoryVitaminsView = self.view
        vitamin_id = self.values[0]

        vitamin = get_vitamin(vitamin_id)
        if not vitamin:
            await interaction.response.send_message("❌ Vitamin not found!", ephemeral=True)
            return

        owned = view.user_data.current_vitamin_inventory.get(vitamin_id, 0)
        if owned <= 0:
            await interaction.response.send_message("❌ You don't own this vitamin!", ephemeral=True)
            return

        cooldown_type = vitamin["cooldown_type"]
        pet_field = COOLDOWN_TYPE_TO_FIELD.get(cooldown_type)

        # Build effect display
        minutes = vitamin["effect"] // 60
        hours = minutes // 60
        if hours >= 1 and minutes % 60 == 0:
            effect_display = f"-{hours}h cooldown"
        elif hours >= 1:
            effect_display = f"-{hours}h {minutes % 60}m cooldown"
        else:
            effect_display = f"-{minutes}m cooldown"

        # Show what the current cooldown field looks like (if pet exists)
        pet = view.user_data.current_pet
        current_time = _time.time()
        cooldown_info = ""
        if pet and pet_field:
            last_ts = getattr(pet, pet_field, 0.0)
            if last_ts > 0:
                elapsed = current_time - last_ts
                new_elapsed = elapsed + vitamin["effect"]
                if new_elapsed >= 0:
                    cooldown_info = f"\nThis will make the **{cooldown_type}** action available sooner."
                else:
                    cooldown_info = f"\nThis reduces time remaining on the **{cooldown_type}** cooldown."

        confirm_view = UseVitaminConfirmView(parent_view=view, vitamin=vitamin)

        await interaction.response.send_message(
            f"💊 **Use Vitamin Confirmation**\n\n"
            f"{vitamin['emoji']} **{vitamin['name']}**\n"
            f"**Effect:** {effect_display}{cooldown_info}\n\n"
            f"Use this vitamin now?",
            view=confirm_view,
            ephemeral=True
        )


class UseVitaminConfirmView(View):
    """Confirmation view for using a vitamin."""

    def __init__(self, parent_view: InventoryVitaminsView, vitamin: dict, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.vitamin = vitamin

    @discord.ui.button(label="Use Vitamin", emoji="💊", style=discord.ButtonStyle.success)
    async def use_button(self, interaction: discord.Interaction, button: Button) -> None:
        import time as _time
        vitamin = self.vitamin
        user_data = self.parent_view.user_data
        vitamin_id = vitamin["id"]

        # Re-check ownership
        owned = user_data.current_vitamin_inventory.get(vitamin_id, 0)
        if owned <= 0:
            await interaction.response.edit_message(
                content="❌ You don't own this vitamin anymore!",
                view=None
            )
            return

        # Apply cooldown reduction to the pet's last_* timestamp
        cooldown_type = vitamin["cooldown_type"]
        pet_field = COOLDOWN_TYPE_TO_FIELD.get(cooldown_type)
        pet = user_data.current_pet
        current_time = _time.time()

        if pet and pet_field:
            last_ts = getattr(pet, pet_field, 0.0)
            if last_ts > 0:
                # Subtract effect seconds from the timestamp (moves it further into the past)
                new_ts = last_ts - vitamin["effect"]
                # Don't push it past 0 (no point going before epoch baseline)
                setattr(pet, pet_field, max(0.0, new_ts))

        # Remove one vitamin from inventory
        user_data.current_vitamin_inventory[vitamin_id] = owned - 1
        if user_data.current_vitamin_inventory[vitamin_id] <= 0:
            del user_data.current_vitamin_inventory[vitamin_id]

        # Save
        self.parent_view.cog.schedule_save()

        minutes = vitamin["effect"] // 60
        hours = minutes // 60
        if hours >= 1 and minutes % 60 == 0:
            effect_display = f"-{hours}h"
        elif hours >= 1:
            effect_display = f"-{hours}h {minutes % 60}m"
        else:
            effect_display = f"-{minutes}m"

        await interaction.response.edit_message(
            content=(
                f"✅ **Vitamin Used!**\n\n"
                f"{vitamin['emoji']} **{vitamin['name']}** applied!\n"
                f"• {cooldown_type.title()} cooldown reduced by **{effect_display}**"
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
        await interaction.response.edit_message(content="❌ Cancelled.", view=None)
        self.stop()


class BackToInventoryFromVitaminsButton(Button):
    """Button to return to the inventory view."""

    def __init__(self):
        super().__init__(
            label="Back to Inventory",
            emoji="🎒",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryVitaminsView = self.view
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


class CloseInventoryVitaminsButton(Button):
    """Button to close the vitamins inventory view."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryVitaminsView = self.view
        view.stop()
        await interaction.response.edit_message(view=None)
        try:
            await interaction.delete_original_response()
        except Exception:
            pass
