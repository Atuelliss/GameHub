"""DoubleView -- Discord UI for the Double press-your-luck dice game in HighRollerClub.

Game flow
---------
Phase 1 (idle)    : Player sees the bet prompt with active Lucky Streak indicator.
                    Buttons: Roll the Dice | Back to Floor | How to Play

Phase 2 (active)  : First roll succeeded -- pot is shown. Player decides.
                    Buttons: Cash Out ({pot}) | Double Again

                    Each subsequent Double Again that wins refreshes this phase
                    with the updated pot.  A failed roll goes straight to loss result.

Phase 3 (result)  : Game over (cash-out or bust).
                    Buttons: Change Bet | Roll (last bet) | Back to Floor

Access guard
------------
_check_access() is called at the top of every action button callback before any
game logic runs.  It checks:
  1. is_allowed_channel(conf, interaction.channel_id)
  2. conf.games_enabled.get("double", True)
Callers return immediately if _check_access returns False.

Multiplier / token eligibility
-------------------------------
Double is NOT in MULTIPLIER_ELIGIBLE_GAMES -- the guard below is explicit so
the check is visible in code and will automatically activate if the constant
ever changes.  consume_multiplier() is never called for this game.

Double is NOT in BONUS_BET_TOKEN_ELIGIBLE_GAMES.  consume_bonus_bet_token()
is called per checklist (it returns False safely and consumes nothing).
self._token_active is always False as a result.

Lucky Streak applies normally on cash-out.  On any loss or bust, the streak
is cancelled and the player is notified via the result embed.

Multiplier rule (user-specified, cash-out path only)
----------------------------------------------------
If Double were eligible for the Multiplier Wheel, the multiplier would apply
only to the NET PROFIT on a depth-1 cash-out, and to the FULL POT on a
depth-2+ cash-out.  Since Double is currently excluded, this logic is present
as a guard-only block and never executes.

Bonus stacking order (cash-out win)
------------------------------------
  1. raw_payout = current pot (bet * 2^depth)
  2. If Lucky Streak active: bonus = apply_lucky_streak_bonus(raw_payout)
     total_payout = raw_payout + bonus
  3. Multiplier Wheel guard: "double" not in MULTIPLIER_ELIGIBLE_GAMES -- skipped.
  4. Bonus Bet Token: consume_bonus_bet_token returns False for "double" -- skipped.

Pure game logic lives in games/double.py.
"""

from __future__ import annotations

import random

import aiohttp
import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.constants import (
    BONUS_BET_TOKEN_ELIGIBLE_GAMES,
    MULTIPLIER_ELIGIBLE_GAMES,
    PALETTE_GOLD,
    RANK_NAMES,
    SPECIALTY_TITLES,
    embed_image,
)
from ..common.interactions import safe_defer, safe_edit_original_response, safe_response_edit_message
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    apply_lucky_streak_bonus,
    apply_rank_change,
    cancel_lucky_streak,
    consume_bonus_bet_token,
    consume_multiplier,
    credit_balance,
    deduct_balance,
    evaluate_rank,
    evaluate_specialty_titles,
    get_balance,
    get_bet_limits,
    get_game_rng,
    get_pending_multiplier,
    has_bonus_bet_token,
    has_lucky_streak,
    is_allowed_channel,
    record_loss,
    record_win,
    validate_bet,
)
from ..games.double import calculate_pot, flip

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_CASHOUT_FLAVOR: list[str] = [
    "Discipline meets fortune -- a rare combination.",
    "You walked away clean. The house respects that.",
    "Knowing when to stop is the mark of a true player.",
    "Chips secured. Well played.",
    "The smart money cashes out. You are the smart money.",
    "A measured exit from a winning position.",
    "The house watched you leave with its chips. It will remember.",
]

_LOSS_FLAVOR: list[str] = [
    "The dice had other plans.",
    "A bold run, ended by fate.",
    "Not every roll goes your way.",
    "High risk, hard lesson.",
    "The dice remember no debts.",
    "The house takes the pot. The Club endures.",
    "Fortune built it up -- and took it back.",
]

