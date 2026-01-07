import discord
from typing import ClassVar, List, Dict, Optional
from . import Base
from pydantic import Field

class User(Base):
    first_join: bool = False
    first_cast_timestamp: str = ""
    total_fish_ever_caught: int = 0
    total_fishing_attempts: int = 0
    total_fish_sold: int = 0
    total_fishpoints: int = 0
    most_fishpoints_ever: int = 0
    current_fishmaster_tokens: int = 0 # Unique tokens obtained by catching the largest weight or length of a species of fish.
    most_fishmaster_tokens_ever: int = 0
    
    # Cooldowns (Unix timestamps)
    last_scavenge_timestamp: int = 0  # Last time player searched garbage (12hr cooldown)
    
    # Inventory lists
    current_rod_inventory: List[dict] = Field(default_factory=list)
    current_lure_inventory: List[dict] = Field(default_factory=list)
    current_clothing_inventory: List[dict] = Field(default_factory=list)
    current_fish_inventory: List[dict] = Field(default_factory=list)
    
    # Equipped items (stores inventory index, None if nothing equipped)
    # Using index allows tracking specific items (e.g., rod durability)
    equipped_rod_index: Optional[int] = None
    equipped_lure_index: Optional[int] = None
    equipped_hat_index: Optional[int] = None
    equipped_coat_index: Optional[int] = None
    equipped_boots_index: Optional[int] = None
    
    # Personal records per fish species
    # Format: {"fish_id": {"max_weight": float, "max_length": float, "weight_timestamp": str, "length_timestamp": str}}
    fish_records: Dict[str, dict] = Field(default_factory=dict)
    
    def update_fish_record(self, fish_id: str, weight: float, length: float) -> Dict[str, bool]:
        """
        Update personal records for a fish species.
        
        Returns dict with {"new_weight_record": bool, "new_length_record": bool}
        """
        import time
        
        result = {"new_weight_record": False, "new_length_record": False}
        
        if fish_id not in self.fish_records:
            self.fish_records[fish_id] = {
                "max_weight": 0.0,
                "max_length": 0.0,
                "weight_timestamp": "",
                "length_timestamp": ""
            }
        
        record = self.fish_records[fish_id]
        timestamp = str(int(time.time()))
        
        if weight > record["max_weight"]:
            record["max_weight"] = weight
            record["weight_timestamp"] = timestamp
            result["new_weight_record"] = True
        
        if length > record["max_length"]:
            record["max_length"] = length
            record["length_timestamp"] = timestamp
            result["new_length_record"] = True
        
        return result
    
    def get_fish_record(self, fish_id: str) -> Optional[dict]:
        """Get personal record for a fish species, or None if never caught."""
        return self.fish_records.get(fish_id)
    
    def get_equipped_rod(self) -> Optional[dict]:
        """Get the currently equipped rod, or None."""
        if self.equipped_rod_index is not None and self.equipped_rod_index < len(self.current_rod_inventory):
            return self.current_rod_inventory[self.equipped_rod_index]
        return None
    
    def get_equipped_lure(self) -> Optional[dict]:
        """Get the currently equipped lure, or None."""
        if self.equipped_lure_index is not None and self.equipped_lure_index < len(self.current_lure_inventory):
            lure = self.current_lure_inventory[self.equipped_lure_index]
            # Auto-migrate old format lures to new uses tracking
            if "remaining_uses" not in lure or "uses_per_item" not in lure:
                from ..commands.helper_functions import ensure_lure_uses
                ensure_lure_uses(lure)
            return lure
        return None
    
    def get_equipped_clothing(self, slot: str) -> Optional[dict]:
        """Get equipped clothing for a specific slot (hat, coat, boots), or None."""
        index_map = {
            "hat": self.equipped_hat_index,
            "coat": self.equipped_coat_index,
            "boots": self.equipped_boots_index,
        }
        idx = index_map.get(slot)
        if idx is not None and idx < len(self.current_clothing_inventory):
            item = self.current_clothing_inventory[idx]
            if item.get("slot") == slot:
                return item
        return None
    
    def equip_rod(self, index: int) -> bool:
        """Equip a rod by inventory index. Returns True if successful."""
        if 0 <= index < len(self.current_rod_inventory):
            self.equipped_rod_index = index
            return True
        return False
    
    def equip_lure(self, index: int) -> bool:
        """Equip a lure by inventory index. Returns True if successful."""
        if 0 <= index < len(self.current_lure_inventory):
            self.equipped_lure_index = index
            return True
        return False
    
    def equip_clothing(self, index: int) -> bool:
        """Equip a clothing item by inventory index. Returns True if successful."""
        if 0 <= index < len(self.current_clothing_inventory):
            item = self.current_clothing_inventory[index]
            slot = item.get("slot")
            if slot == "hat":
                self.equipped_hat_index = index
            elif slot == "coat":
                self.equipped_coat_index = index
            elif slot == "boots":
                self.equipped_boots_index = index
            else:
                return False
            return True
        return False
    
    def unequip_rod(self) -> None:
        """Unequip the current rod."""
        self.equipped_rod_index = None
    
    def unequip_lure(self) -> None:
        """Unequip the current lure."""
        self.equipped_lure_index = None
    
    def unequip_clothing(self, slot: str) -> None:
        """Unequip clothing from a specific slot."""
        if slot == "hat":
            self.equipped_hat_index = None
        elif slot == "coat":
            self.equipped_coat_index = None
        elif slot == "boots":
            self.equipped_boots_index = None
    

class GuildSettings(Base):
    users: dict[int, User] = {}

    # Admin Settings
    admin_role_id: int = None
    timezone: str = "UTC"  # Server's preferred timezone (e.g., "America/New_York", "Europe/London")
    hemisphere: str = "north"  # "north" or "south" - affects season calculation
    is_game_enabled: bool = False

    # Game Time Settings
    game_time_multiplier: float = 2.0  # Game days per real day (2.0 = 2 game days per real day)
    game_epoch: float = None  # Unix timestamp when game time started (auto-set on first use)
    days_per_season: int = 28  # Game days per season (28 days * 4 seasons = 112 day game year)

    # Discord Currency Integration
    discord_currency_conversion_enabled: bool = False
    discord_currency_conversion_rate: int = 100  # Number of Game Currency per Discord Currency unit

    DEFAULT_DISALLOWED_NAMES: ClassVar[List[str]] = [
        "admin", "moderator", "owner", "system", "null", "nigger", "nigga", 
        "kook", "gook", "slave", "bitch", "slut", "whore", "cunt", "cock", 
        "schlong", "rape", "dick", "dickhead", "penis", "vagina", "pussy", 
        "twat"
    ]
    disallowed_names: List[str] = Field(default_factory=list)  # User-added names only
    
    def get_all_disallowed_names(self) -> List[str]:
        """Returns combined list of default and user-added disallowed names."""
        return list(set(self.DEFAULT_DISALLOWED_NAMES + self.disallowed_names))

    allowed_channels: List[int] = Field(default_factory=list)  # Empty means all channels are allowed
    message_cleanup_enabled: bool = False

    # Blacklist Settings
    blacklisted_users: List[int] = Field(default_factory=list)

    def get_user(self, user: discord.User | int) -> User:
        uid = user if isinstance(user, int) else user.id
        return self.users.setdefault(uid, User())

class DB(Base):
    configs: dict[int, GuildSettings] = {}

    def get_conf(self, guild: discord.Guild | int) -> GuildSettings:
        gid = guild if isinstance(guild, int) else guild.id
        return self.configs.setdefault(gid, GuildSettings())
