"""Texas Hold'em -- pure game logic for HighRollerClub (no Discord UI).

The UI lives in views/holdem_view.py. This module plays exactly one hand of
No-Limit Texas Hold'em between 2 or more seated players and reports what
happened, so the table layer can move chips, record stats and award titles.

Standard rules implemented
--------------------------
- Dealer button, small blind, big blind. Heads-up (2 players): the button
  posts the small blind, acts first pre-flop and last after the flop.
- A blind a player can't cover is posted short, and that player is all-in.
- Streets: pre-flop, flop (3 cards), turn (1), river (1). No burn cards: with
  a computer-shuffled deck they change nothing.
- No-Limit betting. Minimum bet is one big blind; minimum raise is the size of
  the last full bet or raise on that street. Any amount up to the player's
  whole stack is allowed.
- An all-in for less than a full raise does not reopen betting for players who
  have already acted. Betting reopens for such a player once the total raised
  since their last action reaches a full raise (two short all-ins can add up).
- The big blind gets the option to raise when everyone just calls pre-flop.
- If fewer than two players can still bet, the rest of the board is dealt out
  with no more betting (an all-in run-out) and every live hand is shown.
- Side pots: each all-in level makes a pot only the players who covered it can
  win. A pot with one eligible player is an uncalled bet and goes back to them.
- Showdown: best 5 of 7 cards. Exact ties split the pot; the odd chip goes to
  the first winner left of the button.

Chips are conserved: what players committed is exactly what is paid back out.
No house money is involved.

Hand evaluation reuses the Club Poker evaluator in games/poker.py.

Texas Hold'em is a CARD_MATH_GAMES game. get_game_rng() must NOT be called for
the "holdem" slug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Sequence

from .poker import CP_HAND_NAMES, Card, Deck, _cp_showdown_key, evaluate_cp_hand

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BETTING_STREETS: tuple[str, ...] = ("preflop", "flop", "turn", "river")
STREET_CARDS: dict[str, int] = {"flop": 3, "turn": 1, "river": 1}

MIN_PLAYERS: int = 2
MAX_PLAYERS: int = 10  # the table layer limits seats further (HOLDEM_MAX_SEATS)

# Hands that count as a Bad Beat when they lose at showdown.
BAD_BEAT_RANKS: frozenset[str] = frozenset({"four_of_a_kind", "straight_flush", "royal_flush"})

ACTIONS: frozenset[str] = frozenset({"fold", "check", "call", "raise", "allin"})


class HoldemError(Exception):
    """Raised when an action is illegal (wrong player, wrong amount, wrong phase)."""


# ---------------------------------------------------------------------------
# Hand evaluation (best 5 of 5-7 cards)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BestHand:
    key: tuple                # sortable strength key from _cp_showdown_key
    cards: tuple[Card, ...]   # the five cards that make the hand
    rank: str                 # hand class slug, e.g. "full_house"

    @property
    def name(self) -> str:
        return CP_HAND_NAMES[self.rank]


def best_hand(cards: Sequence[Card]) -> BestHand:
    """Return the strongest 5-card hand that can be made from 5 to 7 cards."""
    if not 5 <= len(cards) <= 7:
        raise ValueError(f"best_hand needs 5 to 7 cards, got {len(cards)}")
    best: BestHand | None = None
    for combo in combinations(cards, 5):
        hand = list(combo)
        key = _cp_showdown_key(hand)
        if best is None or key > best.key:
            best = BestHand(key=key, cards=tuple(hand), rank=evaluate_cp_hand(hand))
    assert best is not None
    return best


# ---------------------------------------------------------------------------
# State objects
# ---------------------------------------------------------------------------

@dataclass
class HoldemSeat:
    user_id: int
    stack: int                       # chips behind (not yet committed)
    starting_stack: int
    hole: list[Card] = field(default_factory=list)
    street_bet: int = 0              # committed on the current street
    hand_total: int = 0              # committed this hand, all streets
    folded: bool = False
    all_in: bool = False
    acted: bool = False              # has made a voluntary action this street
    matched_at_action: int = 0       # street_bet right after this seat last acted

    @property
    def live(self) -> bool:
        """Still contesting the pot (not folded)."""
        return not self.folded

    @property
    def can_act(self) -> bool:
        """Still able to make betting decisions."""
        return not self.folded and not self.all_in


@dataclass(frozen=True)
class LegalActions:
    """What the player to act may do. Amounts for raises are raise-TO totals
    for the current street (what the player's street bet becomes)."""
    can_fold: bool
    can_check: bool
    can_call: bool
    call_amount: int     # chips the call adds (capped at the stack: an all-in call)
    can_raise: bool      # bet (no open bet) or raise
    is_bet: bool         # True when no bet is open on this street, so "raise" is a bet
    min_to: int          # smallest legal raise-to (equals max_to when only all-in is possible)
    max_to: int          # all-in raise-to (street_bet + stack)


@dataclass(frozen=True)
class PotResult:
    amount: int
    eligible: tuple[int, ...]     # user ids who could win it
    winners: tuple[int, ...]      # user ids who won it (one id for an uncalled return)
    shares: dict[int, int]        # chips each winner received from this pot

    @property
    def contested(self) -> bool:
        return len(self.eligible) >= 2


@dataclass
class HoldemResult:
    """Everything the table layer needs once the hand ends."""
    fold_win: bool                         # everyone else folded; no cards shown
    board: list[Card]
    pots: list[PotResult]                  # pots[0] is the main pot
    contributed: dict[int, int]            # chips each player put in this hand
    payouts: dict[int, int]                # chips each player gets back into their stack
    net: dict[int, int]                    # payout - contributed
    showdown_hands: dict[int, BestHand]    # live players at showdown (empty on a fold win)
    ran_out: bool                          # all-in run-out: every live hand is shown
    players_dealt_in: int
    big_blind: int
    # Title events (the table layer decides whether they count, e.g. 3+ players)
    main_pot_winners: tuple[int, ...]
    fold_winner: int | None
    allin_showdown_wins: frozenset[int]
    river_comebacks: frozenset[int]
    royal_flushes: frozenset[int]
    bad_beats: frozenset[int]
    pot_won_bb: dict[int, int]             # size of the pot(s) won, in big blinds (uncalled bets excluded)

    @property
    def winners(self) -> list[int]:
        return [uid for uid, n in self.net.items() if n > 0]

    @property
    def losers(self) -> list[int]:
        return [uid for uid, n in self.net.items() if n < 0]


# ---------------------------------------------------------------------------
# One hand of No-Limit Texas Hold'em
# ---------------------------------------------------------------------------

class HoldemHand:
    """Plays one hand. Create it with the seated players in clockwise order,
    then feed actions with act() until is_complete is True and read result.

    players : (user_id, stack) pairs in seat order. Every stack must be > 0.
    button  : index into players of the dealer button.
    deck    : optional pre-built Deck (tests stack the deck this way).
    """

    def __init__(
        self,
        players: Sequence[tuple[int, int]],
        button: int,
        small_blind: int,
        big_blind: int,
        deck: Deck | None = None,
    ) -> None:
        if not MIN_PLAYERS <= len(players) <= MAX_PLAYERS:
            raise HoldemError(f"a hand needs {MIN_PLAYERS}-{MAX_PLAYERS} players, got {len(players)}")
        if len({uid for uid, _ in players}) != len(players):
            raise HoldemError("duplicate player in hand")
        if any(stack <= 0 for _, stack in players):
            raise HoldemError("every player needs chips to be dealt in")
        if not 0 < small_blind <= big_blind:
            raise HoldemError("blinds must satisfy 0 < small blind <= big blind")
        if not 0 <= button < len(players):
            raise HoldemError("button index out of range")

        self.seats: list[HoldemSeat] = [
            HoldemSeat(user_id=uid, stack=stack, starting_stack=stack) for uid, stack in players
        ]
        self.n = len(self.seats)
        self.button = button
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.deck = deck if deck is not None else Deck()
        self.board: list[Card] = []
        self.street = "preflop"
        self.current_bet = 0
        self.last_raise_size = big_blind
        self.to_act: int | None = None          # seat index
        self.ran_out = False
        self.result: HoldemResult | None = None
        # (street, user_id, action, chips added, street bet after) -- for the UI log
        self.history: list[tuple[str, int, str, int, int]] = []

        if self.n == 2:
            self.sb_index = button
            self.bb_index = (button + 1) % self.n
        else:
            self.sb_index = (button + 1) % self.n
            self.bb_index = (button + 2) % self.n

        # Hole cards: one at a time around the table, starting left of the button.
        for _ in range(2):
            for offset in range(1, self.n + 1):
                self.seats[(button + offset) % self.n].hole.append(self.deck.draw())

        self._post(self.sb_index, small_blind, "small_blind")
        self._post(self.bb_index, big_blind, "big_blind")
        self.current_bet = big_blind
        self.last_raise_size = big_blind
        self.to_act = self._next_actor(self.bb_index)
        if self.to_act is None:
            self._end_street()

    # -- lookups ------------------------------------------------------------

    def index_of(self, user_id: int) -> int:
        for idx, seat in enumerate(self.seats):
            if seat.user_id == user_id:
                return idx
        raise HoldemError(f"player {user_id} is not in this hand")

    def seat_for(self, user_id: int) -> HoldemSeat:
        return self.seats[self.index_of(user_id)]

    @property
    def is_complete(self) -> bool:
        return self.result is not None

    @property
    def to_act_id(self) -> int | None:
        return None if self.to_act is None else self.seats[self.to_act].user_id

    @property
    def pot_total(self) -> int:
        return sum(seat.hand_total for seat in self.seats)

    def live_seats(self) -> list[HoldemSeat]:
        return [seat for seat in self.seats if seat.live]

    # -- betting ------------------------------------------------------------

    def _put(self, idx: int, amount: int) -> int:
        seat = self.seats[idx]
        amount = max(0, min(amount, seat.stack))
        seat.stack -= amount
        seat.street_bet += amount
        seat.hand_total += amount
        if seat.stack == 0:
            seat.all_in = True
        return amount

    def _post(self, idx: int, blind: int, label: str) -> None:
        added = self._put(idx, blind)
        self.history.append((self.street, self.seats[idx].user_id, label, added, self.seats[idx].street_bet))

    def _needs_action(self, seat: HoldemSeat) -> bool:
        return seat.can_act and (not seat.acted or seat.street_bet < self.current_bet)

    def _next_actor(self, from_idx: int) -> int | None:
        """Seat index of the next player who must act after from_idx, or None
        when the betting round is over."""
        if len(self.live_seats()) <= 1:
            return None
        actors = [seat for seat in self.seats if seat.can_act]
        if not actors:
            return None
        if len(actors) == 1 and actors[0].street_bet >= self.current_bet:
            return None  # nobody left to bet against
        for offset in range(1, self.n + 1):
            idx = (from_idx + offset) % self.n
            if self._needs_action(self.seats[idx]):
                return idx
        return None

    def legal_actions(self, user_id: int) -> LegalActions:
        if self.is_complete or self.to_act is None or self.seats[self.to_act].user_id != user_id:
            raise HoldemError("it isn't this player's turn")
        seat = self.seats[self.to_act]
        to_call = max(0, self.current_bet - seat.street_bet)
        max_to = seat.street_bet + seat.stack
        others_can_act = any(s.can_act for s in self.seats if s is not seat)
        reopened = (not seat.acted) or (self.current_bet - seat.matched_at_action >= self.last_raise_size)
        can_raise = others_can_act and reopened and max_to > self.current_bet
        min_to = min(self.current_bet + self.last_raise_size, max_to)
        return LegalActions(
            can_fold=True,
            can_check=to_call == 0,
            can_call=to_call > 0,
            call_amount=min(to_call, seat.stack),
            can_raise=can_raise,
            is_bet=self.current_bet == 0,
            min_to=min_to,
            max_to=max_to,
        )

    def default_action(self, user_id: int) -> str:
        """What a timed-out player does: check if possible, otherwise fold."""
        return "check" if self.legal_actions(user_id).can_check else "fold"

    def act(self, user_id: int, action: str, amount: int | None = None) -> None:
        """Apply one action for the player whose turn it is.

        action : "fold" | "check" | "call" | "raise" | "allin"
        amount : for "raise", the raise-TO total for this street.
        """
        if action not in ACTIONS:
            raise HoldemError(f"unknown action {action!r}")
        legal = self.legal_actions(user_id)
        idx = self.to_act
        assert idx is not None
        seat = self.seats[idx]

        if action == "allin":
            if legal.can_raise:
                action, amount = "raise", legal.max_to
            elif legal.can_call and legal.call_amount == seat.stack:
                action = "call"  # calling puts the player all-in
            else:
                raise HoldemError("all-in isn't available here; call, check or fold instead")

        if action == "fold":
            seat.folded = True
            self.history.append((self.street, user_id, "fold", 0, seat.street_bet))
        elif action == "check":
            if not legal.can_check:
                raise HoldemError("can't check facing a bet")
            self.history.append((self.street, user_id, "check", 0, seat.street_bet))
        elif action == "call":
            if not legal.can_call:
                raise HoldemError("nothing to call")
            added = self._put(idx, legal.call_amount)
            self.history.append((self.street, user_id, "call", added, seat.street_bet))
        else:  # raise / bet
            if not legal.can_raise:
                raise HoldemError("raising isn't allowed here")
            if amount is None:
                raise HoldemError("a raise needs an amount")
            if amount > legal.max_to:
                raise HoldemError("raise is more than the player's stack")
            if amount < legal.min_to:
                raise HoldemError(f"minimum raise is to {legal.min_to}")
            increment = amount - self.current_bet
            self._put(idx, amount - seat.street_bet)
            if increment >= self.last_raise_size:
                self.last_raise_size = increment  # a full raise
            self.current_bet = amount
            label = "bet" if legal.is_bet else "raise"
            if seat.all_in:
                label = "allin"
            self.history.append((self.street, user_id, label, amount, seat.street_bet))

        seat.acted = True
        seat.matched_at_action = seat.street_bet

        if len(self.live_seats()) == 1:
            self._finish()
            return
        self.to_act = self._next_actor(idx)
        if self.to_act is None:
            self._end_street()

    def fold_player(self, user_id: int) -> None:
        """Fold a player out of turn (they left the table or were removed)."""
        if self.is_complete:
            return
        idx = self.index_of(user_id)
        seat = self.seats[idx]
        if seat.folded:
            return
        if self.to_act == idx:
            self.act(user_id, "fold")
            return
        seat.folded = True
        self.history.append((self.street, user_id, "fold", 0, seat.street_bet))
        if len(self.live_seats()) == 1:
            self._finish()
            return
        # The same player keeps the turn if they still need to act; otherwise
        # move on (or close the round if nobody does).
        if self.to_act is not None:
            self.to_act = self._next_actor(self.to_act - 1)
        if self.to_act is None:
            self._end_street()

    # -- streets ------------------------------------------------------------

    def _end_street(self) -> None:
        """Close the betting round and deal on, running out the board if fewer
        than two players can still bet."""
        while True:
            if len(self.live_seats()) == 1:
                self._finish()
                return
            for seat in self.seats:
                seat.street_bet = 0
                seat.acted = False
                seat.matched_at_action = 0
            self.current_bet = 0
            self.last_raise_size = self.big_blind

            if self.street == "river":
                self._finish()
                return
            self.street = BETTING_STREETS[BETTING_STREETS.index(self.street) + 1]
            self.board.extend(self.deck.deal(STREET_CARDS[self.street]))

            if sum(1 for seat in self.seats if seat.can_act) < 2:
                self.ran_out = True
                continue  # no betting possible: deal the next street
            self.to_act = self._next_actor(self.button)
            if self.to_act is not None:
                return

    # -- settlement ---------------------------------------------------------

    def _build_pots(self) -> list[tuple[int, list[int]]]:
        """(amount, eligible seat indexes) for the main pot then each side pot."""
        live_levels = sorted({seat.hand_total for seat in self.seats if seat.live})
        pots: list[tuple[int, list[int]]] = []
        prev = 0
        for level in live_levels:
            amount = sum(min(s.hand_total, level) - min(s.hand_total, prev) for s in self.seats)
            eligible = [i for i, s in enumerate(self.seats) if s.live and s.hand_total >= level]
            if amount > 0:
                pots.append((amount, eligible))
            prev = level
        # A folded player can't have put in more than the top live level, but
        # never let chips go missing if they somehow did.
        leftover = sum(max(0, s.hand_total - prev) for s in self.seats)
        if leftover:
            amount, eligible = pots[-1]
            pots[-1] = (amount + leftover, eligible)
        return pots

    def _order_from_button(self, indexes: list[int]) -> list[int]:
        """Seat indexes sorted clockwise starting left of the button."""
        return sorted(indexes, key=lambda i: (i - self.button - 1) % self.n)

    def _finish(self) -> None:
        self.to_act = None
        live = [i for i, s in enumerate(self.seats) if s.live]
        contributed = {s.user_id: s.hand_total for s in self.seats}
        payouts = {s.user_id: 0 for s in self.seats}
        pot_results: list[PotResult] = []
        showdown: dict[int, BestHand] = {}
        fold_win = len(live) == 1

        if not fold_win:
            for i in live:
                showdown[self.seats[i].user_id] = best_hand(self.seats[i].hole + self.board)

        for amount, eligible in self._build_pots():
            if len(eligible) == 1 or fold_win:
                winner_idx = eligible[0] if not fold_win else live[0]
                uid = self.seats[winner_idx].user_id
                pot_results.append(PotResult(amount, tuple(self.seats[i].user_id for i in eligible), (uid,), {uid: amount}))
                payouts[uid] += amount
                continue
            best_key = max(showdown[self.seats[i].user_id].key for i in eligible)
            winners = self._order_from_button(
                [i for i in eligible if showdown[self.seats[i].user_id].key == best_key]
            )
            share, odd = divmod(amount, len(winners))
            shares: dict[int, int] = {}
            for pos, i in enumerate(winners):
                uid = self.seats[i].user_id
                shares[uid] = share + (1 if pos < odd else 0)
                payouts[uid] += shares[uid]
            pot_results.append(PotResult(
                amount,
                tuple(self.seats[i].user_id for i in eligible),
                tuple(self.seats[i].user_id for i in winners),
                shares,
            ))

        assert sum(payouts.values()) == sum(contributed.values()), "chips not conserved"
        net = {uid: payouts[uid] - contributed[uid] for uid in payouts}

        main = pot_results[0]
        main_winners = main.winners
        allin_wins: set[int] = set()
        comebacks: set[int] = set()
        royals: set[int] = set()
        bad_beats: set[int] = set()
        if not fold_win:
            turn_hands = {
                self.seats[i].user_id: best_hand(self.seats[i].hole + self.board[:4]) for i in live
            }
            for i in live:
                uid = self.seats[i].user_id
                won_main = uid in main_winners
                if won_main and self.seats[i].all_in:
                    allin_wins.add(uid)
                if won_main and any(
                    turn_hands[uid].key < turn_hands[other].key for other in turn_hands if other != uid
                ):
                    comebacks.add(uid)
                if showdown[uid].rank == "royal_flush":
                    royals.add(uid)
                if not won_main and showdown[uid].rank in BAD_BEAT_RANKS:
                    bad_beats.add(uid)

        # Monster Pot: the size of the pot(s) a player won, own chips included,
        # uncalled bets excluded. On a fold win that's everything except the
        # winner's uncalled excess.
        gross_won = {uid: 0 for uid in payouts}
        if fold_win:
            winner = self.seats[live[0]]
            others_max = max(s.hand_total for s in self.seats if s is not winner)
            gross_won[winner.user_id] = self.pot_total - max(0, winner.hand_total - others_max)
        else:
            for pot in pot_results:
                if pot.contested:
                    for uid, chips in pot.shares.items():
                        gross_won[uid] += chips
        pot_won_bb = {uid: chips // self.big_blind for uid, chips in gross_won.items()}

        for seat in self.seats:
            seat.stack += payouts[seat.user_id]
        self.street = "complete"
        self.result = HoldemResult(
            fold_win=fold_win,
            board=list(self.board),
            pots=pot_results,
            contributed=contributed,
            payouts=payouts,
            net=net,
            showdown_hands=showdown,
            ran_out=self.ran_out and not fold_win,
            players_dealt_in=self.n,
            big_blind=self.big_blind,
            main_pot_winners=main_winners,
            fold_winner=self.seats[live[0]].user_id if fold_win else None,
            allin_showdown_wins=frozenset(allin_wins),
            river_comebacks=frozenset(comebacks),
            royal_flushes=frozenset(royals),
            bad_beats=frozenset(bad_beats),
            pot_won_bb=pot_won_bb,
        )

    def final_stacks(self) -> dict[int, int]:
        """Each player's stack after the hand (only meaningful once complete)."""
        return {seat.user_id: seat.stack for seat in self.seats}
