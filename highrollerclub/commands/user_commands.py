from __future__ import annotations

import importlib
import math

import discord
from redbot.core import bank, commands

from ..abc import MixinMeta
from ..commands.helper_functions import (
    get_balance,
    get_pending_multiplier,
    has_lucky_streak,
    is_allowed_channel,
    is_blacklisted,
)
from ..common.constants import (
    GAME_SLUGS,
    PALETTE_GOLD,
    RANK_NAMES,
    STARTING_CHIP_BALANCE,
    embed_image,
)
from ..common.interactions import safe_defer, safe_edit_original_response, safe_response_edit_message
from ..common.formatting import rank_display, title_display
from ..common.models import GuildSettings, User
from ..games.multiplier_wheel import format_time_remaining

# ---------------------------------------------------------------------------
# Game display metadata
# ---------------------------------------------------------------------------

_GAME_DISPLAY: dict[str, str] = {
    "slots": "Slots",
    "war": "War",
    "allin": "All-In",
    "blackjack": "Blackjack",
    "hilo": "Hi-Lo",
    "keno": "Keno",
    "roulette": "Roulette",
    "videopoker": "Video Poker",
    "clubpoker": "Club Poker",
    "big6": "Big Six Wheel",
    "double": "Double",
    "mysteryspin": "Mystery Wheel",
    "multiplierwheel": "Multiplier Wheel",
}

_GAME_EMOJI: dict[str, str] = {
    "slots": "🎰",
    "war": "⚔️",
    "allin": "💥",
    "blackjack": "🃏",
    "hilo": "📈",
    "keno": "🔢",
    "roulette": "🎡",
    "videopoker": "🎴",
    "clubpoker": "♠️",
    "big6": "🎲",
    "double": "🎲",
    "mysteryspin": "🌀",
    "multiplierwheel": "⚡",
}

# Wheel games rendered in blue (blurple) on the game floor
_WHEEL_GAME_SLUGS: frozenset[str] = frozenset({"big6", "mysteryspin", "multiplierwheel"})

# Maps slug → (module filename without .py, view class name)
# All view files live in the views/ subpackage, named <game>_view.py.
# Pure game logic (math, mechanics) lives in games/<game>.py.
_GAME_MODULE: dict[str, tuple[str, str]] = {
    "slots":          ("slots_view",         "SlotsView"),
    "war":            ("war_view",            "WarView"),
    "allin":          ("all_in_view",         "AllInView"),
    "blackjack":      ("blackjack_view",      "BlackjackView"),
    "hilo":           ("hi_lo_view",          "HiLoView"),
    "keno":           ("keno_view",           "KenoView"),
    "roulette":       ("roulette_view",       "RouletteView"),
    "videopoker":     ("poker_view",          "VideoPokerView"),
    "clubpoker":      ("club_poker_view",     "ClubPokerView"),
        "big6":           ("big_6_wheel_view",    "Big6WheelView"),
    "double":         ("double_view",         "DoubleView"),
    "mysteryspin":    ("mystery_wheel_view",  "MysteryWheelView"),
    "multiplierwheel":("multiplier_wheel_view", "MultiplierWheelView"),
}

_GAME_HELP: dict[str, str] = {
    "slots": (
        "**Slots**\nPay your bet and spin the reels. Matching symbols across the payline award a payout multiplier. "
        "The better the symbol, the bigger the reward. All spins are resolved instantly — no decisions after betting. "
        "A free spin token (from the Mystery Wheel) can cover your wager for one pull."
    ),
    "war": (
        "**War**\nA card is drawn for you and one for the house. Higher card wins. Aces are high. "
        "On a tie, you go to War — an additional equal bet is placed and both sides draw again. "
        "Winning a War returns 2× the total wagered."
    ),
    "allin": (
        "**All-In**\nChoose a Risk Tier (1–5 depending on server cap). Each tier has a fixed win chance and payout "
        "multiplier — higher tiers are riskier but pay more. One flip of the coin decides everything. "
        "The max bet is your full balance (up to 10,000,000)."
    ),
    "blackjack": (
        "**Blackjack**\nBeat the dealer to 21 without going over. Standard rules: "
        "dealer stands on 17, blackjack pays 3:2, bust loses immediately. "
        "Cards are dealt from a virtual deck; suits don't matter."
    ),
    "hilo": (
        "**Hi-Lo**\nA card is revealed. Predict whether the next card will be **Higher** or **Lower**. "
        "Correct predictions grow your payout chain — cash out anytime to collect. "
        "A wrong prediction loses your entire current pot."
    ),
    "double": (
        "**Double**\nPlace a bet. A virtual dice roll (configurable 50% chance by default) is made. "
        "Win → your pot doubles. Lose → you lose everything. After each win, choose to **Cash Out** "
        "and collect `bet × 2ⁿ`, or **Double Again** to risk it all for more."
    ),
    "keno": (
        "**Keno**\nPick 1–10 numbers from a pool of 1–80. The draw selects 20 numbers. "
        "The more of your picks that match, the higher your payout. Payouts scale with both picks and matches."
    ),
    "roulette": (
        "**Roulette**\nBet on a number, color, odd/even, or range. The wheel is spun and the result determines "
        "your payout. Straight-up number bets pay 35:1; color bets pay ~1:1."
    ),
    "big6": (
        "**Big Six Wheel**\nBet on a segment of the wheel. Segments have different frequencies and payouts. "
        "The house segments pay nothing — their count is configurable by admins. "
        "More house segments = higher house edge."
    ),
    "multiplierwheel": (
        "**Multiplier Wheel (The Booster)**\nPay a spin fee to earn a payout multiplier for your next eligible game. "
        "The multiplier stays active for a configurable window (default 30 minutes). "
        "Using it on a win: `profit × (multiplier − 1.0)` is added on top of your payout."
    ),
    "mysteryspin": (
        "**Mystery Wheel (Daily Free Spin)**\nOnce per calendar day (server timezone), spin for a random reward — "
        "chips, bonus tokens, free spins, or other prizes. No cost. "
        "The wheel resets at midnight in the configured timezone."
    ),
    "videopoker": (
        "**Video Poker**\nYou're dealt 5 cards. Choose which to hold, then draw replacements for the rest. "
        "Payouts follow standard Jacks-or-Better table: pair of Jacks or better, two pair, three-of-a-kind, "
        "straight, flush, full house, four-of-a-kind, straight flush, royal flush."
    ),
    "clubpoker": (
        "**Club Poker**\nChallenge one other player to a private 5-card draw hand. Both players ante the same amount, "
        "secretly choose which cards to hold, draw replacements from a shared deck, then play exactly one betting round. "
        "If neither player folds, the best 5-card poker hand wins the pot."
    ),
}

