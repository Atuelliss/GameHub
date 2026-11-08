"""Club Poker -- private two-player 5-card draw poker.

Flow
----
1. Challenger posts a public challenge for one opponent and ante amount.
2. Opponent accepts publicly; both antes are deducted.
3. Both players privately view 5-card hands via ephemeral controls. Each
   player's private panel is edited in place as the hand moves on (like
   Texas Hold'em), and every action is taken from that panel.
4. Each player privately selects holds and locks in their draw.
   Both private panels are sent automatically when the challenge is accepted.
   Every decision has a 90 second clock (ACTION_SECONDS). Missing the draw
   clock, or a Call/Fold decision, folds your hand; missing a turn with no
   bet open Stays (checks) for you. If neither player locks their draw in
   time, the hand is cancelled and both antes are refunded.
5. Once both lock, redraws are applied from a shared deck in fixed order:
   challenger first, challenged second.
6. One fixed betting round follows:
   - Challenger acts first.
   - If no bet is open: Stay or Bet.
   - If a bet is open: Call or Fold.
   - No raises.
7. If no fold occurs, showdown compares both final hands.
8. The winning hand is always shown publicly. The losing player gets
    15 seconds to Show Hand or Muck Hand. Timeout defaults to muck.
"""

from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.interactions import expire_view, safe_defer, safe_edit_original_response, safe_response_edit_message, not_your_session, session_expired
from ..common.constants import PALETTE_GOLD, RANK_NAMES, SPECIALTY_TITLES, embed_image
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    apply_rank_change,
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
    is_blacklisted,
    record_loss,
    record_win,
    validate_bet,
)
from ..games.poker import CP_HAND_NAMES, Card, Deck, compare_cp_showdown, evaluate_cp_hand

log = logging.getLogger("red.highrollerclub.clubpoker")

# Seconds a player has to make each decision before the game acts for them.
ACTION_SECONDS = 90


_CP_WIN_FLAVOR: dict[str, str] = {
    "royal_flush": "An historic hand. The table will talk about this for years.",
    "straight_flush": "Five in sequence, same suit. A beautiful hand.",
    "four_of_a_kind": "Four of a kind. Dominant from the start.",
    "full_house": "Full house. There was no coming back from that.",
    "flush": "A flush at exactly the right moment.",
    "straight": "Straight. The better hand, cleanly dealt.",
    "three_of_a_kind": "Three of a kind held the edge tonight.",
    "two_pair": "Two pair was enough this time.",
    "pair": "A pair sealed the win.",
    "high_card": "High card takes it when no one makes a hand.",
}

_CP_TIE_FLAVOR: list[str] = [
    "Identical hands. The pot splits down the middle.",
    "Dead even. Both wagers come back home.",
    "A standoff. No winner, no loser tonight.",
]


@dataclass
class _ClubPokerPlayerState:
    member: discord.Member
    user: User
    hand: list[Card] = field(default_factory=list)
    held: list[bool] = field(default_factory=lambda: [False, False, False, False, False])
    draw_locked: bool = False
    cards_replaced: int = 0
    extra_committed: int = 0

    @property
    def committed_total(self) -> int:
        return self.extra_committed


