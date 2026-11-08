"""Multiplier Wheel — Pure game logic for HighRollerClub.

The Multiplier Wheel is a paid-boost mechanic, not a traditional gambling game:
  - Player pays a flat spin cost (conf.multiplier_wheel_cost) drawn from their balance.
  - A weighted-random outcome is selected from MULTIPLIER_WHEEL_OUTCOMES.
  - The selected multiplier is stored on the user's profile until consumed or expired.
  - Used up by the next play of a MULTIPLIER_ELIGIBLE_GAMES game, win or lose
    (record_loss burns it on a loss). On a win it adds profit x (multiplier - 1),
    capped at 2 spin costs (multiplier_wheel_bonus), so a spin is never a sure profit.
  - Expires after conf.multiplier_wheel_expiry_minutes regardless of use.

There is no win/loss — every spin guarantees a multiplier. No prestige points are
awarded or deducted. No record_win / record_loss calls are made.

Outcome weights can be overridden per-guild via CONFIGURABLE_RNG["multiplierwheel"].
Call get_game_rng(conf, "multiplierwheel", "weights") to retrieve the effective weights.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from ..common.constants import MULTIPLIER_WHEEL_OUTCOMES


def spin_multiplier_wheel(weights: list[int]) -> dict:
    """Returns a randomly selected outcome dict from MULTIPLIER_WHEEL_OUTCOMES.

    Args:
        weights: Parallel list of integer weights, one per outcome in
                 MULTIPLIER_WHEEL_OUTCOMES. Must have the same length.
                 Higher weight = more common outcome.

    Returns:
        A dict with keys ``"label"`` (str, e.g. ``"2.0x"``) and
        ``"value"`` (float, e.g. ``2.0``).

    Raises:
        ValueError: If ``weights`` length does not match MULTIPLIER_WHEEL_OUTCOMES.
    """
    if len(weights) != len(MULTIPLIER_WHEEL_OUTCOMES):
        raise ValueError(
            f"weights length ({len(weights)}) must match "
            f"MULTIPLIER_WHEEL_OUTCOMES length ({len(MULTIPLIER_WHEEL_OUTCOMES)})"
        )
    return random.choices(MULTIPLIER_WHEEL_OUTCOMES, weights=weights, k=1)[0]


def compute_expiry(expiry_minutes: int) -> datetime:
    """Returns the UTC datetime at which a freshly awarded multiplier expires.

    Args:
        expiry_minutes: Duration in minutes until expiry (from conf.multiplier_wheel_expiry_minutes).

    Returns:
        A timezone-aware UTC datetime object.
    """
    return datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes)


def format_time_remaining(expiry: datetime) -> str:
    """Returns a human-readable time-remaining string for a pending multiplier.

    Examples:
        '59 min 42 sec'
        '4 min 02 sec'
        'Expired'

    Args:
        expiry: The UTC expiry datetime stored on the user.
    """
    delta = expiry - datetime.now(timezone.utc)
    total_seconds = int(delta.total_seconds())
    if total_seconds <= 0:
        return "Expired"
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes} min {seconds:02d} sec"
