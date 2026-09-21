"""Double -- Pure game logic for HighRollerClub.

A press-your-luck dice game with exponential pot growth.  The player bets an
initial amount and then enters a loop where each roll either doubles the pot
or ends the game in a total loss.

Pot math
--------
Starting pot = bet.  Each successful roll doubles the pot:
  depth 0 (before first roll): pot = bet   (the stake, not yet credited)
  depth 1 (first win)        : pot = bet * 2
  depth 2 (second win)       : pot = bet * 4
  depth N (Nth win)          : pot = bet * 2^N

On a successful roll the player may Cash Out (receive the current pot) or
Double Again (risk the entire pot on another roll).  On a failed roll the
original bet is forfeited -- no payout, regardless of depth.

Win chance
----------
Configurable by server admins via get_game_rng(conf, "double", "win_chance").
Default: 0.50 (50%).  Allowed range: 0.30 -- 0.70.

Exclusions
----------
Double is excluded from MULTIPLIER_ELIGIBLE_GAMES and
BONUS_BET_TOKEN_ELIGIBLE_GAMES.  The uncapped exponential upside makes
stacking a multiplier or doubling a token payout disproportionate.
Lucky Streak applies normally on cash-out.

This module contains no Discord UI -- only the flip function and pot math.
get_game_rng() must be called by the view for every flip so admin overrides
are respected at runtime.
"""

from __future__ import annotations

import random


def flip(win_chance: float) -> bool:
    """Return True (win) with probability ``win_chance``.

    ``win_chance`` must be a float in [0.0, 1.0] and should always be fetched
    via get_game_rng(conf, "double", "win_chance") so admin-configured values
    are used.  Passing the raw constant here would bypass admin overrides.
    """
    return random.random() < win_chance


def calculate_pot(bet: int, depth: int) -> int:
    """Return the pot value after ``depth`` consecutive successful rolls.

    pot = bet * 2^depth

    depth must be >= 1.  depth 0 means no rolls have been won yet and there
    is no pot to display or cash out.

    Examples:
      bet=200, depth=1 -> 400
      bet=200, depth=2 -> 800
      bet=200, depth=3 -> 1600
    """
    return bet * (2 ** depth)
