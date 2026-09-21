"""Poker -- Shared game logic for Video Poker and Club Poker in HighRollerClub.

This module contains:
  - Standard 52-card deck infrastructure (Card, Deck)
  - Video Poker hand evaluator (Jacks or Better paytable)
  - Video Poker payout table and calculate_vp_payout()
  - (Club Poker logic appended when implemented)

Card rank convention (matches games/blackjack.py)
--------------------------------------------------
  rank 1  = Ace
  rank 2-10 = pip value
  rank 11 = Jack
  rank 12 = Queen
  rank 13 = King

Ace is treated as both low (rank 1) and high (above King) for straight
detection only. For pair/set evaluation it is simply rank 1.

Video Poker -- Jacks or Better, 9/6 paytable
---------------------------------------------
Hand ranks (strongest first):
  royal_flush      -- A K Q J 10 of the same suit
  straight_flush   -- five sequential cards of the same suit (not royal)
  four_of_a_kind   -- four cards of the same rank
  full_house       -- three of one rank + two of another
  flush            -- five cards of the same suit (not sequential)
  straight         -- five sequential cards (not same suit)
  three_of_a_kind  -- three cards of the same rank
  two_pair         -- two distinct pairs
  jacks_or_better  -- a pair of Jacks, Queens, Kings, or Aces
  nothing          -- no qualifying hand (loss)

Payout convention (GROSS -- profit + returned stake)
------------------------------------------------------
  calculate_vp_payout(bet, hand_rank) = bet * VP_PAYTABLE[hand_rank]
  Loss (nothing) returns 0. The caller is responsible for not calling
  credit_balance when payout == 0.

Video Poker is a CARD_MATH_GAMES game. get_game_rng() must NOT be called
for the "videopoker" slug. The full 52-card deck is dealt and drawn from
each session -- not an infinite shoe.

This module contains no Discord UI.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Card definitions
# ---------------------------------------------------------------------------

SUITS: tuple[str, ...] = ("♠", "♥", "♦", "♣")

_RANK_LABELS: dict[int, str] = {
    1: "A", 2: "2", 3: "3", 4: "4", 5: "5", 6: "6",
    7: "7", 8: "8", 9: "9", 10: "10",
    11: "J", 12: "Q", 13: "K",
}

_ALL_RANKS: list[int] = list(_RANK_LABELS.keys())  # [1, 2, ..., 13]


class Card(NamedTuple):
    rank: int  # 1=Ace, 2-10=pip, 11=J, 12=Q, 13=K
    suit: str

    @property
    def label(self) -> str:
        return f"{_RANK_LABELS[self.rank]}{self.suit}"

    def __str__(self) -> str:
        return self.label


# ---------------------------------------------------------------------------
# Deck
# ---------------------------------------------------------------------------

class Deck:
    """Standard 52-card deck, shuffled on construction.

    Each call to draw() pops one card from the top. Cards are not replaced.
    Used for Video Poker (and later Club Poker) where per-session depletion
    tracking is required.
    """

    def __init__(self) -> None:
        cards: list[Card] = [Card(r, s) for r in _ALL_RANKS for s in SUITS]
        random.shuffle(cards)
        self._cards: list[Card] = cards

    def draw(self) -> Card:
        """Pop and return the top card. Raises IndexError if deck is empty."""
        return self._cards.pop()

    def deal(self, n: int) -> list[Card]:
        """Draw n cards and return them as a list."""
        return [self.draw() for _ in range(n)]

    def remaining(self) -> int:
        return len(self._cards)


# ---------------------------------------------------------------------------
# Video Poker -- Jacks or Better paytable
# ---------------------------------------------------------------------------

# Gross multipliers (includes returned stake).
# Net ratio = value - 1 (e.g. royal_flush nets 800x the bet).
VP_PAYTABLE: dict[str, int] = {
    "royal_flush":     801,
    "straight_flush":   51,
    "four_of_a_kind":   26,
    "full_house":       10,
    "flush":             7,
    "straight":          5,
    "three_of_a_kind":   4,
    "two_pair":          3,
    "jacks_or_better":   2,
    "nothing":           0,
}

# Display names for each hand rank (used in result embeds).
VP_HAND_NAMES: dict[str, str] = {
    "royal_flush":     "💎 Royal Flush",
    "straight_flush":  "🌟 Straight Flush",
    "four_of_a_kind":  "4️⃣ Four of a Kind",
    "full_house":      "🏠 Full House",
    "flush":           "♦ Flush",
    "straight":        "➡ Straight",
    "three_of_a_kind": "3️⃣ Three of a Kind",
    "two_pair":        "✌ Two Pair",
    "jacks_or_better": "🃏 Jacks or Better",
    "nothing":         "❌ No Win",
}


# ---------------------------------------------------------------------------
# Hand evaluator
# ---------------------------------------------------------------------------

def evaluate_hand(hand: list[Card]) -> str:
    """Evaluate a 5-card hand and return its Jacks or Better rank string.

    Returns one of the keys in VP_PAYTABLE / VP_HAND_NAMES.
    hand must contain exactly 5 Card objects.
    """
    if len(hand) != 5:
        raise ValueError(f"evaluate_hand requires exactly 5 cards, got {len(hand)}")

    ranks = sorted(c.rank for c in hand)
    suits = [c.suit for c in hand]
    counts: Counter = Counter(ranks)
    freq = sorted(counts.values(), reverse=True)

    is_flush = len(set(suits)) == 1

    # Straight detection:
    # - Normal: 5 distinct consecutive ranks with span of 4 (e.g. 2-6)
    # - Ace-high: [1, 10, 11, 12, 13] -- special case; span would be 12
    is_straight = False
    if len(counts) == 5:  # all five ranks distinct
        if ranks[-1] - ranks[0] == 4:
            is_straight = True
        elif ranks == [1, 10, 11, 12, 13]:
            # A-K-Q-J-10 straight (ace plays high)
            is_straight = True

    # ----------------------------------------------------------------
    # Evaluation order: strongest hand first
    # ----------------------------------------------------------------

    # Royal Flush -- A-K-Q-J-10 same suit
    if is_flush and ranks == [1, 10, 11, 12, 13]:
        return "royal_flush"

    # Straight Flush -- sequential same suit (not royal)
    if is_flush and is_straight:
        return "straight_flush"

    # Four of a Kind
    if freq[0] == 4:
        return "four_of_a_kind"

    # Full House -- [3, 2]
    if freq[:2] == [3, 2]:
        return "full_house"

    # Flush -- same suit, not straight
    if is_flush:
        return "flush"

    # Straight -- sequential, not same suit
    if is_straight:
        return "straight"

    # Three of a Kind
    if freq[0] == 3:
        return "three_of_a_kind"

    # Two Pair -- [2, 2, 1]
    if freq[:2] == [2, 2]:
        return "two_pair"

    # Jacks or Better -- a pair of J(11), Q(12), K(13), or A(1)
    if freq[0] == 2:
        paired_rank = next(r for r, c in counts.items() if c == 2)
        if paired_rank in (1, 11, 12, 13):
            return "jacks_or_better"

    return "nothing"


# ---------------------------------------------------------------------------
# Payout helper
# ---------------------------------------------------------------------------

def calculate_vp_payout(bet: int, hand_rank: str) -> int:
    """Return the GROSS payout (profit + returned stake) for the given hand.

    Returns 0 for "nothing" (loss -- bet is not returned).
    """
    multiplier = VP_PAYTABLE.get(hand_rank, 0)
    return bet * multiplier


# ===========================================================================
# Club Poker -- Casino-Style Ante & Play vs House Dealer
# ===========================================================================
#
# Game flow:
#   1. Player places an ante bet.
#   2. Both player and dealer receive 5 cards; dealer's are hidden.
#   3. Player decides: PLAY (places an equal play bet) or FOLD (loses ante).
#   4. Dealer's hand is revealed.
#   5. Payout:
#      - Fold:  player loses ante only.
#      - Play + dealer does not qualify (pair or better):
#          ante pays 1:1, play bet pushes (returned).
#      - Play + dealer qualifies + player wins: ante 1:1 + play 1:1.
#      - Play + dealer qualifies + tie: both ante and play push.
#      - Play + dealer qualifies + dealer wins: both ante and play lost.
#      - Ante Bonus: paid on the player's hand regardless of outcome or fold
#          (see CP_ANTE_BONUS below). Not paid on fold.
#
# Club Poker is a CARD_MATH_GAMES game. get_game_rng() must NOT be called
# for the "clubpoker" slug.
# ===========================================================================

# Hand rank ordering (index 0 = strongest).
# Unlike Video Poker, ALL pairs qualify -- not just J+.
CP_HAND_RANKS: list[str] = [
    "royal_flush",
    "straight_flush",
    "four_of_a_kind",
    "full_house",
    "flush",
    "straight",
    "three_of_a_kind",
    "two_pair",
    "pair",
    "high_card",
]

CP_HAND_NAMES: dict[str, str] = {
    "royal_flush":     "💎 Royal Flush",
    "straight_flush":  "🌟 Straight Flush",
    "four_of_a_kind":  "4️⃣ Four of a Kind",
    "full_house":      "🏠 Full House",
    "flush":           "♦ Flush",
    "straight":        "➡ Straight",
    "three_of_a_kind": "3️⃣ Three of a Kind",
    "two_pair":        "✌ Two Pair",
    "pair":            "🃏 Pair",
    "high_card":       "📋 High Card",
}



def evaluate_cp_hand(hand: list[Card]) -> str:
    """Evaluate a 5-card hand for Club Poker (all pairs qualify, not just J+).

    Returns one of the keys in CP_HAND_NAMES.
    hand must contain exactly 5 Card objects.
    """
    if len(hand) != 5:
        raise ValueError(f"evaluate_cp_hand requires exactly 5 cards, got {len(hand)}")

    ranks = sorted(c.rank for c in hand)
    suits = [c.suit for c in hand]
    counts: Counter = Counter(ranks)
    freq = sorted(counts.values(), reverse=True)

    is_flush = len(set(suits)) == 1

    is_straight = False
    if len(counts) == 5:
        if ranks[-1] - ranks[0] == 4:
            is_straight = True
        elif ranks == [1, 10, 11, 12, 13]:
            is_straight = True

    if is_flush and ranks == [1, 10, 11, 12, 13]:
        return "royal_flush"

    if is_flush and is_straight:
        return "straight_flush"

    if freq[0] == 4:
        return "four_of_a_kind"

    if freq[:2] == [3, 2]:
        return "full_house"

    if is_flush:
        return "flush"

    if is_straight:
        return "straight"

    if freq[0] == 3:
        return "three_of_a_kind"

    if freq[:2] == [2, 2]:
        return "two_pair"

    if freq[0] == 2:
        return "pair"

    return "high_card"



def compare_cp_hands(rank1: str, rank2: str) -> int:
    """Compare two Club Poker hand ranks.

    Returns:
        1  if rank1 is stronger than rank2
       -1  if rank1 is weaker than rank2
        0  if they are the same rank
    """
    idx1 = CP_HAND_RANKS.index(rank1)
    idx2 = CP_HAND_RANKS.index(rank2)
    if idx1 < idx2:
        return 1   # lower index = stronger hand
    if idx1 > idx2:
        return -1
    return 0


def _cp_rank_value(rank: int) -> int:
    """Return the comparison rank value for Club Poker showdown logic."""
    return 14 if rank == 1 else rank


def _cp_straight_high(raw_ranks: list[int]) -> int:
    """Return the high card of a straight using the evaluator's conventions."""
    ranks = sorted(raw_ranks)
    if ranks == [1, 10, 11, 12, 13]:
        return 14
    return _cp_rank_value(ranks[-1])


