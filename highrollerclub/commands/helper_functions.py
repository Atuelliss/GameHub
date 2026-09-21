from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Union

import discord
from redbot.core import bank
from redbot.core import commands

from ..common.constants import (
    BONUS_BET_TOKEN_ELIGIBLE_GAMES,
    CARD_MATH_GAMES,
    CONFIGURABLE_RNG,
    DEFAULT_BET_LIMITS,
    LUCKY_STREAK_BONUS_PCT,
    PRESTIGE_SCALE,
)
from ..common.models import GuildSettings, User

# ---------------------------------------------------------------------------
# Admin permission check
# ---------------------------------------------------------------------------

async def check_is_admin(ctx_or_interaction: Union[discord.Interaction, commands.Context]) -> bool:
    """Returns True if the invoker is a bot owner, Red admin, or has manage_guild.

    Accepts either a commands.Context (prefix command callbacks) or a
    discord.Interaction (View button callbacks).  Logic mirrors the is_admin
    function from endeavor2/commands/admin_commands.py, extended to support
    Interaction objects.
    """
    if isinstance(ctx_or_interaction, discord.Interaction):
        user = ctx_or_interaction.user
        bot = ctx_or_interaction.client
        if await bot.is_owner(user):
            return True
        if not ctx_or_interaction.guild:
            return False
        if user.guild_permissions.manage_guild:
            return True
        return await bot.is_admin(user)
    else:
        ctx = ctx_or_interaction
        if await ctx.bot.is_owner(ctx.author):
            return True
        if not ctx.guild:
            return False
        if ctx.author.guild_permissions.manage_guild:
            return True
        return await ctx.bot.is_admin(ctx.author)


# ---------------------------------------------------------------------------
# Bet limits and validation
# ---------------------------------------------------------------------------

def get_bet_limits(conf: GuildSettings, game_slug: str, rank: int) -> tuple[int, int]:
    """Returns (min_bet, max_bet) for a given game and player rank after multiplier.

    Min bet is never scaled — only the max bet is multiplied by the rank
    multiplier.  Falls back to DEFAULT_BET_LIMITS if no admin override exists
    for the slug.
    """
    base = conf.game_bet_limits.get(game_slug) or DEFAULT_BET_LIMITS.get(
        game_slug, {"min": 10, "max": 500}
    )
    min_bet = base["min"]
    max_bet = int(base["max"] * get_rank_multiplier(conf, rank))
    return min_bet, max_bet


def validate_bet(
    conf: GuildSettings,
    user: User,
    game_slug: str,
    amount: int,
    current_balance: int,
) -> str | None:
    """Returns an error string if the bet is invalid, or None if it passes.

    Checks (in order): min bet, max bet after rank multiplier, sufficient
    balance.  Caller must pre-fetch current_balance via get_balance() since
    this function is synchronous and cannot call async bank APIs.
    """
    min_bet, max_bet = get_bet_limits(conf, game_slug, user.rank)
    if amount < min_bet:
        return f"Minimum bet for this game is **{min_bet:,}**."
    if amount > max_bet:
        return f"Maximum bet for your rank is **{max_bet:,}**."
    if amount > current_balance:
        return "You don't have enough to cover that bet."
    return None


# ---------------------------------------------------------------------------
# Balance helpers
# ---------------------------------------------------------------------------

async def get_balance(member: discord.Member, conf: GuildSettings, user: User) -> int:
    """Returns the player's spendable balance.

    Chip mode: returns user.chip_balance (no async call needed).
    Bank mode: returns the live RedBot bank balance.
    Caller extracts member from ctx.author or interaction.user.
    """
    if conf.payment_mode == "chips":
        return user.chip_balance
    return await bank.get_balance(member)


async def deduct_balance(
    member: discord.Member, conf: GuildSettings, user: User, amount: int
) -> None:
    """Deducts amount from chip_balance or bank depending on payment_mode."""
    amount = int(amount)
    if conf.payment_mode == "chips":
        user.chip_balance -= amount
    else:
        await bank.withdraw_credits(member, amount)


async def credit_balance(
    member: discord.Member, conf: GuildSettings, user: User, amount: int
) -> None:
    """Credits amount to chip_balance or bank depending on payment_mode."""
    amount = int(amount)
    if conf.payment_mode == "chips":
        user.chip_balance += amount
    else:
        await bank.deposit_credits(member, amount)


# ---------------------------------------------------------------------------
# Rank helpers
# ---------------------------------------------------------------------------