# ---------------------------------------------------------------------------
# Navigation base view
# ---------------------------------------------------------------------------

class _NavViewBase(discord.ui.View):
    """Base for all player navigation views."""

    def __init__(self, member: discord.Member, cog: MixinMeta, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.member = member
        self.cog = cog

    @property
    def conf(self) -> GuildSettings:
        return self.cog.db.get_conf(self.member.guild)

    @property
    def user(self) -> User:
        return self.conf.get_user(self.member.id)

    async def _get_balance(self) -> int:
        if self.conf.payment_mode == "chips":
            return self.user.chip_balance
        return await bank.get_balance(self.member)

    async def _get_currency_name(self) -> str:
        if self.conf.payment_mode == "chips":
            return "chips"
        return await bank.get_currency_name(self.member.guild)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.member.id:
            await interaction.response.send_message(
                "This isn't your session. Run `[p]highrollerclub` to start your own.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Dynamic game launcher
# ---------------------------------------------------------------------------

async def _launch_game(
    interaction: discord.Interaction,
    slug: str,
    member: discord.Member,
    cog: MixinMeta,
) -> None:
    """Dynamically import and launch a game view. Shows 'coming soon' if not yet implemented."""
    if slug not in _GAME_MODULE:
        await interaction.response.send_message("Unknown game.", ephemeral=True)
        return

    file_name, class_name = _GAME_MODULE[slug]
    # View classes live in the views/ subpackage, named <game>_view.py.
    package_base = __name__.rsplit(".", 2)[0]  # e.g. "highrollerclub" parent
    module_path = f"{package_base}.views.{file_name}"

    try:
        mod = importlib.import_module(module_path)
        cls = getattr(mod, class_name)
    except (ImportError, AttributeError):
        await interaction.response.send_message(
            f"**{_GAME_DISPLAY.get(slug, slug)}** is opening soon — check back later!", ephemeral=True
        )
        return

    conf = cog.db.get_conf(member.guild)
    user = conf.get_user(member.id)
    # Pass the full cog so game views can call cog.save(), access cog.db,
    # and construct back-navigation views (e.g. GameRoomView).
    view = cls(interaction, conf, user, cog)
    embed = view._build_embed() if hasattr(view, "_build_embed") else discord.Embed(title=_GAME_DISPLAY.get(slug, slug))
    await safe_response_edit_message(interaction, embed=embed, view=view)


# ---------------------------------------------------------------------------
# Main Lobby View
# ---------------------------------------------------------------------------

class MainLobbyView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta, balance: int, currency_name: str):
        super().__init__(member, cog, timeout=300)
        self._balance = balance
        self._currency_name = currency_name
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()

        game_room = discord.ui.Button(label="🎲 Game Room", style=discord.ButtonStyle.green, row=0)
        game_room.callback = self._go_game_room
        self.add_item(game_room)

        stats = discord.ui.Button(label="📊 Your Stats", style=discord.ButtonStyle.blurple, row=0)
        stats.callback = self._go_stats
        self.add_item(stats)

        lb = discord.ui.Button(label="🏆 Leaderboards", style=discord.ButtonStyle.blurple, row=0)
        lb.callback = self._go_leaderboards
        self.add_item(lb)

        help_btn = discord.ui.Button(label="❓ Help & Info", style=discord.ButtonStyle.grey, row=0)
        help_btn.callback = self._go_help
        self.add_item(help_btn)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=1)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        user = self.user
        e = discord.Embed(title="-=[ The High Roller Club ]=-", color=PALETTE_GOLD)
        rank_name = rank_display(user.rank)
        desc_parts = [
            f"Welcome back to the Club, **{self.member.display_name}**.",
            "",
            f"You are a: \"{rank_name}\" ranked Player.",
            f"Your {self._currency_name} balance is: {self._balance:,} {self._currency_name}",
            "Please click a button below to continue.",
        ]
        e.description = "\n".join(desc_parts)
        if url := embed_image("lobby"):
            e.set_image(url=url)
        return e

    async def _go_game_room(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = GameRoomView(self.member, self.cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    async def _go_stats(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = StatsView(self.member, self.cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    async def _go_leaderboards(self, interaction: discord.Interaction) -> None:
        view = LeaderboardGameSelectorView(self.member, self.cog)
        await safe_response_edit_message(interaction, embed=view._build_embed(), view=view)

    async def _go_help(self, interaction: discord.Interaction) -> None:
        view = HelpView(self.member, self.cog)
        await safe_response_edit_message(interaction, embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(
            description="*The Club has closed its doors for now.*",
            color=PALETTE_GOLD,
        )
        await safe_response_edit_message(interaction, embed=e, view=self)


# ---------------------------------------------------------------------------
# Game Room View
# ---------------------------------------------------------------------------

class GameRoomView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta, balance: int, currency_name: str):
        super().__init__(member, cog, timeout=120)
        self._balance = balance
        self._currency_name = currency_name
        self._add_buttons()

    def _is_game_available(self, slug: str) -> bool:
        conf = self.conf
        if not conf.games_enabled.get(slug, True):
            return False
        if slug == "mysteryspin" and not conf.mystery_wheel_enabled:
            return False
        return True

    def _add_buttons(self) -> None:
        self.clear_items()
        conf = self.conf
        chips_mode = conf.payment_mode == "chips"

        # Teller Window — chips mode only
        if chips_mode:
            teller = discord.ui.Button(
                label="💰 Teller Window",
                style=discord.ButtonStyle.grey,
                row=0,
            )
            teller.callback = self._go_teller
            self.add_item(teller)

        # Game buttons
        # Chip mode: 4 games row 0 (after teller), 5 row 1, 4 row 2
        # Bank mode: 5 games row 0, 5 row 1, 3 row 2
        if chips_mode:
            row_sizes = [4, 5, 4]
        else:
            row_sizes = [5, 5, 3]

        game_row = 0
        col_in_row = 0
        for slug in GAME_SLUGS:
            available = self._is_game_available(slug)
            display = _GAME_DISPLAY.get(slug, slug)
            emoji = _GAME_EMOJI.get(slug, "🎲")
            label = f"{emoji} {display}" if available else f"🔒 {display}"
            if not available:
                style = discord.ButtonStyle.grey
            elif slug in _WHEEL_GAME_SLUGS:
                style = discord.ButtonStyle.blurple
            else:
                style = discord.ButtonStyle.green
            btn = discord.ui.Button(
                label=label,
                style=style,
                disabled=not available,
                row=game_row,
            )
            if available:
                btn.callback = self._make_game_cb(slug)
            self.add_item(btn)

            col_in_row += 1
            if game_row < len(row_sizes) and col_in_row >= row_sizes[game_row]:
                game_row += 1
                col_in_row = 0

        # Navigation row (row 3)
        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=3)
        back.callback = self._go_lobby
        self.add_item(back)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=3)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        user = self.user
        e = discord.Embed(title="The Game Floor", color=PALETTE_GOLD)
        e.description = (
            f"Welcome to the floor, **{self.member.display_name}** — {rank_display(user.rank)}.\n"
            f"Balance: **{self._balance:,} {self._currency_name}**\n"
            "*The tables are set and the wheels are spinning — where will fortune find you tonight?*"
        )
        title = title_display(user)
        if title:
            e.set_footer(text=title)
        if url := embed_image("game_floor"):
            e.set_thumbnail(url=url)
        return e

    def _make_game_cb(self, slug: str):
        async def cb(interaction: discord.Interaction) -> None:
            await _launch_game(interaction, slug, self.member, self.cog)
        return cb

    async def _go_teller(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        bank_currency = await bank.get_currency_name(self.member.guild)
        view = TellerWindowView(self.member, self.cog, balance, currency_name, bank_currency)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _go_lobby(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = MainLobbyView(self.member, self.cog, balance, currency_name)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(description="*The Club has closed its doors for now.*", color=PALETTE_GOLD)
        await interaction.response.edit_message(embed=e, view=self)


# ---------------------------------------------------------------------------
# Teller Window View (Chip Mode Only)
# ---------------------------------------------------------------------------

class TellerWindowView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta, balance: int, currency_name: str, bank_currency: str = ""):
        super().__init__(member, cog, timeout=180)
        self._balance = balance
        self._currency_name = currency_name
        self._bank_currency = bank_currency  # real Discord bank currency name
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        conf = self.conf

        buy = discord.ui.Button(label="💰 Buy Chips", style=discord.ButtonStyle.green, row=0)
        buy.callback = self._buy_chips
        self.add_item(buy)

        conv_enabled = conf.discord_currency_conversion_enabled
        convert = discord.ui.Button(
            label="🔄 Convert Chips",
            style=discord.ButtonStyle.blurple,
            disabled=not conv_enabled,
            row=0,
        )
        convert.callback = self._convert_chips
        self.add_item(convert)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=1)
        back.callback = self._go_back
        self.add_item(back)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=1)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        conf = self.conf
        bank_cur = self._bank_currency or self._currency_name
        e = discord.Embed(title="🏦 The Teller Window", color=PALETTE_GOLD)
        e.description = (
            f"Current chip balance: **{self.user.chip_balance:,} chips**\n"
            f"Rate: **{conf.discord_currency_conversion_rate:,} chips per 1 {bank_cur}**"
        )
        if conf.discord_currency_conversion_enabled:
            e.description += "\nChip conversion is available — cash out your chips for server currency."
        if url := embed_image("teller"):
            e.set_thumbnail(url=url)
        return e

    async def _buy_chips(self, interaction: discord.Interaction) -> None:
        conf = self.conf
        rate = conf.discord_currency_conversion_rate
        bank_cur = self._bank_currency or await bank.get_currency_name(self.member.guild)
        modal = _BuyChipsModal(rate, bank_cur)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.chips_requested is None:
            return

        chips = modal.chips_requested
        if chips % rate != 0:
            await interaction.followup.send(
                f"\u274c Enter a **multiple of {rate:,}** chips "
                f"(e.g. {rate:,}, {rate * 2:,}, {rate * 5:,}\u2026). No fractions allowed.",
                ephemeral=True,
            )
            return

        cost = chips // rate
        bank_balance = await bank.get_balance(self.member)

        view = _BuyChipsConfirmView(
            self.member, self.cog, chips, cost, bank_balance, bank_cur
        )
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _convert_chips(self, interaction: discord.Interaction) -> None:
        conf = self.conf
        rate = conf.discord_currency_conversion_rate
        bank_cur = self._bank_currency or await bank.get_currency_name(self.member.guild)
        modal = _ConvertChipsModal(rate, bank_cur)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.chips_requested is None:
            return

        chips = modal.chips_requested
        if chips < rate:
            await interaction.followup.send(
                f"You need at least **{rate:,} chips** to convert 1 {bank_cur}.", ephemeral=True
            )
            return

        payout = chips // rate
        remainder = chips % rate
        view = _ConvertChipsConfirmView(
            self.member, self.cog, chips, payout, remainder, bank_cur
        )
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = GameRoomView(self.member, self.cog, balance, currency_name)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(description="*The Club has closed its doors for now.*", color=PALETTE_GOLD)
        await interaction.response.edit_message(embed=e, view=self)


class _BuyChipsModal(discord.ui.Modal, title="Buy Chips"):
    def __init__(self, rate: int, currency_name: str):
        super().__init__()
        self.amount = discord.ui.TextInput(
            label="Chips to buy",
            placeholder=f"Must be a multiple of {rate:,}  (e.g. {rate:,}, {rate * 2:,}, {rate * 5:,}\u2026)",
            min_length=1,
            max_length=12,
        )
        self.add_item(self.amount)
        self.chips_requested: int | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            val = int(self.amount.value.replace(",", "").strip())
            if val < 1:
                raise ValueError
            self.chips_requested = val
        except ValueError:
            await interaction.response.send_message("Please enter a valid positive number.", ephemeral=True)
            return
        await interaction.response.defer()


class _ConvertChipsModal(discord.ui.Modal, title="Convert Chips"):
    def __init__(self, rate: int, currency_name: str):
        super().__init__()
        self.amount = discord.ui.TextInput(
            label="Chips to convert",
            placeholder=f"Min {rate:,} chips = 1 {currency_name}. Remainder not converted.",
            min_length=1,
            max_length=12,
        )
        self.add_item(self.amount)
        self.chips_requested: int | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            val = int(self.amount.value.replace(",", "").strip())
            if val < 1:
                raise ValueError
            self.chips_requested = val
        except ValueError:
            await interaction.response.send_message("Please enter a valid positive number.", ephemeral=True)
            return
        await interaction.response.defer()


class _BuyChipsConfirmView(_NavViewBase):
    def __init__(
        self,
        member: discord.Member,
        cog: MixinMeta,
        chips: int,
        cost: int,
        bank_balance: int,
        currency_name: str,
    ):
        super().__init__(member, cog, timeout=60)
        self._chips = chips
        self._cost = cost
        self._bank_balance = bank_balance
        self._currency_name = currency_name
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        confirm = discord.ui.Button(label="✅ Confirm", style=discord.ButtonStyle.green, row=0)
        confirm.callback = self._confirm
        self.add_item(confirm)
        cancel = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.red, row=0)
        cancel.callback = self._cancel
        self.add_item(cancel)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Confirm Purchase", color=PALETTE_GOLD)
        e.description = (
            f"Buy **{self._chips:,} chips** for **{self._cost:,} {self._currency_name}**?\n"
            f"Your bank balance: **{self._bank_balance:,} {self._currency_name}**"
        )
        return e

    async def _confirm(self, interaction: discord.Interaction) -> None:
        live_balance = await bank.get_balance(self.member)
        if live_balance < self._cost:
            await interaction.response.send_message(
                f"Insufficient {self._currency_name} — you need {self._cost:,} but only have {live_balance:,}.",
                ephemeral=True,
            )
            return

        await bank.withdraw_credits(self.member, self._cost)
        user = self.user
        user.chip_balance += self._chips
        self.cog.save()

        new_balance = user.chip_balance
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]

        e = discord.Embed(title="Transaction Complete!", color=discord.Colour.green())
        e.description = (
            f"**{self._chips:,} chips** added.\n"
            f"New balance: **{new_balance:,} chips**"
        )

        back_btn = discord.ui.Button(label="← Back to Teller", style=discord.ButtonStyle.grey)
        floor_btn = discord.ui.Button(label="🎲 To the Floor", style=discord.ButtonStyle.green)

        result_view = _TellerResultView(self.member, self.cog, new_balance, self._currency_name)
        await interaction.response.edit_message(embed=e, view=result_view)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        chip_balance = self.user.chip_balance
        view = TellerWindowView(self.member, self.cog, chip_balance, "chips", self._currency_name)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)


