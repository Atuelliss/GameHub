"""Horse Racing runner: race lifecycle, money handling and restart safety.

The views (views/horse_racing_view.py) call the hr_* methods here; the pure race
maths lives in games/horse_racing.py.

Lifecycle of a race
-------------------
1. hr_start_race: under the server's race lock, the starter's bet is taken, the
   race is saved to GuildSettings.active_race and announced in the race channel,
   and a countdown task is started.
2. hr_join_race: under the same lock, another player's bet is taken and saved,
   and the announcement's pools are refreshed.
3. _hr_run (the task): posts the 60-second warning, closes betting at starts_at,
   runs the race on one edited message, then pays out.

Money safety
------------
- Every bet is saved the moment it's taken. A race found on load (bot restart or
  crash) has every unpaid bet refunded.
- Payouts mark each bet `paid` straight after crediting it, and the race is in
  phase "paying" while that happens, so a crash mid-payout never pays twice.
- Unloading the cog cancels a race that hasn't started paying and refunds it; one
  that is paying is allowed to finish first.
- A refund that fails (a bank error) goes to race_pending_refunds and is retried
  on the next load.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

import discord
from redbot.core import bank
from redbot.core.errors import BalanceTooHigh

from ..abc import CompositeMetaClass
from ..commands.helper_functions import (
    apply_rank_change,
    deduct_balance,
    evaluate_rank,
    evaluate_specialty_titles,
    get_balance,
    record_loss,
    record_win,
    validate_bet,
)
from ..common.models import GuildSettings, Horse, HorseRace, RaceBet, User
from ..games import horse_racing as hr

log = logging.getLogger("red.highrollerclub.horseracing")

STAGE_DELAY_SECONDS = 5
WARNING_SECONDS = 60
RACE_SLUG = "horserace"


def bet_slug(bet_type: str) -> str:
    """Bet-limit slug for a bet type."""
    return f"{RACE_SLUG}_{bet_type}"


def ensure_horses(conf: GuildSettings) -> dict[str, Horse]:
    """Create the default horses the first time racing is used. Returns conf.horses."""
    for horse_id, name in hr.DEFAULT_HORSES.items():
        if horse_id not in conf.horses:
            conf.horses[horse_id] = Horse(name=name)
    return conf.horses


# Mentions per message stay well under Discord's 2,000 characters, leaving room for the heading.
NOTIFY_CHUNK_CHARS = 1800


def notify_chunks(guild: discord.Guild, conf: GuildSettings, starter_id: int) -> list[str]:
    """Race-notification subscribers' mentions, split into message-sized chunks.

    Skips the starter and anyone no longer in the server.
    """
    chunks: list[str] = []
    current = ""
    for user_id in conf.race_notify_ids:
        if user_id == starter_id or guild.get_member(user_id) is None:
            continue
        mention = f"<@{user_id}>"
        if current and len(current) + 1 + len(mention) > NOTIFY_CHUNK_CHARS:
            chunks.append(current)
            current = mention
        else:
            current = f"{current} {mention}" if current else mention
    if current:
        chunks.append(current)
    return chunks


def cooldown_left(conf: GuildSettings, user: User) -> timedelta | None:
    """Time before this player can start another race, or None if they can now."""
    if not user.last_race_start:
        return None
    try:
        last = datetime.fromisoformat(user.last_race_start)
    except ValueError:
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    left = last + timedelta(minutes=conf.horserace_cooldown_minutes) - datetime.now(timezone.utc)
    return left if left.total_seconds() > 0 else None


class HorseRaceRunner(metaclass=CompositeMetaClass):
    """Mixin: owns the race tasks, locks and odds cache."""

    # ------------------------------------------------------------------
    # Runtime state (not saved)
    # ------------------------------------------------------------------

    def _hr_runtime(self) -> dict:
        state = getattr(self, "_hr_state", None)
        if state is None:
            state = self._hr_state = {"tasks": {}, "locks": {}, "odds": {}, "views": {}}
        return state

    def hr_lock(self, guild_id: int) -> asyncio.Lock:
        return self._hr_runtime()["locks"].setdefault(guild_id, asyncio.Lock())

    # ------------------------------------------------------------------
    # Horses, fields and odds
    # ------------------------------------------------------------------

    def hr_draw_field(self, conf: GuildSettings) -> list[str]:
        horses = ensure_horses(conf)
        return hr.pick_field({hid: h.streak for hid, h in horses.items()})

    async def hr_chances(self, conf: GuildSettings, horse_ids: list[str]) -> tuple[list[float], list[float]]:
        """Exact win and top-2 chances for a field (cached by the horses' current stats)."""
        horses = [conf.horses[hid] for hid in horse_ids]
        key = tuple((hid, h.speed, h.stamina, h.turning, h.start) for hid, h in zip(horse_ids, horses))
        cache: dict = self._hr_runtime()["odds"]
        if key not in cache:
            if len(cache) > 32:
                cache.clear()
            snapshot = [Horse(name=h.name, speed=h.speed, stamina=h.stamina, turning=h.turning, start=h.start) for h in horses]
            cache[key] = await asyncio.to_thread(hr.finish_chances, snapshot)
        return cache[key]

    async def hr_house_line(self, conf: GuildSettings, horse_ids: list[str], bet_type: str) -> list[float | None]:
        win, top2 = await self.hr_chances(conf, horse_ids)
        chances = win if bet_type == "win" else top2
        return hr.house_line(chances, conf.horserace_house_line_return_pct / 100, bet_type)

    # ------------------------------------------------------------------
    # Money
    # ------------------------------------------------------------------

    async def _hr_member(self, guild: discord.Guild | None, user_id: int) -> discord.Member | None:
        if guild is None:
            return None
        member = guild.get_member(user_id)
        if member is not None:
            return member
        try:
            return await guild.fetch_member(user_id)
        except discord.NotFound:
            return None

    async def _hr_credit(
        self, guild: discord.Guild | None, conf: GuildSettings, mode: str, user_id: int, amount: int,
        label: str = "Horse Racing",
    ) -> bool:
        """Pay `amount` in the given payment mode. False only on a retryable failure.

        Also used for Texas Hold'em refunds (label names the game in the log)."""
        amount = int(amount)
        if amount <= 0:
            return True
        if mode == "chips":
            conf.get_user(user_id).chip_balance += amount
            return True
        try:
            member = await self._hr_member(guild, user_id)
        except discord.HTTPException:
            return False
        if member is None:
            log.warning("%s: %s left guild %s; %s could not be paid", label, user_id, getattr(guild, "id", "?"), amount)
            return True  # nothing we can ever do: don't retry forever
        try:
            await bank.deposit_credits(member, amount)
        except BalanceTooHigh as exc:
            await bank.set_balance(member, exc.max_balance)
            log.warning("%s: bank max reached for %s; part of %s not paid", label, user_id, amount)
        except Exception:
            log.exception("%s: paying %s to %s failed", label, amount, user_id)
            return False
        return True

    async def _hr_refund_all(self, guild: discord.Guild | None, conf: GuildSettings, race: HorseRace) -> int:
        """Refund every unpaid bet of `race`. Failed refunds move to race_pending_refunds."""
        refunded = 0
        for bet in race.bets:
            if bet.paid:
                continue
            if await self._hr_credit(guild, conf, race.payment_mode, bet.user_id, bet.amount):
                refunded += 1
            else:
                conf.race_pending_refunds.append(bet.model_copy())
            bet.paid = True
        self.save()
        return refunded

    async def _hr_retry_pending(self, guild: discord.Guild | None, conf: GuildSettings) -> None:
        if not conf.race_pending_refunds:
            return
        still: list[RaceBet] = []
        for bet in conf.race_pending_refunds:
            # Pending refunds were taken in bank mode (chip refunds can't fail).
            if not await self._hr_credit(guild, conf, "bank", bet.user_id, bet.amount):
                still.append(bet)
        conf.race_pending_refunds = still
        self.save()

    # ------------------------------------------------------------------
    # Placing bets
    # ------------------------------------------------------------------

    async def _hr_take_bet(
        self, member: discord.Member, conf: GuildSettings, user: User, bet_type: str, amount: int
    ) -> str | None:
        balance = await get_balance(member, conf, user)
        error = validate_bet(conf, user, bet_slug(bet_type), amount, balance)
        if error:
            return error
        if not await deduct_balance(member, conf, user, amount):
            return "Your balance changed before the bet went in. Nothing was taken."
        return None

    async def hr_start_race(
        self,
        member: discord.Member,
        conf: GuildSettings,
        user: User,
        horse_ids: list[str],
        bet_type: str,
        horse_id: str,
        amount: int,
    ) -> str | None:
        """Take the starter's bet, save and announce the race. Returns an error message or None."""
        from ..views.horse_racing_view import RaceAnnouncementView, announcement_embed  # noqa: PLC0415

        guild = member.guild
        async with self.hr_lock(guild.id):
            if conf.active_race is not None:
                return "Someone just started a race. Join that one instead!"
            if not conf.race_channel_id:
                return "Horse Racing has no race channel set."
            channel = guild.get_channel(conf.race_channel_id)
            if not isinstance(channel, discord.TextChannel):
                return "The race channel no longer exists. Ask an admin to set a new one."
            if cooldown_left(conf, user):
                return "You can't start another race yet."
            if any(hid not in conf.horses for hid in horse_ids) or horse_id not in horse_ids:
                return "The horses changed while you were choosing. Open Horse Racing again."
            # A new race starts solo, so the bet must be one the house line offers.
            if (await self.hr_house_line(conf, horse_ids, bet_type))[horse_ids.index(horse_id)] is None:
                return "The house doesn't offer odds on that bet. Pick another horse or bet type."
            error = await self._hr_take_bet(member, conf, user, bet_type, amount)
            if error:
                return error
            now = datetime.now(timezone.utc).replace(microsecond=0)
            race = HorseRace(
                horse_ids=list(horse_ids),
                starter_id=member.id,
                channel_id=channel.id,
                starts_at=now + timedelta(minutes=conf.horserace_countdown_minutes),
                payment_mode=conf.payment_mode,
                bets=[RaceBet(user_id=member.id, bet_type=bet_type, horse_id=horse_id, amount=amount)],
            )
            conf.active_race = race
            self.save()

            currency = await self.hr_currency(guild, race.payment_mode)
            view = RaceAnnouncementView(self, guild.id, race)
            pings = notify_chunks(guild, conf, member.id)
            content = "🏇 **Horse Races about to Begin!!**"
            if pings:
                content += f"\n🔔 {pings[0]}"
            only_users = discord.AllowedMentions(users=True, roles=False, everyone=False)
            try:
                message = await channel.send(
                    content=content,
                    embed=announcement_embed(conf, race, currency),
                    view=view,
                    allowed_mentions=only_users,
                )
            except discord.HTTPException:
                log.warning("Horse Racing: can't post in race channel %s of guild %s", channel.id, guild.id)
                await self._hr_refund_all(guild, conf, race)
                conf.active_race = None
                self.save()
                return "I couldn't post in the race channel, so the race was cancelled and your bet refunded."
            race.message_id = message.id
            view.message = message
            self._hr_runtime()["views"][guild.id] = view
            self.save()
            self._hr_start_task(guild.id)
            for extra in pings[1:]:
                try:
                    await channel.send(f"🔔 {extra}", allowed_mentions=only_users)
                except discord.HTTPException as exc:
                    log.warning("Horse Racing: couldn't send race notification pings", exc_info=exc)
        return None

    async def hr_join_race(
        self,
        member: discord.Member,
        conf: GuildSettings,
        user: User,
        race: HorseRace,
        bet_type: str,
        horse_id: str,
        amount: int,
    ) -> str | None:
        """Add a bet to the open race. Returns an error message or None."""
        guild = member.guild
        async with self.hr_lock(guild.id):
            if conf.active_race is not race or race.phase != "betting" or datetime.now(timezone.utc) >= race.starts_at:
                return "Betting has closed for this race. Nothing was taken."
            if any(b.user_id == member.id for b in race.bets):
                return "You already have a bet on this race."
            if horse_id not in race.horse_ids:
                return "That horse isn't in this race."
            error = await self._hr_take_bet(member, conf, user, bet_type, amount)
            if error:
                return error
            race.bets.append(RaceBet(user_id=member.id, bet_type=bet_type, horse_id=horse_id, amount=amount))
            self.save()
        await self._hr_refresh_announcement(guild, conf, race)
        return None

    # ------------------------------------------------------------------
    # Cancelling
    # ------------------------------------------------------------------

    async def hr_cancel_by_starter(self, guild: discord.Guild, conf: GuildSettings, user_id: int) -> str:
        async with self.hr_lock(guild.id):
            race = conf.active_race
            if race is None or race.phase != "betting":
                return "There's no race to cancel."
            if race.starter_id != user_id:
                return "Only the player who started the race can cancel it."
            if len(race.bets) > 1:
                return "Other players have joined, so the race goes ahead."
            await self._hr_end_without_running(guild, conf, race, "The starter cancelled the race. Their bet was refunded.")
        return "Race cancelled. Your bet was refunded."

    async def hr_cancel_race(self, guild: discord.Guild, conf: GuildSettings, reason: str) -> int:
        """Cancel and refund the active race (admin command, reset, wipe). Returns bets refunded."""
        async with self.hr_lock(guild.id):
            race = conf.active_race
            if race is None:
                return 0
            if race.phase == "paying":
                return -1  # let the payout finish
            return await self._hr_end_without_running(guild, conf, race, reason)

    async def _hr_end_without_running(
        self, guild: discord.Guild | None, conf: GuildSettings, race: HorseRace, reason: str
    ) -> int:
        """Caller holds the lock. Stops the task, refunds and clears the race."""
        task = self._hr_runtime()["tasks"].pop(getattr(guild, "id", None), None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        refunded = await self._hr_refund_all(guild, conf, race)
        conf.active_race = None
        self.save()
        await self._hr_close_announcement(guild, race, f"❌ **Race cancelled.** {reason}")
        return refunded

    # ------------------------------------------------------------------
    # Announcement helpers
    # ------------------------------------------------------------------

    async def hr_currency(self, guild: discord.Guild, mode: str) -> str:
        return "chips" if mode == "chips" else await bank.get_currency_name(guild)

    def _hr_channel(self, guild: discord.Guild | None, race: HorseRace) -> discord.TextChannel | None:
        channel = guild.get_channel(race.channel_id) if guild else None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _hr_refresh_announcement(self, guild: discord.Guild, conf: GuildSettings, race: HorseRace) -> None:
        from ..views.horse_racing_view import announcement_embed  # noqa: PLC0415

        channel = self._hr_channel(guild, race)
        if channel is None or race.message_id is None:
            return
        currency = await self.hr_currency(guild, race.payment_mode)
        try:
            await channel.get_partial_message(race.message_id).edit(embed=announcement_embed(conf, race, currency))
        except discord.HTTPException:
            pass

    async def _hr_close_announcement(self, guild: discord.Guild | None, race: HorseRace, note: str) -> None:
        view = self._hr_runtime()["views"].pop(getattr(guild, "id", None), None)
        if view is not None:
            view.stop()
        channel = self._hr_channel(guild, race)
        if channel is None or race.message_id is None:
            return
        try:
            await channel.get_partial_message(race.message_id).edit(content=note, view=None)
        except discord.HTTPException:
            pass

    # ------------------------------------------------------------------
    # The race task
    # ------------------------------------------------------------------

    def _hr_start_task(self, guild_id: int) -> None:
        tasks: dict = self._hr_runtime()["tasks"]
        tasks[guild_id] = asyncio.create_task(self._hr_run(guild_id))

    async def _hr_sleep_until(self, when: datetime) -> None:
        delay = (when - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)

    async def _hr_run(self, guild_id: int) -> None:
        conf = self.db.get_conf(guild_id)
        race = conf.active_race
        guild = self.bot.get_guild(guild_id)
        if race is None:
            return
        try:
            channel = self._hr_channel(guild, race)
            warn_at = race.starts_at - timedelta(seconds=WARNING_SECONDS)
            if (warn_at - datetime.now(timezone.utc)).total_seconds() > 5:
                await self._hr_sleep_until(warn_at)
                if conf.active_race is race and channel is not None:
                    try:
                        await channel.send(f"⏱️ **The races start in {WARNING_SECONDS} seconds!** Last call for bets.")
                    except discord.HTTPException:
                        pass
            await self._hr_sleep_until(race.starts_at)
            await self._hr_race_and_pay(guild, conf, race)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Horse Racing: race in guild %s failed; refunding unpaid bets", guild_id)
            async with self.hr_lock(guild_id):
                if conf.active_race is race:
                    await self._hr_end_without_running(
                        guild, conf, race, "Something went wrong, so all unpaid bets were refunded."
                    )
        finally:
            tasks: dict = self._hr_runtime()["tasks"]
            if tasks.get(guild_id) is asyncio.current_task():
                tasks.pop(guild_id, None)

    async def _hr_race_and_pay(self, guild: discord.Guild | None, conf: GuildSettings, race: HorseRace) -> None:
        from ..views.horse_racing_view import results_embed, track_embed  # noqa: PLC0415

        async with self.hr_lock(guild.id if guild else 0):
            if conf.active_race is not race:
                return
            race.phase = "running"
            missing = [hid for hid in race.horse_ids if hid not in conf.horses]
            if missing:
                # A horse was removed mid-countdown (admins are blocked from this, but be safe).
                await self._hr_end_without_running(guild, conf, race, "A horse was withdrawn, so all bets were refunded.")
                return
            self.save()

        solo = len(race.bets) == 1
        horses = [conf.horses[hid] for hid in race.horse_ids]
        line: dict[str, list[float | None]] = {}
        if solo:
            for bet_type in hr.BET_TYPES:
                line[bet_type] = await self.hr_house_line(conf, race.horse_ids, bet_type)
        result = hr.run_race(horses, random.SystemRandom())
        order = [race.horse_ids[i] for i in result.order]

        # The starter's cooldown begins now that the race is actually running.
        starter = conf.get_user(race.starter_id)
        starter.last_race_start = datetime.now(timezone.utc).isoformat()
        if len(race.bets) >= 3:
            starter.races_promoted += 1
        self.save()

        await self._hr_close_announcement(guild, race, "🏁 **Betting is closed. They're off!**")
        channel = self._hr_channel(guild, race)
        race_message: discord.Message | None = None
        for stage_index in range(len(hr.RACE_STAGES)):
            embed = track_embed(conf, race, result, stage_index)
            if channel is not None:
                try:
                    if race_message is None:
                        race_message = await channel.send(embed=embed)
                    else:
                        await race_message.edit(embed=embed)
                except discord.HTTPException:
                    pass
            await asyncio.sleep(STAGE_DELAY_SECONDS)

        payouts, notes = await self._hr_settle(guild, conf, race, order, solo, line)
        changes, triple_crown = self._hr_update_horses(conf, race, order)
        conf.active_race = None
        self.save()

        if channel is not None:
            currency = await self.hr_currency(guild, race.payment_mode) if guild else "chips"
            winners = sorted({uid for uid, amount in payouts.items() if amount > 0})
            content = " ".join(f"<@{uid}>" for uid in winners) or None
            try:
                await channel.send(
                    content=content,
                    embed=results_embed(conf, race, order, changes, payouts, solo, line, currency, notes, triple_crown),
                    allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False),
                )
            except discord.HTTPException:
                pass

    async def _hr_settle(
        self,
        guild: discord.Guild | None,
        conf: GuildSettings,
        race: HorseRace,
        order: list[str],
        solo: bool,
        line: dict[str, list[float | None]],
    ) -> tuple[dict[int, int], list[str]]:
        """Pay every bet once, record stats. Returns ({user_id: payout}, notes)."""
        notes: list[str] = []
        async with self.hr_lock(guild.id if guild else 0):
            race.phase = "paying"
            self.save()

        payouts: dict[int, int] = {}
        if solo:
            bet = race.bets[0]
            if hr.ticket_wins(bet.bet_type, bet.horse_id, order):
                mult = line[bet.bet_type][race.horse_ids.index(bet.horse_id)] or 1.0
                payouts[bet.user_id] = int(bet.amount * mult)
        else:
            outcome = hr.settle_pools(
                [hr.PoolBet(b.user_id, b.bet_type, b.horse_id, b.amount) for b in race.bets],
                order,
                conf.horserace_house_cut_pct,
                conf.race_carryover,
                conf.race_carry_count,
            )
            payouts = dict(outcome.payouts)
            for bet_type in hr.BET_TYPES:
                if outcome.carryover[bet_type] > conf.race_carryover.get(bet_type, 0):
                    notes.append(f"Nobody backed the {bet_type} winner{'s' if bet_type == 'place' else ''}: "
                                 f"{outcome.carryover[bet_type]:,} carries over to the next race.")
                if outcome.house_kept_carryover[bet_type]:
                    notes.append(f"The {bet_type} carryover reached {hr.CARRYOVER_MAX_STACKS} races, "
                                 f"so the house kept {outcome.house_kept_carryover[bet_type]:,}.")
            conf.race_carryover = outcome.carryover
            conf.race_carry_count = outcome.carry_count

        win_backers = sum(1 for b in race.bets if b.bet_type == "win" and b.horse_id == order[0])
        for bet in race.bets:
            if bet.paid:
                continue
            payout = payouts.get(bet.user_id, 0)
            if payout > 0 and not await self._hr_credit(guild, conf, race.payment_mode, bet.user_id, payout):
                conf.race_pending_refunds.append(RaceBet(user_id=bet.user_id, bet_type=bet.bet_type,
                                                         horse_id=bet.horse_id, amount=payout))
            bet.paid = True
            self._hr_record(conf, bet, payout, solo, win_backers)
            self.save()
        return payouts, notes

    def _hr_record(self, conf: GuildSettings, bet: RaceBet, payout: int, solo: bool, win_backers: int) -> None:
        user = conf.get_user(bet.user_id)
        user.race_bets_placed += 1
        if payout > 0:
            record_win(conf, user, RACE_SLUG, payout, bet.amount)
            user.race_best_profit = max(user.race_best_profit, payout - bet.amount)
            if bet.bet_type == "win":
                user.race_win_bets_cashed += 1
                user.race_win_streak += 1
                user.race_best_multiple = max(user.race_best_multiple, round(payout / bet.amount, 2))
                if not solo and win_backers == 1:
                    user.race_called_it += 1
            else:
                user.race_place_bets_cashed += 1
                user.race_win_streak = 0
        else:
            record_loss(conf, user, RACE_SLUG, bet.amount)
            user.race_win_streak = 0
        new_rank = evaluate_rank(conf, user)
        if new_rank != user.rank:
            apply_rank_change(user, new_rank)
        user.earned_titles.extend(evaluate_specialty_titles(user))

    def _hr_update_horses(
        self, conf: GuildSettings, race: HorseRace, order: list[str]
    ) -> tuple[dict[str, dict[str, float]], str | None]:
        """Apply stat changes and records. Returns ({horse_id: changes}, triple-crown horse id)."""
        rng = random.SystemRandom()
        changes: dict[str, dict[str, float]] = {}
        triple_crown: str | None = None
        for position, horse_id in enumerate(order, 1):
            horse = conf.horses.get(horse_id)
            if horse is None:
                continue
            delta = hr.stat_changes(horse, position, rng)
            for stat, value in delta.items():
                setattr(horse, stat, round(getattr(horse, stat) + value, 1))
            changes[horse_id] = delta
            horse.races += 1
            horse.last5 = (horse.last5 + [position])[-5:]
            if position == 1:
                horse.wins += 1
                horse.win_streak += 1
                if horse.win_streak == 3:
                    triple_crown = horse_id
            else:
                horse.win_streak = 0
                if position == 2:
                    horse.places += 1
        streaks = hr.next_streaks({hid: h.streak for hid, h in conf.horses.items()}, race.horse_ids)
        for hid, value in streaks.items():
            conf.horses[hid].streak = value
        return changes, triple_crown

    # ------------------------------------------------------------------
    # Load / unload
    # ------------------------------------------------------------------

    async def hr_recover(self) -> None:
        """On load: refund any race left over from before a restart, and retry failed refunds."""
        for guild_id, conf in self.db.configs.items():
            guild = self.bot.get_guild(guild_id)
            race = conf.active_race
            if race is not None:
                refunded = await self._hr_refund_all(guild, conf, race)
                conf.active_race = None
                self.save()
                log.info("Horse Racing: refunded %s bets of an interrupted race in guild %s", refunded, guild_id)
                channel = self._hr_channel(guild, race)
                if channel is not None:
                    try:
                        await channel.send("🏇 The race was cancelled by a bot restart. All bets were refunded.")
                    except discord.HTTPException:
                        pass
            await self._hr_retry_pending(guild, conf)

    async def hr_shutdown(self) -> None:
        """On unload: let paying races finish, cancel and refund the rest."""
        tasks: dict = self._hr_runtime()["tasks"]
        for guild_id, task in list(tasks.items()):
            conf = self.db.configs.get(guild_id)
            race = conf.active_race if conf else None
            if race is not None and race.phase == "paying":
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=30)
                except (asyncio.TimeoutError, Exception):
                    pass
                continue
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        tasks.clear()
        for guild_id, conf in self.db.configs.items():
            race = conf.active_race
            if race is None or race.phase == "paying":
                continue  # a paying race that didn't finish is refunded (unpaid bets only) on load
            guild = self.bot.get_guild(guild_id)
            # No timeout around the refund: cutting it off between a credit and its
            # `paid` mark would refund that bet twice on the next load.
            try:
                await self._hr_refund_all(guild, conf, race)
                conf.active_race = None
                self.save()
            except Exception:
                log.exception("Horse Racing: refund on unload failed in guild %s; it will be retried on load", guild_id)
                continue
            try:
                await asyncio.wait_for(
                    self._hr_close_announcement(guild, race, "❌ **Race cancelled.** The casino is restarting. All bets were refunded."),
                    timeout=5,
                )
            except Exception:
                pass
