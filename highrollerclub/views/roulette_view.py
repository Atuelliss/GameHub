"""RouletteView -- Discord UI for the Roulette game in HighRollerClub.

Game flow
---------
Phase 1 (idle)    : Player sees the game prompt with active bonus indicators.
                    Buttons: Play Roulette | Back to Floor | How to Play

Phase 2 (config)  : Player has entered a bet amount via BetModal.
                    Row 0: BetTypeSelect dropdown (17 bet types).
                    Row 4: Spin (disabled until type chosen) | Change Bet | Back to Floor
                    For even-money, dozen, and column bets the target is implied
                    by the dropdown option -- Spin enables immediately.
                    For inside bets (straight, split, street, corner, line) a
                    TargetModal pops up for number entry; Spin enables after submit.

Phase 3 (result)  : Wheel result shown with win/loss details.
                    Buttons: Change Bet | Spin Again (X) | Back to Floor | How to Play

Access guard
------------
_check_access() is called at the top of every action button/select callback
before any game logic runs. It checks:
  1. is_allowed_channel(conf, interaction.channel_id)
  2. conf.games_enabled.get("roulette", True)
Callers return immediately if _check_access returns False.

Bonus stacking order (win only)
---------------------------------
  1. raw_payout = calculate_payout(bet, bet_type)   [includes returned stake]
  2. If Lucky Streak active: bonus = apply_lucky_streak_bonus(raw_payout)
     total_payout = raw_payout + bonus
  3. Multiplier Wheel guard -- "roulette" NOT in MULTIPLIER_ELIGIBLE_GAMES:
     guard evaluates False; consume_multiplier() is never called.
  4. Bonus Bet Token -- "roulette" NOT in BONUS_BET_TOKEN_ELIGIBLE_GAMES:
     consume_bonus_bet_token() returns False without consuming; token safe.

On any loss: cancel_lucky_streak(user) if streak is active; notify player.

Pure game logic lives in games/roulette.py.
"""

from __future__ import annotations

