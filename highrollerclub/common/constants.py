from __future__ import annotations

# ---------------------------------------------------------------------------
# Starting balance
# ---------------------------------------------------------------------------
STARTING_CHIP_BALANCE = 100
# Chips auto-granted to first-time players on their first lobby visit in chip mode.

# ---------------------------------------------------------------------------
# Game slugs
# ---------------------------------------------------------------------------
GAME_SLUGS = [
    "slots", "war", "allin", "blackjack", "hilo",
    "keno", "roulette", "videopoker", "clubpoker",
    "double", "big6", "mysteryspin", "multiplierwheel",
]

# ---------------------------------------------------------------------------
# Default bet limits (before rank multiplier)
# ---------------------------------------------------------------------------
DEFAULT_BET_LIMITS: dict[str, dict[str, int]] = {
    "slots":      {"min": 10,  "max": 250},
    "war":        {"min": 10,  "max": 1000},
    "allin":      {"min": 50,  "max": 10000000},
    "blackjack":  {"min": 50,  "max": 250},
    "hilo":       {"min": 25,  "max": 250},
    "keno":       {"min": 10,  "max": 250},
    "roulette":   {"min": 25,  "max": 250},
    "videopoker": {"min": 50,  "max": 1000},
    "clubpoker":  {"min": 100, "max": 1000},
    "big6":       {"min": 25,  "max": 250},
    "double":     {"min": 10,  "max": 250},
    # "mysteryspin" intentionally absent — Mystery Wheel is free; no bet.
    # "multiplierwheel" intentionally absent — uses flat spin cost from GuildSettings.multiplier_wheel_cost.
}

# ---------------------------------------------------------------------------
# Rank names
# ---------------------------------------------------------------------------
RANK_NAMES: dict[int, str] = {
    1: "Member",
    2: "Regular",
    3: "High Roller",
    4: "The Whale",
}

# ---------------------------------------------------------------------------
# Specialty titles
# ---------------------------------------------------------------------------
# Titles are PERMANENT once earned — they cannot be lost regardless of prestige_points changes.
# Rank titles (Member / Regular / High Roller / The Whale) are always shown separately and change dynamically.
# Players choose which specialty title to display alongside their rank title from the Stats view.
SPECIALTY_TITLES: dict[str, str] = {
    # Playstyle titles — earned by game-specific stat milestones
    "card_shark":  "🃏 Card Shark",   # high win rate across Blackjack, Video Poker, Hi-Lo
    "lucky_star":  "⭐ Lucky Star",   # high Slots or Keno win count
    "daredevil":   "🎲 Daredevil",   # multiple wins on Reckless+ All-In
    "the_closer":  "💰 The Closer",  # large Blackjack win at max bet
    "numbers_man": "🔢 Numbers Man", # consistent Keno / Roulette hits
    # Milestone titles — earned by cumulative lifetime achievements
    "centurion":   "💯 Centurion",   # 100 total lifetime wins
    "high_earner": "💎 High Earner", # 10,000 total payout earned
    "iron_streak": "🔥 Iron Streak", # 5 consecutive wins at any point in lifetime history
}

# ---------------------------------------------------------------------------
# All-In risk tiers
# ---------------------------------------------------------------------------
ALLIN_RISK_TIERS: dict[int, dict] = {
    1: {"name": "Standard",  "win_chance": 0.35, "payout": 2.0},
    2: {"name": "Bold",      "win_chance": 0.30, "payout": 2.5},
    3: {"name": "Reckless",  "win_chance": 0.25, "payout": 3.25},
    4: {"name": "Desperate", "win_chance": 0.15, "payout": 4.0},
    5: {"name": "Suicidal",  "win_chance": 0.10, "payout": 7.0},
}
# IMPORTANT: win_chance values above are display/fallback defaults only.
# Game code must ALWAYS read win_chance via get_game_rng(conf, "allin", "tierN_win_chance")
# so that admin overrides in CONFIGURABLE_RNG take effect at runtime.
# ALLIN_RISK_TIERS is used only for payout multiplier and display name — never for win_chance in game logic.

# ---------------------------------------------------------------------------
# Big Six Wheel
# ---------------------------------------------------------------------------
BIG6_DEFAULT_SEGMENTS: dict[str, int] = {
    "house":   8,
    "$1":      18,
    "$2":      12,
    "$5":      7,
    "$10":     5,
    "$20":     3,
    "jackpot": 1,
}
# Total default segments: 54.
# When admin configures big6_house_segments, ONLY the house count changes.
# All other segment counts stay fixed. Total wheel size = house_count + 46.
# Win probability for a chosen segment = segment_count / (house_count + 46).
# House segments are always a loss regardless of chosen bet.

