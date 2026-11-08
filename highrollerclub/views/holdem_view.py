"""Texas Hold'em -- tables for 2-6 players (Discord UI).

Pure hand logic is in games/holdem.py; money safety (escrow, refunds on
load/unload) is in tasks/holdem_tables.py.

Flow
----
1. A player opens Texas Hold'em from the Game Floor (HoldemView), picks a blind
   level their rank allows, then sets the seat count and their buy-in.
2. A public table message (HoldemTableView) is posted in the channel. Other
   players Join with a buy-in, Top Up between hands, or Leave to cash out.
3. The host presses Deal once 2+ players can play. During a hand each player
   presses My Seat for their private controls (HoldemPrivateView): their hole
   cards and, on their turn, the betting buttons. Panels update themselves as
   the hand moves on.
4. Each turn has a timer. On timeout the player checks if they can, otherwise
   folds. A player who times out in 2 hands in a row is sat out until they
   press Sit Out / I'm Back.
5. At showdown the winning hands are shown. Losing hands get 15 seconds to
   Show or Muck (all-in run-outs are always face up).
6. The host (or a moderator) can close the table; every stack is returned. A
   table with no hand dealt for HOLDEM_IDLE_CLOSE_MINUTES closes itself.

Money rules
-----------
Every chip moves through cog.hd_buy_in / cog.hd_cash_out, which keep
GuildSettings.holdem_escrow equal to each player's table stack. Escrow is
written between hands only (after each hand settles), so it always holds the
stacks from the start of the current hand:
- Leaving mid-hand folds the player's hand; they are cashed out when it ends.
- Closing the table mid-hand voids the hand: everyone gets their stack from
  before it, exactly as a restart would.
- A player left with 0 chips is removed from the table; they can Join again.

Tables read the server's live settings (cog.db.get_conf) on every action
rather than keeping a copy, so a player wipe or backup restore never leaves a
table writing to stale data.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..commands.helper_functions import (
    apply_rank_change,
    channel_allowed,
    evaluate_rank,
    evaluate_specialty_titles,
    get_balance,
    get_holdem_tiers,
    get_pending_multiplier,
    has_bonus_bet_token,
    has_lucky_streak,
    holdem_buyin_range,
    holdem_tier_unlocked,
    is_blacklisted,
    record_loss,
    record_win,
)
from ..common.constants import (
    HOLDEM_ACTION_SECONDS,
    HOLDEM_ACTION_SECONDS_RANGE,
    HOLDEM_IDLE_CLOSE_MINUTES,
    HOLDEM_MAX_SEATS,
    HOLDEM_MUCK_SECONDS,
    HOLDEM_PRESTIGE_MIN_PLAYERS,
    HOLDEM_SITOUT_TIMEOUTS,
    PALETTE_GOLD,
    RANK_NAMES,
    embed_image,
)
from ..common.interactions import (
    expire_view,
    not_your_session,
    safe_defer,
    safe_edit_original_response,
    session_expired,
)
from ..common.models import GuildSettings, User
from ..games.holdem import HoldemError, HoldemHand, HoldemResult, best_hand

log = logging.getLogger("red.highrollerclub.holdem")

_TITLE = "♣️ Texas Hold'em"
_HIDDEN = "🂠"
_QUICK_TIMEOUT_SECONDS = 5      # later turns of a player who already timed out this hand
_TABLE_CAPTAIN_HANDS = 10       # counted hands a table must deal for its host to earn Table Captain progress


def _parse_amount(raw: str) -> int | None:
    text = raw.strip().replace(",", "")
    if not text.isdigit():
        return None
    value = int(text)
    return value if value > 0 else None


async def _currency_name(guild: discord.Guild, conf: GuildSettings) -> str:
    if conf.payment_mode == "chips":
        return "chips"
    return await bank.get_currency_name(guild)


def _cards(cards) -> str:
    return "  ".join(card.label for card in cards)


def _board_text(board) -> str:
    shown = [card.label for card in board] + [_HIDDEN] * (5 - len(board))
    return "  ".join(shown)


# ===========================================================================
# The table (shared state for everyone seated)
# ===========================================================================

@dataclass
class _TableSeat:
    member: discord.Member
    stack: int
    joined_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class HoldemTable:
    """One open table in one channel. Created by HoldemView, registered in cog.hd_tables()."""

    def __init__(
        self,
        cog: MixinMeta,
        guild: discord.Guild,
        channel: discord.abc.Messageable,
        host: discord.Member,
        small_blind: int,
        big_blind: int,
        max_seats: int,
        currency: str,
    ) -> None:
        self.cog = cog
        self.guild = guild
        self.channel = channel
        self.channel_id: int = channel.id  # type: ignore[attr-defined]
        self.host_id = host.id
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.max_seats = max_seats
        self.currency = currency
        self.seats: list[_TableSeat] = []
        # "waiting" (between hands) | "hand" | "showdown" (show/muck window) | "closed"
        self.phase = "waiting"
        self.lock = asyncio.Lock()
        self.message: discord.Message | None = None
        self.view: HoldemTableView | None = None
        self.opened_at = datetime.now(timezone.utc)
        self.last_hand_at = self.opened_at
        self.close_reason: str | None = None
        self.cash_outs: list[tuple[int, int, bool]] = []  # (user id, amount, paid) when the table closed
        self._idle_task: asyncio.Task | None = None

        # Hand play
        self.hand: HoldemHand | None = None
        self.hand_no = 0
        self.button_pos: int | None = None          # index into self.seats of the last dealer button
        self.sat_out: set[int] = set()
        self.leaving: set[int] = set()              # dealt-in players who pressed Leave: cashed out after the hand
        self.timed_out_this_hand: set[int] = set()
        self.timeout_streak: dict[int, int] = {}    # hands in a row with a timeout
        self.turn_token = 0                         # bumps on every change of turn, so stale timers do nothing
        self.turn_deadline: datetime | None = None
        self._turn_task: asyncio.Task | None = None
        self._timer_uid: int | None = None          # whose clock _turn_task is running
        self._muck_task: asyncio.Task | None = None
        self.panels: dict[int, discord.Interaction] = {}   # each player's last private-controls interaction
        self.log_lines: list[str] = []

        # The last finished hand, for the table embed
        self.last_result: HoldemResult | None = None
        self.last_hand_no = 0
        self.last_holes: dict[int, list] = {}
        self.reveal: dict[int, str] = {}            # loser uid -> "show" | "muck" | "pending"
        self.notes: list[str] = []                  # e.g. who busted or left after the hand
        self.counted_hands = 0                      # hands with 3+ players (Table Captain)
        self.captain_awarded = False

    # -- lookups ------------------------------------------------------------

    @property
    def key(self) -> tuple[int, int]:
        return (self.guild.id, self.channel_id)

    @property
    def conf(self) -> GuildSettings:
        return self.cog.db.get_conf(self.guild)

    def user(self, user_id: int) -> User:
        return self.conf.get_user(user_id)

    def seat_of(self, user_id: int) -> _TableSeat | None:
        for seat in self.seats:
            if seat.member.id == user_id:
                return seat
        return None

    def buyin_range(self) -> tuple[int, int]:
        return holdem_buyin_range(self.conf, self.big_blind)

    @property
    def idle_deadline(self) -> datetime:
        return self.last_hand_at + timedelta(minutes=HOLDEM_IDLE_CLOSE_MINUTES)

    def in_hand(self, user_id: int) -> bool:
        if self.hand is None or self.hand.is_complete:
            return False
        return any(s.user_id == user_id for s in self.hand.seats)

    def ready_seats(self) -> list[_TableSeat]:
        """Seats that would be dealt into the next hand."""
        return [s for s in self.seats if s.stack > 0 and s.member.id not in self.sat_out]

    def can_deal(self, user_id: int) -> bool:
        """The host deals. If the host is sitting out, any seated player may."""
        if self.seat_of(user_id) is None:
            return False
        if user_id == self.host_id:
            return True
        return self.host_id in self.sat_out or self.seat_of(self.host_id) is None

    def action_seconds(self) -> int:
        low, high = HOLDEM_ACTION_SECONDS_RANGE
        value = self.conf.holdem_action_seconds or HOLDEM_ACTION_SECONDS
        return max(low, min(high, value))

    # -- seating (caller holds cog.hd_lock(guild) for sit) ------------------

    async def sit(self, member: discord.Member, amount: int) -> str | None:
        """Seat a player with a buy-in. Returns an error message, or None on success.

        A player who joins during a hand is dealt in from the next one."""
        conf = self.conf
        if self.phase == "closed":
            return "This table has closed."
        if self.seat_of(member.id) is not None:
            return "You're already at this table."
        if self.cog.hd_is_seated(conf, self.guild.id, member.id):
            return "You're already seated at another Hold'em table. Leave it first."
        if len(self.seats) >= self.max_seats:
            return "This table is full."
        if is_blacklisted(conf, member.id):
            return "You can't play at the club right now."
        low, high = self.buyin_range()
        if not low <= amount <= high:
            return f"The buy-in here is **{low:,}–{high:,}** {self.currency}."
        user = self.user(member.id)
        balance = await get_balance(member, conf, user)
        if balance < amount:
            return f"You don't have enough {self.currency} for a **{amount:,}** buy-in (balance {balance:,})."
        if not await self.cog.hd_buy_in(member, conf, user, amount, self.channel_id):
            return "Your balance changed before the buy-in went in, so nothing was taken."
        self.seats.append(_TableSeat(member=member, stack=amount))
        return None

    async def top_up(self, member: discord.Member, amount: int) -> str | None:
        conf = self.conf
        seat = self.seat_of(member.id)
        if seat is None:
            return "You aren't seated at this table."
        if self.phase != "waiting":
            return "You can top up between hands."
        _, high = self.buyin_range()
        room = high - seat.stack
        if room <= 0:
            return f"Your stack is already at the table maximum (**{high:,}**)."
        if amount > room:
            return f"You can add up to **{room:,}** {self.currency} (table maximum {high:,})."
        user = self.user(member.id)
        if await get_balance(member, conf, user) < amount:
            return f"You don't have **{amount:,}** {self.currency} to add."
        if not await self.cog.hd_buy_in(member, conf, user, amount, self.channel_id):
            return "Nothing was added: your balance changed, or the server switched payment mode since you sat down."
        seat.stack += amount
        return None

    async def leave(self, user_id: int) -> tuple[int, bool] | None:
        """Cash a player out and free their seat. None if they weren't seated.

        Returns (amount, paid). If the payment failed it stays in escrow and is retried on the next load.
        Callers must not use this for a player dealt into the current hand (see request_leave).
        """
        seat = self.seat_of(user_id)
        if seat is None:
            return None
        amount, paid = await self.cog.hd_cash_out(self.guild, self.conf, user_id)
        self.seats.remove(seat)
        self.sat_out.discard(user_id)
        self.panels.pop(user_id, None)
        if self.button_pos is not None and self.seats:
            self.button_pos = min(self.button_pos, len(self.seats) - 1)
        if user_id == self.host_id and self.seats:
            self.host_id = self.seats[0].member.id  # longest-seated player takes over
        return amount, paid

    async def request_leave(self, user_id: int) -> tuple[str, tuple[int, bool] | None]:
        """Leave now, or (if dealt into the hand) fold and leave once it ends.

        Returns ("left", (amount, paid)) or ("after_hand", None) or ("not_seated", None).
        """
        if self.seat_of(user_id) is None:
            return "not_seated", None
        if self.in_hand(user_id):
            self.leaving.add(user_id)
            assert self.hand is not None
            self.hand.fold_player(user_id)
            self.log_lines.append(f"<@{user_id}> left the table (hand folded).")
            await self._after_change(keep_timer=True)
            return "after_hand", None
        result = await self.leave(user_id)
        return "left", result

    def toggle_sit_out(self, user_id: int) -> bool:
        """Flip a player's sit-out. Returns True if they are now sitting out."""
        if user_id in self.sat_out:
            self.sat_out.discard(user_id)
            self.timeout_streak[user_id] = 0
            return False
        self.sat_out.add(user_id)
        return True

    async def close(self, reason: str) -> None:
        """Close the table: cash everyone out, end the public message, unregister. Safe to call twice.

        Mid-hand, the hand is voided: escrow still holds every stack from before it."""
        if self.phase == "closed":
            return
        if self.hand is not None and not self.hand.is_complete:
            reason += " The hand in progress was cancelled, so stacks are from before it."
        self.phase = "closed"
        self.close_reason = reason
        self.hand = None
        for task in (self._idle_task, self._turn_task, self._muck_task):
            if task is not None and task is not asyncio.current_task():
                task.cancel()
        for seat in list(self.seats):
            amount, paid = await self.cog.hd_cash_out(self.guild, self.conf, seat.member.id)
            self.cash_outs.append((seat.member.id, amount, paid))
        self.seats.clear()
        if self.cog.hd_tables().get(self.key) is self:
            del self.cog.hd_tables()[self.key]
        if self.view is not None:
            self.view.stop()
        if self.message is not None:
            try:
                await asyncio.wait_for(self.message.edit(embed=self.build_embed(), view=None), timeout=5)
            except Exception:
                pass
        await self.refresh_panels()

    # -- hand play (caller holds self.lock) ---------------------------------

    def _next_button(self, ready: list[_TableSeat]) -> int:
        """Index into `ready` of this hand's dealer button: the next ready seat after the last button."""
        if self.button_pos is None:
            return 0
        n = len(self.seats)
        for offset in range(1, n + 1):
            seat = self.seats[(self.button_pos + offset) % n]
            if seat in ready:
                return ready.index(seat)
        return 0

    async def deal(self, user_id: int) -> str | None:
        """Start a hand. Returns an error message, or None."""
        if self.phase != "waiting":
            return "A hand is already in progress." if self.phase in {"hand", "showdown"} else "This table has closed."
        if not self.can_deal(user_id):
            return "Only the host can deal."
        ready = self.ready_seats()
        if len(ready) < 2:
            return "At least 2 players with chips (not sitting out) are needed to deal."
        button = self._next_button(ready)
        self.button_pos = self.seats.index(ready[button])
        self.hand = HoldemHand(
            [(s.member.id, s.stack) for s in ready],
            button=button,
            small_blind=self.small_blind,
            big_blind=self.big_blind,
        )
        self.hand_no += 1
        self.phase = "hand"
        self.timed_out_this_hand = set()
        self.log_lines = [f"Hand #{self.hand_no} dealt to {len(ready)} players."]
        self.last_hand_at = datetime.now(timezone.utc)
        await self._after_change()
        return None

    async def act(self, user_id: int, action: str, amount: int | None = None) -> str | None:
        """A player's own action from their private controls. Returns an error message, or None."""
        if self.phase != "hand" or self.hand is None:
            return "There's no hand in progress."
        if self.hand.to_act_id != user_id:
            return "It isn't your turn."
        try:
            self._apply(user_id, action, amount)
        except HoldemError as exc:
            return str(exc).capitalize() + "."
        await self._after_change()
        return None

    def _apply(self, user_id: int, action: str, amount: int | None, note: str = "") -> None:
        assert self.hand is not None
        before = len(self.hand.history)
        street = self.hand.street
        self.hand.act(user_id, action, amount)
        for _, uid, kind, added, street_bet in self.hand.history[before:]:
            self.log_lines.append(self._describe(uid, kind, added, street_bet) + note)
        if self.hand.street != street and not self.hand.is_complete:
            self.log_lines.append(f"— {self.hand.street.capitalize()}: {_cards(self.hand.board)}")

    @staticmethod
    def _describe(uid: int, kind: str, added: int, street_bet: int) -> str:
        who = f"<@{uid}>"
        if kind == "fold":
            return f"{who} folds."
        if kind == "check":
            return f"{who} checks."
        if kind == "call":
            return f"{who} calls {added:,}."
        if kind == "bet":
            return f"{who} bets {street_bet:,}."
        if kind == "raise":
            return f"{who} raises to {street_bet:,}."
        if kind == "allin":
            return f"{who} is all-in ({street_bet:,})."
        return f"{who} {kind} {added:,}."

    async def _after_change(self, keep_timer: bool = False) -> None:
        """After any change to the hand: finish it, or start the next player's timer. Then redraw.

        keep_timer: the change wasn't the acting player's (someone else left), so if the same
        player is still to act their clock keeps running."""
        hand = self.hand
        if (
            keep_timer and hand is not None and not hand.is_complete
            and hand.to_act_id is not None and hand.to_act_id == self._timer_uid
            and self._turn_task is not None and not self._turn_task.done()
        ):
            await self.refresh()
            await self.refresh_panels()
            return
        self.turn_token += 1
        self._timer_uid = None
        if self._turn_task is not None and self._turn_task is not asyncio.current_task():
            self._turn_task.cancel()
        self._turn_task = None
        self.turn_deadline = None
        if self.hand is not None and self.hand.is_complete:
            await self._finish_hand()
        elif self.hand is not None and self.hand.to_act_id is not None:
            uid = self.hand.to_act_id
            seconds = _QUICK_TIMEOUT_SECONDS if uid in self.timed_out_this_hand or uid in self.leaving else self.action_seconds()
            self.turn_deadline = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            self._timer_uid = uid
            self._turn_task = asyncio.create_task(self._turn_timer(self.turn_token, seconds))
        await self.refresh()
        await self.refresh_panels()

    async def _turn_timer(self, token: int, seconds: float) -> None:
        try:
            await asyncio.sleep(seconds)
            async with self.lock:
                await self.on_turn_timeout(token)
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Texas Hold'em: turn timer failed for table %s", self.key)

    async def on_turn_timeout(self, token: int) -> None:
        """The player to act ran out of time: check if possible, otherwise fold. (Caller holds self.lock.)"""
        if token != self.turn_token or self.phase != "hand" or self.hand is None:
            return
        uid = self.hand.to_act_id
        if uid is None:
            return
        action = self.hand.default_action(uid)
        self.timed_out_this_hand.add(uid)
        self._apply(uid, action, None, note=" *(timed out)*")
        await self._after_change()

    async def _finish_hand(self) -> None:
        """Settle a finished hand: stacks, escrow, stats, titles, leavers and busted players."""
        hand = self.hand
        assert hand is not None and hand.result is not None
        result = hand.result
        conf = self.conf
        counted = result.players_dealt_in >= HOLDEM_PRESTIGE_MIN_PLAYERS
        stacks = hand.final_stacks()

        # 1. Stacks and escrow (the only place escrow changes for players in a hand)
        for seat in self.seats:
            if seat.member.id in stacks:
                seat.stack = stacks[seat.member.id]
                entry = conf.holdem_escrow.get(seat.member.id)
                mode = entry.payment_mode if entry else conf.payment_mode
                self.cog.hd_escrow_set(conf, seat.member.id, seat.stack, mode, self.channel_id)

        # 2. Stats, prestige (3+ players only) and Hold'em title counters
        for uid in stacks:
            user = conf.get_user(uid)
            put_in = result.contributed[uid]
            net = result.net[uid]
            if put_in > 0 and net > 0:
                record_win(conf, user, "holdem", result.payouts[uid], put_in, award_prestige=counted)
            elif put_in > 0 and net < 0:
                record_loss(conf, user, "holdem", -net, award_prestige=counted)
            if uid in result.royal_flushes:
                user.holdem_royal_flushes += 1      # pure luck: counts at any table size
            if counted:
                user.holdem_hands_dealt += 1
                if result.fold_winner == uid:
                    user.holdem_fold_wins += 1
                if uid in result.river_comebacks:
                    user.holdem_river_comebacks += 1
                if uid in result.allin_showdown_wins:
                    user.holdem_allin_wins += 1
                if uid in result.bad_beats:
                    user.holdem_bad_beats += 1
                user.holdem_best_pot_bb = max(user.holdem_best_pot_bb, result.pot_won_bb.get(uid, 0))
        if counted:
            self.counted_hands += 1
            if self.counted_hands >= _TABLE_CAPTAIN_HANDS and not self.captain_awarded:
                self.captain_awarded = True
                conf.get_user(self.host_id).holdem_tables_hosted += 1
        for uid in stacks:
            user = conf.get_user(uid)
            new_rank = evaluate_rank(conf, user)
            if new_rank != user.rank:
                apply_rank_change(user, new_rank)
            user.earned_titles.extend(evaluate_specialty_titles(user))

        # 3. Timeouts: two hands in a row with a timeout sits a player out
        for uid in stacks:
            if uid in self.timed_out_this_hand:
                self.timeout_streak[uid] = self.timeout_streak.get(uid, 0) + 1
                if self.timeout_streak[uid] >= HOLDEM_SITOUT_TIMEOUTS and uid not in self.leaving:
                    self.sat_out.add(uid)
            else:
                self.timeout_streak[uid] = 0

        # 4. Remember the hand for the table embed
        self.last_result = result
        self.last_hand_no = self.hand_no
        self.last_holes = {s.user_id: list(s.hole) for s in hand.seats}
        self.notes = []
        losers_at_showdown = [
            uid for uid in result.showdown_hands if uid not in result.main_pot_winners and result.net[uid] <= 0
        ]
        self.reveal = {}
        if not result.fold_win and not result.ran_out:
            self.reveal = {uid: "pending" for uid in losers_at_showdown if uid not in self.leaving}
            for uid in losers_at_showdown:
                if uid in self.leaving:
                    self.reveal[uid] = "muck"

        # 5. Leavers cash out; anyone out of chips leaves the table
        for uid in list(self.leaving):
            await self.leave(uid)
        self.leaving.clear()
        for seat in list(self.seats):
            if seat.stack <= 0:
                self.notes.append(f"{seat.member.mention} is out of chips and left the table. Press **Join** to buy in again.")
                await self.leave(seat.member.id)
        self.cog.save()

        self.hand = None
        self.last_hand_at = datetime.now(timezone.utc)
        if not self.seats:
            await self.close("Everyone left the table.")
            return
        if any(v == "pending" for v in self.reveal.values()):
            self.phase = "showdown"
            self._muck_task = asyncio.create_task(self._muck_timer(self.last_hand_no))
        else:
            self.phase = "waiting"

    async def _muck_timer(self, hand_no: int) -> None:
        try:
            await asyncio.sleep(HOLDEM_MUCK_SECONDS)
            async with self.lock:
                if self.phase == "showdown" and self.last_hand_no == hand_no:
                    for uid, choice in self.reveal.items():
                        if choice == "pending":
                            self.reveal[uid] = "muck"
                    self.phase = "waiting"
                    await self.refresh()
                    await self.refresh_panels()
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Texas Hold'em: muck timer failed for table %s", self.key)

    async def choose_reveal(self, user_id: int, choice: str) -> str | None:
        """A losing player shows or mucks their hand. (Caller holds self.lock.)"""
        if self.phase != "showdown" or self.reveal.get(user_id) != "pending":
            return "There's nothing to show or muck right now."
        self.reveal[user_id] = choice
        if not any(v == "pending" for v in self.reveal.values()):
            self.phase = "waiting"
            if self._muck_task is not None:
                self._muck_task.cancel()
                self._muck_task = None
        await self.refresh()
        await self.refresh_panels()
        return None

    # -- idle close ---------------------------------------------------------

    def start_idle_timer(self) -> None:
        if self._idle_task is not None:
            self._idle_task.cancel()
        self._idle_task = asyncio.create_task(self._idle_watch())

    async def _idle_watch(self) -> None:
        try:
            while self.phase != "closed":
                wait = (self.idle_deadline - datetime.now(timezone.utc)).total_seconds()
                if wait > 0:
                    await asyncio.sleep(wait)
                    continue
                async with self.cog.hd_lock(self.guild.id):
                    async with self.lock:
                        if self.phase == "waiting" and datetime.now(timezone.utc) >= self.idle_deadline:
                            await self.close(f"No hand was dealt for {HOLDEM_IDLE_CLOSE_MINUTES} minutes.")
                            return
                await asyncio.sleep(5)  # a hand is running; its end moves the deadline
        except asyncio.CancelledError:
            return
        except Exception:
            log.exception("Texas Hold'em: idle timer failed for table %s", self.key)

    # -- display ------------------------------------------------------------

    def _seat_line(self, number: int, seat: _TableSeat) -> str:
        uid = seat.member.id
        hand = self.hand if self.phase == "hand" else None
        button = "🔘 " if self.button_pos is not None and self.seats.index(seat) == self.button_pos else ""
        if hand is not None and any(s.user_id == uid for s in hand.seats):
            hs = hand.seat_for(uid)
            line = f"`{number}` {button}{seat.member.mention} — **{hs.stack:,}**"
            if hs.street_bet:
                line += f" · bet {hs.street_bet:,}"
            if hs.folded:
                line += " · folded"
            elif hs.all_in:
                line += " · **all-in**"
            if hand.to_act_id == uid:
                line = "▶️ " + line
            return line
        line = f"`{number}` {button}{seat.member.mention} — **{seat.stack:,}**"
        if uid in self.sat_out:
            line += " · sitting out"
        elif hand is not None:
            line += " · next hand"
        return line

    def _result_lines(self) -> list[str]:
        result = self.last_result
        if result is None:
            return []
        lines = [f"**Hand #{self.last_hand_no}**  {_board_text(result.board) if result.board else ''}".rstrip()]
        if result.fold_win:
            uid = result.fold_winner
            lines.append(f"🏆 <@{uid}> wins **{result.payouts[uid]:,}** — everyone else folded.")
        else:
            winners = [uid for uid, net in result.net.items() if net > 0]
            for uid in sorted(winners, key=lambda u: -result.payouts[u]):
                hand = result.showdown_hands.get(uid)
                name = hand.name if hand else ""
                lines.append(f"🏆 <@{uid}> wins **{result.payouts[uid]:,}** · {name} · {_cards(self.last_holes.get(uid, []))}")
            for uid, hand in result.showdown_hands.items():
                if uid in winners:
                    continue
                choice = "show" if result.ran_out else self.reveal.get(uid, "show")
                if choice == "show":
                    lines.append(f"<@{uid}> · {hand.name} · {_cards(self.last_holes.get(uid, []))}")
                elif choice == "muck":
                    lines.append(f"<@{uid}> · {_HIDDEN} mucked")
                else:
                    lines.append(f"<@{uid}> · ⏳ deciding to show or muck…")
            if len(result.pots) > 1 and any(p.contested for p in result.pots[1:]):
                lines.append("*Side pots were in play.*")
        return lines + self.notes

    def build_embed(self) -> discord.Embed:
        low, high = self.buyin_range()
        blinds = f"{self.small_blind:,} / {self.big_blind:,}"
        if self.phase == "closed":
            e = discord.Embed(title=f"{_TITLE} · Table closed", color=discord.Color.dark_grey())
            lines = [f"**Blinds:** {blinds}", "", self.close_reason or "The table closed.", ""]
            if self.cash_outs:
                lines.append("**Stacks returned**")
                for uid, amount, paid in self.cash_outs:
                    note = "" if paid else " *(payment failed; it will be retried automatically)*"
                    lines.append(f"<@{uid}> — **{amount:,}** {self.currency}{note}")
            else:
                lines.append("Nobody was seated.")
            e.description = "\n".join(lines)
            if url := embed_image("holdem"):
                e.set_thumbnail(url=url)
            return e

        title = f"{_TITLE} · {blinds}"
        if self.phase == "hand":
            title += f" · Hand #{self.hand_no}"
        e = discord.Embed(title=title, color=PALETTE_GOLD)
        lines: list[str] = []
        if self.phase == "hand" and self.hand is not None:
            lines.append(f"**Board:** {_board_text(self.hand.board)}")
            lines.append(f"**Pot:** {self.hand.pot_total:,}")
        else:
            lines.append(f"**Host:** <@{self.host_id}> · **Buy-in:** {low:,}–{high:,} {self.currency}")
        lines.append(f"**Seats:** {len(self.seats)}/{self.max_seats}")
        lines.append("")
        for number, seat in enumerate(self.seats, start=1):
            lines.append(self._seat_line(number, seat))
        if not self.seats:
            lines.append("*No one is seated.*")
        lines.append("")

        if self.phase == "hand" and self.hand is not None:
            uid = self.hand.to_act_id
            if uid is not None and self.turn_deadline is not None:
                lines.append(f"▶️ <@{uid}> to act · time runs out <t:{int(self.turn_deadline.timestamp())}:R>")
            lines.append("Press **🂠 My Seat** to see your cards and act.")
            if self.log_lines:
                lines.append("")
                lines.extend(self.log_lines[-4:])
        else:
            result_lines = self._result_lines()
            if result_lines:
                lines.extend(result_lines)
                lines.append("")
            if self.phase == "showdown":
                lines.append(f"⏳ Losing hands have {HOLDEM_MUCK_SECONDS} seconds to show or muck.")
            elif len(self.ready_seats()) < 2:
                lines.append("⏳ Waiting for players. Press **Join** to take a seat.")
            else:
                lines.append("⏳ Waiting for the host to deal.")
            lines.append(f"Hands with {HOLDEM_PRESTIGE_MIN_PLAYERS}+ players count toward prestige and Hold'em titles.")
            lines.append(f"The table closes <t:{int(self.idle_deadline.timestamp())}:R> if no hand is dealt.")
        e.description = "\n".join(lines)
        if url := embed_image("holdem"):
            e.set_thumbnail(url=url)
        return e

    async def refresh(self) -> None:
        if self.message is None or self.phase == "closed":
            return
        if self.view is not None:
            self.view.sync_items()
        try:
            await self.message.edit(embed=self.build_embed(), view=self.view)
        except discord.HTTPException:
            log.warning("Texas Hold'em: couldn't update table message for %s", self.key)

    async def refresh_panels(self) -> None:
        """Redraw every open private panel. A panel Discord won't edit any more is forgotten."""
        if not self.panels:
            return

        async def redraw(uid: int, interaction: discord.Interaction) -> None:
            view = HoldemPrivateView(self, uid)
            try:
                await interaction.edit_original_response(embed=view.build_embed(), view=view)
            except (discord.HTTPException, discord.NotFound):
                if self.panels.get(uid) is interaction:
                    self.panels.pop(uid, None)

        await asyncio.gather(*(redraw(uid, i) for uid, i in list(self.panels.items())), return_exceptions=True)


