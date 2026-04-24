"""
Pydantic data models for Petcord cog.
"""

from typing import List, Dict, Optional
import discord
from pydantic import Field

from . import Base
from .constants import (
    DEFAULT_FIND_COOLDOWN_MINUTES,
    DEFAULT_HOME_CAPACITY,
    MAX_HOME_CAPACITY,
    DEFAULT_GROWTH_DAY_HOURS,
    GOLD_THRESHOLD,
    SILVER_THRESHOLD,
    BRONZE_THRESHOLD,
    DEFAULT_DISALLOWED_NAMES,
)


class Achievement(Base):
    """Record of an unlocked achievement."""
    id: str
    timestamp: float = 0.0


class DailyCareScore(Base):
    """Tracks care quality for a single day."""
    day_number: int = 0  # Which day of the pet's life
    date_timestamp: float = 0.0  # When this day started
    
    # Component Scores (0-100 each)
    feeding_score: float = 0.0
    happiness_score: float = 0.0
    cleanliness_score: float = 0.0
    energy_score: float = 0.0
    bonus_score: float = 0.0
    
    # Tracking data for calculations
    times_fed: int = 0
    times_played: int = 0
    times_groomed: int = 0
    times_rested: int = 0
    times_petted: int = 0
    times_treated: int = 0
    
    # Time tracking (minutes in critical state)
    minutes_hungry: int = 0  # Minutes below 40 hunger
    minutes_unhappy: int = 0  # Minutes below 50 happiness
    minutes_dirty: int = 0  # Minutes below 30 cleanliness
    minutes_exhausted: int = 0  # Minutes below 20 energy
    
    # Final calculated score
    final_score: float = 0.0  # Weighted average
    rating: str = ""  # "perfect", "excellent", "good", "fair", "poor", "critical"


class Pet(Base):
    """Active pet data."""
    name: str = ""
    species_id: str = ""
    
    # Appearance
    coat_color: str = ""
    pattern: str = ""
    rarity: str = "common"
    
    # Stats (0-100, stored as float for accurate decay, displayed as int)
    hunger: float = 100.0
    happiness: float = 100.0
    cleanliness: float = 100.0
    energy: float = 100.0
    health: float = 100.0
    bond: float = 0.0
    
    # Lifecycle
    age_days: float = 0.0  # Can be fractional for gradual aging
    life_stage: str = "baby"  # baby, juvenile, adult, senior
    ready_to_graduate: bool = False  # True when reached adult, waiting for user interaction
    is_in_home: bool = False  # True once user confirms graduation to Home
    is_immortal: bool = False  # If True, pet never ages or dies
    adopted_timestamp: float = 0.0
    reached_adult_timestamp: float = 0.0  # When pet first reached adult stage
    graduated_timestamp: float = 0.0  # When user confirmed move to Home
    passed_timestamp: float = 0.0  # When passed away (0 = alive)
    death_cause: str = ""  # "old_age", "neglect", or "" (alive)
    last_interaction: float = 0.0
    
    # Growth Phase Tracking (only tracked during Baby/Juvenile)
    growth_daily_scores: List[DailyCareScore] = Field(default_factory=list)
    growth_average_score: float = 0.0  # Running average
    growth_total_days: int = 0  # Days spent in growth phase
    
    # Medal (awarded upon graduation)
    medal: str = ""  # "gold", "silver", "bronze", "" (none)
    medal_score: float = 0.0  # Final average that determined medal
    
    # Action Cooldowns (timestamps)
    last_fed: float = 0.0
    last_played: float = 0.0
    last_groomed: float = 0.0
    last_rested: float = 0.0
    last_treated: float = 0.0
    last_petted: float = 0.0
    
    # Owner Sleep (decay pause)
    decay_paused_until: float = 0.0  # Timestamp when pause expires (0 = not paused)
    last_owner_sleep_date: str = ""  # Date string (YYYY-MM-DD) of last use
    
    # Last known stat tiers (for tier change notifications)
    # Values: "excellent", "good", "fair", "low", "critical"
    last_hunger_tier: str = "excellent"
    last_happiness_tier: str = "excellent"
    last_cleanliness_tier: str = "excellent"
    last_energy_tier: str = "excellent"
    
    # Gift/Transfer tracking
    original_owner_id: Optional[int] = None  # First owner who raised this pet
    previous_owners: List[int] = Field(default_factory=list)  # Transfer history (user IDs)
    last_transferred_timestamp: float = 0.0  # When pet was last gifted (24h cooldown)
    
    # Equipped items (slot -> item_id) for wardrobe system
    equipped_items: Dict[str, str] = Field(default_factory=dict)
    # Example: {"head": "hat_tophat", "neck": "collar_gold"}


