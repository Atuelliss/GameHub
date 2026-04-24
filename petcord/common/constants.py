"""
Petcord Game Constants
"""

# =============================================================================
# TIMING CONSTANTS
# =============================================================================

# Cooldown after declining a pet (in minutes)
DEFAULT_FIND_COOLDOWN_MINUTES = 30

# How long a "pet day" lasts in real hours
DEFAULT_GROWTH_DAY_HOURS = 24


# =============================================================================
# CAPACITY CONSTANTS
# =============================================================================

# Default number of pets allowed in Home
DEFAULT_HOME_CAPACITY = 5

# Maximum achievable Home capacity
MAX_HOME_CAPACITY = 20


# =============================================================================
# STAT THRESHOLDS
# =============================================================================

# Below this value, pet is in critical condition
CRITICAL_THRESHOLD = 20

# Below this value, show warning icon
WARNING_THRESHOLD = 40

# Below this value, send danger warning notification (if enabled)
DANGER_WARNING_THRESHOLD = 30

# Minimum time between danger warning notifications (in seconds) - 1 hour
DANGER_WARNING_COOLDOWN = 3600

# Minimum time between stat tier change notifications (in seconds) - 30 minutes
STAT_TIER_NOTIFICATION_COOLDOWN = 1800

# Stat tier thresholds (for tier change notifications)
STAT_TIER_EXCELLENT = 80  # 80-100: Excellent
STAT_TIER_GOOD = 60       # 60-79: Good
STAT_TIER_FAIR = 40       # 40-59: Fair
STAT_TIER_LOW = 20        # 20-39: Low
# Below 20: Critical

# Stat tier names
STAT_TIERS = ["critical", "low", "fair", "good", "excellent"]

# Friendly notification messages for each stat when dropping to a tier
# Format: {stat: {tier: message}}
STAT_TIER_MESSAGES = {
    "hunger": {
        "good": "🍖 Your {name} is getting a bit hungry.",
        "fair": "🍖 Your {species} **{name}** looks hungry!",
        "low": "🍖 Your {species} **{name}** is very hungry and needs food soon!",
        "critical": "🍖⚠️ Your {species} **{name}** is STARVING! Feed them immediately!",
    },
    "happiness": {
        "good": "🎨 Your {name} could use some attention.",
        "fair": "🎾 Your {species} **{name}** wants to play!",
        "low": "😞 Your {species} **{name}** seems sad and lonely...",
        "critical": "😢⚠️ Your {species} **{name}** is very unhappy! Cheer them up!",
    },
    "cleanliness": {
        "good": "✨ Your {name} could use some grooming.",
        "fair": "🧹 Your {species} **{name}** is getting a bit scruffy!",
        "low": "🧹 Your {species} **{name}** really needs a bath!",
        "critical": "🧹⚠️ Your {species} **{name}** is filthy! Groom them now!",
    },
    "energy": {
        "good": "💤 Your {name} is getting a little tired.",
        "fair": "😴 Your {species} **{name}** looks sleepy!",
        "low": "😴 Your {species} **{name}** is exhausted and needs rest!",
        "critical": "😴⚠️ Your {species} **{name}** is completely exhausted!",
    },
}

# Stats start at this value for new pets
DEFAULT_STAT_VALUE = 100


# =============================================================================
# MEDAL THRESHOLDS (Percentage)
# =============================================================================

GOLD_THRESHOLD = 85.0
SILVER_THRESHOLD = 70.0
BRONZE_THRESHOLD = 50.0


# =============================================================================
# MEDAL PETCOIN REWARDS
# =============================================================================

# Base petcoin values per medal tier
MEDAL_PETCOIN_VALUES = {
    "gold": 50,
    "silver": 20,
    "bronze": 5,
}

# Multipliers based on pet lifespan (longer = more effort = more reward)
LIFESPAN_PETCOIN_MULTIPLIERS = {
    "short": 1.0,
    "medium": 1.5,
    "long": 2.0,
    "extended": 2.5,
}


# =============================================================================
# STAT DECAY RATES (Base per hour, before species multipliers)
# =============================================================================

BASE_HUNGER_DECAY = 9.0
BASE_HAPPINESS_DECAY = 9.0
BASE_CLEANLINESS_DECAY = 9.0
BASE_ENERGY_DECAY = 11.0


# =============================================================================
# ACTION COOLDOWNS (in hours)
# =============================================================================

COOLDOWN_FEED = 1.25
COOLDOWN_PLAY = 1.5
COOLDOWN_GROOM = 1.75
COOLDOWN_REST = 2
COOLDOWN_TREAT = 24
COOLDOWN_PET = 0.5

# Owner Sleep (decay pause) duration in hours
OWNER_SLEEP_DURATION_HOURS = 6

# Shop Treats cooldown and stack limits
SHOP_TREAT_COOLDOWN_HOURS = 6
TREAT_MAX_STACK = 5

# Vitamin stack limit (per vitamin type)
VITAMIN_MAX_STACK = 3

# Rest decay reduction (diminishing over cooldown duration)
# Max 50% reduction right after resting, fading to 0% at cooldown end
REST_DECAY_MAX_REDUCTION = 0.50


