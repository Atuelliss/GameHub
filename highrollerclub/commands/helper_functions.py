from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Union

import discord
from redbot.core import bank
from redbot.core import commands
from redbot.core.errors import BalanceTooHigh

from ..common.constants import (
    BIG6_HOUSE_SEGMENT_OPTIONS,
    BONUS_BET_TOKEN_ELIGIBLE_GAMES,
    CARD_MATH_GAMES,
    CONFIGURABLE_RNG,
    DEFAULT_BET_LIMITS,
    HOLDEM_BUYIN_FLOOR_BB,
    HOLDEM_DEFAULT_STAKE_TIERS,
    HOLDEM_TIER_COUNT,
    LUCKY_STREAK_BONUS_PCT,
    MULTIPLIER_ELIGIBLE_GAMES,
    PRESTIGE_SCALE,
)
from ..common.models import GuildSettings, HoldemStakeTier, User

log = logging.getLogger("red.highrollerclub.helpers")

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


BET_FAILED_MESSAGE = (
    "Your balance changed before the bet went in, so this play was cancelled. Nothing was taken."
)


async def deduct_balance(
    member: discord.Member, conf: GuildSettings, user: User, amount: int
) -> bool:
    """Deducts amount from chip_balance or bank depending on payment_mode.

    Returns False, taking nothing, if the balance can no longer cover it. The bet
    is checked earlier, but in bank mode the balance can change in between.
    Callers must cancel the play on False (and send BET_FAILED_MESSAGE).
    """
    amount = int(amount)
    if conf.payment_mode == "chips":
        if user.chip_balance < amount:
            return False
        user.chip_balance -= amount
        return True
    try:
        await bank.withdraw_credits(member, amount)
    except ValueError:
        return False
    return True


async def credit_balance(
    member: discord.Member,
    conf: GuildSettings,
    user: User,
    amount: int,
    interaction: discord.Interaction | None = None,
) -> int:
    """Credits amount to chip_balance or bank depending on payment_mode. Never raises.

    In bank mode a win can go over the bank's maximum balance. The bank is then
    filled to the maximum, the player is told privately (when an interaction is
    given) and the shortfall is logged. Returns the amount that could not be paid.
    """
    amount = int(amount)
    if amount <= 0:  # the bank rejects non-positive deposits
        return 0
    if conf.payment_mode == "chips":
        user.chip_balance += amount
        return 0
    try:
        await bank.deposit_credits(member, amount)
        return 0
    except BalanceTooHigh as exc:
        room = max(0, exc.max_balance - await bank.get_balance(member))
        # Setting (not adding) can't overshoot even if the balance moved since the read.
        await bank.set_balance(member, exc.max_balance)
        lost = amount - room
        log.warning(
            "Bank max reached for %s in guild %s: paid %s of %s", member.id, member.guild.id, room, amount
        )
        if interaction is not None:
            currency = await bank.get_currency_name(member.guild)
            await send_private(
                interaction,
                f"🏦 Your bank is full (max **{exc.max_balance:,} {currency}**), so **{lost:,}** "
                f"of this payout couldn't be added.",
            )
        return lost


async def send_private(interaction: discord.Interaction, text: str) -> None:
    """Send an ephemeral note whether or not the interaction has been answered yet."""
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except discord.HTTPException:
        pass


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
# Texas Hold'em blind levels and buy-ins
# ---------------------------------------------------------------------------

def get_holdem_tiers(conf: GuildSettings) -> list[HoldemStakeTier]:
    """The server's blind levels: the admin's edits, or the defaults when there are none.

    Always returns HOLDEM_TIER_COUNT levels. The returned objects are the stored ones
    when the server has edits, so admin code can change them in place and save.
    """
    if len(conf.holdem_stake_tiers) != HOLDEM_TIER_COUNT:
        return [HoldemStakeTier(**tier) for tier in HOLDEM_DEFAULT_STAKE_TIERS]
    return conf.holdem_stake_tiers