# ===========================================================================
# Private controls (ephemeral, one per player)
# ===========================================================================

class _RaiseModal(discord.ui.Modal):
    def __init__(self, table: HoldemTable, user_id: int, is_bet: bool, min_to: int, max_to: int) -> None:
        super().__init__(title="Bet" if is_bet else "Raise")
        self._table = table
        self._user_id = user_id
        label = f"{'Bet' if is_bet else 'Raise to'} ({min_to:,}–{max_to:,})"
        self.amount_input = discord.ui.TextInput(label=label[:45], default=str(min_to), min_length=1, max_length=12)
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        amount = _parse_amount(self.amount_input.value)
        if amount is None:
            await interaction.response.send_message("Please enter a positive whole number.", ephemeral=True)
            return
        await safe_defer(interaction)
        table = self._table
        table.panels[self._user_id] = interaction
        async with table.lock:
            error = await table.act(self._user_id, "raise", amount)
        if error:
            await interaction.followup.send(error, ephemeral=True)


class HoldemPrivateView(discord.ui.View):
    """One player's cards and betting buttons. Rebuilt whenever the table changes."""

    def __init__(self, table: HoldemTable, user_id: int) -> None:
        super().__init__(timeout=900)  # Discord lets an ephemeral reply be edited for 15 minutes
        self._table = table
        self._user_id = user_id
        self._build_items()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._user_id:
            await interaction.response.send_message("These private controls aren't for you.", ephemeral=True)
            return False
        return True

    def _hand_seat(self):
        hand = self._table.hand
        if hand is None:
            return None
        for seat in hand.seats:
            if seat.user_id == self._user_id:
                return seat
        return None

    def _raise_sizes(self, la) -> list[tuple[str, int]]:
        """Quick bet/raise sizes (raise-to totals), all legal and short of all-in."""
        hand = self._table.hand
        assert hand is not None
        seat = hand.seat_for(self._user_id)
        to_call = max(0, hand.current_bet - seat.street_bet)
        after_call = hand.pot_total + to_call
        sizes = []
        seen: set[int] = set()
        for label, target in (("Min", la.min_to), ("½ Pot", hand.current_bet + after_call // 2), ("Pot", hand.current_bet + after_call)):
            target = max(la.min_to, target)
            if target >= la.max_to or target in seen:
                continue
            seen.add(target)
            sizes.append((label, target))
        return sizes

    def _build_items(self) -> None:
        self.clear_items()
        table = self._table
        hand = table.hand
        if table.phase == "hand" and hand is not None and hand.to_act_id == self._user_id:
            la = hand.legal_actions(self._user_id)
            seat = hand.seat_for(self._user_id)
            fold = discord.ui.Button(label="Fold", style=discord.ButtonStyle.red, row=0)
            fold.callback = self._make_action("fold")
            self.add_item(fold)
            if la.can_check:
                check = discord.ui.Button(label="Check", style=discord.ButtonStyle.grey, row=0)
                check.callback = self._make_action("check")
                self.add_item(check)
            if la.can_call:
                all_in_call = la.call_amount >= seat.stack
                label = f"Call all-in ({la.call_amount:,})" if all_in_call else f"Call {la.call_amount:,}"
                call = discord.ui.Button(label=label, style=discord.ButtonStyle.green, row=0)
                call.callback = self._make_action("call")
                self.add_item(call)
            if la.can_raise:
                allin = discord.ui.Button(label=f"All-In ({seat.stack:,})", style=discord.ButtonStyle.red, row=0)
                allin.callback = self._make_action("allin")
                self.add_item(allin)
                verb = "Bet" if la.is_bet else "Raise to"
                for label, target in self._raise_sizes(la):
                    btn = discord.ui.Button(label=f"{verb} {target:,} ({label})"[:80], style=discord.ButtonStyle.blurple, row=1)
                    btn.callback = self._make_action("raise", target)
                    self.add_item(btn)
                if la.min_to < la.max_to:
                    custom = discord.ui.Button(label="Custom…", style=discord.ButtonStyle.blurple, row=1)
                    custom.callback = self._on_custom
                    self.add_item(custom)
        elif table.phase == "showdown" and table.reveal.get(self._user_id) == "pending":
            show = discord.ui.Button(label="🪞 Show Hand", style=discord.ButtonStyle.green, row=0)
            show.callback = self._make_reveal("show")
            self.add_item(show)
            muck = discord.ui.Button(label=f"{_HIDDEN} Muck Hand", style=discord.ButtonStyle.grey, row=0)
            muck.callback = self._make_reveal("muck")
            self.add_item(muck)

    def build_embed(self) -> discord.Embed:
        table = self._table
        hand = table.hand
        e = discord.Embed(title=f"{_TITLE} · Your Seat", color=PALETTE_GOLD)
        seat = self._hand_seat()
        lines: list[str] = []
        if table.phase == "closed":
            lines.append("The table has closed. Your stack was returned.")
        elif table.phase == "hand" and hand is not None and seat is not None:
            lines.append(f"**Your cards:** {_cards(seat.hole)}")
            lines.append(f"**Board:** {_board_text(hand.board)}")
            if hand.board:
                lines.append(f"**Best hand:** {best_hand(seat.hole + hand.board).name}")
            lines.append(f"**Stack:** {seat.stack:,} · **Pot:** {hand.pot_total:,}")
            lines.append("")
            if seat.folded:
                lines.append("You folded this hand.")
            elif seat.all_in:
                lines.append("You're all-in. The rest plays out without you acting.")
            elif hand.to_act_id == self._user_id:
                la = hand.legal_actions(self._user_id)
                deadline = f" · time runs out <t:{int(table.turn_deadline.timestamp())}:R>" if table.turn_deadline else ""
                if la.can_call:
                    lines.append(f"▶️ **Your turn.** {la.call_amount:,} to call{deadline}")
                else:
                    lines.append(f"▶️ **Your turn.** You can check{deadline}")
            elif hand.to_act_id is not None:
                lines.append(f"Waiting on <@{hand.to_act_id}>.")
        else:
            last = table.last_result
            if last is not None and self._user_id in last.net:
                holes = table.last_holes.get(self._user_id, [])
                lines.append(f"**Hand #{table.last_hand_no}** · your cards: {_cards(holes)}")
                net = last.net[self._user_id]
                if net > 0:
                    lines.append(f"🏆 You won **{last.payouts[self._user_id]:,}** (+{net:,}).")
                elif net < 0:
                    lines.append(f"You lost **{-net:,}** this hand.")
                else:
                    lines.append("You broke even this hand.")
            if table.phase == "showdown" and table.reveal.get(self._user_id) == "pending":
                lines.append(f"Show your hand or muck it. If you do nothing for {HOLDEM_MUCK_SECONDS} seconds, it's mucked.")
            else:
                table_seat = table.seat_of(self._user_id)
                if table_seat is not None:
                    lines.append(f"**Stack:** {table_seat.stack:,}")
                    if self._user_id in table.sat_out:
                        lines.append("You're sitting out. Press **Sit Out / I'm Back** on the table to rejoin play.")
                    else:
                        lines.append("Waiting for the next hand.")
                else:
                    lines.append("You aren't seated at this table.")
        e.description = "\n".join(lines) or "Waiting for the next hand."
        return e

    def _make_action(self, action: str, amount: int | None = None):
        async def callback(interaction: discord.Interaction) -> None:
            await safe_defer(interaction)
            table = self._table
            table.panels[self._user_id] = interaction
            async with table.lock:
                error = await table.act(self._user_id, action, amount)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                view = HoldemPrivateView(table, self._user_id)
                await safe_edit_original_response(interaction, embed=view.build_embed(), view=view)

        return callback

    async def _on_custom(self, interaction: discord.Interaction) -> None:
        table = self._table
        hand = table.hand
        if table.phase != "hand" or hand is None or hand.to_act_id != self._user_id:
            await interaction.response.send_message("It isn't your turn.", ephemeral=True)
            return
        la = hand.legal_actions(self._user_id)
        await interaction.response.send_modal(_RaiseModal(table, self._user_id, la.is_bet, la.min_to, la.max_to))

    def _make_reveal(self, choice: str):
        async def callback(interaction: discord.Interaction) -> None:
            await safe_defer(interaction)
            table = self._table
            table.panels[self._user_id] = interaction
            async with table.lock:
                error = await table.choose_reveal(self._user_id, choice)
            if error:
                await interaction.followup.send(error, ephemeral=True)

        return callback


# ===========================================================================
# Public table message
# ===========================================================================

class _AmountModal(discord.ui.Modal):
    """Buy-in (Join) or top-up amount for a table."""

    def __init__(self, table: HoldemTable, mode: str) -> None:
        super().__init__(title="Join the Table" if mode == "join" else "Top Up Your Stack")
        self._table = table
        self._mode = mode
        low, high = table.buyin_range()
        if mode == "join":
            label = f"Buy-in ({low:,}–{high:,} {table.currency})"
            default = str(low)
        else:
            label = f"Chips to add (stack max {high:,})"
            default = None
        self.amount_input = discord.ui.TextInput(
            label=label[:45], default=default, min_length=1, max_length=12, placeholder=f"{low:,}"
        )
        self.add_item(self.amount_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction, ephemeral=True, thinking=True)
        member: discord.Member = interaction.user  # type: ignore[assignment]
        amount = _parse_amount(self.amount_input.value)
        if amount is None:
            await interaction.followup.send("Please enter a positive whole number.", ephemeral=True)
            return
        table = self._table
        if self._mode == "join":
            async with table.cog.hd_lock(table.guild.id):
                async with table.lock:
                    error = await table.sit(member, amount)
                    if error is None:
                        await table.refresh()
            note = " You'll be dealt in from the next hand." if table.phase in {"hand", "showdown"} else ""
            message = error or f"🪑 You sat down with **{amount:,}** {table.currency}.{note}"
        else:
            async with table.lock:
                error = await table.top_up(member, amount)
                if error is None:
                    await table.refresh()
            seat = table.seat_of(member.id)
            message = error or f"➕ Added **{amount:,}**. Your stack is now **{seat.stack:,}** {table.currency}."
        await interaction.followup.send(message, ephemeral=True)


class HoldemTableView(discord.ui.View):
    """Buttons on the public table message. Anyone can press them; each checks who may act."""

    def __init__(self, table: HoldemTable) -> None:
        super().__init__(timeout=None)  # the table's own idle timer closes it
        self._table = table
        self.sync_items()

    def sync_items(self) -> None:
        self.clear_items()
        table = self._table
        if table.phase == "closed":
            return
        full = len(table.seats) >= table.max_seats
        playing = table.phase in {"hand", "showdown"}

        if playing:
            seat_btn = discord.ui.Button(label=f"{_HIDDEN} My Seat", style=discord.ButtonStyle.blurple, row=0)
            seat_btn.callback = self._on_my_seat
            self.add_item(seat_btn)
        join = discord.ui.Button(label="🪑 Join", style=discord.ButtonStyle.green, row=0, disabled=full)
        join.callback = self._on_join
        self.add_item(join)
        if not playing:
            top_up = discord.ui.Button(label="➕ Top Up", style=discord.ButtonStyle.blurple, row=0)
            top_up.callback = self._on_top_up
            self.add_item(top_up)
        leave = discord.ui.Button(label="🚪 Leave", style=discord.ButtonStyle.grey, row=0)
        leave.callback = self._on_leave
        self.add_item(leave)

        if not playing:
            deal = discord.ui.Button(
                label="🃏 Deal", style=discord.ButtonStyle.green, row=1, disabled=len(table.ready_seats()) < 2
            )
            deal.callback = self._on_deal
            self.add_item(deal)
        sit = discord.ui.Button(label="⏸ Sit Out / I'm Back", style=discord.ButtonStyle.grey, row=1)
        sit.callback = self._on_sit_out
        self.add_item(sit)
        close = discord.ui.Button(label="✖ Close Table", style=discord.ButtonStyle.red, row=1)
        close.callback = self._on_close
        self.add_item(close)

    async def _can_play_here(self, interaction: discord.Interaction) -> bool:
        conf = self._table.conf
        if not conf.games_enabled.get("holdem", True):
            await interaction.response.send_message("Texas Hold'em is currently disabled on this server.", ephemeral=True)
            return False
        if is_blacklisted(conf, interaction.user.id):
            await interaction.response.send_message("You can't play at the club right now.", ephemeral=True)
            return False
        return True

    async def _on_my_seat(self, interaction: discord.Interaction) -> None:
        table = self._table
        if table.seat_of(interaction.user.id) is None:
            await interaction.response.send_message("You aren't seated at this table. Press **Join** to sit down.", ephemeral=True)
            return
        view = HoldemPrivateView(table, interaction.user.id)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)
        table.panels[interaction.user.id] = interaction

    async def _on_join(self, interaction: discord.Interaction) -> None:
        table = self._table
        if table.seat_of(interaction.user.id) is not None:
            await interaction.response.send_message("You're already seated here.", ephemeral=True)
            return
        if not await self._can_play_here(interaction):
            return
        await interaction.response.send_modal(_AmountModal(table, "join"))

    async def _on_top_up(self, interaction: discord.Interaction) -> None:
        table = self._table
        if table.seat_of(interaction.user.id) is None:
            await interaction.response.send_message("Only seated players can top up. Press **Join** to sit down.", ephemeral=True)
            return
        await interaction.response.send_modal(_AmountModal(table, "topup"))

    async def _on_deal(self, interaction: discord.Interaction) -> None:
        table = self._table
        if not table.can_deal(interaction.user.id):
            await interaction.response.send_message("Only the host can deal.", ephemeral=True)
            return
        if not await self._can_play_here(interaction):
            return
        await safe_defer(interaction)
        async with table.lock:
            error = await table.deal(interaction.user.id)
        if error:
            await interaction.followup.send(error, ephemeral=True)

    async def _on_sit_out(self, interaction: discord.Interaction) -> None:
        table = self._table
        if table.seat_of(interaction.user.id) is None:
            await interaction.response.send_message("You aren't seated at this table.", ephemeral=True)
            return
        await safe_defer(interaction, ephemeral=True, thinking=True)
        async with table.lock:
            now_out = table.toggle_sit_out(interaction.user.id)
            await table.refresh()
        if now_out:
            text = "⏸ You're sitting out from the next hand. Press the button again when you're back."
            if table.in_hand(interaction.user.id):
                text += " You're still in the current hand."
        else:
            text = "▶️ Welcome back. You'll be dealt into the next hand."
        await interaction.followup.send(text, ephemeral=True)

    async def _on_leave(self, interaction: discord.Interaction) -> None:
        table = self._table
        if table.seat_of(interaction.user.id) is None:
            await interaction.response.send_message("You aren't seated at this table.", ephemeral=True)
            return
        await safe_defer(interaction, ephemeral=True, thinking=True)
        async with table.cog.hd_lock(table.guild.id):
            async with table.lock:
                outcome, result = await table.request_leave(interaction.user.id)
                if outcome == "left" and not table.seats and table.phase != "closed":
                    await table.close("Everyone left the table.")
                elif outcome == "left":
                    await table.refresh()
        if outcome == "not_seated" or (outcome == "left" and result is None):
            await interaction.followup.send("You aren't seated at this table.", ephemeral=True)
        elif outcome == "after_hand":
            await interaction.followup.send(
                "🚪 Your hand was folded. You'll be cashed out as soon as this hand ends.", ephemeral=True
            )
        else:
            amount, paid = result
            if paid:
                await interaction.followup.send(f"🚪 You cashed out **{amount:,}** {table.currency}.", ephemeral=True)
            else:
                await interaction.followup.send(
                    f"🚪 You left the table. Paying your **{amount:,}** {table.currency} failed, "
                    "so it will be retried automatically.",
                    ephemeral=True,
                )

    async def _on_close(self, interaction: discord.Interaction) -> None:
        table = self._table
        member: discord.Member = interaction.user  # type: ignore[assignment]
        is_mod = await interaction.client.is_mod(member)  # type: ignore[attr-defined]
        if member.id != table.host_id and not is_mod:
            await interaction.response.send_message("Only the host (or a moderator) can close the table.", ephemeral=True)
            return
        await safe_defer(interaction, ephemeral=True, thinking=True)
        async with table.cog.hd_lock(table.guild.id):
            async with table.lock:
                who = "the host" if member.id == table.host_id else "a moderator"
                await table.close(f"Closed by {who}.")
        await interaction.followup.send("The table is closed and every stack was returned.", ephemeral=True)


# ===========================================================================
# Game Floor entry
# ===========================================================================

class _OpenTableModal(discord.ui.Modal):
    def __init__(self, view: "HoldemView", tier_index: int, big_blind: int) -> None:
        super().__init__(title="Open a Hold'em Table")
        self._view = view
        self._tier_index = tier_index
        low, high = holdem_buyin_range(view._conf, big_blind)
        self.seats_input = discord.ui.TextInput(
            label=f"Seats (2–{HOLDEM_MAX_SEATS})", default=str(HOLDEM_MAX_SEATS), min_length=1, max_length=1
        )
        self.buyin_input = discord.ui.TextInput(
            label=f"Your buy-in ({low:,}–{high:,})"[:45], default=str(low), min_length=1, max_length=12
        )
        self.add_item(self.seats_input)
        self.add_item(self.buyin_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        await self._view._process_open(interaction, self._tier_index, self.seats_input.value, self.buyin_input.value)


class HoldemView(discord.ui.View):
    """The player's own Hold'em screen, opened from the Game Floor."""

    def __init__(self, interaction: discord.Interaction, conf: GuildSettings, user: User, cog: MixinMeta) -> None:
        super().__init__(timeout=120)
        self._member: discord.Member = interaction.user  # type: ignore[assignment]
        self._conf = conf
        self._user = user
        self._cog = cog
        self._channel_id = interaction.channel_id
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""
        self._add_idle_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._member.id:
            await not_your_session(interaction)
            return False
        return True

    async def on_timeout(self) -> None:
        await expire_view(self)

    # -- buttons ------------------------------------------------------------

    def _add_idle_buttons(self) -> None:
        self.clear_items()
        open_btn = discord.ui.Button(label="♣️ Open a Table", style=discord.ButtonStyle.green, row=0)
        open_btn.callback = self._on_open
        self.add_item(open_btn)
        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_floor
        self.add_item(back)
        info = discord.ui.Button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1)
        info.callback = self._show_info
        self.add_item(info)

    def _unlocked_tiers(self) -> list[tuple[int, object]]:
        return [
            (index, tier)
            for index, tier in enumerate(get_holdem_tiers(self._conf))
            if holdem_tier_unlocked(self._conf, tier, self._user.rank)
        ]

    def _add_pick_items(self) -> None:
        self.clear_items()
        options = []
        for index, tier in self._unlocked_tiers():
            low, high = holdem_buyin_range(self._conf, tier.bb)
            options.append(discord.SelectOption(
                label=f"{tier.sb:,} / {tier.bb:,} blinds",
                description=f"Buy-in {low:,}–{high:,}"[:100],
                value=str(index),
            ))
        select = discord.ui.Select(placeholder="Choose the blinds", options=options, row=0)
        select.callback = self._on_pick
        self.add_item(select)
        back = discord.ui.Button(label="↩ Back", style=discord.ButtonStyle.grey, row=1)
        back.callback = self._back_to_idle
        self.add_item(back)

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if not await channel_allowed(interaction.client, self._conf, interaction.user, interaction.channel_id):
            await interaction.response.send_message(
                "Texas Hold'em can only be played in the designated casino channel(s).", ephemeral=True
            )
            return False
        if not self._conf.games_enabled.get("holdem", True):
            await interaction.response.send_message("Texas Hold'em is currently disabled on this server.", ephemeral=True)
            return False
        return True

    async def _on_open(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        if self._cog.hd_table_in(self._member.guild.id, interaction.channel_id) is not None:
            await interaction.response.send_message(
                "There's already a table open in this channel. Use its **Join** button, or open one in another channel.",
                ephemeral=True,
            )
            return
        if self._cog.hd_is_seated(self._conf, self._member.guild.id, self._member.id):
            await interaction.response.send_message("You're already seated at a Hold'em table. Leave it first.", ephemeral=True)
            return
        if not self._unlocked_tiers():
            await interaction.response.send_message("No blind levels are open to you right now.", ephemeral=True)
            return
        self._add_pick_items()
        await interaction.response.edit_message(embed=self._build_pick_embed(), view=self)

    async def _on_pick(self, interaction: discord.Interaction) -> None:
        index = int(interaction.data["values"][0])  # type: ignore[index]
        tiers = get_holdem_tiers(self._conf)
        if index >= len(tiers) or not holdem_tier_unlocked(self._conf, tiers[index], self._user.rank):
            await interaction.response.send_message("That blind level isn't available any more.", ephemeral=True)
            return
        await interaction.response.send_modal(_OpenTableModal(self, index, tiers[index].bb))

    async def _back_to_idle(self, interaction: discord.Interaction) -> None:
        self._add_idle_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title=f"{_TITLE} · How to Play", color=PALETTE_GOLD)
        e.description = (
            "**No-Limit Texas Hold'em for 2–6 players.**\n\n"
            "**The table**\n"
            "• Open a table at a blind level your rank allows, or join any open table you can afford.\n"
            "• You buy in to a table stack. Play as many hands as you like, top up between hands, "
            "and cash out by pressing **Leave**.\n"
            "• The host presses **Deal** to start each hand. Press **My Seat** to see your cards and act.\n\n"
            "**A hand**\n"
            "• Everyone gets 2 private cards. Five community cards come out in three steps: "
            "the flop (3), the turn (1) and the river (1), with a betting round before and after each.\n"
            "• On your turn: **Fold**, **Check**, **Call**, **Bet / Raise**, or go **All-In**. "
            "Minimum bet is the big blind; a raise must be at least the last raise.\n"
            "• Your best 5 cards from your 2 plus the 5 on the board win. Ties split the pot.\n\n"
            "**Good to know**\n"
            f"• If your time runs out you check, or fold if you can't. Time out in {HOLDEM_SITOUT_TIMEOUTS} hands "
            "in a row and you're sat out until you press **Sit Out / I'm Back**.\n"
            f"• Losing hands at showdown get {HOLDEM_MUCK_SECONDS} seconds to show or muck. All-in hands are always shown.\n"
            "• Leaving during a hand folds it; you're cashed out when the hand ends.\n"
            f"• Only hands with {HOLDEM_PRESTIGE_MIN_PLAYERS}+ players change prestige and count toward Hold'em titles.\n"
            "• No bonuses apply: no Lucky Streak, Bonus Bet Token or Multiplier Wheel. "
            "Every chip in a pot comes from the players.\n"
            f"• A table with no hand dealt for {HOLDEM_IDLE_CLOSE_MINUTES} minutes closes and returns every stack."
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        await safe_defer(interaction)
        balance = await get_balance(self._member, self._conf, self._user)
        currency_name = await _currency_name(self._member.guild, self._conf)
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    # -- opening a table ----------------------------------------------------

    async def _process_open(self, interaction: discord.Interaction, tier_index: int, seats_raw: str, buyin_raw: str) -> None:
        seats_text = seats_raw.strip()
        if not seats_text.isdigit() or not 2 <= int(seats_text) <= HOLDEM_MAX_SEATS:
            await interaction.followup.send(f"Seats must be a number from 2 to {HOLDEM_MAX_SEATS}.", ephemeral=True)
            return
        max_seats = int(seats_text)
        amount = _parse_amount(buyin_raw)
        if amount is None:
            await interaction.followup.send("Please enter a positive whole number for your buy-in.", ephemeral=True)
            return
        if await session_expired(self, interaction):
            return

        guild = self._member.guild
        channel = interaction.channel
        if channel is None:
            return
        async with self._cog.hd_lock(guild.id):
            conf = self._cog.db.get_conf(guild)
            tiers = get_holdem_tiers(conf)
            if tier_index >= len(tiers) or not holdem_tier_unlocked(conf, tiers[tier_index], conf.get_user(self._member.id).rank):
                await interaction.followup.send("That blind level isn't available any more.", ephemeral=True)
                return
            tier = tiers[tier_index]
            if self._cog.hd_table_in(guild.id, channel.id) is not None:
                await interaction.followup.send("Someone just opened a table in this channel. Use its **Join** button.", ephemeral=True)
                return
            table = HoldemTable(
                cog=self._cog,
                guild=guild,
                channel=channel,
                host=self._member,
                small_blind=tier.sb,
                big_blind=tier.bb,
                max_seats=max_seats,
                currency=await _currency_name(guild, conf),
            )
            async with table.lock:
                error = await table.sit(self._member, amount)
            if error:
                await interaction.followup.send(error, ephemeral=True)
                return
            self._cog.hd_tables()[table.key] = table
            table.view = HoldemTableView(table)
            try:
                table.message = await interaction.followup.send(embed=table.build_embed(), view=table.view, wait=True)
            except discord.HTTPException:
                log.exception("Texas Hold'em: couldn't post the table in %s", table.key)
                async with table.lock:
                    await table.close("The table couldn't be posted.")
                await interaction.followup.send("The table couldn't be posted, so your buy-in was returned.", ephemeral=True)
                return
            table.start_idle_timer()

        done = discord.Embed(
            title=f"{_TITLE}",
            color=PALETTE_GOLD,
            description=(
                f"✅ Your **{tier.sb:,} / {tier.bb:,}** table is open below with your **{amount:,}** "
                f"{table.currency} buy-in. Others can press **Join** to sit down."
            ),
        )
        if url := embed_image("holdem"):
            done.set_thumbnail(url=url)
        self.clear_items()
        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_floor
        self.add_item(back)
        await safe_edit_original_response(interaction, embed=done, view=self)

    # -- embeds -------------------------------------------------------------

    def _level_lines(self) -> list[str]:
        lines = []
        for tier in get_holdem_tiers(self._conf):
            if not tier.enabled:
                continue
            blinds = f"{tier.sb:,} / {tier.bb:,}"
            if holdem_tier_unlocked(self._conf, tier, self._user.rank):
                low, high = holdem_buyin_range(self._conf, tier.bb)
                lines.append(f"✅ **{blinds}** · buy-in {low:,}–{high:,}")
            elif not self._conf.bet_multipliers_enabled:
                lines.append(f"🔒 {blinds} · rank stakes are off on this server")
            else:
                lines.append(f"🔒 {blinds} · {RANK_NAMES.get(tier.min_rank, 'higher rank')} rank needed")
        return lines

    def _build_pick_embed(self) -> discord.Embed:
        e = discord.Embed(title=f"{_TITLE} · Open a Table", color=PALETTE_GOLD)
        e.description = (
            "Choose the blinds for your table. Next you'll set the number of seats and your buy-in.\n\n"
            + "\n".join(self._level_lines())
        )
        if url := embed_image("holdem"):
            e.set_thumbnail(url=url)
        return e

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title=f"{_TITLE}", color=PALETTE_GOLD)
        desc = (
            "**No-Limit Hold'em for 2–6 players.** Open a table, or join one with its **Join** button. "
            "Buy in, play hands, and cash out whenever you leave.\n\n"
            "**Blind levels**\n" + "\n".join(self._level_lines())
        )
        table = self._cog.hd_table_in(self._member.guild.id, self._channel_id) if self._channel_id else None
        if table is not None:
            desc += "\n\n🃏 There's a table open in this channel: use its **Join** button."
        desc += f"\n\nHands with {HOLDEM_PRESTIGE_MIN_PLAYERS}+ players count toward prestige and Hold'em titles."
        if mul := get_pending_multiplier(self._user):
            desc += f"\n\n⚡ Bonus snapshot: **{mul}x** multiplier is stored on your account, but Hold'em does not use it."
        if has_bonus_bet_token(self._user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token is stored on your account, but Hold'em does not use it."
        if has_lucky_streak(self._user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak is stored on your account, but Hold'em does not use it."
        e.description = desc
        if url := embed_image("holdem"):
            e.set_thumbnail(url=url)
        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")
        return e
