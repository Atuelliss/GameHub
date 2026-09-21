"""War — Pure game logic for HighRollerClub.

A card game where the player and house each draw one card from a virtual shoe.
Higher card wins. Aces are high. On a tie, an additional equal bet is placed
and both sides draw again (the War round).

Payout summary
--------------
Normal win : 1:1  — gross return = 2 × bet.
War win    : 2× total wagered — gross return = 4 × original bet.
Loss       : bet forfeited.
War loss   : both bets forfeited (2 × original bet).
Second tie : treated as a War win in the player's favour.

War is a card-math game (CARD_MATH_GAMES).  Win probability is determined by
deck math — there is no configurable RNG parameter.  get_game_rng() must NOT
be called for this slug.

This module contains no Discord UI — only cards, draw logic, and payouts.
"""

from __future__ import annotations

import random
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Card definitions
# ---------------------------------------------------------------------------

SUITS: tuple[str, ...] = ("♠", "♥", "♦", "♣")

_RANK_LABELS: dict[int, str] = {
    2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "10",
    11: "J", 12: "Q", 13: "K", 14: "A",
}

_ALL_RANKS: list[int] = list(_RANK_LABELS.keys())  # [2, 3, …, 14]


class Card(NamedTuple):
    rank: int  # 2–14; 14 = Ace (highest)
    suit: str  # "♠", "♥", "♦", "♣"

    @property
    def label(self) -> str:
        """Short display string, e.g. 'A♠' or '10♦'."""
        return f"{_RANK_LABELS[self.rank]}{self.suit}"

    def __str__(self) -> str:
        return self.label


# ---------------------------------------------------------------------------
# Card drawing
# ---------------------------------------------------------------------------

def draw_card() -> Card:
    """Draw one card from an effectively infinite mixed shoe.

    Rank probability is uniform across 2–14 (13 distinct values).
    Suits are decorative only — they have no effect on game outcome.
    """
    return Card(rank=random.choice(_ALL_RANKS), suit=random.choice(SUITS))


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare(player: Card, house: Card) -> str:
    """Return 'win', 'loss', or 'tie' from the player's perspective.

    Only card rank determines the result — suit is irrelevant.
    """
    if player.rank > house.rank:
        return "win"
    if player.rank < house.rank:
        return "loss"
    return "tie"


# ---------------------------------------------------------------------------
# Payout calculations
# ---------------------------------------------------------------------------

def normal_payout(bet: int) -> int:
    """Gross chips returned on a standard win (1:1).

    Example: bet=200 → returns 400. Net profit = 200.
    """
    return bet * 2


def war_payout(original_bet: int) -> int:
    """Gross chips returned on a War win (2× total wagered).

    Total wagered = original_bet + war_bet (= original_bet) = 2 × original_bet.
    Gross return  = 2 × total_wagered = 4 × original_bet.

    Example: original_bet=200 → total_wagered=400 → returns 800. Net profit = 400.
    """
    return original_bet * 4
