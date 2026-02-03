from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from typing import TypedDict, Optional, Dict, Any, List
from zoneinfo import ZoneInfo
from pathlib import Path
import time
import random
import json

import discord

from ..common.models import DB
from ..databases.fish import FISH_DATABASE
from ..databases.items import HATS_DATABASE, COATS_DATABASE, BOOTS_DATABASE, LURES_DATABASE


def log_debug_catch(debug_log: list, user: discord.User, fish_id: str, fish_data: dict, weight_oz: float, length_in: float, 
                    max_weight_oz: float, max_length_in: float, earned_token: bool, earned_perfect: bool, total_tokens: int):
    """
    Log a fish catch to the in-memory debug log.
    
    Parameters
    ----------
    debug_log : list
        The cog's in-memory debug log list to append to
    user : discord.User
        The user who caught the fish
    fish_id : str
        The fish's database ID/key
    fish_data : dict
        The fish database entry
    weight_oz : float
        Weight caught
    length_in : float
        Length caught
    max_weight_oz : float
        Maximum possible weight
    max_length_in : float
        Maximum possible length
    earned_token : bool
        Whether token was awarded
    earned_perfect : bool
        Whether this was a perfect trophy
    total_tokens : int
        User's total tokens after this catch
    """
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user.id,
            "user_name": f"{user.name}#{user.discriminator}" if user.discriminator != "0" else user.name,
            "fish_id": fish_id,
            "fish_name": fish_data.get("name", "Unknown"),
            "weight_caught_oz": round(weight_oz, 1),
            "weight_max_oz": round(max_weight_oz, 1),
            "is_max_weight": weight_oz == max_weight_oz,
            "length_caught_in": round(length_in, 1),
            "length_max_in": round(max_length_in, 1),
            "is_max_length": length_in == max_length_in,
            "token_awarded": earned_token,
            "perfect_trophy": earned_perfect,
            "total_tokens": total_tokens
        }
        
        debug_log.append(entry)
        
        # Keep log from growing too large (max 1000 entries)
        if len(debug_log) > 1000:
            debug_log.pop(0)
    except Exception as e:
        # Silently fail - debug logging shouldn't break gameplay
        print(f"Debug log error: {e}")


def ensure_lure_uses(lure_dict: dict) -> None:
    """
    Ensure a lure dict has the uses tracking fields.
    Migrates old format to new format if needed.
    
    Parameters
    ----------
    lure_dict : dict
        The lure dictionary to check/update (modified in place)
    """
    if "remaining_uses" not in lure_dict or "uses_per_item" not in lure_dict:
        lure_id = lure_dict.get("lure_id", "")
        lure_info = LURES_DATABASE.get(lure_id, {})
        uses_per_item = lure_info.get("uses", 1)
        quantity = lure_dict.get("quantity", 0)
        
        # Set uses_per_item from database
        lure_dict["uses_per_item"] = uses_per_item
        
        # If no remaining_uses, calculate from quantity
        if "remaining_uses" not in lure_dict:
            lure_dict["remaining_uses"] = quantity * uses_per_item


async def is_channel_allowed(db: DB, guild: discord.Guild, channel_id: int, author: discord.Member = None, bot = None) -> bool:
    """
    Check if a channel is allowed for fishing commands.
    
    Returns True if:
    - The author is an admin (can use commands anywhere)
    - No channels are in allowed_channels (empty = all allowed)
    - The channel_id is in the allowed_channels list
    
    Parameters
    ----------
    db : DB
        The database instance
    guild : discord.Guild
        The Discord guild
    channel_id : int
        The channel ID to check
    author : discord.Member, optional
        The member running the command (for admin check)
    bot : optional
        The bot instance (for Red admin check)
    
    Returns
    -------
    bool
        True if the channel is allowed, False otherwise
    """
    # Check if author is an admin - admins can use commands anywhere
    if author is not None:
        # Check Discord permissions
        if author.guild_permissions.manage_guild or author.guild_permissions.administrator:
            return True
        # Check Red-DiscordBot admin status
        if bot is not None:
            try:
                if await bot.is_admin(author):
                    return True
            except Exception:
                pass
    
    conf = db.get_conf(guild)
    # If no channels are specified, all channels are allowed
    if not conf.allowed_channels:
        return True
    return channel_id in conf.allowed_channels


class Season(Enum):
    SPRING = "Spring"
    SUMMER = "Summer"
    FALL = "Fall"
    WINTER = "Winter"


class TimeOfDay(Enum):
    """Time periods with their hour ranges (in 24-hour game time)."""
    DAWN = ("Dawn", 5, 7, "🌅")
    MORNING = ("Morning", 7, 12, "☀️")
    AFTERNOON = ("Afternoon", 12, 17, "🌤️")
    EVENING = ("Evening", 17, 20, "🌆")
    DUSK = ("Dusk", 20, 21, "🌇")
    NIGHT = ("Night", 21, 5, "🌙")
    
    @property
    def name_str(self) -> str:
        return self.value[0]
    
    @property
    def start_hour(self) -> int:
        return self.value[1]
    
    @property
    def end_hour(self) -> int:
        return self.value[2]
    
    @property
    def emoji(self) -> str:
        return self.value[3]


class GameCalendar(TypedDict):
    """Type for game calendar information."""
    season: str
    day_of_season: int
    year: int
    total_game_days: int


class GameTimeOfDay(TypedDict):
    """Type for game time of day information."""
    name: str
    emoji: str
    hour: int
    minute: int
    is_daytime: bool


# ============================================================================
# SERVER TIME FUNCTIONS
# ============================================================================

def get_server_time(db: DB, guild: discord.Guild | int) -> datetime:
    """Get the current time in the server's configured timezone."""
    conf = db.get_conf(guild)
    return datetime.now(ZoneInfo(conf.timezone))


def get_server_timezone(db: DB, guild: discord.Guild | int) -> ZoneInfo:
    """Get the server's configured timezone object."""
    conf = db.get_conf(guild)
    return ZoneInfo(conf.timezone)


# ============================================================================
# REAL-WORLD SEASON DETECTION
# ============================================================================

