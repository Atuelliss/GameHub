"""Scratch Card -- Pure game logic for HighRollerClub.

A free scratch ticket each player can claim once per cooldown period
(conf.scratch_cooldown_hours) when the server has Scratch Cards enabled.
No cost and no bet. It is a server perk, not a game, so it records no
win/loss and gives no prestige (apart from the rank_xp reward itself).

Card layout
-----------
A 3x3 grid of symbols. Exactly one symbol appears three times: that's the
prize. Every other symbol appears at most twice, so the card always reads
as one clear match.

Rewards
-------
Drawn at random from conf.scratch_reward_pool and applied with the same
helpers as the Mystery Wheel (games/mystery_wheel.py). Chip prizes are
smaller than the Mystery Wheel's because a card can come round more often
than once a day.

Cooldown
--------
user.last_scratch_date stores the UTC time of the last scratch as an ISO
datetime string. A new card is ready once scratch_cooldown_hours have passed.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# Chip prize range when "chips" is drawn: random.randint(*SCRATCH_CHIP_REWARD_RANGE).
SCRATCH_CHIP_REWARD_RANGE: tuple[int, int] = (25, 250)

# One symbol per reward type; the matching triple on the card reveals the prize.
REWARD_SYMBOL: dict[str, str] = {
    "chips":           "💰",
    "bonus_bet_token": "🎫",
    "rank_xp":         "⭐",
    "free_spin":       "🎰",
    "lucky_streak":    "🔥",
}
# Extra symbols used only as filler, so every card has enough variety.
_FILLER_SYMBOLS: tuple[str, ...] = ("🍒", "🔔", "💎", "🍀")


def _parse(last_iso: str | None) -> datetime | None:
    if not last_iso:
        return None
    try:
        last = datetime.fromisoformat(last_iso)
    except ValueError:
        return None  # an old date-only or garbled value: treat as never scratched
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last


def next_ready_time(last_iso: str | None, cooldown_hours: int) -> datetime | None:
    """UTC time the next card is ready, or None if one is ready now."""
    last = _parse(last_iso)
    if last is None:
        return None
    ready = last + timedelta(hours=cooldown_hours)
    return ready if ready > datetime.now(timezone.utc) else None


def time_until_ready(last_iso: str | None, cooldown_hours: int) -> str:
    """Human-readable wait, e.g. '5 hr 07 min'. '0 hr 00 min' when ready."""
    ready = next_ready_time(last_iso, cooldown_hours)
    if ready is None:
        return "0 hr 00 min"
    seconds = int((ready - datetime.now(timezone.utc)).total_seconds())
    hours, rem = divmod(max(seconds, 0), 3600)
    return f"{hours} hr {rem // 60:02d} min"


def now_iso() -> str:
    """The value to store in user.last_scratch_date when a card is scratched."""
    return datetime.now(timezone.utc).isoformat()


def roll_chip_amount() -> int:
    """Random chip prize within SCRATCH_CHIP_REWARD_RANGE."""
    return random.randint(*SCRATCH_CHIP_REWARD_RANGE)


def build_card(reward_type: str) -> list[str]:
    """Return 9 symbols (row by row) with exactly one triple: the prize symbol."""
    prize = REWARD_SYMBOL.get(reward_type, REWARD_SYMBOL["chips"])
    others = [s for s in (*REWARD_SYMBOL.values(), *_FILLER_SYMBOLS) if s != prize]
    # 6 filler cells, no symbol more than twice, so the prize is the only triple.
    filler = random.sample(others * 2, 6)
    cells = [prize] * 3 + filler
    random.shuffle(cells)
    return cells
