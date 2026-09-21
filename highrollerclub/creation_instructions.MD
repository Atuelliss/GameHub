# HighRollerClub — Build Order & Implementation Instructions

All work follows this sequence. Do not implement a later phase until the previous phase is complete and verified. Each phase defines what to write, what file it lives in, and what decisions need to be made before writing code.

---

## Phase 1 — Expand `common/models.py`

This is the foundation. Every config value that an admin can set, and every stat that a player accumulates, must be defined here before any command touches them. Games read from this schema — if it isn't here first, it gets hardcoded and has to be refactored later.

### `GuildSettings` — Add all server-owner configurable fields

**Payment System**
```
payment_mode: str = "chips"                        # "chips" | "bank"
discord_currency_conversion_rate: int = 100        # chips gained per 1 server currency unit spent (chip mode buy/sell rate)
discord_currency_conversion_enabled: bool = False  # when True in chip mode, players may convert chips back to server currency
```
> **Naming note:** These field names match the existing `models.py` stub. The old name `chip_exchange_rate` is retired — use `discord_currency_conversion_rate` everywhere going forward.

**Rank Thresholds** — prestige point totals required to hold each rank (evaluated dynamically after every game)
```
rank2_threshold: int = 50            # prestige points required to hold Regular
rank3_threshold: int = 200           # prestige points required to hold High Roller
rank4_threshold: int = 1000          # prestige points required to hold The Whale
```
> Rank is always recalculated from the player's live `prestige_points` value. Crossing a threshold
> down demotes the player exactly as crossing it up promotes them. There is no floor between ranks —
> a Whale who loses enough can drop straight to Member.

**Prestige Point Values** — how much each game outcome moves prestige_points (admin-configurable)
```
prestige_win_points: float = 1.0     # points added per win (min 0.1)
prestige_loss_points: float = 0.75   # points removed per loss (floored at 0; min 0.0)
```

**Rank Bet Multipliers** — applied to base bet limits
```
rank1_multiplier: float = 1.0        # Member
rank2_multiplier: float = 1.5        # Regular
rank3_multiplier: float = 2.0        # High Roller
rank4_multiplier: float = 3.0        # The Whale
```

**Base Bet Limits Per Game** — floor/ceiling before rank multiplier is applied.
Store as a dict keyed by game slug for forward compatibility as new games are added.
```
game_bet_limits: dict[str, dict[str, int]] = Field(default_factory=dict)
# e.g. {"slots": {"min": 10, "max": 500}, "blackjack": {"min": 50, "max": 2000}, ...}
```
Default values for all 12 games should be defined in `constants.py` and used to populate this dict when a guild first loads (i.e. if a key is missing, fall back to the constant).

**Channel Restrictions** — already partially exists (`allowed_channels`), verify it works for all games

**All-In Risk Tier Cap**
```
allin_max_tier: int = 5              # 1–5; tiers above this value are hidden from players
```

**Scratch Card Settings**
```
scratch_enabled: bool = False
scratch_cooldown_hours: int = 24
scratch_reward_pool: list[str] = Field(default_factory=lambda: ["chips"])
# valid pool entries: "chips" | "bonus_bet_token" | "rank_xp" | "free_spin" | "lucky_streak"
```
> **Payment mode note:** When `payment_mode == "bank"`, chip rewards from Scratch Cards and Mystery Wheel are deposited to the player's RedBot bank balance. The chip reward amount is converted at `discord_currency_conversion_rate` before deposit. `bonus_bet_token`, `rank_xp`, `free_spin`, and `lucky_streak` rewards are unaffected by payment mode.
>
> **Bonus bet token scope:** A `bonus_bet_token` may only be used on games listed in `BONUS_BET_TOKEN_ELIGIBLE_GAMES` (see Phase 2). Attempting to use one on an ineligible game shows an ephemeral notice — the token is **not consumed**.

**Mystery Wheel (Daily Free Spin)**
```
mystery_wheel_enabled: bool = False
mystery_wheel_timezone: str = "America/New_York"
mystery_wheel_reward_pool: list[str] = Field(default_factory=lambda: ["chips"])
```

**Multiplier Wheel**
```
multiplier_wheel_cost: int = 100     # flat chip/currency cost to spin
multiplier_wheel_expiry_minutes: int = 30
```

**Big Six Wheel**
```
big6_house_segments: int = 8        # configurable 6–12; higher = steeper house edge
```

**Per-Game Enable Flags** — allow admins to disable individual games that don't fit their server
```
games_enabled: dict[str, bool] = Field(default_factory=lambda: {
    "slots":          True,
    "war":            True,
    "allin":          True,
    "blackjack":      True,
    "hilo":           True,
    "keno":           True,
    "roulette":       True,
    "videopoker":     True,
    "clubpoker":      True,
    "big6":           True,
    "mysteryspin":    True,
    "multiplierwheel": True,
})
# All games are enabled by default. Setting a value to False hides the game button on the
# Game Floor (grey style + 🔒 prefix) and blocks access if a player somehow reaches the view.
# Disabling a game does not affect existing player stats for that game.
```

**Rank Multiplier Toggle**
```
bet_multipliers_enabled: bool = True
# When False, all ranks bet at 1x base limits regardless of rank.
# Rank tracking, prestige, and cosmetic titles continue to function normally.
# Useful for servers that want the prestige system without economy impact.
```

**Per-Game RNG Overrides**
```
game_rng_settings: dict[str, dict[str, Any]] = Field(default_factory=dict)
# Stores admin-configured RNG parameters per game.
# Keys per game are defined in constants.CONFIGURABLE_RNG.
# Any missing key falls back to the CONFIGURABLE_RNG default — no key is required.
# Card-math games (blackjack, hilo, war, videopoker, clubpoker) are NOT in this dict.
```

---

### `User` — Replace stub, add all player-tracked fields

> **Storage vs. display:** Players are keyed by Discord user ID (int) in the `users` dict. Display names are **never stored** — always fetched at render time via `interaction.guild.get_member(user_id).display_name` (fall back to `str(user_id)` if member is not in cache).

```
# Currency
chip_balance: int = 0               # only meaningful in chip mode

# Rank progression
rank: int = 1                        # 1=Member, 2=Regular, 3=High Roller, 4=The Whale — re-evaluated after every game
prestige_points: float = 0.0         # primary rank driver; +prestige_win_points per win, -prestige_loss_points per loss; floor 0.0
total_wins: int = 0                  # lifetime stat only — not used for rank; used for leaderboards and title evaluation
total_payout_earned: int = 0         # lifetime stat only — not used for rank

# Specialty titles
earned_titles: list[str] = Field(default_factory=list)
active_title: str | None = None
# valid title slugs: "card_shark" | "lucky_star" | "daredevil" | "the_closer" | "numbers_man"
#                   "centurion" | "high_earner" | "iron_streak"

# Multiplier Wheel state
pending_multiplier: float | None = None
pending_multiplier_expiry: datetime | None = None   # stored as UTC ISO string

# Scratch Card
last_scratch_date: str | None = None    # ISO date string in server timezone

# Mystery Wheel
last_mystery_wheel_date: str | None = None  # ISO date string in server timezone

# Bonus tokens
bonus_bet_tokens: int = 0
free_spins_available: int = 0      # earned from Scratch Card / Mystery Wheel; consumed by a free Slots spin (no bet deducted)
current_win_streak: int = 0        # incremented on each win, reset to 0 on any loss; used to evaluate iron_streak title

# Lucky Streak state — awarded by Scratch Card or Mystery Wheel.
# While active (not expired), every consecutive win pays +25% of the raw game payout.
# Cancelled immediately on the player's first loss. Expires after 1 hour regardless.
# lucky_streak_expiry stored as UTC ISO string. None = no active streak.
lucky_streak_expiry: datetime | None = None

# Lifetime stats — used for Stats embed and leaderboards
total_losses: int = 0
largest_single_payout: int = 0      # largest single payout ever received
largest_single_loss: int = 0        # largest single bet amount lost in one game

# Per-game stats — keyed by game slug; populated on first play of each game
game_play_counts: dict[str, int] = Field(default_factory=dict)
game_win_counts: dict[str, int] = Field(default_factory=dict)
game_loss_counts: dict[str, int] = Field(default_factory=dict)
game_total_payout: dict[str, int] = Field(default_factory=dict)
game_highest_single_payout: dict[str, int] = Field(default_factory=dict)
game_highest_bet: dict[str, int] = Field(default_factory=dict)
game_highest_single_loss: dict[str, int] = Field(default_factory=dict)
# Favorite game = max(game_play_counts, key=game_play_counts.get) — computed at render time, never stored
```