_FIRST_LOSS_FLAVOR: list[str] = [
    "The very first roll turned against you.",
    "No run today -- the dice were cold from the start.",
    "A rough start. The table will be here when you're ready.",
    "The Club has seen this before. It will not be the last time.",
]


# ---------------------------------------------------------------------------
# Bet modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Place Your Bet -- Double"):
    def __init__(self, view: "DoubleView", min_bet: int, max_bet: int) -> None:
        super().__init__()
        self._view = view
        self.bet_input = discord.ui.TextInput(
            label=f"Bet Amount (min {min_bet:,} · max {max_bet:,})",
            placeholder=f"Enter a value between {min_bet:,} and {max_bet:,}",
            min_length=1,
            max_length=10,
        )
        self.add_item(self.bet_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        raw = self.bet_input.value.strip().replace(",", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.followup.send(
                "Please enter a valid positive whole number.", ephemeral=True
            )
            return
        await self._view._start_game(interaction, int(raw))


# ---------------------------------------------------------------------------
# Main Double View
# ---------------------------------------------------------------------------

class DoubleView(discord.ui.View):
    """Discord UI view for the Double press-your-luck dice game.

    Constructor signature: (interaction, conf, user, cog)
    This matches the protocol expected by _launch_game in user_commands.py.
    """

    def __init__(
        self,
        interaction: discord.Interaction,
        conf: GuildSettings,
        user: User,
        cog: MixinMeta,
    ) -> None:
        super().__init__(timeout=120)
        self._member: discord.Member = interaction.user  # type: ignore[assignment]
        self._conf = conf
        self._user = user
        self._cog = cog
        self._message: discord.Message | None = interaction.message

        # Balance cache -- refreshed after each resolve so _build_embed stays sync.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Last validated bet -- enables the "Roll Same Bet" shortcut button.
        self._last_bet: int | None = None

        # Active hand state -- reset at the start of each hand.
        self._bet: int = 0          # initial bet for this hand (deducted at game start)
        self._depth: int = 0        # number of consecutive successful rolls this hand
        self._pot: int = 0          # current pot = bet * 2^depth (never credited until cash-out)
        self._token_active: bool = False  # always False for double; tracked for checklist

        self._add_idle_buttons()

    # ------------------------------------------------------------------
    # Interaction guard
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.message is not None:
            self._message = interaction.message
        if interaction.user.id != self._member.id:
            await interaction.response.send_message(
                "This isn't your game session. Run `[p]highrollerclub` to start your own.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        self.clear_items()
        if self._message is None:
            return
        try:
            await self._message.edit(view=None)
        except (discord.NotFound, aiohttp.ClientOSError, OSError, discord.HTTPException):
            return

    # ------------------------------------------------------------------
    # Button layouts
    # ------------------------------------------------------------------

    def _add_idle_buttons(self) -> None:
        self.clear_items()

        roll = discord.ui.Button(
            label="🎲 Roll the Dice", style=discord.ButtonStyle.green, row=0
        )
        roll.callback = self._on_roll
        self.add_item(roll)

        back = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    def _add_active_buttons(self) -> None:
        self.clear_items()

        cashout = discord.ui.Button(
            label=f"💰 Cash Out ({self._pot:,})",
            style=discord.ButtonStyle.green,
            row=0,
        )
        cashout.callback = self._on_cashout
        self.add_item(cashout)

        again = discord.ui.Button(
            label="🎲 Double Again",
            style=discord.ButtonStyle.blurple,
            row=0,
        )
        again.callback = self._on_double_again
        self.add_item(again)

    def _add_result_buttons(self) -> None:
        self.clear_items()

        change = discord.ui.Button(
            label="🎲 Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._play_again
        self.add_item(change)

        if self._last_bet is not None:
            same = discord.ui.Button(
                label=f"🎲 Roll ({self._last_bet:,})",
                style=discord.ButtonStyle.green,
                row=0,
            )
            same.callback = self._deal_same_bet
            self.add_item(same)

        back = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    # ------------------------------------------------------------------
    # Access guard
    # ------------------------------------------------------------------

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        """Returns True if the player may act.  Sends an ephemeral error and
        returns False if the channel is restricted or the game is disabled.
        Callers must return immediately when this returns False.
        """
        conf = self._conf

        if not is_allowed_channel(conf, interaction.channel_id):
            await interaction.response.send_message(
                "Double can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not conf.games_enabled.get("double", True):
            await interaction.response.send_message(
                "Double is currently disabled on this server.",
                ephemeral=True,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Button callbacks -- idle phase
    # ------------------------------------------------------------------

    async def _on_roll(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "double", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _deal_same_bet(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._start_game(interaction, self._last_bet)

    async def _play_again(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        self._add_idle_buttons()
        await safe_response_edit_message(interaction, embed=self._build_idle_embed(), view=self)

    # ------------------------------------------------------------------
    # Button callbacks -- active (in-progress) phase
    # ------------------------------------------------------------------

    async def _on_cashout(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._resolve_cashout(interaction)

    async def _on_double_again(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._do_roll(interaction)

    # ------------------------------------------------------------------
    # Game start -- validate bet, consume token (no-op), deduct, first roll
    # ------------------------------------------------------------------

    async def _start_game(self, interaction: discord.Interaction, bet: int) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user

        # Validate bet against current balance.
        balance = await get_balance(member, conf, user)
        error = validate_bet(conf, user, "double", bet, balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        self._last_bet = bet
        self._bet = bet
        self._depth = 0
        self._pot = 0

        # Bonus Bet Token -- Double is NOT in BONUS_BET_TOKEN_ELIGIBLE_GAMES.
        # consume_bonus_bet_token returns False safely and consumes nothing.
        # Called per the per-game checklist so the guard is always present.
        self._token_active = False
        if has_bonus_bet_token(user):
            self._token_active = consume_bonus_bet_token(user, "double")
        # self._token_active is always False for "double".

        # Deduct the initial bet before the first roll.
        await deduct_balance(member, conf, user, bet)

        # Refresh cached balance so the idle embed footer stays accurate.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # Run the first roll.
        await self._do_roll(interaction)

    # ------------------------------------------------------------------
    # Roll logic -- shared by _start_game (first roll) and _on_double_again
    # ------------------------------------------------------------------

    async def _do_roll(self, interaction: discord.Interaction) -> None:
        """Execute one roll.  Fetches win_chance at call time via get_game_rng
        so admin overrides in conf.game_rng_settings are always respected.
        """
        conf = self._conf
        user = self._user

        win_chance: float = get_game_rng(conf, "double", "win_chance")
        won = flip(win_chance)

        if won:
            self._depth += 1
            self._pot = calculate_pot(self._bet, self._depth)
            self._add_active_buttons()
            await safe_edit_original_response(interaction, embed=self._build_active_embed(), view=self)
        else:
            await self._resolve_loss(interaction)

    # ------------------------------------------------------------------
    # Cash-out resolution
    # ------------------------------------------------------------------

    async def _resolve_cashout(self, interaction: discord.Interaction) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        bet    = self._bet
        pot    = self._pot
        depth  = self._depth

        # 1. Base payout is the current pot.
        raw_payout   = pot
        total_payout = raw_payout

        # 2. Lucky Streak bonus (+25% of raw_payout).
        streak_cancelled = False
        if has_lucky_streak(user):
            total_payout += apply_lucky_streak_bonus(raw_payout)
        # Streak remains active on a win -- only cancel on loss.

        # 3. Multiplier Wheel -- Double is NOT in MULTIPLIER_ELIGIBLE_GAMES.
        # Guard is explicit so activation is automatic if the constant changes.
        if "double" in MULTIPLIER_ELIGIBLE_GAMES:
            multiplier = consume_multiplier(user)
            if multiplier is not None:
                profit = total_payout - bet
                total_payout += int(profit * (multiplier - 1.0))

        # 4. Bonus Bet Token -- self._token_active is always False for "double".
        if self._token_active:
            total_payout *= 2

        # Credit winnings and record stats.
        await credit_balance(member, conf, user, total_payout)
        record_win(conf, user, "double", total_payout, bet)

        new_rank     = evaluate_rank(conf, user)
        rank_changed = new_rank != user.rank
        old_rank     = user.rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        self._cog.save()

        # Refresh cached balance for the result embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        result_data = {
            "outcome":        "cashout",
            "bet":            bet,
            "depth":          depth,
            "pot":            pot,
            "payout":         total_payout,
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank if rank_changed else old_rank,
            "new_titles":     new_titles,
        }

        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(result_data), view=self)

    # ------------------------------------------------------------------
    # Loss resolution
    # ------------------------------------------------------------------

    async def _resolve_loss(self, interaction: discord.Interaction) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        bet    = self._bet
        depth  = self._depth

        # Cancel Lucky Streak on loss and notify player via result embed.
        streak_cancelled = False
        if has_lucky_streak(user):
            cancel_lucky_streak(user)
            streak_cancelled = True

        # amount_lost is the original bet: the only amount actually deducted
        # from the player's balance.  The pot was never credited.
        record_loss(conf, user, "double", bet)

        new_rank     = evaluate_rank(conf, user)
        rank_changed = new_rank != user.rank
        old_rank     = user.rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        self._cog.save()

        # Refresh cached balance for the result embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        result_data = {
            "outcome":        "loss",
            "bet":            bet,
            "depth":          depth,
            "pot":            self._pot,  # pot at the time of failure (0 if first roll)
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank if rank_changed else old_rank,
            "new_titles":     new_titles,
        }

        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(result_data), view=self)

    # ------------------------------------------------------------------
    # How to Play
    # ------------------------------------------------------------------

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🎲 How to Play -- Double", color=PALETTE_GOLD)
        e.description = (
            "Place a bet and roll the dice. A win doubles your current pot. "
            "A loss ends the game and forfeits your entire bet.\n\n"
            "After each successful roll you choose:\n"
            "**Cash Out** -- claim the current pot\n"
            "**Double Again** -- roll again; success doubles the pot, "
            "failure loses everything."
        )

        e.add_field(
            name="Pot Growth (example: 200 chip bet)",
            value=(
                "```\n"
                "Roll 1 win  :   400\n"
                "Roll 2 win  :   800\n"
                "Roll 3 win  : 1,600\n"
                "Roll 4 win  : 3,200\n"
                "Roll 5 win  : 6,400\n"
                "Any loss    :     0  (entire bet forfeited)\n"
                "```"
            ),
            inline=False,
        )

        e.add_field(
            name="Bonuses",
            value=(
                "• **Lucky Streak** -- adds 25% to pot on cash-out; cancelled on any loss\n"
                "• Multiplier Wheel and Bonus Bet Tokens do not apply to Double."
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    # ------------------------------------------------------------------
    # Back to floor
    # ------------------------------------------------------------------

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        # Lazy import avoids a circular dependency at module load time.
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        await safe_defer(interaction)
        balance = await get_balance(self._member, self._conf, self._user)
        if self._conf.payment_mode == "chips":
            currency_name = "chips"
        else:
            currency_name = await bank.get_currency_name(self._member.guild)
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    # ------------------------------------------------------------------
    # Embed builders
    # ------------------------------------------------------------------

    def _build_idle_embed(self) -> discord.Embed:
        """Idle-state embed shown before the player places a bet."""
        user = self._user
        e    = discord.Embed(title="🎲 High Roller -- Double", color=PALETTE_GOLD)

        desc = (
            "**Roll the dice. Double the pot. Walk away -- or go again.**\n\n"
            "Place your bet and hit **Roll the Dice** to start.\n"
            "Each successful roll doubles your pot. Cash Out any time to claim your winnings. "
            "One failed roll loses everything."
        )

        if has_lucky_streak(user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak adds +25% if it is still active when you cash out."

        # Multiplier Wheel and Bonus Bet Token do not apply to Double; no indicators shown.

        e.description = desc

        if url := embed_image("double"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the GameRoom 'Back' flow."""
        return self._build_idle_embed()

    def _build_active_embed(self) -> discord.Embed:
        """Active-phase embed: pot shown, Cash Out vs Double Again decision."""
        cur   = self._cached_currency
        pot   = self._pot
        bet   = self._bet
        depth = self._depth
        next_pot = pot * 2

        roll_word = "roll" if depth == 1 else "rolls"

        desc = (
            f"✅ **Roll {depth} -- Success!**\n\n"
            f"**Current pot: {pot:,} {cur}** after {depth} consecutive {roll_word}.\n\n"
            f"**Cash Out** now and claim **{pot:,} {cur}**\n"
            f"**Double Again** and try for **{next_pot:,} {cur}**\n\n"
            f"⚠️ A failed roll loses the entire **{pot:,} {cur}** pot."
        )

        e = discord.Embed(title="🎲 High Roller -- Double", color=PALETTE_GOLD)

        # Active bonus indicators (only Lucky Streak applies to Double).
        bonuses: list[str] = []
        if has_lucky_streak(self._user):
            bonuses.append("🔥 Snapshot: Lucky Streak adds +25% if it is still active when you cash out")
        if bonuses:
            desc += "\n\n" + "\n".join(bonuses)

        e.description = desc

        if url := embed_image("double"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_result_embed(self, result: dict) -> discord.Embed:
        """Result-state embed for cash-out win or bust."""
        e       = discord.Embed(title="🎲 High Roller -- Double", color=PALETTE_GOLD)
        outcome = result["outcome"]
        bet     = result["bet"]
        depth   = result["depth"]
        cur     = self._cached_currency

        if outcome == "cashout":
            payout    = result["payout"]
            pot       = result["pot"]
            roll_word = "roll" if depth == 1 else "rolls"
            net       = payout - bet
            desc = (
                f"**💰 Cashed Out!**\n"
                f"{depth} consecutive {roll_word} -- pot: **{pot:,}** {cur}\n"
                f"Bet: **{bet:,}** {cur} → Payout: **{payout:,}** {cur} "
                f"(net: **+{net:,}** {cur})\n"
                f"*{random.choice(_CASHOUT_FLAVOR)}*"
            )
        else:
            # Loss
            if depth == 0:
                # Failed on the very first roll.
                desc = (
                    f"**❌ Bust -- Roll 1 Failed.**\n"
                    f"Bet of **{bet:,}** {cur} lost on the first roll.\n"
                    f"*{random.choice(_FIRST_LOSS_FLAVOR)}*"
                )
            else:
                pot       = result["pot"]
                roll_word = "rolls" if depth != 1 else "roll"
                desc = (
                    f"**❌ Bust!**\n"
                    f"After {depth} successful {roll_word} (pot: **{pot:,}** {cur}), "
                    f"the next roll failed.\n"
                    f"Bet of **{bet:,}** {cur} lost.\n"
                    f"*{random.choice(_LOSS_FLAVOR)}*"
                )

        if result.get("streak_cancelled"):
            desc += "\n💔 **Your lucky streak has ended.**"

        if result.get("rank_changed"):
            old_name = RANK_NAMES.get(result["old_rank"], "Unknown")
            new_name = RANK_NAMES.get(result["new_rank"], "Unknown")
            if result["new_rank"] > result["old_rank"]:
                desc += f"\n🏆 **Rank Up!** You are now a **{new_name}**!"
            else:
                desc += (
                    f"\n📉 **Rank Down.** "
                    f"**{old_name}** → **{new_name}**."
                )

        for slug in result.get("new_titles", []):
            title_str = SPECIALTY_TITLES.get(slug, slug)
            desc += f"\n🎖️ **New title unlocked:** {title_str}"

        e.description = desc

        if url := embed_image("double"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e