def get_rank_multiplier(conf: GuildSettings, rank: int) -> float:
    """Returns the effective bet multiplier for the given rank.

    Returns 1.0 for all ranks when conf.bet_multipliers_enabled is False —
    ranks remain cosmetic but do not affect bet limits.
    """
    if not conf.bet_multipliers_enabled:
        return 1.0
    multipliers = {
        1: conf.rank1_multiplier,
        2: conf.rank2_multiplier,
        3: conf.rank3_multiplier,
        4: conf.rank4_multiplier,
    }
    return multipliers.get(rank, 1.0)


def evaluate_rank(conf: GuildSettings, user: User) -> int:
    """Returns the correct rank (1–4) for the player's current prestige_points.

    Compares against thresholds in descending order — handles both promotions
    and demotions without directional logic.  Caller compares the return value
    to user.rank and calls apply_rank_change() if they differ.
    """
    pts = user.prestige_points
    if pts >= conf.rank4_threshold:
        return 4
    if pts >= conf.rank3_threshold:
        return 3
    if pts >= conf.rank2_threshold:
        return 2
    return 1


def apply_rank_change(user: User, new_rank: int) -> None:
    """Mutates user.rank in place.  Works identically for promotions and demotions."""
    user.rank = new_rank


# ---------------------------------------------------------------------------
# Prestige / stat recording
# ---------------------------------------------------------------------------

def record_win(
    conf: GuildSettings, user: User, game_slug: str, payout: int, bet: int
) -> None:
    """Records a game win: increments lifetime and per-game stats, updates
    personal records, increments win streak, and adds prestige points.

    Does NOT call evaluate_rank — caller is responsible for that after this
    function returns.
    """
    user.total_wins += 1
    user.total_payout_earned += payout
    user.current_win_streak += 1

    user.game_play_counts[game_slug] = user.game_play_counts.get(game_slug, 0) + 1
    user.game_win_counts[game_slug] = user.game_win_counts.get(game_slug, 0) + 1
    user.game_total_payout[game_slug] = user.game_total_payout.get(game_slug, 0) + payout

    if payout > user.largest_single_payout:
        user.largest_single_payout = payout
    if payout > user.game_highest_single_payout.get(game_slug, 0):
        user.game_highest_single_payout[game_slug] = payout
    if bet > user.game_highest_bet.get(game_slug, 0):
        user.game_highest_bet[game_slug] = bet

    user.prestige_points += conf.prestige_win_points * PRESTIGE_SCALE.get(game_slug, 1.0)


def record_loss(
    conf: GuildSettings, user: User, game_slug: str, amount_lost: int
) -> None:
    """Records a game loss: increments lifetime and per-game stats, updates
    personal records, resets win streak, and subtracts prestige points
    (floored at 0.0).

    Does NOT call evaluate_rank — caller is responsible for that after this
    function returns.
    """
    user.total_losses += 1
    user.current_win_streak = 0

    user.game_play_counts[game_slug] = user.game_play_counts.get(game_slug, 0) + 1
    user.game_loss_counts[game_slug] = user.game_loss_counts.get(game_slug, 0) + 1

    if amount_lost > user.largest_single_loss:
        user.largest_single_loss = amount_lost
    if amount_lost > user.game_highest_single_loss.get(game_slug, 0):
        user.game_highest_single_loss[game_slug] = amount_lost
    if amount_lost > user.game_highest_bet.get(game_slug, 0):
        user.game_highest_bet[game_slug] = amount_lost

    user.prestige_points = max(0.0, user.prestige_points - conf.prestige_loss_points * PRESTIGE_SCALE.get(game_slug, 1.0))


# ---------------------------------------------------------------------------
# Multiplier Wheel state
# ---------------------------------------------------------------------------

def get_pending_multiplier(user: User) -> float | None:
    """Returns the active multiplier value if one exists and has not expired.

    Clears both pending_multiplier and pending_multiplier_expiry as a side
    effect if the multiplier has expired.  Returns None if none is active.
    """
    if user.pending_multiplier is None or user.pending_multiplier_expiry is None:
        return None
    if datetime.now(timezone.utc) >= user.pending_multiplier_expiry:
        user.pending_multiplier = None
        user.pending_multiplier_expiry = None
        return None
    return user.pending_multiplier


def consume_multiplier(user: User) -> float | None:
    """Reads, clears, and returns the active multiplier.

    Returns None if no multiplier is active or it has already expired.
    Use at the point of game resolution for eligible games.
    """
    value = get_pending_multiplier(user)
    if value is not None:
        user.pending_multiplier = None
        user.pending_multiplier_expiry = None
    return value