---

## Phase 2 — Populate `common/constants.py`

Define all magic numbers and slug names here so they are never hardcoded anywhere else.

```python
STARTING_CHIP_BALANCE = 100  # chips auto-granted to first-time players on their first lobby visit in chip mode

GAME_SLUGS = [
    "slots", "war", "allin", "blackjack", "hilo",
    "keno", "roulette", "videopoker", "clubpoker",
    "big6", "mysteryspin", "multiplierwheel"
]

DEFAULT_BET_LIMITS: dict[str, dict[str, int]] = {
    "slots":          {"min": 10,  "max": 500},
    "war":            {"min": 10,  "max": 1000},
    "allin":          {"min": 50,  "max": 2000},
    "blackjack":      {"min": 50,  "max": 5000},
    "hilo":           {"min": 25,  "max": 2000},
    "keno":           {"min": 10,  "max": 1000},
    "roulette":       {"min": 25,  "max": 5000},
    "videopoker":     {"min": 50,  "max": 5000},
    "clubpoker":      {"min": 100, "max": 10000},
    "big6":           {"min": 25,  "max": 2000},
    # "mysteryspin" and "multiplierwheel" are intentionally absent:
    # Mystery Wheel is free — no bet; awards from a reward pool (mystery_wheel_reward_pool in GuildSettings).
    # Multiplier Wheel uses a flat spin cost (multiplier_wheel_cost in GuildSettings), not a ranged bet limit.
}

RANK_NAMES = {1: "Member", 2: "Regular", 3: "High Roller", 4: "The Whale"}

# Specialty titles are PERMANENT once earned — they cannot be lost regardless of prestige_points changes.
# Rank titles (Member / Regular / High Roller / The Whale) are always shown separately and change dynamically.
# Players choose which specialty title to display alongside their current rank title from the Stats view.
SPECIALTY_TITLES = {
    # Playstyle titles — earned by game-specific stat milestones
    "card_shark":    "🃏 Card Shark",      # high win rate across Blackjack, Video Poker, Hi-Lo
    "lucky_star":    "⭐ Lucky Star",      # high Slots or Keno win count
    "daredevil":     "🎲 Daredevil",      # multiple wins on Reckless+ All-In
    "the_closer":    "💰 The Closer",     # large Blackjack win at max bet
    "numbers_man":   "🔢 Numbers Man",    # consistent Keno / Roulette hits
    # Milestone titles — earned by cumulative lifetime achievements
    "centurion":     "💯 Centurion",      # 100 total lifetime wins
    "high_earner":   "💎 High Earner",    # 10,000 total payout earned (chips or currency value)
    "iron_streak":   "🔥 Iron Streak",    # 5 consecutive wins at any point in lifetime history
}

ALLIN_RISK_TIERS = {
    1: {"name": "Standard",  "win_chance": 0.50, "payout": 2},
    2: {"name": "Bold",      "win_chance": 0.33, "payout": 3},
    3: {"name": "Reckless",  "win_chance": 0.25, "payout": 4},
    4: {"name": "Desperate", "win_chance": 0.15, "payout": 6},
    5: {"name": "Suicidal",  "win_chance": 0.10, "payout": 9},
}
# IMPORTANT: The win_chance values above are defaults only.
# Game code must ALWAYS read win_chance via get_game_rng(conf, "allin", "tierN_win_chance")
# so that admin overrides in CONFIGURABLE_RNG take effect.
# ALLIN_RISK_TIERS is used only for the payout multiplier and display name — never for win_chance at runtime.

BIG6_DEFAULT_SEGMENTS = {
    "house": 8,
    "$1":    18,
    "$2":    12,
    "$5":    7,
    "$10":   5,
    "$20":   3,
    "jackpot": 1,
}
# Total default segments: 54.
# When the admin configures big6_house_segments, ONLY the house count changes.
# All other segment counts stay fixed. Total wheel size = house_count + 46.
# Win probability for a chosen segment = segment_count / (house_count + 46).
# House segments are always a loss regardless of chosen bet.

BIG6_PAYOUTS = {
    "$1": 1, "$2": 2, "$5": 5, "$10": 10, "$20": 20, "jackpot": 40
}

MULTIPLIER_WHEEL_OUTCOMES = [
    {"label": "1.25x", "value": 1.25, "weight": 30},
    {"label": "1.5x",  "value": 1.50, "weight": 25},
    {"label": "1.75x", "value": 1.75, "weight": 20},
    {"label": "2.0x",  "value": 2.00, "weight": 15},
    {"label": "2.5x",  "value": 2.50, "weight": 7},
    {"label": "3.0x",  "value": 3.00, "weight": 3},
]

MULTIPLIER_ELIGIBLE_GAMES = {"slots", "war", "blackjack", "hilo", "keno"}

# Lucky Streak constants
LUCKY_STREAK_EXPIRY_MINUTES = 60    # streak expires 1 hour after being awarded
LUCKY_STREAK_BONUS_PCT = 0.25       # +25% applied to raw game payout per win (see helper for exact definition)

RANK_XP_BONUS_POINTS = 2            # prestige points awarded when a player receives a rank_xp reward from Scratch Card or Mystery Wheel

# Games where a Bonus Bet Token (doubles next win payout) may be used.
# High-variance and high-ceiling games are excluded to prevent disproportionate payouts.
# Excluded: Roulette (35:1 max), Video Poker (royal flush multipliers), Club Poker (variable pot),
#           All-In tiers 3–5 (Reckless/Desperate/Suicidal).
BONUS_BET_TOKEN_ELIGIBLE_GAMES = {"slots", "war", "blackjack", "hilo", "keno", "big6"}
# All-In is partially eligible: Standard and Bold tiers (1–2) only.
# Game code must check both this set AND the active All-In tier before consuming the token.

SCRATCH_REWARD_OPTIONS = ["chips", "bonus_bet_token", "rank_xp", "free_spin", "lucky_streak"]
MYSTERY_WHEEL_REWARD_OPTIONS = ["chips", "bonus_bet_token", "rank_xp", "free_spin", "lucky_streak"]

# Games where win % is driven by card math — NOT configurable via RNG settings.
# House edge in these games comes from rules, not a tunable RNG parameter.
CARD_MATH_GAMES = {"blackjack", "hilo", "war", "videopoker", "clubpoker"}

# Per-game configurable RNG parameters for pure-RNG games.
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
        "tier1_win_chance": {"type": float, "default": 0.50, "min": 0.30, "max": 0.70, "description": "Standard tier win chance"},
        "tier2_win_chance": {"type": float, "default": 0.33, "min": 0.20, "max": 0.55, "description": "Bold tier win chance"},
        "tier3_win_chance": {"type": float, "default": 0.25, "min": 0.10, "max": 0.40, "description": "Reckless tier win chance"},
        "tier4_win_chance": {"type": float, "default": 0.15, "min": 0.05, "max": 0.25, "description": "Desperate tier win chance"},
        "tier5_win_chance": {"type": float, "default": 0.10, "min": 0.03, "max": 0.18, "description": "Suicidal tier win chance"},
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
            "description": "0=European (single zero, ~2.7% edge), 1=American (double zero, ~5.3% edge), 2=Triple zero (~7.7% edge). Controls house edge via dead segments without changing any other math.",
        },
    },
    "multiplierwheel": {
        "weights": {
            "type": list, "default": [30, 25, 20, 15, 7, 3], "min": 1, "max": 100,
            "description": "Parallel weight list for MULTIPLIER_WHEEL_OUTCOMES (1.25x → 3.0x). Higher weight = more common. Must have exactly 6 entries.",
        },
    },
}

PALETTE_GOLD = 0xD4AF37
PALETTE_BLACK = 0x0D0D0D

# Chip denominations used for display flavor text only.
# The underlying balance is always a single integer — these are never tracked separately.
# Greedy decomposition (largest denomination first) is used to describe a bet amount.
CHIP_DENOMINATIONS = [100, 50, 25, 10, 5, 1]  # descending order
CHIP_LABELS = {100: "$100", 50: "$50", 25: "$25", 10: "$10", 5: "$5", 1: "$1"}

# ---------------------------------------------------------------------------
# Embed Images — hosted on GitHub under highrollerclub/assets/
# Base URL: https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/highrollerclub/assets/<filename.png>
# ALL URL values are empty strings until asset files are uploaded to the repository.
# To activate an image: replace the empty string with the full raw GitHub URL.
# ---------------------------------------------------------------------------
EMBED_IMAGES: dict[str, str] = {
    # Main Lobby — displayed via embed.set_image() (large banner, bottom of embed)
    "lobby":           "",  # Grand casino entrance — wide shot, art deco neon/gold
    # Game Floor
    "game_floor":      "",  # Casino floor aerial — felt tables, chips, ambient crowd
    # Teller Window
    "teller":          "",  # Stacked casino chips or a cashier window
    # Navigation views
    "stats":           "",  # Trophy or a single ornate gold card
    "leaderboard":     "",  # Gold/silver/bronze podium
    "help":            "",  # Open book or ornate casino guide
    # Games — per-game thumbnails, all via embed.set_thumbnail()
    "slots":           "",  # Close-up of a classic slot machine
    "war":             "",  # Two cards face-down about to be flipped
    "allin":           "",  # Chips dramatically shoved to center of table
    "blackjack":       "",  # Cards and chips on green felt
    "hilo":            "",  # Single playing card, face partially revealed
    "keno":            "",  # Numbered lottery balls
    "roulette":        "",  # Roulette wheel close-up, mid-spin
    "videopoker":      "",  # Cards fanned out on felt surface
    "clubpoker":       "",  # Poker table aerial view, chips in center pot
    "big6":            "",  # Money wheel with gold segments
    "mysteryspin":     "",  # Mysterious glowing wheel, obscured segments
    "multiplierwheel": "",  # Prize wheel with glowing multiplier labels
}

def embed_image(key: str) -> str | None:
    """Returns the URL for the given image key, or None if the entry is empty.
    Use at embed build time to avoid passing empty strings to set_thumbnail().
    Example:
        if url := embed_image("slots"):
            embed.set_thumbnail(url=url)
    """
    url = EMBED_IMAGES.get(key, "")
    return url if url else None
```

