from ..abc import CompositeMetaClass
from .admin_commands import Admin
from .user_commands import User


class Commands(Admin, User, metaclass=CompositeMetaClass):
    """Subclass all command classes"""