def _cp_showdown_key(hand: list[Card]) -> tuple[int, tuple[int, ...]]:
    """Return a sortable showdown key for Club Poker hands.

    The first tuple item is the hand class strength. The second item contains
    tie-break ranks in descending comparison order.
    """
    hand_rank = evaluate_cp_hand(hand)
    category_strength = len(CP_HAND_RANKS) - CP_HAND_RANKS.index(hand_rank)

    raw_ranks = [c.rank for c in hand]
    normalized = [_cp_rank_value(rank) for rank in raw_ranks]
    counts: Counter = Counter(normalized)

    if hand_rank == "royal_flush":
        return category_strength, (14,)

    if hand_rank in {"straight_flush", "straight"}:
        return category_strength, (_cp_straight_high(raw_ranks),)

    if hand_rank == "four_of_a_kind":
        quad_rank = max(rank for rank, count in counts.items() if count == 4)
        kicker = max(rank for rank, count in counts.items() if count == 1)
        return category_strength, (quad_rank, kicker)

    if hand_rank == "full_house":
        triple_rank = max(rank for rank, count in counts.items() if count == 3)
        pair_rank = max(rank for rank, count in counts.items() if count == 2)
        return category_strength, (triple_rank, pair_rank)

    if hand_rank == "flush":
        return category_strength, tuple(sorted(normalized, reverse=True))

    if hand_rank == "three_of_a_kind":
        triple_rank = max(rank for rank, count in counts.items() if count == 3)
        kickers = sorted((rank for rank, count in counts.items() if count == 1), reverse=True)
        return category_strength, (triple_rank, *kickers)

    if hand_rank == "two_pair":
        pair_ranks = sorted((rank for rank, count in counts.items() if count == 2), reverse=True)
        kicker = max(rank for rank, count in counts.items() if count == 1)
        return category_strength, (*pair_ranks, kicker)

    if hand_rank == "pair":
        pair_rank = max(rank for rank, count in counts.items() if count == 2)
        kickers = sorted((rank for rank, count in counts.items() if count == 1), reverse=True)
        return category_strength, (pair_rank, *kickers)

    return category_strength, tuple(sorted(normalized, reverse=True))


def compare_cp_showdown(hand1: list[Card], hand2: list[Card]) -> int:
    """Compare two Club Poker hands including tie-break kickers.

    Returns:
        1  if hand1 is stronger than hand2
       -1  if hand1 is weaker than hand2
        0  if both hands are exactly tied
    """
    key1 = _cp_showdown_key(hand1)
    key2 = _cp_showdown_key(hand2)
    if key1 > key2:
        return 1
    if key1 < key2:
        return -1
    return 0



