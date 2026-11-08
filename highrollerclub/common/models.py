from __future__ import annotations

from datetime import datetime
from typing import Any, List

import discord
from pydantic import Field, field_validator

from . import Base


class Horse(Base):
    """A racehorse. Default horses (ids d01-d15) and custom ones (c01-c10). See games/horse_racing.py."""
    name: str
    custom: bool = False
    speed: float = 0.0
    stamina: float = 0.0
    turning: float = 0.0
    start: float = 0.0
    races: int = 0
    wins: int = 0
    places: int = 0                                    # 2nd-place finishes
    last5: List[int] = Field(default_factory=list)     # most recent finishing positions, newest last
    streak: int = 0                                    # consecutive races run (rotation rule)
    win_streak: int = 0                                # consecutive races won (Triple Crown)


class RaceBet(Base):
    """One player's bet on the active race. amount is exactly what was taken (refunds use it as-is)."""
    user_id: int
    bet_type: str     # "win" | "place"
    horse_id: str
    amount: int
    paid: bool = False  # set right after the payout or refund is credited


class HorseRace(Base):
    """The server's active race, saved so bets survive (and are refunded after) a restart."""
    horse_ids: List[str]
    starter_id: int
    channel_id: int
    message_id: int | None = None
    starts_at: datetime                     # UTC; betting closes and the race runs at this time
    payment_mode: str = "chips"             # mode the bets were taken in; refunds and payouts use it
    phase: str = "betting"                  # "betting" | "running" | "paying"
    bets: List[RaceBet] = Field(default_factory=list)


class User(Base):
    # Currency              
    chip_balance: int = 0  # only meaningful when GuildSettings.payment_mode == "chips"
    starting_chips_granted: bool = False  # the one-time welcome chips have been given
    # Rank progression      
    rank: int = 1                 # 1 = Member | 2 = Regular | 3 = High Roller | 4 = The Whale | Re-evaluated via evaluate_rank() after every game — never mutate directly.
    prestige_points: float = 0.0  # Primary rank driver. +prestige_win_points per win, -prestige_loss_points per loss. Floored at 0.0 — never goes negative.
    total_wins: int = 0           # lifetime stat; used for leaderboards and title evaluation
    total_payout_earned: int = 0  # lifetime winnings (profit, stake not included); used for leaderboards and title evaluation
    # Specialty titles      
    earned_titles: List[str] = Field(default_factory=list)
    active_title: str | None = None # valid title slugs: Playstyle  — "card_shark" | "lucky_star" | "daredevil" | "the_closer" | "numbers_man" | Milestone  — "centurion" | "high_earner" | "iron_streak" |  Titles are PERMANENT once earned. active_title is the one displayed; player selects via Stats view.
    # Multiplier Wheel state
    pending_multiplier: float | None = None
    pending_multiplier_expiry: datetime | None = None  # UTC; None = no active multiplier
    # Scratch Card / Mystery Wheel cooldowns                               
    last_scratch_date: str | None = None         # ISO date string in server timezone
    last_mystery_wheel_date: str | None = None   # ISO date string in server timezone
    mystery_wheel_last_reward_type: str | None = None
    mystery_wheel_last_chip_amount: int = 0
    mystery_wheel_last_payout_amount: int = 0
    mystery_wheel_last_currency_name: str | None = None
    # Bonus tokens                                                         
    bonus_bet_tokens: int = 0
    free_spins_available: int = 0  # Earned from Scratch Card / Mystery Wheel. Consumed by a free Slots spin — deduct_balance() is skipped entirely for that play. Free spins apply to Slots only.
    current_win_streak: int = 0    # Incremented on every win; reset to 0 on any loss. Used by evaluate_specialty_titles() to award the iron_streak title (5 consecutive wins).
    # Lucky Streak state                                                  
    lucky_streak_expiry: datetime | None = None  # UTC expiry time. None = no active streak. Awarded by Scratch Card / Mystery Wheel → expiry = now + 60 minutes. Every consecutive win while active pays +25% of the winnings on top. Cancelled immediately on first loss; expires automatically after 1 hour.
    # Lifetime stats                                                       
    total_losses: int = 0
    largest_single_payout: int = 0  # largest single win (profit) ever
    largest_single_loss: int = 0    # largest single bet amount lost in one game
    # Per-game stats — keyed by game slug; populated on first play         
    game_play_counts: dict[str, int] = Field(default_factory=dict)
    game_win_counts: dict[str, int] = Field(default_factory=dict)
    game_loss_counts: dict[str, int] = Field(default_factory=dict)
    game_total_payout: dict[str, int] = Field(default_factory=dict)
    game_highest_single_payout: dict[str, int] = Field(default_factory=dict)
    game_highest_bet: dict[str, int] = Field(default_factory=dict)
    game_highest_single_loss: dict[str, int] = Field(default_factory=dict) # Favorite game = max(game_play_counts, key=game_play_counts.get) — computed at render time, never stored.
    # Horse Racing                                                         
    last_race_start: str | None = None  # ISO UTC time the player's last started race ran (starter cooldown)
    race_bets_placed: int = 0
    race_win_bets_cashed: int = 0
    race_place_bets_cashed: int = 0
    race_win_streak: int = 0            # consecutive races with a cashed Win bet (Hot Streak)
    race_best_profit: int = 0           # best single-race profit (Big Payday)
    race_best_multiple: float = 0.0     # best Win-bet return as a multiple of the stake (Longshot)
    race_called_it: int = 0             # Win bets cashed as the only backer of the winner (Called It)
    # Texas Hold'em title counters (only hands with 3+ players dealt in count, except royal flushes)
    holdem_hands_dealt: int = 0         # Grinder
    holdem_fold_wins: int = 0           # Bluff Master: pots won when everyone else folded
    holdem_river_comebacks: int = 0     # River Rat
    holdem_allin_wins: int = 0          # Shove Survivor: showdowns won while all-in
    holdem_best_pot_bb: int = 0         # Monster Pot: biggest pot won, in big blinds
    holdem_royal_flushes: int = 0       # Royal Treatment (any table size)
    holdem_bad_beats: int = 0           # Bad Beat: lost a showdown with four of a kind or better
    holdem_tables_hosted: int = 0       # Table Captain: hosted tables that dealt 10+ hands with 3+ players
    races_promoted: int = 0             # races started that had 3+ bettors (Race Promoter)


