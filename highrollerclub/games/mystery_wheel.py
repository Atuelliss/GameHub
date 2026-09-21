"""Mystery Wheel -- Pure game logic for HighRollerClub.

The Mystery Wheel is a free daily spin that awards a random reward from
the server's configured mystery_wheel_reward_pool. No cost to spin.

Daily gate:
  - One spin allowed per calendar day, tracked in the server's configured
    timezone (conf.mystery_wheel_timezone).
  - last_mystery_wheel_date is stored as an ISO date string (YYYY-MM-DD)
    in that timezone. If the stored date equals today's date, the spin
    is blocked.
  - Resets at midnight in the configured timezone.

Reward selection:
  - Random.choice() over conf.mystery_wheel_reward_pool.
  - Pool entries: "chips" | "bonus_bet_token" | "rank_xp" | "free_spin" | "lucky_streak"
  - If the pool is empty or contains only unknown entries, "chips" is used.
  - For "chips": a random amount is selected from MYSTERY_CHIP_REWARD_RANGE.
    In bank mode, the amount is converted using conf.discord_currency_conversion_rate.
  - For "rank_xp": RANK_XP_BONUS_POINTS prestige points added.
  - For "bonus_bet_token": user.bonus_bet_tokens += 1.
  - For "free_spin": user.free_spins_available += 1.
  - For "lucky_streak": user.lucky_streak_expiry set to now + LUCKY_STREAK_EXPIRY_MINUTES.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..common.constants import LUCKY_STREAK_EXPIRY_MINUTES, RANK_XP_BONUS_POINTS

# Chip reward range when "chips" is drawn from the pool.
# Final amount = random.randint(*MYSTERY_CHIP_REWARD_RANGE).
MYSTERY_CHIP_REWARD_RANGE: tuple[int, int] = (100, 1000)

# Reward display labels used by the view.
REWARD_DISPLAY: dict[str, str] = {
    "chips":            "💰 Chip Bonus",
    "bonus_bet_token":  "🎫 Bonus Bet Token",
    "rank_xp":          "⭐ Rank XP",
    "free_spin":        "🎰 Free Spin",
    "lucky_streak":     "🔥 Lucky Streak",
}

REWARD_DESCRIPTION: dict[str, str] = {
    "chips":           "Extra chips deposited directly to your balance.",
    "bonus_bet_token": "Your next eligible win pays double — consumed automatically.",
    "rank_xp":         f"+{RANK_XP_BONUS_POINTS} prestige points toward your rank.",
    "free_spin":       "One free Slots spin — no bet deducted.",
    "lucky_streak":    f"+25% on every consecutive win for {LUCKY_STREAK_EXPIRY_MINUTES} minutes.",
}


def get_today_date_string(timezone_name: str) -> str:
    """Returns today's date as an ISO date string (YYYY-MM-DD) in the given timezone.

    Args:
        timezone_name: IANA timezone string (e.g. ``"America/New_York"``).
            Falls back to UTC if the timezone is invalid.

    Returns:
        A string like ``"2024-07-15"``.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, KeyError):
        tz = ZoneInfo("UTC")
    return datetime.now(tz).date().isoformat()


def can_spin(user_last_date: str | None, timezone_name: str) -> bool:
    """Returns True if the player is allowed to spin today.

    Args:
        user_last_date: The value of ``user.last_mystery_wheel_date``.
            ``None`` means the player has never spun.
        timezone_name: IANA timezone string from conf.mystery_wheel_timezone.
    """
    if user_last_date is None:
        return True
    return user_last_date != get_today_date_string(timezone_name)


def time_until_reset(timezone_name: str) -> str:
    """Returns a human-readable string for how long until midnight in the given timezone.

    Used in the "already spun" embed to tell the player when to return.

    Examples:
        "14 hr 32 min"
        "0 hr 58 min"
    """
    try:
        tz = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, KeyError):
        tz = ZoneInfo("UTC")

    now_local = datetime.now(tz)
    # Midnight at the start of tomorrow in local time.
    tomorrow = (now_local.date() + __import__("datetime").date.resolution).isoformat()
    # Reconstruct as datetime for delta calculation.
    from datetime import date  # noqa: PLC0415
    tomorrow_midnight = datetime(
        *date.fromisoformat(tomorrow).timetuple()[:3], tzinfo=tz
    )
    delta = tomorrow_midnight - now_local
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(max(total_seconds, 0), 3600)
    minutes = remainder // 60
    return f"{hours} hr {minutes:02d} min"


def pick_reward(pool: list[str]) -> str:
    """Returns a randomly selected reward type string from the pool.

    Falls back to ``"chips"`` if the pool is empty.

    Args:
        pool: List of valid reward type strings from conf.mystery_wheel_reward_pool.
    """
    valid = [r for r in pool if r in REWARD_DISPLAY]
    if not valid:
        return "chips"
    return random.choice(valid)


def roll_chip_amount() -> int:
    """Returns a random chip amount within MYSTERY_CHIP_REWARD_RANGE."""
    return random.randint(*MYSTERY_CHIP_REWARD_RANGE)


def apply_reward(user, reward_type: str, chip_amount: int = 0) -> None:
    """Mutates user in place to reflect the awarded reward.

    Chip balance credit and bank deposits are handled by the view (async).
    This function handles all non-balance state mutations:
        - bonus_bet_token: increments user.bonus_bet_tokens
        - rank_xp: adds RANK_XP_BONUS_POINTS to user.prestige_points
        - free_spin: increments user.free_spins_available
        - lucky_streak: sets user.lucky_streak_expiry
        - chips: no mutation here — caller credits balance separately

    Args:
        user: A User model instance.
        reward_type: One of REWARD_DISPLAY keys.
        chip_amount: Used for chips only. Ignored for other reward types.
    """
    if reward_type == "bonus_bet_token":
        user.bonus_bet_tokens += 1
    elif reward_type == "rank_xp":
        user.prestige_points += RANK_XP_BONUS_POINTS
    elif reward_type == "free_spin":
        user.free_spins_available += 1
    elif reward_type == "lucky_streak":
        user.lucky_streak_expiry = (
            datetime.now(timezone.utc) + timedelta(minutes=LUCKY_STREAK_EXPIRY_MINUTES)
        )
    # "chips" balance credit is async — handled by the view via credit_balance().
