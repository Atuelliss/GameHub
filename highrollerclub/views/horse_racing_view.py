"""HorseRacingView -- Discord UI for Horse Racing in HighRollerClub.

Screens
-------
HorseRacingView (private, from the Game Room)
    "Start a Race?" with a freshly drawn field, or the race in progress.
    Buttons: Start a Race | Join the Race | Stable | How to Play | Back to Floor
RaceBetView (private: in place from HorseRacingView, or ephemeral from the Join button)
    Bet type (Win / Place) -> horse -> amount (modal) -> confirm.
RaceAnnouncementView (public, in the race channel)
    Join the Race | Cancel Race (starter, while solo) | How to Play

The embeds for the announcement, the live race and the results are built here and
used by tasks/horse_races.py, which runs the race and handles all the money.
Pure race maths lives in games/horse_racing.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.constants import PALETTE_GOLD, embed_image
from ..common.interactions import (
    expire_view,
    not_your_session,
    one_at_a_time,
    safe_defer,
    safe_edit_original_response,
    session_expired,
)
from ..common.models import GuildSettings, Horse, HorseRace, User
from ..commands.helper_functions import channel_allowed, get_balance, get_bet_limits, is_blacklisted
from ..games import horse_racing as hr

if TYPE_CHECKING:
    from ..games.horse_racing import RaceResult

log = logging.getLogger("red.highrollerclub.horseracing")

_BET_LABEL = {"win": "🥇 Win", "place": "🥈 Place"}
# The race results: each bet's name, and the medal shown only beside a bet that paid
_RESULT_LABEL = {"win": "Win Bet", "place": "Place Bet"}
_WON_MEDAL = {"win": "🥇", "place": "🥈"}
_PLACE_RULE = "Place pays if your horse finishes **1st or 2nd**."
_BAR_WIDTH = 12


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------

def _name(conf: GuildSettings, horse_id: str) -> str:
    horse = conf.horses.get(horse_id)
    return horse.name if horse else "Unknown"


def _stats_line(horse: Horse) -> str:
    return (
        f"SPD {horse.speed:.0f} · STA {horse.stamina:.0f} · "
        f"TRN {horse.turning:.0f} · GTE {horse.start:.0f}"
    )


def _form(horse: Horse) -> str:
    return "-".join(str(p) for p in reversed(horse.last5)) if horse.last5 else "—"


def _unix(dt: datetime) -> int:
    return int(dt.timestamp())


def _pool_lines(conf: GuildSettings, race: HorseRace, currency: str) -> list[str]:
    bets = [hr.PoolBet(b.user_id, b.bet_type, b.horse_id, b.amount) for b in race.bets]
    totals = hr.pool_totals(bets, conf.race_carryover)
    lines = []
    for bet_type, label in (("win", "Win pool"), ("place", "Place pool")):
        carry = conf.race_carryover.get(bet_type, 0)
        extra = f" (includes {carry:,} carried over)" if carry else ""
        lines.append(f"**{label}:** {totals[bet_type]:,} {currency}{extra}")
    return lines


def _payout_mode_line(conf: GuildSettings, race: HorseRace) -> str:
    if len(race.bets) <= 1:
        return (
            "**Payout:** house line (solo race). The starter's bet pays fixed odds. "
            "If anyone joins, the race switches to the pools."
        )
    return f"**Payout:** shared pools, {conf.horserace_house_cut_pct}% house cut."


def how_to_play_embed(conf: GuildSettings) -> discord.Embed:
    e = discord.Embed(title="🏇 How to Play: Horse Racing", color=PALETTE_GOLD)
    e.description = (
        f"Ten horses run each race, drawn from the club's stable. Start a race with one bet, "
        f"and other players have **{conf.horserace_countdown_minutes} minutes** to join before the gates open."
    )
    e.add_field(
        name="Bets",
        value=(
            "• **Win:** your horse finishes 1st.\n"
            "• **Place:** your horse finishes **1st or 2nd**.\n"
            "• One bet per player per race: one type, one horse, one amount."
        ),
        inline=False,
    )
    e.add_field(
        name="Payouts",
        value=(
            f"• **Pools:** Win bets go into the Win pool and Place bets into the Place pool. "
            f"The house takes **{conf.horserace_house_cut_pct}%** of new bets; the rest is shared by the "
            f"winning tickets in proportion to their bets. A Place pool is split in half between "
            f"the backers of the 1st and 2nd horses. A winning ticket always gets at least its bet back.\n"
            f"• **Carryover:** if nobody backed a winner, that pool carries over to the next race, "
            f"for up to {hr.CARRYOVER_MAX_STACKS} races. After that, the house keeps it.\n"
            f"• **Solo race:** if nobody joins, your bet pays the **house line** instead: fixed odds "
            f"shown in the horse picker, set from each horse's real chances. Very likely bets "
            f"show \"no odds\" and can't be picked."
        ),
        inline=False,
    )
    e.add_field(
        name="The Horses",
        value=(
            "Every horse has Speed, Stamina, Turning and Gate (start) stats, and they change "
            "after every race: good finishes improve them, poor ones wear them down. "
            f"A horse never runs more than {hr.MAX_CONSECUTIVE_RACES} races in a row. "
            "Check the **Stable** for each horse's record and form."
        ),
        inline=False,
    )
    e.add_field(
        name="Rules",
        value=(
            f"• The player who starts a race waits **{conf.horserace_cooldown_minutes} minutes** before "
            "starting another, but can join other races any time. No wait if the race is cancelled.\n"
            "• The starter can cancel while they're the only bettor (full refund).\n"
            "• No bonuses apply: no Lucky Streak, Bonus Bet Token or Multiplier Wheel.\n"
            "• Press **🔔 Enable Race Notifications** to be pinged when a race opens for betting "
            "(not for races you start). Press it again to stop."
        ),
        inline=False,
    )
    return e


def stable_embed(conf: GuildSettings) -> discord.Embed:
    horses = sorted(conf.horses.values(), key=lambda h: (-h.wins, -h.places, h.name.casefold()))
    champion = horses[0] if horses and horses[0].wins > 0 else None
    lines = []
    for horse in horses:
        crown = " 👑" if horse is champion else ""
        custom = " ✨" if horse.custom else ""
        lines.append(
            f"**{horse.name}**{crown}{custom} · Rating {hr.rating(horse)}\n"
            f"{horse.wins}W {horse.places}P in {horse.races} · Form {_form(horse)}"
        )
    e = discord.Embed(title="🐎 The Stable", color=PALETTE_GOLD)
    e.description = "\n".join(lines) or "No horses yet."
    e.set_footer(text="👑 Champion of the Stable (most wins) · ✨ added by this server · Form: latest first")
    return e


# ---------------------------------------------------------------------------
# Embeds used by the race runner
# ---------------------------------------------------------------------------

def announcement_embed(conf: GuildSettings, race: HorseRace, currency: str) -> discord.Embed:
    start = _unix(race.starts_at)
    e = discord.Embed(title="🏇 Horse Races about to Begin!!", color=PALETTE_GOLD)
    e.description = (
        f"**The gates open <t:{start}:R>** (<t:{start}:t>).\n"
        f"{_PLACE_RULE}\n\n"
        + "\n".join(_pool_lines(conf, race, currency))
        + f"\n**Bettors:** {len(race.bets)}\n"
        + _payout_mode_line(conf, race)
    )
    runners = [
        f"`{i:>2}` {_name(conf, hid)} · Rating {hr.rating(conf.horses[hid]) if hid in conf.horses else 0}"
        for i, hid in enumerate(race.horse_ids, 1)
    ]
    e.add_field(name="Runners", value="\n".join(runners), inline=False)
    e.set_footer(text="Press Join the Race to bet. One bet per player.")
    return e


def track_embed(conf: GuildSettings, race: HorseRace, result: RaceResult, stage_index: int) -> discord.Embed:
    stage = hr.RACE_STAGES[stage_index]
    finish = max(result.stage_distances[-1]) or 1.0
    lines = []
    for pos, i in enumerate(result.standings(stage_index), 1):
        dist = result.stage_distances[stage_index][i]
        filled = max(1, min(_BAR_WIDTH, round(_BAR_WIDTH * dist / finish)))
        name = _name(conf, race.horse_ids[i])[:13]
        lines.append(f"{pos:>2} {name:<13} {'█' * filled}")
    e = discord.Embed(
        title=f"🏇 Stage {stage_index + 1}/{len(hr.RACE_STAGES)}: {stage.name}",
        color=PALETTE_GOLD,
    )
    e.description = "```\n" + "\n".join(lines) + "\n```"
    e.set_footer(text="Place pays on 1st or 2nd.")
    return e


def results_embed(
    conf: GuildSettings,
    race: HorseRace,
    order: list[str],
    changes: dict[str, dict[str, float]],
    payouts: dict[int, int],
    solo: bool,
    line: dict[str, list[float | None]],
    currency: str,
    notes: list[str],
    triple_crown: str | None,
) -> discord.Embed:
    e = discord.Embed(title="🏁 Race Results", color=PALETTE_GOLD)
    rows = []
    for pos, hid in enumerate(order, 1):
        delta = changes.get(hid, {})
        avg = sum(delta.values()) / len(delta) if delta else 0.0
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(pos, f"`{pos:>2}`")
        horse = conf.horses.get(hid)
        rating = f" · Rating {hr.rating(horse)}" if horse else ""
        rows.append(f"{medal} **{_name(conf, hid)}**{rating} ({avg:+.1f})")
    e.description = "\n".join(rows)
    if triple_crown:
        e.description += f"\n\n👑 **TRIPLE CROWN!** {_name(conf, triple_crown)} has won 3 races in a row!"

    bet_lines = []
    for bet in race.bets:
        ticket = f"<@{bet.user_id}>'s [{_RESULT_LABEL[bet.bet_type]}] of {bet.amount:,} {currency} on {_name(conf, bet.horse_id)}"
        paid = payouts.get(bet.user_id, 0)
        if paid > 0:
            # The medal only shows on a bet that paid: gold for a Win bet, silver for a Place bet
            bet_lines.append(f"{_WON_MEDAL[bet.bet_type]} {ticket} won **{paid:,} {currency}**!")
        else:
            bet_lines.append(f"❌ {ticket} was lost!")
    if bet_lines:
        mode = "House line (solo race)" if solo else f"Pools, {conf.horserace_house_cut_pct}% house cut"
        e.add_field(name=f"Bets · {mode}", value="\n".join(bet_lines)[:1024], inline=False)
    if notes:
        e.add_field(name="Pools", value="\n".join(notes)[:1024], inline=False)
    e.set_footer(text="Stat changes shown as the average across the four stats.")
    return e


# ---------------------------------------------------------------------------
# Bet amount modal
# ---------------------------------------------------------------------------

class _AmountModal(discord.ui.Modal, title="Place Your Bet — Horse Racing"):
    def __init__(self, view: RaceBetView, min_bet: int, max_bet: int) -> None:
        super().__init__(timeout=300)
        self._view = view
        self.amount = discord.ui.TextInput(
            label=f"Bet Amount (min {min_bet:,} · max {max_bet:,})",
            placeholder=f"Enter a value between {min_bet:,} and {max_bet:,}",
            min_length=1,
            max_length=10,
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        raw = self.amount.value.strip().replace(",", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.response.send_message("Please enter a valid positive whole number.", ephemeral=True)
            return
        await safe_defer(interaction)
        await self._view.show_confirm(interaction, int(raw))


# ---------------------------------------------------------------------------
# Bet flow (shared by the starter and joiners)
# ---------------------------------------------------------------------------

class RaceBetView(discord.ui.View):
    """Bet type -> horse -> amount -> confirm.

    mode "start": horse_ids is the drawn field; confirming starts the race (solo
    odds shown from the house line). mode "join": race is the open race.
    """

    def __init__(
        self,
        cog: MixinMeta,
        member: discord.Member,
        conf: GuildSettings,
        user: User,
        mode: str,
        horse_ids: list[str],
        race: HorseRace | None = None,
        home: HorseRacingView | None = None,
    ) -> None:
        super().__init__(timeout=300)
        self._cog = cog
        self._member = member
        self._conf = conf
        self._user = user
        self._mode = mode
        self._horse_ids = horse_ids
        self._race = race
        self._home = home  # set when the flow runs in place on the game screen
        self._bet_type: str | None = None
        self._horse_id: str | None = None
        self._amount: int | None = None
        self._line: list[float | None] | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._member.id:
            await not_your_session(interaction, "bet slip")
            return False
        return True

    async def on_timeout(self) -> None:
        await expire_view(self)

    # -- step 1: bet type ---------------------------------------------------

    def type_embed(self) -> discord.Embed:
        e = discord.Embed(title="🏇 Choose Your Bet", color=PALETTE_GOLD)
        win_min, win_max = get_bet_limits(self._conf, "horserace_win", self._user.rank)
        pl_min, pl_max = get_bet_limits(self._conf, "horserace_place", self._user.rank)
        e.description = (
            f"**🥇 Win:** your horse must finish 1st. Bet {win_min:,}–{win_max:,}.\n"
            f"**🥈 Place:** your horse must finish **1st or 2nd**. Bet {pl_min:,}–{pl_max:,}.\n\n"
            "One bet per race, and it can't be changed once confirmed."
        )
        return e

    def show_type_buttons(self) -> None:
        self.clear_items()
        for bet_type in hr.BET_TYPES:
            btn = discord.ui.Button(label=_BET_LABEL[bet_type], style=discord.ButtonStyle.green, row=0)
            btn.callback = self._make_type_cb(bet_type)
            self.add_item(btn)
        self._add_exit_button(row=1)

    def _make_type_cb(self, bet_type: str):
        async def cb(interaction: discord.Interaction) -> None:
            self._bet_type = bet_type
            self._horse_id = None
            await safe_defer(interaction)
            await self._show_horses(interaction)
        return cb

    # -- step 2: horse ------------------------------------------------------

    async def _show_horses(self, interaction: discord.Interaction) -> None:
        if self._mode == "start":
            self._line = await self._cog.hr_house_line(self._conf, self._horse_ids, self._bet_type)
        self.clear_items()
        options = []
        no_odds = []
        backed: dict[str, int] = {}
        if self._race is not None:
            for bet in self._race.bets:
                if bet.bet_type == self._bet_type:
                    backed[bet.horse_id] = backed.get(bet.horse_id, 0) + bet.amount
        for i, hid in enumerate(self._horse_ids):
            horse = self._conf.horses.get(hid)
            if horse is None:
                continue
            label = horse.name
            if self._line is not None:
                mult = self._line[i]
                if mult is None:
                    no_odds.append(horse.name)
                    continue
                label = f"{horse.name}  ×{mult:.2f}"
            desc = f"{_stats_line(horse)} · Form {_form(horse)}"
            if backed.get(hid):
                desc += f" · {backed[hid]:,} on it"
            options.append(discord.SelectOption(label=label[:100], value=hid, description=desc[:100],
                                                default=hid == self._horse_id))
        if options:
            select = discord.ui.Select(placeholder="Pick your horse", options=options, row=0)
            select.callback = self._on_horse
            self.add_item(select)
        back = discord.ui.Button(label="← Bet Type", style=discord.ButtonStyle.grey, row=1)
        back.callback = self._back_to_type
        self.add_item(back)
        self._add_exit_button(row=1)

        e = discord.Embed(title=f"{_BET_LABEL[self._bet_type]}: Pick a Horse", color=PALETTE_GOLD)
        if self._bet_type == "place":
            e.description = _PLACE_RULE + "\n\n"
        else:
            e.description = "Win pays if your horse finishes **1st**.\n\n"
        if self._line is not None:
            e.description += (
                "**Solo odds (house line):** the number after each horse is what a winning bet "
                "multiplies by if nobody joins. If anyone joins, the race pays from the pools instead."
            )
            if no_odds:
                e.description += f"\n**No odds:** {', '.join(no_odds)} (too likely to finish there)."
            if not options:
                e.description += "\n\nThe house has no odds on any horse for this bet type. Try the other bet type."
        else:
            e.description += "\n".join(_pool_lines(self._conf, self._race, await self._currency()))
        await safe_edit_original_response(interaction, embed=e, view=self)

    async def _on_horse(self, interaction: discord.Interaction) -> None:
        self._horse_id = interaction.data["values"][0]  # type: ignore[index]
        min_bet, max_bet = get_bet_limits(self._conf, f"horserace_{self._bet_type}", self._user.rank)
        await interaction.response.send_modal(_AmountModal(self, min_bet, max_bet))

    async def _back_to_type(self, interaction: discord.Interaction) -> None:
        self.show_type_buttons()
        await interaction.response.edit_message(embed=self.type_embed(), view=self)

    # -- step 3: confirm ----------------------------------------------------

    async def show_confirm(self, interaction: discord.Interaction, amount: int) -> None:
        self._amount = amount
        min_bet, max_bet = get_bet_limits(self._conf, f"horserace_{self._bet_type}", self._user.rank)
        balance = await get_balance(self._member, self._conf, self._user)
        if not min_bet <= amount <= max_bet:
            await interaction.followup.send(f"Your bet must be between {min_bet:,} and {max_bet:,}.", ephemeral=True)
            return
        if amount > balance:
            await interaction.followup.send("You don't have enough to cover that bet.", ephemeral=True)
            return
        currency = await self._currency()
        name = _name(self._conf, self._horse_id)
        e = discord.Embed(title="🏇 Confirm Your Bet", color=PALETTE_GOLD)
        e.description = f"**{_BET_LABEL[self._bet_type]}** on **{name}** for **{amount:,} {currency}**.\n"
        if self._bet_type == "place":
            e.description += _PLACE_RULE + "\n"
        if self._mode == "start" and self._line is not None:
            mult = self._line[self._horse_ids.index(self._horse_id)] or 0
            e.description += (
                f"\nPays **×{mult:.2f}** (**{int(amount * mult):,} {currency}**) if it comes in "
                "(house line: solo race). If anyone joins, it pays from the pools instead.\n"
                f"\nConfirming starts the race and opens betting in <#{self._conf.race_channel_id}> "
                f"for {self._conf.horserace_countdown_minutes} minutes."
            )
        else:
            e.description += (
                f"\nPaid from the {self._bet_type.title()} pool, shared with other winning tickets "
                f"({self._conf.horserace_house_cut_pct}% house cut). A winning ticket always gets at least its bet back."
            )
        self.clear_items()
        confirm = discord.ui.Button(label="✅ Confirm Bet", style=discord.ButtonStyle.green, row=0)
        confirm.callback = self._on_confirm
        self.add_item(confirm)
        back = discord.ui.Button(label="← Change Horse", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_horses
        self.add_item(back)
        self._add_exit_button(row=1)
        await safe_edit_original_response(interaction, embed=e, view=self)

    async def _back_to_horses(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        await self._show_horses(interaction)

    @one_at_a_time
    async def _on_confirm(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        if await session_expired(self, interaction):
            return
        if self._mode == "start":
            error = await self._cog.hr_start_race(
                self._member, self._conf, self._user, self._horse_ids, self._bet_type, self._horse_id, self._amount
            )
        else:
            error = await self._cog.hr_join_race(
                self._member, self._conf, self._user, self._race, self._bet_type, self._horse_id, self._amount
            )
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return
        race = self._conf.active_race
        currency = await self._currency()
        e = discord.Embed(title="✅ Bet Placed", color=PALETTE_GOLD)
        e.description = (
            f"**{_BET_LABEL[self._bet_type]}** on **{_name(self._conf, self._horse_id)}** "
            f"for **{self._amount:,} {currency}**."
        )
        if race is not None:
            e.description += f"\nThe gates open <t:{_unix(race.starts_at)}:R> in <#{race.channel_id}>."
            if self._mode == "start":
                e.description += "\nYou can cancel from the race announcement while you're the only bettor."
        self.clear_items()
        if self._home is not None:
            back = discord.ui.Button(label="↩ Horse Racing", style=discord.ButtonStyle.grey, row=0)
            back.callback = self._go_home
            self.add_item(back)
        else:
            self.stop()
        await safe_edit_original_response(interaction, embed=e, view=self)

    # -- shared -------------------------------------------------------------

    def _add_exit_button(self, row: int) -> None:
        label = "✕ Cancel" if self._home is None else "↩ Horse Racing"
        btn = discord.ui.Button(label=label, style=discord.ButtonStyle.grey, row=row)
        btn.callback = self._go_home if self._home is not None else self._close
        self.add_item(btn)

    async def _close(self, interaction: discord.Interaction) -> None:
        self.stop()
        self.clear_items()
        await interaction.response.edit_message(content="Bet cancelled. Nothing was taken.", embed=None, view=None)

    async def _go_home(self, interaction: discord.Interaction) -> None:
        self.stop()
        home = HorseRacingView(interaction, self._conf, self._user, self._cog)
        await interaction.response.edit_message(embed=home._build_embed(), view=home)

    async def _currency(self) -> str:
        mode = self._race.payment_mode if self._race is not None else self._conf.payment_mode
        return await self._cog.hr_currency(self._member.guild, mode)


# ---------------------------------------------------------------------------
# Game screen (from the Game Room)
# ---------------------------------------------------------------------------

class HorseRacingView(discord.ui.View):
    """Horse Racing screen. Constructor signature matches _launch_game: (interaction, conf, user, cog)."""

    def __init__(
        self,
        interaction: discord.Interaction,
        conf: GuildSettings,
        user: User,
        cog: MixinMeta,
    ) -> None:
        super().__init__(timeout=300)
        self._member: discord.Member = interaction.user  # type: ignore[assignment]
        self._conf = conf
        self._user = user
        self._cog = cog
        self._cached_balance: int | None = user.chip_balance if conf.payment_mode == "chips" else None
        self._cached_currency: str = "chips" if conf.payment_mode == "chips" else ""
        self._field: list[str] | None = None
        if conf.active_race is None:
            try:
                self._field = cog.hr_draw_field(conf)
            except ValueError:
                self._field = None
        self._add_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._member.id:
            await not_your_session(interaction)
            return False
        return True

    async def on_timeout(self) -> None:
        await expire_view(self)

    def _cooldown(self):
        from ..tasks.horse_races import cooldown_left  # noqa: PLC0415

        return cooldown_left(self._conf, self._user)

    def _add_buttons(self) -> None:
        self.clear_items()
        race = self._conf.active_race
        if race is None:
            start = discord.ui.Button(
                label="🏁 Start a Race",
                style=discord.ButtonStyle.green,
                disabled=self._field is None or self._cooldown() is not None,
                row=0,
            )
            start.callback = self._on_start
            self.add_item(start)
        else:
            already = any(b.user_id == self._member.id for b in race.bets)
            join = discord.ui.Button(
                label="📣 Join the Race",
                style=discord.ButtonStyle.green,
                disabled=already or race.phase != "betting",
                row=0,
            )
            join.callback = self._on_join
            self.add_item(join)
        stable = discord.ui.Button(label="🐎 Stable", style=discord.ButtonStyle.blurple, row=0)
        stable.callback = self._show_stable
        self.add_item(stable)
        info = discord.ui.Button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1)
        info.callback = self._show_info
        self.add_item(info)
        if self._member.id in self._conf.race_notify_ids:
            notify = discord.ui.Button(label="🔕 Disable Race Notifications", style=discord.ButtonStyle.red, row=1)
        else:
            notify = discord.ui.Button(label="🔔 Enable Race Notifications", style=discord.ButtonStyle.green, row=1)
        notify.callback = self._toggle_notify
        self.add_item(notify)
        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=1)
        back.callback = self._back_to_floor
        self.add_item(back)

    def _build_embed(self) -> discord.Embed:
        conf = self._conf
        race = conf.active_race
        e = discord.Embed(title="🏇 High Roller: Horse Racing", color=PALETTE_GOLD)
        if race is not None:
            mine = next((b for b in race.bets if b.user_id == self._member.id), None)
            link = (
                f"https://discord.com/channels/{self._member.guild.id}/{race.channel_id}/{race.message_id}"
                if race.message_id else f"<#{race.channel_id}>"
            )
            if race.phase == "betting":
                e.description = (
                    f"**A race is open for betting.** The gates open <t:{_unix(race.starts_at)}:R>.\n"
                    f"Announcement: {link}\n\n{_PLACE_RULE}\n"
                    f"**Bettors:** {len(race.bets)}"
                )
            else:
                e.description = f"**A race is running now** in <#{race.channel_id}>. Results are on the way!"
            if mine is not None:
                e.description += (
                    f"\n\nYour bet: **{_BET_LABEL[mine.bet_type]}** on **{_name(conf, mine.horse_id)}** "
                    f"for **{mine.amount:,}**."
                )
        elif self._field is None:
            e.description = f"The stable needs at least {hr.FIELD_SIZE} horses to race. Ask an admin."
        else:
            runners = "\n".join(
                f"`{i:>2}` {_name(conf, hid)} · Rating {hr.rating(conf.horses[hid])}"
                for i, hid in enumerate(self._field, 1)
            )
            e.description = (
                "**Start a Race?** These ten horses are drawn for the next race.\n"
                f"Place the first bet to open betting in <#{conf.race_channel_id}> for "
                f"**{conf.horserace_countdown_minutes} minutes**.\n\n{runners}"
            )
            left = self._cooldown()
            if left is not None:
                minutes = int(left.total_seconds() // 60) + 1
                e.description += f"\n\n⏳ You can start another race in **{minutes} min**. You can still join others' races."
        if url := embed_image("horserace"):
            e.set_thumbnail(url=url)
        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")
        return e

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if await session_expired(self, interaction):
            return False
        conf = self._conf
        if not await channel_allowed(interaction.client, conf, interaction.user, interaction.channel_id):
            await interaction.response.send_message(
                "Horse Racing can only be played in the designated casino channel(s).", ephemeral=True
            )
            return False
        if not conf.games_enabled.get("horserace", False) or not conf.race_channel_id:
            await interaction.response.send_message("Horse Racing is not open on this server.", ephemeral=True)
            return False
        if is_blacklisted(conf, self._member.id):
            await interaction.response.send_message("You can't use the club right now.", ephemeral=True)
            return False
        return True

    async def _on_start(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        if self._conf.active_race is not None:
            await interaction.response.send_message("A race has just been started. Join it instead!", ephemeral=True)
            return
        if self._cooldown() is not None:
            await interaction.response.send_message("You can't start another race yet.", ephemeral=True)
            return
        self.stop()
        flow = RaceBetView(self._cog, self._member, self._conf, self._user, "start", list(self._field), home=self)
        flow.show_type_buttons()
        await interaction.response.edit_message(embed=flow.type_embed(), view=flow)

    async def _on_join(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        race = self._conf.active_race
        if race is None or race.phase != "betting":
            await interaction.response.send_message("Betting has closed for this race.", ephemeral=True)
            return
        if any(b.user_id == self._member.id for b in race.bets):
            await interaction.response.send_message("You already have a bet on this race.", ephemeral=True)
            return
        self.stop()
        flow = RaceBetView(
            self._cog, self._member, self._conf, self._user, "join", list(race.horse_ids), race=race, home=self
        )
        flow.show_type_buttons()
        await interaction.response.edit_message(embed=flow.type_embed(), view=flow)

    async def _toggle_notify(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        subscribers = self._conf.race_notify_ids
        if self._member.id in subscribers:
            subscribers.remove(self._member.id)
            note = "🔕 You won't be pinged when a race opens anymore."
        else:
            subscribers.append(self._member.id)
            note = (
                f"🔔 You'll be pinged in <#{self._conf.race_channel_id}> when a race opens for betting, "
                "except races you start yourself."
            )
        self._cog.save()
        self._add_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)
        try:
            await interaction.followup.send(note, ephemeral=True)
        except discord.HTTPException as exc:
            log.warning("Horse Racing: couldn't confirm a notification toggle", exc_info=exc)

    async def _show_stable(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=stable_embed(self._conf), ephemeral=True)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=how_to_play_embed(self._conf), ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        self.stop()
        await safe_defer(interaction)
        balance = await get_balance(self._member, self._conf, self._user)
        if self._conf.payment_mode == "chips":
            currency_name = "chips"
        else:
            currency_name = await bank.get_currency_name(self._member.guild)
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)


# ---------------------------------------------------------------------------
# Public announcement (race channel)
# ---------------------------------------------------------------------------

class RaceAnnouncementView(discord.ui.View):
    """Join / Cancel buttons on the race announcement. The race runner closes it."""

    def __init__(self, cog: MixinMeta, guild_id: int, race: HorseRace) -> None:
        seconds = max(60.0, (race.starts_at - datetime.now(timezone.utc)).total_seconds())
        super().__init__(timeout=seconds + 300)
        self._cog = cog
        self._guild_id = guild_id
        self._race = race
        self.message: discord.Message | None = None

    def _conf(self) -> GuildSettings:
        return self._cog.db.get_conf(self._guild_id)

    @discord.ui.button(label="🏇 Join the Race", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        conf = self._conf()
        race = conf.active_race
        if race is not self._race or race.phase != "betting" or datetime.now(timezone.utc) >= race.starts_at:
            await interaction.response.send_message("Betting has closed for this race.", ephemeral=True)
            return
        if not conf.games_enabled.get("horserace", False):
            await interaction.response.send_message("Horse Racing is not open on this server.", ephemeral=True)
            return
        if interaction.user.bot or is_blacklisted(conf, interaction.user.id):
            await interaction.response.send_message("You can't use the club right now.", ephemeral=True)
            return
        if any(b.user_id == interaction.user.id for b in race.bets):
            await interaction.response.send_message("You already have a bet on this race.", ephemeral=True)
            return
        user = conf.get_user(interaction.user.id)
        flow = RaceBetView(self._cog, interaction.user, conf, user, "join", list(race.horse_ids), race=race)  # type: ignore[arg-type]
        flow.show_type_buttons()
        await interaction.response.send_message(embed=flow.type_embed(), view=flow, ephemeral=True)

    @discord.ui.button(label="❌ Cancel Race", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        conf = self._conf()
        if interaction.user.id != self._race.starter_id:
            await interaction.response.send_message("Only the player who started the race can cancel it.", ephemeral=True)
            return
        await safe_defer(interaction, ephemeral=True, thinking=True)
        message = await self._cog.hr_cancel_by_starter(interaction.guild, conf, interaction.user.id)
        await interaction.followup.send(message, ephemeral=True)

    @discord.ui.button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey)
    async def info(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.send_message(embed=how_to_play_embed(self._conf()), ephemeral=True)
