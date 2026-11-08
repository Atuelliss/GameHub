import asyncio
import json
import logging
import shutil
from io import BytesIO
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from .abc import CompositeMetaClass
from .commands import Commands
from .common import write_json_atomic
from .common.models import DB
from .listeners import Listeners
from .tasks import TaskLoops

log = logging.getLogger("red.highrollerclub")

DB_FILENAME = "db.json"
ADMIN_GROUP = "highrollerclubset"  # backup commands live under "<ADMIN_GROUP> backup"
BACKUP_KEEP = 3  # rotating backups kept in <data>/backups
BACKUP_INTERVAL_HOURS = 8  # minimum gap between rotating backups
SAVE_RETRIES = 3


class HighRollerClub(
    Commands, Listeners, TaskLoops, commands.Cog, metaclass=CompositeMetaClass
):
    """The High Roller Club: a Vegas-style casino with ranks, prestige and 15 games."""

    __author__ = "Jayar/Vainne"
    __version__ = "0.1.23"

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.db: DB = DB()

        # Data-safety state
        self._db_loaded = False  # True once db.json has been read; saves and commands wait for it
        self._load_failed = False  # True if db.json couldn't be read; blocks saves so it isn't overwritten
        self._save_lock = asyncio.Lock()
        self._save_task: Optional[asyncio.Task] = None
        self._save_again = False
        self._init_task: Optional[asyncio.Task] = None

    def format_help_for_context(self, ctx: commands.Context):
        helpcmd = super().format_help_for_context(ctx)
        txt = "Version: {}\nAuthor: {}".format(self.__version__, self.__author__)
        return f"{helpcmd}\n\n{txt}"

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Remove the user's player record (stats, chips, titles) from every server."""
        if not self._db_loaded:
            return  # nothing in memory to delete from, and saving is blocked anyway
        removed = False
        for conf in self.db.configs.values():
            if conf.users.pop(user_id, None) is not None:
                removed = True
            # Drop (without refunding) any horse-racing bet or refund owed to them.
            if conf.active_race is not None:
                kept = [b for b in conf.active_race.bets if b.user_id != user_id]
                if len(kept) != len(conf.active_race.bets):
                    conf.active_race.bets = kept
                    removed = True
            pending = [b for b in conf.race_pending_refunds if b.user_id != user_id]
            if len(pending) != len(conf.race_pending_refunds):
                conf.race_pending_refunds = pending
                removed = True
            if user_id in conf.race_notify_ids:
                conf.race_notify_ids.remove(user_id)
                removed = True
            # Drop (without refunding) any Texas Hold'em table chips held for them.
            if conf.holdem_escrow.pop(user_id, None) is not None:
                removed = True
            if user_id in conf.blacklisted_users and requester != "user":
                conf.blacklisted_users.remove(user_id)
                removed = True
        if removed:
            await self.save_now()

    async def red_get_data_for_user(self, *, user_id: int) -> dict:
        """Return the user's player records as a JSON file, one entry per server."""
        records = {}
        for gid, conf in self.db.configs.items():
            if user_id in conf.users:
                records[str(gid)] = conf.users[user_id].model_dump(mode="json")
            if user_id in conf.race_notify_ids:
                records.setdefault(str(gid), {})["race_notifications"] = True
            if user_id in conf.holdem_escrow:
                records.setdefault(str(gid), {})["holdem_table_chips"] = conf.holdem_escrow[user_id].amount
        if not records:
            return {}
        payload = json.dumps(records, indent=2).encode("utf-8")
        return {"highrollerclub.json": BytesIO(payload)}

    async def cog_load(self) -> None:
        # Keep a reference so the startup task can't be garbage-collected mid-run.
        self._init_task = asyncio.create_task(self.initialize())

    async def initialize(self) -> None:
        await self.bot.wait_until_red_ready()
        if not await self._load_db():
            return
        cleared_multipliers, cleared_streaks = self.cleanup_expired_bonus_state()
        if cleared_multipliers or cleared_streaks:
            await self.save_now()
            log.info(
                "Cleared expired bonuses during startup: %s multipliers, %s lucky streaks",
                cleared_multipliers,
                cleared_streaks,
            )
        self.start_background_tasks()
        await self.hr_recover()  # refund any horse race interrupted by a restart
        await self.hd_recover()  # refund Texas Hold'em stacks left at tables by a restart
        log.info("Config loaded")

    async def cog_unload(self) -> None:
        if self._init_task is not None and not self._init_task.done():
            self._init_task.cancel()
        await self.stop_background_tasks()
        if self._db_loaded:
            await self.hr_shutdown()  # refund open horse races before the final save
            await self.hd_shutdown()  # close Texas Hold'em tables and refund every stack
        await self._final_save()

    # ------------------------------------------------------------------
    # Data safety: load guard, never-dropped saves, rotating backups.
    # Owner commands for these live under `<admin group> backup` in commands/admin_commands.py.
    # ------------------------------------------------------------------

    @property
    def data_path(self) -> Path:
        return cog_data_path(self) / DB_FILENAME

    async def cog_check(self, ctx: commands.Context) -> bool:
        """Block the cog's commands until the data file has loaded, so nobody plays on an empty DB."""
        if self._db_loaded or (ctx.command is not None and _is_recovery_command(ctx.command)):
            return True
        # Only reply when one of our commands is actually run (not during [p]help filtering)
        if ctx.command is not None and ctx.command.cog is self:
            if self._load_failed:
                await ctx.send(
                    "⚠️ This game's data failed to load. The bot owner needs to check the logs "
                    f"(or restore a backup with `{ctx.clean_prefix}{ADMIN_GROUP} backup`)."
                )
            else:
                await ctx.send("⏳ Still loading game data. Please try again in a few seconds.")
        return False

    async def _load_db(self) -> bool:
        """Load db.json. On failure, block all saves so the real file is never overwritten."""
        path = self.data_path
        try:
            self.db = await asyncio.to_thread(DB.from_file, path)
        except Exception:
            self._load_failed = True
            log.exception(
                "DATABASE LOAD FAILED - saving is disabled so %s is not overwritten. "
                "Fix the file or restore a backup with [p]%s backup restore, then reload the cog.",
                path, ADMIN_GROUP,
            )
            return False
        # Snapshot of the file as it was before this session changed anything
        try:
            await asyncio.to_thread(shutil.copy2, path, path.with_name(DB_FILENAME + ".backup"))
        except OSError as e:
            log.warning("Could not create start-of-session backup: %s", e)
        self._db_loaded = True
        return True

    def _can_save(self) -> bool:
        if self._load_failed:
            log.warning("Save blocked - the database failed to load. Fix it and reload the cog.")
            return False
        if not self._db_loaded:
            log.warning("Save skipped - the database has not finished loading yet.")
            return False
        return True

    def save(self) -> None:
        """Queue a save. A request that arrives mid-save triggers one more save afterwards, never dropped."""
        if not self._can_save():
            return
        if self._save_task is not None and not self._save_task.done():
            self._save_again = True
            return
        self._save_task = asyncio.create_task(self._save_loop())

    async def _save_loop(self) -> None:
        while True:
            self._save_again = False
            try:
                await self.save_now()
            except Exception:
                log.exception("Failed to save config")
            if not self._save_again:
                return

    async def save_now(self) -> None:
        """Save immediately and wait for it to finish. Raises if every retry fails."""
        if not self._can_save():
            return
        async with self._save_lock:
            # Serialize on the event loop: the snapshot can't change halfway through,
            # which it could if model_dump_json ran in a thread while commands edit the data.
            dump = self.db.model_dump_json()
            for attempt in range(1, SAVE_RETRIES + 1):
                try:
                    await asyncio.to_thread(self._write_db, dump)
                    return
                except Exception as e:
                    if attempt == SAVE_RETRIES:
                        raise
                    log.warning("Save attempt %d failed: %s - retrying", attempt, e)
                    await asyncio.sleep(0.5 * attempt)

    def _write_db(self, dump: str) -> None:
        """Runs in a worker thread."""
        self._rotate_backups()
        write_json_atomic(self.data_path, dump)

    def _rotate_backups(self) -> None:
        """Keep BACKUP_KEEP copies of db.json, at least BACKUP_INTERVAL_HOURS apart. Runs in a worker thread."""
        path = self.data_path
        if not path.exists():
            return
        backup_dir = path.parent / "backups"
        try:
            backup_dir.mkdir(exist_ok=True)
            existing = sorted(backup_dir.glob("db_*.json"), reverse=True)
            if existing:
                try:
                    newest = datetime.strptime(existing[0].stem[3:], "%Y%m%d_%H%M%S")
                    if datetime.now() - newest < timedelta(hours=BACKUP_INTERVAL_HOURS):
                        return
                except ValueError:
                    pass  # unrecognised name; make a fresh backup
            shutil.copy2(path, backup_dir / f"db_{datetime.now():%Y%m%d_%H%M%S}.json")
            for old in sorted(backup_dir.glob("db_*.json"), reverse=True)[BACKUP_KEEP:]:
                old.unlink(missing_ok=True)
        except OSError as e:
            log.warning("Could not rotate backups: %s", e)

    def list_backups(self) -> list[Path]:
        """All backups, newest first: rotating, manual, and the start-of-session copy."""
        path = self.data_path
        backup_dir = path.parent / "backups"
        backups = list(backup_dir.glob("db_*.json")) + list(backup_dir.glob("manual_*.json"))
        session_copy = path.with_name(DB_FILENAME + ".backup")
        if session_copy.exists():
            backups.append(session_copy)
        return sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)

    async def create_backup(self) -> Path:
        """Save now (if possible) and copy db.json to backups/manual_<time>.json.

        Manual backups are never rotated out; delete them by hand when no longer needed.
        """
        if self._can_save():
            await self.save_now()
        path = self.data_path
        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist yet")
        target = path.parent / "backups" / f"manual_{datetime.now():%Y%m%d_%H%M%S}.json"

        def _copy() -> None:
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(path, target)

        await asyncio.to_thread(_copy)
        return target

    async def restore_backup(self, source: Path) -> None:
        """Replace db.json with `source`. Raises if the backup doesn't load or the copy fails.

        Saving is paused afterwards (so the old in-memory data can't overwrite the restored
        file) until the cog is reloaded. The replaced file is kept as db.json.pre-restore.
        """
        await asyncio.to_thread(DB.from_file, source)  # make sure it actually loads
        path = self.data_path
        self._db_loaded = False
        if self._save_task is not None and not self._save_task.done():
            try:
                await self._save_task  # let an in-flight save finish before we replace the file
            except Exception:
                pass
        async with self._save_lock:
            if path.exists():
                await asyncio.to_thread(shutil.copy2, path, path.with_name(DB_FILENAME + ".pre-restore"))
            await asyncio.to_thread(shutil.copy2, source, path)

    async def _final_save(self) -> None:
        if self._save_task is not None and not self._save_task.done():
            try:
                await self._save_task
            except Exception:
                pass  # already logged by _save_loop
        try:
            await self.save_now()
        except Exception:
            log.exception("Final save on unload failed")


def _is_recovery_command(command: commands.Command) -> bool:
    """The admin group and its `backup` subcommands must work even when the data failed to load.

    The bare admin group is included because discord.py runs a parent group's checks when a
    subcommand is invoked; on its own the group only shows help. Its other subcommands are
    still blocked by their own check.
    """
    name = command.qualified_name
    return name == ADMIN_GROUP or name == f"{ADMIN_GROUP} backup" or name.startswith(f"{ADMIN_GROUP} backup ")
