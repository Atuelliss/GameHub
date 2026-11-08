from ..abc import CompositeMetaClass
from .admin_commands import Admin
from .user_commands import UserCommands


class Commands(Admin, UserCommands, metaclass=CompositeMetaClass):
    """Subclass all command classes"""