class _ConvertChipsConfirmView(_NavViewBase):
    def __init__(
        self,
        member: discord.Member,
        cog: MixinMeta,
        chips: int,
        payout: int,
        remainder: int,
        currency_name: str,
    ):
        super().__init__(member, cog, timeout=60)
        self._chips = chips
        self._payout = payout
        self._remainder = remainder
        self._currency_name = currency_name
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        confirm = discord.ui.Button(label="✅ Confirm", style=discord.ButtonStyle.green, row=0)
        confirm.callback = self._confirm
        self.add_item(confirm)
        cancel = discord.ui.Button(label="❌ Cancel", style=discord.ButtonStyle.red, row=0)
        cancel.callback = self._cancel
        self.add_item(cancel)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Confirm Conversion", color=PALETTE_GOLD)
        e.description = (
            f"Convert **{self._chips:,} chips** → **{self._payout:,} {self._currency_name}**.\n"
            f"Remainder: **{self._remainder:,} chips** (not deducted, not converted)."
        )
        return e

    async def _confirm(self, interaction: discord.Interaction) -> None:
        user = self.user
        if user.chip_balance < self._chips:
            await interaction.response.send_message(
                f"Insufficient chips — you need {self._chips:,} but only have {user.chip_balance:,}.",
                ephemeral=True,
            )
            return

        user.chip_balance -= self._chips
        await bank.deposit_credits(self.member, self._payout)
        self.cog.save()

        new_chip_balance = user.chip_balance
        new_bank_balance = await bank.get_balance(self.member)
        currency_name = self._currency_name

        e = discord.Embed(title="Conversion Complete!", color=discord.Colour.green())
        e.description = (
            f"**{self._payout:,} {currency_name}** added to your bank.\n"
            f"New chip balance: **{new_chip_balance:,} chips** | "
            f"Bank: **{new_bank_balance:,} {currency_name}**"
        )
        result_view = _TellerResultView(self.member, self.cog, new_chip_balance, currency_name)
        await interaction.response.edit_message(embed=e, view=result_view)

    async def _cancel(self, interaction: discord.Interaction) -> None:
        chip_balance = self.user.chip_balance
        view = TellerWindowView(self.member, self.cog, chip_balance, "chips", self._currency_name)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)