import random

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.constants import (
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
from ..games.roulette import (
    CORNER_STARTS,
    LINE_STARTS,
    PAYOUTS,
    STREET_STARTS,
    calculate_payout,
    evaluate_bet,
    is_valid_split,
    result_color,
    spin,
)

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_FLAVOR: list[str] = [
    "The wheel turned in your favor. A well-placed bet.",
    "Fortune knows its own.",
    "The ball found your number -- and your pocket found the chips.",
    "Calculated. Clean. Correct.",
    "The house pays its debts.",
    "The Club respects a player who knows their bet.",
    "Patience and precision -- the winning combination.",
]

_LOSS_FLAVOR: list[str] = [
    "The wheel has no loyalty. Try again.",
    "The ball had other ideas today.",
    "The house edge claims another spin.",
    "Not your number -- but there's always the next spin.",
    "The wheel turns for everyone eventually.",
    "The Club endures. So do you.",
    "A miss on the board. Better luck next time.",
]


# ---------------------------------------------------------------------------
# Bet type Select component
# ---------------------------------------------------------------------------

class BetTypeSelect(discord.ui.Select):
    """Dropdown presenting all 17 supported roulette bet types.

    For even-money, dozen, and column bets the target is implied by the
    option value -- the view stores the bet type and target immediately and
    enables the Spin button.

    For inside bets (straight, split, street, corner, line) a TargetModal is
    sent so the player can enter the specific number(s) required.
    """

    _EVENMONEY_LABELS: dict[str, str] = {
        "red":   "🔴 Red",
        "black": "⚫ Black",
        "odd":   "Odd",
        "even":  "Even",
        "low":   "Low (1-18)",
        "high":  "High (19-36)",
    }

    def __init__(self, roulette_view: RouletteView) -> None:
        options = [
            discord.SelectOption(label="🔴 Red (1:1)",           value="evenmoney_red"),
            discord.SelectOption(label="⚫ Black (1:1)",          value="evenmoney_black"),
            discord.SelectOption(label="🔢 Odd (1:1)",            value="evenmoney_odd"),
            discord.SelectOption(label="🔢 Even (1:1)",           value="evenmoney_even"),
            discord.SelectOption(label="⬇ Low 1-18 (1:1)",       value="evenmoney_low"),
            discord.SelectOption(label="⬆ High 19-36 (1:1)",     value="evenmoney_high"),
            discord.SelectOption(label="1st Dozen 1-12 (2:1)",    value="dozen_1"),
            discord.SelectOption(label="2nd Dozen 13-24 (2:1)",   value="dozen_2"),
            discord.SelectOption(label="3rd Dozen 25-36 (2:1)",   value="dozen_3"),
            discord.SelectOption(
                label="Column 1 (2:1)", value="col_1",
                description="1  4  7  10  13  16  19  22  25  28  31  34",
            ),
            discord.SelectOption(
                label="Column 2 (2:1)", value="col_2",
                description="2  5  8  11  14  17  20  23  26  29  32  35",
            ),
            discord.SelectOption(
                label="Column 3 (2:1)", value="col_3",
                description="3  6  9  12  15  18  21  24  27  30  33  36",
            ),
            discord.SelectOption(
                label="Straight Up (35:1)", value="straight",
                description="Pick any single number 0-36",
            ),
            discord.SelectOption(
                label="Split (17:1)", value="split",
                description="Pick two horizontally or vertically adjacent numbers",
            ),
            discord.SelectOption(
                label="Street (11:1)", value="street",
                description="Pick a 3-number row (enter row start: 1, 4, 7 ... 34)",
            ),
            discord.SelectOption(
                label="Corner (8:1)", value="corner",
                description="Pick a 4-number 2x2 block (enter top-left number)",
            ),
            discord.SelectOption(
                label="Line (5:1)", value="line",
                description="Pick two adjacent rows of 3 (enter first row start: 1-31)",
            ),
        ]
        super().__init__(
            placeholder="Choose your bet type...",
            min_values=1,
            max_values=1,
            options=options,
            row=0,
        )
        self._rv = roulette_view

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self._rv._check_access(interaction):
            return

        value = self.values[0]

        if value.startswith("evenmoney_"):
            sub = value[len("evenmoney_"):]
            self._rv._bet_type = "evenmoney"
            self._rv._bet_target = sub
            self._rv._bet_label = self._EVENMONEY_LABELS.get(sub, sub)
            self._rv.clear_items()
            self._rv._add_config_components(spin_enabled=True)
            await safe_response_edit_message(interaction, embed=self._rv._build_config_embed(), view=self._rv)

        elif value.startswith("dozen_"):
            n = int(value[-1])
            ranges = {1: "1-12", 2: "13-24", 3: "25-36"}
            self._rv._bet_type = "dozen"
            self._rv._bet_target = n
            self._rv._bet_label = f"Dozen {ranges[n]}"
            self._rv.clear_items()
            self._rv._add_config_components(spin_enabled=True)
            await safe_response_edit_message(interaction, embed=self._rv._build_config_embed(), view=self._rv)

        elif value.startswith("col_"):
            n = int(value[-1])
            self._rv._bet_type = "column"
            self._rv._bet_target = n
            self._rv._bet_label = f"Column {n}"
            self._rv.clear_items()
            self._rv._add_config_components(spin_enabled=True)
            await safe_response_edit_message(interaction, embed=self._rv._build_config_embed(), view=self._rv)

        else:
            # Inside bet -- requires TargetModal for number entry.
            await interaction.response.send_modal(TargetModal(self._rv, value))


# ---------------------------------------------------------------------------
# Modals
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Roulette: Place Your Bet"):
    def __init__(self, view: RouletteView, min_bet: int, max_bet: int) -> None:
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
        await self._view._start_config_phase(interaction, int(raw))


class TargetModal(discord.ui.Modal):
    """Collects the specific number(s) for inside bets.

    Opened automatically after the player selects an inside bet type from
    BetTypeSelect.  On valid submit the view transitions to spin-enabled config.
    """

    _LABELS: dict[str, str] = {
        "straight": "Straight Up -- Enter a number (0-36)",
        "split":    "Split -- Enter two adjacent numbers (e.g. 14,17)",
        "street":   "Street -- Enter row start (1, 4, 7 ... 34)",
        "corner":   "Corner -- Enter top-left number (e.g. 1, 2 ... 33)",
        "line":     "Line -- Enter row start (1, 4, 7 ... 31)",
    }
    _SHORT_TITLES: dict[str, str] = {
        "straight": "Roulette: Straight Up",
        "split": "Roulette: Split",
        "street": "Roulette: Street",
        "corner": "Roulette: Corner",
        "line": "Roulette: Line",
    }
    _SHORT_INPUT_LABELS: dict[str, str] = {
        "straight": "Number",
        "split": "Adjacent Numbers",
        "street": "Row Start",
        "corner": "Top-Left Number",
        "line": "First Row Start",
    }
    _PLACEHOLDERS: dict[str, str] = {
        "straight": "Any single number between 0 and 36",
        "split":    "e.g. 14,17  (must be adjacent on the board)",
        "street":   "e.g. 4  (covers 4, 5, 6)",
        "corner":   "e.g. 1  (covers 1, 2, 4, 5)",
        "line":     "e.g. 1  (covers 1, 2, 3, 4, 5, 6)",
    }

    def __init__(self, view: RouletteView, inside_type: str) -> None:
        super().__init__(title=self._SHORT_TITLES.get(inside_type, "Roulette: Target"))
        self._view = view
        self._inside_type = inside_type
        self.number_input = discord.ui.TextInput(
            label=self._SHORT_INPUT_LABELS.get(inside_type, "Target"),
            placeholder=self._PLACEHOLDERS.get(inside_type, ""),
            min_length=1,
            max_length=12,
        )
        self.add_item(self.number_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        raw = self.number_input.value.strip()
        error, bet_type, target, label = self._parse(raw)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        self._view._bet_type = bet_type
        self._view._bet_target = target
        self._view._bet_label = label
        self._view.clear_items()
        self._view._add_config_components(spin_enabled=True)
        await safe_edit_original_response(interaction, embed=self._view._build_config_embed(), view=self._view)

    def _parse(self, raw: str) -> tuple:
        """Return (error | None, bet_type, target, label)."""
        t = self._inside_type

        if t == "straight":
            if not raw.isdigit():
                return "Enter a valid whole number.", None, None, None
            n = int(raw)
            if not 0 <= n <= 36:
                return "Number must be between 0 and 36.", None, None, None
            return None, "straight", n, f"Straight Up #{n}"

        if t == "split":
            parts = [p.strip() for p in raw.split(",")]
            if len(parts) != 2 or not all(p.isdigit() for p in parts):
                return "Enter exactly two numbers separated by a comma.", None, None, None
            a, b = int(parts[0]), int(parts[1])
            if not is_valid_split(a, b):
                return (
                    f"{a} and {b} are not adjacent on the board. "
                    "Numbers must be horizontally or vertically adjacent.",
                    None, None, None,
                )
            lo, hi = min(a, b), max(a, b)
            return None, "split", (lo, hi), f"Split {lo}/{hi}"

        if t == "street":
            if not raw.isdigit():
                return "Enter the first number of the row.", None, None, None
            n = int(raw)
            if n not in STREET_STARTS:
                return f"{n} is not a valid row start. Use 1, 4, 7, 10 ... 34.", None, None, None
            return None, "street", n, f"Street {n}-{n+2}"

        if t == "corner":
            if not raw.isdigit():
                return "Enter the top-left number of the 2x2 block.", None, None, None
            n = int(raw)
            if n not in CORNER_STARTS:
                return f"{n} is not a valid corner position.", None, None, None
            return None, "corner", n, f"Corner {n}/{n+1}/{n+3}/{n+4}"

        if t == "line":
            if not raw.isdigit():
                return "Enter the first number of the first row.", None, None, None
            n = int(raw)
            if n not in LINE_STARTS:
                return f"{n} is not a valid line start. Use 1, 4, 7 ... 31.", None, None, None
            return None, "line", n, f"Line {n}-{n+5}"

        return "Unknown bet type.", None, None, None


# ---------------------------------------------------------------------------
# Main Roulette View
# ---------------------------------------------------------------------------

class RouletteView(discord.ui.View):
    """Discord UI view for the Roulette game.

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

        # Balance cache -- refreshed after every resolve so embed builders stay sync.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Bet state.
        self._last_bet: int | None = None
        self._bet_type: str | None = None
        # target: int | tuple[int, int] | str depending on bet_type.
        self._bet_target = None
        self._bet_label: str | None = None

        self._add_idle_buttons()

    # ------------------------------------------------------------------
    # Interaction guard
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._member.id:
            await interaction.response.send_message(
                "This isn't your game session. Run `[p]highrollerclub` to start your own.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        self.clear_items()

    # ------------------------------------------------------------------
    # Button layouts
    # ------------------------------------------------------------------

    def _add_idle_buttons(self) -> None:
        play = discord.ui.Button(
            label="🎡 Play Roulette", style=discord.ButtonStyle.green, row=0
        )
        play.callback = self._on_play
        self.add_item(play)

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

    def _add_config_components(self, spin_enabled: bool = False) -> None:
        """Add the BetTypeSelect (row 0) and action buttons (row 4)."""
        self.add_item(BetTypeSelect(self))

        spin = discord.ui.Button(
            label="🎡 Spin",
            style=discord.ButtonStyle.green if spin_enabled else discord.ButtonStyle.grey,
            disabled=not spin_enabled,
            row=4,
        )
        spin.callback = self._on_spin
        self.add_item(spin)

        change = discord.ui.Button(
            label="💰 Change Bet", style=discord.ButtonStyle.blurple, row=4
        )
        change.callback = self._on_change_bet
        self.add_item(change)

        back = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=4
        )
        back.callback = self._back_to_floor
        self.add_item(back)

    def _add_result_buttons(self) -> None:
        change = discord.ui.Button(
            label="💰 Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._on_change_bet
        self.add_item(change)

        if self._last_bet is not None:
            again = discord.ui.Button(
                label=f"🎡 Spin Again ({self._last_bet:,})",
                style=discord.ButtonStyle.green,
                row=0,
            )
            again.callback = self._on_spin_again
            self.add_item(again)

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
        """Returns True if the player may act. Sends an ephemeral error and
        returns False if the channel is restricted or the game is disabled.
        Callers must return immediately when this returns False.
        """
        conf = self._conf

        if not is_allowed_channel(conf, interaction.channel_id):
            await interaction.response.send_message(
                "Roulette can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not conf.games_enabled.get("roulette", True):
            await interaction.response.send_message(
                "Roulette is currently disabled on this server.",
                ephemeral=True,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _on_play(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "roulette", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _on_change_bet(self, interaction: discord.Interaction) -> None:
        """Opens BetModal so the player can enter a new bet amount."""
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "roulette", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _on_spin_again(self, interaction: discord.Interaction) -> None:
        """Result button -- reuse last bet and return to config phase."""
        if not await self._check_access(interaction):
            return
        self._bet_type = None
        self._bet_target = None
        self._bet_label = None
        self.clear_items()
        self._add_config_components(spin_enabled=False)
        await safe_response_edit_message(interaction, embed=self._build_config_embed(), view=self)

    async def _on_spin(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        if self._bet_type is None or self._bet_target is None:
            await interaction.response.send_message(
                "Please select a bet type first.", ephemeral=True
            )
            return
        await safe_defer(interaction)
        await self._resolve(interaction)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🎡 How to Play: Roulette", color=PALETTE_GOLD)
        e.description = (
            "The wheel is spun and a ball lands on a numbered slot. "
            "Place your bet on any of the bet types below before spinning. "
            "Zero slots (0, 00, or 000 depending on wheel type) lose all bets "
            "except a Straight Up bet on 0."
        )

        e.add_field(
            name="Even Money (1:1)",
            value="Red, Black, Odd, Even, Low (1-18), High (19-36)",
            inline=False,
        )
        e.add_field(
            name="Outside Bets (2:1)",
            value="1st Dozen (1-12), 2nd Dozen (13-24), 3rd Dozen (25-36), Column 1/2/3",
            inline=False,
        )
        e.add_field(
            name="Inside Bets",
            value=(
                "```\n"
                "Straight Up   35:1  Any single number 0-36\n"
                "Split         17:1  Two adjacent numbers\n"
                "Street        11:1  Three-number row\n"
                "Corner         8:1  Four-number 2x2 block\n"
                "Line           5:1  Six numbers (two rows)\n"
                "```"
            ),
            inline=False,
        )
        e.add_field(
            name="Bonuses",
            value=(
                "• **Lucky Streak** -- adds 25% to raw payout on any win; "
                "cancelled on any loss\n"
                "• Multiplier Wheel and Bonus Bet Token do not apply to Roulette"
            ),
            inline=False,
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        # Lazy import avoids circular dependency at module load time.
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
    # Config phase entry point (called from BetModal.on_submit)
    # ------------------------------------------------------------------

    async def _start_config_phase(
        self, interaction: discord.Interaction, bet: int
    ) -> None:
        """Validate the bet then show the bet-type selection screen."""
        balance = await get_balance(self._member, self._conf, self._user)
        error = validate_bet(self._conf, self._user, "roulette", bet, balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        self._last_bet = bet
        self._bet_type = None
        self._bet_target = None
        self._bet_label = None
        self.clear_items()
        self._add_config_components(spin_enabled=False)
        await safe_edit_original_response(interaction, embed=self._build_config_embed(), view=self)

    # ------------------------------------------------------------------
    # Embed builders (sync -- use cached balance)
    # ------------------------------------------------------------------

    def _build_idle_embed(self) -> discord.Embed:
        user = self._user
        e = discord.Embed(title="🎡 High Roller: Roulette", color=PALETTE_GOLD)

        desc = (
            "**Place your bet. Spin the wheel. Beat the house.**\n\n"
            "Choose from 17 bet types including even-money, dozens, columns, "
            "and high-risk inside bets paying up to **35:1**.\n\n"
            "Press **Play Roulette** to enter your bet and choose your numbers."
        )

        mul = get_pending_multiplier(user)
        if mul is not None:
            desc += f"\n\n⚡ Bonus snapshot: **{mul}x** multiplier is stored on your account, but Roulette does not use it."
        if has_bonus_bet_token(user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token is stored on your account, but Roulette does not use it."
        if has_lucky_streak(user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak adds +25% if it is still active on your next win."

        e.description = desc

        if url := embed_image("roulette"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the _launch_game protocol."""
        return self._build_idle_embed()

    def _build_config_embed(self) -> discord.Embed:
        e = discord.Embed(title="🎡 High Roller: Roulette", color=PALETTE_GOLD)
        bet = self._last_bet or 0
        cur = self._cached_currency or "chips"

        desc = f"**Bet:** {bet:,} {cur}\n\n"

        if self._bet_type is not None and self._bet_label is not None:
            gross = PAYOUTS.get(self._bet_type, 0)
            net = gross - 1
            desc += (
                f"**Bet Type:** {self._bet_label}\n"
                f"**Pays:** {net}:1 (returns {gross}x your bet on a win)\n\n"
                f"Press **Spin** when ready!"
            )
        else:
            desc += (
                "Select your **bet type** from the dropdown below.\n\n"
                "For inside bets (Straight Up, Split, Street, Corner, Line) "
                "a number entry prompt will appear after selection."
            )

        e.description = desc

        if url := embed_image("roulette"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    def _build_result_embed(self, result: dict) -> discord.Embed:
        e = discord.Embed(title="🎡 High Roller: Roulette", color=PALETTE_GOLD)

        spin_result  = result["spin_result"]
        color        = result_color(spin_result)
        color_emoji  = {"red": "🔴", "black": "⚫", "green": "🟢"}[color]
        color_label  = color.capitalize()
        is_win       = result["is_win"]
        bet          = result["bet"]
        payout       = result["payout"]
        bet_label    = result["bet_label"]
        cur          = self._cached_currency

        spin_line = f"{color_emoji} **{spin_result}** ({color_label})"

        if is_win:
            desc = (
                f"🎡 The wheel lands on: {spin_line}\n\n"
                f"✅ **{bet_label} -- WIN!**\n"
                f"Bet: **{bet:,}** {cur} "
                f"→ Payout: **{payout:,}** {cur} "
                f"*(+{payout - bet:,} profit)*\n"
                f"*{random.choice(_WIN_FLAVOR)}*"
            )
        else:
            desc = (
                f"🎡 The wheel lands on: {spin_line}\n\n"
                f"❌ **{bet_label} -- no win.**\n"
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
                desc += f"\n📉 **Rank Down.** **{old_name}** → **{new_name}**."

        for slug in result.get("new_titles", []):
            title_str = SPECIALTY_TITLES.get(slug, slug)
            desc += f"\n🎖️ **New title unlocked:** {title_str}"

        e.description = desc

        if url := embed_image("roulette"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    # ------------------------------------------------------------------
    # Game resolution
    # ------------------------------------------------------------------

    async def _resolve(self, interaction: discord.Interaction) -> None:
        member    = self._member
        conf      = self._conf
        user      = self._user
        bet       = self._last_bet
        bet_type  = self._bet_type
        bet_target = self._bet_target

        # 1. Bonus Bet Token -- "roulette" NOT in BONUS_BET_TOKEN_ELIGIBLE_GAMES.
        #    consume_bonus_bet_token internally checks eligibility and returns
        #    False without consuming the token on ineligible games.
        token_active = False
        if has_bonus_bet_token(user):
            token_active = consume_bonus_bet_token(user, "roulette")  # always False

        # 2. Deduct balance before the spin.
        await deduct_balance(member, conf, user, bet)

        # 3. Spin -- use admin-configured zero_count.
        zero_count: int = get_game_rng(conf, "roulette", "zero_count")
        spin_result = spin(zero_count)

        # 4. Evaluate the bet.
        is_win = evaluate_bet(spin_result, bet_type, bet_target)

        streak_cancelled = False

        if is_win:
            # ----------------------------------------------------------------
            # Win path
            # ----------------------------------------------------------------
            raw_payout   = calculate_payout(bet, bet_type)
            total_payout = raw_payout

            # Lucky Streak adds 25% of raw payout.
            if has_lucky_streak(user):
                total_payout += apply_lucky_streak_bonus(raw_payout)

            # Multiplier Wheel -- "roulette" is NOT in MULTIPLIER_ELIGIBLE_GAMES.
            # Guard is explicit so activation is automatic if the constant changes.
            if "roulette" in MULTIPLIER_ELIGIBLE_GAMES:
                multiplier = consume_multiplier(user)
                if multiplier is not None:
                    profit = total_payout - bet
                    total_payout += int(profit * (multiplier - 1.0))

            # Bonus Bet Token -- token_active is always False for roulette.
            if token_active:
                total_payout *= 2

            await credit_balance(member, conf, user, total_payout)
            record_win(conf, user, "roulette", total_payout, bet)

        else:
            # ----------------------------------------------------------------
            # Loss path
            # ----------------------------------------------------------------
            total_payout = 0

            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True

            record_loss(conf, user, "roulette", bet)

        # 5. Rank evaluation.
        new_rank     = evaluate_rank(conf, user)
        old_rank     = user.rank
        rank_changed = new_rank != old_rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        # 6. Specialty titles.
        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        # 7. Save.
        self._cog.save()

        # 8. Refresh cached balance for embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # 9. Build result and update message.
        result = {
            "bet":            bet,
            "bet_type":       bet_type,
            "bet_target":     bet_target,
            "bet_label":      self._bet_label,
            "spin_result":    spin_result,
            "is_win":         is_win,
            "payout":         total_payout,
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank,
            "new_titles":     new_titles,
        }

        self.clear_items()
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(result), view=self)
