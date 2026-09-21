"""MysteryWheelView -- Discord UI for the Mystery Wheel in HighRollerClub.

Game flow
---------
Phase 1 (idle)   : Player sees daily-spin status, reward pool summary, and balance.
                   Buttons: Spin the Wheel | Back to Floor | How to Play

Phase 2 (result) : One free daily spin resolves to a reward from the configured pool.
                   Buttons: Back to Floor | How to Play

Access guard
------------
_check_access() is called at the top of every action button callback.
Checks:
  1. is_allowed_channel(conf, interaction.channel_id)
  2. conf.games_enabled.get("mysteryspin", True)
  3. conf.mystery_wheel_enabled
Callers return immediately when False.

Economy / progression rules
---------------------------
- Mystery Wheel is free: there is no bet and no balance deduction.
- No record_win / record_loss calls; this is a reward mode, not a wagered game.
- If reward_type == "chips": chip value is credited directly in chip mode.
  In bank mode, the chip value is converted using discord_currency_conversion_rate
  before depositing to the Red bank balance.
- If reward_type == "rank_xp": prestige_points are increased and rank is re-evaluated.
- Multiplier Wheel does not apply to Mystery Wheel. Active multipliers remain untouched.

Pure game logic lives in games/mystery_wheel.py.
"""

from __future__ import annotations

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.constants import MULTIPLIER_ELIGIBLE_GAMES, PALETTE_GOLD, RANK_NAMES, embed_image
from ..common.interactions import safe_defer, safe_edit_original_response
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    apply_rank_change,
    credit_balance,
    evaluate_rank,
    get_balance,
    get_pending_multiplier,
    is_allowed_channel,
)
from ..games.mystery_wheel import (
    REWARD_DESCRIPTION,
    REWARD_DISPLAY,
    apply_reward,
    can_spin,
    get_today_date_string,
    pick_reward,
    roll_chip_amount,
    time_until_reset,
)


