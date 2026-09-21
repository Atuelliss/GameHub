"""Big6WheelView -- Discord UI for the Big Six Wheel game in HighRollerClub.

Game flow
---------
Phase 1 (idle)    : Player sees the game prompt with active bonus indicators
                    and the current house edge segment count.
                    Buttons: Spin the Wheel | Back to Floor | How to Play

Phase 2 (pick)    : Player has entered a bet amount via BetModal.
                    Row 0: [$1]  [$2]  [$5]
                    Row 1: [$10] [$20] [Jackpot]
                    Row 4: Change Bet | Back to Floor
                    Clicking any segment button immediately spins and resolves.

Phase 3 (result)  : Wheel result shown with win/loss details.
                    Buttons: Change Bet | Spin Again ([last_bet] on [last_segment])
                             | Back to Floor | How to Play

Access guard
------------
_check_access() is called at the top of every action button callback.
Checks:
  1. is_allowed_channel(conf, interaction.channel_id)
  2. conf.games_enabled.get("big6", True)
Callers return immediately when this returns False.

Bonus stacking order (win only)
---------------------------------
  1. consume_bonus_bet_token(user, "big6") -- "big6" IS in BONUS_BET_TOKEN_ELIGIBLE_GAMES;
     may return True and consume the token if the player has one.
  2. raw_payout = calculate_payout(bet, segment)   [gross, includes returned stake]
  3. If Lucky Streak active: bonus = apply_lucky_streak_bonus(raw_payout)
     total_payout = raw_payout + bonus
  4. Multiplier Wheel guard -- "big6" NOT in MULTIPLIER_ELIGIBLE_GAMES:
     guard evaluates False; consume_multiplier() is never called.
  5. If token_active: total_payout *= 2

On any loss: cancel_lucky_streak(user) if streak is active; notify player.

Pure game logic lives in games/big_6_wheel.py.
"""

from __future__ import annotations

import random

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.constants import (
    MULTIPLIER_ELIGIBLE_GAMES,
    PALETTE_GOLD,
    RANK_NAMES,
    SPECIALTY_TITLES,
    embed_image,
)
from ..common.interactions import safe_defer, safe_edit_original_response
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    apply_lucky_streak_bonus,
    apply_rank_change,
    cancel_lucky_streak,
    consume_bonus_bet_token,
    consume_multiplier,
    credit_balance,
    deduct_balance,
    evaluate_rank,
    evaluate_specialty_titles,
    get_balance,
    get_bet_limits,
    get_pending_multiplier,
    has_bonus_bet_token,
    has_lucky_streak,
    is_allowed_channel,
    record_loss,
    record_win,
    validate_bet,
)
from ..common.constants import BIG6_DEFAULT_SEGMENTS
from ..games.big_6_wheel import (
    BIG6_PAYOUTS,
    PLAYER_SEGMENTS,
    SEGMENT_DISPLAY,
    SEGMENT_EMOJI,
    build_wheel,
    calculate_payout,
    is_house_segment,
    spin_wheel,
    win_probability,
)

# Non-house segment counts used for probability display throughout the view.
BIG6_DEFAULT_SEGMENTS_COUNT: dict[str, int] = {
    k: v for k, v in BIG6_DEFAULT_SEGMENTS.items() if k != "house"
}

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_FLAVOR: list[str] = [
    "The wheel knows your name tonight.",
    "Right where you called it.",
    "A steady hand, a steady win.",
    "The Club pays its dues.",
    "Fortune rewarded the patient.",
    "Precision bet. Clean result.",
    "You read the wheel correctly.",
]

_LOSS_FLAVOR: list[str] = [
    "The house claims this one.",
    "The wheel turned against you.",
    "House segment. It happens.",
    "The odds caught up for a spin.",
    "The wheel has no favorites.",
    "Not this time -- spin again.",
    "The Club endures. So do you.",
]


