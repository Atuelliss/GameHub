"""HiLoView -- Discord UI for the Hi-Lo press-your-luck card game in HighRollerClub.

Game flow
---------
Phase 1 (idle)    : Player sees the bet prompt with active bonus indicators.
                    Buttons: Deal Card | Back to Floor | How to Play

Phase 2 (guessing): A card is shown face-up. Player chooses Higher or Lower.
                    On a correct guess the multiplier grows by the odds of the
                    guess (see games/hi_lo.py), so long shots pay more. The player may Cash Out at any chain
                    depth >= 1 to claim their winnings, or keep guessing.
                    On a wrong guess the bet is lost. Same-rank cards are never drawn next.
                    Buttons: Higher | Lower | Cash Out (if depth >= 1)

Phase 3 (result)  : Game outcome displayed with payout or loss message.
                    Buttons: Change Bet | Deal (last bet) | Back to Floor

Access guard
------------
_check_access() is called at the top of every action button callback before
any game logic runs. It checks:
  1. channel_allowed(...): the channel lock (staff bypass it)
  2. conf.games_enabled.get("hilo", True)
Callers return immediately if _check_access returns False.

Bonus stacking order (cash-out win only)
-----------------------------------------
  1. raw_payout = calculate_payout(bet, multiplier)
  2. If Lucky Streak active: bonus = apply_lucky_streak_bonus(raw_payout, bet)
     total_payout = raw_payout + bonus
  3. If Multiplier Wheel active (hilo in MULTIPLIER_ELIGIBLE_GAMES):
     profit = total_payout - bet
     total_payout += multiplier_wheel_bonus(conf, profit, multiplier)
  4. If Bonus Bet Token consumed this hand: total_payout += bonus_token_bonus(raw_payout, bet)

On any loss: cancel_lucky_streak(user) if streak is active; notify player.
The Bonus Bet Token is consumed before the first card is dealt -- consistent
with War and Slots (consumed regardless of outcome; only pays on win).

Pure game logic lives in games/hi_lo.py.
"""

from __future__ import annotations

import random

import aiohttp
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
from ..common.interactions import expire_view, finish_hand_on_timeout, one_at_a_time, safe_defer, safe_edit_original_response, safe_response_edit_message, not_your_session, session_expired
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    BET_FAILED_MESSAGE,
    send_private,
    apply_lucky_streak_bonus,
    bonus_token_bonus,
    apply_rank_change,
    cancel_lucky_streak,
    consume_bonus_bet_token,
    consume_multiplier,
    multiplier_wheel_bonus,
    credit_balance,
    deduct_balance,
    evaluate_rank,
    evaluate_specialty_titles,
    get_balance,
    get_bet_limits,
    get_pending_multiplier,
    has_bonus_bet_token,
    has_lucky_streak,
    channel_allowed,
    record_loss,
    record_win,
    validate_bet,
)
from ..games.hi_lo import (
    Card,
    MAX_TOTAL_MULTIPLIER,
    Deck,
    calculate_payout,
    guess_multiplier,
    draw_card,
    draw_non_matching_card,
    evaluate_guess,
    higher_chance,
    lower_chance,
)

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_CASHOUT_FLAVOR: list[str] = [
    "A wise exit from a winning position.",
    "You took the chips and walked away clean.",
    "Knowing when to stop is half the game.",
    "The house respects a disciplined player.",
    "Profit secured. Excellent read of the room.",
    "The smart money cashes out early.",
    "A calculated retreat with your winnings intact.",
]

_LOSS_FLAVOR: list[str] = [
    "The deck had other plans.",
    "A tough break -- the cards did not cooperate.",
    "Even the best reads miss sometimes.",
    "The prediction was off. The house remembers.",
    "Not every guess lands. The Club endures.",
    "Better luck with the next card.",
    "The deck is neutral -- it favors no one.",
]


# ---------------------------------------------------------------------------
# Bet modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Place Your Bet -- Hi-Lo"):
    def __init__(self, view: "HiLoView", min_bet: int, max_bet: int) -> None:
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
# Main Hi-Lo View
# ---------------------------------------------------------------------------

