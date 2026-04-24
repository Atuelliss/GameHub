from abc import ABC, ABCMeta, abstractmethod

from discord.ext.commands.cog import CogMeta
from redbot.core.bot import Red

from .common.models import DB


class CompositeMetaClass(CogMeta, ABCMeta):
    """Type detection for composite classes."""


class MixinMeta(ABC):
    """Type hinting for mixin classes."""

    def __init__(self, *_args):
        self.bot: Red
        self.db: DB
        self.debug_log: list
        super().__init__(*_args)

    @abstractmethod
    def save(self) -> None:
        raise NotImplementedError
