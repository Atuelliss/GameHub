from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Pool and draw constants
# ---------------------------------------------------------------------------

POOL_SIZE: int = 80
# Numbers run from 1 to POOL_SIZE inclusive.
# draw_count is fetched at runtime via get_game_rng(conf, "keno", "draw_count")
# so the admin can tune it. DEFAULT_DRAW_COUNT is the fallback reference only.
DEFAULT_DRAW_COUNT: int = 20

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
# Approximate house edge per spot count (draw_count=20, pool=80):
#   1 spot:  ~25%    2 spots: ~29%    3 spots: ~31%    4 spots: ~27%
#   5 spots: ~25%    6 spots: ~33%    7 spots: ~29%    8 spots: ~33%
#   9 spots: ~29%   10 spots: ~35%

KENO_PAYTABLE: dict[int, dict[int, int]] = {
    1:  {1: 3},
    2:  {2: 12},
    3:  {2: 2,  3: 50},
    4:  {2: 1,  3: 5,  4: 100},
    5:  {3: 3,  4: 20, 5: 400},
    6:  {3: 2,  4: 8,  5: 75,  6: 1500},
    7:  {3: 2,  4: 6,  5: 40,  6: 400,  7: 7000},
    8:  {4: 10, 5: 30, 6: 200, 7: 2000, 8: 20000},
    9:  {4: 8,  5: 25, 6: 120, 7: 800,  8: 8000,  9: 30000},
    10: {4: 3,  5: 15, 6: 50,  7: 250,  8: 2500,  9: 15000, 10: 50000},
}


def draw_numbers(draw_count: int) -> frozenset[int]:
    """Draw draw_count unique numbers from 1-POOL_SIZE without replacement.

    draw_count must satisfy 1 <= draw_count <= POOL_SIZE.  Callers fetch the
    configured value from get_game_rng(conf, "keno", "draw_count") before
    calling this function.
    """
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
        calculate_payout(100, 4, 3)  ->  500  (100 * 5x multiplier)
        calculate_payout(100, 4, 1)  ->  0    (1 hit on pick-4 pays nothing)
        calculate_payout(100, 1, 1)  ->  300  (100 * 3x multiplier)
    """
    multiplier = KENO_PAYTABLE.get(spots, {}).get(hits, 0)
    return bet * multiplier