# ---------------------------------------------------------------------------
# Lucky Streak state
# ---------------------------------------------------------------------------

def has_lucky_streak(user: User) -> bool:
    """Returns True if the player has an active, unexpired Lucky Streak.

    Clears lucky_streak_expiry in place if it has expired (side effect).
    Call at the start of every game resolution and on embed renders to keep
    stale state cleaned up automatically.
    """
    if user.lucky_streak_expiry is None:
        return False
    if datetime.now(timezone.utc) >= user.lucky_streak_expiry:
        user.lucky_streak_expiry = None
        return False
    return True


def apply_lucky_streak_bonus(raw_payout: int) -> int:
    """Returns the bonus amount to add on top of a raw game payout.

    Bonus = int(raw_payout * LUCKY_STREAK_BONUS_PCT).  raw_payout is the
    gross payout produced by game logic BEFORE Multiplier Wheel stacking —
    it does NOT include the returned original bet.

    This function is pure math.  Caller must call has_lucky_streak() first
    and only call this when it returns True.

    Stacking order:
      1. Compute raw_payout from game logic.
      2. Add lucky_streak_bonus = apply_lucky_streak_bonus(raw_payout).
      3. total_payout = raw_payout + lucky_streak_bonus.
      4. If multiplier wheel is active: profit = total_payout - bet;
         wheel_bonus = profit * (multiplier - 1.0); total_payout += wheel_bonus.
    """
    return int(raw_payout * LUCKY_STREAK_BONUS_PCT)


def cancel_lucky_streak(user: User) -> None:
    """Clears lucky_streak_expiry.  Called on the player's first loss while a
    streak is active.  Caller is responsible for notifying the player.
    """
    user.lucky_streak_expiry = None


# ---------------------------------------------------------------------------
# Specialty title evaluation
# ---------------------------------------------------------------------------

# Thresholds — adjust here without touching game code
_CARD_SHARK_GAMES: frozenset[str] = frozenset({"blackjack", "videopoker", "hilo"})
_CARD_SHARK_MIN_PLAYS: int = 20      # combined plays across BJ + VP + HiLo
_CARD_SHARK_WIN_RATE: float = 0.60   # 60% combined win rate required

_LUCKY_STAR_GAMES: frozenset[str] = frozenset({"slots", "keno"})
_LUCKY_STAR_MIN_WINS: int = 50       # combined wins across Slots + Keno

_DAREDEVIL_MIN_WINS: int = 10        # All-In wins (any tier); proxy for Reckless+ history

_THE_CLOSER_MIN_PAYOUT: int = 500    # single Blackjack payout must reach this value

_NUMBERS_MAN_GAMES: frozenset[str] = frozenset({"keno", "roulette"})
_NUMBERS_MAN_MIN_WINS: int = 30      # combined wins across Keno + Roulette

_CENTURION_MIN_WINS: int = 100       # total lifetime wins
_HIGH_EARNER_MIN_PAYOUT: int = 10_000  # total lifetime payout
_IRON_STREAK_LENGTH: int = 5         # consecutive wins required


def evaluate_specialty_titles(user: User) -> list[str]:
    """Returns a list of newly earned specialty title slugs not already in
    user.earned_titles.  Both playstyle and milestone titles are evaluated.

    Caller must append the returned slugs to user.earned_titles and notify
    the player of each new unlock.
    """
    already_earned: set[str] = set(user.earned_titles)
    newly_earned: list[str] = []

    def _check(slug: str, condition: bool) -> None:
        if slug not in already_earned and condition:
            newly_earned.append(slug)

    # --- Playstyle titles ---
    card_plays = sum(user.game_play_counts.get(g, 0) for g in _CARD_SHARK_GAMES)
    card_wins = sum(user.game_win_counts.get(g, 0) for g in _CARD_SHARK_GAMES)
    card_rate = card_wins / card_plays if card_plays > 0 else 0.0
    _check(
        "card_shark",
        card_plays >= _CARD_SHARK_MIN_PLAYS and card_rate >= _CARD_SHARK_WIN_RATE,
    )

    lucky_wins = sum(user.game_win_counts.get(g, 0) for g in _LUCKY_STAR_GAMES)
    _check("lucky_star", lucky_wins >= _LUCKY_STAR_MIN_WINS)

    _check("daredevil", user.game_win_counts.get("allin", 0) >= _DAREDEVIL_MIN_WINS)

    _check(
        "the_closer",
        user.game_highest_single_payout.get("blackjack", 0) >= _THE_CLOSER_MIN_PAYOUT,
    )

    numbers_wins = sum(user.game_win_counts.get(g, 0) for g in _NUMBERS_MAN_GAMES)
    _check("numbers_man", numbers_wins >= _NUMBERS_MAN_MIN_WINS)

    # --- Milestone titles ---
    _check("centurion", user.total_wins >= _CENTURION_MIN_WINS)
    _check("high_earner", user.total_payout_earned >= _HIGH_EARNER_MIN_PAYOUT)
    # iron_streak: awarded when current_win_streak reaches 5 for the first time;
    # permanently earned from that point even if the streak is later broken.
    _check("iron_streak", user.current_win_streak >= _IRON_STREAK_LENGTH)

    return newly_earned