class PetMemorial(Base):
    """Record of a passed pet for the memorial."""
    name: str = ""
    species_id: str = ""
    coat_color: str = ""
    pattern: str = ""
    rarity: str = ""
    
    # Life summary
    adopted_timestamp: float = 0.0
    graduated_timestamp: float = 0.0  # 0.0 if died before graduation
    passed_timestamp: float = 0.0
    total_lifespan_days: int = 0
    
    # Death information
    death_cause: str = ""  # "old_age" or "neglect"
    
    # Achievements (only applicable for old_age deaths)
    medal: str = ""  # "" if death_cause == "neglect" (never graduated)
    medal_score: float = 0.0
    final_bond: int = 0
    reached_home: bool = False  # True if pet made it to Home
    
    # Optional epitaph (only allowed for old_age deaths)
    epitaph: str = ""
    epitaph_allowed: bool = True  # False if death_cause == "neglect"


class InventoryItem(Base):
    """Record of an item in user's inventory."""
    item_id: str  # Key from SHOP_DATABASE
    acquired_timestamp: float = 0.0  # When the item was acquired
    acquired_via: str = "purchase"  # "purchase", "daily_freebie", "legendary_reward", "event"


class PetHistoryEntry(Base):
    """Record of a released/abandoned pet."""
    name: str = ""
    species_id: str = ""
    rarity: str = ""
    released_timestamp: float = 0.0
    age_at_release: int = 0
    bond_at_release: int = 0
    reason: str = ""  # "released", "rehomed", etc.