class _TellerResultView(_NavViewBase):
    """Shown after a successful Buy or Convert — Back to Teller or To the Floor."""

    def __init__(self, member: discord.Member, cog: MixinMeta, chip_balance: int, currency_name: str):
        super().__init__(member, cog, timeout=120)
        self._chip_balance = chip_balance
        self._currency_name = currency_name
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        back = discord.ui.Button(label="← Back to Teller", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._go_teller
        self.add_item(back)
        floor = discord.ui.Button(label="🎲 To the Floor", style=discord.ButtonStyle.green, row=0)
        floor.callback = self._go_floor
        self.add_item(floor)

    async def _go_teller(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        bank_currency = await bank.get_currency_name(self.member.guild)
        view = TellerWindowView(self.member, self.cog, balance, currency_name, bank_currency)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _go_floor(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = GameRoomView(self.member, self.cog, balance, currency_name)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)


# ---------------------------------------------------------------------------
# Stats View
# ---------------------------------------------------------------------------

class StatsView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta, balance: int, currency_name: str):
        super().__init__(member, cog, timeout=180)
        self._balance = balance
        self._currency_name = currency_name
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        titles_btn = discord.ui.Button(label="🎭 Manage Titles", style=discord.ButtonStyle.blurple, row=0)
        titles_btn.callback = self._go_titles
        self.add_item(titles_btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._go_lobby
        self.add_item(back)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=0)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        user = self.user
        e = discord.Embed(title=f"{self.member.display_name}'s Club Record", color=PALETTE_GOLD)

        # Rank + title
        rank_str = RANK_NAMES.get(user.rank, "Member")
        title_str = title_display(user) or "None"
        e.add_field(name="Rank", value=f"{rank_str}\n*{title_str}*", inline=True)

        # Prestige
        conf = self.conf
        thresholds = {2: conf.rank2_threshold, 3: conf.rank3_threshold, 4: conf.rank4_threshold}
        if user.rank >= 4:
            next_info = "Max rank"
        else:
            next_rank = user.rank + 1
            next_thresh = thresholds[next_rank]
            next_info = f"Next rank at {next_thresh:,} pts"
        e.add_field(name="Prestige", value=f"{user.prestige_points:.2f} pts\n*{next_info}*", inline=True)

        # Balance
        e.add_field(name="Balance", value=f"{self._balance:,} {self._currency_name}", inline=True)

        # Record
        total = user.total_wins + user.total_losses
        win_rate = (user.total_wins / total * 100) if total > 0 else 0.0
        e.add_field(
            name="Record",
            value=f"{user.total_wins}W / {user.total_losses}L ({win_rate:.1f}% win rate)",
            inline=True,
        )

        # Largest payout/loss
        e.add_field(name="Largest Payout", value=f"{user.largest_single_payout:,} {self._currency_name}", inline=True)
        e.add_field(name="Largest Loss", value=f"{user.largest_single_loss:,} {self._currency_name}", inline=True)

        # Favorite game
        play_counts = user.game_play_counts
        if play_counts and any(v > 0 for v in play_counts.values()):
            fav_slug = max(play_counts, key=lambda k: play_counts.get(k, 0))
            fav = _GAME_DISPLAY.get(fav_slug, fav_slug)
        else:
            fav = "None yet"
        e.add_field(name="Favorite Game", value=fav, inline=True)

        # Active modifiers
        modifiers: list[str] = []
        active_multiplier = get_pending_multiplier(user)
        if active_multiplier is not None and user.pending_multiplier_expiry is not None:
            modifiers.append(
                f"⚡ Multiplier: **{active_multiplier}x** ({format_time_remaining(user.pending_multiplier_expiry)} left)"
            )
        if has_lucky_streak(user) and user.lucky_streak_expiry is not None:
            modifiers.append(
                f"🔥 Lucky Streak: **+25% payout** ({format_time_remaining(user.lucky_streak_expiry)} left)"
            )
        e.add_field(
            name="Current Modifiers",
            value="\n".join(modifiers) if modifiers else "No active bonuses",
            inline=False,
        )

        # Per-game breakdown code block — only games the player has attempted.
        played = {
            slug: play_counts.get(slug, 0)
            for slug in _GAME_DISPLAY
            if play_counts.get(slug, 0) > 0
        }
        if played:
            # Sort alphabetically by display name.
            rows = sorted(played.keys(), key=lambda s: _GAME_DISPLAY.get(s, s))
            col_w = max(len(_GAME_DISPLAY.get(s, s)) for s in rows)
            col_w = max(col_w, 4)  # at least as wide as "Game"
            header = f"{'Game':<{col_w}}   {'W':>5}  {'L':>5}  {'Win%':>6}"
            divider = "─" * len(header)
            lines = [header, divider]
            for slug in rows:
                display = _GAME_DISPLAY.get(slug, slug)
                w = user.game_win_counts.get(slug, 0)
                l = user.game_loss_counts.get(slug, 0)
                total_g = w + l
                pct = f"{w / total_g * 100:.1f}%" if total_g > 0 else "—"
                lines.append(f"{display:<{col_w}}   {w:>5}  {l:>5}  {pct:>6}")
            e.add_field(name="Game Breakdown", value=f"```\n{chr(10).join(lines)}\n```", inline=False)

        if url := embed_image("stats"):
            e.set_thumbnail(url=url)
        return e

    async def _go_titles(self, interaction: discord.Interaction) -> None:
        view = TitleSelectView(self.member, self.cog, self._balance, self._currency_name)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_lobby(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = MainLobbyView(self.member, self.cog, balance, currency_name)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(description="*The Club has closed its doors for now.*", color=PALETTE_GOLD)
        await interaction.response.edit_message(embed=e, view=self)


# ---------------------------------------------------------------------------
# Title Select View
# ---------------------------------------------------------------------------

class TitleSelectView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta, balance: int, currency_name: str):
        super().__init__(member, cog, timeout=180)
        self._balance = balance
        self._currency_name = currency_name
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        user = self.user

        for idx, title in enumerate(user.earned_titles):
            is_active = title == user.active_title
            btn = discord.ui.Button(
                label=f"{'✅ ' if is_active else ''}{title}",
                style=discord.ButtonStyle.green if is_active else discord.ButtonStyle.grey,
                row=idx // 4,
            )
            btn.callback = self._make_title_cb(title)
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)

    def _build_embed(self) -> discord.Embed:
        user = self.user
        e = discord.Embed(title="Manage Titles", color=PALETTE_GOLD)
        if user.earned_titles:
            active_str = f"**{user.active_title}**" if user.active_title else "*None selected*"
            e.description = (
                f"Select a title to display next to your rank.\n"
                f"Active title: {active_str}\n"
                f"*Tap the active title to deselect it.*"
            )
        else:
            e.description = "You haven't earned any specialty titles yet. Keep playing to unlock them!"
        return e

    def _make_title_cb(self, title: str):
        async def cb(interaction: discord.Interaction) -> None:
            user = self.user
            if user.active_title == title:
                user.active_title = None
            else:
                user.active_title = title
            self.cog.save()
            self._add_buttons()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        return cb

    async def _go_back(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = StatsView(self.member, self.cog, balance, currency_name)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)