# ---------------------------------------------------------------------------
# RNG settings helper
# ---------------------------------------------------------------------------

def get_game_rng(conf: GuildSettings, game_slug: str, key: str) -> Any:
    """Returns the configured RNG value for a game parameter.

    Priority: admin override in conf.game_rng_settings → CONFIGURABLE_RNG default.

    Raises ValueError if game_slug is in CARD_MATH_GAMES (never configurable).
    Raises KeyError if game_slug is unknown or key is not valid for that game.
    Game code must always call this — never read game_rng_settings directly.
    """
    if game_slug in CARD_MATH_GAMES:
        raise ValueError(
            f"'{game_slug}' is a card-math game — win chance is not RNG-configurable."
        )
    if game_slug not in CONFIGURABLE_RNG:
        raise KeyError(f"'{game_slug}' has no configurable RNG parameters.")
    if key not in CONFIGURABLE_RNG[game_slug]:
        raise KeyError(f"'{key}' is not a valid RNG parameter for '{game_slug}'.")
    overrides = conf.game_rng_settings.get(game_slug, {})
    return overrides.get(key, CONFIGURABLE_RNG[game_slug][key]["default"])


# ---------------------------------------------------------------------------
# Channel and blacklist checks
# ---------------------------------------------------------------------------

def is_allowed_channel(conf: GuildSettings, channel_id: int) -> bool:
    """Returns True if allowed_channels is empty (all channels allowed) or
    channel_id is in the list.
    """
    return not conf.allowed_channels or channel_id in conf.allowed_channels


def is_blacklisted(conf: GuildSettings, user_id: int) -> bool:
    """Returns True if user_id is in conf.blacklisted_users."""
    return user_id in conf.blacklisted_users


# ---------------------------------------------------------------------------
# Bonus Bet Token helpers
# ---------------------------------------------------------------------------

def has_bonus_bet_token(user: User) -> bool:
    """Returns True if the player holds at least one Bonus Bet Token."""
    return user.bonus_bet_tokens > 0


def consume_bonus_bet_token(
    user: User,
    game_slug: str,
    allin_tier: int | None = None,
) -> bool:
    """Validates eligibility and consumes one Bonus Bet Token.

    Returns True and decrements bonus_bet_tokens if eligible.
    Returns False without mutating state if ineligible.
    Caller must notify the player with an ephemeral message when False is returned.

    Eligibility rules:
    - game_slug must be in BONUS_BET_TOKEN_ELIGIBLE_GAMES, OR be "allin" at
      tier 1 or 2.  All-In is intentionally absent from the set because tiers
      3-5 are ineligible — we handle the partial eligibility here explicitly.
    - For All-In, allin_tier must be 1 or 2 (Standard / Bold only).
    """
    if user.bonus_bet_tokens <= 0:
        return False
    # All-In partial eligibility: tiers 1–2 only.
    if game_slug == "allin":
        if allin_tier is None or allin_tier > 2:
            return False
        user.bonus_bet_tokens -= 1
        return True
    if game_slug not in BONUS_BET_TOKEN_ELIGIBLE_GAMES:
        return False
    user.bonus_bet_tokens -= 1
    return True


# ---------------------------------------------------------------------------
# Free Spin helper
# ---------------------------------------------------------------------------

def consume_free_spin(user: User) -> bool:
    """Decrements free_spins_available by 1 and returns True if a free spin
    was available.  Returns False without mutating state if none remain.

    When True is returned, the Slots game must skip deduct_balance() entirely
    for that play.  Free spins apply to Slots only — caller must enforce this.
    """
    if user.free_spins_available <= 0:
        return False
    user.free_spins_available -= 1
    return True