class User(Base):
    """User game data."""
    # Current Growing Pet (Baby/Juvenile stage)
    current_pet: Optional[Pet] = None

    # Pet Item inventory
    current_item_inventory: List[InventoryItem] = Field(default_factory=list)

    # Player Treat Inventory
    current_treat_inventory: Dict[str, int] = Field(default_factory=dict)
    last_shoptreat_used: float = 0.0  # Timestamp of last shop treat usage (6hr cooldown)

    # Player Vitamin Inventory (vitamin_id -> count)
    current_vitamin_inventory: Dict[str, int] = Field(default_factory=dict)
    
    # Pending Death Notification (shown when user next opens petcord)
    warning_notifications: bool = True  # Whether user wants danger warnings (default enabled)
    last_warning_sent: float = 0.0  # Timestamp of last danger warning sent (cooldown)
    last_stat_tier_notification: float = 0.0  # Timestamp of last stat tier change notification
    pending_death_notification: bool = False
    pending_death_pet_name: str = ""
    pending_death_cause: str = ""  # "neglect" or "old_age"
    pending_death_age_days: int = 0
    pending_death_bond: int = 0
    
    # Pet Finding Cooldown
    last_pet_declined: float = 0.0  # Timestamp of last declined pet
    
    # Home - Mature pets (Adult/Senior stage)
    home_pets: List[Pet] = Field(default_factory=list)
    home_capacity: int = DEFAULT_HOME_CAPACITY  # Base capacity (can be admin-boosted)
    
    @property
    def effective_home_capacity(self) -> int:
        """Calculate home capacity based on graduation milestones.
        
        Every 5 graduations unlocks +5 capacity, up to MAX_HOME_CAPACITY.
        Admin-set home_capacity acts as a bonus on top of the base.
        """
        base = DEFAULT_HOME_CAPACITY
        graduation_bonus = (self.total_pets_graduated // 5) * 5
        admin_bonus = max(0, self.home_capacity - DEFAULT_HOME_CAPACITY)
        return min(base + graduation_bonus + admin_bonus, MAX_HOME_CAPACITY)
    
    # Memorial - Passed pets
    memorial: List[PetMemorial] = Field(default_factory=list)
    
    # History (released/abandoned pets)
    pet_history: List[PetHistoryEntry] = Field(default_factory=list)
    total_pets_owned: int = 0
    total_pets_released: int = 0
    pets_abandoned: int = 0  # Pets given up via Abandon button
    total_pets_graduated: int = 0  # Successfully raised to adulthood
    
    # Death Tracking (separated by cause)
    pets_passed_naturally: int = 0  # Pets that died of old age in Home (good!)
    pets_lost_to_neglect: int = 0  # Pets that died from neglect during growth (bad)
    total_pets_passed: int = 0  # Sum of above two (for quick reference)
    
    # Medal Tracking
    most_petcoin_earned: int = 0  # Most petcoin earned    
    gold_medals: int = 0
    silver_medals: int = 0
    bronze_medals: int = 0
    total_medals: int = 0
    best_medal_streak: int = 0  # Consecutive gold medals
    current_medal_streak: int = 0
    petcoin_earned_from_medals: int = 0  # Total petcoin earned from medals
    current_petcoin: int = 0  # Petcoin remaining
    legendarycoin: int = 0  # Legendary currency (for future use)
    most_legendarycoin_earned: int = 0  # Most legendarycoin earned

    # Daily Care Stats (for current growing pet)
    current_day_start: float = 0.0  # Timestamp when current day started
    current_day_scores: Optional[DailyCareScore] = None  # Today's tracking
    care_history: List[DailyCareScore] = Field(default_factory=list)  # All days for current pet
    
    # Care Performance Tracking (tracked at end of each growth day)
    # Each stat is checked at day's end - above 40 = met, below 40 = failed
    hunger_needs_met: int = 0
    hunger_needs_failed: int = 0
    happiness_needs_met: int = 0
    happiness_needs_failed: int = 0
    cleanliness_needs_met: int = 0
    cleanliness_needs_failed: int = 0
    energy_needs_met: int = 0
    energy_needs_failed: int = 0
    
    @property
    def total_needs_met(self) -> int:
        """Total needs met across all stat types."""
        return (self.hunger_needs_met + self.happiness_needs_met + 
                self.cleanliness_needs_met + self.energy_needs_met)
    
    @property
    def total_needs_failed(self) -> int:
        """Total needs failed across all stat types."""
        return (self.hunger_needs_failed + self.happiness_needs_failed + 
                self.cleanliness_needs_failed + self.energy_needs_failed)
    
    # Lifetime Stats
    total_interactions: int = 0
    total_feedings: int = 0
    total_play_sessions: int = 0
    total_grooming_sessions: int = 0
    total_rest_sessions: int = 0
    total_treats_given: int = 0
    total_petting_sessions: int = 0
    longest_pet_lifespan: int = 0
    highest_bond_achieved: int = 0
    
    # Achievements
    achievements: List[Achievement] = Field(default_factory=list)
    
    # Gift/Transfer Statistics
    pets_gifted: int = 0  # Pets given to others
    pets_received: int = 0  # Pets received from others
    last_gift_sent_timestamp: float = 0.0  # Cooldown for sending gifts
    
    # Daily Freebie Tracking
    last_daily_freebie_claim: float = 0.0  # Timestamp of last daily freebie claim
    total_freebies_claimed: int = 0  # Total freebies claimed all-time
    
    # Debug Mode
    debug_mode: bool = False  # If True, log decay info for this user's pets


class GuildSettings(Base):
    """Server-specific settings and user data."""
    users: Dict[int, User] = Field(default_factory=dict)
    game_is_enabled: bool = False
    discord_server_timezone: str = "UTC"  # For accurate daily resets and time-based events
    active_holiday: Optional[str] = None  # e.g., "halloween", "christmas", etc.

    # Pet Finding Settings
    find_cooldown_minutes: int = DEFAULT_FIND_COOLDOWN_MINUTES
    
    # Game Settings
    pet_death_enabled: bool = True  # Whether GROWING pets can die from neglect
    abandoned_pet_shelter: bool = True  # Released pets go to shelter
    
    # Home Settings
    default_home_capacity: int = DEFAULT_HOME_CAPACITY
    max_home_capacity: int = MAX_HOME_CAPACITY
    
    # Growth & Medal Settings
    growth_day_length_hours: int = DEFAULT_GROWTH_DAY_HOURS
    medal_gold_threshold: float = GOLD_THRESHOLD
    medal_silver_threshold: float = SILVER_THRESHOLD
    medal_bronze_threshold: float = BRONZE_THRESHOLD
    
    # Admin Settings
    admin_role_id: Optional[int] = None
    disallowed_names: List[str] = Field(default_factory=lambda: list(DEFAULT_DISALLOWED_NAMES))
    
    # Channel Settings
    allowed_channel_id: Optional[int] = None  # Channel for notifications (deaths, etc.)
    
    # Gift/Transfer Settings
    gift_cooldown_hours: int = 6  # Hours between sending gifts (default 6)
    
    # Blacklist Settings
    blacklisted_users: List[int] = Field(default_factory=list)

    def get_user(self, user: discord.User | int) -> User:
        """Get or create user data."""
        uid = user if isinstance(user, int) else user.id
        return self.users.setdefault(uid, User())


class DB(Base):
    """Root database containing all guild configurations."""
    configs: Dict[int, GuildSettings] = Field(default_factory=dict)

    def get_conf(self, guild: discord.Guild | int) -> GuildSettings:
        """Get or create guild configuration."""
        gid = guild if isinstance(guild, int) else guild.id
        return self.configs.setdefault(gid, GuildSettings())