class MysteryWheelView(discord.ui.View):
    """Mystery Wheel lobby and daily reward view.

    Constructor signature: (interaction, conf, user, cog)
    Matches the protocol expected by _launch_game in user_commands.py.
    """

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
        self._last_result: dict | None = None

        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        self._add_idle_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._member.id:
            await interaction.response.send_message(
                "This isn't your game session. Run `[p]highrollerclub` to start your own.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        self.clear_items()

    def _spin_available(self) -> bool:
        return can_spin(self._user.last_mystery_wheel_date, self._conf.mystery_wheel_timezone)

    def _add_idle_buttons(self) -> None:
        self.clear_items()

        spin_btn = discord.ui.Button(
            label="🌀 Spin the Wheel",
            style=discord.ButtonStyle.green,
            row=0,
            disabled=not self._spin_available(),
        )
        spin_btn.callback = self._on_spin
        self.add_item(spin_btn)

        back_btn = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back_btn.callback = self._back_to_floor
        self.add_item(back_btn)

        info_btn = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info_btn.callback = self._show_info
        self.add_item(info_btn)

    def _add_result_buttons(self) -> None:
        self.clear_items()

        back_btn = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back_btn.callback = self._back_to_floor
        self.add_item(back_btn)

        info_btn = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info_btn.callback = self._show_info
        self.add_item(info_btn)

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if not is_allowed_channel(self._conf, interaction.channel_id):
            await interaction.response.send_message(
                "Mystery Wheel can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False
        if not self._conf.games_enabled.get("mysteryspin", True):
            await interaction.response.send_message(
                "Mystery Wheel is currently disabled on this server.",
                ephemeral=True,
            )
            return False
        if not self._conf.mystery_wheel_enabled:
            await interaction.response.send_message(
                "Mystery Wheel is not enabled on this server.",
                ephemeral=True,
            )
            return False
        return True

    async def _on_spin(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        if not self._spin_available():
            await interaction.response.send_message(
                (
                    "You've already used today's Mystery Wheel spin. "
                    f"Come back in **{time_until_reset(self._conf.mystery_wheel_timezone)}**."
                ),
                ephemeral=True,
            )
            return

        await safe_defer(interaction)

        conf = self._conf
        user = self._user
        member = self._member

        reward_type = pick_reward(conf.mystery_wheel_reward_pool)
        chip_amount = roll_chip_amount() if reward_type == "chips" else 0

        payout_amount = 0
        currency_name = "chips"
        if conf.payment_mode == "bank":
            currency_name = await bank.get_currency_name(member.guild)

        if reward_type == "chips":
            if conf.payment_mode == "chips":
                payout_amount = chip_amount
            else:
                payout_amount = chip_amount // max(conf.discord_currency_conversion_rate, 1)
                if payout_amount <= 0:
                    payout_amount = 1
            await credit_balance(member, conf, user, payout_amount)

        apply_reward(user, reward_type, chip_amount)
        user.last_mystery_wheel_date = get_today_date_string(conf.mystery_wheel_timezone)
        user.mystery_wheel_last_reward_type = reward_type
        user.mystery_wheel_last_chip_amount = chip_amount
        user.mystery_wheel_last_payout_amount = payout_amount
        user.mystery_wheel_last_currency_name = currency_name

        old_rank = user.rank
        new_rank = evaluate_rank(conf, user)
        rank_changed = new_rank != old_rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        self._cog.save()

        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = currency_name

        multiplier_applies = "mysteryspin" in MULTIPLIER_ELIGIBLE_GAMES
        active_multiplier = get_pending_multiplier(user)

        result = {
            "reward_type": reward_type,
            "chip_amount": chip_amount,
            "payout_amount": payout_amount,
            "currency_name": currency_name,
            "rank_changed": rank_changed,
            "old_rank": old_rank,
            "new_rank": new_rank,
            "active_multiplier": active_multiplier,
            "multiplier_applies": multiplier_applies,
        }
        self._last_result = result

        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(result), view=self)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        reward_lines = []
        for reward in self._conf.mystery_wheel_reward_pool:
            label = REWARD_DISPLAY.get(reward)
            if label is not None:
                reward_lines.append(f"• {label}")
        if not reward_lines:
            reward_lines.append(f"• {REWARD_DISPLAY['chips']}")

        e = discord.Embed(title="🌀 How to Play: Mystery Wheel", color=PALETTE_GOLD)
        e.description = (
            "**One free spin per calendar day, reset in the server timezone.**\n\n"
            "1. Click **Spin the Wheel** to claim today's reward.\n"
            "2. The reward is selected at random from the server's configured reward pool.\n"
            "3. After you spin, the wheel locks until midnight in the configured timezone.\n\n"
            "**Possible rewards on this server:**\n"
            + "\n".join(reward_lines)
            + "\n\n• Multiplier Wheel does not apply to Mystery Wheel rewards."
        )

        if url := embed_image("mysteryspin"):
            e.set_thumbnail(url=url)

        await interaction.response.send_message(embed=e, ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        await safe_defer(interaction)
        balance = await get_balance(self._member, self._conf, self._user)
        if self._conf.payment_mode == "chips":
            currency_name = "chips"
        else:
            currency_name = await bank.get_currency_name(self._member.guild)
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    def _format_reward_value(
        self,
        reward_type: str,
        chip_amount: int,
        payout_amount: int,
        currency_name: str,
    ) -> str:
        reward_text = REWARD_DESCRIPTION.get(reward_type, "A mystery reward has been granted.")
        if reward_type == "chips":
            if self._conf.payment_mode == "chips":
                return f"**+{payout_amount:,} chips**"
            return (
                f"**+{payout_amount:,} {currency_name}** "
                f"from **{chip_amount:,} chip value**"
            )
        if reward_type == "bonus_bet_token":
            return "**+1 Bonus Bet Token**"
        if reward_type == "free_spin":
            return "**+1 Free Slots Spin**"
        return reward_text

    def _build_idle_embed(self) -> discord.Embed:
        can_claim = self._spin_available()
        timezone_name = self._conf.mystery_wheel_timezone

        e = discord.Embed(title="🌀 High Roller: Mystery Wheel", color=PALETTE_GOLD)

        if can_claim:
            desc = (
                "**One free spin. Once per day. No wager required.**\n\n"
                "Claim a random reward from the server's configured Mystery Wheel pool. "
                "Rewards can include chips, bonus tokens, free spins, Lucky Streak, or rank XP.\n\n"
                "Press **Spin the Wheel** to use today's free spin."
            )
        else:
            desc = (
                "**Today's Mystery Wheel spin has already been used.**\n\n"
                f"The wheel resets in **{time_until_reset(timezone_name)}** "
                f"based on **{timezone_name}**.\n\n"
                "You can still open **How to Play** to review the reward pool."
            )

            reward_type = self._user.mystery_wheel_last_reward_type
            if reward_type is not None:
                currency_name = (
                    self._user.mystery_wheel_last_currency_name
                    or self._cached_currency
                    or "chips"
                )
                reward_value = self._format_reward_value(
                    reward_type,
                    self._user.mystery_wheel_last_chip_amount,
                    self._user.mystery_wheel_last_payout_amount,
                    currency_name,
                )
                reward_label = REWARD_DISPLAY.get(reward_type, reward_type)
                desc += (
                    f"\n\n**Last reward claimed today:** {reward_label}\n"
                    f"{reward_value}"
                )

        active_multiplier = get_pending_multiplier(self._user)
        if active_multiplier is not None and "mysteryspin" not in MULTIPLIER_ELIGIBLE_GAMES:
            desc += (
                f"\n\n⚡ Bonus snapshot: **{active_multiplier}x** multiplier is stored on your account, "
                "but it does not apply to Mystery Wheel rewards."
            )

        e.description = desc

        if url := embed_image("mysteryspin"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")

        return e

    def _build_result_embed(self, result: dict) -> discord.Embed:
        reward_type = result["reward_type"]
        reward_label = REWARD_DISPLAY.get(reward_type, reward_type)
        reward_text = REWARD_DESCRIPTION.get(reward_type, "A mystery reward has been granted.")
        reward_value = self._format_reward_value(
            reward_type,
            result["chip_amount"],
            result["payout_amount"],
            result["currency_name"],
        )

        e = discord.Embed(title="🌀 High Roller: Mystery Wheel", color=PALETTE_GOLD)
        e.description = (
            f"🎯 **The wheel lands on: {reward_label}!**\n\n"
            f"{reward_value}\n\n"
            f"*{reward_text}*"
        )

        if result["reward_type"] == "rank_xp" and result["rank_changed"]:
            old_name = RANK_NAMES.get(result["old_rank"], "Unknown")
            new_name = RANK_NAMES.get(result["new_rank"], "Unknown")
            if result["new_rank"] > result["old_rank"]:
                e.description += f"\n\n🏆 **Rank Up!** You are now a **{new_name}**!"
            else:
                e.description += f"\n\n📉 **Rank Down.** **{old_name}** → **{new_name}**."

        if result["active_multiplier"] is not None and not result["multiplier_applies"]:
            e.description += (
                f"\n\n⚡ Your active **{result['active_multiplier']}x** multiplier was not consumed. "
                "Mystery Wheel does not qualify for multiplier bonuses."
            )

        if url := embed_image("mysteryspin"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")

        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the _launch_game protocol."""
        return self._build_idle_embed()