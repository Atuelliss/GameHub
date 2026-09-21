from __future__ import annotations

import random

# ---------------------------------------------------------------------------
# Table layout constants
# ---------------------------------------------------------------------------

# Red numbers on a standard roulette wheel.
RED_NUMBERS: frozenset[int] = frozenset({
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36,
})

# Three vertical columns of the 3-column board layout.
COLUMNS: dict[int, frozenset[int]] = {
    1: frozenset(range(1, 37, 3)),   # 1,4,7,10,13,16,19,22,25,28,31,34
    2: frozenset(range(2, 37, 3)),   # 2,5,8,11,14,17,20,23,26,29,32,35
    3: frozenset(range(3, 37, 3)),   # 3,6,9,12,15,18,21,24,27,30,33,36
}

# Valid starting numbers for each inside-bet type.
STREET_STARTS: frozenset[int] = frozenset(range(1, 35, 3))   # 1,4,7,...,34
LINE_STARTS: frozenset[int] = frozenset(range(1, 32, 3))      # 1,4,7,...,31
# Corner: top-left of a 2x2 block -- must not be in column 3 (n%3 != 0),
# and must have a row below it (n <= 33).
CORNER_STARTS: frozenset[int] = frozenset(
    n for n in range(1, 34) if n % 3 != 0
)

# ---------------------------------------------------------------------------
# Payout table
# ---------------------------------------------------------------------------
# Gross multipliers (bet * multiplier = total returned, including stake).
# Net profit = payout - bet.
PAYOUTS: dict[str, int] = {
    "straight":  36,   # 35:1 net
    "split":     18,   # 17:1 net
    "street":    12,   # 11:1 net
    "corner":     9,   #  8:1 net
    "line":       6,   #  5:1 net
    "column":     3,   #  2:1 net
    "dozen":      3,   #  2:1 net
    "evenmoney":  2,   #  1:1 net
}

# ---------------------------------------------------------------------------
# Wheel spin
# ---------------------------------------------------------------------------

def spin(zero_count: int) -> str:
    """Spin the wheel and return the winning slot as a display string.

    zero_count is fetched via get_game_rng(conf, "roulette", "zero_count"):
        0 -> European  (single 0; 37 slots total)
        1 -> American  (0 + 00;   38 slots total)  [default]
        2 -> Triple    (0 + 00 + 000; 39 slots total)

    Returns: "0", "00", "000", or a string digit "1"-"36".
    """
    wheel: list[str] = [str(n) for n in range(37)]  # "0" through "36"
    if zero_count >= 1:
        wheel.append("00")
    if zero_count >= 2:
        wheel.append("000")
    return random.choice(wheel)


def is_zero_slot(result: str) -> bool:
    """Return True if the result landed on a zero/house slot."""
    return result in ("0", "00", "000")


def result_color(result: str) -> str:
    """Return 'red', 'black', or 'green' for display purposes."""
    if is_zero_slot(result):
        return "green"
    return "red" if int(result) in RED_NUMBERS else "black"


# ---------------------------------------------------------------------------
# Input validation helpers (used by the view's TargetModal)
# ---------------------------------------------------------------------------

def is_valid_split(a: int, b: int) -> bool:
    """Return True if a and b are horizontally or vertically adjacent.

    Horizontal: same row (same (n-1)//3 group), consecutive integers.
    Vertical:   same column, differ by exactly 3.
    Both numbers must be in range 1-36.
    """
    if not (1 <= a <= 36 and 1 <= b <= 36) or a == b:
        return False
    lo, hi = min(a, b), max(a, b)
    # Horizontal: same row, differ by 1
    if hi - lo == 1 and (lo - 1) // 3 == (hi - 1) // 3:
        return True
    # Vertical: same column, differ by 3
    if hi - lo == 3:
        return True
    return False


# ---------------------------------------------------------------------------
# Hit-detection helpers
# ---------------------------------------------------------------------------