def holdem_tier_unlocked(conf: GuildSettings, tier: HoldemStakeTier, rank: int) -> bool:
    """Can a player of this rank open a table at this level?

    When rank bet multipliers are switched off, rank doesn't unlock bigger stakes:
    only levels open to Members (min_rank 1) can be opened.
    """
    if not tier.enabled:
        return False
    effective_rank = rank if conf.bet_multipliers_enabled else 1
    return tier.min_rank <= effective_rank


def holdem_buyin_range(conf: GuildSettings, big_blind: int) -> tuple[int, int]:
    """(min, max) buy-in in chips for a table with this big blind."""
    low_bb = max(HOLDEM_BUYIN_FLOOR_BB, conf.holdem_min_buyin_bb)
    high_bb = max(low_bb, conf.holdem_max_buyin_bb)
    return low_bb * big_blind, high_bb * big_blind


# ---------------------------------------------------------------------------
# Prestige / stat recording
# ---------------------------------------------------------------------------

def add_wagered(user: User, game_slug: str, amount: int) -> None:
    """Add a stake to the player's lifetime and per-game total wagered."""
    amount = max(0, amount)
    user.total_wagered += amount
    user.game_total_wagered[game_slug] = user.game_total_wagered.get(game_slug, 0) + amount


def record_win(
    conf: GuildSettings, user: User, game_slug: str, payout: int, bet: int, *, award_prestige: bool = True
) -> None:
    """Records a game win: increments lifetime and per-game stats, updates
    personal records, increments win streak, and adds prestige points.

    `payout` is the gross amount credited and `bet` the total staked on it. The
    winnings stats record the profit (payout - bet): the returned stake isn't
    winnings, and losses are already recorded as the amount staked.

    award_prestige=False records every stat but leaves prestige alone (Texas
    Hold'em hands with fewer than 3 players, so friends can't trade wins).

    Does NOT call evaluate_rank — caller is responsible for that after this
    function returns.
    """
    winnings = max(0, payout - bet)
    user.total_wins += 1
    user.total_payout_earned += winnings
    user.current_win_streak += 1

    user.game_play_counts[game_slug] = user.game_play_counts.get(game_slug, 0) + 1
    user.game_win_counts[game_slug] = user.game_win_counts.get(game_slug, 0) + 1
    user.game_total_payout[game_slug] = user.game_total_payout.get(game_slug, 0) + winnings
    add_wagered(user, game_slug, bet)

    if winnings > user.largest_single_payout:
        user.largest_single_payout = winnings
    if winnings > user.game_highest_single_payout.get(game_slug, 0):
        user.game_highest_single_payout[game_slug] = winnings
    if bet > user.game_highest_bet.get(game_slug, 0):
        user.game_highest_bet[game_slug] = bet

    if award_prestige:
        user.prestige_points += conf.prestige_win_points * PRESTIGE_SCALE.get(game_slug, 1.0)


def record_loss(
    conf: GuildSettings,
    user: User,
    game_slug: str,
    amount_lost: int,
    *,
    award_prestige: bool = True,
    wagered: int | None = None,
) -> None:
    """Records a game loss: increments lifetime and per-game stats, updates
    personal records, resets win streak, subtracts prestige points
    (floored at 0.0) and uses up a pending Multiplier Wheel boost on eligible games.

    award_prestige=False records every stat but leaves prestige alone (see record_win).

    wagered is what the player staked, when that isn't amount_lost: a Hold'em
    player who got part of their chips back, or a free spin that cost nothing.

    Does NOT call evaluate_rank — caller is responsible for that after this
    function returns.
    """
    user.total_losses += 1
    user.current_win_streak = 0

    user.game_play_counts[game_slug] = user.game_play_counts.get(game_slug, 0) + 1
    user.game_loss_counts[game_slug] = user.game_loss_counts.get(game_slug, 0) + 1
    staked = amount_lost if wagered is None else wagered
    add_wagered(user, game_slug, staked)
    # What actually left the player's balance: never more than they staked
    # (a free spin that loses costs nothing).
    lost = max(0, min(amount_lost, staked))
    user.total_lost += lost
    user.game_total_lost[game_slug] = user.game_total_lost.get(game_slug, 0) + lost

    if amount_lost > user.largest_single_loss:
        user.largest_single_loss = amount_lost
    if amount_lost > user.game_highest_single_loss.get(game_slug, 0):
        user.game_highest_single_loss[game_slug] = amount_lost
    if amount_lost > user.game_highest_bet.get(game_slug, 0):
        user.game_highest_bet[game_slug] = amount_lost

    if award_prestige:
        user.prestige_points = max(0.0, user.prestige_points - conf.prestige_loss_points * PRESTIGE_SCALE.get(game_slug, 1.0))

    # A Multiplier Wheel boost is used up by the next eligible play, win or lose.
    if game_slug in MULTIPLIER_ELIGIBLE_GAMES:
        consume_multiplier(user)


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