---

## Phase 3 — Write `commands/helper_functions.py`

These are called by admin commands, game logic, and anywhere else. Write them before either. Every function takes `conf: GuildSettings` and/or `user: User` as arguments — no direct `self.db` access inside helpers.

**Admin permission check** — Do NOT inline permission logic in every command. Define one async helper:
```python
async def check_is_admin(ctx_or_interaction) -> bool:
    """Returns True if the invoker is a bot admin or has manage_guild.
    Accepts either a commands.Context (command callbacks) or a discord.Interaction (View button callbacks).
    If a shared is_admin utility exists in another cog (e.g. vainneutils),
    import it here and call it inside this function — keep the call site identical.
    """
    if isinstance(ctx_or_interaction, discord.Interaction):
        user = ctx_or_interaction.user
        guild_perms = ctx_or_interaction.user.guild_permissions
        bot = ctx_or_interaction.client
    else:
        user = ctx_or_interaction.author
        guild_perms = ctx_or_interaction.author.guild_permissions
        bot = ctx_or_interaction.bot
    return await bot.is_admin(user) or guild_perms.manage_guild
```
All admin commands call `if not await check_is_admin(ctx): return` at the top, or use the `@commands.admin_or_permissions(manage_guild=True)` decorator — pick one pattern and use it consistently across every command in `admin_commands.py`.

### Functions to implement (in this order):

**Bet validation**
```python
def get_bet_limits(conf: GuildSettings, game_slug: str, rank: int) -> tuple[int, int]:
    """Returns (min_bet, max_bet) for a given game and player rank after multiplier."""

def validate_bet(conf: GuildSettings, user: User, game_slug: str, amount: int, current_balance: int) -> str | None:
    """Returns an error string if the bet is invalid, or None if it's clean.
    Checks: min/max limits after rank multiplier, sufficient balance.
    Caller must pre-fetch current_balance via get_balance() — this function is sync and cannot call async bank APIs."""
```

**Balance helpers**
```python
async def get_balance(member: discord.Member, conf: GuildSettings, user: User) -> int:
    """Returns player's spendable balance — chip_balance in chip mode, bank balance in bank mode.
    Accepts discord.Member directly; caller extracts from ctx.author or interaction.user."""

async def deduct_balance(member: discord.Member, conf: GuildSettings, user: User, amount: int) -> None:
    """Deducts from chip_balance or bank depending on payment_mode.
    Accepts discord.Member directly; caller extracts from ctx.author or interaction.user."""

async def credit_balance(member: discord.Member, conf: GuildSettings, user: User, amount: int) -> None:
    """Credits chip_balance or bank depending on payment_mode.
    Accepts discord.Member directly; caller extracts from ctx.author or interaction.user."""
```

**Rank helpers**
```python
def get_rank_multiplier(conf: GuildSettings, rank: int) -> float:
    """Returns the effective bet multiplier for the given rank.
    If conf.bet_multipliers_enabled is False, always returns 1.0 regardless of rank.
    """

def evaluate_rank(conf: GuildSettings, user: User) -> int:
    """Returns the correct rank (1–4) for the player's current prestige_points.
    Compares prestige_points against rank4_threshold, rank3_threshold, rank2_threshold in descending order.
    Called after every prestige_points mutation (win, loss, rank_xp award).
    Caller compares the return value to user.rank and calls apply_rank_change() if they differ.
    Handles both promotions and demotions — no directional logic needed."""

def apply_rank_change(user: User, new_rank: int) -> None:
    """Mutates user.rank in place. Called when evaluate_rank() returns a value different from user.rank.
    Works identically for promotions and demotions."""
```

**Prestige / stat recording**
```python
def record_win(conf: GuildSettings, user: User, game_slug: str, payout: int, bet: int) -> None:
    """Increments total_wins, total_payout_earned, and all per-game win stats.
    Updates largest_single_payout and game_highest_single_payout[slug] if payout is a new record.
    Updates game_play_counts, game_win_counts, game_total_payout, game_highest_bet for the slug.
    Adds conf.prestige_win_points to user.prestige_points.
    Does not call evaluate_rank — caller does that."""

def record_loss(conf: GuildSettings, user: User, game_slug: str, amount_lost: int) -> None:
    """Increments total_losses and per-game loss stats.
    Updates largest_single_loss and game_highest_single_loss[slug] if amount_lost is a new record.
    Updates game_play_counts and game_loss_counts for the slug.
    Subtracts conf.prestige_loss_points from user.prestige_points, floored at 0.
    Does not call evaluate_rank — caller does that."""
```

**Multiplier Wheel state**
```python
def get_pending_multiplier(user: User) -> float | None:
    """Returns the multiplier if one exists and hasn't expired, else None (and clears expired state)."""

def consume_multiplier(user: User) -> float | None:
    """Reads, returns, and clears the pending multiplier. Call on eligible game resolution."""
```