def hits_straight(result: str, number: int) -> bool:
    """Win if the result matches the chosen number (0-36).
    00 and 000 are never valid straight-up targets.
    """
    if result in ("00", "000"):
        return False
    return int(result) == number


def hits_split(result: str, a: int, b: int) -> bool:
    if is_zero_slot(result):
        return False
    return int(result) in (a, b)


def hits_street(result: str, start: int) -> bool:
    """Win if result is in the 3-number row [start, start+2]."""
    if is_zero_slot(result):
        return False
    return start <= int(result) <= start + 2


def hits_corner(result: str, top_left: int) -> bool:
    """Win if result is one of the four numbers in the 2x2 block."""
    if is_zero_slot(result):
        return False
    n = int(result)
    return n in (top_left, top_left + 1, top_left + 3, top_left + 4)


def hits_line(result: str, start: int) -> bool:
    """Win if result is in the 6-number double row [start, start+5]."""
    if is_zero_slot(result):
        return False
    return start <= int(result) <= start + 5


def hits_column(result: str, col: int) -> bool:
    if is_zero_slot(result):
        return False
    return int(result) in COLUMNS[col]


def hits_dozen(result: str, dozen: int) -> bool:
    """Win if result is in the chosen dozen (1=1-12, 2=13-24, 3=25-36)."""
    if is_zero_slot(result):
        return False
    n = int(result)
    low = (dozen - 1) * 12 + 1
    return low <= n <= low + 11


def hits_red(result: str) -> bool:
    if is_zero_slot(result):
        return False
    return int(result) in RED_NUMBERS


def hits_black(result: str) -> bool:
    if is_zero_slot(result):
        return False
    n = int(result)
    return n != 0 and n not in RED_NUMBERS


def hits_odd(result: str) -> bool:
    if is_zero_slot(result):
        return False
    n = int(result)
    return n != 0 and n % 2 == 1


def hits_even(result: str) -> bool:
    if is_zero_slot(result):
        return False
    n = int(result)
    return n != 0 and n % 2 == 0


def hits_low(result: str) -> bool:
    if is_zero_slot(result):
        return False
    return 1 <= int(result) <= 18


def hits_high(result: str) -> bool:
    if is_zero_slot(result):
        return False
    return 19 <= int(result) <= 36


# ---------------------------------------------------------------------------
# Unified bet evaluation
# ---------------------------------------------------------------------------

def evaluate_bet(result: str, bet_type: str, target) -> bool:
    """Return True if result is a win for the given bet configuration.

    target meaning per bet_type:
        "straight"  -> int  (0-36)
        "split"     -> tuple[int, int]
        "street"    -> int  (row start: STREET_STARTS)
        "corner"    -> int  (top-left: CORNER_STARTS)
        "line"      -> int  (row start: LINE_STARTS)
        "column"    -> int  (1, 2, or 3)
        "dozen"     -> int  (1, 2, or 3)
        "evenmoney" -> str  ("red","black","odd","even","low","high")
    """
    if bet_type == "straight":
        return hits_straight(result, int(target))
    if bet_type == "split":
        a, b = target
        return hits_split(result, a, b)
    if bet_type == "street":
        return hits_street(result, int(target))
    if bet_type == "corner":
        return hits_corner(result, int(target))
    if bet_type == "line":
        return hits_line(result, int(target))
    if bet_type == "column":
        return hits_column(result, int(target))
    if bet_type == "dozen":
        return hits_dozen(result, int(target))
    if bet_type == "evenmoney":
        fn_map = {
            "red":   hits_red,
            "black": hits_black,
            "odd":   hits_odd,
            "even":  hits_even,
            "low":   hits_low,
            "high":  hits_high,
        }
        fn = fn_map.get(str(target))
        return fn(result) if fn else False
    return False


def calculate_payout(bet: int, bet_type: str) -> int:
    """Return gross payout (including returned stake) for a winning bet."""
    return bet * PAYOUTS.get(bet_type, 0)
