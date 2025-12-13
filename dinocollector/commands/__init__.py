from ..abc import CompositeMetaClass
from .admin import Admin
from .user import User
from .shop import Shop


class Commands(Admin, User, Shop, metaclass=CompositeMetaClass):
    """Subclass all command classes"""
