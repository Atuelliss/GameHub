from __future__ import annotations

from datetime import datetime
from typing import Any, List

import discord
from pydantic import Field

from . import Base


class User(Base):
    # Currency              
    chip_balance: int = 0  # only meaningful when GuildSettings.payment_mode == "chips"
    # Rank progression      
    rank: int = 1                 # 1 = Member | 2 = Regular | 3 = High Roller | 4 = The Whale | Re-evaluated via evaluate_rank() after every game — never mutate directly.
    prestige_points: float = 0.0  # Primary rank driver. +prestige_win_points per win, -prestige_loss_points per loss. Floored at 0.0 — never goes negative.
    total_wins: int = 0           # lifetime stat; used for leaderboards and title evaluation
    total_payout_earned: int = 0  # lifetime stat; used for leaderboards and title evaluation
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
    lucky_streak_expiry: datetime | None = None  # UTC expiry time. None = no active streak. Awarded by Scratch Card / Mystery Wheel → expiry = now + 60 minutes. Every consecutive win while active pays +25% of raw game payout on top. Cancelled immediately on first loss; expires automatically after 1 hour.
    # Lifetime stats                                                       
    total_losses: int = 0
    largest_single_payout: int = 0  # largest single payout ever received
    largest_single_loss: int = 0    # largest single bet amount lost in one game
    # Per-game stats — keyed by game slug; populated on first play         
    game_play_counts: dict[str, int] = Field(default_factory=dict)
    game_win_counts: dict[str, int] = Field(default_factory=dict)
    game_loss_counts: dict[str, int] = Field(default_factory=dict)
    game_total_payout: dict[str, int] = Field(default_factory=dict)
    game_highest_single_payout: dict[str, int] = Field(default_factory=dict)
    game_highest_bet: dict[str, int] = Field(default_factory=dict)
    game_highest_single_loss: dict[str, int] = Field(default_factory=dict) # Favorite game = max(game_play_counts, key=game_play_counts.get) — computed at render time, never stored.


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
    big6_house_segments: int = 8  # Configurable 6–12. Only the house count changes; all other segment counts stay fixed. Win probability for a chosen segment = segment_count / (house_count + 46).
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
        "big6":            False,
        "mysteryspin":     False,
        "multiplierwheel": False,
        "double":          False,
    })    # False = game button renders as grey + 🔒 on Game Floor; view access is blocked. Existing player stats for disabled games are preserved.
    # Per-game RNG overrides                                               
    game_rng_settings: dict[str, dict[str, Any]] = Field(default_factory=dict) # Stores admin-configured RNG parameters per game. Keys per game are defined in constants.CONFIGURABLE_RNG. Missing keys fall back to the CONFIGURABLE_RNG default automatically. Card-math games (blackjack, hilo, war, videopoker, clubpoker) are never in this dict.
    # Helpers                                                              #
    def get_user(self, user: discord.User | int) -> User:
        uid = user if isinstance(user, int) else user.id
        return self.users.setdefault(uid, User())

class DB(Base):
    configs: dict[int, GuildSettings] = Field(default_factory=dict)

    def get_conf(self, guild: discord.Guild | int) -> GuildSettings:
        gid = guild if isinstance(guild, int) else guild.id
        return self.configs.setdefault(gid, GuildSettings())
