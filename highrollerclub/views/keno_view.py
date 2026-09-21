"""KenoView -- Discord UI for the Keno number-pick game in HighRollerClub.

Game flow
---------
Phase 1 (idle)    : Player sees the game prompt with active bonus indicators.
                    Buttons: Play Keno | Back to Floor | How to Play

Phase 2 (picking) : Player selects 1-10 numbers from four range Select menus
                    (1-20, 21-40, 41-60, 61-80). Total across all menus must
                    be 1-10 before confirming. The embed updates live as
                    numbers are selected.
                    Row 4 buttons: Confirm Picks | Change Bet | Back to Floor

Phase 3 (result)  : Drawn numbers revealed; hits counted; payout applied.
                    Buttons: Change Bet | Play Again (X) | Back to Floor | How to Play

Access guard
------------
_check_access() is called at the top of every action button/select callback
before any game logic runs. It checks:
  1. is_allowed_channel(conf, interaction.channel_id)
  2. conf.games_enabled.get("keno", True)
Callers return immediately if _check_access returns False.

Bonus stacking order (win only)
---------------------------------
  1. raw_payout = calculate_payout(bet, spots, hits)
  2. If Lucky Streak active: bonus = apply_lucky_streak_bonus(raw_payout)
     total_payout = raw_payout + bonus
  3. Multiplier Wheel guard -- "keno" in MULTIPLIER_ELIGIBLE_GAMES (True):
     multiplier = consume_multiplier(user)
     if multiplier is not None:
         profit = total_payout - bet
         total_payout += int(profit * (multiplier - 1.0))
  4. If Bonus Bet Token consumed before draw: total_payout *= 2

On any loss: cancel_lucky_streak(user) if streak is active; notify player.
The Bonus Bet Token is consumed before the draw -- consistent with other
eligible games (consumed regardless of outcome; only pays on win).

Pure game logic lives in games/keno.py.
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
from ..common.interactions import safe_defer, safe_edit_original_response, safe_response_edit_message
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
    get_game_rng,
    get_pending_multiplier,
    has_bonus_bet_token,
    has_lucky_streak,
    is_allowed_channel,
    record_loss,
    record_win,
    validate_bet,
)
from ..games.keno import (
    KENO_PAYTABLE,
    MAX_PICKS,
    MIN_PICKS,
    POOL_SIZE,
    calculate_payout,
    count_hits,
    draw_numbers,
)

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_FLAVOR: list[str] = [
    "The numbers aligned -- the odds bent in your favor.",
    "A precise read of the board. Well played.",
    "Fortune smiled on your selection today.",
    "You picked winners out of a pool of eighty. Impressive.",
    "The board was generous, and you were ready for it.",
    "A calculated bet, a satisfying result.",
    "The Club respects a Keno player with an eye for numbers.",
]

_LOSS_FLAVOR: list[str] = [
    "The board had other plans today.",
    "Eighty numbers, and the odds did not swing your way.",
    "A near miss is still a miss. The chips belong to the house.",
    "The draw was cruel -- better luck next round.",
    "Keno favors the patient. Try again.",
    "The house draws what it draws. No hard feelings.",
    "The Club will be here when your numbers come in.",
]


# ---------------------------------------------------------------------------
# Range Select component
# ---------------------------------------------------------------------------

class RangeSelect(discord.ui.Select):
    """Multi-select picker for one 20-number range in the keno number grid.

    Four instances cover 1-20, 21-40, 41-60, and 61-80.  Each select
    fires a callback that updates KenoView._range_picks for that range and
    re-renders the pick embed to show the updated total.
    """

    def __init__(self, keno_view: KenoView, range_start: int, row: int) -> None:
        range_end = range_start + 19
        options = [
            discord.SelectOption(label=str(n), value=str(n))
            for n in range(range_start, range_end + 1)
        ]
        super().__init__(
            placeholder=f"Numbers {range_start}-{range_end} (pick any)",
            min_values=0,
            max_values=10,
            options=options,
            row=row,
        )
        self._keno_view = keno_view
        self._range_start = range_start

    async def callback(self, interaction: discord.Interaction) -> None:
        # Update picks for this range and re-render the pick embed with live count.
        selected = [int(v) for v in self.values]
        self._keno_view._range_picks[self._range_start] = selected
        total = self._keno_view._picks_total
        await safe_response_edit_message(interaction, embed=self._keno_view._build_pick_embed(total), view=self._keno_view)


# ---------------------------------------------------------------------------
# Bet modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Keno: Place Your Bet"):
    def __init__(self, view: KenoView, min_bet: int, max_bet: int) -> None:
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
# Main Keno View
# ---------------------------------------------------------------------------

class KenoView(discord.ui.View):
    """Discord UI view for the Keno number-pick game.

    Constructor signature: (interaction, conf, user, cog)
    This matches the protocol expected by _launch_game in user_commands.py.
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
        self._interaction: discord.Interaction = interaction

        # Balance cache -- refreshed after every resolve so embed builders stay sync.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Last validated bet -- enables Play Again without reopening the modal.
        self._last_bet: int | None = None

        # Pick state -- one list per range start (1, 21, 41, 61).
        self._range_picks: dict[int, list[int]] = {1: [], 21: [], 41: [], 61: []}

        self._add_idle_buttons()

    # ------------------------------------------------------------------
    # Pick state helpers
    # ------------------------------------------------------------------

    @property
    def _picks_total(self) -> int:
        return sum(len(v) for v in self._range_picks.values())

    @property
    def _all_picks(self) -> list[int]:
        picks: list[int] = []
        for v in self._range_picks.values():
            picks.extend(v)
        return sorted(picks)

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
            label="🎰 Play Keno", style=discord.ButtonStyle.green, row=0
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

    def _add_pick_buttons(self) -> None:
        """Add the four range selects (rows 0-3) and the action row (row 4)."""
        for idx, start in enumerate([1, 21, 41, 61]):
            self.add_item(RangeSelect(self, start, row=idx))

        confirm = discord.ui.Button(
            label="✅ Confirm Picks", style=discord.ButtonStyle.green, row=4
        )
        confirm.callback = self._on_confirm
        self.add_item(confirm)

        change = discord.ui.Button(
            label="💰 Change Bet", style=discord.ButtonStyle.blurple, row=4
        )
        change.callback = self._on_change_bet
        self.add_item(change)

        back = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=4
        )
        back.callback = self._back_to_floor
        self.add_item(back)

    def _add_result_buttons(self) -> None:
        change = discord.ui.Button(
            label="💰 Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._on_change_bet
        self.add_item(change)

        if self._last_bet is not None:
            again = discord.ui.Button(
                label=f"🎰 Play Again ({self._last_bet:,})",
                style=discord.ButtonStyle.green,
                row=0,
            )
            again.callback = self._on_play_again
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
        """Returns True if the player may act. Sends an ephemeral error and
        returns False if the channel is restricted or the game is disabled.
        Callers must return immediately when this returns False.
        """
        conf = self._conf

        if not is_allowed_channel(conf, interaction.channel_id):
            await interaction.response.send_message(
                "Keno can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not conf.games_enabled.get("keno", True):
            await interaction.response.send_message(
                "Keno is currently disabled on this server.",
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
        min_bet, max_bet = get_bet_limits(self._conf, "keno", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _on_play_again(self, interaction: discord.Interaction) -> None:
        """Result button -- reuse last bet and go directly to picker phase."""
        if not await self._check_access(interaction):
            return
        self._range_picks = {1: [], 21: [], 41: [], 61: []}
        self.clear_items()
        self._add_pick_buttons()
        await safe_response_edit_message(interaction, embed=self._build_pick_embed(0), view=self)

    async def _on_change_bet(self, interaction: discord.Interaction) -> None:
        """Return to idle phase so the player can enter a new bet amount."""
        if not await self._check_access(interaction):
            return
        self._range_picks = {1: [], 21: [], 41: [], 61: []}
        self.clear_items()
        self._add_idle_buttons()
        await safe_response_edit_message(interaction, embed=self._build_idle_embed(), view=self)

    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        """Picker phase confirm -- validate total picks then resolve the game."""
        if not await self._check_access(interaction):
            return

        picks = self._all_picks
        total = len(picks)

        if total < MIN_PICKS or total > MAX_PICKS:
            await interaction.response.send_message(
                f"You must select between **{MIN_PICKS}** and **{MAX_PICKS}** numbers "
                f"before confirming (you currently have **{total}** selected).",
                ephemeral=True,
            )
            return

        await safe_defer(interaction)
        await self._resolve(interaction, self._last_bet, picks)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🎰 How to Play: Keno", color=PALETTE_GOLD)
        e.description = (
            "Pick **1 to 10** numbers from a pool of 1 to 80. "
            "The house draws 20 numbers at random. "
            "Every pick that matches a drawn number is a **hit**. "
            "More hits on more spots means bigger payouts."
        )

        # Build a compact paytable display
        table_lines = [
            "```",
            f"{'Picks':<6} {'Hits':<8} {'Payout'}",
            "-" * 28,
        ]
        for spots in range(1, 11):
            tier = KENO_PAYTABLE.get(spots, {})
            for hits, mult in sorted(tier.items()):
                label = f"{hits} hit{'s' if hits != 1 else ''}"
                table_lines.append(f"  {spots:<4}  {label:<8}  {mult}x")
        table_lines.append("```")

        e.add_field(
            name=f"Payout Table (pool: 1-{POOL_SIZE}, draw: 20)",
            value="\n".join(table_lines),
            inline=False,
        )

        e.add_field(
            name="Bonuses",
            value=(
                "• **Bonus Bet Token** -- doubles payout on any win. "
                "Consumed before draw; no effect on a loss.\n"
                "• **Multiplier Wheel** -- applies to profit on any win\n"
                "• **Lucky Streak** -- adds 25% to raw payout on any win; "
                "cancelled on any loss"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        # Lazy import avoids a circular dependency at module load time.
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

    async def _start_pick_phase(self, interaction: discord.Interaction, bet: int) -> None:
        """Validate the bet then transition to the number-picker phase.

        interaction is the deferred modal submission interaction.  We call
        interaction.edit_original_response() to update the original message
        (the one that triggered the modal).
        """
        balance = await get_balance(self._member, self._conf, self._user)
        error = validate_bet(self._conf, self._user, "keno", bet, balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        self._last_bet = bet
        self._range_picks = {1: [], 21: [], 41: [], 61: []}
        self.clear_items()
        self._add_pick_buttons()
        await safe_edit_original_response(interaction, embed=self._build_pick_embed(0), view=self)

    # ------------------------------------------------------------------
    # Embed builders (sync -- use cached balance)
    # ------------------------------------------------------------------

    def _build_idle_embed(self) -> discord.Embed:
        user = self._user
        e = discord.Embed(title="🎰 High Roller: Keno", color=PALETTE_GOLD)

        desc = (
            "**Pick numbers. Match the draw. Win chips.**\n\n"
            "Choose **1 to 10** numbers from a pool of 1 to 80. "
            "The house draws 20 numbers -- every match is a hit. "
            "More hits means bigger multipliers.\n\n"
            "Press **Play Keno** to set your bet and select your numbers."
        )

        mul = get_pending_multiplier(user)
        if mul is not None:
            desc += f"\n\n⚡ Bonus snapshot: **{mul}x** multiplier if it is still active on your next win."
        if has_bonus_bet_token(user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token doubles payout if it is still unused when a win resolves."
        if has_lucky_streak(user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak adds +25% if it is still active on your next win."

        e.description = desc

        if url := embed_image("keno"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the _launch_game protocol."""
        return self._build_idle_embed()

    def _build_pick_embed(self, total_picked: int) -> discord.Embed:
        e = discord.Embed(title="🎰 High Roller: Keno", color=PALETTE_GOLD)

        current_picks = self._all_picks
        bet = self._last_bet or 0
        cur = self._cached_currency or "chips"

        if current_picks:
            picks_str = "  ".join(str(n) for n in current_picks)
        else:
            picks_str = "*(none yet)*"

        desc = (
            f"Select your numbers using the menus below.\n"
            f"You must pick between **{MIN_PICKS}** and **{MAX_PICKS}** numbers "
            f"total across all four ranges.\n\n"
            f"**Bet:** {bet:,} {cur}\n"
            f"**Selected ({total_picked}/{MAX_PICKS}):** {picks_str}\n\n"
            f"When you're done, press **Confirm Picks** to play."
        )

        e.description = desc

        if url := embed_image("keno"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_result_embed(self, result: dict) -> discord.Embed:
        e = discord.Embed(title="🎰 High Roller: Keno", color=PALETTE_GOLD)

        bet      = result["bet"]
        picks    = result["picks"]       # sorted list[int]
        drawn    = result["drawn"]       # sorted list[int]
        hits     = result["hits"]
        spots    = result["spots"]
        payout   = result["payout"]
        is_win   = result["is_win"]
        cur      = self._cached_currency

        drawn_set = set(drawn)

        # Picks line: bold and mark hits with a checkmark, plain for misses.
        picks_display = "  ".join(
            f"**{n}✓**" if n in drawn_set else str(n)
            for n in picks
        )

        # Drawn numbers: two rows of 10.
        drawn_row1 = "  ".join(str(n) for n in drawn[:10])
        drawn_row2 = "  ".join(str(n) for n in drawn[10:])
        drawn_display = f"{drawn_row1}\n{drawn_row2}"

        hit_word = "hit" if hits == 1 else "hits"
        if is_win:
            hit_line = f"✅ **{hits} {hit_word} out of {spots} picks!**"
            payout_line = (
                f"Bet: **{bet:,}** {cur} "
                f"→ Payout: **{payout:,}** {cur} "
                f"*(+{payout - bet:,} profit)*"
            )
            flavor = random.choice(_WIN_FLAVOR)
        else:
            hit_line = f"❌ **{hits} {hit_word} out of {spots} picks.**"
            payout_line = f"Bet of **{bet:,}** {cur} lost."
            flavor = random.choice(_LOSS_FLAVOR)

        desc = (
            f"{hit_line}\n\n"
            f"**Your picks:** {picks_display}\n\n"
            f"**Drawn numbers (20):**\n{drawn_display}\n\n"
            f"{payout_line}\n"
            f"*{flavor}*"
        )

        if result.get("streak_cancelled"):
            desc += "\n💔 **Your lucky streak has ended.**"

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

        if url := embed_image("keno"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    # ------------------------------------------------------------------
    # Game resolution
    # ------------------------------------------------------------------

    async def _resolve(
        self,
        interaction: discord.Interaction,
        bet: int,
        picks: list[int],
    ) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user

        # 1. Consume Bonus Bet Token before draw (keno is eligible).
        #    consume_bonus_bet_token internally checks BONUS_BET_TOKEN_ELIGIBLE_GAMES
        #    and returns False without consuming if the game is ineligible -- safe
        #    to call unconditionally.
        token_active = False
        if has_bonus_bet_token(user):
            token_active = consume_bonus_bet_token(user, "keno")

        # 2. Deduct balance before resolution.
        await deduct_balance(member, conf, user, bet)

        # 3. Draw numbers -- use admin-configured draw count.
        draw_count: int = get_game_rng(conf, "keno", "draw_count")
        drawn = draw_numbers(draw_count)

        # 4. Count hits and compute raw payout.
        player_set = frozenset(picks)
        hits = count_hits(player_set, drawn)
        spots = len(picks)
        raw_payout = calculate_payout(bet, spots, hits)

        streak_cancelled = False

        if raw_payout > 0:
            # ----------------------------------------------------------------
            # Win path
            # ----------------------------------------------------------------
            total_payout = raw_payout

            # Lucky Streak adds 25% of raw payout.
            if has_lucky_streak(user):
                total_payout += apply_lucky_streak_bonus(raw_payout)

            # Multiplier Wheel -- "keno" IS in MULTIPLIER_ELIGIBLE_GAMES.
            if "keno" in MULTIPLIER_ELIGIBLE_GAMES:
                multiplier = consume_multiplier(user)
                if multiplier is not None:
                    profit = total_payout - bet
                    total_payout += int(profit * (multiplier - 1.0))

            # Bonus Bet Token doubles payout on a win.
            if token_active:
                total_payout *= 2

            await credit_balance(member, conf, user, total_payout)
            record_win(conf, user, "keno", total_payout, bet)

        else:
            # ----------------------------------------------------------------
            # Loss path
            # ----------------------------------------------------------------
            total_payout = 0

            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True

            record_loss(conf, user, "keno", bet)

        # 5. Rank evaluation.
        new_rank     = evaluate_rank(conf, user)
        old_rank     = user.rank
        rank_changed = new_rank != old_rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        # 6. Specialty titles.
        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        # 7. Save.
        self._cog.save()

        # 8. Refresh cached balance for embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # 9. Build result and update message.
        result = {
            "bet":            bet,
            "picks":          sorted(picks),
            "drawn":          sorted(drawn),
            "hits":           hits,
            "spots":          spots,
            "payout":         total_payout,
            "is_win":         raw_payout > 0,
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank,
            "new_titles":     new_titles,
            "token_active":   token_active,
        }

        self.clear_items()
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(result), view=self)
