"""Big Six Wheel -- pure game logic (no Discord UI).

Wheel composition
-----------------
The wheel has a fixed set of non-house segment counts plus an admin-configurable
number of house (loss) segments.

  Fixed segments (total 46):
    $1     -- 18 segments
    $2     -- 12 segments
    $5     --  7 segments
    $10    --  5 segments
    $20    --  3 segments
    jackpot --  1 segment

  House segments: default 8, configurable 6-12.
  Total wheel size = house_count + 46.

Payout convention
-----------------
BIG6_PAYOUTS stores the net profit ratio (the X in "X to 1"):
  $1      pays 1:1  (even money)
  $2      pays 2:1
  $5      pays 5:1
  $10     pays 10:1
  $20     pays 20:1
  jackpot pays 40:1

calculate_payout() returns the GROSS amount (profit + returned stake):
  gross = bet * (BIG6_PAYOUTS[segment] + 1)

Caller flow
-----------
1. build_wheel(house_count) -- build the weighted list from conf.big6_house_segments
2. spin_wheel(wheel)        -- pick a random segment label
3. is_house_segment(label)  -- True if result is a loss
4. calculate_payout(bet, segment) -- gross payout on a player win
"""

from __future__ import annotations

import random

from ..common.constants import BIG6_DEFAULT_SEGMENTS, BIG6_PAYOUTS

# Labels the player can bet on (all non-house segment labels, in display order).
PLAYER_SEGMENTS: list[str] = ["$1", "$2", "$5", "$10", "$20", "jackpot"]

# Display labels used in embeds (jackpot gets a fancier name).
SEGMENT_DISPLAY: dict[str, str] = {
    "$1":      "$1",
    "$2":      "$2",
    "$5":      "$5",
    "$10":     "$10",
    "$20":     "$20",
    "jackpot": "🏆 Jackpot",
}

# Emoji per segment for embed flavor.
SEGMENT_EMOJI: dict[str, str] = {
    "$1":      "🟢",
    "$2":      "🔵",
    "$5":      "🟡",
    "$10":     "🟠",
    "$20":     "🔴",
    "jackpot": "💎",
    "house":   "🏠",
}


def build_wheel(house_count: int) -> list[str]:
    """Return the full weighted list of segment labels for this spin.

    Each label appears as many times as its segment count, giving an accurate
    probability distribution when sampling a single element uniformly.

    house_count is from conf.big6_house_segments (default 8, range 6-12).
    """
    wheel: list[str] = []
    for label, count in BIG6_DEFAULT_SEGMENTS.items():
        if label == "house":
            wheel.extend(["house"] * house_count)
        else:
            wheel.extend([label] * count)
    return wheel


def spin_wheel(wheel: list[str]) -> str:
    """Pick one segment at random from the weighted wheel list."""
    return random.choice(wheel)


def is_house_segment(result: str) -> bool:
    """Return True if the result is a house (loss) segment."""
    return result == "house"


def win_probability(segment: str, house_count: int) -> float:
    """Return the probability (0.0-1.0) of landing on the given player segment."""
    total = house_count + 46  # 46 fixed non-house segments
    count = BIG6_DEFAULT_SEGMENTS.get(segment, 0)
    return count / total if total > 0 else 0.0


def calculate_payout(bet: int, segment: str) -> int:
    """Return the GROSS payout (profit + returned stake) for a win on segment.

    gross = bet * (net_ratio + 1)
    where net_ratio = BIG6_PAYOUTS[segment] (the X in X:1 payout).
    """
    net_ratio = BIG6_PAYOUTS[segment]
    return bet * (net_ratio + 1)