def get_real_season(db: DB, guild: discord.Guild | int) -> tuple[Season, int]:
    """
    Get the current real-world season and day within that season based on server timezone and hemisphere.
    
    Season dates (approximate):
    - Spring: Mar 20 - Jun 20 (93 days)
    - Summer: Jun 21 - Sep 22 (94 days)
    - Fall: Sep 23 - Dec 20 (89 days)
    - Winter: Dec 21 - Mar 19 (89 days, 90 in leap year)
    
    Returns:
        Tuple of (Season, day_of_season) where day_of_season is 1-indexed
    """
    conf = db.get_conf(guild)
    now = get_server_time(db, guild)
    
    # Get day of year (1-366)
    day_of_year = now.timetuple().tm_yday
    
    # Season start days (approximate, 1-indexed day of year)
    # Spring: Mar 20 = day 79 (80 in leap year)
    # Summer: Jun 21 = day 172 (173 in leap year)
    # Fall: Sep 23 = day 266 (267 in leap year)
    # Winter: Dec 21 = day 355 (356 in leap year)
    
    # Check for leap year
    is_leap = now.year % 4 == 0 and (now.year % 100 != 0 or now.year % 400 == 0)
    
    spring_start = 80 if is_leap else 79
    summer_start = 173 if is_leap else 172
    fall_start = 267 if is_leap else 266
    winter_start = 356 if is_leap else 355
    
    # Determine season and day within season for Northern Hemisphere
    if day_of_year >= spring_start and day_of_year < summer_start:
        northern_season = Season.SPRING
        day_of_season = day_of_year - spring_start + 1
    elif day_of_year >= summer_start and day_of_year < fall_start:
        northern_season = Season.SUMMER
        day_of_season = day_of_year - summer_start + 1
    elif day_of_year >= fall_start and day_of_year < winter_start:
        northern_season = Season.FALL
        day_of_season = day_of_year - fall_start + 1
    else:
        # Winter wraps around the year
        northern_season = Season.WINTER
        if day_of_year >= winter_start:
            day_of_season = day_of_year - winter_start + 1
        else:
            # We're in the early part of the year (Jan-Mar 19)
            days_in_prev_year = 366 if is_leap else 365
            day_of_season = (days_in_prev_year - winter_start + 1) + day_of_year
    
    # Flip seasons for Southern Hemisphere
    if conf.hemisphere == "south":
        season_flip = {
            Season.SPRING: Season.FALL,
            Season.SUMMER: Season.WINTER,
            Season.FALL: Season.SPRING,
            Season.WINTER: Season.SUMMER,
        }
        return (season_flip[northern_season], day_of_season)
    
    return (northern_season, day_of_season)


# ============================================================================
# GAME TIME FUNCTIONS
# ============================================================================

def _ensure_game_epoch(db: DB, guild: discord.Guild | int) -> float:
    """
    Ensure the game epoch is set. Returns the epoch timestamp.
    If not set, initializes it to the current time.
    """
    conf = db.get_conf(guild)
    if conf.game_epoch is None:
        conf.game_epoch = time.time()
    return conf.game_epoch


def get_total_game_days(db: DB, guild: discord.Guild | int) -> float:
    """
    Calculate total game days elapsed since game epoch.
    
    With default 2.0 multiplier:
    - 1 real day = 2 game days
    - 12 real hours = 1 game day
    """
    conf = db.get_conf(guild)
    epoch = _ensure_game_epoch(db, guild)
    
    real_seconds_elapsed = time.time() - epoch
    real_days_elapsed = real_seconds_elapsed / 86400  # 86400 seconds per day
    game_days_elapsed = real_days_elapsed * conf.game_time_multiplier
    
    return game_days_elapsed


def get_game_calendar(db: DB, guild: discord.Guild | int) -> GameCalendar:
    """
    Get the full game calendar state.
    
    Returns:
        GameCalendar with:
        - season: Current season name (based on real-world season)
        - day_of_season: Actual day number within the real-world season
        - year: Real calendar year
        - total_game_days: Total game days since epoch (for game mechanics)
    """
    total_days = get_total_game_days(db, guild)
    now = get_server_time(db, guild)
    
    # Get real-world season and day within that season
    current_season, day_of_season = get_real_season(db, guild)
    
    return GameCalendar(
        season=current_season.value,
        day_of_season=day_of_season,
        year=now.year,
        total_game_days=int(total_days)
    )


