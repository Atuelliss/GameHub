from __future__ import annotations

from .constants import CHIP_DENOMINATIONS, CHIP_LABELS, RANK_NAMES, SPECIALTY_TITLES
from .models import User

# ---------------------------------------------------------------------------
# Chip / balance display
# ---------------------------------------------------------------------------

def chips_label(amount: int) -> str:
    """Returns e.g. '1,250 chips' formatted with commas."""
    return f"{amount:,} chips"


# Word representations for chip counts up to 20.
# Values beyond 20 fall back to the numeric string.
_NUM_WORDS: dict[int, str] = {
    1: "one",      2: "two",      3: "three",    4: "four",
    5: "five",     6: "six",      7: "seven",    8: "eight",
    9: "nine",     10: "ten",     11: "eleven",  12: "twelve",
    13: "thirteen", 14: "fourteen", 15: "fifteen", 16: "sixteen",
    17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
}


def _num_word(n: int) -> str:
    return _NUM_WORDS.get(n, str(n))


def describe_chip_bet(amount: int) -> str:
    """Decomposes a bet into chip denominations using a greedy algorithm and
    returns a natural-language description.  Only called in chip mode.

    Examples:
      21  -> 'two $10 chips and one $1 chip'
      100 -> 'one $100 chip'
      37  -> 'one $25 chip, one $10 chip, and two $1 chips'
    """
    parts: list[str] = []
    remaining = amount
    for denom in CHIP_DENOMINATIONS:
        count = remaining // denom
        if count:
            label = CHIP_LABELS[denom]
            chip_word = "chip" if count == 1 else "chips"
            parts.append(f"{_num_word(count)} {label} {chip_word}")
            remaining -= count * denom
        if remaining == 0:
            break

    if not parts:
        return f"{amount:,} chips"
    if len(parts) == 1:
        return parts[0]
    if len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    return ", ".join(parts[:-1]) + f", and {parts[-1]}"


# ---------------------------------------------------------------------------
# Rank and title display
# ---------------------------------------------------------------------------

def rank_display(rank: int) -> str:
    """Returns the rank name string for a rank integer, e.g. 'High Roller'."""
    return RANK_NAMES.get(rank, "Member")


def title_display(user: User) -> str:
    """Returns the active specialty title formatted string (including emoji),
    or an empty string if the player has no active specialty title set.
    """
    if not user.active_title:
        return ""
    return SPECIALTY_TITLES.get(user.active_title, "")


def build_balance_footer(
    user: User,
    balance: int,
    currency_name: str = "chips",
) -> str:
    """Returns footer text combining active specialty title, rank name, and balance.

    In chip mode, currency_name is always 'chips'.
    In bank mode, pass the live currency name from bank.get_currency_name(guild).

    Examples:
      '🃏 Card Shark | High Roller | Balance: 4,800 chips'
      'High Roller | Balance: 4,800 chips'   (no active specialty title)
      'The Whale | Balance: 12,500 credits'  (bank mode)
    """
    parts: list[str] = []
    title = title_display(user)
    if title:
        parts.append(title)
    parts.append(rank_display(user.rank))
    parts.append(f"Balance: {balance:,} {currency_name}")
    return " | ".join(parts)
