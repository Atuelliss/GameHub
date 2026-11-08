from abc import ABC, ABCMeta, abstractmethod
from pathlib import Path

from discord.ext.commands.cog import CogMeta
from redbot.core.bot import Red

from .common.models import DB


class CompositeMetaClass(CogMeta, ABCMeta):
    """Type detection"""


class MixinMeta(ABC):
    """Type hinting"""

    def __init__(self, *_args):
        self.bot: Red
        self.db: DB

    @abstractmethod
    def save(self) -> None:
        raise NotImplementedError

    # Data backups (implemented in main.py, used by the `backup` admin commands)
    @abstractmethod
    def list_backups(self) -> list[Path]:
        raise NotImplementedError

    @abstractmethod
    async def create_backup(self) -> Path:
        raise NotImplementedError

    @abstractmethod
    async def restore_backup(self, source: Path) -> None:
        raise NotImplementedError
