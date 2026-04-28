import asyncio
import logging

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from .abc import CompositeMetaClass
from .commands import Commands
from .common.models import DB
from .listeners import Listeners
from .tasks import TaskLoops

log = logging.getLogger("red.highrollerclub")


class HighRollerClub(
    Commands, Listeners, TaskLoops, commands.Cog, metaclass=CompositeMetaClass
):
    """Description"""

    __author__ = "author name"
    __version__ = "0.0.1"

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.db: DB = DB()

        # States
        self._saving = False

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
        self.db = await asyncio.to_thread(DB.from_file, cog_data_path(self) / "db.json")
        log.info("Config loaded")

    async def cog_unload(self) -> None:
        await asyncio.to_thread(self.db.to_file, cog_data_path(self) / "db.json")

    def save(self) -> None:
        async def _save():
            if self._saving:
                return
            try:
                self._saving = True
                await asyncio.to_thread(self.db.to_file, cog_data_path(self) / "db.json")
            except Exception as e:
                log.exception("Failed to save config", exc_info=e)
            finally:
                self._saving = False

        asyncio.create_task(_save())