BIG6_PAYOUTS: dict[str, int] = {
    "$1": 1, "$2": 2, "$5": 5, "$10": 10, "$20": 20, "jackpot": 40,
}

# ---------------------------------------------------------------------------
# Multiplier Wheel
# ---------------------------------------------------------------------------
MULTIPLIER_WHEEL_OUTCOMES: list[dict] = [
    {"label": "1.25x", "value": 1.25, "weight": 30},
    {"label": "1.5x",  "value": 1.50, "weight": 25},
    {"label": "1.75x", "value": 1.75, "weight": 20},
    {"label": "2.0x",  "value": 2.00, "weight": 15},
    {"label": "2.5x",  "value": 2.50, "weight": 7},
    {"label": "3.0x",  "value": 3.00, "weight": 3},
]

MULTIPLIER_ELIGIBLE_GAMES: set[str] = {"slots", "war", "blackjack", "hilo", "keno"}
# "double" excluded — exponential payout growth already provides extreme upside; stacking a multiplier is disproportionate.

# ---------------------------------------------------------------------------
# Lucky Streak
# ---------------------------------------------------------------------------
LUCKY_STREAK_EXPIRY_MINUTES = 60   # streak expires 1 hour after being awarded
LUCKY_STREAK_BONUS_PCT = 0.25      # +25% applied to raw game payout per win

# ---------------------------------------------------------------------------
# Rank XP reward
# ---------------------------------------------------------------------------
RANK_XP_BONUS_POINTS = 2
# Prestige points awarded when a player receives a rank_xp reward from Scratch Card or Mystery Wheel.

# ---------------------------------------------------------------------------
# Bonus Bet Token eligible games
# ---------------------------------------------------------------------------
# High-variance and high-ceiling games are excluded to prevent disproportionate payouts.
# Excluded: Roulette (35:1 max), Video Poker (royal flush multipliers), Club Poker (variable pot),
#           All-In tiers 3–5 (Reckless / Desperate / Suicidal), Double (uncapped exponential payout).
BONUS_BET_TOKEN_ELIGIBLE_GAMES: set[str] = {"slots", "war", "blackjack", "hilo", "keno", "big6"}
# All-In is partially eligible: Standard and Bold tiers (1–2) only.
# Game code must check both this set AND the active All-In tier before consuming the token.

# ---------------------------------------------------------------------------
# Reward pool option lists
# ---------------------------------------------------------------------------
SCRATCH_REWARD_OPTIONS: list[str] = [
    "chips", "bonus_bet_token", "rank_xp", "free_spin", "lucky_streak",
]
MYSTERY_WHEEL_REWARD_OPTIONS: list[str] = [
    "chips", "bonus_bet_token", "rank_xp", "free_spin", "lucky_streak",
]

# ---------------------------------------------------------------------------
# Card-math games (win % not configurable via RNG settings)
# ---------------------------------------------------------------------------
# House edge in these games comes from rules and deck math, not a tunable RNG parameter.
# get_game_rng() raises ValueError if called with any of these slugs.
CARD_MATH_GAMES: set[str] = {"blackjack", "hilo", "war", "videopoker", "clubpoker"}

# ---------------------------------------------------------------------------
# Per-game prestige point scale
# ---------------------------------------------------------------------------
# Multiplier applied to conf.prestige_win_points / conf.prestige_loss_points
# for a specific game.  Games not listed here use 1.0 (full delta).
# Slots is intentionally reduced because its high play frequency and
# naturally low win rate would otherwise erode prestige too quickly.

PRESTIGE_SCALE: dict[str, float] = {
    "slots": 0.3,
}

