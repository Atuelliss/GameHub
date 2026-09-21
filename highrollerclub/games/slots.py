"""
Slots — pure game logic for HighRollerClub.

Covers:
  - Symbol pool definition and weighted sampling
  - Reel spin  (3×3 grid; middle row is the payline)
  - Payout calculation
  - ASCII reel display string generation

Discord UI (View, Modal, buttons) lives in views/slots_view.py.
"""

from __future__ import annotations

import random
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Symbol definitions
# ---------------------------------------------------------------------------
# Each symbol's `name` is exactly 5 characters so it fits cleanly in the
# 7-wide cell (| XXXXX |) of the ASCII reel display with 1 space of padding
# on each side.
#
# `base_weight`  : relative draw probability before house-edge scaling.
# `payout`       : multiplier on the original bet for N matching payline
#                  symbols.  e.g. {3: 50} → 3-of-a-kind pays 50× the bet.
#                  No entry for a count = no payout for that count.

class SlotSymbol(NamedTuple):
    name: str               # exactly 5 chars
    base_weight: int
    payout: dict[int, int]  # {match_count: payout_multiplier}
                            # match_count 3 = three-of-a-kind on payline
                            # match_count 2 = partial match on payline (two of three)
                            # no entry     = no payout for that count


SLOT_SYMBOLS: list[SlotSymbol] = [
    SlotSymbol(" 777 ", 1,  {3: 50}),              # Jackpot — rarest, highest payout
    SlotSymbol(" BAR ", 3,  {3: 15}),              # Classic BAR
    SlotSymbol(" BEL ", 5,  {3: 10, 2: 4}),        # Bell — 2× pays 4×
    SlotSymbol(" DIA ", 8,  {3: 6,  2: 3}),        # Diamond — 2× pays 3×
    SlotSymbol(" CHR ", 12, {3: 4,  2: 2}),        # Cherry — 2× pays 2× (most common win)
    SlotSymbol(" --- ", 8,  {}),                    # Dead reel — no payout; scaled for house edge
]

# Index of the dead-weight --- symbol in SLOT_SYMBOLS.
_LOW_IDX: int = 5

# ---------------------------------------------------------------------------
# Vertical column payouts
# ---------------------------------------------------------------------------
# A vertical match means all three rows in a single reel column show the same
# paying symbol.  These are secondary paylines evaluated in addition to the
# horizontal center row.  Payouts are set independently from the horizontal
# multipliers and are intentionally lower.
#
# Dead --- symbols are excluded — a vertical column of --- yields nothing.

COLUMN_PAYOUTS: dict[str, int] = {
    " 777 ": 25,   # 50% of center jackpot
    " BAR ":  7,   # ≈50% of center BAR
    " BEL ":  5,   # 50% of center BEL
    " DIA ":  3,   # 50% of center DIA
    " CHR ":  2,   # 50% of center CHR
}


# ---------------------------------------------------------------------------
# House-edge weight scaling
# ---------------------------------------------------------------------------

def _effective_weights(house_edge_pct: float) -> list[int]:
    """Return the symbol weight list with the --- symbol scaled for house edge.

    The --- symbol is the only dead-weight symbol (no payout for any match
    count).  Increasing its weight relative to paying symbols raises the
    house edge by reducing win frequency.

    Formula:  effective_dead_weight = base_weight × (1.0 + house_edge_pct / 10.0)

    At the default 15 % house edge → dead weight = 8 × 2.5 = 20. Total pool = 49.
    At 0 %  house edge             → dead weight = 8 × 1.0 = 8.  Total pool = 37.
    At 40 % house edge             → dead weight = 8 × 5.0 = 40. Total pool = 69.

    Approximate payline win rates (horizontal center row only):
      0 % edge  → ~42 % of spins pay something
      15 % edge → ~25 % of spins pay something  (default)
      40 % edge → ~13 % of spins pay something
    """
    weights = [s.base_weight for s in SLOT_SYMBOLS]
    scale = 1.0 + house_edge_pct / 10.0
    weights[_LOW_IDX] = int(SLOT_SYMBOLS[_LOW_IDX].base_weight * scale)
    return weights


# ---------------------------------------------------------------------------
# Spin
# ---------------------------------------------------------------------------

def spin_reels(house_edge_pct: float) -> tuple[list[list[SlotSymbol]], list[SlotSymbol]]:
    """Spin all three reels and return a 3×3 grid plus the payline.

    Args:
        house_edge_pct: Value from get_game_rng(conf, "slots", "house_edge_pct").
                        Accepted range: 0.0 – 40.0.

    Returns:
        grid    : 3 rows × 3 columns of SlotSymbol.
                    Row 0 = top    (display only — no payout impact)
                    Row 1 = middle (PAYLINE — determines win/loss)
                    Row 2 = bottom (display only — no payout impact)
        payline : The 3 symbols from Row 1 (middle row).
    """
    weights = _effective_weights(house_edge_pct)
    grid: list[list[SlotSymbol]] = [
        random.choices(SLOT_SYMBOLS, weights=weights, k=3)
        for _ in range(3)
    ]
    return grid, grid[1]


# ---------------------------------------------------------------------------
# Payout calculation
# ---------------------------------------------------------------------------