# ---------------------------------------------------------------------------
# Bet modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Big Six Wheel: Place Your Bet"):
    def __init__(self, view: Big6WheelView, min_bet: int, max_bet: int) -> None:
        super().__init__()
        self._view = view
        self.bet_input = discord.ui.TextInput(
            label=f"Bet Amount (min {min_bet:,} · max {max_bet:,})",
            placeholder=f"Enter a value between {min_bet:,} and {max_bet:,}",
            min_length=1,
            max_length=10,
        )
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        raw = self.bet_input.value.strip().replace(",", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.followup.send(
                "Please enter a valid positive whole number.", ephemeral=True
            )
            return
        await self._view._start_pick_phase(interaction, int(raw))


# ---------------------------------------------------------------------------
# Main Big Six Wheel View
# ---------------------------------------------------------------------------

class Big6WheelView(discord.ui.View):
    """Discord UI view for the Big Six Wheel game.

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

        # Balance cache -- refreshed after every resolve.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Bet state.
        self._last_bet: int | None = None
        self._last_segment: str | None = None

        self._add_idle_buttons()

    # ------------------------------------------------------------------
    # Interaction guard
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Button layouts
    # ------------------------------------------------------------------

    def _add_idle_buttons(self) -> None:
        play = discord.ui.Button(
            label="🎡 Spin the Wheel", style=discord.ButtonStyle.green, row=0
        )
        play.callback = self._on_play
        self.add_item(play)

        back = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    def _add_segment_buttons(self) -> None:
        """Add one button per bettable segment, 3 per row, plus action row."""
        house_count = self._conf.big6_house_segments
        total = house_count + 46

        row_labels: dict[str, tuple[int, discord.ButtonStyle]] = {
            "$1":      (0, discord.ButtonStyle.green),
            "$2":      (0, discord.ButtonStyle.green),
            "$5":      (0, discord.ButtonStyle.blurple),
            "$10":     (1, discord.ButtonStyle.blurple),
            "$20":     (1, discord.ButtonStyle.red),
            "jackpot": (1, discord.ButtonStyle.red),
        }

        for seg in PLAYER_SEGMENTS:
            row, style = row_labels[seg]
            prob = BIG6_DEFAULT_SEGMENTS_COUNT[seg] / total
            net = BIG6_PAYOUTS[seg]
            pct = f"{prob * 100:.1f}%"
            label = f"{SEGMENT_EMOJI.get(seg, '')} {SEGMENT_DISPLAY[seg]} ({net}:1 · {pct})"
            btn = discord.ui.Button(label=label, style=style, row=row)
            # Closure capture via default arg.
            btn.callback = self._make_segment_callback(seg)
            self.add_item(btn)

        change = discord.ui.Button(
            label="💰 Change Bet", style=discord.ButtonStyle.grey, row=4
        )
        change.callback = self._on_change_bet
        self.add_item(change)

        back = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=4
        )
        back.callback = self._back_to_floor
        self.add_item(back)

    def _make_segment_callback(self, segment: str):
        async def _callback(interaction: discord.Interaction) -> None:
            if not await self._check_access(interaction):
                return
            await interaction.response.defer()
            self._last_segment = segment
            await self._resolve(interaction)
        return _callback

    def _add_result_buttons(self) -> None:
        change = discord.ui.Button(
            label="💰 Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._on_change_bet
        self.add_item(change)

        if self._last_bet is not None and self._last_segment is not None:
            seg_label = SEGMENT_DISPLAY.get(self._last_segment, self._last_segment)
            again = discord.ui.Button(
                label=f"🎡 Again ({self._last_bet:,} on {seg_label})",
                style=discord.ButtonStyle.green,
                row=0,
            )
            again.callback = self._on_spin_again
            self.add_item(again)

        back = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    # ------------------------------------------------------------------
    # Access guard
    # ------------------------------------------------------------------

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if not is_allowed_channel(self._conf, interaction.channel_id):
            await interaction.response.send_message(
                "Big Six Wheel can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not self._conf.games_enabled.get("big6", True):
            await interaction.response.send_message(
                "Big Six Wheel is currently disabled on this server.",
                ephemeral=True,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _on_play(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "big6", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _on_change_bet(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "big6", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _on_spin_again(self, interaction: discord.Interaction) -> None:
        """Reuse last bet and segment -- resolve immediately."""
        if not await self._check_access(interaction):
            return
        if self._last_bet is None or self._last_segment is None:
            await interaction.response.send_message(
                "No previous bet to repeat.", ephemeral=True
            )
            return
        await safe_defer(interaction)
        await self._resolve(interaction)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        house_count = self._conf.big6_house_segments
        total = house_count + 46

        e = discord.Embed(title="🎡 How to Play: Big Six Wheel", color=PALETTE_GOLD)
        e.description = (
            "Choose a segment label and place your bet. The wheel spins once -- "
            "if the ball lands on your chosen segment, you win based on that segment's "
            "payout ratio. If it lands on a house segment, you lose your bet.\n\n"
            "**Current Wheel Composition**"
        )

        rows = []
        for seg in PLAYER_SEGMENTS:
            count = BIG6_DEFAULT_SEGMENTS_COUNT[seg]
            prob = count / total * 100
            net = BIG6_PAYOUTS[seg]
            display = SEGMENT_DISPLAY[seg]
            emoji = SEGMENT_EMOJI.get(seg, "")
            rows.append(f"{emoji} **{display}** -- {net}:1 payout · {count}/{total} = {prob:.1f}% chance")

        house_prob = house_count / total * 100
        rows.append(
            f"🏠 **House** -- always loses · {house_count}/{total} = {house_prob:.1f}% chance"
        )
        e.add_field(name="Segments", value="\n".join(rows), inline=False)

        e.add_field(
            name="Bonuses",
            value=(
                "• **Lucky Streak** -- adds 25% to raw payout on any win; "
                "cancelled on any loss\n"
                "• **Bonus Bet Token** -- doubles your total payout on a win\n"
                "• Multiplier Wheel does not apply to Big Six"
            ),
            inline=False,
        )
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

    # ------------------------------------------------------------------
    # Pick phase entry point (called from BetModal.on_submit)
    # ------------------------------------------------------------------

    async def _start_pick_phase(
        self, interaction: discord.Interaction, bet: int
    ) -> None:
        balance = await get_balance(self._member, self._conf, self._user)
        error = validate_bet(self._conf, self._user, "big6", bet, balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        self._last_bet = bet
        self.clear_items()
        self._add_segment_buttons()
        await safe_edit_original_response(interaction, embed=self._build_pick_embed(), view=self)

    # ------------------------------------------------------------------
    # Embed builders
    # ------------------------------------------------------------------

    def _build_idle_embed(self) -> discord.Embed:
        user = self._user
        conf = self._conf
        house_count = conf.big6_house_segments
        total = house_count + 46

        e = discord.Embed(title="🎡 High Roller: Big Six Wheel", color=PALETTE_GOLD)

        desc = (
            "**Spin the wheel. Pick your segment. Beat the house.**\n\n"
            "Six bettable segments pay from **1:1 even money** up to **40:1 jackpot**. "
            f"The wheel has **{house_count} house segments** out of {total} total "
            f"({house_count / total * 100:.1f}% house chance).\n\n"
            "How it works: enter your bet, choose one segment, then the wheel spins once. "
            "If the ball lands on your segment, you win that segment's payout.\n\n"
            "Press **Spin the Wheel** to enter your bet and choose a segment."
        )

        mul = get_pending_multiplier(user)
        if mul is not None:
            desc += f"\n\n⚡ Bonus snapshot: **{mul}x** multiplier is stored on your account, but Big Six does not use it."
        if has_bonus_bet_token(user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token doubles payout if it is still unused when a win resolves."
        if has_lucky_streak(user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak adds +25% if it is still active on your next win."

        e.description = desc

        if url := embed_image("big6"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )
        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the _launch_game protocol."""
        return self._build_idle_embed()

    def _build_pick_embed(self) -> discord.Embed:
        conf = self._conf
        house_count = conf.big6_house_segments
        total = house_count + 46
        bet = self._last_bet or 0
        cur = self._cached_currency or "chips"

        e = discord.Embed(title="🎡 High Roller: Big Six Wheel", color=PALETTE_GOLD)

        rows = []
        for seg in PLAYER_SEGMENTS:
            count = BIG6_DEFAULT_SEGMENTS_COUNT[seg]
            prob = count / total * 100
            net = BIG6_PAYOUTS[seg]
            gross_win = bet * (net + 1)
            display = SEGMENT_DISPLAY[seg]
            emoji = SEGMENT_EMOJI.get(seg, "")
            rows.append(
                f"{emoji} **{display}** -- {net}:1 · {prob:.1f}% · win: **{gross_win:,}** {cur}"
            )

        house_prob = house_count / total * 100
        rows.append(f"🏠 House -- loss · {house_prob:.1f}% chance")

        e.description = (
            f"**Bet:** {bet:,} {cur}\n\n"
            "Pick a segment to spin the wheel:\n\n"
            + "\n".join(rows)
        )

        if url := embed_image("big6"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )
        return e

    def _build_result_embed(self, result: dict) -> discord.Embed:
        e = discord.Embed(title="🎡 High Roller: Big Six Wheel", color=PALETTE_GOLD)

        seg_chosen  = result["segment_chosen"]
        seg_landed  = result["segment_landed"]
        is_win      = result["is_win"]
        bet         = result["bet"]
        payout      = result["payout"]
        cur         = self._cached_currency

        chosen_display = SEGMENT_DISPLAY.get(seg_chosen, seg_chosen)
        landed_display = (
            SEGMENT_DISPLAY.get(seg_landed, seg_landed)
            if seg_landed != "house" else "🏠 House"
        )
        chosen_emoji = SEGMENT_EMOJI.get(seg_chosen, "")
        landed_emoji = SEGMENT_EMOJI.get(seg_landed, "🏠")

        if is_win:
            desc = (
                f"🎡 The wheel lands on: {landed_emoji} **{landed_display}**\n\n"
                f"✅ **You bet on {chosen_emoji} {chosen_display} -- WIN!**\n"
                f"Bet: **{bet:,}** {cur} "
                f"→ Payout: **{payout:,}** {cur} "
                f"*(+{payout - bet:,} profit)*\n"
                f"*{random.choice(_WIN_FLAVOR)}*"
            )
        else:
            desc = (
                f"🎡 The wheel lands on: {landed_emoji} **{landed_display}**\n\n"
                f"❌ **You bet on {chosen_emoji} {chosen_display} -- no win.**\n"
                f"Bet of **{bet:,}** {cur} lost.\n"
                f"*{random.choice(_LOSS_FLAVOR)}*"
            )

        if result.get("streak_cancelled"):
            desc += "\n💔 **Your lucky streak has ended.**"

        if result.get("token_used"):
            desc += "\n🎫 **Bonus Bet Token used -- payout doubled!**"

        if result.get("rank_changed"):
            old_name = RANK_NAMES.get(result["old_rank"], "Unknown")
            new_name = RANK_NAMES.get(result["new_rank"], "Unknown")
            if result["new_rank"] > result["old_rank"]:
                desc += f"\n🏆 **Rank Up!** You are now a **{new_name}**!"
            else:
                desc += f"\n📉 **Rank Down.** **{old_name}** → **{new_name}**."

        for slug in result.get("new_titles", []):
            title_str = SPECIALTY_TITLES.get(slug, slug)
            desc += f"\n🎖️ **New title unlocked:** {title_str}"

        e.description = desc

        if url := embed_image("big6"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )
        return e

    # ------------------------------------------------------------------
    # Game resolution
    # ------------------------------------------------------------------

    async def _resolve(self, interaction: discord.Interaction) -> None:
        member   = self._member
        conf     = self._conf
        user     = self._user
        bet      = self._last_bet
        segment  = self._last_segment

        # 1. Bonus Bet Token -- "big6" IS in BONUS_BET_TOKEN_ELIGIBLE_GAMES.
        #    Consume before deducting so the token is only spent on real spins.
        token_active = False
        if has_bonus_bet_token(user):
            token_active = consume_bonus_bet_token(user, "big6")

        # 2. Deduct balance before the spin.
        await deduct_balance(member, conf, user, bet)

        # 3. Build wheel from admin-configured house segment count, then spin.
        house_count = conf.big6_house_segments
        wheel = build_wheel(house_count)
        landed = spin_wheel(wheel)

        # 4. Evaluate outcome.
        is_win = (landed == segment)

        streak_cancelled = False

        if is_win:
            # ----------------------------------------------------------------
            # Win path
            # ----------------------------------------------------------------
            raw_payout   = calculate_payout(bet, segment)
            total_payout = raw_payout

            # Lucky Streak adds 25% of raw payout.
            if has_lucky_streak(user):
                total_payout += apply_lucky_streak_bonus(raw_payout)

            # Multiplier Wheel -- "big6" is NOT in MULTIPLIER_ELIGIBLE_GAMES.
            # Guard is explicit so it auto-activates if the constant ever changes.
            if "big6" in MULTIPLIER_ELIGIBLE_GAMES:
                multiplier = consume_multiplier(user)
                if multiplier is not None:
                    profit = total_payout - bet
                    total_payout += int(profit * (multiplier - 1.0))

            # Bonus Bet Token -- doubles total payout if active.
            if token_active:
                total_payout *= 2

            await credit_balance(member, conf, user, total_payout)
            record_win(conf, user, "big6", total_payout, bet)

        else:
            # ----------------------------------------------------------------
            # Loss path (includes house segments and wrong-segment landings)
            # ----------------------------------------------------------------
            total_payout = 0

            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True

            record_loss(conf, user, "big6", bet)

        # 5. Rank evaluation.
        new_rank     = evaluate_rank(conf, user)
        old_rank     = user.rank
        rank_changed = new_rank != old_rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        # 6. Specialty titles.
        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        # 7. Save (synchronous -- no await).
        self._cog.save()

        # 8. Refresh cached balance for embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # 9. Build result and update message.
        result = {
            "bet":              bet,
            "segment_chosen":   segment,
            "segment_landed":   landed,
            "is_win":           is_win,
            "payout":           total_payout,
            "token_used":       token_active,
            "streak_cancelled": streak_cancelled,
            "rank_changed":     rank_changed,
            "old_rank":         old_rank,
            "new_rank":         new_rank,
            "new_titles":       new_titles,
        }

        self.clear_items()
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(result), view=self)



