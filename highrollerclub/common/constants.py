from __future__ import annotations

from pathlib import Path

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
    "keno", "roulette", "videopoker", "clubpoker", "holdem",
    "double", "horserace", "big6", "mysteryspin", "multiplierwheel",
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
    # Horse Racing has one limit per bet type; "horserace" itself has none.
    "horserace_win":   {"min": 10, "max": 1500},
    "horserace_place": {"min": 10, "max": 750},
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
    "high_earner": "💎 High Earner", # 10,000 total winnings
    "iron_streak": "🔥 Iron Streak", # 5 consecutive wins at any point in lifetime history
    # Horse Racing titles
    "railbird":      "🏇 Railbird",      # bet on 25 races
    "longshot":      "🎯 Longshot",      # a Win bet that returned 10x the stake or more
    "big_payday":    "💰 Big Payday",    # 5,000+ profit from a single race
    "steady_eddie":  "🥈 Steady Eddie",  # 10 Place bets cashed
    "hot_streak":    "🔥 Hot Streak",    # Win bets cashed in 3 races in a row
    "race_promoter": "🎪 Race Promoter", # started 15 races that had 3+ bettors
    "called_it":     "🏆 Called It",     # cashed a Win bet as the only backer of the winner
    # Texas Hold'em titles (only hands with 3+ players dealt in count, except Royal Treatment)
    "grinder":         "♣️ Grinder",         # dealt into 250 hands
    "bluff_master":    "🎭 Bluff Master",    # won 25 pots where everyone else folded
    "river_rat":       "🌊 River Rat",       # won 5 showdowns after being behind on the turn
    "shove_survivor":  "💥 Shove Survivor",  # won 10 showdowns while all-in
    "monster_pot":     "🏔️ Monster Pot",     # won a pot of 100+ big blinds
    "royal_treatment": "👑 Royal Treatment", # made a royal flush at showdown (any table size)
    "bad_beat":        "💔 Bad Beat",        # lost a showdown with four of a kind or better
    "table_captain":   "🎩 Table Captain",   # hosted 10 tables that dealt 10+ hands with 3+ players
}

# ---------------------------------------------------------------------------
# All-In risk tiers
# ---------------------------------------------------------------------------
ALLIN_RISK_TIERS: dict[int, dict] = {
    1: {"name": "Standard",  "payout": 2.0},
    2: {"name": "Bold",      "payout": 2.5},
    3: {"name": "Reckless",  "payout": 3.25},
    4: {"name": "Desperate", "payout": 4.0},
    5: {"name": "Suicidal",  "payout": 7.0},
}
# Win chances live only in CONFIGURABLE_RNG["allin"] (tierN_win_chance) and are always
# read with get_game_rng(conf, "allin", "tierN_win_chance") so admin overrides apply.
# Every tier's max win chance keeps its return under 100% (max x payout < 1.0).

# ---------------------------------------------------------------------------
# Big Six Wheel
# ---------------------------------------------------------------------------
BIG6_DEFAULT_SEGMENTS: dict[str, int] = {
    "house":   2,
    "$1":      24,
    "$2":      15,
    "$5":      7,
    "$10":     4,
    "$20":     2,
    "jackpot": 1,
}
# Mirrors a real casino Big Six wheel (54 segments at the default 2 house segments).
# When admin configures big6_house_segments, ONLY the house count changes.
# All other segment counts stay fixed. Total wheel size = house_count + BIG6_FIXED_SEGMENTS.
# House segments are always a loss regardless of chosen bet.
# Return per bet at the default 2 house segments: $1 87%, $2 82%, $5 76%, $10 80%,
# $20 76%, jackpot 84%. At 0 house segments the best bet ($1) returns 91%.
BIG6_FIXED_SEGMENTS: int = sum(v for k, v in BIG6_DEFAULT_SEGMENTS.items() if k != "house")
BIG6_HOUSE_SEGMENT_OPTIONS: tuple[int, ...] = (0, 2, 4, 6)

