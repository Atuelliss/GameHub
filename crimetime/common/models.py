import discord
import time
from uuid import uuid4

from pydantic import Field

from . import Base
from .. import blackmarket


class Gang(Base):
    """Gang/Group Data Structure"""
    gang_id: str = ""                   # Unique identifier (UUID)
    name: str = ""                      # Gang name (max 25 characters)
    leader_id: int = 0                  # Discord user ID of the gang leader
    members: list[int] = Field(default_factory=list)  # List of member user IDs (max 4, excluding leader)
    created_at: float = 0               # Timestamp of gang creation
    total_earnings: int = 0             # Lifetime earnings for the gang (future stat)

    @property
    def member_count(self) -> int:
        """Total members including leader."""
        return len(self.members) + 1

    @property
    def is_full(self) -> bool:
        """Check if gang is at max capacity (5 total: 1 leader + 4 members)."""
        return len(self.members) >= 4

    def has_member(self, user_id: int) -> bool:
        """Check if a user is in this gang (leader or member)."""
        return user_id == self.leader_id or user_id in self.members

    def add_member(self, user_id: int) -> bool:
        """Add a member to the gang. Returns False if full or already member."""
        if self.is_full or self.has_member(user_id):
            return False
        self.members.append(user_id)
        return True

    def remove_member(self, user_id: int) -> bool:
        """Remove a member from the gang. Cannot remove leader this way."""
        if user_id in self.members:
            self.members.remove(user_id)
            return True
        return False


class User(Base):
    '''Stored User Info'''
    balance: int = 0     #Cash Balance
    gold_bars: int = 0   #Gold Bars Owned
    gems_owned: int = 0  #Gems Owned
    gang_id: str | None = None  # UUID of the gang the user belongs to
    p_wins:   int = 0    #Player Mugging Wins
    p_losses: int = 0    #Player Mugging Losses
    p_bonus:  float = 0  #Player Bonus from Win/Loss Ratio
    pve_win: int = 0     #Basic "Mug" win count.
    pve_loss: int = 0    #Basic "Mug" loss count.
    r_wins:   int = 0    #Player Robbery Wins - Upcoming
    r_losses: int = 0    #Player Robbery Losses - Upcoming
    h_wins:   int = 0    #Player Heist Wins - Upcoming
    h_losses: int = 0    #Player Heist Losses - Upcoming
    pop_up_wins: int = 0 #Player Pop-up Challenge victories - upcoming.
    pop_up_losses: int = 0 #Player Pop-up Challenge losses - upcoming.
    mugclear_count: int = 0   #Number of times Player has used "clearratio"
    player_exp: int = 0   #Total player experience.
    player_level: int = 0 #Future variable for Player level.
    tnl_exp: int = 0 #Exp needed for next level.
    recent_targets: list[int] = Field(default_factory=list)

    # Player worn Inventory bits
    worn_weapon: str | None = None
    worn_head: str | None = None
    worn_chest: str | None = None
    worn_legs: str | None = None
    worn_feet: str | None = None
    worn_consumable: str | None = None

    # Player inventory storage bits
    owned_weapon: dict[str, int] = Field(default_factory=dict)
    owned_head: dict[str, int] = Field(default_factory=dict)
    owned_chest: dict[str, int] = Field(default_factory=dict)
    owned_legs: dict[str, int] = Field(default_factory=dict)
    owned_feet: dict[str, int] = Field(default_factory=dict)
    owned_consumable: dict[str, int] = Field(default_factory=dict)

    # Ratio property sets
    @property # Ratio for player pvp mugging stats
    def p_ratio(self) -> float:
        return round((self.p_wins / self.p_losses) if self.p_losses > 0 else self.p_wins, 2)
    @property
    def p_ratio_str(self) -> str:
        return f"{self.p_wins}:{self.p_losses}"
    @property # Ratio for Player Robbery stats
    def r_ratio(self) -> float:
        return (self.r_wins / self.r_losses) if self.r_losses > 0 else self.r_wins
    @property
    def r_ratio_str(self) -> str:
        return f"{self.r_wins}:{self.r_losses}"
    @property # Ratio for Player Heist stats
    def h_ratio(self) -> float:
        return (self.h_wins / self.h_losses) if self.h_losses > 0 else self.h_wins
    @property
    def h_ratio_str(self) -> str:
        return f"{self.h_wins}:{self.h_losses}"    
    @property  # Ratio for random pop-up mugging challenges
    def pop_up_ratio(self) -> float:
        return (self.pop_up_wins / self.pop_up_losses) if self.pop_up_losses > 0 else self.pop_up_wins    
    @property
    def pop_up_ratio_str(self) -> str:
        return f"{self.pop_up_wins}:{self.pop_up_losses}"
    @property
    def total_pve_mug(self) -> str:
        return f"{self.pve_win}:{self.pve_loss}"
