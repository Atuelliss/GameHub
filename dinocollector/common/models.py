from typing import List, Dict
import discord
from pydantic import Field

from . import Base
from ..databases.constants import DEFAULT_DISALLOWED_NAMES


class User(Base):
    # User Dino Information
    current_dino_inv: List[dict] = Field(default_factory=list)
    explorer_log: List[dict] = Field(default_factory=list)
    explorer_logs_sold: int = 0
    achievement_log: List[dict] = Field(default_factory=list)
    has_dinocoins: int = 0
    total_dinocoins_earned: int = 0
    has_spent_dinocoins: int = 0
    total_converted_dinocoin: int = 0
    first_dino_ever_caught: str = ""
    first_dino_caught_timestamp: str = ""
    buddy_dino: dict = Field(default_factory=dict)
    buddy_dino_rarity: str = ""
    buddy_bonus_total_gained: int = 0
    buddy_name: str = ""
    current_inventory_upgrade_level: int = 0
    total_ever_claimed: int = 0
    total_ever_sold: int = 0
    total_ever_traded: int = 0
    total_gifts_given: int = 0
    total_gifts_received: int = 0
    total_escaped: int = 0
    has_lure: bool = False
    last_lure_use: float = 0.0
    total_lures_used: int = 0
    total_legendary_caught: int = 0
        
    # Removed current_inventory_size property to enforce use of GuildSettings.inventory_per_upgrade
    # Calculation: base_inventory_size + (current_inventory_upgrade_level * conf.inventory_per_upgrade)


class GuildSettings(Base):
    users: Dict[int, User] = Field(default_factory=dict)
    game_is_enabled: bool = False
    event_mode_enabled: bool = False
    event_active_type: str = ""  # e.g., "valentines", "easter", "halloween", "christmas"
    dino_image_usage: bool = True    # Whether to use dino images in embeds or not
    
    # Shop Settings
    base_inventory_size: int = 20
    price_upgrade: int = 500
    inventory_per_upgrade: int = 10
    maximum_upgrade_amount: int = 8
    price_lure: int = 200
    lure_cooldown: int = 3600     # 1 hour in seconds
    buddy_bonus_enabled: bool = True
    explorer_log_value: int = 7500

    # Admin Settings
    admin_role_id: int = None

    # Discord Currency Integration
    discord_conversion_enabled: bool = False
    discord_conversion_rate: int = 100  # Number of DinoCoins per Discord Currency unit

    # Spawn Settings
    spawn_mode: str = "time"  # "message" or "time"
    spawn_chance: int = 5        # Percent chance (0-100) for message spawn
    spawn_fail_chance: int = 15  # Percent chance (0-100) that a spawn fails (dino escapes)
    spawn_interval: int = 300    # Seconds for time spawn (default 5 mins)
    spawn_cooldown: int = 30     # Seconds cooldown between spawns in message mode
    last_spawn: float = 0.0      # Timestamp of last spawn
    last_spawn_channel_id: int = None # Channel ID of last spawn
    
    disallowed_names: List[str] = Field(default_factory=lambda: list(DEFAULT_DISALLOWED_NAMES))

    allowed_channels: List[int] = Field(default_factory=list)  # Empty means all channels are allowed
    message_cleanup_enabled: bool = False

    # Blacklist Settings
    blacklisted_users: List[int] = Field(default_factory=list)

    def get_user(self, user: discord.User | int) -> User:
        uid = user if isinstance(user, int) else user.id
        return self.users.setdefault(uid, User())


class DB(Base):
    configs: Dict[int, GuildSettings] = Field(default_factory=dict)

    def get_conf(self, guild: discord.Guild | int) -> GuildSettings:
        gid = guild if isinstance(guild, int) else guild.id
        return self.configs.setdefault(gid, GuildSettings())
