# Task loops can be defined here
from __future__ import annotations

import logging
from datetime import datetime, timezone

from discord.ext import tasks

from ..abc import CompositeMetaClass

log = logging.getLogger("red.highrollerclub.tasks")


class TaskLoops(metaclass=CompositeMetaClass):
    """
    Subclass all task loops in this directory so you can import this single task loop class in your cog's class constructor.

    See `commands` directory for the same pattern.
    """

    def start_background_tasks(self) -> None:
        if not self.expired_bonus_cleanup_loop.is_running():
            self.expired_bonus_cleanup_loop.start()

    async def stop_background_tasks(self) -> None:
        if self.expired_bonus_cleanup_loop.is_running():
            self.expired_bonus_cleanup_loop.cancel()

    def cleanup_expired_bonus_state(self) -> tuple[int, int]:
        now = datetime.now(timezone.utc)
        cleared_multipliers = 0
        cleared_streaks = 0

        for conf in self.db.configs.values():
            for user in conf.users.values():
                if user.pending_multiplier_expiry is not None and now >= user.pending_multiplier_expiry:
                    if user.pending_multiplier is not None or user.pending_multiplier_expiry is not None:
                        cleared_multipliers += 1
                    user.pending_multiplier = None
                    user.pending_multiplier_expiry = None

                if user.lucky_streak_expiry is not None and now >= user.lucky_streak_expiry:
                    cleared_streaks += 1
                    user.lucky_streak_expiry = None

        return cleared_multipliers, cleared_streaks

    @tasks.loop(minutes=1)
    async def expired_bonus_cleanup_loop(self) -> None:
        cleared_multipliers, cleared_streaks = self.cleanup_expired_bonus_state()
        if cleared_multipliers == 0 and cleared_streaks == 0:
            return

        log.debug(
            "Cleared expired bonuses: %s multipliers, %s lucky streaks",
            cleared_multipliers,
            cleared_streaks,
        )
        self.save()

    @expired_bonus_cleanup_loop.before_loop
    async def before_expired_bonus_cleanup_loop(self) -> None:
        await self.bot.wait_until_red_ready()
