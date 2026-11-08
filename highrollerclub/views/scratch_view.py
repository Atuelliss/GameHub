"""ScratchCardView -- Discord UI for Scratch Cards in HighRollerClub.

Flow
----
Phase 1 (idle)   : Card status (ready, or time until the next card) and the prize pool.
                   Buttons: Scratch Card | Back to Floor | How to Play
Phase 2 (result) : The card is shown as a 3x3 grid of spoiler-covered panels. The
                   player clicks the panels to scratch them; three matching symbols
                   reveal the prize, which has already been paid out.
                   Buttons: Back to Floor | How to Play

Access guard
------------
_check_access() runs at the top of the Scratch callback:
  1. channel_allowed(...): the channel lock (staff bypass it)
  2. conf.scratch_enabled
  3. the player is not blacklisted

Economy rules
-------------
- Free: no bet, no record_win / record_loss, no prestige except the rank_xp prize.
- Chip prizes are paid like the Mystery Wheel's: directly in chip mode, converted
  with discord_currency_conversion_rate (minimum 1) in bank mode.
- The Multiplier Wheel does not apply.

Pure game logic lives in games/scratch_card.py; the reward pool helpers are shared
with games/mystery_wheel.py.
"""

from __future__ import annotations

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.constants import PALETTE_GOLD, RANK_NAMES, embed_image
from ..common.interactions import expire_view, one_at_a_time, safe_defer, safe_edit_original_response, not_your_session, session_expired
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    apply_rank_change,
    credit_balance,
    evaluate_rank,
    get_balance,
    channel_allowed,
    is_blacklisted,
)
from ..games.mystery_wheel import REWARD_DESCRIPTION, REWARD_DISPLAY, apply_reward, pick_reward
from ..games.scratch_card import (
    SCRATCH_CHIP_REWARD_RANGE,
    build_card,
    next_ready_time,
    now_iso,
    roll_chip_amount,
    time_until_ready,
)


