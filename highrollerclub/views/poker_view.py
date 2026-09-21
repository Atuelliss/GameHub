"""VideoPokerView -- Discord UI for the Video Poker game in HighRollerClub.

Game flow
---------
Phase 1 (idle)    : Player sees the game prompt with paytable preview.
                    Buttons: Play Video Poker | Back to Floor | How to Play

Phase 2 (deal)    : Player has entered a bet via BetModal.
                    A fresh 52-card deck is shuffled; 5 cards are dealt.
                    Row 0: 5 hold-toggle buttons (one per card).
                            Grey = not held. Green = held.
                            Label format: "[HOLD] A♠" or "A♠"
                    Row 1: Draw | Back to Floor
                    Clicking Draw replaces all non-held cards from the
                    remaining deck, evaluates the hand, and resolves.

Phase 3 (result)  : Final 5-card hand shown with hand name + payout.
                    Buttons: Play Again (same bet) | Change Bet
                             | Back to Floor | How to Play

Access guard
------------
_check_access() is called at the top of every action button callback.
Checks:
  1. is_allowed_channel(conf, interaction.channel_id)
  2. conf.games_enabled.get("videopoker", True)
Callers return immediately when this returns False.

Bonus stacking order (win only)
---------------------------------
  1. raw_payout = calculate_vp_payout(bet, hand_rank) [gross, includes stake]
  2. If Lucky Streak active: bonus = apply_lucky_streak_bonus(raw_payout)
     total_payout = raw_payout + bonus
  3. Multiplier Wheel guard -- "videopoker" NOT in MULTIPLIER_ELIGIBLE_GAMES:
     guard evaluates False; consume_multiplier() is never called.
  4. Bonus Bet Token -- "videopoker" NOT in BONUS_BET_TOKEN_ELIGIBLE_GAMES:
     consume_bonus_bet_token() returns False without consuming; token safe.

On any loss (payout == 0): cancel_lucky_streak(user) if active.
"nothing" hand is a loss. "jacks_or_better" and above are wins.

get_game_rng() must NOT be called for "videopoker" -- it is a CARD_MATH_GAMES
game. Win probability is determined by deck math.

Pure game logic lives in games/poker.py.
"""

from __future__ import annotations

import random

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.interactions import safe_defer, safe_edit_original_response, safe_response_edit_message
from ..common.constants import (
    MULTIPLIER_ELIGIBLE_GAMES,
    PALETTE_GOLD,
    RANK_NAMES,
    SPECIALTY_TITLES,
    embed_image,
)
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
from ..games.poker import (
    VP_HAND_NAMES,
    VP_PAYTABLE,
    Card,
    Deck,
    calculate_vp_payout,
    evaluate_hand,
)

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_FLAVOR: dict[str, str] = {
    "royal_flush":    "The rarest hand in the deck. The Club tips its hat.",
    "straight_flush": "Five in a row, same color. Exceptional.",
    "four_of_a_kind": "Four of a kind -- the crowd takes notice.",
    "full_house":     "A full house. Solid poker.",
    "flush":          "All the same suit. Clean and profitable.",
    "straight":       "Five straight. A disciplined hand.",
    "three_of_a_kind": "Three of a kind. You found the edge.",
    "two_pair":       "Two pair. Not glamorous -- but profitable.",
    "jacks_or_better": "Jacks or better. Even money, and you came through.",
}

_LOSS_FLAVOR: list[str] = [
    "The draw didn't cooperate. Try again.",
    "No qualifying hand this time.",
    "The deck had other ideas.",
    "Variance. It happens to everyone.",
    "The Club endures. So do you.",
    "A miss on the draw. Better luck next round.",
    "The cards weren't on your side.",
]


# ---------------------------------------------------------------------------
# Paytable display (for How to Play and idle embed)
# ---------------------------------------------------------------------------

_PAYTABLE_DISPLAY: list[tuple[str, str, int]] = [
    ("royal_flush",     "Royal Flush",      800),
    ("straight_flush",  "Straight Flush",    50),
    ("four_of_a_kind",  "Four of a Kind",    25),
    ("full_house",      "Full House",         9),
    ("flush",           "Flush",              6),
    ("straight",        "Straight",           4),
    ("three_of_a_kind", "Three of a Kind",    3),
    ("two_pair",        "Two Pair",           2),
    ("jacks_or_better", "Jacks or Better",    1),
]


# ---------------------------------------------------------------------------
# Bet Modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Video Poker: Place Your Bet"):
    def __init__(self, view: VideoPokerView, min_bet: int, max_bet: int) -> None:
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
        await self._view._start_deal_phase(interaction, int(raw))


# ---------------------------------------------------------------------------
# Main Video Poker View
# ---------------------------------------------------------------------------