# ---------------------------------------------------------------------------
# Leaderboard — Game Selector
# ---------------------------------------------------------------------------

class LeaderboardGameSelectorView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta):
        super().__init__(member, cog, timeout=180)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        conf = self.conf

        # Check which games have any data
        for idx, slug in enumerate(GAME_SLUGS):
            has_data = any(
                user.game_play_counts.get(slug, 0) > 0
                for user in conf.users.values()
            )
            display = _GAME_DISPLAY.get(slug, slug)
            emoji = _GAME_EMOJI.get(slug, "🎲")
            btn = discord.ui.Button(
                label=f"{emoji} {display}",
                style=discord.ButtonStyle.blurple if has_data else discord.ButtonStyle.grey,
                disabled=not has_data,
                row=idx // 5,
            )
            if has_data:
                btn.callback = self._make_game_cb(slug)
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=3)
        back.callback = self._go_lobby
        self.add_item(back)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=3)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Leaderboards — Select a Game", color=PALETTE_GOLD)
        e.description = "Choose a game to view its leaderboard. Grey buttons have no data yet."
        if url := embed_image("leaderboard"):
            e.set_thumbnail(url=url)
        return e

    def _make_game_cb(self, slug: str):
        async def cb(interaction: discord.Interaction) -> None:
            view = LeaderboardView(self.member, self.cog, slug)
            await interaction.response.edit_message(embed=view._build_embed(), view=view)
        return cb

    async def _go_lobby(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = MainLobbyView(self.member, self.cog, balance, currency_name)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(description="*The Club has closed its doors for now.*", color=PALETTE_GOLD)
        await interaction.response.edit_message(embed=e, view=self)


# ---------------------------------------------------------------------------
# Per-Game Leaderboard View
# ---------------------------------------------------------------------------

_LB_SORTS = [
    ("💰 Total Payout", "game_total_payout"),
    ("🏆 Total Wins", "game_win_counts"),
    ("⭐ Best Win", "game_highest_single_payout"),
    ("🎲 Biggest Bet", "game_highest_bet"),
    ("💸 Biggest Loss", "game_highest_single_loss"),
    ("📉 Total Losses", "game_loss_counts"),
]

_PAGE_SIZE = 10


class LeaderboardView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta, slug: str, sort_key: str = "game_total_payout", page: int = 0):
        super().__init__(member, cog, timeout=180)
        self.slug = slug
        self.sort_key = sort_key
        self.page = page
        self._add_buttons()

    def _get_sorted_entries(self) -> list[tuple[int, int]]:
        """Returns [(user_id, value), ...] sorted descending."""
        conf = self.conf
        slug = self.slug
        entries: list[tuple[int, int]] = []
        for uid, user in conf.users.items():
            val_dict: dict = getattr(user, self.sort_key, {})
            val = val_dict.get(slug, 0)
            if val > 0:
                entries.append((uid, val))
        entries.sort(key=lambda x: x[1], reverse=True)
        return entries

    def _add_buttons(self) -> None:
        self.clear_items()
        entries = self._get_sorted_entries()
        total_pages = max(1, math.ceil(len(entries) / _PAGE_SIZE))

        # Row 0 — sort filters 1-5
        for label, key in _LB_SORTS[:5]:
            btn = discord.ui.Button(
                label=label,
                style=discord.ButtonStyle.green if key == self.sort_key else discord.ButtonStyle.grey,
                row=0,
            )
            btn.callback = self._make_sort_cb(key)
            self.add_item(btn)

        # Row 1 — 6th sort + pagination
        label6, key6 = _LB_SORTS[5]
        sort6 = discord.ui.Button(
            label=label6,
            style=discord.ButtonStyle.green if key6 == self.sort_key else discord.ButtonStyle.grey,
            row=1,
        )
        sort6.callback = self._make_sort_cb(key6)
        self.add_item(sort6)

        prev_btn = discord.ui.Button(
            label="◀ Prev", style=discord.ButtonStyle.grey, disabled=self.page == 0, row=1
        )
        prev_btn.callback = self._go_prev
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label="▶ Next", style=discord.ButtonStyle.grey, disabled=self.page >= total_pages - 1, row=1
        )
        next_btn.callback = self._go_next
        self.add_item(next_btn)

        # Row 2 — navigation
        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=2)
        back.callback = self._go_selector
        self.add_item(back)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=2)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        entries = self._get_sorted_entries()
        total_pages = max(1, math.ceil(len(entries) / _PAGE_SIZE))
        page_entries = entries[self.page * _PAGE_SIZE: (self.page + 1) * _PAGE_SIZE]

        display = _GAME_DISPLAY.get(self.slug, self.slug)
        sort_label = next((lbl for lbl, key in _LB_SORTS if key == self.sort_key), self.sort_key)

        e = discord.Embed(title=f"{display} Leaderboard", color=PALETTE_GOLD)

        if not page_entries:
            e.description = "No entries yet."
        else:
            lines = []
            for rank_pos, (uid, val) in enumerate(page_entries, start=self.page * _PAGE_SIZE + 1):
                member = self.member.guild.get_member(uid)
                name = member.display_name if member else str(uid)
                lines.append(f"**{rank_pos}.** {name} — {val:,}")
            e.description = "\n".join(lines)

        e.set_footer(text=f"Sorted by: {sort_label} | Page {self.page + 1}/{total_pages}")
        if url := embed_image("leaderboard"):
            e.set_thumbnail(url=url)
        return e

    def _make_sort_cb(self, key: str):
        async def cb(interaction: discord.Interaction) -> None:
            self.sort_key = key
            self.page = 0
            self._add_buttons()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)
        return cb

    async def _go_prev(self, interaction: discord.Interaction) -> None:
        self.page = max(0, self.page - 1)
        self._add_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        entries = self._get_sorted_entries()
        total_pages = max(1, math.ceil(len(entries) / _PAGE_SIZE))
        self.page = min(total_pages - 1, self.page + 1)
        self._add_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _go_selector(self, interaction: discord.Interaction) -> None:
        view = LeaderboardGameSelectorView(self.member, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(description="*The Club has closed its doors for now.*", color=PALETTE_GOLD)
        await interaction.response.edit_message(embed=e, view=self)


# ---------------------------------------------------------------------------
# Help & Info View
# ---------------------------------------------------------------------------

class HelpView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta):
        super().__init__(member, cog, timeout=180)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        for idx, slug in enumerate(GAME_SLUGS):
            display = _GAME_DISPLAY.get(slug, slug)
            emoji = _GAME_EMOJI.get(slug, "🎲")
            btn = discord.ui.Button(
                label=f"{emoji} {display}",
                style=discord.ButtonStyle.grey,
                row=idx // 5,
            )
            btn.callback = self._make_game_help_cb(slug)
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=3)
        back.callback = self._go_lobby
        self.add_item(back)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=3)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="The High Roller Club — How It Works", color=PALETTE_GOLD)
        e.add_field(
            name="🏆 Ranks & Prestige",
            value=(
                "Earn prestige points by winning games and lose points by losing. "
                "Ranks: Member → Regular → High Roller → The Whale. "
                "Higher ranks unlock larger bet limits (if enabled by admins)."
            ),
            inline=False,
        )
        e.add_field(
            name="🪙 Payment Modes",
            value=(
                "**House Chips** — buy chips from the Teller Window using server currency. "
                "All games use chips; conversion back to server currency is optional.\n"
                "**Server Currency** — games use your bank balance directly."
            ),
            inline=False,
        )
        e.add_field(
            name="🎭 Specialty Titles",
            value=(
                "Earn unique titles by hitting specific milestones — big payouts, long streaks, or rare hands. "
                "Equip titles from 📊 Your Stats."
            ),
            inline=False,
        )
        e.add_field(
            name="🎫 Bonus Tokens & Free Spins",
            value=(
                "Bonus Bet Tokens double your next win in eligible games. "
                "Free Spin tokens grant a free Slots pull. "
                "Both can be earned from the Mystery Wheel and Scratch Cards."
            ),
            inline=False,
        )
        e.add_field(
            name="🃏 Scratch Cards & 🌀 Mystery Wheel",
            value=(
                "**Scratch Cards** — earn one card per cooldown period; scratch for a random reward.\n"
                "**Mystery Wheel** — free daily spin that resets at midnight (server timezone)."
            ),
            inline=False,
        )
        e.add_field(
            name="⚡ Multiplier Wheel",
            value=(
                "Spend chips/currency to spin the Booster Wheel. "
                "Land a multiplier that boosts your next eligible game's profit. "
                "Valid for a limited time window after spinning."
            ),
            inline=False,
        )
        e.set_footer(text="Select a game below to see its rules.")
        if url := embed_image("help"):
            e.set_thumbnail(url=url)
        return e

    def _make_game_help_cb(self, slug: str):
        async def cb(interaction: discord.Interaction) -> None:
            view = PerGameHelpView(self.member, self.cog, slug)
            await interaction.response.edit_message(embed=view._build_embed(), view=view)
        return cb

    async def _go_lobby(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer()
        balance = await self._get_balance()
        currency_name = await self._get_currency_name()
        view = MainLobbyView(self.member, self.cog, balance, currency_name)
        await interaction.edit_original_response(embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(description="*The Club has closed its doors for now.*", color=PALETTE_GOLD)
        await interaction.response.edit_message(embed=e, view=self)


class PerGameHelpView(_NavViewBase):
    def __init__(self, member: discord.Member, cog: MixinMeta, slug: str):
        super().__init__(member, cog, timeout=180)
        self.slug = slug
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._go_help
        self.add_item(back)

        close = discord.ui.Button(label="✕ Close", style=discord.ButtonStyle.red, row=0)
        close.callback = self._close
        self.add_item(close)

    def _build_embed(self) -> discord.Embed:
        display = _GAME_DISPLAY.get(self.slug, self.slug)
        help_text = _GAME_HELP.get(self.slug, "No rules description available yet.")
        e = discord.Embed(title=f"{display} — How to Play", color=PALETTE_GOLD, description=help_text)
        return e

    async def _go_help(self, interaction: discord.Interaction) -> None:
        view = HelpView(self.member, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _close(self, interaction: discord.Interaction) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        e = discord.Embed(description="*The Club has closed its doors for now.*", color=PALETTE_GOLD)
        await interaction.response.edit_message(embed=e, view=self)


# ---------------------------------------------------------------------------
# UserCommands — the single player-facing command
# ---------------------------------------------------------------------------

class UserCommands(MixinMeta):
    """Player-facing command for HighRollerClub."""

    @commands.command(name="highrollerclub", aliases=["hrc"])
    @commands.guild_only()
    async def highrollerclub(self, ctx: commands.Context) -> None:
        """The HighRollerClub is a Casino cog with modular control that
        allows the Owner/Admin to select what games they want enabled,
        how the economy functions, prices and modifiers, and more.

        To setup, use `[p]hrcsetup` to configure the club for your server."""
        conf = self.db.get_conf(ctx.guild)

        # Pre-flight: channel check
        if not is_allowed_channel(conf, ctx.channel.id):
            await ctx.send("The High Roller Club isn't available in this channel.")
            return

        # Pre-flight: blacklist check
        if is_blacklisted(conf, ctx.author.id):
            await ctx.send("You are not permitted to enter the High Roller Club.")
            return

        user = conf.get_user(ctx.author.id)

        # Auto-grant starting chips for new players in chip mode
        if (
            conf.payment_mode == "chips"
            and user.chip_balance == 0
            and user.total_wins == 0
            and user.total_losses == 0
        ):
            user.chip_balance = STARTING_CHIP_BALANCE
            self.save()
            welcome_e = discord.Embed(
                title="Welcome to the High Roller Club!",
                description=(
                    f"You've been granted **{STARTING_CHIP_BALANCE:,} chips** to get started.\n"
                    "Head to the Teller Window on the Game Floor to buy more chips anytime.\n\n"
                    "*Good luck at the tables.*"
                ),
                color=PALETTE_GOLD,
            )
            await ctx.send(embed=welcome_e)

        # Fetch balance and currency name
        if conf.payment_mode == "chips":
            balance = user.chip_balance
            currency_name = "chips"
        else:
            balance = await bank.get_balance(ctx.author)
            currency_name = await bank.get_currency_name(ctx.guild)

        # Open Main Lobby
        view = MainLobbyView(ctx.author, self, balance, currency_name)
        await ctx.send(embed=view._build_embed(), view=view)

