"""BlackjackView — Discord UI for the Blackjack game in HighRollerClub.

Game flow
---------
Phase 1 (idle)   : Bet modal triggered by "Deal" button.
Phase 2 (active) : Player's turn — Hit / Stand / Double Down buttons.
                   Split button also appears when the opening hand is a pair.
                   Dealer's hole card is shown as [?] during player's turn.
Phase 3 (result) : Dealer plays out, cards revealed, outcome shown.
                   Buttons: Change Bet | Deal (last bet) | Back to Floor

Split handling
--------------
On Split, the initial two cards become Hand 1 and Hand 2, each dealt one
additional card.  The player plays Hand 1 first (Hit / Stand only — no Double
or re-Split).  When Hand 1 is done, Hand 2 is presented the same way.
Finally, the dealer plays and each hand is resolved independently.

Bonus stacking order (on any winning hand)
------------------------------------------
  1. raw_payout  = game-logic payout function (blackjack_payout / win_payout /
                   double_down_payout), applied per hand.
  2. lucky_streak_bonus = apply_lucky_streak_bonus(raw_payout) if active.
  3. total_payout += lucky_streak_bonus
  4. If Multiplier Wheel active: profit = total_payout - bet_for_that_hand;
     total_payout += int(profit × (multiplier − 1.0)).
     Multiplier is consumed once, on the first winning hand of the session.
  5. If Bonus Bet Token active: total_payout × 2.
     Token is consumed before the deal; applies once across all hands.

Push returns the bet for that hand — no bonuses on a push.
Lucky Streak is cancelled on the first loss encountered during resolution.
All four bonus mechanisms apply identically on Split hands.

Pure game logic lives in games/blackjack.py.
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
from ..games.blackjack import (
    Card,
    Deck,
    blackjack_payout,
    can_split,
    compare_hands,
    dealer_play,
    double_down_payout,
    draw_card,
    draw_hand,
    hand_label,
    hand_value,
    is_blackjack,
    is_bust,
    win_payout,
)

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_BJ_FLAVOR: list[str] = [
    "Ace and a ten — poetry in cards.",
    "Natural blackjack. The Club bows.",
    "Twenty-one on the deal. A perfect hand.",
    "A royal entrance — blackjack!",
    "The cards sang your name tonight.",
]

_WIN_FLAVOR: list[str] = [
    "A sharper hand, a heavier wallet.",
    "The dealer folded under the pressure.",
    "Closer to 21 — and it showed.",
    "Clean play, clean win.",
    "The house remembers. You've earned this.",
    "The cards had a plan. You executed it.",
    "Discipline rewarded.",
]

_LOSS_FLAVOR: list[str] = [
    "The dealer's hand was better this time.",
    "The cards have no favorites.",
    "Not every hand is a winning one.",
    "So close — and yet.",
    "The house edges ahead. Try again.",
    "A learning moment — and the Club is always open.",
    "The deck didn't cooperate.",
]

_BUST_FLAVOR: list[str] = [
    "Over 21 — the cards went too far.",
    "Greed and gravity — both pull down.",
    "One card too many.",
    "Bust. The house collects.",
    "The risk was high, and the deck agreed.",
]

_PUSH_FLAVOR: list[str] = [
    "A perfect tie — your bet returns.",
    "Equal hands. The Club calls it even.",
    "Neither side blinked. Push.",
    "Matched — and nothing lost.",
]

_DOUBLE_WIN_FLAVOR: list[str] = [
    "Doubled down and delivered.",
    "One card, double the reward.",
    "The boldest move — and it paid off.",
    "Maximum risk, maximum return.",
]

_DOUBLE_LOSS_FLAVOR: list[str] = [
    "Doubled down — and lost double.",
    "One card. Not enough.",
    "Brave, but the deck had other ideas.",
    "The risk was real, and so was the loss.",
]


# ---------------------------------------------------------------------------
# Bet modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Place Your Bet — Blackjack"):
    def __init__(self, view: BlackjackView, min_bet: int, max_bet: int) -> None:
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
        await self._view._start_game(interaction, int(raw))


# ---------------------------------------------------------------------------
# Main Blackjack View
# ---------------------------------------------------------------------------

class BlackjackView(discord.ui.View):
    """Discord UI view for the Blackjack game.

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
        super().__init__(timeout=180)
        self._member: discord.Member = interaction.user  # type: ignore[assignment]
        self._conf = conf
        self._user = user
        self._cog = cog

        # Balance cache — refreshed after every resolve.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Game state — populated by _start_game.
        self._bet: int = 0
        self._deck: Deck | None = None
        self._player_hand: list[Card] = []
        self._dealer_hand: list[Card] = []

        # Split state
        self._split_active: bool = False
        self._split_hand1: list[Card] = []
        self._split_hand2: list[Card] = []
        self._playing_split_hand: int = 1  # 1 or 2

        # Bonus state — captured once before the deal.
        self._token_active: bool = False
        self._multiplier_consumed: bool = False

        # Last validated bet for "Deal Same Bet" shortcut.
        self._last_bet: int | None = None

        # Phase tracking: "idle" | "active" | "split_h1" | "split_h2" | "result"
        self._phase: str = "idle"

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

    async def _edit_game_message(
        self,
        interaction: discord.Interaction,
        *,
        embed: discord.Embed,
        view: discord.ui.View,
    ) -> bool:
        try:
            await interaction.edit_original_response(embed=embed, view=view)
            return True
        except discord.NotFound:
            if interaction.message is None:
                return False
            try:
                await interaction.message.edit(embed=embed, view=view)
                return True
            except discord.NotFound:
                return False

    # ------------------------------------------------------------------
    # Access guard
    # ------------------------------------------------------------------

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        conf = self._conf
        if not is_allowed_channel(conf, interaction.channel_id):
            await interaction.response.send_message(
                "Blackjack can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False
        if not conf.games_enabled.get("blackjack", True):
            await interaction.response.send_message(
                "Blackjack is currently disabled on this server.",
                ephemeral=True,
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Button layouts
    # ------------------------------------------------------------------

    def _add_idle_buttons(self) -> None:
        self.clear_items()
        deal = discord.ui.Button(
            label="🃏 Deal", style=discord.ButtonStyle.green, row=0
        )
        deal.callback = self._on_deal
        self.add_item(deal)

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

    def _add_player_action_buttons(self, allow_double: bool, allow_split: bool) -> None:
        self.clear_items()
        hit = discord.ui.Button(
            label="👊 Hit", style=discord.ButtonStyle.green, row=0
        )
        hit.callback = self._on_hit
        self.add_item(hit)

        stand = discord.ui.Button(
            label="✋ Stand", style=discord.ButtonStyle.blurple, row=0
        )
        stand.callback = self._on_stand
        self.add_item(stand)

        if allow_double:
            dbl = discord.ui.Button(
                label=f"✌️ Double Down ({self._bet * 2:,})",
                style=discord.ButtonStyle.red,
                row=0,
            )
            dbl.callback = self._on_double
            self.add_item(dbl)

        if allow_split:
            sp = discord.ui.Button(
                label="↕️ Split", style=discord.ButtonStyle.red, row=0
            )
            sp.callback = self._on_split
            self.add_item(sp)

        info = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    def _add_split_hand_buttons(self) -> None:
        """Hit / Stand only during split hand play — no Double or re-Split."""
        self.clear_items()
        hit = discord.ui.Button(
            label="👊 Hit", style=discord.ButtonStyle.green, row=0
        )
        hit.callback = self._on_hit
        self.add_item(hit)

        stand = discord.ui.Button(
            label="✋ Stand", style=discord.ButtonStyle.blurple, row=0
        )
        stand.callback = self._on_stand
        self.add_item(stand)

        info = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    def _add_result_buttons(self) -> None:
        self.clear_items()
        change = discord.ui.Button(
            label="🃏 Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._on_play_again
        self.add_item(change)

        if self._last_bet is not None:
            same = discord.ui.Button(
                label=f"🃏 Deal ({self._last_bet:,})",
                style=discord.ButtonStyle.green,
                row=0,
            )
            same.callback = self._deal_same_bet
            self.add_item(same)

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
    # Idle / navigation callbacks
    # ------------------------------------------------------------------

    async def _on_deal(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "blackjack", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _deal_same_bet(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._start_game(interaction, self._last_bet)

    async def _on_play_again(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        self._phase = "idle"
        self._add_idle_buttons()
        await safe_response_edit_message(interaction, embed=self._build_embed(), view=self)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        await safe_defer(interaction)
        balance = await get_balance(self._member, self._conf, self._user)
        currency_name = (
            "chips" if self._conf.payment_mode == "chips"
            else await bank.get_currency_name(self._member.guild)
        )
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🃏 How to Play — Blackjack", color=PALETTE_GOLD)
        e.description = (
            "Beat the dealer to **21** without going over. "
            "Face cards (J, Q, K) are worth **10**. "
            "Aces are worth **11** or **1** — whichever keeps you under 22."
        )
        e.add_field(
            name="Basic Rules",
            value=(
                "• You and the dealer each receive **2 cards**.\n"
                "• The dealer's second card is hidden until your turn ends.\n"
                "• **Dealer stands on hard 17+** — hits on soft 16 or lower.\n"
                "• Whoever is closer to 21 wins. Tie = **Push** (bet returned).\n"
                "• Going over 21 = **Bust** — instant loss."
            ),
            inline=False,
        )
        e.add_field(
            name="Actions",
            value=(
                "**Hit** — Draw another card.\n"
                "**Stand** — End your turn; dealer plays out.\n"
                "**Double Down** — Double your bet, receive exactly one more card, then stand.\n"
                "**Split** — Available when your first two cards share the same rank. "
                "Splits into two hands; each hand plays Hit/Stand only."
            ),
            inline=False,
        )
        e.add_field(
            name="Payouts",
            value=(
                "```\n"
                "Blackjack (natural)  3:2\n"
                "Win                  1:1\n"
                "Push                 Bet returned\n"
                "Loss / Bust          Bet forfeited\n"
                "Double Down Win      1:1 on doubled bet\n"
                "```"
            ),
            inline=False,
        )
        e.add_field(
            name="Bonuses",
            value=(
                "• **Bonus Bet Token** — doubles payout on any winning hand(s). "
                "No effect on push or loss.\n"
                "• **Multiplier Wheel** — applies to profit on the first winning hand.\n"
                "• **Lucky Streak** — adds 25% to each winning hand's raw payout. "
                "Cancelled on first loss."
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ------------------------------------------------------------------
    # Game start — deal initial cards
    # ------------------------------------------------------------------

    async def _start_game(self, interaction: discord.Interaction, bet: int) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user

        # 1. Validate bet.
        balance = await get_balance(member, conf, user)
        error = validate_bet(conf, user, "blackjack", bet, balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        self._last_bet = bet
        self._bet      = bet

        # 2. Consume Bonus Bet Token before any cards are drawn.
        self._token_active = False
        if has_bonus_bet_token(user):
            self._token_active = consume_bonus_bet_token(user, "blackjack")

        # 3. Deduct initial bet.
        await deduct_balance(member, conf, user, bet)

        # 4. Deal initial cards.
        self._deck = Deck()
        self._player_hand = draw_hand(self._deck)
        self._dealer_hand = draw_hand(self._deck)
        self._split_active = False
        self._multiplier_consumed = False

        # Refresh balance cache now that the bet has been deducted.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # 5. Instant blackjack check (player). Dealer BJ is resolved at stand.
        if is_blackjack(self._player_hand):
            self._phase = "active"
            await self._resolve_round(interaction, doubled=False)
            return

        # 6. Determine allowed actions.
        balance_after = self._cached_balance
        allow_double = balance_after >= bet        # must afford the additional bet
        allow_split  = can_split(self._player_hand) and balance_after >= bet

        self._phase = "active"
        self._add_player_action_buttons(allow_double=allow_double, allow_split=allow_split)
        await self._edit_game_message(interaction, embed=self._build_embed(), view=self)

    # ------------------------------------------------------------------
    # Player action callbacks
    # ------------------------------------------------------------------

    async def _on_hit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()

        assert self._deck is not None, "Deck not initialized before hit"

        if self._phase in ("active",):
            self._player_hand.append(draw_card(self._deck))

            if is_bust(self._player_hand):
                await self._resolve_round(interaction, doubled=False)
                return

            # Refresh action buttons — Double and Split no longer valid after Hit.
            self._add_player_action_buttons(allow_double=False, allow_split=False)
            await self._edit_game_message(interaction, embed=self._build_embed(), view=self)

        elif self._phase in ("split_h1", "split_h2"):
            current_hand = (
                self._split_hand1 if self._phase == "split_h1" else self._split_hand2
            )
            current_hand.append(draw_card(self._deck))

            if is_bust(current_hand):
                await self._advance_split_or_resolve(interaction)
                return

            self._add_split_hand_buttons()
            await self._edit_game_message(interaction, embed=self._build_embed(), view=self)

    async def _on_stand(self, interaction: discord.Interaction) -> None:
        try:
            await interaction.response.defer()
        except discord.NotFound:
            pass

        if self._phase == "active":
            await self._resolve_round(interaction, doubled=False)
        elif self._phase in ("split_h1", "split_h2"):
            await self._advance_split_or_resolve(interaction)

    async def _on_double(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        member = self._member
        conf   = self._conf
        user   = self._user

        assert self._deck is not None, "Deck not initialized before double down"

        # Deduct the additional bet — bet doubles in total.
        await deduct_balance(member, conf, user, self._bet)
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # Exactly one more card, then stand.
        self._player_hand.append(draw_card(self._deck))
        await self._resolve_round(interaction, doubled=True)

    async def _on_split(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        member = self._member
        conf   = self._conf
        user   = self._user

        assert self._deck is not None, "Deck not initialized before split"

        # Deduct second hand bet.
        await deduct_balance(member, conf, user, self._bet)
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # Create two hands, each starting with one card from the original pair.
        self._split_hand1 = [self._player_hand[0], draw_card(self._deck)]
        self._split_hand2 = [self._player_hand[1], draw_card(self._deck)]
        self._split_active = True
        self._playing_split_hand = 1
        self._phase = "split_h1"

        self._add_split_hand_buttons()
        await self._edit_game_message(interaction, embed=self._build_embed(), view=self)

    # ------------------------------------------------------------------
    # Split progression helper
    # ------------------------------------------------------------------

    async def _advance_split_or_resolve(self, interaction: discord.Interaction) -> None:
        """After a split hand completes, move to the next or resolve."""
        if self._phase == "split_h1":
            self._phase = "split_h2"
            self._playing_split_hand = 2
            self._add_split_hand_buttons()
            await self._edit_game_message(interaction, embed=self._build_embed(), view=self)
        else:
            # Both hands done — resolve dealer + payouts.
            await self._resolve_split(interaction)

    # ------------------------------------------------------------------
    # Resolution — standard hand
    # ------------------------------------------------------------------

    async def _resolve_round(
        self,
        interaction: discord.Interaction,
        doubled: bool,
    ) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        cog    = self._cog
        bet    = self._bet

        player_val    = hand_value(self._player_hand)
        player_busted = is_bust(self._player_hand)
        player_bj     = is_blackjack(self._player_hand)
        effective_bet = bet * 2 if doubled else bet  # total deducted from player

        # Dealer plays only if player hasn't busted and doesn't have a natural blackjack.
        # On a natural BJ, the dealer only needs their initial 2 cards to check for a push —
        # no additional cards are drawn regardless of the dealer's total.
        if not player_busted and not player_bj:
            assert self._deck is not None, "Deck not initialized before dealer play"
            dealer_play(self._dealer_hand, self._deck)

        dealer_val    = hand_value(self._dealer_hand)
        dealer_busted = is_bust(self._dealer_hand)
        dealer_bj     = is_blackjack(self._dealer_hand)

        streak_cancelled = False
        total_credit: int = 0
        outcome: str

        # --- Outcome determination ---
        if player_busted:
            outcome = "bust"
        elif player_bj and dealer_bj:
            outcome = "push"       # both naturals → push
        elif player_bj:
            outcome = "blackjack"
        elif dealer_bj:
            outcome = "loss"
        else:
            raw = compare_hands(player_val, dealer_val, dealer_busted)
            if doubled:
                outcome = f"double_{raw}"   # "double_win" | "double_loss" | "double_push"
            else:
                outcome = raw               # "win" | "loss" | "push"

        # --- Credit / record ---
        if outcome == "blackjack":
            raw_payout = blackjack_payout(bet)
            total_credit = self._apply_bonuses(raw_payout, effective_bet, user)
            await credit_balance(member, conf, user, total_credit)
            record_win(conf, user, "blackjack", total_credit, bet)

        elif outcome in ("win", "double_win"):
            raw_payout = win_payout(effective_bet) if outcome == "win" else double_down_payout(bet)
            total_credit = self._apply_bonuses(raw_payout, effective_bet, user)
            await credit_balance(member, conf, user, total_credit)
            record_win(conf, user, "blackjack", total_credit, effective_bet)

        elif outcome in ("push", "double_push"):
            # Return the bet — no bonus applied on push.
            total_credit = effective_bet
            await credit_balance(member, conf, user, total_credit)
            # Push: no record_win / record_loss (play count managed in record_win/loss only).

        else:
            # loss, bust, double_loss
            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True
            record_loss(conf, user, "blackjack", effective_bet)

        await self._finish_round(
            interaction,
            outcome=outcome,
            total_credit=total_credit,
            effective_bet=effective_bet,
            streak_cancelled=streak_cancelled,
            dealer_bj=dealer_bj,
        )

    # ------------------------------------------------------------------
    # Resolution — split hands
    # ------------------------------------------------------------------

    async def _resolve_split(self, interaction: discord.Interaction) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        cog    = self._cog
        bet    = self._bet

        # Dealer plays once for both hands.
        assert self._deck is not None, "Deck not initialized before split dealer play"
        dealer_play(self._dealer_hand, self._deck)
        dealer_val    = hand_value(self._dealer_hand)
        dealer_busted = is_bust(self._dealer_hand)
        dealer_bj     = is_blackjack(self._dealer_hand)

        streak_cancelled = False
        split_results: list[dict] = []
        total_credit: int = 0

        for hand in (self._split_hand1, self._split_hand2):
            player_val    = hand_value(hand)
            player_busted = is_bust(hand)

            if player_busted:
                outcome = "bust"
            elif dealer_bj:
                outcome = "loss"
            else:
                outcome = compare_hands(player_val, dealer_val, dealer_busted)

            hand_credit = 0

            if outcome == "win":
                raw_payout = win_payout(bet)
                hand_credit = self._apply_bonuses(raw_payout, bet, user)
                await credit_balance(member, conf, user, hand_credit)
                record_win(conf, user, "blackjack", hand_credit, bet)

            elif outcome == "push":
                hand_credit = bet
                await credit_balance(member, conf, user, hand_credit)

            else:
                # loss or bust
                if has_lucky_streak(user) and not streak_cancelled:
                    cancel_lucky_streak(user)
                    streak_cancelled = True
                record_loss(conf, user, "blackjack", bet)

            total_credit += hand_credit
            split_results.append({
                "hand":       hand,
                "outcome":    outcome,
                "hand_value": player_val,
                "credit":     hand_credit,
            })

        await self._finish_round(
            interaction,
            outcome="split",
            total_credit=total_credit,
            effective_bet=bet * 2,
            streak_cancelled=streak_cancelled,
            dealer_bj=dealer_bj,
            split_results=split_results,
        )

    # ------------------------------------------------------------------
    # Bonus stacking helper  (pure math — no async)
    # ------------------------------------------------------------------

    def _apply_bonuses(self, raw_payout: int, effective_bet: int, user: User) -> int:
        """Apply Lucky Streak, Multiplier Wheel, and Bonus Bet Token to a win.

        Called once per winning hand.  Multiplier is consumed only on the
        first call (self._multiplier_consumed guards re-consumption on Split).
        """
        total = raw_payout

        # 1. Lucky Streak.
        if has_lucky_streak(user):
            total += apply_lucky_streak_bonus(raw_payout)

        # 2. Multiplier Wheel — only on first winning hand.
        if not self._multiplier_consumed and "blackjack" in MULTIPLIER_ELIGIBLE_GAMES:
            multiplier = consume_multiplier(user)
            if multiplier is not None:
                profit = total - effective_bet
                total += int(profit * (multiplier - 1.0))
                self._multiplier_consumed = True

        # 3. Bonus Bet Token — doubles payout on a win.
        if self._token_active:
            total *= 2

        return total

    # ------------------------------------------------------------------
    # Common post-resolution wrap-up
    # ------------------------------------------------------------------

    async def _finish_round(
        self,
        interaction: discord.Interaction,
        outcome: str,
        total_credit: int,
        effective_bet: int,
        streak_cancelled: bool,
        dealer_bj: bool,
        split_results: list[dict] | None = None,
    ) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        cog    = self._cog

        # Rank evaluation.
        new_rank     = evaluate_rank(conf, user)
        old_rank     = user.rank
        rank_changed = new_rank != old_rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        # Specialty titles.
        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        # Save.
        cog.save()

        # Refresh cached balance.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        result = {
            "outcome":         outcome,
            "effective_bet":   effective_bet,
            "total_credit":    total_credit,
            "player_hand":     self._player_hand,
            "dealer_hand":     self._dealer_hand,
            "player_val":      hand_value(self._player_hand) if not self._split_active else None,
            "dealer_val":      hand_value(self._dealer_hand),
            "dealer_bj":       dealer_bj,
            "streak_cancelled": streak_cancelled,
            "rank_changed":    rank_changed,
            "old_rank":        old_rank,
            "new_rank":        new_rank,
            "new_titles":      new_titles,
            "split_results":   split_results,
        }

        self._phase = "result"
        self._add_result_buttons()
        await self._edit_game_message(interaction, embed=self._build_embed(result=result), view=self)

    # ------------------------------------------------------------------
    # Embed builder  (sync — uses cached balance)
    # ------------------------------------------------------------------

    def _build_embed(self, result: dict | None = None) -> discord.Embed:
        user = self._user
        e    = discord.Embed(title="🃏 High Roller — Blackjack", color=PALETTE_GOLD)
        cur  = self._cached_currency

        if result is None:
            # ---- Idle or active phase ----
            if self._phase == "idle":
                desc = (
                    "**Beat the dealer to 21 — without going over.**\n\n"
                    "Place your bet and click **Deal** to receive your cards.\n"
                    "Face cards = 10. Aces = 1 or 11."
                )
                mul = get_pending_multiplier(user)
                if mul is not None:
                    desc += f"\n⚡ Bonus snapshot: **{mul}×** multiplier if it is still active on your first winning hand."
                if has_bonus_bet_token(user):
                    desc += "\n🎫 Bonus snapshot: Bonus Bet Token doubles payout if it is still unused when a winning hand resolves."

            elif self._phase in ("active",):
                p_val    = hand_value(self._player_hand)
                p_label  = hand_label(self._player_hand)
                d_show   = f"{self._dealer_hand[0].label}  [?]"
                desc = (
                    f"```\n"
                    f"  Dealer: {d_show}\n"
                    f"  You   : {p_label}  (total: {p_val})\n"
                    f"```"
                    f"\nBet: **{self._bet:,}** {cur} — choose your action."
                )
                if self._token_active:
                    desc += "\n🎫 Bonus snapshot: Bonus Bet Token is still available for this hand if it has not been used elsewhere before resolution."

            elif self._phase == "split_h1":
                h1_val   = hand_value(self._split_hand1)
                h1_label = hand_label(self._split_hand1)
                h2_label = hand_label(self._split_hand2)
                d_show   = f"{self._dealer_hand[0].label}  [?]"
                desc = (
                    f"```\n"
                    f"  Dealer  : {d_show}\n"
                    f"  Hand 1▶ : {h1_label}  (total: {h1_val})  ← Playing now\n"
                    f"  Hand 2  : {h2_label}\n"
                    f"```"
                    f"\nEach hand bet: **{self._bet:,}** {cur}"
                )

            elif self._phase == "split_h2":
                h1_val   = hand_value(self._split_hand1)
                h1_label = hand_label(self._split_hand1)
                h2_val   = hand_value(self._split_hand2)
                h2_label = hand_label(self._split_hand2)
                d_show   = f"{self._dealer_hand[0].label}  [?]"
                desc = (
                    f"```\n"
                    f"  Dealer  : {d_show}\n"
                    f"  Hand 1  : {h1_label}  (total: {h1_val})\n"
                    f"  Hand 2▶ : {h2_label}  (total: {h2_val})  ← Playing now\n"
                    f"```"
                    f"\nEach hand bet: **{self._bet:,}** {cur}"
                )
            else:
                desc = "Loading…"

        else:
            # ---- Result phase ----
            outcome      = result["outcome"]
            effective_bet = result["effective_bet"]
            total_credit  = result["total_credit"]
            d_val         = result["dealer_val"]
            dealer_bj     = result["dealer_bj"]
            d_label       = hand_label(result["dealer_hand"])
            d_bust        = is_bust(result["dealer_hand"])

            dealer_line = (
                f"  Dealer: {d_label}  "
                f"({'BJ!' if dealer_bj else 'bust!' if d_bust else str(d_val)})"
            )

            if outcome == "split":
                split_results = result["split_results"]
                lines = [dealer_line]
                for i, sr in enumerate(split_results, 1):
                    h_label  = hand_label(sr["hand"])
                    h_val    = sr["hand_value"]
                    h_out    = sr["outcome"]
                    h_credit = sr["credit"]
                    icon = (
                        "✅" if h_out in ("win", "blackjack")
                        else "↩️" if h_out == "push"
                        else "❌"
                    )
                    extra = (
                        f" → +{h_credit:,} {cur}" if h_out in ("win", "blackjack")
                        else f" → returned {h_credit:,} {cur}" if h_out == "push"
                        else " → lost"
                    )
                    label = "bust!" if h_out == "bust" else str(h_val)
                    lines.append(
                        f"  {icon} Hand {i}: {h_label}  ({label}){extra}"
                    )
                card_block = "```\n" + "\n".join(lines) + "\n```"

                net = total_credit - effective_bet
                net_str = f"+{net:,}" if net >= 0 else str(net)
                desc = card_block + f"\nTotal returned: **{total_credit:,}** {cur}  (net {net_str})"
                flavor_outcomes = [sr["outcome"] for sr in split_results]
                if any(o in ("win", "blackjack") for o in flavor_outcomes):
                    desc += f"\n*{random.choice(_WIN_FLAVOR)}*"
                elif all(o in ("bust", "loss") for o in flavor_outcomes):
                    desc += f"\n*{random.choice(_LOSS_FLAVOR)}*"

            else:
                p_label = hand_label(result["player_hand"])
                p_val   = result["player_val"]
                p_bust  = is_bust(result["player_hand"])
                p_bj    = is_blackjack(result["player_hand"])
                player_line = (
                    f"  You   : {p_label}  "
                    f"({'BJ!' if p_bj else 'bust!' if p_bust else str(p_val)})"
                )
                card_block = f"```\n{player_line}\n{dealer_line}\n```"

                if outcome == "blackjack":
                    desc = (
                        card_block
                        + f"\n🃏 **BLACKJACK!** 3:2 payout."
                        + f"\nBet: **{effective_bet:,}** {cur} → Payout: **{total_credit:,}** {cur}"
                        + f"\n*{random.choice(_BJ_FLAVOR)}*"
                    )
                elif outcome == "win":
                    desc = (
                        card_block
                        + f"\n✅ **You win!**"
                        + f"\nBet: **{effective_bet:,}** {cur} → Payout: **{total_credit:,}** {cur}"
                        + f"\n*{random.choice(_WIN_FLAVOR)}*"
                    )
                elif outcome == "double_win":
                    desc = (
                        card_block
                        + f"\n✅ **Double Down — Win!**"
                        + f"\nTotal wagered: **{effective_bet:,}** {cur} → Payout: **{total_credit:,}** {cur}"
                        + f"\n*{random.choice(_DOUBLE_WIN_FLAVOR)}*"
                    )
                elif outcome in ("push", "double_push"):
                    desc = (
                        card_block
                        + f"\n↩️ **Push — it's a tie.**"
                        + f"\nBet of **{effective_bet:,}** {cur} returned."
                        + f"\n*{random.choice(_PUSH_FLAVOR)}*"
                    )
                elif outcome == "bust":
                    desc = (
                        card_block
                        + f"\n❌ **Bust!** Over 21."
                        + f"\nBet of **{effective_bet:,}** {cur} lost."
                        + f"\n*{random.choice(_BUST_FLAVOR)}*"
                    )
                elif outcome == "double_loss":
                    desc = (
                        card_block
                        + f"\n❌ **Double Down — Loss.**"
                        + f"\nTotal wagered: **{effective_bet:,}** {cur} lost."
                        + f"\n*{random.choice(_DOUBLE_LOSS_FLAVOR)}*"
                    )
                else:
                    # "loss", "double_loss" fall-through
                    desc = (
                        card_block
                        + f"\n❌ **Dealer wins.**"
                        + f"\nBet of **{effective_bet:,}** {cur} lost."
                        + f"\n*{random.choice(_LOSS_FLAVOR)}*"
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

        if url := embed_image("blackjack"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e