**Lucky Streak state**
```python
def has_lucky_streak(user: User) -> bool:
    """Returns True if the player has an active, unexpired Lucky Streak.
    Clears lucky_streak_expiry in place if it has expired (side effect).
    Call at the start of every game resolution to decide whether to apply the bonus.
    """

def apply_lucky_streak_bonus(raw_payout: int) -> int:
    """Returns the bonus chip/currency amount to add on top of a win.
    Bonus = raw_payout * LUCKY_STREAK_BONUS_PCT.
    'raw_payout' is the gross payout as calculated by game logic BEFORE any Multiplier Wheel
    or other stack modifiers are applied. It does NOT include the original bet returned to the player.
    Example: bet 100, game pays 2x → raw_payout = 200 → bonus = 50 → player receives 250 + bet return.
    This function is pure math — the caller is responsible for checking has_lucky_streak() first.
    """

def cancel_lucky_streak(user: User) -> None:
    """Clears lucky_streak_expiry (cancels the streak). Called on the player's first loss.
    After calling this, the game code must notify the player:
      e.g. 'Your Lucky Streak has ended — better luck next time.'
    Notification is the caller's responsibility; this function only mutates state.
    """
```
> **Streak behaviour summary:**
> - Awarded by Scratch Card or Mystery Wheel → sets `lucky_streak_expiry = now + 60 minutes`
> - On every **win**: `has_lucky_streak()` → if True, call `apply_lucky_streak_bonus(raw_payout)` → credit the bonus on top of normal payout. Streak remains active.
> - On every **loss**: call `cancel_lucky_streak(user)` → notify player the streak is gone.
> - On game load / embed render: always call `has_lucky_streak()` — the expiry check clears stale state automatically.
> - Stacks with Multiplier Wheel: Lucky Streak bonus is calculated from `raw_payout` first; Multiplier Wheel profit bonus is calculated from profit after Lucky Streak is added.

**Specialty title evaluation**
```python
def evaluate_specialty_titles(user: User) -> list[str]:
    """Checks user lifetime stats and returns a list of newly earned permanent specialty title slugs
    not already in user.earned_titles. Called after every game resolution.
    Evaluates both playstyle titles (card_shark, daredevil, etc.) and milestone titles
    (centurion, high_earner, iron_streak). Caller appends results to user.earned_titles
    and notifies the player of each newly unlocked title."""
```

**RNG settings helper**
```python
def get_game_rng(conf: GuildSettings, game_slug: str, key: str) -> Any:
    """Returns the configured RNG value for a game parameter.
    Falls back to CONFIGURABLE_RNG[game_slug][key]['default'] if not set by admin.
    Raises ValueError if game_slug is in CARD_MATH_GAMES — these are never RNG-configurable.
    Raises KeyError if game_slug is not in CONFIGURABLE_RNG or key is not a valid param for that game.
    Game logic should always call this — never read game_rng_settings directly.
    """
```

**Channel check**
```python
def is_allowed_channel(conf: GuildSettings, channel_id: int) -> bool:
    """Returns True if allowed_channels is empty (all allowed) or channel_id is in the list."""

def is_blacklisted(conf: GuildSettings, user_id: int) -> bool:
    """Returns True if the user_id is in conf.blacklisted_users. Used in pre-flight checks before showing the lobby."""
```

**Bonus Bet Token helpers**
```python
def has_bonus_bet_token(user: User) -> bool:
    """Returns True if user.bonus_bet_tokens > 0."""

def consume_bonus_bet_token(user: User, conf: GuildSettings, game_slug: str, allin_tier: int | None = None) -> bool:
    """Validates eligibility and consumes one token. Returns True if consumed, False if ineligible.
    Checks: game_slug in BONUS_BET_TOKEN_ELIGIBLE_GAMES; for All-In, also checks allin_tier <= 2.
    If ineligible, returns False without mutating state (token is NOT consumed).
    Caller should notify the player with an ephemeral message if False is returned.
    """
```

**Free Spin helper**
```python
def consume_free_spin(user: User) -> bool:
    """Decrements free_spins_available by 1 and returns True if a free spin was available.
    Returns False if free_spins_available == 0 (no spin consumed).
    When True is returned, the Slots game must skip deduct_balance() entirely for that play.
    Free spins only apply to Slots — not to any other game.
    """
```

**Formatting helpers** — these live in `common/formatting.py`, not `helper_functions.py`
```python
def chips_label(amount: int) -> str:
    """Returns e.g. '1,250 chips' formatted with commas."""

def describe_chip_bet(amount: int) -> str:
    """Decomposes a bet amount into chip denominations using a greedy algorithm
    (largest denomination first) and returns a natural-language description.

    Examples:
      21  -> 'two $10 chips and one $1 chip'
      100 -> 'one $100 chip'
      37  -> 'one $25 chip, one $10 chip, and two $1 chips'

    This is cosmetic only — used in game flavor text like:
      'You set down {describe_chip_bet(bet)} for a total bet of {bet:,} chips.'

    Only called when conf.payment_mode == 'chips'. Never called in bank mode.
    """

def rank_display(rank: int) -> str:
    """Returns e.g. '⭐ High Roller'."""

def title_display(user: User) -> str:
    """Returns active specialty title string or empty string."""

def build_balance_footer(user: User, conf: GuildSettings, balance: int) -> str:
    """Returns footer text like '🃏 Card Shark | High Roller | Balance: 4,800 chips'."""
```

---

## Phase 4 — Admin Setup Command in `commands/admin_commands.py`

This is the interactive embed-and-button setup wizard. It walks the server owner through every configurable setting. It does **not** have to configure everything in one session — each setting can also be changed individually via subcommands.

### Admin permission pattern

All admin commands live in this file under a single top-level command group. The admin permission check is applied **once at the group level** — all subcommands inherit it automatically. Do NOT decorate individual subcommands with `@commands.admin_or_permissions`. Define a `cog_check` or use `@group.before_invoke` that calls `await check_is_admin(ctx)` and raises `commands.CheckFailure` (shown as an ephemeral error) if it returns False.

