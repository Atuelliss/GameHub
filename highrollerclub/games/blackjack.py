"""Blackjack — Pure game logic for HighRollerClub.

Standard casino Blackjack rules:
    - Finite 52-card deck per hand (cards are not replaced during the round).
  - Face cards (J, Q, K) worth 10; Ace worth 1 or 11 (soft hand logic).
  - Dealer stands on hard 17+; hits on soft 16 or lower.
  - Blackjack (Ace + 10-value on the initial two-card deal) pays 3:2.
  - Player can Double Down: bet doubled, exactly one more card drawn, then stand.
  - Player can Split: only when initial two cards share the same rank.
    Split creates two independent hands, each with one additional card drawn.
    Each hand is then played separately (Hit / Stand only — no re-split, no
    Double after Split, no Blackjack on split aces).
  - Push (tie) returns the original bet with no profit or loss.

Payout table
------------
  Blackjack (natural)  : 3:2  — gross = bet + int(bet * 1.5)
  Normal win           : 1:1  — gross = bet * 2
  Push                 : bet returned (net 0)
  Loss / bust          : bet forfeited

  Double Down win      : 1:1 on doubled bet  — gross = (bet * 2) * 2
  Double Down push     : doubled bet returned
  Double Down loss     : doubled bet forfeited

  Split: each hand is independent. Win/loss/push applies per hand.

Blackjack is a CARD_MATH_GAMES game — win probability is determined by deck
math. get_game_rng() must NOT be called for this slug.

This module contains no Discord UI — only cards, hand logic, and payouts.
"""

from __future__ import annotations

import random
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Card definitions
# ---------------------------------------------------------------------------

SUITS: tuple[str, ...] = ("♠", "♥", "♦", "♣")

# rank: 1=Ace, 2-10=pip, 11=J, 12=Q, 13=K
_RANK_LABELS: dict[int, str] = {
    1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "10",
    11: "J", 12: "Q", 13: "K",
}

_ALL_RANKS: list[int] = list(_RANK_LABELS.keys())  # 1–13


class Card(NamedTuple):
    rank: int  # 1 = Ace, 2–10 pip, 11 = J, 12 = Q, 13 = K
    suit: str

    @property
    def label(self) -> str:
        return f"{_RANK_LABELS[self.rank]}{self.suit}"

    @property
    def point_value(self) -> int:
        """Returns the base point value. Aces return 11; soft-hand reduction
        is handled by hand_value()."""
        if self.rank == 1:
            return 11   # Ace — hand_value() reduces to 1 when needed
        return min(self.rank, 10)  # J/Q/K → 10

    def __str__(self) -> str:
        return self.label


# ---------------------------------------------------------------------------
# Deck / card drawing
# ---------------------------------------------------------------------------

class Deck:
    """Standard 52-card deck, shuffled on construction.

    Each call to draw() removes one card from the deck.
    """

    def __init__(self) -> None:
        cards = [Card(rank=rank, suit=suit) for rank in _ALL_RANKS for suit in SUITS]
        random.shuffle(cards)
        self._cards: list[Card] = cards

    def draw(self) -> Card:
        """Pop and return the top card. Raises IndexError if the deck is empty."""
        return self._cards.pop()


def draw_card(deck: Deck) -> Card:
    """Draw one card from the supplied deck."""
    return deck.draw()


def draw_hand(deck: Deck) -> list[Card]:
    """Deal an initial two-card hand from the supplied deck."""
    return [draw_card(deck), draw_card(deck)]


# ---------------------------------------------------------------------------
# Hand evaluation
# ---------------------------------------------------------------------------

def hand_value(hand: list[Card]) -> int:
    """Return the best (highest non-bust) total for a hand.

    Aces initially count as 11. If the total exceeds 21, each Ace is
    reduced to 1 until the total is ≤ 21 or no Aces remain.
    """
    total = sum(c.point_value for c in hand)
    aces = sum(1 for c in hand if c.rank == 1)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_bust(hand: list[Card]) -> bool:
    return hand_value(hand) > 21


def is_blackjack(hand: list[Card]) -> bool:
    """True only for a natural blackjack: exactly 2 cards totalling 21."""
    return len(hand) == 2 and hand_value(hand) == 21


def is_soft(hand: list[Card]) -> bool:
    """True if the hand contains an Ace counted as 11 (soft hand)."""
    total = sum(c.point_value for c in hand)
    aces = sum(1 for c in hand if c.rank == 1)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    # If any ace is still contributing 11, the hand is soft.
    return aces > 0


def can_split(hand: list[Card]) -> bool:
    """True when the initial two cards share the same rank (pair)."""
    return len(hand) == 2 and hand[0].rank == hand[1].rank


def hand_label(hand: list[Card]) -> str:
    """Space-separated card labels for display, e.g. 'A♠ 10♦ 7♣'."""
    return "  ".join(c.label for c in hand)


# ---------------------------------------------------------------------------
# Dealer play
# ---------------------------------------------------------------------------

def dealer_play(dealer_hand: list[Card], deck: Deck) -> list[Card]:
    """Run the dealer's turn to completion using house rules.

    Dealer stands on hard 17+ and hits on soft 16 or lower.
    Returns the completed dealer hand (may include additional drawn cards).
    The list is mutated in-place and also returned for convenience.
    """
    while True:
        total = hand_value(dealer_hand)
        if total > 17:
            break
        if total == 17 and not is_soft(dealer_hand):
            break
        dealer_hand.append(draw_card(deck))
    return dealer_hand


# ---------------------------------------------------------------------------
# Outcome evaluation
# ---------------------------------------------------------------------------

def compare_hands(player_val: int, dealer_val: int, dealer_bust: bool) -> str:
    """Return 'win', 'loss', or 'push' from the player's perspective.

    dealer_bust is passed separately so the caller does not need to re-check it.
    player_val must already be the best non-bust value (caller validates bust).
    """
    if dealer_bust:
        return "win"
    if player_val > dealer_val:
        return "win"
    if player_val < dealer_val:
        return "loss"
    return "push"


# ---------------------------------------------------------------------------
# Payout calculations
# ---------------------------------------------------------------------------

def blackjack_payout(bet: int) -> int:
    """Gross return for a natural blackjack: bet + int(bet * 1.5).

    Example: bet=100 → returns 250 (profit 150).
    """
    return bet + int(bet * 1.5)


def win_payout(bet: int) -> int:
    """Gross return for a standard win: 2 × bet.

    Example: bet=100 → returns 200 (profit 100).
    """
    return bet * 2


def double_down_payout(bet: int) -> int:
    """Gross return for a Double Down win: 2 × doubled bet = 4 × original bet.

    Total deducted from player = 2 × bet (original + double bet).
    Gross return = 4 × original bet → net profit = 2 × original bet.
    """
    return bet * 4