# =============================================================================
# LIFE STAGE DECAY MULTIPLIERS
# =============================================================================

# Multipliers applied to decay based on pet's life stage
# Babies decay at full rate (1.0) - they need constant attention
# Juveniles decay at half rate (0.5) - they're more independent
# Adults and Seniors decay at full rate (1.0) - back to normal maintenance
LIFE_STAGE_DECAY_MULTIPLIERS = {
    "baby": 1.0,       # Full decay - babies need constant care
    "juvenile": 0.5,   # Half decay - juveniles are more resilient
    "adult": 1.0,      # Full decay - normal maintenance
    "senior": 1.0,     # Full decay - seniors need regular care
}


# =============================================================================
# ACTION STAT CHANGES
# =============================================================================

# Format: {"stat_name": change_amount}
ACTION_EFFECTS = {
    "feed": {"hunger": 30, "happiness": 5},
    "play": {"happiness": 25, "energy": -15, "bond": 3},
    "groom": {"cleanliness": 35, "happiness": 5},
    "rest": {"energy": 40, "health": 10},
    "treat": {"happiness": 20, "bond": 5},
    "pet": {"happiness": 10, "bond": 2},
}


# =============================================================================
# CATEGORY DECAY MULTIPLIERS
# =============================================================================

# Applied to base decay rates per species category
DECAY_MULTIPLIERS = {
    "dogs": {"hunger": 1.5, "happiness": 1.2, "cleanliness": 1.0, "energy": 1.3},
    "cats": {"hunger": 1.0, "happiness": 0.8, "cleanliness": 0.5, "energy": 0.8},
    "small_mammals": {"hunger": 2.0, "happiness": 1.0, "cleanliness": 1.0, "energy": 1.5},
    "reptiles": {"hunger": 0.3, "happiness": 0.5, "cleanliness": 0.8, "energy": 0.5},
    "birds": {"hunger": 1.8, "happiness": 1.5, "cleanliness": 1.2, "energy": 1.0},
    "aquatic": {"hunger": 1.0, "happiness": 0.6, "cleanliness": 1.5, "energy": 0.5},
    "exotic": {"hunger": 1.0, "happiness": 1.0, "cleanliness": 1.0, "energy": 1.0},
}


# =============================================================================
# RARITY WEIGHTS (for random selection)
# =============================================================================

RARITY_WEIGHTS = {
    "common": 40,
    "uncommon": 30,
    "rare": 18,
    "very_rare": 8,
    "legendary": 3.5,
    "mythical": 0.5,
}


# =============================================================================
# LIFE STAGE THRESHOLDS (in pet days)
# =============================================================================

# Format: lifespan_category -> {stage: days_to_reach_this_stage}
# Home lifespan: short=~1 month, medium=~2 months, long=~4 months, extended=~6 months
STAGE_THRESHOLDS = {
    "short": {"baby": 0, "juvenile": 2, "adult": 5, "senior": 20, "max_age": 35},
    "medium": {"baby": 0, "juvenile": 4, "adult": 10, "senior": 40, "max_age": 70},
    "long": {"baby": 0, "juvenile": 7, "adult": 21, "senior": 80, "max_age": 141},
    "extended": {"baby": 0, "juvenile": 10, "adult": 30, "senior": 120, "max_age": 210},
}


# =============================================================================
# DEFAULT BLACKLISTED NAMES
# =============================================================================

DEFAULT_DISALLOWED_NAMES = [
    "admin",
    "mod",
    "moderator",
    "owner",
    "bot",
    "system",
]


# =============================================================================
# DAILY SCORE WEIGHTS
# =============================================================================

DAILY_SCORE_WEIGHTS = {
    "feeding": 0.30,
    "happiness": 0.25,
    "cleanliness": 0.20,
    "energy": 0.15,
    "bonus": 0.10,
}


# =============================================================================
# WEAR SLOT SYSTEM (Pet Wardrobe)
# =============================================================================

# Maps wear slots to item categories that can fill that slot
WEAR_SLOTS = {
    "head": ["hat", "headband"],
    "face": ["eyepatch", "glasses"],
    "neck": ["collar"],
    "body": ["onesie", "cape", "costume"],
    "feet": ["socks", "booties"],
    "tail": ["tail"],
    "ears": ["earring"],
}

# Reverse lookup - category to slot
CATEGORY_TO_SLOT = {
    "hat": "head",
    "headband": "head",
    "eyepatch": "face",
    "glasses": "face",
    "collar": "neck",
    "onesie": "body",
    "cape": "body",
    "costume": "body",
    "socks": "feet",
    "booties": "feet",
    "tail": "tail",
    "earring": "ears",
}

# Display order and info for slots
SLOT_DISPLAY = {
    "head": {"name": "Head", "emoji": "🎩", "order": 1},
    "face": {"name": "Face", "emoji": "😎", "order": 2},
    "neck": {"name": "Neck", "emoji": "📿", "order": 3},
    "body": {"name": "Body", "emoji": "👕", "order": 4},
    "feet": {"name": "Feet", "emoji": "🧦", "order": 5},
    "tail": {"name": "Tail", "emoji": "🎀", "order": 6},
    "ears": {"name": "Ears", "emoji": "💎", "order": 7},
}