class HoldemStakeTier(Base):
    """One Texas Hold'em blind level. Defaults are HOLDEM_DEFAULT_STAKE_TIERS in constants.py."""
    sb: int
    bb: int
    min_rank: int = 1        # 1=Member .. 4=The Whale: lowest rank that can open a table at this level
    enabled: bool = True


class HoldemEscrow(Base):
    """Chips the cog is holding for a seated Hold'em player (their stack at the start of the hand)."""
    amount: int
    payment_mode: str        # "chips" | "bank": how the buy-in was taken, so the refund matches it
    channel_id: int | None = None  # the table's channel, for the restart notice


class GuildSettings(Base):
    users: dict[int, User] = Field(default_factory=dict)

    # Payment system                                                      
    payment_mode: str = "chips"  # "chips" = players hold a chip_balance stored in User; all bets/payouts use chip_balance. "bank"  = all balance operations go through RedBot's bank API directly.
    discord_currency_conversion_rate: int = 100 # Chips gained per 1 server currency unit spent (chip mode buy rate). Also used as the sell rate when discord_currency_conversion_enabled is True.
    discord_currency_conversion_enabled: bool = False # When True in chip mode, players may cash out chips → server currency at the same rate via the Teller Window Convert Chips flow.
    # Rank thresholds (prestige points required to hold each rank)        
    rank2_threshold: int = 20    # Regular
    rank3_threshold: int = 50   # High Roller
    rank4_threshold: int = 75  # The Whale
    # Rank is recalculated from live prestige_points after every game. Crossing a threshold down demotes exactly as crossing it up promotes. There is no floor between ranks — a Whale can drop straight to Member.
    # Prestige point values (admin-configurable)                           
    prestige_win_points: float = 1.0    # added per win (min 0.1)
    prestige_loss_points: float = 0.75  # removed per loss, floored at 0 (min 0.0)
    # Rank bet multipliers                                                 
    rank1_multiplier: float = 1.0  # Member
    rank2_multiplier: float = 1.5  # Regular
    rank3_multiplier: float = 2.0  # High Roller
    rank4_multiplier: float = 3.0  # The Whale
    bet_multipliers_enabled: bool = True # When False, all ranks bet at 1x base limits regardless of rank. Rank tracking, prestige, and cosmetic titles continue to function normally.
    # Base bet limits per game                                             
    game_bet_limits: dict[str, dict[str, int]] = Field(default_factory=dict) # Keyed by game slug: {"slots": {"min": 10, "max": 500}, ...} | Applied before rank multiplier. Missing keys fall back to DEFAULT_BET_LIMITS in constants.py.
    # Channel restrictions                                                 
    allowed_channels: List[int] = Field(default_factory=list) # Empty list = all channels allowed. Non-empty = only listed channel IDs permitted.
    message_cleanup_enabled: bool = False
    # Blacklist                                                            
    blacklisted_users: List[int] = Field(default_factory=list)
    # All-In risk tier cap                                                 
    allin_max_tier: int = 5    # 1–5. Tiers above this value are hidden from players on the Game Floor.
    # Scratch Card settings                                                
    scratch_enabled: bool = False
    scratch_cooldown_hours: int = 24
    scratch_reward_pool: List[str] = Field(default_factory=lambda: ["chips"])  # Valid pool entries: "chips" | "bonus_bet_token" | "rank_xp" | "free_spin" | "lucky_streak"
    # Mystery Wheel (daily free spin)                                      
    mystery_wheel_enabled: bool = False
    mystery_wheel_timezone: str = "America/New_York"
    mystery_wheel_reward_pool: List[str] = Field(default_factory=lambda: ["chips"])
    # Multiplier Wheel                                                     
    multiplier_wheel_cost: int = 250         # flat chip/currency cost to spin
    multiplier_wheel_expiry_minutes: int = 30
    # Big Six Wheel                                                        
    big6_house_segments: int = 2  # One of BIG6_HOUSE_SEGMENT_OPTIONS (0/2/4/6). Only the house count changes; all other segment counts stay fixed. Read it with get_big6_house_segments(), which clamps old out-of-range values.
    # Per-game enable flags                                                
    games_enabled: dict[str, bool] = Field(default_factory=lambda: {
        "slots":           False,
        "war":             False,
        "allin":           False,
        "blackjack":       False,
        "hilo":            False,
        "keno":            False,
        "roulette":        False,
        "videopoker":      False,
        "clubpoker":       False,
        "holdem":          False,
        "big6":            False,
        "mysteryspin":     False,
        "multiplierwheel": False,
        "double":          False,
        "horserace":       False,
    })    # False = game button renders as grey + 🔒 on Game Floor; view access is blocked. Existing player stats for disabled games are preserved.
    # Per-game RNG overrides                                               
    game_rng_settings: dict[str, dict[str, Any]] = Field(default_factory=dict) # Stores admin-configured RNG parameters per game. Keys per game are defined in constants.CONFIGURABLE_RNG. Missing keys fall back to the CONFIGURABLE_RNG default automatically. Card-math games (blackjack, hilo, war, videopoker, clubpoker) are never in this dict.
    # Horse Racing                                                         
    race_channel_id: int | None = None          # Horse Racing is unavailable until this is set
    horserace_house_cut_pct: int = 10           # cut taken from each pool's new stakes (0-25)
    horserace_countdown_minutes: int = 5        # betting window before the race runs (2-10)
    horserace_cooldown_minutes: int = 30        # wait before the same player can start another race
    horserace_house_line_return_pct: int = 80   # average return of solo (house-line) races (50-95)
    horses: dict[str, Horse] = Field(default_factory=dict)  # created on first use; see ensure_horses()
    race_carryover: dict[str, int] = Field(default_factory=lambda: {"win": 0, "place": 0})
    race_carry_count: dict[str, int] = Field(default_factory=lambda: {"win": 0, "place": 0})
    active_race: HorseRace | None = None
    race_pending_refunds: List[RaceBet] = Field(default_factory=list)  # refunds that failed; retried on load
    race_notify_ids: List[int] = Field(default_factory=list)  # players pinged when a race opens for betting
    # Texas Hold'em                                                       
    holdem_stake_tiers: List[HoldemStakeTier] = Field(default_factory=list)  # empty = the defaults; read via get_holdem_tiers()
    holdem_action_seconds: int = 60       # HOLDEM_ACTION_SECONDS; admin range HOLDEM_ACTION_SECONDS_RANGE
    holdem_min_buyin_bb: int = 20         # HOLDEM_MIN_BUYIN_BB
    holdem_max_buyin_bb: int = 100        # HOLDEM_MAX_BUYIN_BB
    holdem_escrow: dict[int, HoldemEscrow] = Field(default_factory=dict)  # user id -> chips held at a table; refunded on load/unload

    @field_validator("games_enabled", mode="after")
    @classmethod
    def _new_games_start_off(cls, value: dict[str, bool]) -> dict[str, bool]:
        # Saved settings from before a game existed don't list it: it starts switched off.
        value.setdefault("horserace", False)
        value.setdefault("holdem", False)
        return value

    # Helpers                                                              #
    def get_user(self, user: discord.User | int) -> User:
        uid = user if isinstance(user, int) else user.id
        return self.users.setdefault(uid, User())

class DB(Base):
    configs: dict[int, GuildSettings] = Field(default_factory=dict)

    def get_conf(self, guild: discord.Guild | int) -> GuildSettings:
        gid = guild if isinstance(guild, int) else guild.id
        return self.configs.setdefault(gid, GuildSettings())