MULTIPLIER_BONUS_CAP_SPINS = 2  # a wheel bonus can't exceed this many spin costs


def multiplier_wheel_bonus(conf: GuildSettings, profit: int, multiplier: float) -> int:
    """Extra chips a Multiplier Wheel result adds to a win's profit.

    profit * (multiplier - 1.0), capped at MULTIPLIER_BONUS_CAP_SPINS spin costs so
    a cheap spin can't be turned into a large guaranteed gain on a big bet.
    """
    bonus = int(max(0, profit) * (multiplier - 1.0))
    return min(bonus, conf.multiplier_wheel_cost * MULTIPLIER_BONUS_CAP_SPINS)


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


def apply_lucky_streak_bonus(raw_payout: int, stake: int) -> int:
    """Returns the Lucky Streak bonus to add on top of a win.

    Bonus = LUCKY_STREAK_BONUS_PCT of the winnings (raw_payout - stake), so the
    player's own returned stake never earns a bonus. raw_payout is the gross
    payout from game logic BEFORE any other bonus; stake is everything the
    player put in for that result (e.g. original + war bet in War).

    This function is pure math. Caller must call has_lucky_streak() first
    and only call this when it returns True.

    Stacking order (all bonuses are based on the base winnings):
      1. raw_payout from game logic.
      2. + apply_lucky_streak_bonus(raw_payout, stake)
      3. + Multiplier Wheel: (total - stake) * (multiplier - 1.0)
      4. + bonus_token_bonus(raw_payout, stake)
    """
    return int(max(0, raw_payout - stake) * LUCKY_STREAK_BONUS_PCT)


def bonus_token_bonus(raw_payout: int, stake: int) -> int:
    """Returns the Bonus Bet Token bonus: the base winnings paid a second time.

    The token doubles the winnings (raw_payout - stake), not the returned stake.
    Example: bet 100, gross 200 -> winnings 100 -> token adds 100 (total 300).
    """
    return max(0, raw_payout - stake)


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

_THE_CLOSER_MIN_PAYOUT: int = 250    # single Blackjack win (profit) must reach this value

_NUMBERS_MAN_GAMES: frozenset[str] = frozenset({"keno", "roulette"})
_NUMBERS_MAN_MIN_WINS: int = 30      # combined wins across Keno + Roulette

_CENTURION_MIN_WINS: int = 100       # total lifetime wins
_HIGH_EARNER_MIN_PAYOUT: int = 10_000  # total lifetime winnings (profit)
_IRON_STREAK_LENGTH: int = 5         # consecutive wins required

_RAILBIRD_MIN_RACES: int = 25          # race bets placed
_LONGSHOT_MIN_MULTIPLE: float = 10.0   # a Win bet returning this many times the stake
_BIG_PAYDAY_MIN_PROFIT: int = 5_000    # profit from a single race
_STEADY_EDDIE_MIN_PLACES: int = 10     # Place bets cashed
_HOT_STREAK_LENGTH: int = 3            # races in a row with a cashed Win bet
_RACE_PROMOTER_MIN_RACES: int = 15     # started races that had 3+ bettors

