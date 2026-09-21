"""Hi-Lo -- Pure game logic for HighRollerClub.

A press-your-luck card-guessing chain. The dealer reveals one card; the player
predicts whether the next card will be Higher or Lower in rank. A correct
prediction earns a multiplier and the player may continue chaining guesses or
cash out. A wrong prediction ends the game immediately with no payout.

Multiplier progression (gross payout, bet included)
----------------------------------------------------
  Chain depth 1 : 1.5x
  Chain depth 2 : 2.5x
  Chain depth 3 : 4.0x
  Chain depth 4 : 6.0x
  Chain depth 5 : 9.0x
  Chain depth 6+ : 13.0x  (soft cap; deepest multiplier offered)

Tie handling: equal-rank next cards are not dealt. If the remaining deck runs
out of playable cards, it is reshuffled before the next draw.

Probability: cards are drawn from a finite 52-card deck for each hand. The
next card is always drawn from the remaining deck excluding the current rank.
Suits are decorative.

Hi-Lo is in CARD_MATH_GAMES. Win probability is determined by deck math --
the rank distribution across the shoe. get_game_rng() must NOT be called for
this slug.

This module contains no Discord UI -- only cards, guess logic, and payouts.
"""

from __future__ import annotations

import random
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Card definitions  (mirrors games/war.py for consistency)
# ---------------------------------------------------------------------------

SUITS: tuple[str, ...] = ("♠", "♥", "♦", "♣")

_RANK_LABELS: dict[int, str] = {
    2: "2",  3: "3",  4: "4",  5: "5",  6: "6",
    7: "7",  8: "8",  9: "9",  10: "10",
    11: "J", 12: "Q", 13: "K", 14: "A",
}

_ALL_RANKS: list[int] = list(_RANK_LABELS.keys())  # [2, 3, ..., 14]


class Card(NamedTuple):
    rank: int  # 2-14; 14 = Ace (highest)
    suit: str  # decorative only

    @property
    def label(self) -> str:
        """Short display string, e.g. 'A♠' or '10♦'."""
        return f"{_RANK_LABELS[self.rank]}{self.suit}"

    def __str__(self) -> str:
        return self.label


# ---------------------------------------------------------------------------
# Chain multipliers
# ---------------------------------------------------------------------------

CHAIN_MULTIPLIERS: dict[int, float] = {
    1: 1.5,
    2: 2.5,
    3: 4.0,
    4: 6.0,
    5: 9.0,
}

# Depth 6 and beyond use the cap.
MAX_CHAIN_MULTIPLIER: float = 13.0
MAX_CHAIN_DEPTH: int = 6  # first depth that uses the cap


def chain_multiplier(depth: int) -> float:
    """Return the gross payout multiplier for the given chain depth.

    depth 1 = first correct guess. Depths 6 and above return MAX_CHAIN_MULTIPLIER.
    Depth 0 is invalid; callers should only call this when depth >= 1.
    """
    return CHAIN_MULTIPLIERS.get(depth, MAX_CHAIN_MULTIPLIER)


# ---------------------------------------------------------------------------
# Deck / card drawing
# ---------------------------------------------------------------------------

class Deck:
    """Standard 52-card deck, shuffled on construction.

    Each call to draw() removes one card from the deck.
    """

    def __init__(self) -> None:
        self._cards: list[Card] = []
        self.reset()

    def reset(self) -> None:
        cards = [Card(rank=rank, suit=suit) for rank in _ALL_RANKS for suit in SUITS]
        random.shuffle(cards)
        self._cards = cards

    def draw(self) -> Card:
        return self._cards.pop()

    def remaining(self) -> list[Card]:
        return list(self._cards)


def draw_card(deck: Deck) -> Card:
    """Draw one card from the supplied finite deck."""
    return deck.draw()


def draw_non_matching_card(deck: Deck, current_rank: int) -> tuple[Card, bool]:
    """Draw the next playable card, reshuffling if needed.

    Returns a tuple of (card, reshuffled). A reshuffle occurs when the current
    deck has no remaining card with a rank different from `current_rank`.
    """
    if not any(card.rank != current_rank for card in deck.remaining()):
        deck.reset()
        reshuffled = True
    else:
        reshuffled = False

    buffer: list[Card] = []
    while True:
        candidate = deck.draw()
        if candidate.rank != current_rank:
            while buffer:
                deck._cards.append(buffer.pop())
            return candidate, reshuffled
        buffer.append(candidate)


# ---------------------------------------------------------------------------
# Guess evaluation
# ---------------------------------------------------------------------------

def evaluate_guess(current: Card, next_card: Card, guess: str) -> str:
    """Evaluate a player's guess against the next drawn card.

    Args:
        current   : The card currently showing face-up.
        next_card : The newly drawn card.
        guess     : "higher" or "lower" (case-insensitive).

    Returns:
        "win"  -- the guess matched the outcome (strictly higher or strictly lower).
        "loss" -- the guess was wrong.
    """
    g = guess.lower()
    if next_card.rank > current.rank:
        return "win" if g == "higher" else "loss"
    if next_card.rank < current.rank:
        return "win" if g == "lower" else "loss"
    raise ValueError("Hi-Lo next card draw produced an equal rank, which should be impossible")


# ---------------------------------------------------------------------------
# Payout calculation
# ---------------------------------------------------------------------------

def calculate_payout(bet: int, depth: int) -> int:
    """Return the gross chips awarded for cashing out after `depth` correct guesses.

    Gross = int(bet * chain_multiplier(depth)).
    Net profit = gross - bet.
    depth must be >= 1; depth 0 is not a valid cash-out state.
    """
    return int(bet * chain_multiplier(depth))


# ---------------------------------------------------------------------------
# Probability hint helpers  (displayed in the UI for informed decision-making)
# ---------------------------------------------------------------------------

def higher_chance(current_rank: int, remaining_cards: list[Card]) -> float:
    """Fraction of playable remaining cards that are strictly higher than current_rank."""
    playable = [card for card in remaining_cards if card.rank != current_rank]
    if not playable:
        return 0.0
    higher = sum(1 for card in playable if card.rank > current_rank)
    return higher / len(playable)


def lower_chance(current_rank: int, remaining_cards: list[Card]) -> float:
    """Fraction of playable remaining cards that are strictly lower than current_rank."""
    playable = [card for card in remaining_cards if card.rank != current_rank]
    if not playable:
        return 0.0
    lower = sum(1 for card in playable if card.rank < current_rank)
    return lower / len(playable)
