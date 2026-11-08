"""Horse Racing -- Pure game logic for HighRollerClub.

No Discord code lives here: the race model, stat changes, field selection,
house-line odds and pool settlement. views/horse_racing_view.py and
tasks/horse_races.py drive it.

Race model
----------
A race has RACE_STAGES stages. In every stage each horse moves

    STAGE_BASE + SKILL_SCALE * (weighted stats for that stage) / STAT_CAP + gauss(0, STAGE_SIGMA)

so its final distance is normally distributed with mean `expected_distance()` and
standard deviation STAGE_SIGMA * sqrt(RACE_STAGES). That lets `finish_chances()`
compute each horse's exact chance of winning and of finishing in the top 2 by
numerical integration, from the same numbers the race uses. The house line is
priced from those chances, so knowing the stats gives no edge.

Stats
-----
Every horse has speed, stamina, turning and start, from 0 to STAT_CAP. All start
at 0. After each race `stat_changes()` moves them by finishing position (the
changes roughly cancel out across a field) plus a pull toward STAT_MIDPOINT, so
the field stays competitive instead of one horse running away with it. Tuned by
simulation (6,000 races, 15 and 25 horses): ratings settle between about 35 and
75, and the horse with the best stats wins about 25% of races (target 20-35%).

Payouts
-------
Pool races (2+ bettors): Win and Place pools, a house cut on new stakes, a
carryover for unclaimed pools (max CARRYOVER_MAX_STACKS races), and a winning
ticket never pays back less than its stake. Place pays on 1st or 2nd; the net
Place pool is split in half between the backers of the two horses.

Solo races: the house line, fixed odds of target_return / chance, capped, and
not offered at all below HOUSE_LINE_MIN_MULTIPLIER.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Iterable, Protocol, Sequence

# ---------------------------------------------------------------------------
# Horses
# ---------------------------------------------------------------------------

STAT_NAMES: tuple[str, ...] = ("speed", "stamina", "turning", "start")
STAT_CAP: float = 100.0

FIELD_SIZE = 10            # horses per race
MAX_CONSECUTIVE_RACES = 3  # a horse sits out after running this many races in a row
MAX_CUSTOM_HORSES = 10

# Default horses: stable ids d01-d15. Names never change.
DEFAULT_HORSES: dict[str, str] = {
    "d01": "Lucky Seven",
    "d02": "Royal Flush",
    "d03": "Midnight Ante",
    "d04": "Double Down",
    "d05": "Snake Eyes",
    "d06": "Jackpot Jenny",
    "d07": "Wild Card",
    "d08": "Silver Dollar",
    "d09": "Dealer's Choice",
    "d10": "Velvet Rope",
    "d11": "Last Call",
    "d12": "Full House",
    "d13": "Neon Dancer",
    "d14": "High Stakes",
    "d15": "Boxcar Bandit",
}
CUSTOM_HORSE_IDS: tuple[str, ...] = tuple(f"c{i:02d}" for i in range(1, MAX_CUSTOM_HORSES + 1))

HORSE_NAME_MIN = 2
HORSE_NAME_MAX = 20
_NAME_FORBIDDEN = set("@<>`")
_NAME_BAD_START = set("*_~|>#-+:")


class HorseStats(Protocol):
    speed: float
    stamina: float
    turning: float
    start: float


def validate_horse_name(name: str, taken: Iterable[str]) -> str | None:
    """Return an error message, or None if the (already stripped) name is allowed."""
    if not HORSE_NAME_MIN <= len(name) <= HORSE_NAME_MAX:
        return f"Horse names must be {HORSE_NAME_MIN}–{HORSE_NAME_MAX} characters."
    if any(ch in _NAME_FORBIDDEN for ch in name):
        return "Horse names can't contain `@`, `<`, `>` or backticks."
    if name[0] in _NAME_BAD_START:
        return "Horse names can't start with a formatting character."
    if name.casefold() in {t.casefold() for t in taken}:
        return f"There's already a horse called **{name}**."
    return None


# ---------------------------------------------------------------------------
# Field selection
# ---------------------------------------------------------------------------

def pick_field(streaks: dict[str, int], rng: random.Random | None = None) -> list[str]:
    """Pick FIELD_SIZE horse ids from `streaks` ({horse_id: consecutive races run}).

    Horses that have run MAX_CONSECUTIVE_RACES in a row sit out. If that leaves too
    few (horses removed mid-cycle), the most rested horses fill the gap.
    Raises ValueError if there are fewer than FIELD_SIZE horses in total.
    """
    rng = rng or random
    if len(streaks) < FIELD_SIZE:
        raise ValueError(f"Racing needs at least {FIELD_SIZE} horses.")
    eligible = [h for h, s in streaks.items() if s < MAX_CONSECUTIVE_RACES]
    if len(eligible) >= FIELD_SIZE:
        return rng.sample(eligible, FIELD_SIZE)
    rested = sorted(streaks, key=lambda h: (streaks[h], rng.random()))
    return rested[:FIELD_SIZE]


def next_streaks(streaks: dict[str, int], ran: Iterable[str]) -> dict[str, int]:
    """Streaks after a race: +1 for the horses that ran, 0 for the rest."""
    ran = set(ran)
    return {h: (s + 1 if h in ran else 0) for h, s in streaks.items()}


# ---------------------------------------------------------------------------
# Race model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Stage:
    name: str
    weights: dict[str, float]  # stat -> weight, summing to 1


RACE_STAGES: tuple[Stage, ...] = (
    Stage("Gate break",   {"start": 0.6, "speed": 0.4}),
    Stage("First turn",   {"turning": 0.7, "speed": 0.3}),
    Stage("Backstretch",  {"speed": 0.8, "stamina": 0.2}),
    Stage("Far turn",     {"turning": 0.6, "stamina": 0.4}),
    Stage("Home stretch", {"speed": 0.5, "stamina": 0.5}),
    Stage("Finish",       {"stamina": 0.6, "speed": 0.4}),
)
STAGE_BASE = 10.0    # distance every horse covers per stage
SKILL_SCALE = 1.6    # extra distance per stage for a horse at the stat cap
STAGE_SIGMA = 1.0    # random spread per stage

_TOTAL_SIGMA = STAGE_SIGMA * math.sqrt(len(RACE_STAGES))


def stage_skill(horse: HorseStats, stage: Stage) -> float:
    return SKILL_SCALE * sum(w * getattr(horse, stat) for stat, w in stage.weights.items()) / STAT_CAP


def expected_distance(horse: HorseStats) -> float:
    return sum(STAGE_BASE + stage_skill(horse, stage) for stage in RACE_STAGES)


@dataclass
class RaceResult:
    # stage_distances[s][i] = horse i's total distance after stage s
    stage_distances: list[list[float]] = field(default_factory=list)
    order: list[int] = field(default_factory=list)  # horse indexes, winner first

    def standings(self, stage_index: int) -> list[int]:
        """Horse indexes in running order after the given stage."""
        dist = self.stage_distances[stage_index]
        return sorted(range(len(dist)), key=lambda i: -dist[i])


def run_race(horses: Sequence[HorseStats], rng: random.Random | None = None) -> RaceResult:
    """Run one race. Exact ties (vanishingly rare) go to the lower index."""
    rng = rng or random
    totals = [0.0] * len(horses)
    result = RaceResult()
    for stage in RACE_STAGES:
        for i, horse in enumerate(horses):
            totals[i] += STAGE_BASE + stage_skill(horse, stage) + rng.gauss(0.0, STAGE_SIGMA)
        result.stage_distances.append(list(totals))
    result.order = result.standings(len(RACE_STAGES) - 1)
    return result


def _phi(z: float) -> float:
    return math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def _cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def finish_chances(horses: Sequence[HorseStats], steps: int = 1600) -> tuple[list[float], list[float]]:
    """Exact (numerically integrated) chance of each horse winning and of finishing top 2.

    Final distances are independent normals N(mean_i, TOTAL_SIGMA), so
      P(i wins)  = ∫ f_i(x) Π_{j≠i} F_j(x) dx
      P(i top 2) = ∫ f_i(x) [Π_{j≠i} F_j(x) + Σ_{k≠i} (1−F_k(x)) Π_{j≠i,k} F_j(x)] dx
    Results are normalised so the win chances sum to 1 and the top-2 chances to 2.
    """
    means = [expected_distance(h) for h in horses]
    n = len(means)
    lo = min(means) - 8 * _TOTAL_SIGMA
    hi = max(means) + 8 * _TOTAL_SIGMA
    dx = (hi - lo) / steps
    win = [0.0] * n
    top2 = [0.0] * n
    for k in range(steps):
        x = lo + (k + 0.5) * dx
        cdfs = [_cdf((x - m) / _TOTAL_SIGMA) for m in means]
        pdfs = [_phi((x - m) / _TOTAL_SIGMA) / _TOTAL_SIGMA for m in means]
        for i in range(n):
            if pdfs[i] < 1e-300:
                continue
            others = [cdfs[j] for j in range(n) if j != i]
            prod_all = math.prod(others)
            # Exactly one other horse ahead of i: Σ (1−F_k) Π_{j≠k} F_j over the others.
            one_ahead = 0.0
            for idx, fk in enumerate(others):
                if fk >= 1.0:
                    continue
                rest = prod_all / fk if fk > 1e-300 else math.prod(o for t, o in enumerate(others) if t != idx)
                one_ahead += (1.0 - fk) * rest
            win[i] += pdfs[i] * prod_all * dx
            top2[i] += pdfs[i] * (prod_all + one_ahead) * dx
    sw, st = sum(win), sum(top2)
    return [w / sw for w in win], [t * 2.0 / st for t in top2]


# ---------------------------------------------------------------------------
# Stat changes after a race
# ---------------------------------------------------------------------------

# Base change per stat by finishing position (1st..10th). Roughly cancels out across a field.
POSITION_CHANGE: tuple[float, ...] = (2.0, 1.4, 0.9, 0.5, 0.1, -0.1, -0.5, -0.8, -1.1, -1.4)
STAT_MIDPOINT = 50.0
REVERSION = 0.04  # each race, a stat moves this fraction of the way toward STAT_MIDPOINT


def stat_changes(horse: HorseStats, position: int, rng: random.Random | None = None) -> dict[str, float]:
    """Stat deltas for a horse that finished in `position` (1-based).

    The finishing-position change (with a random swing) plus a pull toward the
    midpoint: a horse far above it drifts back down, one far below catches up.
    Results are rounded to 1 decimal and kept within 0..STAT_CAP.
    """
    rng = rng or random
    base = POSITION_CHANGE[min(position, len(POSITION_CHANGE)) - 1]
    changes: dict[str, float] = {}
    for stat in STAT_NAMES:
        value = getattr(horse, stat)
        delta = base * rng.uniform(0.5, 1.5) + REVERSION * (STAT_MIDPOINT - value)
        new_value = min(STAT_CAP, max(0.0, round(value + delta, 1)))
        changes[stat] = round(new_value - value, 1)
    return changes


def rating(horse: HorseStats) -> int:
    """One-number summary of a horse (0-100), for display."""
    return round(sum(getattr(horse, s) for s in STAT_NAMES) / len(STAT_NAMES))


# ---------------------------------------------------------------------------
# House line (solo races)
# ---------------------------------------------------------------------------

HOUSE_LINE_MAX: dict[str, float] = {"win": 30.0, "place": 15.0}
HOUSE_LINE_MIN_MULTIPLIER = 1.05


def house_line(chances: Sequence[float], target_return: float, bet_type: str) -> list[float | None]:
    """Multiplier per horse for a solo bet, or None where the bet isn't offered."""
    cap = HOUSE_LINE_MAX[bet_type]
    out: list[float | None] = []
    for p in chances:
        mult = cap if p <= 0 else min(cap, math.floor(target_return / p * 100) / 100)
        out.append(mult if mult >= HOUSE_LINE_MIN_MULTIPLIER else None)
    return out