def get_game_time_of_day(db: DB, guild: discord.Guild | int) -> GameTimeOfDay:
    """
    Get the current game time of day.
    
    With 2.0 multiplier, a full game day (24 game hours) = 12 real hours.
    So 1 game hour = 30 real minutes.
    
    Returns:
        GameTimeOfDay with:
        - name: Time period name (Dawn, Morning, Afternoon, Evening, Dusk, Night)
        - emoji: Appropriate emoji for the time
        - hour: Game hour (0-23)
        - minute: Game minute (0-59)
        - is_daytime: True if between 6 AM and 8 PM game time
    """
    conf = db.get_conf(guild)
    total_days = get_total_game_days(db, guild)
    
    # Get fractional part of day (0.0 to 1.0)
    day_fraction = total_days % 1.0
    
    # Convert to hours and minutes
    total_game_minutes = day_fraction * 24 * 60  # Total minutes in game day
    game_hour = int(total_game_minutes // 60)
    game_minute = int(total_game_minutes % 60)
    
    # Determine time period
    time_period = TimeOfDay.NIGHT  # Default
    for tod in TimeOfDay:
        if tod == TimeOfDay.NIGHT:
            # Night wraps around midnight
            if game_hour >= tod.start_hour or game_hour < tod.end_hour:
                time_period = tod
                break
        elif tod.start_hour <= game_hour < tod.end_hour:
            time_period = tod
            break
    
    # Daytime is roughly 6 AM to 8 PM
    is_daytime = 6 <= game_hour < 20
    
    return GameTimeOfDay(
        name=time_period.name_str,
        emoji=time_period.emoji,
        hour=game_hour,
        minute=game_minute,
        is_daytime=is_daytime
    )


def get_game_time_display(db: DB, guild: discord.Guild | int) -> str:
    """
    Get a formatted string showing current game time and calendar.
    
    Example: "☀️ Morning (09:30) - Day 15 of Summer, Year 2"
    """
    calendar = get_game_calendar(db, guild)
    time_of_day = get_game_time_of_day(db, guild)
    
    return (
        f"{time_of_day['emoji']} {time_of_day['name']} "
        f"({time_of_day['hour']:02d}:{time_of_day['minute']:02d}) - "
        f"Day {calendar['day_of_season']} of {calendar['season']}, "
        f"Year {calendar['year']}"
    )


def is_fish_biting_time(db: DB, guild: discord.Guild | int) -> tuple[bool, str]:
    """
    Determine if it's a good time for fish to bite based on game time.
    
    Best times: Dawn, Dusk
    Good times: Morning, Evening
    Okay times: Afternoon
    Slow times: Night
    
    Returns:
        Tuple of (is_good_time: bool, reason: str)
    """
    time_of_day = get_game_time_of_day(db, guild)
    
    if time_of_day['name'] in ("Dawn", "Dusk"):
        return True, "🎣 The fish are very active right now!"
    elif time_of_day['name'] in ("Morning", "Evening"):
        return True, "🎣 Good fishing conditions."
    elif time_of_day['name'] == "Afternoon":
        return True, "🎣 The fish are a bit sluggish in the heat."
    else:  # Night
        return True, "🎣 Night fishing... some species are more active now."


# ============================================================================
# WELCOME FUNCTIONS
# ============================================================================

async def welcome_to_fishing(
    interaction: discord.Interaction,
    db: DB,
    guild: discord.Guild,
    user: discord.Member
) -> discord.Embed:
    """
    Create the welcome embed for first-time players.
    This is shown when a player runs the fish command for the first time.
    
    Args:
        interaction: The Discord interaction
        db: The database instance
        guild: The Discord guild
        user: The Discord member
    
    Returns:
        A Discord embed welcoming the new player
    """
    embed = discord.Embed(
        title="🎣 Welcome to Greenacres Fishing!",
        description=(
            f"Hello **{user.display_name}**! Welcome to the best fishing spot in town!\n\n"
            "Greenacres Fishing is a relaxing fishing game where you can:\n"
            "• 🎣 Catch various fish species\n"
            "• 🌤️ Experience dynamic weather and seasons\n"
            "• 🛒 Buy rods, lures, and bait from the shop\n"
            "• 💰 Sell your catches for FishPoints\n"
            "• 🏆 Compete on the leaderboards\n"
        ),
        color=discord.Color.green()
    )
    
    # Get current game conditions
    calendar = get_game_calendar(db, guild)
    time_of_day = get_game_time_of_day(db, guild)
    
    embed.add_field(
        name="🌍 Current Conditions",
        value=(
            f"**Season:** {calendar['season']}\n"
            f"**Time:** {time_of_day['emoji']} {time_of_day['name']}\n"
            f"**Day:** {calendar['day_of_season']} of {calendar['season']}, Year {calendar['year']}"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🎁 Starter Kit",
        value=(
            "You'll receive:\n"
            "• 🎣 Wooden Canepole\n"
            "• 🍞 10x Breadballs\n"
            "• 💰 100 FishPoints"
        ),
        inline=True
    )
    
    embed.add_field(
        name="💡 Getting Started",
        value=(
            "1. Click **Go Fishing** and select a location to start!\n"
            "2. Cast your line and wait for a bite\n"
            "3. Sell your fish for FishPoints\n"
            "4. Upgrade your gear at the Bait Shop"
        ),
        inline=True
    )
    
    embed.set_footer(text="Click 'Start Fishing!' below to begin your adventure!")
    
    return embed


async def setup_new_player(db: DB, guild: discord.Guild, user: discord.Member) -> None:
    """
    Set up a new player with starter items and mark them as joined.
    
    Args:
        db: The database instance
        guild: The Discord guild
        user: The Discord member
    """
    import time
    
    conf = db.get_conf(guild)
    user_data = conf.get_user(user)
    
    # Mark as joined
    user_data.first_join = True
    user_data.first_cast_timestamp = str(int(time.time()))
    
    # Give starter items
    user_data.total_fishpoints = 100
    user_data.most_fishpoints_ever = 100  # Track starting FP as initial max
    
    # Add wooden canepole and equip it
    user_data.current_rod_inventory.append({
        "rod_id": "wooden_canepole",
        "durability": 50,
    })
    user_data.equip_rod(0)  # Equip the first rod
    
    # Add starter bait (breadballs) and equip it
    user_data.current_lure_inventory.append({
        "lure_id": "breadballs",
        "quantity": 10,
        "remaining_uses": 10,  # 10 breadballs × 1 use each
        "uses_per_item": 1,
    })
    user_data.equip_lure(0)  # Equip the first lure


# =============================================================================
# FISHING SESSION STATE
# =============================================================================

class FishingPhase(Enum):
    """Phases of the fishing process."""
    IDLE = "idle"                    # Not actively fishing
    CASTING = "casting"              # Line is being cast
    WAITING = "waiting"              # Waiting for a bite
    RETRIEVING = "retrieving"        # Pulling in line, no fish
    FISH_FOLLOWING = "following"     # Fish is following the lure
    FISH_STRIKE = "strike"           # Fish has struck, need to set hook
    FIGHTING = "fighting"            # Fighting the fish
    TENSION_HIGH = "tension"         # Line is tight, don't reel!
    LANDED = "landed"                # Fish has been landed
    ESCAPED = "escaped"              # Fish got away


@dataclass
class FishingSession:
    """Tracks the state of an active fishing session."""
    
    # Location info
    location: str = "pond"
    water_type: str = "freshwater"
    
    # Equipped rod
    rod_id: Optional[str] = None
    
    # Current phase
    phase: FishingPhase = FishingPhase.IDLE
    
    # Line state
    line_distance: int = 0           # Distance in feet (increments of 5)
    max_distance: int = 0            # Original cast distance
    
    # Fish info (once hooked)
    fish_id: Optional[str] = None
    fish_data: Optional[Dict[str, Any]] = None
    fish_weight_oz: float = 0.0
    fish_length_inches: float = 0.0
    is_max_size: bool = False        # True if this is a trophy fish
    
    # Attempt tracking
    successful_interactions: int = 0
    botched_attempts: int = 0
    max_botched: int = 3             # 3 botched = line snaps
    
    # Gear bonus (set from user's equipped gear)
    luck_bonus: int = 0              # Total luck from hat/coat/boots
    
    # Timing
    last_action_time: float = field(default_factory=time.time)
    timeout_seconds: float = 3.0     # Player has 3 seconds to respond
    
    # Messages for dynamic updates
    status_messages: List[str] = field(default_factory=list)
    
    # Event tracking to prevent lockups
    last_event_was_tension: bool = False  # Track if last event was tension
    
    def add_message(self, msg: str):
        """Add a status message."""
        self.status_messages.append(msg)
        # Keep only last 5 messages
        if len(self.status_messages) > 5:
            self.status_messages.pop(0)
    
    def reset_timer(self):
        """Reset the action timer."""
        self.last_action_time = time.time()
    
    def is_timed_out(self) -> bool:
        """Check if the player has timed out."""
        return (time.time() - self.last_action_time) > self.timeout_seconds
    
    def reel_in(self, feet: int = 5, count_success: bool = True):
        """Reel in some line.
        
        Parameters
        ----------
        feet : int
            How many feet to reel in.
        count_success : bool
            Whether this should count as a successful interaction.
            Set to False for passive retrieval without a fish.
        """
        self.line_distance = max(0, self.line_distance - feet)
        if count_success:
            self.successful_interactions += 1
        self.reset_timer()
    
    def fish_pulls_out(self, feet: int = 5):
        """Fish pulls out more line (botched attempt)."""
        self.line_distance += feet
        self.botched_attempts += 1
        self.reset_timer()
    
    def is_line_snapped(self) -> bool:
        """Check if the line has snapped from too many botched attempts."""
        return self.botched_attempts >= self.max_botched
    
    def is_fish_landed(self) -> bool:
        """Check if the fish has been landed."""
        return self.line_distance <= 0 and self.fish_id is not None


# =============================================================================
# FISH SELECTION AND GENERATION
# =============================================================================

def get_eligible_fish(
    location: str,
    water_type: str,
    season: str,
    weather_type: str,
    bait_id: str,
    rod_id: Optional[str] = None,
    line_integrity: float = 1.0
) -> List[tuple]:
    """
    Get list of eligible fish with their spawn weights.
    
    Returns list of (fish_id, fish_data, weight) tuples.
    Weight is based on rarity, season, weather, bait match, rod requirements, and line integrity.
    
    Parameters
    ----------
    rod_id : Optional[str]
        The ID of the equipped rod. Used to filter fish with required_rod restrictions.
    line_integrity : float
        Line integrity from 0.2 to 1.0. Lower values filter out rarer fish.
    """
    eligible = []
    
    # Get allowed rarities based on line integrity
    allowed_rarities = get_allowed_rarities(line_integrity)
    
    for fish_id, fish_data in FISH_DATABASE.items():
        # Check water type match
        fish_water_type = fish_data.get("water_type")
        if fish_water_type not in [water_type, "both"]:
            continue
        
        # Check location match
        if location not in fish_data.get("locations", []):
            continue
        
        # Check rod requirement
        required_rod = fish_data.get("required_rod")
        if required_rod is not None and rod_id != required_rod:
            continue
        
        # Check rarity against line integrity allowance
        rarity = fish_data.get("rarity", "common")
        if rarity not in allowed_rarities:
            continue
        
        # Base weight from rarity
        rarity_weights = {
            "common": 100,
            "uncommon": 50,
            "rare": 20,
            "epic": 5,
            "legendary": 1
        }
        weight = rarity_weights.get(rarity, 50)
        
        # Season modifier
        best_season = fish_data.get("best_season")
        worst_season = fish_data.get("worst_season")
        season_lower = season.lower()
        
        if best_season and best_season.lower() == season_lower:
            weight *= 2.0  # Double chance in best season
        elif worst_season and worst_season.lower() == season_lower:
            weight *= 0.15  # 15% chance in worst season
        
        # Weather modifier
        best_weather = fish_data.get("best_weather")
        if best_weather:
            weather_lower = weather_type.lower()
            if best_weather.lower() == weather_lower:
                weight *= 1.5  # 50% boost in preferred weather
        
        # Bait modifier
        preferred_bait = fish_data.get("preferred_bait", [])
        if "any" in preferred_bait or bait_id in preferred_bait:
            weight *= 2.0  # Double chance with right bait
        else:
            weight *= 0.25  # 25% chance with wrong bait
        
        if weight > 0:
            eligible.append((fish_id, fish_data, weight))
    
    return eligible


def select_fish(
    location: str,
    water_type: str,
    season: str,
    weather_type: str,
    bait_id: str,
    rod_id: Optional[str] = None,
    line_integrity: float = 1.0
) -> Optional[tuple]:
    """
    Select a random fish based on conditions.
    
    Returns (fish_id, fish_data) or None if no fish available.
    
    Parameters
    ----------
    line_integrity : float
        Line integrity from 0.2 to 1.0. Lower values filter out rarer fish.
    """
    eligible = get_eligible_fish(location, water_type, season, weather_type, bait_id, rod_id, line_integrity)
    
    if not eligible:
        return None
    
    # Weighted random selection
    total_weight = sum(w for _, _, w in eligible)
    roll = random.uniform(0, total_weight)
    
    cumulative = 0
    for fish_id, fish_data, weight in eligible:
        cumulative += weight
        if roll <= cumulative:
            return (fish_id, fish_data)
    
    # Fallback (shouldn't happen)
    return eligible[0][:2] if eligible else None


def calculate_gear_luck_bonus(user_data) -> int:
    """
    Calculate total luck bonus from equipped gear (hat, coat, boots).
    
    Parameters
    ----------
    user_data : User
        The user's data model.
    
    Returns
    -------
    int
        Total luck bonus (0-9 max with full FishMaster gear).
    """
    total_luck = 0
    
    # Check hat
    hat = user_data.get_equipped_clothing("hat")
    if hat:
        hat_info = HATS_DATABASE.get(hat.get("item_id", ""), {})
        total_luck += hat_info.get("luck_bonus", 0)
    
    # Check coat
    coat = user_data.get_equipped_clothing("coat")
    if coat:
        coat_info = COATS_DATABASE.get(coat.get("item_id", ""), {})
        total_luck += coat_info.get("luck_bonus", 0)
    
    # Check boots
    boots = user_data.get_equipped_clothing("boots")
    if boots:
        boots_info = BOOTS_DATABASE.get(boots.get("item_id", ""), {})
        total_luck += boots_info.get("luck_bonus", 0)
    
    return total_luck


def generate_fish_size(fish_data: Dict[str, Any], luck_bonus: int = 0) -> tuple:
    """
    Generate weight and length for a caught fish.
    
    Returns (weight_oz, length_inches, is_max_size).
    Base 0.25% chance of being maximum size (trophy), increased by luck.
    
    Parameters
    ----------
    fish_data : Dict[str, Any]
        The fish's data from FISH_DATABASE.
    luck_bonus : int
        Total luck bonus from equipped gear (0-9).
        - Increases trophy chance by 0.01% per luck point
        - Shifts weight distribution toward larger fish
    
    Returns
    -------
    tuple
        (weight_oz, length_inches, is_max_size)
    """
    min_weight = fish_data.get("min_weight_oz", 1.0)
    max_weight = fish_data.get("max_weight_oz", 10.0)
    max_length = fish_data.get("max_length_inches", 10.0)
    
    # Trophy chance: 0.25% base + 0.01% per luck point
    # Max luck (9) = 0.25% + 0.09% = 0.34% trophy chance
    trophy_chance = 0.0025 + (luck_bonus * 0.0001)
    
    if random.random() < trophy_chance:
        # Randomly determine if max weight, max length, or both
        roll = random.random()
        if roll < 0.33:  # 33% chance for max weight only
            is_max_weight = True
            is_max_length = False
        elif roll < 0.66:  # 33% chance for max length only
            is_max_weight = False
            is_max_length = True
        else:  # 34% chance for both (true trophy)
            is_max_weight = True
            is_max_length = True
        
        # Generate the actual values
        weight = max_weight if is_max_weight else random.triangular(min_weight, max_weight, min_weight + (max_weight - min_weight) * 0.7)
        
        if is_max_length:
            length = max_length
        else:
            weight_ratio = (weight - min_weight) / (max_weight - min_weight) if max_weight > min_weight else 0.5
            min_length = max_length * 0.4
            length = min_length + (max_length - min_length) * weight_ratio
            length *= random.uniform(0.95, 1.05)
            length = min(length, max_length)
        
        return (round(weight, 1), round(length, 1), is_max_weight or is_max_length)
    
    # Size distribution shifts toward larger fish with luck
    # Base mode is at 30% of range, luck shifts it toward 50%
    # Each luck point shifts mode by ~2%
    base_mode_ratio = 0.3 + (luck_bonus * 0.02)  # 0.3 to 0.48 with max luck
    base_mode_ratio = min(base_mode_ratio, 0.5)  # Cap at 50%
    
    mode = min_weight + (max_weight - min_weight) * base_mode_ratio
    weight = random.triangular(min_weight, max_weight, mode)
    
    # Length correlates with weight (roughly)
    weight_ratio = (weight - min_weight) / (max_weight - min_weight) if max_weight > min_weight else 0.5
    min_length = max_length * 0.4  # Minimum is 40% of max length
    length = min_length + (max_length - min_length) * weight_ratio
    
    # Add some randomness to length
    length *= random.uniform(0.95, 1.05)
    length = min(length, max_length)
    
    return (round(weight, 1), round(length, 1), False)


def calculate_cast_distance(location: str = "pond") -> int:
    """
    Calculate a random cast distance in feet (increments of 5).
    Base range: 20-100 feet.
    Ocean/River: +20-45 feet (40-145 feet total).
    
    Parameters
    ----------
    location : str
        The fishing location (pond, lake, river, ocean).
    
    Returns
    -------
    int
        Cast distance in feet.
    """
    # Base distance from 20 to 100 feet in 5-foot increments
    base_distance = random.choice([20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100])
    
    # Add extra distance for ocean and river locations
    if location.lower() in ["ocean", "river"]:
        extra_distance = random.choice([20, 25, 30, 35, 40, 45])
        return base_distance + extra_distance
    
    return base_distance


def calculate_line_integrity(current_distance: int, original_distance: int, grace_feet: int = 15) -> float:
    """
    Calculate line integrity based on how much line was reeled in before a bite.
    
    Players get a grace period of free reeling (default 15ft) before penalties apply.
    This prevents short RNG casts from being penalized.
    
    Parameters
    ----------
    current_distance : int
        Current line distance in feet.
    original_distance : int
        Original cast distance in feet.
    grace_feet : int
        Amount of "free" reeling allowed before penalties (default 15ft).
    
    Returns
    -------
    float
        Line integrity from 0.2 (minimum) to 1.0 (full).
        - 1.0 = No penalty (within grace distance)
        - 0.2 = Maximum penalty (reeled far beyond grace)
    """
    if original_distance <= 0:
        return 1.0
    
    feet_reeled = original_distance - current_distance
    
    # Within grace distance = no penalty
    if feet_reeled <= grace_feet:
        return 1.0
    
    # Calculate penalty based on how much beyond grace they reeled
    excess_reeled = feet_reeled - grace_feet
    remaining_after_grace = original_distance - grace_feet
    
    if remaining_after_grace <= 0:
        return 1.0
    
    # Linear falloff from 1.0 to 0.2 (floor)
    integrity = 1.0 - (excess_reeled / remaining_after_grace) * 0.8
    return max(0.2, integrity)


def get_allowed_rarities(line_integrity: float) -> List[str]:
    """
    Get list of allowed fish rarities based on line integrity.
    
    Parameters
    ----------
    line_integrity : float
        Line integrity from 0.2 to 1.0.
    
    Returns
    -------
    List[str]
        List of allowed rarity strings.
    """
    if line_integrity >= 0.8:
        # Full access to all rarities
        return ["common", "uncommon", "rare", "epic", "legendary"]
    elif line_integrity >= 0.5:
        # No legendary
        return ["common", "uncommon", "rare", "epic"]
    elif line_integrity >= 0.3:
        # No epic or legendary
        return ["common", "uncommon", "rare"]
    else:
        # Common and uncommon only
        return ["common", "uncommon"]


def check_fish_interest(
    location: str,
    water_type: str,
    season: str,
    weather_type: str,
    bait_id: str,
    luck_modifier: float = 1.0,
    rod_id: Optional[str] = None,
    line_integrity: float = 1.0
) -> bool:
    """
    Check if a fish is interested based on conditions.
    
    Returns True if a fish shows interest.
    Base chance is 30%, modified by conditions and line integrity.
    
    Parameters
    ----------
    line_integrity : float
        Line integrity from 0.2 to 1.0. Lower values reduce bite chance.
    """
    base_chance = 0.30
    
    # Get number of eligible fish - more fish = higher chance
    eligible = get_eligible_fish(location, water_type, season, weather_type, bait_id, rod_id, line_integrity)
    if not eligible:
        return False
    
    # More eligible fish = slightly higher chance
    fish_modifier = min(1.0 + len(eligible) * 0.02, 1.5)
    
    # Apply luck modifier from gear/stats
    base_final = base_chance * fish_modifier * luck_modifier
    
    # Apply line integrity penalty to bite chance
    # Integrity of 1.0 = no penalty, 0.2 = 20% of normal bite rate
    final_chance = base_final * line_integrity
    
    return random.random() < final_chance


# =============================================================================
# FISHING PROCESS FUNCTIONS
# =============================================================================

def create_fishing_session(
    location: str,
    water_type: str,
    luck_bonus: int = 0,
    rod_id: Optional[str] = None
) -> FishingSession:
    """
    Create a new fishing session.
    
    Parameters
    ----------
    location : str
        The fishing location (pond, lake, river, ocean).
    water_type : str
        The water type (freshwater, saltwater).
    luck_bonus : int
        Total luck bonus from equipped gear (hat, coat, boots).
        Affects fish size distribution and trophy chance.
    rod_id : Optional[str]
        The ID of the equipped rod.
    
    Returns
    -------
    FishingSession
        A new fishing session object.
    """
    session = FishingSession(
        location=location,
        water_type=water_type,
        phase=FishingPhase.IDLE,
        luck_bonus=luck_bonus,
        rod_id=rod_id
    )
    return session


def cast_line(session: FishingSession) -> str:
    """
    Cast the fishing line into the water.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    
    Returns
    -------
    str
        A message describing the cast.
    """
    distance = calculate_cast_distance(session.location)
    session.line_distance = distance
    session.max_distance = distance
    session.phase = FishingPhase.WAITING
    session.reset_timer()
    session.botched_attempts = 0
    session.successful_interactions = 0
    
    msg = f"*You cast your line {distance} feet into the water.*"
    session.add_message(msg)
    return msg


def check_for_bite(
    session: FishingSession,
    season: str,
    weather_type: str,
    bait_id: str,
    luck_modifier: float = 1.0
) -> tuple:
    """
    Check if a fish bites after the waiting period.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    season : str
        Current game season.
    weather_type : str
        Current weather type.
    bait_id : str
        The equipped bait/lure ID.
    luck_modifier : float
        Luck modifier from gear/stats.
    
    Returns
    -------
    tuple
        (bool interested, str message)
    """
    # Calculate line integrity based on how much was reeled in before bite
    line_integrity = calculate_line_integrity(session.line_distance, session.max_distance)
    
    interested = check_fish_interest(
        session.location,
        session.water_type,
        season,
        weather_type,
        bait_id,
        luck_modifier,
        session.rod_id,
        line_integrity
    )
    
    if interested:
        # Fish is following!
        session.phase = FishingPhase.FISH_FOLLOWING
        msg = "*As you pull in a bit of the line, you get a sense that something is following your bait.*"
    else:
        # Nothing biting - add hint if line integrity is low
        if line_integrity < 0.5:
            msg = "*After a bit of time you believe nothing is biting. The fish seem wary of your shortened line...*"
        else:
            msg = "*After a bit of time you believe nothing is biting.*"
    
    session.add_message(msg)
    session.reset_timer()
    return (interested, msg)


def retrieve_line(session: FishingSession) -> str:
    """
    Retrieve some line when nothing is biting.
    This does NOT count as a successful interaction.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    
    Returns
    -------
    str
        A message describing the retrieval.
    """
    session.reel_in(5, count_success=False)  # Don't count as success
    session.phase = FishingPhase.RETRIEVING
    
    if session.line_distance <= 0:
        msg = "*You've reeled in all your line.*"
        session.phase = FishingPhase.IDLE
    else:
        msg = f"*You reel in a bit of line. Your lure is now {session.line_distance} feet out.*"
    
    session.add_message(msg)
    return msg


def fish_strikes(
    session: FishingSession,
    season: str,
    weather_type: str,
    bait_id: str
) -> tuple:
    """
    A fish strikes the lure! Player must set the hook.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    season : str
        Current game season.
    weather_type : str
        Current weather type.
    bait_id : str
        The equipped bait/lure ID.
    
    Returns
    -------
    tuple
        (fish_id, fish_data, message) or (None, None, message) if fish swims away.
    """
    # 50/50 chance the fish strikes or swims away
    if random.random() < 0.5:
        # Calculate line integrity for fish selection (affects rarity)
        line_integrity = calculate_line_integrity(session.line_distance, session.max_distance)
        
        # Fish strikes!
        result = select_fish(
            session.location,
            session.water_type,
            season,
            weather_type,
            bait_id,
            session.rod_id,
            line_integrity
        )
        
        if result:
            fish_id, fish_data = result
            session.fish_id = fish_id
            session.fish_data = fish_data
            session.phase = FishingPhase.FISH_STRIKE
            session.reset_timer()
            session.timeout_seconds = 5.0  # 5 seconds to set hook
            
            msg = "*Suddenly you feel a sharp tug on your line!!*"
            session.add_message(msg)
            return (fish_id, fish_data, msg)
    
    # Fish swam away
    session.phase = FishingPhase.WAITING
    msg = "*The fish loses interest and swims away.*"
    session.add_message(msg)
    session.reset_timer()
    return (None, None, msg)


def attempt_set_hook(session: FishingSession, user_data=None) -> tuple:
    """
    Attempt to set the hook when the fish strikes.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    user_data : User, optional
        User data for checking pending spawns (admin testing).
    
    Returns
    -------
    tuple
        (bool success, str message)
    """
    if session.is_timed_out():
        # Too slow! Fish spits out the hook
        session.phase = FishingPhase.WAITING
        session.fish_id = None
        session.fish_data = None
        session.timeout_seconds = 3.0  # Reset to normal timeout
        msg = "*Too slow! The fish spits out the hook and swims away.*"
        session.add_message(msg)
        return (False, msg)
    
    # Check for admin-spawned fish
    if user_data and hasattr(user_data, 'pending_spawn') and user_data.pending_spawn:
        spawn = user_data.pending_spawn
        
        # Override the fish type if specified in spawn
        from ..databases.fish import FISH_DATABASE
        spawn_fish_id = spawn.get("fish_id")
        if spawn_fish_id and spawn_fish_id in FISH_DATABASE:
            session.fish_id = spawn_fish_id
            session.fish_data = FISH_DATABASE[spawn_fish_id]
        
        fish_data = session.fish_data
        
        # Parse weight
        if spawn["weight"] == "max":
            weight = fish_data.get("max_weight_oz", 10.0)
        elif spawn["weight"] == "random":
            weight, _, _ = generate_fish_size(fish_data, session.luck_bonus)
        else:
            weight = float(spawn["weight"])
        
        # Parse length
        if spawn["length"] == "max":
            length = fish_data.get("max_length_inches", 10.0)
        elif spawn["length"] == "random":
            _, length, _ = generate_fish_size(fish_data, session.luck_bonus)
        else:
            length = float(spawn["length"])
        
        # Determine if max size
        is_max = (weight == fish_data.get("max_weight_oz")) or (length == fish_data.get("max_length_inches"))
        
        # Clear the spawn
        user_data.pending_spawn = None
    else:
        # Normal fish generation
        weight, length, is_max = generate_fish_size(session.fish_data, session.luck_bonus)
    
    session.fish_weight_oz = weight
    session.fish_length_inches = length
    session.is_max_size = is_max
    
    session.phase = FishingPhase.FIGHTING
    session.reel_in(5)  # Initial pull
    session.timeout_seconds = 3.0  # Back to normal timeout
    
    msg = "*You pull back sharply on the rod and set the hook. All slack goes out of the line as you begin to reel in your catch.*"
    session.add_message(msg)
    return (True, msg)


def get_fight_event(session: FishingSession) -> tuple:
    """
    Get the next event during the fish fight.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    
    Returns
    -------
    tuple
        (FishingPhase next_phase, str message, bool should_reel)
        should_reel: True if player should reel, False if they should wait.
    """
    fish_name = session.fish_data.get("name", "fish") if session.fish_data else "fish"
    
    # Random fight events
    events = [
        (FishingPhase.FIGHTING, f"*The {fish_name} thrashes about wildly in the water!*", True),
        (FishingPhase.FIGHTING, "*Your line cuts through the water as the fish darts left!*", True),
        (FishingPhase.FIGHTING, "*You feel strong resistance as the fish fights back!*", True),
        (FishingPhase.TENSION_HIGH, "*Your line tension goes incredibly tight as your rod bends down sharply!*", False),
        (FishingPhase.TENSION_HIGH, "*The rod nearly bends in half! Don't reel or the line will snap!*", False),
        (FishingPhase.FIGHTING, f"*A loud splash can be heard as the {fish_name} breaches the surface and crashes back down under the water!*", True),
        (FishingPhase.FIGHTING, "*The fish is tiring! Keep reeling!*", True),
    ]
    
    # ANTI-LOCKUP: Prevent consecutive tension events
    # If the last event was tension, force this one to be fighting
    if session.last_event_was_tension:
        # Guarantee a fighting event so player can make progress
        event = random.choice([e for e in events if e[0] == FishingPhase.FIGHTING])
        phase, msg, should_reel = event
        session.phase = phase
        session.last_event_was_tension = False
        session.add_message(msg)
        session.reset_timer()
        return (phase, msg, should_reel)
    
    # Dynamic tension probability based on line distance
    # As fish gets closer (lower distance), tension events become more likely
    # Assume fish started around 50-100 feet away, scale tension from 25% to 75%
    current_distance = session.line_distance
    
    # Calculate tension probability based on current distance
    # At 50+ feet: 25% tension, decreasing to 75% tension at 0 feet
    if current_distance >= 50:
        tension_probability = 0.25
    elif current_distance <= 0:
        tension_probability = 0.75
    else:
        # Linear scale from 25% at 50ft to 75% at 0ft
        distance_ratio = current_distance / 50.0  # 1.0 at 50ft, 0.0 at 0ft
        tension_probability = 0.75 - (distance_ratio * 0.5)  # 0.75 at 0ft, 0.25 at 50ft
    
    # Weight toward fighting events (reel) vs tension events (wait)
    if random.random() < tension_probability:
        # Tension event - fish fights harder as it gets closer
        event = random.choice([e for e in events if e[0] == FishingPhase.TENSION_HIGH])
        session.last_event_was_tension = True
    else:
        # Fighting event - safe to reel
        event = random.choice([e for e in events if e[0] == FishingPhase.FIGHTING])
        session.last_event_was_tension = False
    
    phase, msg, should_reel = event
    session.phase = phase
    session.add_message(msg)
    session.reset_timer()
    
    return (phase, msg, should_reel)


def process_reel_attempt(session: FishingSession, did_reel: bool) -> tuple:
    """
    Process a reel attempt during the fight.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    did_reel : bool
        True if the player clicked reel, False if they waited.
    
    Returns
    -------
    tuple
        (bool success, str message, bool fish_landed)
    """
    fish_name = session.fish_data.get("name", "fish") if session.fish_data else "fish"
    
    if session.phase == FishingPhase.TENSION_HIGH:
        # During high tension, player should NOT reel
        if did_reel:
            # They reeled during high tension - bad!
            if session.is_line_snapped():
                session.phase = FishingPhase.ESCAPED
                msg = f"*SNAP! The line breaks from too much tension! The {fish_name} escapes!*"
                session.add_message(msg)
                return (False, msg, False)
            else:
                session.fish_pulls_out(5)  # This increments botched_attempts
                msg = f"*The line strains dangerously! The fish pulls out more line! ({session.botched_attempts}/{session.max_botched} mistakes)*"
                session.add_message(msg)
                return (False, msg, False)
        else:
            # They waited correctly!
            session.successful_interactions += 1
            msg = "*The tension eases as the fish tires a bit.*"
            session.phase = FishingPhase.FIGHTING
            session.add_message(msg)
            return (True, msg, False)
    
    elif session.phase == FishingPhase.FIGHTING:
        # During fighting, player SHOULD reel
        if did_reel:
            # Good, they reeled!
            session.reel_in(5)
            
            if session.is_fish_landed():
                session.phase = FishingPhase.LANDED
                return (True, "", True)  # Message handled by land_fish
            else:
                msg = f"*You reel in hard! The {fish_name} is now {session.line_distance} feet out.*"
                session.add_message(msg)
                return (True, msg, False)
        else:
            # They didn't reel when they should have - timeout
            if session.is_timed_out():
                session.botched_attempts += 1
                if session.is_line_snapped():
                    session.phase = FishingPhase.ESCAPED
                    msg = f"*The {fish_name} makes a powerful run and snaps the line! It got away!*"
                    session.add_message(msg)
                    return (False, msg, False)
                else:
                    session.fish_pulls_out(5)
                    msg = f"*You hesitated too long! The fish gains traction and pulls out more line! ({session.botched_attempts}/{session.max_botched} mistakes)*"
                    session.add_message(msg)
                    return (False, msg, False)
    
    return (True, "", False)


def land_the_fish(session: FishingSession, user_data, debug_log: list = None, user_obj: discord.User = None) -> tuple:
    """
    Land the fish and add it to inventory.
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    user_data : User
        The user's data model.
    debug_log : list, optional
        In-memory debug log list for debug logging
    user_obj : discord.User, optional
        Discord user object for debug logging
    
    Returns
    -------
    tuple
        (str message, bool is_record, bool earned_token, dict debug_info)
    """
    fish_name = session.fish_data.get("name", "fish") if session.fish_data else "fish"
    weight_oz = session.fish_weight_oz
    length_in = session.fish_length_inches
    
    # Convert weight for display
    if weight_oz >= 16:
        weight_lbs = weight_oz / 16
        weight_display = f"{weight_lbs:.1f} lbs"
    else:
        weight_display = f"{weight_oz:.1f} oz"
    
    length_display = f"{length_in:.1f} inches"
    
    # Check for FishMaster token (max weight OR max length)
    # This needs to happen before adding to inventory so is_trophy is correct
    max_weight_oz = session.fish_data.get("max_weight_oz", 0)
    max_length_inches = session.fish_data.get("max_length_inches", 0)
    
    is_max_weight = (weight_oz == max_weight_oz)
    is_max_length = (length_in == max_length_inches)
    earned_token = is_max_weight or is_max_length
    earned_perfect_trophy = is_max_weight and is_max_length  # Both max - placeholder for future reward
    
    # Add fish to inventory
    fish_entry = {
        "fish_id": session.fish_id,
        "weight_oz": weight_oz,
        "length_inches": length_in,
        "location": session.location,
        "is_trophy": earned_token,  # True if either max weight or max length
        "fishpoints": session.fish_data.get("base_fishpoints", 10)
    }
    user_data.current_fish_inventory.append(fish_entry)
    
    # Consume the lure (fish ate the bait!)
    equipped_lure = user_data.get_equipped_lure()
    if equipped_lure:
        # Ensure lure has uses tracking (migration)
        ensure_lure_uses(equipped_lure)
        
        # Consume one use
        equipped_lure["remaining_uses"] = max(0, equipped_lure.get("remaining_uses", 1) - 1)
        
        # Calculate how many physical items consumed based on uses
        uses_per_item = equipped_lure.get("uses_per_item", 1)
        remaining_uses = equipped_lure["remaining_uses"]
        new_quantity = (remaining_uses + uses_per_item - 1) // uses_per_item  # Ceiling division
        equipped_lure["quantity"] = new_quantity
        
        if remaining_uses <= 0:
            # Remove empty lure stack
            idx = user_data.equipped_lure_index
            if idx is not None and 0 <= idx < len(user_data.current_lure_inventory):
                user_data.current_lure_inventory.pop(idx)
                user_data.equipped_lure_index = None
    
    # Update stats
    user_data.total_fish_ever_caught += 1
    # Note: fishpoints are awarded when selling fish, not when catching
    
    # Check for personal record
    is_record = user_data.update_fish_record(
        session.fish_id,
        weight_oz,
        length_in
    )
    
    # Award FishMaster token if earned (max weight OR max length)
    if earned_token:
        user_data.current_fishmaster_tokens += 1
        # Update max tokens record if needed
        if user_data.current_fishmaster_tokens > user_data.most_fishmaster_tokens_ever:
            user_data.most_fishmaster_tokens_ever = user_data.current_fishmaster_tokens
        
        # TODO: Implement reward for earned_perfect_trophy (both max weight AND max length)
        # This is a placeholder for a future special reward system
    
    # Build message
    if is_max_weight and is_max_length:
        # Both at maximum - perfect trophy
        msg = f"🏆💎 *You managed to land a PERFECT TROPHY {length_display}, {weight_display} **{fish_name}**! This is the absolute maximum size specimen!*"
        msg += "\n\n🎖️ **You earned a FishMaster Token!**"
        # msg += "\n✨ **[PLACEHOLDER: Special reward for perfect trophy]**"  # Uncomment when reward implemented
    elif is_max_weight or is_max_length:
        # One at maximum - record-breaking
        record_type = "heaviest" if is_max_weight else "longest"
        msg = f"🏆 *You managed to land the {record_type} possible {length_display}, {weight_display} **{fish_name}**!*"
        msg += "\n\n🎖️ **You earned a FishMaster Token!**"
    elif is_record:
        msg = f"⭐ *You managed to land a {length_display}, {weight_display} **{fish_name}**! That's a new personal record!*"
    else:
        msg = f"*You managed to land a {length_display}, {weight_display} **{fish_name}** and pull it out of the water with pride!*"
    
    session.add_message(msg)
    session.phase = FishingPhase.LANDED
    
    # Build debug info
    debug_info = {
        "weight_oz": weight_oz,
        "length_in": length_in,
        "max_weight_oz": max_weight_oz,
        "max_length_in": max_length_inches,
        "is_max_weight": is_max_weight,
        "is_max_length": is_max_length,
        "earned_token": earned_token,
        "earned_perfect_trophy": earned_perfect_trophy,
        "total_tokens": user_data.current_fishmaster_tokens
    }
    
    # Log to in-memory debug log if user has debug mode enabled
    if user_data.debug_mode and debug_log is not None and user_obj:
        log_debug_catch(
            debug_log, user_obj, session.fish_id, session.fish_data,
            weight_oz, length_in, max_weight_oz, max_length_inches,
            earned_token, earned_perfect_trophy, user_data.current_fishmaster_tokens
        )
    
    return (msg, is_record, earned_token, debug_info)


def handle_line_snap(session: FishingSession, user_data) -> tuple:
    """
    Handle when the line snaps (too many botched attempts).
    
    Parameters
    ----------
    session : FishingSession
        The current fishing session.
    user_data : User
        The user's data model.
    
    Returns
    -------
    tuple
        (str message, bool rod_broke) - message describing what happened and whether rod broke.
    """
    fish_name = session.fish_data.get("name", "fish") if session.fish_data else "fish"
    
    # Reduce rod durability (gear luck reduces damage)
    # Base damage is 5, reduced by 0.5 per luck point (min 2 damage)
    luck_bonus = calculate_gear_luck_bonus(user_data)
    base_damage = 5
    damage_reduction = luck_bonus * 0.5
    rod_damage = max(2, int(base_damage - damage_reduction))
    
    rod_broke = False
    equipped_rod = user_data.get_equipped_rod()
    if equipped_rod:
        old_durability = equipped_rod.get("durability", 0)
        equipped_rod["durability"] = max(0, old_durability - rod_damage)
        
        # Check if rod broke
        if equipped_rod["durability"] <= 0 and old_durability > 0:
            rod_broke = True
            # Auto-unequip the broken rod
            user_data.equipped_rod_index = None
    
    # Lose the lure - line snap loses entire bait item (all its uses)
    equipped_lure = user_data.get_equipped_lure()
    if equipped_lure:
        # Ensure lure has uses tracking (migration)
        ensure_lure_uses(equipped_lure)
        
        # Lose one entire physical bait item (all its uses)
        uses_per_item = equipped_lure.get("uses_per_item", 1)
        equipped_lure["remaining_uses"] = max(0, equipped_lure.get("remaining_uses", 0) - uses_per_item)
        equipped_lure["quantity"] = max(0, equipped_lure.get("quantity", 1) - 1)
        
        if equipped_lure["quantity"] <= 0 or equipped_lure["remaining_uses"] <= 0:
            # Remove empty lure stack
            idx = user_data.equipped_lure_index
            if idx is not None and 0 <= idx < len(user_data.current_lure_inventory):
                user_data.current_lure_inventory.pop(idx)
                user_data.equipped_lure_index = None
    
    # Update stats
    user_data.total_fishing_attempts += 1
    
    session.phase = FishingPhase.ESCAPED
    
    # Build message based on whether rod broke
    if rod_broke:
        msg = f"💥 *The {fish_name} got away! Your line snapped and you lost your lure. Your rod has BROKEN and been removed from your equipment!*"
    else:
        msg = f"*The {fish_name} got away! Your line snapped and you lost your lure. Your rod took some wear.*"
    
    session.add_message(msg)
    
    return (msg, rod_broke)
