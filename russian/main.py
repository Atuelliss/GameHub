import asyncio
import logging

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from .abc import CompositeMetaClass
from .common.commands import Commands
from .common.gamemodes import GameModes  # Add import for GameModes
from .common.models import DB
from .common.leaderboard import Leaderboard

log = logging.getLogger("red.rroulette")


class Russian(
    Commands, GameModes, Leaderboard, commands.Cog, metaclass=CompositeMetaClass  # Added GameModes
):
    """A game of chance where players risk it all for rewards"""

    __author__ = "Jayar"
    __version__ = "1.0.0"

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.db: DB = DB()

        # States
        self._saving = False
        self.active_games = {}  # Track active games to prevent multiple games per user

    def format_help_for_context(self, ctx: commands.Context):
        helpcmd = super().format_help_for_context(ctx)
        txt = "Version: {}\nAuthor: {}".format(self.__version__, self.__author__)
        return f"{helpcmd}\n\n{txt}"

    async def red_delete_data_for_user(self, *args, **kwargs):
        return

    async def red_get_data_for_user(self, *args, **kwargs):
        return

    async def cog_load(self) -> None:
        asyncio.create_task(self.initialize())

    async def initialize(self) -> None:
        await self.bot.wait_until_red_ready()
        try:
            db_path = cog_data_path(self) / "db.json"  # Specify a filename
            self.db = await asyncio.to_thread(DB.from_file, db_path)
        except FileNotFoundError:
            self.db = DB()  # Create a new DB
            self.save()  # Save the new DB
        except Exception as e:
            log.exception("Error loading database", exc_info=e)
            self.db = DB()  # Fallback to a new DB
        log.info("Config loaded")

    def save(self) -> None:
        async def _save():
            if self._saving:
                return
            try:
                self._saving = True
                db_path = cog_data_path(self) / "db.json"  # Specify a filename
                await asyncio.to_thread(self.db.to_file, db_path)
            except Exception as e:
                log.exception("Failed to save config", exc_info=e)
            finally:
                self._saving = False

        asyncio.create_task(_save())