BIG6_PAYOUTS: dict[str, int] = {
    "$1": 1, "$2": 2, "$5": 5, "$10": 10, "$20": 20, "jackpot": 45,
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
LUCKY_STREAK_BONUS_PCT = 0.25      # +25% of the winnings (payout minus stake) per win

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
CARD_MATH_GAMES: set[str] = {"blackjack", "hilo", "war", "videopoker", "clubpoker", "holdem"}

# ---------------------------------------------------------------------------
# Texas Hold'em (logic in games/holdem.py, money safety in tasks/holdem_tables.py)
# ---------------------------------------------------------------------------
# Hold'em has no min/max bet (it is not in DEFAULT_BET_LIMITS). Tables are opened at a
# blind level, and the player's rank sets which levels they can open. Servers start
# with these defaults; admins can edit them (GuildSettings.holdem_stake_tiers).
# Read them only through helper_functions.get_holdem_tiers().
HOLDEM_DEFAULT_STAKE_TIERS: list[dict[str, int]] = [
    {"sb": 100,  "bb": 200,  "min_rank": 1},   # Standard table
    {"sb": 200,  "bb": 500,  "min_rank": 1},   # Member's prestige table
    {"sb": 500,  "bb": 750,  "min_rank": 2},   # Regular
    {"sb": 750,  "bb": 1000, "min_rank": 3},   # High Roller
    {"sb": 1000, "bb": 1500, "min_rank": 4},   # The Whale
]
HOLDEM_TIER_COUNT = 5                # admins edit or switch off levels; they don't add more
HOLDEM_PRESTIGE_MIN_PLAYERS = 3      # a hand changes prestige (and Hold'em titles) only with 3+ players dealt in
HOLDEM_MIN_BUYIN_BB = 20             # default buy-in range, in big blinds
HOLDEM_MAX_BUYIN_BB = 100
HOLDEM_BUYIN_FLOOR_BB = 10           # admins can't set the minimum buy-in below this
HOLDEM_MAX_SEATS = 6
HOLDEM_ACTION_SECONDS = 60           # default time to act before an auto check/fold
HOLDEM_ACTION_SECONDS_RANGE = (30, 180)
HOLDEM_SITOUT_TIMEOUTS = 2           # timeouts in a row before a player is sat out
HOLDEM_IDLE_CLOSE_MINUTES = 10       # a table with no hand started for this long closes
HOLDEM_MUCK_SECONDS = 15             # losing hands at showdown: time to show or muck

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
            "type": float, "default": 10.0, "min": 2.0, "max": 40.0,
            "description": "Real house edge: the average % of each bet the house keeps (10 = slots return 90%).",
        },
    },
    "allin": {
        # Defaults return ~88-91% (win chance x payout). Max values stay just under 100%.
        "tier1_win_chance": {
            "type": float, "default": 0.45, "min": 0.30, "max": 0.49,
            "description": "Standard tier win chance (pays 2x)",
        },
        "tier2_win_chance": {
            "type": float, "default": 0.36, "min": 0.20, "max": 0.39,
            "description": "Bold tier win chance (pays 2.5x)",
        },
        "tier3_win_chance": {
            "type": float, "default": 0.28, "min": 0.10, "max": 0.30,
            "description": "Reckless tier win chance (pays 3.25x)",
        },
        "tier4_win_chance": {
            "type": float, "default": 0.22, "min": 0.05, "max": 0.24,
            "description": "Desperate tier win chance (pays 4x)",
        },
        "tier5_win_chance": {
            "type": float, "default": 0.13, "min": 0.03, "max": 0.14,
            "description": "Suicidal tier win chance (pays 7x)",
        },
    },
    # Keno has no RNG setting: its house edge comes from the paytable, which is
    # built for a fixed 20-number draw (see games/keno.py).
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
            "type": float, "default": 0.47, "min": 0.30, "max": 0.49,
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
#   https://raw.githubusercontent.com/Atuelliss/GameHub/main/highrollerclub/assets/<filename.png>
# All URL values are empty strings until asset files are uploaded to the repository.
# To activate an image: replace the empty string with the full raw GitHub URL,
# then uncomment the embed_image() call in the relevant view's embed build block.
# See assets/README.md for the full activation workflow and naming convention.
_RAW = "https://raw.githubusercontent.com/Atuelliss/GameHub/main/highrollerclub/assets"
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _asset(filename: str) -> str:
    """Raw GitHub URL for an image in assets/, or "" if the file isn't in the folder yet.

    An empty entry makes embed_image() return None, so a game without its image
    shows no thumbnail instead of a broken one. Add the file (and push it) to activate.
    """
    return f"{_RAW}/{filename}" if (_ASSETS_DIR / filename).is_file() else ""


EMBED_IMAGES: dict[str, str] = {
    # Main Lobby — displayed via embed.set_image() (large landscape banner, bottom of embed)
    "lobby":           _asset("lobby_banner.png"),
    # Navigation views — displayed via embed.set_thumbnail() (small square, top-right)
    "game_floor":      _asset("game_floor_thumb.png"),
    "teller":          _asset("teller_thumb.png"),
    "stats":           _asset("stats_thumb.png"),
    "leaderboard":     _asset("leaderboard_thumb.png"),
    "help":            _asset("help_thumb.png"),
    # Games — displayed via embed.set_thumbnail()
    "slots":           _asset("slots_thumb.png"),
    "war":             _asset("war_thumb.png"),
    "allin":           _asset("allin_thumb.png"),
    "blackjack":       _asset("blackjack_thumb.png"),
    "hilo":            _asset("hilo_thumb.png"),
    "keno":            _asset("keno_thumb.png"),
    "roulette":        _asset("roulette_thumb.png"),
    "videopoker":      _asset("video_poker_thumb.png"),
    "clubpoker":       _asset("club_poker_thumb.png"),
    "holdem":          _asset("texas_holdem.png"),
    "big6":            _asset("big_6_thumb.png"),
    "mysteryspin":     _asset("mystery_wheel_thumb.png"),
    "multiplierwheel": _asset("multiplier_wheel_thumb.png"),
    "double":          _asset("double_thumb.png"),
    "horserace":       _asset("horse_racing_thumb.png"),
}


def embed_image(key: str) -> str | None:
    """Return the URL for the given image key, or None if the entry is empty.

    Use at embed build time to avoid passing empty strings to Discord's API:

        if url := embed_image("slots"):
            embed.set_thumbnail(url=url)
    """
    url = EMBED_IMAGES.get(key, "")
    return url if url else None