# Texas Hold'em (counters on User; the table counts only hands with 3+ players, except royal flushes)
_GRINDER_MIN_HANDS: int = 250
_BLUFF_MASTER_MIN_FOLD_WINS: int = 25
_RIVER_RAT_MIN_COMEBACKS: int = 5
_SHOVE_SURVIVOR_MIN_WINS: int = 10
_MONSTER_POT_MIN_BB: int = 100
_TABLE_CAPTAIN_MIN_TABLES: int = 10


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

    # --- Horse Racing titles ---
    _check("railbird", user.race_bets_placed >= _RAILBIRD_MIN_RACES)
    _check("longshot", user.race_best_multiple >= _LONGSHOT_MIN_MULTIPLE)
    _check("big_payday", user.race_best_profit >= _BIG_PAYDAY_MIN_PROFIT)
    _check("steady_eddie", user.race_place_bets_cashed >= _STEADY_EDDIE_MIN_PLACES)
    _check("hot_streak", user.race_win_streak >= _HOT_STREAK_LENGTH)
    _check("race_promoter", user.races_promoted >= _RACE_PROMOTER_MIN_RACES)
    _check("called_it", user.race_called_it >= 1)

    # --- Texas Hold'em titles ---
    _check("grinder", user.holdem_hands_dealt >= _GRINDER_MIN_HANDS)
    _check("bluff_master", user.holdem_fold_wins >= _BLUFF_MASTER_MIN_FOLD_WINS)
    _check("river_rat", user.holdem_river_comebacks >= _RIVER_RAT_MIN_COMEBACKS)
    _check("shove_survivor", user.holdem_allin_wins >= _SHOVE_SURVIVOR_MIN_WINS)
    _check("monster_pot", user.holdem_best_pot_bb >= _MONSTER_POT_MIN_BB)
    _check("royal_treatment", user.holdem_royal_flushes >= 1)
    _check("bad_beat", user.holdem_bad_beats >= 1)
    _check("table_captain", user.holdem_tables_hosted >= _TABLE_CAPTAIN_MIN_TABLES)

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
    spec = CONFIGURABLE_RNG[game_slug][key]
    value = conf.game_rng_settings.get(game_slug, {}).get(key, spec["default"])
    # Clamp numbers to the current bounds, so a value saved under older, wider
    # bounds can't push a game's return over 100%.
    if spec["type"] in (int, float) and isinstance(value, (int, float)):
        value = spec["type"](min(max(value, spec["min"]), spec["max"]))
    return value


def get_big6_house_segments(conf: GuildSettings) -> int:
    """House segments on the Big Six wheel, clamped to the allowed range."""
    lo, hi = min(BIG6_HOUSE_SEGMENT_OPTIONS), max(BIG6_HOUSE_SEGMENT_OPTIONS)
    return min(max(conf.big6_house_segments, lo), hi)


# ---------------------------------------------------------------------------
# Channel and blacklist checks
# ---------------------------------------------------------------------------

def is_allowed_channel(conf: GuildSettings, channel_id: int) -> bool:
    """Returns True if allowed_channels is empty (all channels allowed) or
    channel_id is in the list.
    """
    return not conf.allowed_channels or channel_id in conf.allowed_channels


async def can_bypass_channel_lock(bot: Any, member: Any) -> bool:
    """Staff can use the club in any channel.

    The same people as admin_or_permissions(manage_guild=True): the server owner, anyone
    with Manage Server, Red's admin role, or the bot owner.
    """
    if not isinstance(member, discord.Member):
        return False
    if member.guild.owner_id == member.id or member.guild_permissions.manage_guild:
        return True
    return await bot.is_owner(member) or await bot.is_admin(member)


async def channel_allowed(bot: Any, conf: GuildSettings, member: Any, channel_id: int) -> bool:
    """True if the club can be used in this channel by this member (staff bypass the channel lock)."""
    if is_allowed_channel(conf, channel_id):
        return True
    return await can_bypass_channel_lock(bot, member)


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