# ---------------------------------------------------------------------------
# Per-game configurable RNG parameters (pure-RNG games only)
# ---------------------------------------------------------------------------
# Format: game_slug → { param_key → { type, default, min, max, description } }
# Bounds are enforced at input time — never trust raw user input against these.
CONFIGURABLE_RNG: dict[str, dict] = {
    "slots": {
        "house_edge_pct": {
            "type": float, "default": 15.0, "min": 0.0, "max": 40.0,
            "description": "Percentage of bets retained by the house on average via symbol weights.",
        },
    },
    "allin": {
        "tier1_win_chance": {
            "type": float, "default": 0.35, "min": 0.30, "max": 0.70,
            "description": "Standard tier win chance",
        },
        "tier2_win_chance": {
            "type": float, "default": 0.25, "min": 0.20, "max": 0.55,
            "description": "Bold tier win chance",
        },
        "tier3_win_chance": {
            "type": float, "default": 0.20, "min": 0.10, "max": 0.40,
            "description": "Reckless tier win chance",
        },
        "tier4_win_chance": {
            "type": float, "default": 0.10, "min": 0.05, "max": 0.25,
            "description": "Desperate tier win chance",
        },
        "tier5_win_chance": {
            "type": float, "default": 0.05, "min": 0.03, "max": 0.18,
            "description": "Suicidal tier win chance",
        },
    },
    "keno": {
        "draw_count": {
            "type": int, "default": 20, "min": 15, "max": 25,
            "description": "How many numbers are drawn from the 80-number pool.",
        },
    },
    "roulette": {
        "zero_count": {
            "type": int, "default": 1, "min": 0, "max": 2,
            "description": (
                "0 = European (single zero, ~2.7% edge), "
                "1 = American (double zero, ~5.3% edge), "
                "2 = Triple zero (~7.7% edge). "
                "Controls house edge via dead segments without changing any other math."
            ),
        },
    },
    "multiplierwheel": {
        "weights": {
            "type": list, "default": [30, 25, 20, 15, 7, 3], "min": 1, "max": 100,
            "description": (
                "Parallel weight list for MULTIPLIER_WHEEL_OUTCOMES (1.25x → 3.0x). "
                "Higher weight = more common. Must have exactly 6 entries."
            ),
        },
    },
    "double": {
        "win_chance": {
            "type": float, "default": 0.50, "min": 0.30, "max": 0.70,
            "description": "Probability of a successful roll on each double attempt. Applies equally to every round of the same session.",
        },
    },
}

# ---------------------------------------------------------------------------
# Visual palette
# ---------------------------------------------------------------------------
PALETTE_GOLD = 0xD4AF37
PALETTE_BLACK = 0x0D0D0D

# ---------------------------------------------------------------------------
# Chip denomination display
# ---------------------------------------------------------------------------
# Used for flavor text only. The underlying balance is always a single integer.
# Greedy decomposition (largest denomination first) describes a bet in chip_labels.
CHIP_DENOMINATIONS: list[int] = [100, 50, 25, 10, 5, 1]  # descending order
CHIP_LABELS: dict[int, str] = {
    100: "$100", 50: "$50", 25: "$25", 10: "$10", 5: "$5", 1: "$1",
}

# ---------------------------------------------------------------------------
# Embed images — hosted on GitHub under highrollerclub/assets/
# ---------------------------------------------------------------------------
# Base URL pattern:
#   https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/highrollerclub/assets/<filename.png>
# All URL values are empty strings until asset files are uploaded to the repository.
# To activate an image: replace the empty string with the full raw GitHub URL,
# then uncomment the embed_image() call in the relevant view's embed build block.
# See assets/README.md for the full activation workflow and naming convention.
_RAW = "https://raw.githubusercontent.com/Atuelliss/GameHub/main/highrollerclub/assets"
EMBED_IMAGES: dict[str, str] = {
    # Main Lobby — displayed via embed.set_image() (large landscape banner, bottom of embed)
    "lobby":           f"{_RAW}/lobby_banner.png",
    # Navigation views — displayed via embed.set_thumbnail() (small square, top-right)
    "game_floor":      f"{_RAW}/game_floor_thumb.png",
    "teller":          f"{_RAW}/teller_thumb.png",
    "stats":           f"{_RAW}/stats_thumb.png",
    "leaderboard":     f"{_RAW}/leaderboard_thumb.png",
    "help":            f"{_RAW}/help_thumb.png",
    # Games — displayed via embed.set_thumbnail()
    "slots":           f"{_RAW}/slots_thumb.png",
    "war":             f"{_RAW}/war_thumb.png",
    "allin":           f"{_RAW}/allin_thumb.png",
    "blackjack":       f"{_RAW}/blackjack_thumb.png",
    "hilo":            f"{_RAW}/hilo_thumb.png",
    "keno":            f"{_RAW}/keno_thumb.png",
    "roulette":        f"{_RAW}/roulette_thumb.png",
    "videopoker":      f"{_RAW}/video_poker_thumb.png",
    "clubpoker":       f"{_RAW}/club_poker_thumb.png",
    "big6":            f"{_RAW}/big_6_thumb.png",
    "mysteryspin":     f"{_RAW}/mystery_wheel_thumb.png",
    "multiplierwheel": f"{_RAW}/multiplier_wheel_thumb.png",
    "double":          f"{_RAW}/double_thumb.png",
}


def embed_image(key: str) -> str | None:
    """Return the URL for the given image key, or None if the entry is empty.

    Use at embed build time to avoid passing empty strings to Discord's API:

        if url := embed_image("slots"):
            embed.set_thumbnail(url=url)
    """
    url = EMBED_IMAGES.get(key, "")
    return url if url else None
