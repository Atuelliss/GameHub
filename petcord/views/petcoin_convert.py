"""
Petcoin to server currency conversion view for Petcord cog.

Players exchange Petcoin for the server's Red bank currency at the admin-set
rate of "X Petcoin -> Y currency". Conversions happen in whole batches of X;
any leftover Petcoin stays in the player's balance.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, Optional, Tuple
from zoneinfo import ZoneInfo

import discord
from discord.ui import Button, Modal, TextInput, View
from redbot.core import bank
from redbot.core.errors import BalanceTooHigh

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings


# One lock per (guild, user) so a double-click or two open views can't convert twice
_conversion_locks: Dict[Tuple[int, int], asyncio.Lock] = {}


def _get_lock(guild_id: int, user_id: int) -> asyncio.Lock:
    return _conversion_locks.setdefault((guild_id, user_id), asyncio.Lock())


def get_conversion_day(settings: "GuildSettings") -> str:
    """Current date (YYYY-MM-DD) in the server timezone, used for the daily cap."""
    try:
        tz = ZoneInfo(settings.discord_server_timezone)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz).strftime("%Y-%m-%d")


def get_cooldown_remaining(settings: "GuildSettings", user_data: "User") -> int:
    """Seconds until the user may convert again (0 = ready)."""
    if settings.petcoin_conversion_cooldown_hours <= 0 or not user_data.last_petcoin_conversion:
        return 0
    ready_at = user_data.last_petcoin_conversion + settings.petcoin_conversion_cooldown_hours * 3600
    return max(0, int(ready_at - time.time()))


def get_currency_converted_today(settings: "GuildSettings", user_data: "User") -> int:
    """Server currency the user has already received today."""
    if user_data.conversion_day != get_conversion_day(settings):
        return 0
    return user_data.currency_converted_today


def calculate_conversion(
    settings: "GuildSettings",
    user_data: "User",
    requested: int,
) -> Tuple[int, int, str]:
    """
    Work out how much of a requested Petcoin amount can actually be converted.

    Returns:
        (petcoin_used, currency_received, note) -- note explains any limit applied,
        or why nothing can be converted when petcoin_used is 0.
    """
    rate = max(1, settings.petcoin_conversion_rate)
    per_batch = max(1, settings.petcoin_conversion_currency)
    note = ""

    requested = max(0, min(requested, user_data.current_petcoin))
    batches = requested // rate

    # Daily cap (in server currency)
    if settings.petcoin_conversion_daily_cap > 0:
        remaining_today = settings.petcoin_conversion_daily_cap - get_currency_converted_today(settings, user_data)
        if remaining_today < per_batch:
            return 0, 0, "You've reached today's conversion limit."
        max_batches = remaining_today // per_batch
        if batches > max_batches:
            batches = max_batches
            note = "Reduced to fit today's conversion limit."

    if batches <= 0:
        return 0, 0, f"You need at least **{rate:,}** Petcoin to convert."

    petcoin_used = batches * rate
    minimum = settings.petcoin_conversion_minimum
    if minimum > 0 and petcoin_used < minimum:
        return 0, 0, f"The minimum conversion is **{minimum:,}** Petcoin."

    if petcoin_used < requested and not note:
        note = f"Rounded down to whole batches of {rate:,} Petcoin."

    return petcoin_used, batches * per_batch, note


def _format_duration(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{max(1, minutes)}m"


class CustomAmountModal(Modal, title="Convert Petcoin"):
    """Modal for entering a custom Petcoin amount."""

    amount = TextInput(
        label="Petcoin to convert",
        placeholder="Enter a number, or 'all'",
        max_length=12,
    )

    def __init__(self, convert_view: "PetcoinConvertView"):
        super().__init__()
        self.convert_view = convert_view

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.amount.value.strip().lower().replace(",", "")
        balance = self.convert_view.user_data.current_petcoin
        if raw == "all":
            value = balance
        else:
            try:
                value = int(raw)
            except ValueError:
                await interaction.response.send_message("❌ Please enter a whole number or `all`.", ephemeral=True)
                return
        if value <= 0:
            await interaction.response.send_message("❌ Amount must be greater than 0.", ephemeral=True)
            return
        self.convert_view.selected = min(value, balance)
        await self.convert_view.refresh(interaction)


class PetcoinConvertView(View):
    """Ephemeral view for converting Petcoin into the server's currency."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        currency_name: str,
        origin: discord.Interaction,
        parent_view: Optional[View] = None,
        timeout: float = 120,
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.currency_name = currency_name
        self.origin = origin  # Interaction that sent this ephemeral message (used to edit it on timeout)
        self.parent_view = parent_view
        self.selected: int = 0
        self._setup_buttons()

    def _setup_buttons(self) -> None:
        self.clear_items()
        for label, fraction in (("25%", 0.25), ("50%", 0.5), ("All", 1.0)):
            button = Button(label=label, style=discord.ButtonStyle.secondary, row=0)
            button.callback = self._make_preset_callback(fraction)
            self.add_item(button)

        custom = Button(label="Custom", emoji="✏️", style=discord.ButtonStyle.secondary, row=0)
        custom.callback = self._custom_callback
        self.add_item(custom)

        petcoin_used, _, _ = calculate_conversion(self.guild_settings, self.user_data, self.selected)
        confirm = Button(
            label="Confirm",
            emoji="✅",
            style=discord.ButtonStyle.success,
            disabled=petcoin_used <= 0,
            row=1,
        )
        confirm.callback = self._confirm_callback
        self.add_item(confirm)

        cancel = Button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger, row=1)
        cancel.callback = self._cancel_callback
        self.add_item(cancel)

    def build_embed(self) -> discord.Embed:
        settings = self.guild_settings
        user = self.user_data
        rate = settings.petcoin_conversion_rate
        per_batch = settings.petcoin_conversion_currency

        embed = discord.Embed(
            title="💱 Convert Petcoin",
            description=(
                f"💰 Your Petcoin: **{user.current_petcoin:,}**\n"
                f"📈 Rate: **{rate:,}** Petcoin → **{per_batch:,}** {self.currency_name}"
            ),
            color=discord.Color.gold(),
        )

        limits = []
        if settings.petcoin_conversion_minimum > 0:
            limits.append(f"Minimum: **{settings.petcoin_conversion_minimum:,}** Petcoin")
        if settings.petcoin_conversion_daily_cap > 0:
            used_today = get_currency_converted_today(settings, user)
            limits.append(
                f"Daily limit: **{used_today:,}**/{settings.petcoin_conversion_daily_cap:,} {self.currency_name} used"
            )
        if settings.petcoin_conversion_cooldown_hours > 0:
            limits.append(f"Cooldown: **{settings.petcoin_conversion_cooldown_hours}h** between conversions")
        if limits:
            embed.add_field(name="📋 Limits", value="\n".join(limits), inline=False)

        if self.selected > 0:
            petcoin_used, currency, note = calculate_conversion(settings, user, self.selected)
            if petcoin_used > 0:
                preview = f"**{petcoin_used:,}** Petcoin → **{currency:,}** {self.currency_name}"
                if note:
                    preview += f"\n*{note}*"
            else:
                preview = f"❌ {note}"
            embed.add_field(name="🔎 Preview", value=preview, inline=False)
        else:
            embed.add_field(name="🔎 Preview", value="Choose an amount below.", inline=False)

        cooldown = get_cooldown_remaining(settings, user)
        if cooldown > 0:
            embed.set_footer(text=f"⏳ You can convert again in {_format_duration(cooldown)}")
        return embed

    async def refresh(self, interaction: discord.Interaction) -> None:
        self._setup_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("This isn't your conversion!", ephemeral=True)
            return False
        return True

    def _make_preset_callback(self, fraction: float):
        async def callback(interaction: discord.Interaction) -> None:
            self.selected = int(self.user_data.current_petcoin * fraction)
            await self.refresh(interaction)
        return callback

    async def _custom_callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(CustomAmountModal(self))

    async def _cancel_callback(self, interaction: discord.Interaction) -> None:
        self.stop()
        await interaction.response.edit_message(content="Conversion cancelled.", embed=None, view=None)

    async def _confirm_callback(self, interaction: discord.Interaction) -> None:
        settings = self.guild_settings
        user = self.user_data
        member = interaction.user

        async with _get_lock(interaction.guild_id, member.id):
            # Re-check everything -- settings or balance may have changed since the view opened
            if not settings.petcoin_conversion_enabled:
                self.stop()
                await interaction.response.edit_message(
                    content="❌ Petcoin conversion is currently disabled on this server.",
                    embed=None,
                    view=None,
                )
                return

            cooldown = get_cooldown_remaining(settings, user)
            if cooldown > 0:
                await interaction.response.send_message(
                    f"⏳ You can convert again in **{_format_duration(cooldown)}**.",
                    ephemeral=True,
                )
                return

            petcoin_used, currency, note = calculate_conversion(settings, user, self.selected)
            if petcoin_used <= 0:
                await interaction.response.send_message(f"❌ {note}", ephemeral=True)
                return

            # Don't deposit past the bank's maximum balance
            max_balance = await bank.get_max_balance(interaction.guild)
            room = max_balance - await bank.get_balance(member)
            if room < currency:
                per_batch = max(1, settings.petcoin_conversion_currency)
                batches = max(0, room) // per_batch
                if batches <= 0:
                    await interaction.response.send_message(
                        f"❌ Your {self.currency_name} balance is already at the maximum.",
                        ephemeral=True,
                    )
                    return
                petcoin_used = batches * settings.petcoin_conversion_rate
                currency = batches * per_batch
                note = f"Reduced to stay under the maximum {self.currency_name} balance."

            try:
                await bank.deposit_credits(member, currency)
            except BalanceTooHigh:
                await interaction.response.send_message(
                    f"❌ That would put you over the maximum {self.currency_name} balance.",
                    ephemeral=True,
                )
                return

            # Deposit succeeded -- now take the Petcoin and record the conversion
            today = get_conversion_day(settings)
            if user.conversion_day != today:
                user.conversion_day = today
                user.currency_converted_today = 0
            user.currency_converted_today += currency
            user.current_petcoin -= petcoin_used
            user.total_petcoin_converted += petcoin_used
            user.total_currency_from_petcoin += currency
            user.last_petcoin_conversion = time.time()
            self.cog.schedule_save()

        self.stop()
        receipt = discord.Embed(
            title="✅ Conversion Complete",
            description=(
                f"Converted **{petcoin_used:,}** Petcoin → **{currency:,}** {self.currency_name}\n\n"
                f"💰 Remaining Petcoin: **{user.current_petcoin:,}**"
            ),
            color=discord.Color.green(),
        )
        if note:
            receipt.set_footer(text=note)
        await interaction.response.edit_message(content=None, embed=receipt, view=None)

        # Refresh the Stats screen balance, unless the player has already moved on
        parent = self.parent_view
        if parent is not None and not parent.is_finished() and getattr(parent, "message", None):
            try:
                embed = parent.build_embed()
                embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                await parent.message.edit(embed=embed, view=parent)
            except (discord.NotFound, discord.HTTPException):
                pass

    async def on_timeout(self) -> None:
        try:
            await self.origin.edit_original_response(content="Conversion timed out.", embed=None, view=None)
        except (discord.NotFound, discord.HTTPException):
            pass