#        return f"{self.mug_pve_win_count}:{self.mug_pve_loss_count}"

    #Update the Users atk bonus above when wearing a weapon.
    @property
    def player_atk_bonus(self) -> float:
        if not self.worn_weapon:
            return 0
        for item in blackmarket.all_items:
            if item["keyword"] == self.worn_weapon:
                return item.get("factor", 0)
        return 0

    #Update the Users def bonus above when wearing armor.
    @property
    def player_def_bonus(self) -> float:
        """Calculate total defense bonus from equipped armor (head, chest, legs, feet)."""
        total = 0.0
        worn_slots = [
            self.worn_head,
            self.worn_chest,
            self.worn_legs,
            self.worn_feet,
        ]
        for keyword in worn_slots:
            if not keyword:
                continue
            for item in blackmarket.all_items:
                if item["keyword"] == keyword:
                    total += item.get("factor", 0)
                    break
        return round(total, 4)  # Rounded for display or comparison

class GuildSettings(Base):
    users: dict[int, User] = Field(default_factory=dict)
    gangs: dict[str, Gang] = Field(default_factory=dict)  # Gang ID -> Gang data
    
    is_mug_enabled: bool = True        # Mugging enabled/disabled
    is_carjacking_enabled: bool = False # Carjacking enabled/disabled
    is_robbery_enabled: bool = False   # Robbery enabled/disabled
    is_heist_enabled: bool = False     # Heist enabled/disabled
    is_pop_up_enabled: bool = False    # Pop-up challenge enabled/disabled

    # Bank functions
    is_bank_enabled: bool = True      # Bank feature enabled/disabled
    bank_interest_rate: float = 0.05  # Interest rate for bank deposits
    bank_max_withdraw: int = 1000000   # Max withdrawal limit per transaction
    is_conversion_enabled: bool = False # Currency conversion enabled/disabled

    # Blackmarket fields
    blackmarket_last_cycle: float = 0           # Timestamp of last cycle
    blackmarket_current_items: list[dict] = Field(default_factory=list)  # Currently available items (4 items)

    def get_user(self, user: discord.User | int) -> User:
        uid = user if isinstance(user, int) else user.id
        return self.users.setdefault(uid, User())

    def get_gang(self, gang_id: str) -> Gang | None:
        """Get a gang by its ID."""
        return self.gangs.get(gang_id)

    def get_gang_by_name(self, name: str) -> Gang | None:
        """Find a gang by name (case-insensitive)."""
        name_lower = name.lower()
        for gang in self.gangs.values():
            if gang.name.lower() == name_lower:
                return gang
        return None

    def create_gang(self, name: str, leader_id: int) -> Gang:
        """Create a new gang and return it."""
        gang_id = str(uuid4())
        gang = Gang(
            gang_id=gang_id,
            name=name,
            leader_id=leader_id,
            members=[],
            created_at=time.time()
        )
        self.gangs[gang_id] = gang
        return gang

    def delete_gang(self, gang_id: str) -> bool:
        """Delete a gang by its ID."""
        if gang_id in self.gangs:
            del self.gangs[gang_id]
            return True
        return False


class DB(Base):
    bar_value: int = 2500
    gem_value: int = 5000
    bank_conversion_enabled: bool = False
    gem_conversion_value: int = 3000

    configs: dict[int, GuildSettings] = Field(default_factory=dict)

    def get_conf(self, guild: discord.Guild | int) -> GuildSettings:
        gid = guild if isinstance(guild, int) else guild.id
        return self.configs.setdefault(gid, GuildSettings())