class HiLoView(discord.ui.View):
    """Discord UI view for the Hi-Lo press-your-luck card game.

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
        self._message: discord.Message | None = interaction.message

        # Balance cache -- refreshed after each resolve so _build_embed stays sync.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Last validated bet -- enables the "Deal Same Bet" shortcut button.
        self._last_bet: int | None = None

        # Active game state -- reset at the start of each hand.
        self._deck: Deck | None = None
        self._current_card: Card | None = None
        self._chain_depth: int = 0        # correct guesses so far this hand
        self._multiplier: float = 1.0     # gross cash-out multiplier built up this hand
        self._token_active: bool = False  # True if a Bonus Bet Token was consumed this hand
        self._in_hand: bool = False       # True from the deduct until cash-out or a wrong guess

        self._add_idle_buttons()

    # ------------------------------------------------------------------
    # Interaction guard
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.message is not None:
            self._message = interaction.message
        if interaction.user.id != self._member.id:
            await not_your_session(interaction)
            return False
        return True

    async def on_timeout(self) -> None:
        # A hand left mid-play is settled for the player, so the bet isn't taken without a result.
        if self._in_hand:
            await finish_hand_on_timeout(self, self._settle_abandoned_hand)
        else:
            await expire_view(self)

    async def _settle_abandoned_hand(self, interaction: discord.Interaction) -> None:
        """Cash out a timed-out hand, or hand the bet back if no guess was made yet."""
        if self._chain_depth >= 1:
            await self._resolve_cashout(interaction)
            return
        # Depth 0 has no cash-out value: return the bet (and the token) as if never played.
        self._in_hand = False
        if self._token_active:
            self._user.bonus_bet_tokens += 1
            self._token_active = False
        await credit_balance(self._member, self._conf, self._user, self._last_bet, interaction=interaction)
        self._cog.save()
        self._cached_balance = await get_balance(self._member, self._conf, self._user)
        self._add_idle_buttons()
        embed = self._build_idle_embed()
        embed.add_field(
            name="⏰ Hand timed out",
            value=f"No guess was made, so your **{self._last_bet:,}** bet was returned.",
            inline=False,
        )
        await self._edit_game_message(interaction, embed=embed, view=self)

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
        except (discord.NotFound, aiohttp.ClientOSError, OSError):
            if interaction.message is None:
                return False
            try:
                await interaction.message.edit(embed=embed, view=view)
                return True
            except (discord.NotFound, aiohttp.ClientOSError, OSError):
                return False

    # ------------------------------------------------------------------
    # Button layouts
    # ------------------------------------------------------------------

    def _add_idle_buttons(self) -> None:
        self.clear_items()

        deal = discord.ui.Button(
            label="🃏 Deal Card", style=discord.ButtonStyle.green, row=0
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

    def _guess_chances(self) -> tuple[float, float]:
        """(higher, lower) chances for the current card from the cards left in the deck."""
        assert self._deck is not None and self._current_card is not None
        remaining = self._deck.remaining()
        rank = self._current_card.rank
        return higher_chance(rank, remaining), lower_chance(rank, remaining)

    def _ensure_playable_deck(self) -> bool:
        """Reshuffle now if no card of a different rank is left, so the odds shown are the odds drawn."""
        assert self._deck is not None and self._current_card is not None
        rank = self._current_card.rank
        if any(card.rank != rank for card in self._deck.remaining()):
            return False
        self._deck.reset()
        return True

    def _add_guess_buttons(self) -> None:
        self.clear_items()
        h_chance, l_chance = self._guess_chances()

        higher = discord.ui.Button(
            label=f"⬆ Higher (×{guess_multiplier(h_chance):.2f})" if h_chance else "⬆ Higher",
            style=discord.ButtonStyle.green,
            row=0,
            disabled=h_chance <= 0,
        )
        higher.callback = self._on_higher
        self.add_item(higher)

        lower = discord.ui.Button(
            label=f"⬇ Lower (×{guess_multiplier(l_chance):.2f})" if l_chance else "⬇ Lower",
            style=discord.ButtonStyle.blurple,
            row=0,
            disabled=l_chance <= 0,
        )
        lower.callback = self._on_lower
        self.add_item(lower)

        if self._chain_depth >= 1:
            cashout = discord.ui.Button(
                label=f"💰 Cash Out ({self._multiplier:.2f}×)",
                style=discord.ButtonStyle.grey,
                row=0,
            )
            cashout.callback = self._on_cashout
            self.add_item(cashout)

    def _add_result_buttons(self) -> None:
        self.clear_items()

        change = discord.ui.Button(
            label="🃏 Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._play_again
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
    # Access guard
    # ------------------------------------------------------------------

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        """Returns True if the player may act. Sends an ephemeral error and
        returns False if the channel is restricted or the game is disabled.
        Callers must return immediately when this returns False.
        """
        conf = self._conf

        if not await channel_allowed(interaction.client, conf, interaction.user, interaction.channel_id):
            await interaction.response.send_message(
                "Hi-Lo can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not conf.games_enabled.get("hilo", True):
            await interaction.response.send_message(
                "Hi-Lo is currently disabled on this server.",
                ephemeral=True,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Button callbacks -- idle phase
    # ------------------------------------------------------------------

    async def _on_deal(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "hilo", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _deal_same_bet(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._start_game(interaction, self._last_bet)

    async def _play_again(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        self._add_idle_buttons()
        await safe_response_edit_message(interaction, embed=self._build_idle_embed(), view=self)

    # ------------------------------------------------------------------
    # Button callbacks -- guessing phase
    # ------------------------------------------------------------------

    @one_at_a_time
    async def _on_higher(self, interaction: discord.Interaction) -> None:
        if not self._in_hand:  # a late click on a hand that already ended
            await safe_defer(interaction)
            return
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        self._hrc_last_interaction = interaction  # lets on_timeout finish this hand
        await self._process_guess(interaction, "higher")

    @one_at_a_time
    async def _on_lower(self, interaction: discord.Interaction) -> None:
        if not self._in_hand:  # a late click on a hand that already ended
            await safe_defer(interaction)
            return
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        self._hrc_last_interaction = interaction  # lets on_timeout finish this hand
        await self._process_guess(interaction, "lower")

    @one_at_a_time
    async def _on_cashout(self, interaction: discord.Interaction) -> None:
        if not self._in_hand:  # a late click on a hand that already ended
            await safe_defer(interaction)
            return
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._resolve_cashout(interaction)

    # ------------------------------------------------------------------
    # Game start -- validates bet, consumes token, deducts, draws first card
    # ------------------------------------------------------------------

    @one_at_a_time
    async def _start_game(self, interaction: discord.Interaction, bet: int) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user

        # Validate bet against current balance.
        balance = await get_balance(member, conf, user)
        if await session_expired(self, interaction):
            return
        error = validate_bet(conf, user, "hilo", bet, balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        self._last_bet = bet

        # Deduct the initial bet.
        if not await deduct_balance(member, conf, user, bet):
            await send_private(interaction, BET_FAILED_MESSAGE)
            return
        self._in_hand = True
        self._hrc_last_interaction = interaction  # lets on_timeout finish this hand

        # Consume Bonus Bet Token before the deal -- consistent with War/Slots.
        # After the deduct, so a failed deduct can't waste it.
        self._token_active = False
        if has_bonus_bet_token(user):
            self._token_active = consume_bonus_bet_token(user, "hilo")

        # Refresh cached balance.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # Reset chain state and draw the first card.
        self._deck = Deck()
        self._chain_depth = 0
        self._multiplier = 1.0
        self._current_card = draw_card(self._deck)
        self._ensure_playable_deck()

        self._add_guess_buttons()
        await self._edit_game_message(interaction, embed=self._build_guess_embed(), view=self)

    # ------------------------------------------------------------------
    # Guess processing
    # ------------------------------------------------------------------

    async def _process_guess(self, interaction: discord.Interaction, guess: str) -> None:
        prev_card = self._current_card
        assert self._deck is not None, "Deck not initialized before Hi-Lo guess"
        h_chance, l_chance = self._guess_chances()
        step = guess_multiplier(h_chance if guess == "higher" else l_chance)
        if step <= 0:  # impossible side (its button is disabled); ignore the click
            return
        next_card, _ = draw_non_matching_card(self._deck, prev_card.rank)
        result = evaluate_guess(prev_card, next_card, guess)

        if result == "win":
            self._chain_depth += 1
            self._multiplier = min(MAX_TOTAL_MULTIPLIER, round(self._multiplier * step, 2))
            self._current_card = next_card
            # Reshuffle up front when needed, so the next odds shown are the real odds.
            reshuffled = self._ensure_playable_deck()
            if self._multiplier >= MAX_TOTAL_MULTIPLIER:
                # Nothing left to gain: cash out at the cap.
                await self._resolve_cashout(interaction)
                return
            self._add_guess_buttons()
            await self._edit_game_message(
                interaction,
                embed=self._build_guess_embed(
                    prev_card=prev_card,
                    revealed_card=next_card,
                    guess=guess,
                    was_correct=True,
                    reshuffled=reshuffled,
                ),
                view=self,
            )
        else:
            await self._resolve_loss(interaction, prev_card, next_card, guess, False)

    # ------------------------------------------------------------------
    # Cash-out resolution
    # ------------------------------------------------------------------

    async def _resolve_cashout(self, interaction: discord.Interaction) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        bet    = self._last_bet
        depth  = self._chain_depth
        mult   = self._multiplier
        self._in_hand = False

        # 1. Base payout from the multiplier built up this hand.
        raw_payout   = calculate_payout(bet, mult)
        total_payout = raw_payout

        # 2. Lucky Streak bonus.
        streak_cancelled = False
        if has_lucky_streak(user):
            total_payout += apply_lucky_streak_bonus(raw_payout, bet)

        # 3. Multiplier Wheel (hilo is in MULTIPLIER_ELIGIBLE_GAMES).
        if "hilo" in MULTIPLIER_ELIGIBLE_GAMES:
            multiplier = consume_multiplier(user)
            if multiplier is not None:
                profit = total_payout - bet
                total_payout += multiplier_wheel_bonus(conf, profit, multiplier)

        # 4. Bonus Bet Token doubles the winnings.
        if self._token_active:
            total_payout += bonus_token_bonus(raw_payout, bet)

        # Credit winnings and record.
        await credit_balance(member, conf, user, total_payout, interaction=interaction)
        record_win(conf, user, "hilo", total_payout, bet)

        new_rank   = evaluate_rank(conf, user)
        rank_changed = new_rank != user.rank
        old_rank   = user.rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        self._cog.save()

        # Refresh cached balance.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        result_data = {
            "outcome":        "cashout",
            "bet":            bet,
            "depth":          depth,
            "multiplier":     mult,
            "payout":         total_payout,
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank if rank_changed else old_rank,
            "new_titles":     new_titles,
        }

        self._add_result_buttons()
        await self._edit_game_message(interaction, embed=self._build_result_embed(result_data), view=self)

    # ------------------------------------------------------------------
    # Loss resolution
    # ------------------------------------------------------------------

    async def _resolve_loss(
        self,
        interaction: discord.Interaction,
        prev_card: Card,
        revealed_card: Card,
        guess: str,
        reshuffled: bool,
    ) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        bet    = self._last_bet
        self._in_hand = False

        # Cancel Lucky Streak on loss and notify.
        streak_cancelled = False
        if has_lucky_streak(user):
            cancel_lucky_streak(user)
            streak_cancelled = True

        record_loss(conf, user, "hilo", bet)

        new_rank     = evaluate_rank(conf, user)
        rank_changed = new_rank != user.rank
        old_rank     = user.rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        self._cog.save()

        # Refresh cached balance.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        result_data = {
            "outcome":        "loss",
            "bet":            bet,
            "depth":          self._chain_depth,
            "prev_card":      prev_card,
            "revealed_card":  revealed_card,
            "guess":          guess,
            "reshuffled":     reshuffled,
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank if rank_changed else old_rank,
            "new_titles":     new_titles,
        }

        self._add_result_buttons()
        await self._edit_game_message(interaction, embed=self._build_result_embed(result_data), view=self)

    # ------------------------------------------------------------------
    # How to Play
    # ------------------------------------------------------------------

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🃏 How to Play -- Hi-Lo", color=PALETTE_GOLD)
        e.description = (
            "A card is dealt face-up. Predict whether the next card will be "
            "**Higher** or **Lower** in rank. Aces are highest (14); 2s are lowest.\n\n"
            "Each button shows what a correct guess multiplies your pot by. "
            "Unlikely guesses pay more; safe guesses pay little. You may keep "
            "guessing or click **Cash Out** to claim your winnings. "
            "A wrong guess ends the game and the bet is lost. Equal-rank next cards are skipped, and the deck reshuffles when needed."
        )

        e.add_field(
            name="Payouts",
            value=(
                "Each button shows what a correct guess multiplies your pot by. "
                "The riskier the guess, the bigger the multiplier. "
                f"The pot is capped at **{MAX_TOTAL_MULTIPLIER:g}×** your bet and cashes out "
                "automatically when it gets there."
            ),
            inline=False,
        )

        e.add_field(
            name="Bonuses",
            value=(
                "• **Bonus Bet Token** -- doubles your winnings on cash-out. "
                "Consumed before the deal; no effect on a loss.\n"
                "• **Multiplier Wheel** -- applies to profit on cash-out\n"
                "• **Lucky Streak** -- adds 25% of your winnings on cash-out; "
                "cancelled on any loss"
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    # ------------------------------------------------------------------
    # Back to floor
    # ------------------------------------------------------------------

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        # Lazy import avoids a circular dependency at module load time.
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        # Stop this view so its on_timeout can't strip the Game Room's buttons later.
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
    # Embed builders
    # ------------------------------------------------------------------

    def _build_idle_embed(self) -> discord.Embed:
        """Idle-state embed shown before the player places a bet."""
        user = self._user
        e    = discord.Embed(title="🃏 High Roller -- Hi-Lo", color=PALETTE_GOLD)

        desc = (
            "**Predict the card. Chain your guesses. Cash out before the deck turns.**\n\n"
            "Place your bet and click **Deal Card** to begin.\n"
            "Each correct prediction multiplies your pot -- long shots pay more. "
            "Cash out any time once you have at least one correct guess -- "
            "or keep pushing your luck."
        )

        mul = get_pending_multiplier(user)
        if mul is not None:
            desc += f"\n⚡ Bonus snapshot: **{mul}×** multiplier if it is still active on your next cash-out."
        if has_bonus_bet_token(user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token doubles your winnings if it is still unused when you cash out."
        if has_lucky_streak(user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak adds +25% of your winnings if it is still active on any cash-out win."

        e.description = desc

        if url := embed_image("hilo"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the GameRoom 'Back' flow."""
        return self._build_idle_embed()

    def _build_guess_embed(
        self,
        prev_card: Card | None = None,
        revealed_card: Card | None = None,
        guess: str | None = None,
        was_correct: bool = False,
        reshuffled: bool = False,
    ) -> discord.Embed:
        """Active guessing-phase embed.

        When called at game start (first card dealt): all optional args are None.
        When called after a correct guess: prev_card, revealed_card, guess, and
        was_correct are all provided.  self._current_card is already updated to
        revealed_card by the time this is called.
        """
        current = self._current_card
        depth   = self._chain_depth
        bet     = self._last_bet
        cur     = self._cached_currency
        assert self._deck is not None, "Deck not initialized before building Hi-Lo guess embed"
        remaining_cards = self._deck.remaining()

        e = discord.Embed(title="🃏 High Roller -- Hi-Lo", color=PALETTE_GOLD)

        # Payout per guess for the current card (the odds themselves are not shown).
        h_chance, l_chance = self._guess_chances()
        playable_remaining = sum(1 for card in remaining_cards if card.rank != current.rank)

        card_block = (
            f"```\n"
            f"  Current card : {current.label}\n"
            f"  Cards left   : {len(remaining_cards)}\n"
            f"  Playable     : {playable_remaining}\n"
            f"  Higher pays  : ×{guess_multiplier(h_chance):.2f}\n"
            f"  Lower pays   : ×{guess_multiplier(l_chance):.2f}\n"
            f"```"
        )

        reshuffle_line = "\n🔀 **Reshuffle:** The deck ran out of playable cards and was reshuffled before the next draw.\n" if reshuffled else ""

        if not was_correct or prev_card is None:
            # Initial state -- first card just dealt.
            desc = (
                f"**The card has been dealt.**\n"
                f"{card_block}\n"
                f"Bet: **{bet:,}** {cur} -- Guess **Higher** or **Lower**?"
            )
        else:
            # Post-correct-guess state -- show what just happened, then new card.
            guess_label = "Higher" if guess == "higher" else "Lower"
            potential   = calculate_payout(bet, self._multiplier)
            mult        = f"{self._multiplier:.2f}"
            desc = (
                f"✅ **Correct!** You guessed {guess_label}: "
                f"the next card was **{revealed_card.label}** (was **{prev_card.label}**).\n\n"
                f"{reshuffle_line}"
                f"**Chain: {depth} correct** -- Multiplier: **{mult}x**\n"
                f"{card_block}\n"
                f"Cash out now for **{potential:,}** {cur} -- or push your luck?"
            )

        e.description = desc

        # Active bonus indicators.
        bonuses: list[str] = []
        mul = get_pending_multiplier(self._user)
        if mul is not None:
            bonuses.append(f"⚡ Snapshot: **{mul}×** multiplier if it is still active when you cash out")
        if self._token_active:
            bonuses.append("🎫 Snapshot: Bonus Bet Token doubles your winnings if it is still unused when you cash out")
        if has_lucky_streak(self._user):
            bonuses.append("🔥 Snapshot: Lucky Streak adds +25% of your winnings if it is still active on a cash-out win")
        if bonuses:
            e.add_field(name="Bonus Snapshot", value="\n".join(bonuses), inline=False)

        if url := embed_image("hilo"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_result_embed(self, result: dict) -> discord.Embed:
        """Result-state embed for cash-out or loss."""
        e       = discord.Embed(title="🃏 High Roller -- Hi-Lo", color=PALETTE_GOLD)
        outcome = result["outcome"]
        bet     = result["bet"]
        depth   = result["depth"]
        cur     = self._cached_currency

        if outcome == "cashout":
            payout = result["payout"]
            mult   = f"{result.get('multiplier', 1.0):.2f}"
            guess_word = "guess" if depth == 1 else "guesses"
            desc = (
                f"**💰 Cashed Out!**\n"
                f"Chain: **{depth}** correct {guess_word} -- multiplier: **{mult}x**\n"
                f"Bet: **{bet:,}** {cur} → Payout: **{payout:,}** {cur}\n"
                f"*{random.choice(_WIN_CASHOUT_FLAVOR)}*"
            )
        else:
            # loss
            prev_card:     Card = result["prev_card"]
            revealed_card: Card = result["revealed_card"]
            guess_label = "Higher" if result["guess"] == "higher" else "Lower"
            chain_str = (
                f" after {depth} correct guess{'es' if depth != 1 else ''}"
                if depth > 0
                else ""
            )
            desc = (
                f"**❌ Wrong!** You guessed **{guess_label}** from **{prev_card.label}**, "
                f"but the next card was **{revealed_card.label}**{chain_str}.\n"
                f"Bet of **{bet:,}** {cur} lost.\n"
                f"*{random.choice(_LOSS_FLAVOR)}*"
            )
            if result.get("reshuffled"):
                desc += "\n🔀 **Reshuffle:** The deck ran out of playable cards and was reshuffled before that draw."

        if result.get("streak_cancelled"):
            desc += "\n💔 **Your lucky streak has ended.**"

        if result.get("rank_changed"):
            old_name = RANK_NAMES.get(result["old_rank"], "Unknown")
            new_name = RANK_NAMES.get(result["new_rank"], "Unknown")
            if result["new_rank"] > result["old_rank"]:
                desc += f"\n🏆 **Rank Up!** You are now a **{new_name}**!"
            else:
                desc += (
                    f"\n📉 **Rank Down.** "
                    f"**{old_name}** → **{new_name}**."
                )

        for slug in result.get("new_titles", []):
            title_str = SPECIALTY_TITLES.get(slug, slug)
            desc += f"\n🎖️ **New title unlocked:** {title_str}"

        e.description = desc

        if url := embed_image("hilo"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e