class _ClubPokerSession:
    def __init__(
        self,
        challenger: discord.Member,
        challenger_user: User,
        challenged: discord.Member,
        challenged_user: User,
        conf: GuildSettings,
        cog: MixinMeta,
        ante: int,
        currency: str,
    ) -> None:
        self.challenger = _ClubPokerPlayerState(challenger, challenger_user)
        self.challenged = _ClubPokerPlayerState(challenged, challenged_user)
        self.conf = conf
        self.cog = cog
        self.ante = ante
        self.currency = currency
        self.deck = Deck()
        self.lock = asyncio.Lock()
        self.phase = "draw"
        self.turn_user_id = challenger.id
        self.bet_open = False
        self.bettor_id: int | None = None
        self.first_check_complete = False
        self.public_message: discord.Message | None = None
        self.public_view: ClubPokerSessionView | None = None
        self.result: dict | None = None
        self.loser_visibility: str | None = None
        self.loser_user_id: int | None = None
        self._muck_task: asyncio.Task | None = None
        self._resolved = False
        # Each player's open private panel, edited in place whenever the hand changes.
        # An interaction (the player pressed a button on it) or a followup message (sent on accept).
        self.panels: dict[int, discord.Interaction | discord.WebhookMessage] = {}
        # Action clock. turn_token goes up whenever the clock restarts or stops,
        # so a timer that fires late can tell it is stale.
        self.turn_token = 0
        self.turn_deadline: datetime | None = None
        self._turn_task: asyncio.Task | None = None
        self.timed_out_user_id: int | None = None
        # Players who ran out of time with no bet open and were Stayed for automatically.
        self.auto_stayed: list[int] = []
        self.refresh_count = 0  # bumped on every full redraw, so callers know panels are fresh

        self.challenger.hand = self.deck.deal(5)
        self.challenged.hand = self.deck.deal(5)

    def all_players(self) -> list[_ClubPokerPlayerState]:
        return [self.challenger, self.challenged]

    def is_participant(self, user_id: int) -> bool:
        return user_id in {self.challenger.member.id, self.challenged.member.id}

    def player_for(self, user_id: int) -> _ClubPokerPlayerState:
        if user_id == self.challenger.member.id:
            return self.challenger
        if user_id == self.challenged.member.id:
            return self.challenged
        raise KeyError(f"Unknown player id: {user_id}")

    def other_player(self, user_id: int) -> _ClubPokerPlayerState:
        if user_id == self.challenger.member.id:
            return self.challenged
        if user_id == self.challenged.member.id:
            return self.challenger
        raise KeyError(f"Unknown player id: {user_id}")

    def total_pot(self) -> int:
        return (self.ante * 2) + self.challenger.extra_committed + self.challenged.extra_committed

    def committed_total_for(self, player: _ClubPokerPlayerState) -> int:
        return self.ante + player.extra_committed

    def _challenger_hand_text(self) -> tuple[str, str]:
        return (
            "  ".join(card.label for card in self.challenger.hand),
            CP_HAND_NAMES[evaluate_cp_hand(self.challenger.hand)],
        )

    def _challenged_hand_text(self) -> tuple[str, str]:
        return (
            "  ".join(card.label for card in self.challenged.hand),
            CP_HAND_NAMES[evaluate_cp_hand(self.challenged.hand)],
        )

    def replacement_count_for(self, user_id: int) -> int:
        return self.player_for(user_id).cards_replaced

    def deadline_text(self) -> str:
        """Relative Discord timestamp for the current action clock, e.g. 'in 1 minute'."""
        if self.turn_deadline is None:
            return f"within {ACTION_SECONDS} seconds"
        return f"<t:{int(self.turn_deadline.timestamp())}:R>"

    def timeout_penalty(self) -> str:
        """What happens to the player on the clock if they don't act in time."""
        if self.phase == "betting" and not self.bet_open:
            return "you **Stay** (check) automatically"
        return "your hand is **folded**"

    def _status_line(self) -> str:
        if self.phase == "draw":
            return (
                f"{self.challenger.member.mention}: {'locked' if self.challenger.draw_locked else 'choosing cards'}\n"
                f"{self.challenged.member.mention}: {'locked' if self.challenged.draw_locked else 'choosing cards'}\n"
                f"⏰ Draws must be locked {self.deadline_text()} or that hand is folded."
            )
        if self.phase == "betting":
            actor = self.player_for(self.turn_user_id).member.mention
            if self.bet_open:
                clock = f"\n⏰ {actor} must act {self.deadline_text()} or their hand is folded."
            else:
                clock = f"\n⏰ {actor} must act {self.deadline_text()} or they Stay automatically."
            for uid in self.auto_stayed:
                clock = f"\n⏰ {self.player_for(uid).member.mention} ran out of time and Stayed automatically." + clock
            if self.bet_open and self.bettor_id is not None:
                bettor = self.player_for(self.bettor_id).member.mention
                return f"Betting round: {bettor} opened betting for **{self.ante:,} {self.currency}**. Waiting on {actor}.{clock}"
            return f"Betting round: it is {actor}'s turn.{clock}"
        if self.phase == "muck_choice":
            if self.loser_user_id is None:
                return "The losing player has 15 seconds to show or muck their hand."
            loser = self.player_for(self.loser_user_id).member.mention
            return f"{loser} has 15 seconds to show or muck their hand."
        if self.phase == "cancelled":
            return "The hand was cancelled and all committed bets were refunded."
        return "Hand resolved."

    def build_public_embed(self) -> discord.Embed:
        if self.result is None:
            embed = discord.Embed(title="🃏 Club Poker", color=PALETTE_GOLD)
            embed.description = (
                f"**Players:** {self.challenger.member.mention} vs {self.challenged.member.mention}\n"
                f"**Ante:** {self.ante:,} {self.currency} each\n"
                f"**Pot:** {self.total_pot():,} {self.currency}\n\n"
                "Your private hand has been sent to each player. Every decision is made there, "
                f"and you have **{ACTION_SECONDS} seconds** for each one. Lost your hand? Press **Reopen My Hand**.\n\n"
                f"{self._status_line()}"
            )
            if url := embed_image("clubpoker"):
                embed.set_thumbnail(url=url)
            return embed

        if self.result["outcome"] == "cancelled":
            embed = discord.Embed(
                title="🃏 Club Poker -- Cancelled",
                color=discord.Color.red(),
                description=(
                    f"{self.result.get('reason') or 'The hand was cancelled.'}\n"
                    "Every committed bet was refunded. No money changed hands."
                ),
            )
            if url := embed_image("clubpoker"):
                embed.set_thumbnail(url=url)
            return embed

        challenger_cards, challenger_hand_name = self._challenger_hand_text()
        challenged_cards, challenged_hand_name = self._challenged_hand_text()

        outcome = self.result["outcome"]
        winner = self.result["winner"]
        total_payout = self.result["total_payout"]
        net_profit = self.result["net_profit"]
        fold_user = self.result["fold_user"]

        challenged_section: str
        challenged_is_loser = self.loser_user_id == self.challenged.member.id
        if not challenged_is_loser:
            challenged_section = f"**{self.challenged.member.mention}:**\n{challenged_cards}\n*{challenged_hand_name}*"
        elif self.loser_visibility == "show":
            challenged_section = f"**{self.challenged.member.mention}:**\n{challenged_cards}\n*{challenged_hand_name}*"
        elif self.loser_visibility == "muck":
            challenged_section = f"**{self.challenged.member.mention}:**\n🂠 Hand mucked."
        else:
            challenged_section = f"**{self.challenged.member.mention}:**\n🂠 Hand hidden pending reveal choice."

        challenger_is_loser = self.loser_user_id == self.challenger.member.id
        if not challenger_is_loser:
            challenger_section = f"**{self.challenger.member.mention}:**\n{challenger_cards}\n*{challenger_hand_name}*"
        elif self.loser_visibility == "show":
            challenger_section = f"**{self.challenger.member.mention}:**\n{challenger_cards}\n*{challenger_hand_name}*"
        elif self.loser_visibility == "muck":
            challenger_section = f"**{self.challenger.member.mention}:**\n🂠 Hand mucked."
        else:
            challenger_section = f"**{self.challenger.member.mention}:**\n🂠 Hand hidden pending reveal choice."

        lines = [
            challenger_section,
            challenged_section,
            "",
        ]

        if outcome == "tie":
            lines.append(f"🤝 **Tie!** Both players get their committed bets back.")
            lines.append(f"*{random.choice(_CP_TIE_FLAVOR)}*")
        elif outcome == "fold":
            assert winner is not None
            lines.append(f"🏆 **{winner.mention} wins by fold.**")
            if fold_user is not None:
                if self.timed_out_user_id == fold_user.id:
                    lines.append(f"⏰ {fold_user.mention} ran out of time and their hand was folded.")
                else:
                    lines.append(f"{fold_user.mention} folded during the betting round.")
            lines.append(
                f"Pot: **{self.total_pot():,}** {self.currency} → Payout: **{total_payout:,}** {self.currency} *(+{net_profit:,} profit)*"
            )
            lines.append(f"*{_CP_WIN_FLAVOR.get(self.result['winner_rank'], 'The better line took the pot.')}*")
        else:
            assert winner is not None
            lines.append(f"🏆 **{winner.mention} wins at showdown.**")
            lines.append(
                f"Pot: **{self.total_pot():,}** {self.currency} → Payout: **{total_payout:,}** {self.currency} *(+{net_profit:,} profit)*"
            )
            lines.append(f"*{_CP_WIN_FLAVOR.get(self.result['winner_rank'], 'The better hand wins.')}*")

        if self.phase == "muck_choice" and self.loser_visibility is None:
            lines.append("⏳ Waiting for the losing player to show or muck their hand.")

        embed = discord.Embed(
            title="🃏 Club Poker -- Result",
            color=PALETTE_GOLD if self.phase != "cancelled" else discord.Color.red(),
            description="\n".join(lines),
        )
        if url := embed_image("clubpoker"):
            embed.set_thumbnail(url=url)
        return embed

    async def refresh_public(self) -> None:
        if self.public_message is None or self.public_view is None:
            return
        self.public_view.sync_items()
        try:
            await self.public_message.edit(embed=self.build_public_embed(), view=self.public_view)
        except discord.HTTPException:
            log.warning("Club Poker: couldn't update the public message")

    async def refresh_panels(self) -> None:
        """Redraw every open private panel. A panel Discord won't edit any more is forgotten."""
        if not self.panels:
            return

        async def redraw(uid: int, panel: discord.Interaction | discord.WebhookMessage) -> None:
            view = ClubPokerPrivateView(self, uid)
            try:
                if isinstance(panel, discord.Interaction):
                    await panel.edit_original_response(embed=view.build_embed(), view=view)
                else:
                    await panel.edit(embed=view.build_embed(), view=view)
            except (discord.HTTPException, discord.NotFound):
                if self.panels.get(uid) is panel:
                    self.panels.pop(uid, None)

        await asyncio.gather(*(redraw(uid, i) for uid, i in list(self.panels.items())), return_exceptions=True)

    async def refresh(self) -> None:
        self.refresh_count += 1
        await self.refresh_public()
        await self.refresh_panels()

    # -- action clock --------------------------------------------------------

    def start_turn_timer(self) -> None:
        """Restart the action clock for whoever has to act now."""
        self.stop_turn_timer()
        self.turn_deadline = datetime.now(timezone.utc) + timedelta(seconds=ACTION_SECONDS)
        self._turn_task = asyncio.create_task(self._turn_timer(self.turn_token))

    def stop_turn_timer(self) -> None:
        self.turn_token += 1
        self.turn_deadline = None
        if self._turn_task is not None and self._turn_task is not asyncio.current_task():
            self._turn_task.cancel()
        self._turn_task = None

    async def _turn_timer(self, token: int) -> None:
        try:
            await asyncio.sleep(ACTION_SECONDS)
            async with self.lock:
                await self._on_turn_timeout(token)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Club Poker: action timer failed")

    async def _on_turn_timeout(self, token: int) -> None:
        """The clock ran out: Stay if no bet is open, otherwise fold. (Caller holds self.lock.)"""
        if token != self.turn_token or self._resolved:
            return
        if self.phase == "draw":
            late = [p for p in self.all_players() if not p.draw_locked]
            if len(late) == 2:
                await self.cancel_and_refund("Neither player locked their draw in time.")
            elif len(late) == 1:
                self.timed_out_user_id = late[0].member.id
                await self.resolve_hand(fold_user_id=late[0].member.id)
        elif self.phase == "betting" and self.turn_user_id is not None:
            if self.bet_open:
                self.timed_out_user_id = self.turn_user_id
                await self.resolve_hand(fold_user_id=self.turn_user_id)
            else:
                self.auto_stayed.append(self.turn_user_id)
                await self.take_check(self.turn_user_id)

    async def cancel_and_refund(self, reason: str) -> None:
        if self._resolved:
            return
        if self.phase != "draw" and self.phase != "betting":
            return
        self.stop_turn_timer()
        self._resolved = True
        self.phase = "cancelled"
        await credit_balance(self.challenger.member, self.conf, self.challenger.user, self.committed_total_for(self.challenger))
        await credit_balance(self.challenged.member, self.conf, self.challenged.user, self.committed_total_for(self.challenged))
        self.result = {
            "outcome": "cancelled",
            "winner": None,
            "winner_rank": None,
            "total_payout": 0,
            "net_profit": 0,
            "fold_user": None,
            "reason": reason,
        }
        self.cog.save()
        await self.refresh()

    async def lock_draw(self, user_id: int) -> None:
        player = self.player_for(user_id)
        player.draw_locked = True
        if not all(p.draw_locked for p in self.all_players()):
            await self.refresh()
            return

        for p in (self.challenger, self.challenged):
            p.cards_replaced = 0
            for idx in range(5):
                if not p.held[idx]:
                    p.cards_replaced += 1
                    p.hand[idx] = self.deck.draw()

        self.phase = "betting"
        self.turn_user_id = self.challenger.member.id
        self.bet_open = False
        self.bettor_id = None
        self.first_check_complete = False
        self.start_turn_timer()
        await self.refresh()

    async def take_check(self, user_id: int) -> None:
        if self.phase != "betting" or self.bet_open or self.turn_user_id != user_id:
            return
        if user_id == self.challenger.member.id and not self.first_check_complete:
            self.first_check_complete = True
            self.turn_user_id = self.challenged.member.id
            self.start_turn_timer()
            await self.refresh()
            return
        await self.resolve_hand()

    async def open_bet(self, user_id: int) -> str | None:
        if self.phase != "betting" or self.bet_open or self.turn_user_id != user_id:
            return None
        player = self.player_for(user_id)
        balance = await get_balance(player.member, self.conf, player.user)
        if balance < self.ante or not await deduct_balance(player.member, self.conf, player.user, self.ante):
            return f"You no longer have enough {self.currency} to open betting for **{self.ante:,}**."
        player.extra_committed += self.ante
        self.bet_open = True
        self.bettor_id = user_id
        self.turn_user_id = self.other_player(user_id).member.id
        self.start_turn_timer()
        await self.refresh()
        return None

    async def call_bet(self, user_id: int) -> str | None:
        if self.phase != "betting" or not self.bet_open or self.turn_user_id != user_id:
            return None
        player = self.player_for(user_id)
        balance = await get_balance(player.member, self.conf, player.user)
        if balance < self.ante or not await deduct_balance(player.member, self.conf, player.user, self.ante):
            return f"You no longer have enough {self.currency} to call **{self.ante:,}**."
        player.extra_committed += self.ante
        await self.resolve_hand()
        return None

    async def fold_hand(self, user_id: int) -> None:
        if self.phase != "betting" or not self.bet_open or self.turn_user_id != user_id:
            return
        await self.resolve_hand(fold_user_id=user_id)

    async def resolve_hand(self, fold_user_id: int | None = None) -> None:
        if self._resolved:
            return
        self.stop_turn_timer()

        challenger_rank = evaluate_cp_hand(self.challenger.hand)
        challenged_rank = evaluate_cp_hand(self.challenged.hand)

        total_payout = 0
        net_profit = 0
        winner: discord.Member | None = None
        winner_player: _ClubPokerPlayerState | None = None
        loser_player: _ClubPokerPlayerState | None = None
        outcome: str

        if fold_user_id is not None:
            loser_player = self.player_for(fold_user_id)
            winner_player = self.other_player(fold_user_id)
            winner = winner_player.member
            outcome = "fold"
            total_payout = self.total_pot()
            winner_bet = self.committed_total_for(winner_player)
            await credit_balance(winner_player.member, self.conf, winner_player.user, total_payout)
            loser_bet = self.committed_total_for(loser_player)
            record_win(self.conf, winner_player.user, "clubpoker", total_payout, winner_bet)
            record_loss(self.conf, loser_player.user, "clubpoker", loser_bet)
            net_profit = total_payout - winner_bet
        else:
            comparison = compare_cp_showdown(self.challenger.hand, self.challenged.hand)
            if comparison == 0:
                outcome = "tie"
                await credit_balance(self.challenger.member, self.conf, self.challenger.user, self.committed_total_for(self.challenger))
                await credit_balance(self.challenged.member, self.conf, self.challenged.user, self.committed_total_for(self.challenged))
            else:
                winner_player = self.challenger if comparison > 0 else self.challenged
                loser_player = self.challenged if comparison > 0 else self.challenger
                winner = winner_player.member
                outcome = "showdown"
                total_payout = self.total_pot()
                winner_bet = self.committed_total_for(winner_player)
                await credit_balance(winner_player.member, self.conf, winner_player.user, total_payout)
                loser_bet = self.committed_total_for(loser_player)
                record_win(self.conf, winner_player.user, "clubpoker", total_payout, winner_bet)
                record_loss(self.conf, loser_player.user, "clubpoker", loser_bet)
                net_profit = total_payout - winner_bet

        for player in self.all_players():
            old_rank = player.user.rank
            new_rank = evaluate_rank(self.conf, player.user)
            if new_rank != old_rank:
                apply_rank_change(player.user, new_rank)
            new_titles = evaluate_specialty_titles(player.user)
            player.user.earned_titles.extend(new_titles)

        self.cog.save()

        self.result = {
            "outcome": outcome,
            "winner": winner,
            "winner_rank": challenger_rank if winner == self.challenger.member else challenged_rank,
            "challenger_rank": challenger_rank,
            "challenged_rank": challenged_rank,
            "total_payout": total_payout,
            "net_profit": net_profit,
            "fold_user": self.player_for(fold_user_id).member if fold_user_id is not None else None,
        }

        self.phase = "muck_choice"
        self.turn_user_id = None
        self.bet_open = False
        self.bettor_id = None
        self._resolved = True
        self.loser_user_id = loser_player.member.id if loser_player is not None else None
        self.loser_visibility = None
        if outcome == "tie" or self.loser_user_id is None:
            self.phase = "resolved"
        else:
            if self._muck_task is not None:
                self._muck_task.cancel()
            self._muck_task = asyncio.create_task(self._auto_muck())
        await self.refresh()

    async def _auto_muck(self) -> None:
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            return
        async with self.lock:
            if self.phase == "muck_choice" and self.loser_visibility is None:
                self.loser_visibility = "muck"
                self.phase = "resolved"
                await self.refresh()

    async def set_loser_visibility(self, visibility: str) -> None:
        if self.phase != "muck_choice" or self.loser_visibility is not None:
            return
        self.loser_visibility = visibility
        self.phase = "resolved"
        if self._muck_task is not None:
            self._muck_task.cancel()
            self._muck_task = None
        await self.refresh()