class ScratchCardView(discord.ui.View):
    """Scratch Card screen. Constructor signature matches _launch_game: (interaction, conf, user, cog)."""

    def __init__(
        self,
        interaction: discord.Interaction,
        conf: GuildSettings,
        user: User,
        cog: MixinMeta,
    ) -> None:
        super().__init__(timeout=120)
        self._member: discord.Member = interaction.user  # type: ignore[assignment]
        self._conf = conf
        self._user = user
        self._cog = cog

        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        self._add_idle_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._member.id:
            await not_your_session(interaction)
            return False
        return True

    async def on_timeout(self) -> None:
        await expire_view(self)

    # ------------------------------------------------------------------
    # Buttons
    # ------------------------------------------------------------------

    def _card_ready(self) -> bool:
        return next_ready_time(self._user.last_scratch_date, self._conf.scratch_cooldown_hours) is None

    def _add_idle_buttons(self) -> None:
        self.clear_items()
        scratch = discord.ui.Button(
            label="🎟️ Scratch Card",
            style=discord.ButtonStyle.green,
            row=0,
            disabled=not self._card_ready(),
        )
        scratch.callback = self._on_scratch
        self.add_item(scratch)
        self._add_nav_buttons()

    def _add_nav_buttons(self) -> None:
        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_floor
        self.add_item(back)
        info = discord.ui.Button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1)
        info.callback = self._show_info
        self.add_item(info)

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if await session_expired(self, interaction):
            return False
        conf = self._conf
        if not await channel_allowed(interaction.client, conf, interaction.user, interaction.channel_id):
            await interaction.response.send_message(
                "Scratch Cards can only be played in the designated casino channel(s).", ephemeral=True
            )
            return False
        if not conf.scratch_enabled:
            await interaction.response.send_message(
                "Scratch Cards are not enabled on this server.", ephemeral=True
            )
            return False
        if is_blacklisted(conf, self._member.id):
            await interaction.response.send_message("You can't use the club right now.", ephemeral=True)
            return False
        return True

    # ------------------------------------------------------------------
    # Scratch
    # ------------------------------------------------------------------

    @one_at_a_time
    async def _on_scratch(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        conf = self._conf
        user = self._user
        member = self._member
        if not self._card_ready():
            await interaction.response.send_message(
                "You've already scratched your card. The next one is ready in "
                f"**{time_until_ready(user.last_scratch_date, conf.scratch_cooldown_hours)}**.",
                ephemeral=True,
            )
            return

        # Claim the card before the first await, so a double-click can't scratch twice.
        user.last_scratch_date = now_iso()
        await safe_defer(interaction)

        reward_type = pick_reward(conf.scratch_reward_pool)
        chip_amount = roll_chip_amount() if reward_type == "chips" else 0
        payout_amount = 0
        currency_name = "chips"
        if conf.payment_mode == "bank":
            currency_name = await bank.get_currency_name(member.guild)
        if reward_type == "chips":
            if conf.payment_mode == "chips":
                payout_amount = chip_amount
            else:
                payout_amount = max(1, chip_amount // max(conf.discord_currency_conversion_rate, 1))
            await credit_balance(member, conf, user, payout_amount, interaction=interaction)

        apply_reward(user, reward_type, chip_amount)

        old_rank = user.rank
        new_rank = evaluate_rank(conf, user)
        if new_rank != old_rank:
            apply_rank_change(user, new_rank)

        self._cog.save()

        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = currency_name

        self.clear_items()
        self._add_nav_buttons()
        embed = self._build_result_embed(reward_type, chip_amount, payout_amount, currency_name, old_rank, new_rank)
        await safe_edit_original_response(interaction, embed=embed, view=self)

    # ------------------------------------------------------------------
    # Info / navigation
    # ------------------------------------------------------------------

    async def _show_info(self, interaction: discord.Interaction) -> None:
        conf = self._conf
        prizes = [REWARD_DISPLAY[r] for r in conf.scratch_reward_pool if r in REWARD_DISPLAY] or [REWARD_DISPLAY["chips"]]
        low, high = SCRATCH_CHIP_REWARD_RANGE
        e = discord.Embed(title="🎟️ How to Play: Scratch Cards", color=PALETTE_GOLD)
        e.description = (
            f"**One free card every {conf.scratch_cooldown_hours} hours.**\n\n"
            "1. Press **Scratch Card** to claim your card.\n"
            "2. Click the grey panels to scratch them off.\n"
            "3. Three matching symbols show your prize. It's already been added to your account.\n\n"
            "**Possible prizes on this server:**\n"
            + "\n".join(f"• {p}" for p in prizes)
            + f"\n\nChip prizes are {low:,}–{high:,} chips (converted to server currency in bank mode)."
        )
        if url := embed_image("help"):
            e.set_thumbnail(url=url)
        await interaction.response.send_message(embed=e, ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        self.stop()
        await safe_defer(interaction)
        balance = await get_balance(self._member, self._conf, self._user)
        if self._conf.payment_mode == "chips":
            currency_name = "chips"
        else:
            currency_name = await bank.get_currency_name(self._member.guild)
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    # ------------------------------------------------------------------
    # Embeds
    # ------------------------------------------------------------------

    def _footer(self, e: discord.Embed) -> None:
        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="🎟️ High Roller: Scratch Cards", color=PALETTE_GOLD)
        hours = self._conf.scratch_cooldown_hours
        if self._card_ready():
            e.description = (
                f"**A free scratch card, once every {hours} hours.**\n\n"
                "Your card is ready. Press **Scratch Card** to claim it."
            )
        else:
            wait = time_until_ready(self._user.last_scratch_date, hours)
            e.description = (
                "**You've scratched your card.**\n\n"
                f"Your next card is ready in **{wait}**."
            )
        self._footer(e)
        return e

    def _build_result_embed(
        self,
        reward_type: str,
        chip_amount: int,
        payout_amount: int,
        currency_name: str,
        old_rank: int,
        new_rank: int,
    ) -> discord.Embed:
        cells = build_card(reward_type)
        # Each panel is a spoiler: clicking it in Discord "scratches" it off.
        grid = "\n".join(" ".join(f"||{c}||" for c in cells[r * 3:r * 3 + 3]) for r in range(3))

        if reward_type == "chips":
            prize = f"+{payout_amount:,} {currency_name}"
            if self._conf.payment_mode != "chips":
                prize += f" (from {chip_amount:,} chips)"
        elif reward_type == "bonus_bet_token":
            prize = "+1 Bonus Bet Token"
        elif reward_type == "free_spin":
            prize = "+1 Free Slots Spin"
        else:
            prize = REWARD_DISPLAY.get(reward_type, reward_type)

        e = discord.Embed(title="🎟️ High Roller: Scratch Cards", color=PALETTE_GOLD)
        e.description = (
            "**Scratch the panels!** Three of a kind wins.\n\n"
            f"{grid}\n\n"
            f"Prize: ||**{prize}**||\n"
            f"*{REWARD_DESCRIPTION.get(reward_type, '')}*"
        )
        if new_rank != old_rank:
            if new_rank > old_rank:
                e.description += f"\n\n🏆 **Rank Up!** You are now a **{RANK_NAMES.get(new_rank, 'Unknown')}**!"
            else:
                e.description += (
                    f"\n\n📉 **Rank Down.** **{RANK_NAMES.get(old_rank, 'Unknown')}** → "
                    f"**{RANK_NAMES.get(new_rank, 'Unknown')}**."
                )
        e.add_field(
            name="Next card",
            value=f"in {time_until_ready(self._user.last_scratch_date, self._conf.scratch_cooldown_hours)}",
            inline=False,
        )
        self._footer(e)
        return e
