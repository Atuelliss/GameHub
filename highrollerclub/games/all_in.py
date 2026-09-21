"""All-In — Pure game logic for HighRollerClub.

A single-decision, all-or-nothing wager.  The player bets and selects a risk
tier.  One flip resolves the entire game — no intermediate decisions.

Tier mechanics
--------------
* win_chance  — always read at runtime via get_game_rng(conf, "allin", "tierN_win_chance")
                so admin overrides in CONFIGURABLE_RNG take effect.
* payout      — fixed integer multiplier stored in ALLIN_RISK_TIERS[tier]["payout"].
                 gross payout = bet × multiplier (bet is included in the return).

This module contains no Discord UI — only pure math and RNG.
"""
from __future__ import annotations

import random


def flip(win_chance: float) -> bool:
    """Return True (win) with probability ``win_chance``.

    ``win_chance`` must be a float in [0.0, 1.0] and should always be fetched
    via ``get_game_rng`` so admin-configured values are used.
    """
    return random.random() < win_chance


def calculate_payout(bet: int, payout_multiplier: int | float) -> int:
    """Return the gross payout (bet returned + profit) for a winning flip.

    Example: bet=500, payout_multiplier=3 → returns 1500.
    Always returns int even when payout_multiplier is a float (e.g. 2.5).
    """
    return int(bet * payout_multiplier)