class ClubPokerChallengeModal(discord.ui.Modal, title="Club Poker: Challenge a Player"):
    def __init__(self, view: "ClubPokerView") -> None:
        super().__init__()
        self._view = view
        min_bet, max_bet = get_bet_limits(view._conf, "clubpoker", view._user.rank)
        self.bet_input = discord.ui.TextInput(
            label=f"Ante Amount (min {min_bet:,} · max {max_bet:,})",
            placeholder=f"Enter {min_bet:,} to {max_bet:,}",
            min_length=1,
            max_length=10,
        )
        self.opponent_input = discord.ui.TextInput(
            label="Opponent (@mention, exact name, or user ID)",
            placeholder="@username  or  Display Name  or  123456789012345678",
            min_length=2,
            max_length=50,
        )
        self.add_item(self.bet_input)
        self.add_item(self.opponent_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        await self._view._process_challenge(
            interaction,
            self.bet_input.value,
            self.opponent_input.value,
        )


class ClubPokerView(discord.ui.View):
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

    def _add_idle_buttons(self) -> None:
        self.clear_items()
        challenge_btn = discord.ui.Button(label="🃏 Challenge a Player", style=discord.ButtonStyle.green, row=0)
        challenge_btn.callback = self._on_challenge
        self.add_item(challenge_btn)

        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1)
        info.callback = self._show_info
        self.add_item(info)

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if not await channel_allowed(interaction.client, self._conf, interaction.user, interaction.channel_id):
            await interaction.response.send_message(
                "Club Poker can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False
        if not self._conf.games_enabled.get("clubpoker", True):
            await interaction.response.send_message(
                "Club Poker is currently disabled on this server.",
                ephemeral=True,
            )
            return False
        return True

    async def _on_challenge(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await interaction.response.send_modal(ClubPokerChallengeModal(self))

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🃏 How to Play: Club Poker", color=PALETTE_GOLD)
        e.description = (
            "**Heads-up private 5-card draw with one betting round.**\n\n"
            "1. Challenge one player for an ante amount.\n"
            "2. On accept, both antes are locked in.\n"
            "3. Both players privately choose which cards to hold.\n"
            "4. After both lock in, replacement cards are drawn from the same deck.\n"
            "5. One betting round follows: Stay or Bet, then Call or Fold. No raises.\n"
            "6. If neither player folds, the best 5-card hand wins.\n\n"
            "Your private hand is sent to you as soon as the challenge is accepted. It updates itself and tells you when the game is waiting on you. "
            f"You get **{ACTION_SECONDS} seconds** for each decision. **If you don't act in time, your hand is folded**, "
            "except when no bet is open: then you Stay automatically. "
            "If neither player locks their draw in time, the hand is cancelled and both antes are refunded.\n\n"
            "The winning hand is always shown publicly. The losing player gets 15 seconds to show or muck their hand.\n\n"
            "No bonuses apply: no Lucky Streak, Bonus Bet Token or Multiplier Wheel. Every chip in the pot comes from the two players."
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

    async def _process_challenge(self, interaction: discord.Interaction, bet_raw: str, opponent_raw: str) -> None:
        raw = bet_raw.strip().replace(",", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.followup.send("Please enter a valid positive whole number for the ante.", ephemeral=True)
            return
        bet = int(raw)

        guild = interaction.guild
        opponent_str = opponent_raw.strip()
        challenged_member: discord.Member | None = None
        if opponent_str.startswith("<@") and opponent_str.endswith(">"):
            id_str = opponent_str.lstrip("<@!").rstrip(">")
        else:
            id_str = opponent_str.lstrip("@")

        if id_str.isdigit():
            challenged_member = guild.get_member(int(id_str))
            if challenged_member is None:
                try:
                    challenged_member = await guild.fetch_member(int(id_str))
                except Exception:
                    challenged_member = None
        else:
            needle = opponent_str.lstrip("@").casefold()
            matches: list[discord.Member] = []
            for member in guild.members:
                candidates = {member.display_name.casefold(), member.name.casefold()}
                if member.global_name:
                    candidates.add(member.global_name.casefold())
                if needle in candidates:
                    matches.append(member)
            if len(matches) == 1:
                challenged_member = matches[0]
            elif len(matches) > 1:
                await interaction.followup.send(
                    "Multiple members match that name. Use an @mention or paste their user ID instead.",
                    ephemeral=True,
                )
                return

        if challenged_member is None:
            await interaction.followup.send(
                "That user couldn't be found in this server. Use an @mention, exact name, or user ID.",
                ephemeral=True,
            )
            return
        if challenged_member.id == self._member.id:
            await interaction.followup.send("You can't challenge yourself.", ephemeral=True)
            return
        if challenged_member.bot:
            await interaction.followup.send("You can't challenge a bot.", ephemeral=True)
            return
        if is_blacklisted(self._conf, challenged_member.id):
            await interaction.followup.send(
                f"{challenged_member.display_name} can't play at the club right now.", ephemeral=True
            )
            return

        challenger_balance = await get_balance(self._member, self._conf, self._user)
        if await session_expired(self, interaction):
            return
        error = validate_bet(self._conf, self._user, "clubpoker", bet, challenger_balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        challenged_user = self._conf.get_user(challenged_member.id)
        challenged_balance = await get_balance(challenged_member, self._conf, challenged_user)
        if challenged_balance < bet:
            await interaction.followup.send(
                f"{challenged_member.display_name} doesn't have enough {self._cached_currency or 'chips'} to cover a **{bet:,}** ante.",
                ephemeral=True,
            )
            return

        challenge_embed = discord.Embed(
            title="🃏 Club Poker Challenge",
            color=PALETTE_GOLD,
            description=(
                f"{self._member.mention} challenges {challenged_member.mention} to **Club Poker**!\n\n"
                f"**Ante:** {bet:,} {self._cached_currency or 'chips'} each\n"
                "Private 5-card draw, then one betting round.\n\n"
                f"{challenged_member.mention} -- accept or decline below.\n"
                "*This challenge expires in 5 minutes.*"
            ),
        )
        if url := embed_image("clubpoker"):
            challenge_embed.set_thumbnail(url=url)

        challenge_view = ClubPokerChallengeView(
            challenger=self._member,
            challenger_user=self._user,
            challenged=challenged_member,
            challenged_user=challenged_user,
            conf=self._conf,
            cog=self._cog,
            ante=bet,
            currency=self._cached_currency or "chips",
            challenger_interaction=interaction,
        )
        challenge_message = await interaction.followup.send(embed=challenge_embed, view=challenge_view, wait=True)
        challenge_view._message = challenge_message

        waiting_embed = discord.Embed(
            title="🃏 High Roller: Club Poker",
            color=PALETTE_GOLD,
            description=f"⏳ Challenge sent to {challenged_member.mention}! Waiting for their response...",
        )
        if url := embed_image("clubpoker"):
            waiting_embed.set_thumbnail(url=url)
        self.clear_items()
        await safe_edit_original_response(interaction, embed=waiting_embed, view=self)

    def _build_idle_embed(self) -> discord.Embed:
        e = discord.Embed(title="🃏 High Roller: Club Poker", color=PALETTE_GOLD)
        desc = (
            "**Heads-up private 5-card draw poker.**\n\n"
            "Challenge one other player. Both players ante the same amount, privately choose holds, draw replacements, then play one fixed betting round with **Stay**, **Bet**, **Call**, or **Fold**.\n\n"
            "The winning hand is always shown. The losing hand may be shown or mucked."
        )
        if mul := get_pending_multiplier(self._user):
            desc += f"\n\n⚡ Bonus snapshot: **{mul}x** multiplier is stored on your account, but Club Poker does not use it."
        if has_bonus_bet_token(self._user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token is stored on your account, but Club Poker does not use it."
        if has_lucky_streak(self._user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak is stored on your account, but Club Poker does not use it."
        e.description = desc
        if url := embed_image("clubpoker"):
            e.set_thumbnail(url=url)
        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")
        return e

    def _build_embed(self) -> discord.Embed:
        return self._build_idle_embed()


class ClubPokerChallengeView(discord.ui.View):
    def __init__(
        self,
        challenger: discord.Member,
        challenger_user: User,
        challenged: discord.Member,
        challenged_user: User,
        conf: GuildSettings,
        cog: MixinMeta,
        ante: int,
        currency: str,
        challenger_interaction: discord.Interaction,
    ) -> None:
        super().__init__(timeout=300)
        # The challenger's own interaction (their challenge form). Only it can send them a
        # private message, so it's how their hand is delivered when the challenge is accepted.
        self._challenger_interaction = challenger_interaction
        self._challenger = challenger
        self._challenger_user = challenger_user
        self._challenged = challenged
        self._challenged_user = challenged_user
        self._conf = conf
        self._cog = cog
        self._ante = ante
        self._currency = currency
        self._resolved = False
        self._message: discord.Message | None = None

        accept_btn = discord.ui.Button(label="✅ Accept", style=discord.ButtonStyle.green, row=0)
        accept_btn.callback = self._on_accept
        self.add_item(accept_btn)
        decline_btn = discord.ui.Button(label="❌ Decline", style=discord.ButtonStyle.red, row=0)
        decline_btn.callback = self._on_decline
        self.add_item(decline_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._challenged.id:
            await interaction.response.send_message(
                f"Only {self._challenged.display_name} can respond to this challenge.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        if self._resolved:
            return
        self._resolved = True
        self.clear_items()
        if self._message is not None:
            expired = discord.Embed(
                title="🃏 Club Poker Challenge -- Expired",
                color=discord.Color.dark_grey(),
                description="The challenge expired before it was accepted. No money changed hands.",
            )
            if url := embed_image("clubpoker"):
                expired.set_thumbnail(url=url)
            await self._message.edit(embed=expired, view=self)

    async def _on_accept(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message("This challenge has already been resolved.", ephemeral=True)
            return
        self._resolved = True
        # Stop the challenge timer so on_timeout can't overwrite the session/cancelled embed.
        self.stop()
        await safe_defer(interaction)

        challenger_balance = await get_balance(self._challenger, self._conf, self._challenger_user)
        challenged_balance = await get_balance(self._challenged, self._conf, self._challenged_user)
        antes_in = False
        if challenger_balance >= self._ante and challenged_balance >= self._ante:
            # Either deduct can still fail if a balance changed after the check above.
            if await deduct_balance(self._challenger, self._conf, self._challenger_user, self._ante):
                if await deduct_balance(self._challenged, self._conf, self._challenged_user, self._ante):
                    antes_in = True
                else:
                    await credit_balance(self._challenger, self._conf, self._challenger_user, self._ante)
        if not antes_in:
            self.clear_items()
            cancelled = discord.Embed(
                title="🃏 Club Poker -- Cancelled",
                color=discord.Color.red(),
                description="One of the players no longer has enough balance to cover the ante.",
            )
            if url := embed_image("clubpoker"):
                cancelled.set_thumbnail(url=url)
            await safe_edit_original_response(interaction, embed=cancelled, view=self)
            return

        session = _ClubPokerSession(
            challenger=self._challenger,
            challenger_user=self._challenger_user,
            challenged=self._challenged,
            challenged_user=self._challenged_user,
            conf=self._conf,
            cog=self._cog,
            ante=self._ante,
            currency=self._currency,
        )
        session.public_message = interaction.message
        session_view = ClubPokerSessionView(session)
        session.public_view = session_view
        session.start_turn_timer()  # the draw clock
        await safe_edit_original_response(interaction, embed=session.build_public_embed(), view=session_view)

        # Deliver both private hands straight away, so nobody has to press a button to start.
        async def send_hand(user_id: int, via: discord.Interaction) -> None:
            view = ClubPokerPrivateView(session, user_id)
            try:
                message = await via.followup.send(embed=view.build_embed(), view=view, ephemeral=True, wait=True)
            except discord.HTTPException:
                log.warning("Club Poker: couldn't deliver the private hand to %s", user_id)
                return
            session.panels.setdefault(user_id, message)

        await asyncio.gather(
            send_hand(self._challenger.id, self._challenger_interaction),
            send_hand(self._challenged.id, interaction),
        )

    async def _on_decline(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message("This challenge has already been resolved.", ephemeral=True)
            return
        self._resolved = True
        self.stop()
        self.clear_items()
        declined_embed = discord.Embed(
            title="🃏 Club Poker Challenge -- Declined",
            color=discord.Color.dark_grey(),
            description=(
                f"{self._challenged.mention} declined the challenge from {self._challenger.mention}.\n"
                "No money changed hands."
            ),
        )
        if url := embed_image("clubpoker"):
            declined_embed.set_thumbnail(url=url)
        await safe_response_edit_message(interaction, embed=declined_embed, view=self)


class ClubPokerSessionView(discord.ui.View):
    def __init__(self, session: _ClubPokerSession) -> None:
        super().__init__(timeout=600)
        self._session = session
        self.sync_items()

    def sync_items(self) -> None:
        self.clear_items()
        # Both hands are sent automatically on accept. This is only a fallback for a player
        # who dismissed theirs, or whose hand couldn't be delivered.
        if self._session.phase in {"draw", "betting", "muck_choice"}:
            open_btn = discord.ui.Button(label="🂠 Reopen My Hand", style=discord.ButtonStyle.grey, row=0)
            open_btn.callback = self._open_private
            self.add_item(open_btn)

    async def _open_private(self, interaction: discord.Interaction) -> None:
        if not self._session.is_participant(interaction.user.id):
            await interaction.response.send_message("Only the two players in this hand can open private controls.", ephemeral=True)
            return
        view = ClubPokerPrivateView(self._session, interaction.user.id)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)
        self._session.panels[interaction.user.id] = interaction

    async def on_timeout(self) -> None:
        async with self._session.lock:
            if self._session.phase == "muck_choice" and self._session.loser_visibility is None:
                self._session.loser_visibility = "muck"
                self._session.phase = "resolved"
                self.sync_items()
                if self._session.public_message is not None:
                    await self._session.public_message.edit(embed=self._session.build_public_embed(), view=self)
                return
            if self._session.phase in {"draw", "betting"}:
                await self._session.cancel_and_refund("timed out")
                self.sync_items()


class ClubPokerPrivateView(discord.ui.View):
    def __init__(self, session: _ClubPokerSession, user_id: int) -> None:
        super().__init__(timeout=900)  # Discord lets an ephemeral reply be edited for 15 minutes
        self._session = session
        self._user_id = user_id
        self.sync_items()

    def _player(self) -> _ClubPokerPlayerState:
        return self._session.player_for(self._user_id)

    def sync_items(self) -> None:
        self.clear_items()
        player = self._player()

        if self._session.phase == "draw" and not player.draw_locked:
            for idx, card in enumerate(player.hand):
                held = player.held[idx]
                label = f"[HOLD] {card.label}" if held else card.label
                button = discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.green if held else discord.ButtonStyle.grey,
                    row=0,
                )
                button.callback = self._make_hold_callback(idx)
                self.add_item(button)

            lock_btn = discord.ui.Button(label="🔒 Lock Draw", style=discord.ButtonStyle.blurple, row=1)
            lock_btn.callback = self._lock_draw()
            self.add_item(lock_btn)

        elif self._session.phase == "betting" and self._session.turn_user_id == self._user_id:
            if self._session.bet_open:
                call_btn = discord.ui.Button(label=f"📞 Call ({self._session.ante:,})", style=discord.ButtonStyle.green, row=0)
                call_btn.callback = self._call_bet()
                self.add_item(call_btn)
                fold_btn = discord.ui.Button(label="🚪 Fold", style=discord.ButtonStyle.red, row=0)
                fold_btn.callback = self._fold_hand()
                self.add_item(fold_btn)
            else:
                stay_btn = discord.ui.Button(label="✋ Stay", style=discord.ButtonStyle.grey, row=0)
                stay_btn.callback = self._take_check()
                self.add_item(stay_btn)
                bet_btn = discord.ui.Button(label=f"💰 Bet ({self._session.ante:,})", style=discord.ButtonStyle.green, row=0)
                bet_btn.callback = self._open_bet()
                self.add_item(bet_btn)

        elif (
            self._session.phase == "muck_choice"
            and self._user_id == self._session.loser_user_id
            and self._session.loser_visibility is None
        ):
            show_btn = discord.ui.Button(label="🪞 Show Hand", style=discord.ButtonStyle.green, row=0)
            show_btn.callback = self._show_hand()
            self.add_item(show_btn)
            muck_btn = discord.ui.Button(label="🂠 Muck Hand", style=discord.ButtonStyle.grey, row=0)
            muck_btn.callback = self._muck_hand()
            self.add_item(muck_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._user_id:
            await interaction.response.send_message("These private controls aren't for you.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        self.clear_items()

    def _is_my_move(self) -> bool:
        """True when the hand is waiting on this player."""
        session = self._session
        if session.phase == "draw":
            return not self._player().draw_locked
        if session.phase == "betting":
            return session.turn_user_id == self._user_id
        return False

    def build_embed(self) -> discord.Embed:
        session = self._session
        player = self._player()
        opponent = session.other_player(self._user_id)
        my_move = self._is_my_move()
        embed = discord.Embed(
            title="🃏 Club Poker -- ⏰ YOUR MOVE" if my_move else "🃏 Club Poker -- Private Hand",
            color=discord.Color.red() if my_move else PALETTE_GOLD,
        )
        hand_text = "  ".join(
            f"**[{card.label}]**" if player.held[idx] else card.label
            for idx, card in enumerate(player.hand)
        )
        lines = [f"**Your hand:**\n{hand_text}", f"**Pot:** {session.total_pot():,} {session.currency}", ""]
        hurry = (
            f"⏰ **The game is waiting on YOU. Hurry up and go!**\n"
            f"You have **{ACTION_SECONDS} seconds** per decision. Time runs out {session.deadline_text()}, "
            f"and if you don't act by then {session.timeout_penalty()}."
        )

        if session.phase == "draw":
            if player.draw_locked:
                lines.append(f"🔒 Your draw is locked in. Waiting on {opponent.member.mention} to lock theirs.")
                lines.append(f"They have until {session.deadline_text()} or their hand is folded.")
            else:
                held_count = sum(player.held)
                lines.append(hurry)
                lines.append("")
                lines.append(
                    f"Tap cards to **hold** them. Holding **{held_count}/5** card(s). "
                    "When ready, press **Lock Draw**."
                )
                lines.append(
                    f"{opponent.member.mention}: {'🔒 locked in' if opponent.draw_locked else 'still choosing'}"
                )
        elif session.phase == "betting":
            if self._user_id in session.auto_stayed:
                lines.append("⏰ You ran out of time, so you **Stayed** automatically.")
            replaced = session.replacement_count_for(self._user_id)
            lines.append(f"You drew **{replaced}** new card(s) from the cards you did not keep.")
            lines.append(f"**Your hand now:** *{CP_HAND_NAMES[evaluate_cp_hand(player.hand)]}*")
            lines.append("")
            if my_move:
                lines.append(hurry)
                lines.append("")
                if session.bet_open:
                    bettor = session.player_for(session.bettor_id).member.mention
                    lines.append(
                        f"{bettor} opened betting for **{session.ante:,} {session.currency}**. "
                        "Choose **Call** or **Fold**."
                    )
                else:
                    lines.append(
                        f"Choose **Stay** or open betting for **{session.ante:,} {session.currency}**."
                    )
            else:
                lines.append(f"⏳ Waiting on {opponent.member.mention} to act.")
                if session.bet_open:
                    lines.append(f"They have until {session.deadline_text()} or their hand is folded.")
                else:
                    lines.append(f"They have until {session.deadline_text()} or they Stay automatically.")
        elif session.phase == "muck_choice":
            lines.append(self._result_line())
            if self._user_id == session.loser_user_id and session.loser_visibility is None:
                lines.append("You may **Show Hand** or **Muck Hand**. If you do nothing for 15 seconds, your hand is mucked.")
        elif session.phase == "cancelled":
            reason = (session.result or {}).get("reason") or "The hand was cancelled."
            lines.append(f"❌ {reason} Every committed bet was refunded.")
        else:
            lines.append(self._result_line())
            lines.append("The hand is over. See the table message for both hands.")

        embed.description = "\n".join(lines)
        return embed

    def _result_line(self) -> str:
        result = self._session.result or {}
        outcome = result.get("outcome")
        if outcome == "tie":
            return "🤝 **Tie.** Your committed bets were returned."
        winner = result.get("winner")
        if winner is not None and winner.id == self._user_id:
            return f"🏆 **You won {result.get('total_payout', 0):,} {self._session.currency}** (+{result.get('net_profit', 0):,})."
        if self._session.timed_out_user_id == self._user_id:
            return "⏰ **You ran out of time and your hand was folded.**"
        if outcome == "fold":
            return "🚪 **You folded.** Your opponent takes the pot."
        return "❌ **You lost at showdown.**"

    def _run(self, action):
        """Wrap a session action as a button callback.

        The pressed panel becomes this player's live panel. Session actions redraw
        every live panel themselves; if the action redrew nothing (a hold toggle,
        a stale button) or failed, only this panel is redrawn."""

        async def callback(interaction: discord.Interaction) -> None:
            await safe_defer(interaction)
            session = self._session
            session.panels[self._user_id] = interaction
            async with session.lock:
                before = session.refresh_count
                error = await action()
                if error:
                    await interaction.followup.send(error, ephemeral=True)
                if error or session.refresh_count == before:
                    view = ClubPokerPrivateView(session, self._user_id)
                    await safe_edit_original_response(interaction, embed=view.build_embed(), view=view)

        return callback

    def _make_hold_callback(self, idx: int):
        async def toggle() -> None:
            if self._session.phase == "draw" and not self._player().draw_locked:
                self._player().held[idx] = not self._player().held[idx]

        return self._run(toggle)

    def _lock_draw(self):
        async def act() -> None:
            if self._session.phase == "draw" and not self._player().draw_locked:
                await self._session.lock_draw(self._user_id)

        return self._run(act)

    def _take_check(self):
        return self._run(lambda: self._session.take_check(self._user_id))

    def _open_bet(self):
        return self._run(lambda: self._session.open_bet(self._user_id))

    def _call_bet(self):
        return self._run(lambda: self._session.call_bet(self._user_id))

    def _fold_hand(self):
        return self._run(lambda: self._session.fold_hand(self._user_id))

    def _show_hand(self):
        return self._run(lambda: self._session.set_loser_visibility("show"))

    def _muck_hand(self):
        return self._run(lambda: self._session.set_loser_visibility("muck"))