class VideoPokerView(discord.ui.View):
    """Discord UI view for the Video Poker game (Jacks or Better).

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

        # Hand state (populated at deal time).
        self._hand: list[Card] = []
        self._deck: Deck | None = None
        self._held: list[bool] = [False, False, False, False, False]

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
            label="🃏 Play Video Poker", style=discord.ButtonStyle.green, row=0
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

    def _add_deal_components(self) -> None:
        """Row 0: 5 hold-toggle card buttons. Row 1: Draw + Back."""
        for i, card in enumerate(self._hand):
            held = self._held[i]
            label = f"[HOLD] {card.label}" if held else card.label
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.green if held else discord.ButtonStyle.grey,
                row=0,
            )
            btn.callback = self._make_hold_callback(i)
            self.add_item(btn)

        draw_btn = discord.ui.Button(
            label="🃏 Draw", style=discord.ButtonStyle.blurple, row=1
        )
        draw_btn.callback = self._on_draw
        self.add_item(draw_btn)

        back_btn = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=1
        )
        back_btn.callback = self._back_to_floor
        self.add_item(back_btn)

    def _add_result_buttons(self) -> None:
        if self._last_bet is not None:
            again = discord.ui.Button(
                label=f"🃏 Play Again ({self._last_bet:,})",
                style=discord.ButtonStyle.green,
                row=0,
            )
            again.callback = self._on_play_again
            self.add_item(again)

        change = discord.ui.Button(
            label="💰 Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._on_change_bet
        self.add_item(change)

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
    # Hold toggle factory
    # ------------------------------------------------------------------

    def _make_hold_callback(self, idx: int):
        async def _callback(interaction: discord.Interaction) -> None:
            if not await self._check_access(interaction):
                return
            self._held[idx] = not self._held[idx]
            self.clear_items()
            self._add_deal_components()
            await safe_response_edit_message(interaction, embed=self._build_deal_embed(), view=self)
        return _callback

    # ------------------------------------------------------------------
    # Access guard
    # ------------------------------------------------------------------

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if not is_allowed_channel(self._conf, interaction.channel_id):
            await interaction.response.send_message(
                "Video Poker can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not self._conf.games_enabled.get("videopoker", True):
            await interaction.response.send_message(
                "Video Poker is currently disabled on this server.",
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
        min_bet, max_bet = get_bet_limits(self._conf, "videopoker", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _on_change_bet(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "videopoker", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _on_play_again(self, interaction: discord.Interaction) -> None:
        """Reuse last bet and deal a fresh hand."""
        if not await self._check_access(interaction):
            return
        if self._last_bet is None:
            await interaction.response.send_message(
                "No previous bet to repeat.", ephemeral=True
            )
            return
        await safe_defer(interaction)
        await self._start_deal_phase(interaction, self._last_bet, deferred=True)

    async def _on_draw(self, interaction: discord.Interaction) -> None:
        """Replace non-held cards then resolve the hand."""
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._resolve(interaction)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🃏 How to Play: Video Poker", color=PALETTE_GOLD)
        e.description = (
            "**Jacks or Better** -- standard 9/6 paytable.\n\n"
            "1. Place your bet and receive 5 cards from a shuffled 52-card deck.\n"
            "2. Click each card you want to **HOLD** (green = held).\n"
            "3. Click **Draw** -- all non-held cards are replaced.\n"
            "4. Your final hand is evaluated for the payout below.\n\n"
            "A **pair of Jacks, Queens, Kings, or Aces** is the minimum qualifying hand."
        )

        paytable_lines = []
        for _, name, net in _PAYTABLE_DISPLAY:
            paytable_lines.append(f"`{net:>3}:1`  {name}")
        e.add_field(
            name="Paytable (net payout)",
            value="\n".join(paytable_lines),
            inline=False,
        )

        e.add_field(
            name="Bonuses",
            value=(
                "• **Lucky Streak** -- adds 25% to raw payout on any win; "
                "cancelled on any loss\n"
                "• Multiplier Wheel and Bonus Bet Token do not apply to Video Poker"
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
    # Deal phase entry point
    # ------------------------------------------------------------------

    async def _start_deal_phase(
        self,
        interaction: discord.Interaction,
        bet: int,
        deferred: bool = False,
    ) -> None:
        """Validate bet, shuffle deck, deal 5 cards, show hold buttons."""
        balance = await get_balance(self._member, self._conf, self._user)
        error = validate_bet(self._conf, self._user, "videopoker", bet, balance)
        if error:
            if deferred:
                await interaction.followup.send(error, ephemeral=True)
            else:
                await interaction.followup.send(error, ephemeral=True)
            return

        self._last_bet = bet
        self._deck = Deck()
        self._hand = self._deck.deal(5)
        self._held = [False, False, False, False, False]

        self.clear_items()
        self._add_deal_components()
        await safe_edit_original_response(interaction, embed=self._build_deal_embed(), view=self)

    # ------------------------------------------------------------------
    # Embed builders
    # ------------------------------------------------------------------

    def _build_idle_embed(self) -> discord.Embed:
        user = self._user
        e = discord.Embed(title="🃏 High Roller: Video Poker", color=PALETTE_GOLD)

        desc = (
            "**Jacks or Better -- 9/6 paytable.**\n\n"
            "Deal 5 cards, hold the ones you want, draw replacements. "
            "A pair of Jacks or better qualifies for a payout. "
            "Royal Flush pays **800:1**.\n\n"
        )

        paytable_lines = [
            f"`{net:>3}:1`  {name}"
            for _, name, net in _PAYTABLE_DISPLAY
        ]
        desc += "**Paytable (net):**\n" + "\n".join(paytable_lines)

        mul = get_pending_multiplier(user)
        if mul is not None:
            desc += f"\n\n⚡ Bonus snapshot: **{mul}x** multiplier is stored on your account, but Video Poker does not use it."
        if has_bonus_bet_token(user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token is stored on your account, but Video Poker does not use it."
        if has_lucky_streak(user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak adds +25% if it is still active on your next win."

        e.description = desc

        if url := embed_image("videopoker"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )
        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the _launch_game protocol."""
        return self._build_idle_embed()

    def _build_deal_embed(self) -> discord.Embed:
        bet = self._last_bet or 0
        cur = self._cached_currency or "chips"

        e = discord.Embed(title="🃏 High Roller: Video Poker", color=PALETTE_GOLD)

        card_display = "  ".join(
            f"**[{c.label}]**" if self._held[i] else c.label
            for i, c in enumerate(self._hand)
        )
        held_count = sum(self._held)

        desc = (
            f"**Bet:** {bet:,} {cur}\n\n"
            f"**Your hand:**\n{card_display}\n\n"
            f"Click the card buttons below to toggle **HOLD** (green = held). "
            f"Currently holding **{held_count}/5** card(s).\n"
            f"Press **Draw** to replace all non-held cards."
        )

        e.description = desc

        if url := embed_image("videopoker"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )
        return e

    def _build_result_embed(self, result: dict) -> discord.Embed:
        e = discord.Embed(title="🃏 High Roller: Video Poker", color=PALETTE_GOLD)

        hand          = result["hand"]
        hand_rank     = result["hand_rank"]
        hand_name     = VP_HAND_NAMES.get(hand_rank, hand_rank)
        is_win        = result["is_win"]
        bet           = result["bet"]
        payout        = result["payout"]
        cur           = self._cached_currency

        card_display = "  ".join(c.label for c in hand)

        if is_win:
            net = payout - bet
            flavor = _WIN_FLAVOR.get(hand_rank, "A winning hand.")
            desc = (
                f"**Final hand:**\n{card_display}\n\n"
                f"✅ **{hand_name}**\n"
                f"Bet: **{bet:,}** {cur} "
                f"→ Payout: **{payout:,}** {cur} "
                f"*(+{net:,} profit)*\n"
                f"*{flavor}*"
            )
        else:
            flavor = random.choice(_LOSS_FLAVOR)
            desc = (
                f"**Final hand:**\n{card_display}\n\n"
                f"❌ **{hand_name}**\n"
                f"Bet of **{bet:,}** {cur} lost.\n"
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

        if url := embed_image("videopoker"):
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
        member = self._member
        conf   = self._conf
        user   = self._user
        bet    = self._last_bet

        # 1. Replace non-held cards from the remaining deck.
        assert self._deck is not None, "Deck not initialized before draw"
        for i in range(5):
            if not self._held[i]:
                self._hand[i] = self._deck.draw()

        # 2. Evaluate final hand.
        hand_rank  = evaluate_hand(self._hand)
        raw_payout = calculate_vp_payout(bet, hand_rank)
        is_win     = raw_payout > 0

        # 3. Bonus Bet Token -- "videopoker" NOT in BONUS_BET_TOKEN_ELIGIBLE_GAMES.
        #    consume_bonus_bet_token() checks eligibility internally and returns
        #    False without consuming the token on ineligible games.
        token_active = False
        if has_bonus_bet_token(user):
            token_active = consume_bonus_bet_token(user, "videopoker")  # always False

        # 4. Deduct balance before crediting.
        await deduct_balance(member, conf, user, bet)

        streak_cancelled = False

        if is_win:
            # ----------------------------------------------------------------
            # Win path
            # ----------------------------------------------------------------
            total_payout = raw_payout

            # Lucky Streak adds 25% of raw payout.
            if has_lucky_streak(user):
                total_payout += apply_lucky_streak_bonus(raw_payout)

            # Multiplier Wheel -- "videopoker" NOT in MULTIPLIER_ELIGIBLE_GAMES.
            # Explicit guard so it auto-activates if the constant ever changes.
            if "videopoker" in MULTIPLIER_ELIGIBLE_GAMES:
                multiplier = consume_multiplier(user)
                if multiplier is not None:
                    profit = total_payout - bet
                    total_payout += int(profit * (multiplier - 1.0))

            # Bonus Bet Token -- token_active is always False for videopoker.
            if token_active:
                total_payout *= 2

            await credit_balance(member, conf, user, total_payout)
            record_win(conf, user, "videopoker", total_payout, bet)

        else:
            # ----------------------------------------------------------------
            # Loss path
            # ----------------------------------------------------------------
            total_payout = 0

            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True

            record_loss(conf, user, "videopoker", bet)

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
            "bet":            bet,
            "hand":           list(self._hand),
            "hand_rank":      hand_rank,
            "is_win":         is_win,
            "payout":         total_payout,
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank,
            "new_titles":     new_titles,
        }

        self.clear_items()
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(result), view=self)
