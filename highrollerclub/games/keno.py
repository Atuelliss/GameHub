from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Pool and draw constants
# ---------------------------------------------------------------------------

POOL_SIZE: int = 80
# Numbers run from 1 to POOL_SIZE inclusive.
# The paytable below is built for exactly DRAW_COUNT numbers per draw, so the
# draw size is fixed (changing it would swing the return far above or below 100%).
DRAW_COUNT: int = 20

MIN_PICKS: int = 1
MAX_PICKS: int = 10

# ---------------------------------------------------------------------------
# Payout table
# ---------------------------------------------------------------------------
# Indexed by (spots_picked, exact_hits) -> gross multiplier applied to the bet.
# A missing key or zero value means the player receives no return.
# Multipliers represent gross return INCLUDING the original bet:
#     payout = bet * multiplier
#
# Exact return to player per spot count (20 drawn from 80), worked out from
# the hypergeometric odds of each hit count:
#   1 spot: 90.0%   2 spots: 90.2%   3 spots: 91.6%   4 spots: 91.4%
#   5 spots: 90.5%  6 spots: 89.7%   7 spots: 92.4%   8 spots: 92.5%
#   9 spots: 91.8%  10 spots: 88.6%
# Re-check these numbers after any paytable change.

KENO_PAYTABLE: dict[int, dict[int, float]] = {
    1:  {1: 3.6},
    2:  {2: 15},
    3:  {2: 2,  3: 46},
    4:  {2: 1,  3: 7,  4: 130},
    5:  {3: 3,  4: 22, 5: 600},
    6:  {3: 1,  4: 9,  5: 90,  6: 1800},
    7:  {3: 1,  4: 3,  5: 22,  6: 350,  7: 6000},
    8:  {5: 15, 6: 140, 7: 1500, 8: 18000},
    9:  {4: 1,  5: 5,  6: 50,  7: 300,  8: 5000,  9: 20000},
    10: {5: 3,  6: 25, 7: 150, 8: 1200, 9: 6000, 10: 30000},
}


def draw_numbers(draw_count: int = DRAW_COUNT) -> frozenset[int]:
    """Draw draw_count unique numbers from 1-POOL_SIZE without replacement."""
    return frozenset(random.sample(range(1, POOL_SIZE + 1), draw_count))


def count_hits(player_picks: frozenset[int], drawn: frozenset[int]) -> int:
    """Return the number of player picks that appear in the drawn set."""
    return len(player_picks & drawn)


def calculate_payout(bet: int, spots: int, hits: int) -> int:
    """Return gross payout (original bet included) for the spot/hit combination.

    Returns 0 if hits is below the minimum paying threshold for the given
    spot count, or if spots is not in the paytable (should not occur in
    normal use since the view enforces MIN_PICKS <= spots <= MAX_PICKS).

    Examples:
        calculate_payout(100, 4, 3)  ->  700  (100 * 7x multiplier)
        calculate_payout(100, 4, 1)  ->  0    (1 hit on pick-4 pays nothing)
        calculate_payout(100, 1, 1)  ->  360  (100 * 3.6x multiplier)
    """
    multiplier = KENO_PAYTABLE.get(spots, {}).get(hits, 0)
    return int(bet * multiplier)
