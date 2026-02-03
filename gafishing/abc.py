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
        self.data_path: Path
        self.debug_log: list

    @abstractmethod
    def save(self) -> None:
        raise NotImplementedError