def calculate_payout(bet: int, grid: list[list[SlotSymbol]]) -> tuple[int, str]:
    """Calculate the total chips returned and a short result label.

    Evaluates two types of paylines:
      1. Horizontal center row (primary) — checks 3-of-a-kind and 2-of-a-kind
         matches using each symbol's `payout` dict.  Symbols are tested in
         SLOT_SYMBOLS order (highest value first) so the best match wins.
      2. Vertical columns (secondary) — checks each of the three columns for a
         3-of-a-kind match using COLUMN_PAYOUTS.  All matching columns pay;
         their payouts are summed on top of the center-row result.

    Args:
        bet  : Original bet in chips.
        grid : Full 3×3 grid from spin_reels().
                 Row 0 = top display row.
                 Row 1 = center payline (primary horizontal).
                 Row 2 = bottom display row.

    Returns:
        payout_total  : Total chips returned to the player before bonus stacking.
                        0 on a complete loss.
        outcome_label : Human-readable result string shown in the embed.
                        Multiple win sources are joined with " · ".
    """
    total_payout: int = 0
    win_parts: list[str] = []
    center_no_pay_label: str | None = None  # only set when dead symbol fills the payline

    # ------------------------------------------------------------------
    # 1. Horizontal center row — primary payline.
    # ------------------------------------------------------------------
    payline = grid[1]
    names = [s.name for s in payline]
    for symbol in SLOT_SYMBOLS:
        count = names.count(symbol.name)
        # Dead-weight symbol: visible 3-of-a-kind but no payout.
        if count == 3 and not symbol.payout:
            center_no_pay_label = f"{symbol.name.strip()} × 3 — no payout."
            break
        if count in symbol.payout:
            multiplier = symbol.payout[count]
            total_payout += bet * multiplier
            sym = symbol.name.strip()
            if sym == "777" and count == 3:
                win_parts.append(f"JACKPOT!  777  777  777  — {multiplier}×!")
            else:
                win_parts.append(f"{sym} × {count} — {multiplier}×")
            break

    # ------------------------------------------------------------------
    # 2. Vertical columns — secondary paylines (3-of-a-kind only).
    # ------------------------------------------------------------------
    col_labels = ("Left", "Center", "Right")
    for col_idx in range(3):
        top_sym = grid[0][col_idx]
        if grid[1][col_idx] == top_sym and grid[2][col_idx] == top_sym:
            if top_sym.name in COLUMN_PAYOUTS:
                multiplier = COLUMN_PAYOUTS[top_sym.name]
                total_payout += bet * multiplier
                win_parts.append(
                    f"{col_labels[col_idx]} col {top_sym.name.strip()} × 3 — {multiplier}×"
                )

    # ------------------------------------------------------------------
    # 3. Compose the outcome label.
    # ------------------------------------------------------------------
    if win_parts:
        outcome_label = " · ".join(win_parts)
    elif center_no_pay_label:
        outcome_label = center_no_pay_label
    else:
        outcome_label = "No match — better luck next time."

    return total_payout, outcome_label


# ---------------------------------------------------------------------------
# ASCII reel display
# ---------------------------------------------------------------------------
# Rendered inside a triple-backtick code block so Discord uses monospace font,
# guaranteeing every character is exactly 1 unit wide and columns line up
# perfectly.
#
# Layout (25 chars wide):
#
#   +-------+-------+-------+
#   |  XXX  |  XXX  |  XXX  |   ← row above payline  (decoration)
#   [  XXX  |  XXX  |  XXX  ]   ← PAYLINE             ([ ] marks the active row)
#   |  XXX  |  XXX  |  XXX  |   ← row below payline  (decoration)
#   +-------+-------+-------+
#
# Each cell interior is 7 chars: space + 5-char symbol + space.
# The border is 25 chars: + (7 dashes +) × 3.
# Payline delimiters are [ and ] instead of | | to visually distinguish it.

_BORDER   = "+-------+-------+-------+"
_TITLE    = "=[ HIGH ROLLER SLOTS ]= "   # 25 chars (padded to match border width)
_PIPE     = "|"
_PAY_L    = "["
_PAY_R    = "]"


def _cell(symbol: SlotSymbol) -> str:
    """Return the 7-char interior of one reel cell: ' XXXXX '."""
    return f" {symbol.name} "


def _row(symbols: list[SlotSymbol], *, is_payline: bool) -> str:
    """Build one row of the reel display."""
    left  = _PAY_L if is_payline else _PIPE
    right = _PAY_R if is_payline else _PIPE
    cells = _PIPE.join(_cell(s) for s in symbols)
    return f"{left}{cells}{right}"


def build_reel_display(grid: list[list[SlotSymbol]]) -> str:
    """Build the full ASCII slot machine face from a resolved 3×3 grid.

    Args:
        grid: 3×3 list of SlotSymbol — row 0 = top, row 1 = payline, row 2 = bottom.

    Returns:
        Multiline string to be wrapped in ```...``` in the embed description.
    """
    return "\n".join([
        _TITLE,
        _BORDER,
        _row(grid[0], is_payline=False),
        _row(grid[1], is_payline=True),
        _row(grid[2], is_payline=False),
        _BORDER,
    ])


# Idle display shown before the player has placed a bet.
_IDLE_TOP    = "|  ---  |  ---  |  ---  |"
_IDLE_MIDDLE = "[  ???  |  ???  |  ???  ]"
_IDLE_BOTTOM = "|  ---  |  ---  |  ---  |"


def build_idle_display() -> str:
    """Return the idle (pre-spin) ASCII reel face."""
    return "\n".join([
        _TITLE,
        _BORDER,
        _IDLE_TOP,
        _IDLE_MIDDLE,
        _IDLE_BOTTOM,
        _BORDER,
    ])