# ---------------------------------------------------------------------------
# Pools
# ---------------------------------------------------------------------------

CARRYOVER_MAX_STACKS = 5
BET_TYPES: tuple[str, ...] = ("win", "place")


@dataclass
class PoolBet:
    key: int        # anything that identifies the ticket (the bettor's user id)
    bet_type: str   # "win" | "place"
    horse: str      # horse id
    amount: int


@dataclass
class PoolOutcome:
    payouts: dict[int, int]          # ticket key -> gross payout (winning tickets only)
    carryover: dict[str, int]        # new carryover per pool
    carry_count: dict[str, int]      # new stack count per pool
    house_cut: dict[str, int]        # cut taken from new stakes per pool
    house_kept_carryover: dict[str, int]  # carryover the house kept after the max stacks
    house_topup: int = 0             # paid by the house to keep tickets at their stake


def pool_totals(bets: Iterable[PoolBet], carryover: dict[str, int]) -> dict[str, int]:
    """What each pool shows on the announcement: new stakes plus carryover."""
    totals = {t: carryover.get(t, 0) for t in BET_TYPES}
    for bet in bets:
        totals[bet.bet_type] += bet.amount
    return totals


def _split(net: int, tickets: list[PoolBet]) -> dict[int, int]:
    total = sum(b.amount for b in tickets)
    return {b.key: net * b.amount // total for b in tickets}


def settle_pools(
    bets: Sequence[PoolBet],
    order: Sequence[str],
    cut_pct: int,
    carryover: dict[str, int],
    carry_count: dict[str, int],
) -> PoolOutcome:
    """Settle the Win and Place pools of a race. `order` is horse ids, winner first."""
    out = PoolOutcome(
        payouts={},
        carryover=dict(carryover),
        carry_count=dict(carry_count),
        house_cut={t: 0 for t in BET_TYPES},
        house_kept_carryover={t: 0 for t in BET_TYPES},
    )
    for bet_type in BET_TYPES:
        tickets = [b for b in bets if b.bet_type == bet_type]
        stakes = sum(b.amount for b in tickets)
        old_carry = carryover.get(bet_type, 0)
        cut = stakes * cut_pct // 100
        out.house_cut[bet_type] = cut
        net = stakes - cut + old_carry

        if bet_type == "win":
            groups = [[b for b in tickets if b.horse == order[0]]]
        else:
            groups = [[b for b in tickets if b.horse == order[0]], [b for b in tickets if b.horse == order[1]]]
        groups = [g for g in groups if g]

        if groups:
            share = net // len(groups)
            for i, group in enumerate(groups):
                # The first group takes the odd chip when splitting in half.
                part = share + (net - share * len(groups) if i == 0 else 0)
                out.payouts.update(_split(part, group))
            out.carryover[bet_type] = 0
            out.carry_count[bet_type] = 0
        elif stakes == 0:
            pass  # nothing bet in this pool: the carryover just waits
        else:
            count = carry_count.get(bet_type, 0) + 1
            if count > CARRYOVER_MAX_STACKS:
                out.house_kept_carryover[bet_type] = net
                out.carryover[bet_type] = 0
                out.carry_count[bet_type] = 0
            else:
                out.carryover[bet_type] = net
                out.carry_count[bet_type] = count

    # A winning ticket always gets at least its stake back; the house covers the gap.
    for bet in bets:
        if bet.key in out.payouts and out.payouts[bet.key] < bet.amount:
            out.house_topup += bet.amount - out.payouts[bet.key]
            out.payouts[bet.key] = bet.amount
    return out


def ticket_wins(bet_type: str, horse: str, order: Sequence[str]) -> bool:
    return horse == order[0] if bet_type == "win" else horse in order[:2]
