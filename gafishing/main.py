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

log = logging.getLogger("red.greenacresfishing")


class GreenacresFishing(
    Commands, Listeners, TaskLoops, commands.Cog, metaclass=CompositeMetaClass
):
    """Description"""

    __author__ = "Jayar/Vainne"
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
        
        # Run migrations
        await self._migrate_inventory_format()

    async def _migrate_inventory_format(self) -> None:
        """Migrate old inventory format to new format.
        
        Old format used 'id' key, new format uses 'rod_id' and 'lure_id'.
        Also removes deprecated keys like 'name', 'catch_bonus', and 'equipped'.
        Caps durability to database max values.
        Migrates old 'equipped' boolean to new index-based equipped system.
        """
        from .databases.items import RODS_DATABASE
        
        migrated = False
        
        for guild_id, conf in self.db.configs.items():
            for user_id, user_data in conf.users.items():
                # Migrate rod inventory
                for idx, rod in enumerate(user_data.current_rod_inventory):
                    if "id" in rod and "rod_id" not in rod:
                        rod["rod_id"] = rod.pop("id")
                        migrated = True
                    # Remove deprecated keys
                    for key in ["name", "catch_bonus"]:
                        if key in rod:
                            del rod[key]
                            migrated = True
                    # Migrate old equipped boolean to index-based system
                    if rod.pop("equipped", False) and user_data.equipped_rod_index is None:
                        user_data.equipped_rod_index = idx
                        migrated = True
                    # Cap durability to database max
                    rod_id = rod.get("rod_id")
                    if rod_id and rod_id in RODS_DATABASE:
                        max_durability = RODS_DATABASE[rod_id].get("durability", 50)
                        if rod.get("durability", 0) > max_durability:
                            rod["durability"] = max_durability
                            migrated = True
                
                # Migrate lure inventory
                for idx, lure in enumerate(user_data.current_lure_inventory):
                    if "id" in lure and "lure_id" not in lure:
                        lure["lure_id"] = lure.pop("id")
                        migrated = True
                    # Remove deprecated keys
                    for key in ["name", "catch_bonus"]:
                        if key in lure:
                            del lure[key]
                            migrated = True
                    # Migrate old equipped boolean to index-based system
                    if lure.pop("equipped", False) and user_data.equipped_lure_index is None:
                        user_data.equipped_lure_index = idx
                        migrated = True
                
                # Migrate clothing inventory
                for idx, clothing in enumerate(user_data.current_clothing_inventory):
                    # Migrate old equipped boolean to index-based system
                    if clothing.pop("equipped", False):
                        slot = clothing.get("slot")
                        if slot == "hat" and user_data.equipped_hat_index is None:
                            user_data.equipped_hat_index = idx
                            migrated = True
                        elif slot == "coat" and user_data.equipped_coat_index is None:
                            user_data.equipped_coat_index = idx
                            migrated = True
                        elif slot == "boots" and user_data.equipped_boots_index is None:
                            user_data.equipped_boots_index = idx
                            migrated = True
        
        if migrated:
            log.info("Migrated inventory format to new schema")
            self.save()

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