For View button callbacks (where group-level checks don't apply), call `await check_is_admin(interaction)` at the top of the callback and respond with an ephemeral error if it returns False. Never skip this check in callbacks.

If a shared `is_admin` utility exists in another cog in this workspace (e.g., `vainneutils`), import its function here and call it inside `check_is_admin()` — the call site stays identical.

### Command structure

Top-level group: `[p]highrollerclubset` (alias: `hrcset`, `guild_only=True`)
Admin check applied at the group level — all subcommands are covered by a single check, no per-command decorator needed.

```
[p]highrollerclubset setup          — launches the full multi-page embed wizard
[p]highrollerclubset set <setting>  — set a single value directly (for quick edits post-setup)
[p]highrollerclubset status         — shows current config as a read-only embed
[p]highrollerclubset reset          — resets all settings to defaults (with confirmation prompt)
```

All of the above are also accessible via the `hrcset` alias, e.g. `[p]hrcset setup`, `[p]hrcset set paymentmode chips`.

### The `setup` wizard — embed-driven button flow

The wizard is a multi-page discord.ui.View. Each page covers one logical group of settings. Navigation: **Back** / **Next** / **Done** buttons at the bottom of every page. Values are not saved until the player hits **Done** on the final page (or hits **Save & Exit** on any page).

Page 1 — **Payment Mode**
- Title: `"Payment Setup"`
- Two buttons: `[ House Chips ]` `[ Server Currency ]`
- If House Chips is selected:
  - Shows a modal prompt: *"How many chips does 1 server currency unit buy?"* (default 100; stored as `discord_currency_conversion_rate`)
  - Shows a second toggle: `[ Allow Chip Conversion ]` / `[ Conversion Disabled ]` — controls `discord_currency_conversion_enabled`; when enabled, players may cash out chips at the same rate via the Teller Window
- Selected payment mode highlights in green; chip conversion toggle highlights green when enabled

Page 2 — **Rank Progression**
- Title: `"Rank Progression"`
- Shows current thresholds and prestige point values in embed fields
- Note shown in embed: *"Rank is fluid — players promote and demote based on their current prestige point total. There is no floor between ranks."*
- Three threshold buttons: `[ Set Regular Threshold ]` `[ Set High Roller Threshold ]` `[ Set Whale Threshold ]`
- Each opens a modal: integer input for prestige points required to hold that rank
- Two point value buttons: `[ Set Win Points ]` `[ Set Loss Points ]`
- Each opens a modal: float input; validated > 0 for win points, ≥ 0 for loss points

Page 3 — **Rank Bet Multipliers**
- Title: `"Bet Limit Multipliers"`
- Shows a table: Rank → current multiplier
- Toggle at top of page: `[ Multipliers Enabled ]` / `[ Multipliers Disabled ]` — when disabled, all fields grey out and a note reads *"Ranks are cosmetic only — all players bet at base limits"*
- Four buttons, one per rank (Member is always 1.0x, greyed out/disabled). All four disabled when toggle is off.
- Each opens a modal for the multiplier value (float, validated 1.0–10.0)

Page 4 — **Base Bet Limits**
- Title: `"Game Bet Limits"`
- Game selector dropdown — only games that have ranged bet limits (i.e. the 10 games in `DEFAULT_BET_LIMITS`). Exclude `mysteryspin` (free, no bet) and `multiplierwheel` (flat cost set on Page 8).
- After selecting a game: shows two modals in sequence — min bet, max bet
- Shows currently configured limits per game in embed fields

Page 5 — **All-In Tier Cap**
- Title: `"All-In Risk Settings"`
- Shows the 5 tier names and current cap
- Buttons `[ 1 ] [ 2 ] [ 3 ] [ 4 ] [ 5 ]` — selected tier highlights green
- Selecting a lower tier greyes out higher tiers visually in the embed

Page 6 — **Scratch Cards**
- Title: `"Scratch Card Rewards"`
- Toggle button: `[ Enable ]` / `[ Disable ]` (shows current state)
- Cooldown selector: buttons for `[ 12h ]` `[ 24h ]` `[ 48h ]` or modal for custom hours
- Reward pool: multi-select buttons (each reward type toggles on/off, green = active)

Page 7 — **Mystery Wheel (Daily Free Spin)**
- Title: `"Daily Free Spin"`
- Toggle: `[ Enable ]` / `[ Disable ]`
- Timezone input: opens a modal, validated against `zoneinfo.available_timezones()`
- Reward pool: same multi-select button pattern as scratch cards

Page 8 — **Multiplier Wheel**
- Title: `"Multiplier Wheel — The Booster"`
- Spin cost: modal number input (min 1)
- Expiry: buttons `[ 15 min ]` `[ 30 min ]` `[ 60 min ]` or custom modal

Page 9 — **Big Six Wheel**
- Title: `"Big Six Wheel — House Edge"`
- House segments selector: buttons `[ 6 ] [ 8 ] [ 10 ] [ 12 ]`
- Shows win probability table updating live in embed as selection changes

Page 10 — **RNG Game Settings**
- Title: `"Win Chance Tuning"`
- Intro note in embed: *"Card-based games (Blackjack, Hi-Lo, War, Video Poker, Poker) use fixed deck math and are not configurable here."*
- Game selector dropdown — only pure-RNG games listed (Slots, All-In, Keno, Roulette, Multiplier Wheel)
- After selecting a game, embed updates to show that game's configurable params with current values and allowed ranges
- A `[ Edit ]` button per param opens a modal with the param name, current value, and min/max shown in the placeholder text
- Values are validated against `CONFIGURABLE_RNG` bounds before accepting — show an inline error if out of range
- All-In sub-selection: shows all 5 tiers as separate editable rows

Page 11 — **Game Toggles**
- Title: `"Game Availability"`
- Intro note: *"All games are enabled by default. Disable any that don't fit your server. Disabled games appear locked on the Game Floor — player stats for those games are preserved."*
- One toggle button per game (13 total across rows). Each button shows the game name and current state — green when enabled, grey when disabled.
- Clicking a button flips that game's state in `games_enabled` immediately (live toggle, no confirm step needed).
- A `[ Enable All ]` button at the bottom resets all entries to True.

Page 12 — **Channel Lock**
- Title: `"Channel Restrictions"`
- Lists currently locked channels (if any)
- Buttons: `[ Add Channel ]` (opens modal for channel ID or mention) `[ Clear All ]`
- Shows "All channels allowed" if list is empty

Final confirmation page — **Review & Save**
- Title: `"Configuration Summary"`
- Shows all chosen settings as embed fields
- Two buttons: `[ Save Configuration ]` `[ Go Back ]`
- On save: writes to `GuildSettings`, calls `self.save()`, sends success message

### Single-setting subcommands (`[p]highrollerclubset set` / alias `[p]hrcset set`)

Each of these mirrors a wizard page for quick post-setup edits:
```
[p]highrollerclubset set paymentmode <chips|bank>
[p]highrollerclubset set conversionrate <amount>         — chips per 1 server currency unit (discord_currency_conversion_rate)
[p]highrollerclubset set conversion <enable|disable>    — allow or block players from cashing chips out to server currency
[p]highrollerclubset set rankthreshold <rank 2|3|4> <amount>
[p]highrollerclubset set prestigewin <float>             — prestige points per win (default 1.0; min 0.1)
[p]highrollerclubset set prestigeloss <float>            — prestige points removed per loss (default 0.75; min 0.0)
[p]highrollerclubset set rankmultipliers <enable|disable>    — toggle whether ranks affect bet limits
[p]highrollerclubset set multiplier <rank 1|2|3|4> <float>
[p]highrollerclubset set betlimits <game_slug> <min> <max>
[p]highrollerclubset set allintier <1-5>
[p]highrollerclubset set rng <game_slug> <param_key> <value>  — set a single RNG param; rejects card-math games
[p]highrollerclubset set scratch <enable|disable>
[p]highrollerclubset set scratchcooldown <hours>
[p]highrollerclubset set mysteryspin <enable|disable>
[p]highrollerclubset set timezone <timezone_string>
[p]highrollerclubset set wheelcost <amount>
[p]highrollerclubset set housesegments <6|8|10|12>
[p]highrollerclubset set channel add <#channel>
[p]highrollerclubset set channel clear
[p]highrollerclubset set blacklist add <@user>    — add a player to blacklisted_users
[p]highrollerclubset set blacklist remove <@user> — remove a player from blacklisted_users
[p]highrollerclubset set blacklist list            — show all currently blacklisted users
[p]highrollerclubset set game <game_slug> <enable|disable>  — enable or disable a specific game
[p]highrollerclubset set game list                — show all games and their current enabled state
```

`[p]hrcset set game` validation rules:
- Reject with a clear error if `game_slug` is not in `GAME_SLUGS`
- On success: write to `conf.games_enabled[game_slug]` and call `self.save()`
- Notify the admin of the new state: *"✅ Blackjack is now disabled. Players will see it as locked on the Game Floor."*

`[p]hrcset set rng` validation rules:
- Reject with a clear error if `game_slug` is in `CARD_MATH_GAMES`
- Reject if `game_slug` or `param_key` is not in `CONFIGURABLE_RNG`
- Clamp/reject the value if it falls outside the `min`/`max` bounds defined in `CONFIGURABLE_RNG`
- On success: write to `conf.game_rng_settings[game_slug][param_key]` and call `self.save()`

### `[p]hrcset status` embed layout

```
┌─────────────────────────────────────────────┐
│  HighRollerClub — Server Configuration      │
├─────────────────────────────────────────────┤
│ Payment Mode       │ House Chips (100:1)     │
│ Rank Thresholds    │ R2: 50 | R3: 200 | R4: 1000      │
│ Prestige Points    │ Win: +1.0 | Loss: -0.75           │
│ Multipliers        │ 1x / 1.5x / 2x / 3x (Enabled)    │
│ All-In Cap         │ Tier 4 (Desperate)      │
│ Scratch Cards      │ Enabled — 24h cooldown  │
│ Daily Free Spin    │ Disabled                │
│ Wheel Cost         │ 100 chips               │
│ House Segments     │ 8                       │
│ RNG Overrides      │ Slots: 15% edge | Roulette: American │
│ Games Enabled      │ All enabled  (or lists disabled games e.g. "Club Poker, Mystery Wheel disabled") │
│ Channel Lock       │ #casino only            │
└─────────────────────────────────────────────┘
```

---

## Phase 5 — Player Navigation (`commands/user_commands.py`)

Only after Phases 1–4 are complete and the config layer is verified working.

### Image Theming

All embeds support optional images via `EMBED_IMAGES` in `constants.py`. All asset URLs are now populated -- add the following snippet **uncommented** to every embed build block in new games:

```python
# Thumbnail (set_thumbnail for all views; set_image for Main Lobby banner only)
if url := embed_image("<key>"):
    embed.set_thumbnail(url=url)   # or embed.set_image(url=url) for the Lobby banner
```

| View / Game | `EMBED_IMAGES` key | Discord method |
|---|---|---|
| Main Lobby | `"lobby"` | `.set_image()` — large banner at bottom |
| Game Floor | `"game_floor"` | `.set_thumbnail()` — small top-right |
| Teller Window | `"teller"` | `.set_thumbnail()` |
| Stats View | `"stats"` | `.set_thumbnail()` |
| Leaderboards | `"leaderboard"` | `.set_thumbnail()` |
| Help & Info | `"help"` | `.set_thumbnail()` |
| Slots | `"slots"` | `.set_thumbnail()` |
| War | `"war"` | `.set_thumbnail()` |
| All-In | `"allin"` | `.set_thumbnail()` |
| Blackjack | `"blackjack"` | `.set_thumbnail()` |
| Hi-Lo | `"hilo"` | `.set_thumbnail()` |
| Keno | `"keno"` | `.set_thumbnail()` |
| Roulette | `"roulette"` | `.set_thumbnail()` |
| Video Poker | `"videopoker"` | `.set_thumbnail()` |
| Club Poker | `"clubpoker"` | `.set_thumbnail()` |
| Big Six | `"big6"` | `.set_thumbnail()` |
| Mystery Wheel | `"mysteryspin"` | `.set_thumbnail()` |
| Multiplier Wheel | `"multiplierwheel"` | `.set_thumbnail()` |
| Double | `"double"` | `.set_thumbnail()` |

All URLs are already populated in `EMBED_IMAGES`. New game views should include the `embed_image()` snippet uncommented from the start -- no further activation steps are needed.

---

### Single entry command: `[p]highrollerclub`

This is the **only command players ever need**. It launches the Main Lobby. All navigation from that point is button-driven inside a single Discord message. No subcommands, no game-specific commands exist for players.

**Pre-flight checks** (silent ephemeral error if any fail — do not show the lobby):
1. `is_allowed_channel(conf, ctx.channel.id)`
2. Player is not blacklisted
3. If `payment_mode == "chips"` and `chip_balance == 0` and the player has no prior activity (`total_wins == 0 and total_losses == 0`): auto-grant `STARTING_CHIP_BALANCE` (100) chips with a one-time welcome embed before opening the lobby. For returning players with 0 chips, open the lobby normally — the **Teller Window** on the Game Floor handles top-ups.

---

### Main Lobby View

**Embed:**
- Title: `"The High Roller Club"`
- Description: *"Welcome back, {display_name}."* — rank badge and active specialty title on the next line
- Footer: current balance — chip mode: `"{amount:,} chips"` — bank mode: `"{amount:,} {await bank.get_currency_name(guild)}"` — never hardcode "credits" or any currency name

**Row 0 — Navigation buttons:**

| Label | Style |
|---|---|
| `🎲 Game Room` | Green |
| `📊 Your Stats` | Blurple |
| `🏆 Leaderboards` | Blurple |
| `❓ Help & Info` | Grey |

**Row 1:**

| Label | Style | Behavior |
|---|---|---|
| `✕ Close` | Red | Disables all buttons, edits embed to *"The Club has closed its doors for now."* |

---

### Game Room View

Triggered by: `🎲 Game Room`

**Embed:**
- Title: `"The Game Floor"`
- Description: *"Welcome to the floor, {display_name} — {rank_display}."* followed by balance line
- Balance line: `"Balance: {balance_string}"` — uses actual currency name in bank mode
- Brief atmosphere flavor text line
- Footer: active specialty title if any

**Row 0, Col 0 — Teller Window (chip mode only):**

| Label | Style | Behavior |
|---|---|---|
| `🏦 Teller Window` | Blurple | Opens the Teller Window embed. **Not rendered at all in bank mode** — not greyed, simply absent. |

**Game buttons** — 13 total, one per game, filling the remaining button slots after the Teller Window (if present). Layout:
- **Chip mode:** Teller at [Row 0, Col 0]; 4 game buttons at [Row 0, Cols 1–4]; 5 at Row 1; 4 at Row 2; navigation at Row 3. (4 rows total — within Discord's 5-row limit.)
- **Bank mode:** 5 game buttons at Row 0; 5 at Row 1; 3 at Row 2; navigation at Row 3.
- Games toggled off by admin config (e.g., Mystery Wheel when `mystery_wheel_enabled == False`) display with grey style and a `🔒` prefix — they render but cannot be interacted with.

**Navigation row:**

| Label | Style | Behavior |
|---|---|---|
| `← Back` | Grey | Returns to Main Lobby (edits same message) |
| `✕ Close` | Red | Closes session |

Pressing a game button launches that game's `View` in the same message, replacing the Game Room embed. All game Views return to the Game Room (not the Lobby) when the player hits `[ Back to Floor ]`.

---

### Teller Window View (Chip Mode Only)

Triggered by: `🏦 Teller Window` on the Game Floor. Never rendered when `payment_mode == "bank"`.

**Embed:**
- Title: `"🏦 The Teller Window"`
- Description: Current chip balance + rate line: `"Rate: {rate:,} chips per 1 {currency_name}"` + conversion note if `discord_currency_conversion_enabled == True`

**Row 0:**

| Label | Style | Behavior |
|---|---|---|
| `💰 Buy Chips` | Green | Opens the Buy Chips flow |
| `🔄 Convert Chips` | Blurple (disabled if `discord_currency_conversion_enabled == False`) | Opens the Convert Chips flow |

**Row 1:**

| Label | Style | Behavior |
|---|---|---|
| `← Back` | Grey | Returns to Game Floor |
| `✕ Close` | Red | Closes session |

**Buy Chips flow:**
1. Modal: *"How many chips would you like to buy?"* — placeholder shows rate: `"Rate: {rate:,} chips per 1 {currency_name}"`
2. Input validated as positive integer (min 1)
3. Cost: `cost = math.ceil(chips_requested / discord_currency_conversion_rate)` server currency units
4. Confirmation embed replaces Teller Window:
   - *"Buy {chips_requested:,} chips for {cost:,} {currency_name}? Your bank balance: {bank_balance:,} {currency_name}."*
   - Row 0: `[ ✅ Confirm ]` (Green) | `[ ❌ Cancel ]` (Red)
5. Cancel → return to Teller Window embed (no changes made)
6. Confirm:
   - Re-check `bank.get_balance(player) >= cost` — reject with ephemeral error if insufficient
   - `bank.withdraw_credits(player, cost)` → `user.chip_balance += chips_requested` → `save()`
   - Success embed: *"Transaction complete! {chips_requested:,} chips added. New balance: {new_balance:,} chips."*
   - Row 0: `[ ← Back to Teller ]` (Grey) | `[ 🎲 To the Floor ]` (Green)

**Convert Chips flow** (only accessible when `discord_currency_conversion_enabled == True`):
1. Modal: *"How many chips would you like to convert?"* — placeholder: `"Min {rate:,} chips = 1 {currency_name}. Remainder is not converted."`
2. Validate: positive integer; minimum = `discord_currency_conversion_rate` (must yield ≥ 1 server currency unit — reject below minimum with ephemeral error)
3. Payout: `payout = chips_requested // discord_currency_conversion_rate` (floor division; remainder chips are neither deducted nor converted)
4. Confirmation embed:
   - *"Convert {chips_requested:,} chips → {payout:,} {currency_name}. Remainder: {chips_requested % rate:,} chips (not deducted, not converted)."*
   - Row 0: `[ ✅ Confirm ]` (Green) | `[ ❌ Cancel ]` (Red)
5. Cancel → return to Teller Window embed (no changes made)
6. Confirm:
   - Check `user.chip_balance >= chips_requested` — reject with ephemeral if insufficient
   - `user.chip_balance -= chips_requested` → `bank.deposit_credits(player, payout)` → `save()`
   - Success embed with updated chip balance and bank balance
   - Row 0: `[ ← Back to Teller ]` (Grey) | `[ 🎲 To the Floor ]` (Green)

---

### Stats View

Triggered by: `📊 Your Stats`

**Embed:**
- Title: `"{display_name}'s Club Record"`
- Fields (use inline layout where sensible):

| Field | Value |
|---|---|
| **Rank** | tier name (e.g. *High Roller*) + active specialty title, or *"None"* |
| **Prestige** | `{prestige_points:.2f} pts` — next threshold shown: e.g. *"Next rank at 200 pts"* or *"Max rank"* if Rank 4 |
| **Balance** | chip balance in chip mode; live `bank.get_balance` in bank mode — actual currency name |
| **Record** | `{total_wins}W / {total_losses}L ({win_rate:.1f}% win rate)` |
| **Largest Payout** | `largest_single_payout` formatted with commas + currency label |
| **Largest Loss** | `largest_single_loss` formatted with commas + currency label |
| **Favorite Game** | display name of `max(game_play_counts, key=game_play_counts.get)`, or *"None yet"* |
| **Game Breakdown** | Non-inline. Monospace code block (triple backtick). Only rendered if the player has played at least one game. Lists only games with `game_play_counts[slug] > 0`, sorted alphabetically by display name. Format: |

```
Game              W      L    Win%
──────────────────────────────────
Blackjack             0      0      —
Slots                12     41  22.6%
```

Column width for the name column is dynamic (`max(len(display_name) for played games)`). Win% shows `—` if total plays is 0 (shouldn't happen since only played games appear). Games with 0 plays are omitted entirely until the player's first attempt.

**Row 0:**

| Label | Style | Behavior |
|---|---|---|
| `🎭 Manage Titles` | Blurple | Opens a title selection embed listing all titles in `user.earned_titles`. Player taps one to set it as `active_title`. Tapping the currently active title deselects it (no active title). Rank title always displays separately — it is not selectable here. |
| `← Back` | Grey | Returns to Main Lobby |
| `✕ Close` | Red | Closes session |

---

### Leaderboards View

Triggered by: `🏆 Leaderboards`

**Screen 1 — Game Selector:**
- Embed title: `"Leaderboards — Select a Game"`
- One button per game; greyed out and non-clickable if no data exists for that game yet
- Back + Close buttons

**Screen 2 — Per-Game Leaderboard:**
- Embed title: `"{Game Display Name} Leaderboard"`
- Default sort: **Total Payout** (`game_total_payout[slug]`)
- 10 entries per page; paginated — display is never truncated
- Entry format: `{position}. {display_name} — {value:,}`
- Display names fetched via `guild.get_member(uid).display_name` at render time; fall back to `str(uid)` if not in cache
- Active sort filter button shows Green style; all others show Grey

**Row 0 — Sort filter buttons (5 max per Discord row):**

| Label | Sorts by |
|---|---|
| `💰 Total Payout` | `game_total_payout[slug]` |
| `🏆 Total Wins` | `game_win_counts[slug]` |
| `⭐ Best Win` | `game_highest_single_payout[slug]` |
| `🎲 Biggest Bet` | `game_highest_bet[slug]` |
| `💸 Biggest Loss` | `game_highest_single_loss[slug]` |

**Row 1 — 6th sort filter + Pagination:**

| Label | Behavior |
|---|---|
| `📉 Total Losses` | Sorts by `game_loss_counts[slug]` |
| `◀ Prev` | Previous page (disabled on page 1) |
| `▶ Next` | Next page (disabled on last page) |

**Row 2 — Navigation:**

| Label | Behavior |
|---|---|
| `← Back` | Returns to Game Selector screen |
| `✕ Close` | Closes session |

---

### Help & Info View

Triggered by: `❓ Help & Info`

Follows the same structure used in `gafishing` and `dinocollector`.

**Screen 1 — Overview:**
- Embed title: `"The High Roller Club — How It Works"`
- Covers: ranks and prestige system, payment modes, specialty titles, bonus tokens, scratch cards, multiplier wheel
- One button per game for per-game help rules
- Back + Close buttons

**Per-game help screen:**
- Embed title: `"{Game Name} — How to Play"`
- Explains: rules, how to place a bet, win conditions, special mechanics, payout table
- Back button returns to Overview screen
- Close button closes the session

---

### Navigation Architecture Rules

- **One message, always edited** — never send a second message for navigation. All view transitions edit the original response in place.
- **View chaining** — each View class holds a `previous_view` reference (or `None` for the Lobby). Back always restores the prior View to the same message.
- **Timeouts:**
  - Main Lobby: `timeout=300`
  - Game Room: `timeout=120`
  - Stats, Leaderboards, Help: `timeout=180`
  - On timeout: all buttons disabled, embed footer updated to *"Session expired. Run the command again to return."* — bet is refunded if a game was in progress.
- **Display names** — always fetched from `interaction.guild.get_member(user_id).display_name` at render time. Never stored in the database. Fall back to `str(user_id)` if member is not in cache.
- **Balance display** — chip mode: `f"{amount:,} chips"`. Bank mode: `f"{amount:,} {await bank.get_currency_name(guild)}"`. No hardcoded currency names anywhere in view or game code.
- **Game view signature** — every game View is initialized as `GameView(interaction, conf, user, save_callback)`. On game end: `[ Play Again ]` resets the same game View; `[ Back to Floor ]` restores the Game Room View.

---

## Phase 6 — Individual Games (in recommended implementation order)

Implement games from simplest to most complex. Each game gets its own file in `games/`.

| Order | Game | File | Reason |
|---|---|---|---|
| 1 | Slots | `games/slots.py` | Fully instant, no interaction after bet — simplest possible flow |

### Slots — Game Mechanics (`games/slots.py`)

A 3×3 reel grid is generated independently each spin. Two types of paylines are evaluated:

1. **Horizontal center row (primary)** — the middle row is the main payline. Partial matches (2-of-3) pay for CHR, DIA, and BEL. Full 3-of-a-kind pays for all symbols except `---`.
2. **Vertical columns (secondary)** — all three rows in a single reel column show the same paying symbol. All matching columns pay simultaneously. Column payouts are roughly 50% of the equivalent center-row 3-of-a-kind multiplier.

**Payout table (horizontal center row):**

| Symbol | ×3 | ×2 |
|--------|----|----|
| 777    | 50× | — |
| BAR    | 15× | — |
| BEL    | 10× | 4× |
| DIA    |  6× | 3× |
| CHR    |  4× | 2× |
| ---    | —   | — |

**Column payout table (×3 only):** 777→25×, BAR→7×, BEL→5×, DIA→3×, CHR→2×.

**Win frequency at default 15 % house edge:** ~25 % of spins yield at least one paying combination on the horizontal payline. Column wins add additional frequency on top.

**Prestige delta:** Slots uses a reduced prestige scale (`PRESTIGE_SCALE["slots"] = 0.3` in `constants.py`). `record_win` and `record_loss` automatically apply this — no extra code is needed in the view.

**Key implementation note:** `calculate_payout` takes the full 3×3 `grid` (not just the payline). The call in `slots_view.py` is `calculate_payout(bet, grid)`.
| 2 | All-In | `games/all_in.py` | One decision (tier), one flip — tests bet validation + risk tiers |
| 3 | War | `games/war.py` | Solo mode first, then 2-player — tests card draw + multiplayer |
| 4 | Hi-Lo | `games/hi_lo.py` | Press-your-luck chain — tests multi-step interaction |
| 5 | Double | `games/double.py` | Dice-roll press-your-luck, exponential doubling — tests hold/bust loop |
| 6 | Blackjack | `games/blackjack.py` | Two-phase: deal → hit/stand → resolve |
| 7 | Keno | `games/keno.py` | Number picker — tests multi-select UI |
| 8 | Roulette | `games/roulette.py` | Multiple bet types on a single spin |
| 9 | Big Six Wheel | `games/big_6_wheel.py` | Segment betting + house edge segments |
| 10 | Multiplier Wheel | `games/multiplier_wheel.py` | Paid spin that sets pending state |
| 11 | Mystery Wheel | `games/mystery_wheel.py` | Free daily spin — calendar-day gating |
| 12 | Video Poker | `games/poker.py` | Two-phase + hand ranking table |
| 13 | Club Poker | `games/poker.py` | Multiplayer, hidden hands, DM architecture — shares file with Video Poker; implement last |

> **Poker file note:** Both Video Poker and Club Poker live in `games/poker.py`. Video Poker is implemented as a standalone `VideoPokersView` class; Club Poker as a separate `ClubPokerView` class in the same file. The `club_poker.py` file should not be created — do not split them.

### Double — Game Mechanics (`games/double.py`)

Player places an initial bet (min 10, max 250 by default). The game then enters a loop:

1. **Roll phase:** A random roll is evaluated against the configurable `win_chance` (default 50%). On success, the current pot doubles. On failure, the player loses their entire bet immediately with no payout.
2. **Decision phase:** If the roll succeeds, the player is shown the current pot value and presented two choices:
   - **Cash Out** — ends the game and credits the current pot to the player.
   - **Double Again** — rolls again; success doubles the pot again, failure loses everything.
3. **Pot math:** Each successful roll doubles the *pot* — not just the profit. A 100-chip bet progresses: 200 → 400 → 800 → 1,600 etc. The return on a cash-out after N successes is `bet × 2ᴺ`.
4. **No ceiling:** There is no cap on how many times a player may press Double Again.

**Risk profile:** High variance, exponential upside with total-loss on bust. Due to uncapped payout potential, `double` is excluded from `BONUS_BET_TOKEN_ELIGIBLE_GAMES` and `MULTIPLIER_ELIGIBLE_GAMES`.

**Win chance config:** Admins may tune `win_chance` via `[p]hrcset set rng double win_chance <value>` (allowed range: 0.30–0.70).

**File:** `games/double.py`

### Per-game implementation checklist

For each game:
- [ ] Define the `View` class with correct timeout
- [ ] Add a `_check_access(interaction)` guard method — called at the top of every action button callback (spin, play again, deal, etc.) before any game logic runs. It must:
  1. Call `is_allowed_channel(conf, interaction.channel_id)` — respond with ephemeral error and return `False` if the channel is not permitted
  2. Call `conf.games_enabled.get("<game_slug>", True)` — respond with ephemeral error and return `False` if the game is disabled
  Callers must `return` immediately when `_check_access` returns `False`.
- [ ] Add commented-out thumbnail to embed build block: `# if url := embed_image("<game_slug>"): embed.set_thumbnail(url=url)` — activate when asset is uploaded
- [ ] Implement bet input modal — dynamically set its label and placeholder to show the player's actual min/max:
  ```python
  min_bet, max_bet = get_bet_limits(conf, "<game_slug>", user.rank)
  modal.bet_input.label = f"Bet Amount (min {min_bet:,} · max {max_bet:,})"
  modal.bet_input.placeholder = f"Enter a value between {min_bet:,} and {max_bet:,}"
  ```
  Call `get_bet_limits` at the time the Spin button is pressed, not at view construction time.
- [ ] Call `validate_bet()` — reject with ephemeral message if invalid
- [ ] Store the validated bet on the view (`self._last_bet = bet`) so a "Spin Same Bet" button can reuse it without opening the modal
- [ ] Call `deduct_balance()` before resolution begins
- [ ] Resolve game outcome
- [ ] On win: check `has_lucky_streak(user)` → if True, call `apply_lucky_streak_bonus(raw_payout)` to get the bonus amount; add it to raw_payout to get `total_payout`
- [ ] Multiplier Wheel — check `game_slug in MULTIPLIER_ELIGIBLE_GAMES` (import from `common.constants`) **before** calling `consume_multiplier()`. Never call `consume_multiplier()` on ineligible games — it would silently consume the player's pending multiplier:
  ```python
  if "<game_slug>" in MULTIPLIER_ELIGIBLE_GAMES:
      multiplier = consume_multiplier(user)
      if multiplier is not None:
          profit = total_payout - bet
          total_payout += int(profit * (multiplier - 1.0))
  ```
- [ ] If game is Slots and `consume_free_spin(user)` returns True, skip `deduct_balance()` for this play (bet was free)
- [ ] If `has_bonus_bet_token(user)`, call `consume_bonus_bet_token(user, game_slug)` before resolution. The helper internally checks `BONUS_BET_TOKEN_ELIGIBLE_GAMES` and returns `False` on ineligible games without consuming the token — so it is always safe to call. If it returns `True`, double `total_payout` on win.
- [ ] On loss: call `cancel_lucky_streak(user)` if streak was active, then send player a notification that the streak ended
- [ ] Call `credit_balance(member, conf, user, total_payout)` on win (single call)
- [ ] Call `record_win(conf, user, game_slug, total_payout, bet)` or `record_loss(conf, user, game_slug, amount_lost)` — prestige delta is automatically scaled by `PRESTIGE_SCALE.get(game_slug, 1.0)` inside these helpers; no extra code needed in the view
- [ ] Call `evaluate_rank(conf, user)` — compare result to `user.rank`; if different, call `apply_rank_change(user, new_rank)` and notify the player (promotion or demotion message)
- [ ] Call `evaluate_specialty_titles()` and handle new title notification
- [ ] Call `self.save()` via callback
- [ ] Show resolution embed with flavor text from constants
- [ ] Show `[ Change Bet ]` (opens modal), `[ Spin (X) ]` (reuses `self._last_bet`, skip modal), and `[ Back to Floor ]` buttons after result

---

## Phase 7 — Listeners and Tasks

Implement after all games are working.

**`listeners/messages.py`** — message cleanup (if `message_cleanup_enabled` is True): delete player command invocations in the casino channel to keep it tidy.

**`tasks/`** — periodic background work on bot startup/restart:
- Scan all users with a non-None `pending_multiplier_expiry` and clear any that are past their expiry timestamp.
- Scan all users with a non-None `lucky_streak_expiry` and clear any that are past their expiry timestamp.
- Both scans run once at cog load inside `cog_load` or a startup task, not on a recurring timer.

---

## Notes & Conventions

- **Prestige points floor:** `prestige_points` cannot go below 0. There is no per-rank floor — a player at any rank can drop all the way to Rank 1 (Member) if they lose enough. This is intentional; it mirrors the high-risk Vegas identity of the cog.
- **Rank re-evaluation after every game:** After `record_win()` or `record_loss()` mutates `prestige_points`, always call `evaluate_rank(conf, user)`. If the returned rank differs from `user.rank`, call `apply_rank_change()` and send the player a promotion or demotion notification embed before showing the game result.
- **Specialty titles are permanent; rank titles are not:** `earned_titles` and `active_title` survive any prestige fluctuation. The dynamic rank (Member/Regular/High Roller/Whale) is always displayed separately from the chosen specialty title.
- All embed colors use `PALETTE_GOLD` (`0xD4AF37`) for standard frames, `0xFF0000` for errors.
- All admin command responses are ephemeral where possible to reduce channel noise.
- All player-facing game views have a `timeout=120` (2 minutes) — on timeout, bet is refunded and a "session expired" message replaces the embed.
- The `save()` call always happens at the end of any operation that mutates `GuildSettings` or `User`. Never assume it will be called by something else.
- `payment_mode == "bank"` means all balance operations go through RedBot's bank API (`bank.get_balance`, `bank.deposit_credits`, `bank.withdraw_credits`). Abstract this fully inside the balance helper functions so game code never calls bank directly.
- `zoneinfo` is stdlib in Python 3.9+. Use `zoneinfo.ZoneInfo(tz_string)` for timezone operations. Validate on input; store as string in config.
- All admin commands use `@commands.admin_or_permissions(manage_guild=True)`. For View button callbacks (where decorators don't apply), call `await check_is_admin(interaction)` at the top of the callback and respond with an ephemeral error if it returns False. Never skip this check in callbacks.
- If a shared `is_admin` utility is imported from another cog in this workspace, it must be called inside `check_is_admin()` in `helper_functions.py` — not scattered across individual command files.
- Card-math games (Blackjack, Hi-Lo, War, Video Poker, Club Poker) must never appear in `CONFIGURABLE_RNG` or `game_rng_settings`. If `get_game_rng()` is called with one of these slugs it should raise a clear `ValueError`; if called with a valid pure-RNG game but an unknown param key, it should raise `KeyError`. Both error types surface at development time rather than silently returning wrong values.
