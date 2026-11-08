from __future__ import annotations

import copy
import zoneinfo
from datetime import datetime

import discord
from redbot.core import commands

from ..abc import MixinMeta
from ..common.interactions import safe_edit_original_response
from ..common.constants import (
    ALLIN_RISK_TIERS,
    BIG6_DEFAULT_SEGMENTS,
    BIG6_FIXED_SEGMENTS,
    BIG6_HOUSE_SEGMENT_OPTIONS,
    BIG6_PAYOUTS,
    CARD_MATH_GAMES,
    CONFIGURABLE_RNG,
    DEFAULT_BET_LIMITS,
    GAME_SLUGS,
    HOLDEM_ACTION_SECONDS_RANGE,
    HOLDEM_BUYIN_FLOOR_BB,
    HOLDEM_DEFAULT_STAKE_TIERS,
    PALETTE_GOLD,
    RANK_NAMES,
    SCRATCH_REWARD_OPTIONS,
)
from ..commands.helper_functions import get_holdem_tiers
from ..common.models import GuildSettings, HoldemStakeTier, Horse
from ..games import horse_racing as hr


# ---------------------------------------------------------------------------
# Shared modal helpers
# ---------------------------------------------------------------------------

class _SingleInputModal(discord.ui.Modal):
    """Generic single-text-input modal reused across wizard pages."""

    def __init__(self, title: str, label: str, placeholder: str = "", default: str = ""):
        # A timeout so a modal the admin closes doesn't leave modal.wait() hanging forever.
        super().__init__(title=title, timeout=300)
        self.answer = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            default=default,
        )
        self.add_item(self.answer)
        self.value: str | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.value = self.answer.value
        await interaction.response.defer()


class _BetLimitsModal(discord.ui.Modal):
    """Min and max bet for one game in a single modal."""

    def __init__(self, game_name: str, current_min: int, current_max: int):
        super().__init__(title=f"{game_name} Bet Limits"[:45], timeout=300)
        self.min_input = discord.ui.TextInput(label="Minimum bet", default=str(current_min), max_length=12)
        self.max_input = discord.ui.TextInput(label="Maximum bet (before rank multiplier)", default=str(current_max), max_length=12)
        self.add_item(self.min_input)
        self.add_item(self.max_input)
        self.values: tuple[int, int] | None = None
        self.error: str | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            low = int(self.min_input.value.replace(",", "").strip())
            high = int(self.max_input.value.replace(",", "").strip())
        except ValueError:
            self.error = "Both limits must be whole numbers."
        else:
            if low < 1:
                self.error = "The minimum bet must be at least 1."
            elif high < low:
                self.error = "The maximum bet can't be lower than the minimum."
            else:
                self.values = (low, high)
        if self.error:
            await interaction.response.send_message(f"❌ {self.error} Nothing was changed.", ephemeral=True)
        else:
            await interaction.response.defer()


def _threshold_order_error(r2: int, r3: int, r4: int) -> str | None:
    """Rank thresholds must climb: Regular < High Roller < The Whale."""
    if not r2 < r3 < r4:
        return (
            "Rank thresholds must climb: Regular < High Roller < The Whale "
            f"(this would make them {r2:,} / {r3:,} / {r4:,})."
        )
    return None


# ---------------------------------------------------------------------------
# Wizard state container (holds uncommitted settings across pages)
# ---------------------------------------------------------------------------

class _WizardState:
    """Holds pending changes while the admin navigates the setup wizard.
    Nothing is written to GuildSettings until Save is confirmed.
    """

    def __init__(self, conf: GuildSettings):
        # Copy all mutable fields we will edit
        self.payment_mode = conf.payment_mode
        self.discord_currency_conversion_rate = conf.discord_currency_conversion_rate
        self.discord_currency_conversion_enabled = conf.discord_currency_conversion_enabled

        self.rank2_threshold = conf.rank2_threshold
        self.rank3_threshold = conf.rank3_threshold
        self.rank4_threshold = conf.rank4_threshold
        self.prestige_win_points = conf.prestige_win_points
        self.prestige_loss_points = conf.prestige_loss_points

        self.bet_multipliers_enabled = conf.bet_multipliers_enabled
        self.rank1_multiplier = conf.rank1_multiplier
        self.rank2_multiplier = conf.rank2_multiplier
        self.rank3_multiplier = conf.rank3_multiplier
        self.rank4_multiplier = conf.rank4_multiplier

        self.game_bet_limits: dict[str, dict[str, int]] = dict(conf.game_bet_limits)

        self.allin_max_tier = conf.allin_max_tier

        self.scratch_enabled = conf.scratch_enabled
        self.scratch_cooldown_hours = conf.scratch_cooldown_hours
        self.scratch_reward_pool: list[str] = list(conf.scratch_reward_pool)

        self.mystery_wheel_enabled = conf.mystery_wheel_enabled
        self.mystery_wheel_timezone = conf.mystery_wheel_timezone
        self.mystery_wheel_reward_pool: list[str] = list(conf.mystery_wheel_reward_pool)

        self.multiplier_wheel_cost = conf.multiplier_wheel_cost
        self.multiplier_wheel_expiry_minutes = conf.multiplier_wheel_expiry_minutes

        self.big6_house_segments = conf.big6_house_segments

        self.game_rng_settings: dict[str, dict] = {
            k: dict(v) for k, v in conf.game_rng_settings.items()
        }

        self.games_enabled: dict[str, bool] = dict(conf.games_enabled)

        self.allowed_channels: list[int] = list(conf.allowed_channels)

        self.race_channel_id = conf.race_channel_id
        self.horserace_house_cut_pct = conf.horserace_house_cut_pct
        self.horserace_countdown_minutes = conf.horserace_countdown_minutes
        self.horserace_cooldown_minutes = conf.horserace_cooldown_minutes
        self.horserace_house_line_return_pct = conf.horserace_house_line_return_pct

        # Texas Hold'em (copies, so edits don't touch the live levels until Save)
        self.holdem_stake_tiers: list[HoldemStakeTier] = [t.model_copy() for t in get_holdem_tiers(conf)]
        self.holdem_action_seconds = conf.holdem_action_seconds
        self.holdem_min_buyin_bb = conf.holdem_min_buyin_bb
        self.holdem_max_buyin_bb = conf.holdem_max_buyin_bb

        # Wizard bookkeeping (underscore names are not settings).
        self._initial = copy.deepcopy({k: v for k, v in vars(self).items() if not k.startswith("_")})
        self._message: discord.Message | None = None  # the wizard message, for on_timeout
        self._current_view: discord.ui.View | None = None  # the page currently shown on it

    def apply(self, conf: GuildSettings) -> None:
        """Write the settings changed in the wizard into the live GuildSettings object.

        Settings the admin didn't touch are left alone, so a `hrcset set ...` made while
        the wizard was open isn't overwritten by the wizard's older copy.
        """
        for key, initial in self._initial.items():
            value = getattr(self, key)
            if value != initial:
                setattr(conf, key, copy.deepcopy(value))


# ---------------------------------------------------------------------------
# Wizard page base
# ---------------------------------------------------------------------------

class _WizardPageBase(discord.ui.View):
    """Base class for all setup wizard pages.  Subclasses implement
    _build_embed() and add their own interactive buttons/selects.
    """

    def __init__(
        self,
        ctx: commands.Context,
        state: _WizardState,
        cog: MixinMeta,
        page_index: int,
        total_pages: int = 14,
    ):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.state = state
        self.cog = cog
        self.page_index = page_index
        self.total_pages = total_pages
        state._current_view = self  # every page is built right before it's shown

    def _footer(self) -> str:
        return f"Page {self.page_index} of {self.total_pages} • HighRollerClub Setup"

    def _build_embed(self) -> discord.Embed:
        raise NotImplementedError

    async def _render(self, interaction: discord.Interaction) -> None:
        embed = self._build_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "Only the admin who ran this command can use these buttons.", ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        # Only the page still on screen edits the message; older pages just expire.
        if self.state._current_view is not self or self.state._message is None:
            return
        try:
            await self.state._message.edit(
                content="⌛ The setup wizard timed out. Unsaved changes were discarded.", view=self
            )
        except discord.HTTPException:
            pass


# ---------------------------------------------------------------------------
# Page 1 — Payment Mode
# ---------------------------------------------------------------------------

class _Page1PaymentMode(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=1)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()

        chips_btn = discord.ui.Button(
            label="🪙 House Chips",
            style=discord.ButtonStyle.green if self.state.payment_mode == "chips" else discord.ButtonStyle.grey,
            row=0,
        )
        chips_btn.callback = self._select_chips
        self.add_item(chips_btn)

        bank_btn = discord.ui.Button(
            label="🏦 Server Currency",
            style=discord.ButtonStyle.green if self.state.payment_mode == "bank" else discord.ButtonStyle.grey,
            row=0,
        )
        bank_btn.callback = self._select_bank
        self.add_item(bank_btn)

        if self.state.payment_mode == "chips":
            rate_btn = discord.ui.Button(label=f"Set Rate ({self.state.discord_currency_conversion_rate}:1)", style=discord.ButtonStyle.blurple, row=1)
            rate_btn.callback = self._set_rate
            self.add_item(rate_btn)

            conv_style = discord.ButtonStyle.green if self.state.discord_currency_conversion_enabled else discord.ButtonStyle.grey
            conv_label = "✅ Conversion Enabled" if self.state.discord_currency_conversion_enabled else "❌ Conversion Disabled"
            conv_btn = discord.ui.Button(label=conv_label, style=conv_style, row=1)
            conv_btn.callback = self._toggle_conversion
            self.add_item(conv_btn)

        next_btn = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        next_btn.callback = self._go_next
        self.add_item(next_btn)

        save_btn = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save_btn.callback = self._save_exit
        self.add_item(save_btn)

    def _build_embed(self) -> discord.Embed:
        mode_str = "House Chips 🪙" if self.state.payment_mode == "chips" else "Server Currency 🏦"
        e = discord.Embed(title="Payment Setup", color=PALETTE_GOLD)
        e.add_field(name="Current Mode", value=mode_str, inline=False)
        if self.state.payment_mode == "chips":
            e.add_field(name="Chip Rate", value=f"{self.state.discord_currency_conversion_rate:,} chips per 1 server currency unit", inline=False)
            conv_str = "✅ Enabled — players can cash chips out to server currency" if self.state.discord_currency_conversion_enabled else "❌ Disabled"
            e.add_field(name="Chip Conversion", value=conv_str, inline=False)
        e.set_footer(text=self._footer())
        return e

    async def _select_chips(self, interaction: discord.Interaction) -> None:
        self.state.payment_mode = "chips"
        self._add_buttons()
        await self._render(interaction)

    async def _select_bank(self, interaction: discord.Interaction) -> None:
        self.state.payment_mode = "bank"
        self._add_buttons()
        await self._render(interaction)

    async def _set_rate(self, interaction: discord.Interaction) -> None:
        modal = _SingleInputModal("Chip Conversion Rate", "Chips per 1 server currency unit", placeholder="e.g. 100", default=str(self.state.discord_currency_conversion_rate))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.value:
            try:
                val = int(modal.value)
                if val < 1:
                    raise ValueError
                self.state.discord_currency_conversion_rate = val
            except ValueError:
                pass
        self._add_buttons()
        embed = self._build_embed()
        await safe_edit_original_response(interaction, embed=embed, view=self)

    async def _toggle_conversion(self, interaction: discord.Interaction) -> None:
        self.state.discord_currency_conversion_enabled = not self.state.discord_currency_conversion_enabled
        self._add_buttons()
        await self._render(interaction)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page2RankProgression(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 2 — Rank Progression
# ---------------------------------------------------------------------------

class _Page2RankProgression(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=2)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        for label, attr, rank_name in [
            ("Set Regular Threshold", "rank2_threshold", "Regular"),
            ("Set High Roller Threshold", "rank3_threshold", "High Roller"),
            ("Set Whale Threshold", "rank4_threshold", "The Whale"),
        ]:
            btn = discord.ui.Button(label=label, style=discord.ButtonStyle.blurple, row=0)
            btn.callback = self._make_threshold_cb(attr, rank_name)
            self.add_item(btn)

        win_btn = discord.ui.Button(label="Set Win Points", style=discord.ButtonStyle.blurple, row=1)
        win_btn.callback = self._set_win_points
        self.add_item(win_btn)

        loss_btn = discord.ui.Button(label="Set Loss Points", style=discord.ButtonStyle.blurple, row=1)
        loss_btn.callback = self._set_loss_points
        self.add_item(loss_btn)

        self._add_nav(back_cb=self._go_back, next_cb=self._go_next)

    def _add_nav(self, back_cb, next_cb) -> None:
        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = back_cb
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = next_cb
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Rank Progression", color=PALETTE_GOLD)
        e.description = "Rank is fluid — players promote and demote based on their current prestige point total. There is no floor between ranks."
        e.add_field(name="Regular Threshold", value=f"{self.state.rank2_threshold:,} pts", inline=True)
        e.add_field(name="High Roller Threshold", value=f"{self.state.rank3_threshold:,} pts", inline=True)
        e.add_field(name="Whale Threshold", value=f"{self.state.rank4_threshold:,} pts", inline=True)
        e.add_field(name="Win Points", value=f"+{self.state.prestige_win_points}", inline=True)
        e.add_field(name="Loss Points", value=f"-{self.state.prestige_loss_points}", inline=True)
        e.set_footer(text=self._footer())
        return e

    def _make_threshold_cb(self, attr: str, rank_name: str):
        async def cb(interaction: discord.Interaction) -> None:
            modal = _SingleInputModal(f"{rank_name} Threshold", "Prestige points required", placeholder="e.g. 50", default=str(getattr(self.state, attr)))
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.value:
                try:
                    val = int(modal.value)
                    if val < 1:
                        raise ValueError
                    trial = {k: getattr(self.state, k) for k in ("rank2_threshold", "rank3_threshold", "rank4_threshold")}
                    trial[attr] = val
                    error = _threshold_order_error(trial["rank2_threshold"], trial["rank3_threshold"], trial["rank4_threshold"])
                    if error:
                        await interaction.followup.send(f"❌ {error}", ephemeral=True)
                    else:
                        setattr(self.state, attr, val)
                except ValueError:
                    pass
            embed = self._build_embed()
            await safe_edit_original_response(interaction, embed=embed, view=self)
        return cb

    async def _set_win_points(self, interaction: discord.Interaction) -> None:
        modal = _SingleInputModal("Win Points", "Prestige points per win (> 0)", placeholder="e.g. 1.0", default=str(self.state.prestige_win_points))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.value:
            try:
                val = float(modal.value)
                if val <= 0:
                    raise ValueError
                self.state.prestige_win_points = val
            except ValueError:
                pass
        embed = self._build_embed()
        await safe_edit_original_response(interaction, embed=embed, view=self)

    async def _set_loss_points(self, interaction: discord.Interaction) -> None:
        modal = _SingleInputModal("Loss Points", "Prestige points removed per loss (≥ 0)", placeholder="e.g. 0.75", default=str(self.state.prestige_loss_points))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.value:
            try:
                val = float(modal.value)
                if val < 0:
                    raise ValueError
                self.state.prestige_loss_points = val
            except ValueError:
                pass
        embed = self._build_embed()
        await safe_edit_original_response(interaction, embed=embed, view=self)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page1PaymentMode(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page3BetMultipliers(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 3 — Rank Bet Multipliers
# ---------------------------------------------------------------------------

class _Page3BetMultipliers(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=3)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        enabled = self.state.bet_multipliers_enabled
        toggle_label = "✅ Multipliers Enabled" if enabled else "❌ Multipliers Disabled"
        toggle_style = discord.ButtonStyle.green if enabled else discord.ButtonStyle.grey
        toggle = discord.ui.Button(label=toggle_label, style=toggle_style, row=0)
        toggle.callback = self._toggle_multipliers
        self.add_item(toggle)

        for rank, attr in [(2, "rank2_multiplier"), (3, "rank3_multiplier"), (4, "rank4_multiplier")]:
            val = getattr(self.state, attr)
            btn = discord.ui.Button(
                label=f"{RANK_NAMES[rank]}: {val}x",
                style=discord.ButtonStyle.blurple,
                disabled=not enabled,
                row=1,
            )
            btn.callback = self._make_multiplier_cb(attr, RANK_NAMES[rank])
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Bet Limit Multipliers", color=PALETTE_GOLD)
        if not self.state.bet_multipliers_enabled:
            e.description = "Ranks are cosmetic only — all players bet at base limits."
        rows = [
            f"Member: {self.state.rank1_multiplier}x (fixed)",
            f"Regular: {self.state.rank2_multiplier}x",
            f"High Roller: {self.state.rank3_multiplier}x",
            f"The Whale: {self.state.rank4_multiplier}x",
        ]
        e.add_field(name="Current Multipliers", value="\n".join(rows), inline=False)
        e.set_footer(text=self._footer())
        return e

    def _make_multiplier_cb(self, attr: str, rank_name: str):
        async def cb(interaction: discord.Interaction) -> None:
            modal = _SingleInputModal(f"{rank_name} Multiplier", "Multiplier (1.0–10.0)", placeholder="e.g. 2.0", default=str(getattr(self.state, attr)))
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.value:
                try:
                    val = float(modal.value)
                    if not 1.0 <= val <= 10.0:
                        raise ValueError
                    setattr(self.state, attr, val)
                except ValueError:
                    pass
            self._add_buttons()
            embed = self._build_embed()
            await safe_edit_original_response(interaction, embed=embed, view=self)
        return cb

    async def _toggle_multipliers(self, interaction: discord.Interaction) -> None:
        self.state.bet_multipliers_enabled = not self.state.bet_multipliers_enabled
        self._add_buttons()
        await self._render(interaction)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page2RankProgression(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page4BetLimits(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 4 — Base Bet Limits
# ---------------------------------------------------------------------------

_BET_LIMIT_GAMES = [s for s in GAME_SLUGS if s in DEFAULT_BET_LIMITS] + ["horserace_win", "horserace_place"]
_BET_LIMIT_LABELS = {"horserace_win": "Horse Racing (Win)", "horserace_place": "Horse Racing (Place)"}


def _limit_label(slug: str) -> str:
    return _BET_LIMIT_LABELS.get(slug, slug.title())


class _Page4BetLimits(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=4)
        self._selected_game: str | None = None
        self._add_items()

    def _add_items(self) -> None:
        self.clear_items()

        options = [
            discord.SelectOption(label=_limit_label(slug), value=slug)
            for slug in _BET_LIMIT_GAMES
        ]
        select = discord.ui.Select(placeholder="Select a game to configure limits…", options=options, row=0)
        select.callback = self._on_game_select
        self.add_item(select)

        if self._selected_game:
            edit_btn = discord.ui.Button(label=f"Edit {_limit_label(self._selected_game)} Limits", style=discord.ButtonStyle.blurple, row=1)
            edit_btn.callback = self._edit_limits
            self.add_item(edit_btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Game Bet Limits", color=PALETTE_GOLD)
        lines = []
        for slug in _BET_LIMIT_GAMES:
            limits = self.state.game_bet_limits.get(slug) or DEFAULT_BET_LIMITS[slug]
            lines.append(f"**{_limit_label(slug)}**: {limits['min']:,} – {limits['max']:,}")
        e.add_field(name="Current Limits", value="\n".join(lines), inline=False)
        e.set_footer(text=self._footer())
        return e

    async def _on_game_select(self, interaction: discord.Interaction) -> None:
        self._selected_game = interaction.data["values"][0]  # type: ignore[index]
        self._add_items()
        await self._render(interaction)

    async def _edit_limits(self, interaction: discord.Interaction) -> None:
        slug = self._selected_game
        current = self.state.game_bet_limits.get(slug) or DEFAULT_BET_LIMITS.get(slug, {"min": 10, "max": 500})

        modal = _BetLimitsModal(_limit_label(slug), current["min"], current["max"])
        await interaction.response.send_modal(modal)
        if await modal.wait() or modal.values is None:
            return  # closed, timed out or invalid (the modal already explained why)
        low, high = modal.values
        self.state.game_bet_limits[slug] = {"min": low, "max": high}
        self._add_items()
        await safe_edit_original_response(interaction, embed=self._build_embed(), view=self)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page3BetMultipliers(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page5AllinTier(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 5 — All-In Tier Cap
# ---------------------------------------------------------------------------

class _Page5AllinTier(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=5)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        for tier in range(1, 6):
            style = discord.ButtonStyle.green if tier == self.state.allin_max_tier else discord.ButtonStyle.grey
            btn = discord.ui.Button(label=str(tier), style=style, row=0)
            btn.callback = self._make_tier_cb(tier)
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="All-In Risk Settings", color=PALETTE_GOLD)
        lines = []
        for tier_num, tier_data in ALLIN_RISK_TIERS.items():
            marker = "✅" if tier_num <= self.state.allin_max_tier else "🔒"
            key = f"tier{tier_num}_win_chance"
            chance = self.state.game_rng_settings.get("allin", {}).get(key, CONFIGURABLE_RNG["allin"][key]["default"])
            lines.append(f"{marker} Tier {tier_num}: {tier_data['name']} — {chance:.0%} win, {tier_data['payout']}x payout")
        e.add_field(name="Risk Tiers", value="\n".join(lines), inline=False)
        e.add_field(name="Current Cap", value=f"Tier {self.state.allin_max_tier} — {ALLIN_RISK_TIERS[self.state.allin_max_tier]['name']}", inline=False)
        e.set_footer(text=self._footer())
        return e

    def _make_tier_cb(self, tier: int):
        async def cb(interaction: discord.Interaction) -> None:
            self.state.allin_max_tier = tier
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page4BetLimits(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page6ScratchCards(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 6 — Scratch Cards
# ---------------------------------------------------------------------------

class _Page6ScratchCards(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=6)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()

        enabled = self.state.scratch_enabled
        toggle = discord.ui.Button(
            label="✅ Enabled" if enabled else "❌ Disabled",
            style=discord.ButtonStyle.green if enabled else discord.ButtonStyle.grey,
            row=0,
        )
        toggle.callback = self._toggle
        self.add_item(toggle)

        for hours, label in [(12, "12h"), (24, "24h"), (48, "48h")]:
            style = discord.ButtonStyle.green if self.state.scratch_cooldown_hours == hours else discord.ButtonStyle.grey
            btn = discord.ui.Button(label=label, style=style, row=1)
            btn.callback = self._make_cooldown_cb(hours)
            self.add_item(btn)

        custom = discord.ui.Button(label="Custom…", style=discord.ButtonStyle.blurple, row=1)
        custom.callback = self._custom_cooldown
        self.add_item(custom)

        for reward in SCRATCH_REWARD_OPTIONS:
            active = reward in self.state.scratch_reward_pool
            btn = discord.ui.Button(
                label=reward.replace("_", " ").title(),
                style=discord.ButtonStyle.green if active else discord.ButtonStyle.grey,
                row=2,
            )
            btn.callback = self._make_reward_cb(reward)
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Scratch Card Rewards", color=PALETTE_GOLD)
        e.add_field(name="Status", value="✅ Enabled" if self.state.scratch_enabled else "❌ Disabled", inline=True)
        e.add_field(name="Cooldown", value=f"{self.state.scratch_cooldown_hours}h", inline=True)
        pool_str = ", ".join(self.state.scratch_reward_pool) if self.state.scratch_reward_pool else "None selected"
        e.add_field(name="Reward Pool", value=pool_str, inline=False)
        e.set_footer(text=self._footer())
        return e

    async def _toggle(self, interaction: discord.Interaction) -> None:
        self.state.scratch_enabled = not self.state.scratch_enabled
        self._add_buttons()
        await self._render(interaction)

    def _make_cooldown_cb(self, hours: int):
        async def cb(interaction: discord.Interaction) -> None:
            self.state.scratch_cooldown_hours = hours
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _custom_cooldown(self, interaction: discord.Interaction) -> None:
        modal = _SingleInputModal("Custom Cooldown", "Hours (1–168)", placeholder="e.g. 36", default=str(self.state.scratch_cooldown_hours))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.value:
            try:
                val = int(modal.value)
                if not 1 <= val <= 168:
                    raise ValueError
                self.state.scratch_cooldown_hours = val
            except ValueError:
                pass
        self._add_buttons()
        embed = self._build_embed()
        await safe_edit_original_response(interaction, embed=embed, view=self)

    def _make_reward_cb(self, reward: str):
        async def cb(interaction: discord.Interaction) -> None:
            if reward in self.state.scratch_reward_pool:
                self.state.scratch_reward_pool.remove(reward)
            else:
                self.state.scratch_reward_pool.append(reward)
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page5AllinTier(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page7MysteryWheel(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Timezone Select Sub-Page
# ---------------------------------------------------------------------------

_COMMON_TIMEZONES: list[tuple[str, str]] = [
    ("🇺🇸 US Eastern",           "America/New_York"),
    ("🇺🇸 US Central",           "America/Chicago"),
    ("🇺🇸 US Mountain",          "America/Denver"),
    ("🇺🇸 US Arizona (no DST)",  "America/Phoenix"),
    ("🇺🇸 US Pacific",           "America/Los_Angeles"),
    ("🇺🇸 US Alaska",            "America/Anchorage"),
    ("🇺🇸 US Hawaii",            "Pacific/Honolulu"),
    ("🇨🇦 Canada Eastern",       "America/Toronto"),
    ("🇨🇦 Canada Pacific",       "America/Vancouver"),
    ("🇧🇷 Brazil (São Paulo)",   "America/Sao_Paulo"),
    ("🇦🇷 Argentina",            "America/Argentina/Buenos_Aires"),
    ("🇬🇧 UK / Ireland",         "Europe/London"),
    ("🇪🇺 Central Europe",       "Europe/Paris"),
    ("🇪🇺 Eastern Europe",       "Europe/Helsinki"),
    ("🇷🇺 Moscow",               "Europe/Moscow"),
    ("🇮🇳 India",                "Asia/Kolkata"),
    ("🇦🇪 Gulf / UAE",           "Asia/Dubai"),
    ("🇮🇱 Israel",               "Asia/Jerusalem"),
    ("🇿🇦 South Africa",         "Africa/Johannesburg"),
    ("🇨🇳 China / Singapore",    "Asia/Shanghai"),
    ("🇯🇵 Japan / Korea",        "Asia/Tokyo"),
    ("🇦🇺 Australia Eastern",    "Australia/Sydney"),
    ("🇦🇺 Australia Western",    "Australia/Perth"),
    ("🇳🇿 New Zealand",          "Pacific/Auckland"),
]


class _TimezoneSelectView(discord.ui.View):
    """Sub-page for selecting a timezone via dropdown."""

    def __init__(self, ctx: commands.Context, state: _WizardState, cog: MixinMeta) -> None:
        super().__init__(timeout=300)
        self.ctx = ctx
        self.state = state
        self.cog = cog

        options = [
            discord.SelectOption(
                label=label,
                value=tz,
                description=tz,
                default=(tz == state.mystery_wheel_timezone),
            )
            for label, tz in _COMMON_TIMEZONES
        ]
        options.append(discord.SelectOption(
            label="Other (enter manually)\u2026",
            value="__manual__",
            description="Type a custom IANA timezone string",
        ))

        self.tz_select = discord.ui.Select(
            placeholder="Select a timezone\u2026",
            options=options,
            min_values=1,
            max_values=1,
            row=0,
        )
        self.tz_select.callback = self._on_select
        self.add_item(self.tz_select)

        back = discord.ui.Button(label="\u2190 Back", style=discord.ButtonStyle.grey, row=1)
        back.callback = self._go_back
        self.add_item(back)

    def _build_embed(self) -> discord.Embed:
        current = self.state.mystery_wheel_timezone
        e = discord.Embed(
            title="Select Timezone",
            description=(
                "Choose the timezone used to determine when the Daily Free Spin resets at midnight.\n\n"
                f"**Current:** `{current}`"
            ),
            color=PALETTE_GOLD,
        )
        return e

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This menu isn't for you.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        chosen = self.tz_select.values[0]
        if chosen == "__manual__":
            modal = _SingleInputModal(
                "Custom Timezone",
                "IANA Timezone String",
                placeholder="e.g. America/New_York",
                default=self.state.mystery_wheel_timezone,
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.value and modal.value in zoneinfo.available_timezones():
                self.state.mystery_wheel_timezone = modal.value
                view = _Page7MysteryWheel(self.ctx, self.state, self.cog)
                await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)
            elif modal.value:
                await interaction.followup.send(
                    f"\u274c `{modal.value}` is not a recognised IANA timezone. No change made.",
                    ephemeral=True,
                )
        else:
            self.state.mystery_wheel_timezone = chosen
            view = _Page7MysteryWheel(self.ctx, self.state, self.cog)
            await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page7MysteryWheel(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)


# ---------------------------------------------------------------------------
# Page 7 — Mystery Wheel
# ---------------------------------------------------------------------------

class _Page7MysteryWheel(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=7)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()

        enabled = self.state.mystery_wheel_enabled
        toggle = discord.ui.Button(
            label="✅ Enabled" if enabled else "❌ Disabled",
            style=discord.ButtonStyle.green if enabled else discord.ButtonStyle.grey,
            row=0,
        )
        toggle.callback = self._toggle
        self.add_item(toggle)

        tz_btn = discord.ui.Button(label=f"Timezone: {self.state.mystery_wheel_timezone}", style=discord.ButtonStyle.blurple, row=0)
        tz_btn.callback = self._set_timezone
        self.add_item(tz_btn)

        for reward in SCRATCH_REWARD_OPTIONS:
            active = reward in self.state.mystery_wheel_reward_pool
            btn = discord.ui.Button(
                label=reward.replace("_", " ").title(),
                style=discord.ButtonStyle.green if active else discord.ButtonStyle.grey,
                row=1,
            )
            btn.callback = self._make_reward_cb(reward)
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Daily Free Spin", color=PALETTE_GOLD)
        e.add_field(name="Status", value="✅ Enabled" if self.state.mystery_wheel_enabled else "❌ Disabled", inline=True)
        e.add_field(name="Timezone", value=self.state.mystery_wheel_timezone, inline=True)
        pool_str = ", ".join(self.state.mystery_wheel_reward_pool) if self.state.mystery_wheel_reward_pool else "None selected"
        e.add_field(name="Reward Pool", value=pool_str, inline=False)
        e.set_footer(text=self._footer())
        return e

    async def _toggle(self, interaction: discord.Interaction) -> None:
        self.state.mystery_wheel_enabled = not self.state.mystery_wheel_enabled
        # One switch for players: the Game Availability toggle follows this one.
        self.state.games_enabled["mysteryspin"] = self.state.mystery_wheel_enabled
        self._add_buttons()
        await self._render(interaction)

    async def _set_timezone(self, interaction: discord.Interaction) -> None:
        view = _TimezoneSelectView(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    def _make_reward_cb(self, reward: str):
        async def cb(interaction: discord.Interaction) -> None:
            if reward in self.state.mystery_wheel_reward_pool:
                self.state.mystery_wheel_reward_pool.remove(reward)
            else:
                self.state.mystery_wheel_reward_pool.append(reward)
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page6ScratchCards(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page8MultiplierWheel(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 8 — Multiplier Wheel
# ---------------------------------------------------------------------------

class _Page8MultiplierWheel(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=8)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()

        cost_btn = discord.ui.Button(label=f"Spin Cost: {self.state.multiplier_wheel_cost:,}", style=discord.ButtonStyle.blurple, row=0)
        cost_btn.callback = self._set_cost
        self.add_item(cost_btn)

        for minutes, label in [(15, "15 min"), (30, "30 min"), (60, "60 min")]:
            style = discord.ButtonStyle.green if self.state.multiplier_wheel_expiry_minutes == minutes else discord.ButtonStyle.grey
            btn = discord.ui.Button(label=label, style=style, row=1)
            btn.callback = self._make_expiry_cb(minutes)
            self.add_item(btn)

        custom = discord.ui.Button(label="Custom…", style=discord.ButtonStyle.blurple, row=1)
        custom.callback = self._custom_expiry
        self.add_item(custom)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Multiplier Wheel — The Booster", color=PALETTE_GOLD)
        e.add_field(name="Spin Cost", value=f"{self.state.multiplier_wheel_cost:,} chips/currency", inline=True)
        e.add_field(name="Multiplier Expiry", value=f"{self.state.multiplier_wheel_expiry_minutes} minutes", inline=True)
        e.set_footer(text=self._footer())
        return e

    async def _set_cost(self, interaction: discord.Interaction) -> None:
        modal = _SingleInputModal("Spin Cost", "Cost to spin (min 1)", placeholder="e.g. 100", default=str(self.state.multiplier_wheel_cost))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.value:
            try:
                val = int(modal.value)
                if val < 1:
                    raise ValueError
                self.state.multiplier_wheel_cost = val
            except ValueError:
                pass
        self._add_buttons()
        embed = self._build_embed()
        await safe_edit_original_response(interaction, embed=embed, view=self)

    def _make_expiry_cb(self, minutes: int):
        async def cb(interaction: discord.Interaction) -> None:
            self.state.multiplier_wheel_expiry_minutes = minutes
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _custom_expiry(self, interaction: discord.Interaction) -> None:
        modal = _SingleInputModal("Custom Expiry", "Minutes (1–1440)", placeholder="e.g. 45", default=str(self.state.multiplier_wheel_expiry_minutes))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.value:
            try:
                val = int(modal.value)
                if not 1 <= val <= 1440:
                    raise ValueError
                self.state.multiplier_wheel_expiry_minutes = val
            except ValueError:
                pass
        self._add_buttons()
        embed = self._build_embed()
        await safe_edit_original_response(interaction, embed=embed, view=self)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page7MysteryWheel(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page9BigSix(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 9 — Big Six Wheel
# ---------------------------------------------------------------------------

class _Page9BigSix(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=9)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        for count in BIG6_HOUSE_SEGMENT_OPTIONS:
            style = discord.ButtonStyle.green if self.state.big6_house_segments == count else discord.ButtonStyle.grey
            btn = discord.ui.Button(label=str(count), style=style, row=0)
            btn.callback = self._make_seg_cb(count)
            self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        house = self.state.big6_house_segments
        total = house + BIG6_FIXED_SEGMENTS
        e = discord.Embed(title="Big Six Wheel — House Edge", color=PALETTE_GOLD)
        e.add_field(name="House Segments", value=str(house), inline=True)
        e.add_field(name="Total Segments", value=str(total), inline=True)

        prob_lines = []
        for seg_name, count in BIG6_DEFAULT_SEGMENTS.items():
            if seg_name == "house":
                continue
            pct = count / total * 100
            payout = BIG6_PAYOUTS.get(seg_name, 0)
            rtp = count * (payout + 1) / total * 100
            prob_lines.append(f"{seg_name}: {pct:.1f}% → pays {payout}:1 (returns {rtp:.0f}%)")
        e.add_field(name="Win Probabilities", value="\n".join(prob_lines), inline=False)
        e.set_footer(text=self._footer())
        return e

    def _make_seg_cb(self, count: int):
        async def cb(interaction: discord.Interaction) -> None:
            self.state.big6_house_segments = count
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page8MultiplierWheel(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page10RNGSettings(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 10 — RNG Settings
# ---------------------------------------------------------------------------

_RNG_GAMES = [s for s in GAME_SLUGS if s in CONFIGURABLE_RNG]

class _Page10RNGSettings(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=10)
        self._selected_game: str | None = None
        self._add_items()

    def _add_items(self) -> None:
        self.clear_items()

        options = [discord.SelectOption(label=slug.title(), value=slug) for slug in _RNG_GAMES]
        select = discord.ui.Select(placeholder="Select a game to tune…", options=options, row=0)
        select.callback = self._on_game_select
        self.add_item(select)

        if self._selected_game:
            params = CONFIGURABLE_RNG[self._selected_game]
            overrides = self.state.game_rng_settings.get(self._selected_game, {})
            for idx, (key, meta) in enumerate(params.items()):
                current = overrides.get(key, meta["default"])
                btn = discord.ui.Button(
                    label=f"Edit {key}: {current}",
                    style=discord.ButtonStyle.blurple,
                    row=1 + (idx // 4),
                )
                btn.callback = self._make_param_cb(self._selected_game, key, meta)
                self.add_item(btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Win Chance Tuning", color=PALETTE_GOLD)
        e.description = "Card-based games (Blackjack, Hi-Lo, War, Video Poker, Poker) use fixed deck math and are not configurable here."
        if self._selected_game:
            params = CONFIGURABLE_RNG[self._selected_game]
            overrides = self.state.game_rng_settings.get(self._selected_game, {})
            for key, meta in params.items():
                current = overrides.get(key, meta["default"])
                e.add_field(
                    name=key,
                    value=f"Current: **{current}** | Range: {meta['min']}–{meta['max']}\n{meta['description']}",
                    inline=False,
                )
        e.set_footer(text=self._footer())
        return e

    async def _on_game_select(self, interaction: discord.Interaction) -> None:
        self._selected_game = interaction.data["values"][0]  # type: ignore[index]
        self._add_items()
        await self._render(interaction)

    def _make_param_cb(self, slug: str, key: str, meta: dict):
        async def cb(interaction: discord.Interaction) -> None:
            current = self.state.game_rng_settings.get(slug, {}).get(key, meta["default"])
            modal = _SingleInputModal(
                f"Edit {key}",
                f"{key} (range: {meta['min']}–{meta['max']})",
                placeholder=f"Current: {current}",
                default=str(current),
            )
            await interaction.response.send_modal(modal)
            await modal.wait()
            if modal.value:
                try:
                    raw = modal.value
                    val: int | float | list
                    if meta["type"] is float:
                        val = float(raw)
                    elif meta["type"] is int:
                        val = int(raw)
                    else:
                        val = [int(x.strip()) for x in raw.split(",")]
                    # Validate bounds
                    if meta["type"] is list:
                        if len(val) != len(meta["default"]) or any(v < meta["min"] or v > meta["max"] for v in val):  # type: ignore[union-attr]
                            raise ValueError
                    else:
                        if not (meta["min"] <= val <= meta["max"]):  # type: ignore[operator]
                            raise ValueError
                    self.state.game_rng_settings.setdefault(slug, {})[key] = val
                except ValueError:
                    await interaction.followup.send(
                        f"Value out of range or invalid. Allowed: {meta['min']}–{meta['max']}.", ephemeral=True
                    )
            self._add_items()
            embed = self._build_embed()
            await safe_edit_original_response(interaction, embed=embed, view=self)
        return cb

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page9BigSix(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page11GameToggles(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 11 — Game Toggles
# ---------------------------------------------------------------------------

class _Page11GameToggles(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=11)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        for idx, slug in enumerate(GAME_SLUGS):
            enabled = self.state.games_enabled.get(slug, True)
            btn = discord.ui.Button(
                label=f"{'✅' if enabled else '🔒'} {slug.title()}",
                style=discord.ButtonStyle.green if enabled else discord.ButtonStyle.grey,
                row=idx // 4,
            )
            btn.callback = self._make_toggle_cb(slug)
            self.add_item(btn)

        enable_all = discord.ui.Button(label="Enable All", style=discord.ButtonStyle.blurple, row=4)
        enable_all.callback = self._enable_all
        self.add_item(enable_all)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Game Availability", color=PALETTE_GOLD)
        e.description = "New servers start with every game switched off, so you choose what opens. Enable the games that fit your server. Disabled games appear locked on the Game Floor — player stats for those games are preserved."
        disabled = [s for s in GAME_SLUGS if not self.state.games_enabled.get(s, True)]
        e.add_field(name="Disabled Games", value=", ".join(disabled) if disabled else "None — all enabled", inline=False)
        e.set_footer(text=self._footer())
        return e

    def _make_toggle_cb(self, slug: str):
        async def cb(interaction: discord.Interaction) -> None:
            self.state.games_enabled[slug] = not self.state.games_enabled.get(slug, True)
            if slug == "mysteryspin":  # keep the Daily Free Spin switch in sync
                self.state.mystery_wheel_enabled = self.state.games_enabled[slug]
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _enable_all(self, interaction: discord.Interaction) -> None:
        for slug in GAME_SLUGS:
            self.state.games_enabled[slug] = True
        self.state.mystery_wheel_enabled = True
        self._add_buttons()
        await self._render(interaction)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page10RNGSettings(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page12ChannelLock(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Typed channel entry (fallback for the dropdowns)
# ---------------------------------------------------------------------------

def _resolve_text_channels(guild: discord.Guild, raw: str) -> tuple[list[discord.TextChannel], list[str]]:
    """Turn typed entries (#mention, ID or name; separated by commas or spaces) into text channels.

    Returns the channels found, in order without repeats, and an error line for each entry that
    didn't match exactly one text channel."""
    found: list[discord.TextChannel] = []
    problems: list[str] = []
    for entry in raw.replace(",", " ").split():
        token = entry.strip()
        if token.startswith("<#") and token.endswith(">"):
            token = token[2:-1]
        token = token.lstrip("#")
        if not token:
            continue
        if token.isdigit():
            channel = guild.get_channel(int(token))
            if isinstance(channel, discord.TextChannel):
                matches = [channel]
            else:
                matches = []
        else:
            needle = token.casefold()
            matches = [c for c in guild.text_channels if c.name.casefold() == needle]
        if len(matches) == 1:
            if matches[0] not in found:
                found.append(matches[0])
        elif len(matches) > 1:
            problems.append(f"`{entry}` matches {len(matches)} channels. Use its #mention or ID instead.")
        else:
            problems.append(f"`{entry}` isn't a text channel in this server.")
    return found, problems


class _ChannelEntryModal(discord.ui.Modal):
    """Type one or more channels by #mention, ID or name. Fills .channels on success."""

    def __init__(self, title: str, multiple: bool) -> None:
        super().__init__(title=title, timeout=300)
        self._multiple = multiple
        self.entry = discord.ui.TextInput(
            label="Channels (#mention, ID or name)" if multiple else "Channel (#mention, ID or name)",
            placeholder="general, 123456789012345678, #casino" if multiple else "#casino  or  123456789012345678",
            style=discord.TextStyle.paragraph if multiple else discord.TextStyle.short,
            max_length=1000 if multiple else 100,
        )
        self.add_item(self.entry)
        self.channels: list[discord.TextChannel] | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        found, problems = _resolve_text_channels(interaction.guild, self.entry.value)
        if not self._multiple and len(found) > 1:
            problems.append("Enter just one channel here.")
        if problems or not found:
            lines = problems or ["No channel was entered."]
            await interaction.response.send_message(
                "❌ " + "\n❌ ".join(lines) + "\nNothing was changed.", ephemeral=True
            )
            return
        self.channels = found
        await interaction.response.defer()


# ---------------------------------------------------------------------------
# Channel Add Sub-Page
# ---------------------------------------------------------------------------

class _ChannelAddSelectView(discord.ui.View):
    """Sub-page for adding allowed channels via a dropdown of guild text channels."""

    PAGE_SIZE = 25

    def __init__(
        self,
        ctx: commands.Context,
        state: _WizardState,
        cog: MixinMeta,
        page_index: int = 0,
    ) -> None:
        super().__init__(timeout=300)
        self.ctx = ctx
        self.state = state
        self.cog = cog

        self._channels = sorted(ctx.guild.text_channels, key=lambda c: c.position)
        self._page_count = max(1, (len(self._channels) + self.PAGE_SIZE - 1) // self.PAGE_SIZE)
        self._page_index = max(0, min(page_index, self._page_count - 1))
        self.ch_select: discord.ui.Select | None = None
        self._add_components()

    def _page_channels(self) -> list[discord.TextChannel]:
        start = self._page_index * self.PAGE_SIZE
        end = start + self.PAGE_SIZE
        return self._channels[start:end]

    def _add_components(self) -> None:
        self.clear_items()

        channels = self._page_channels()
        if channels:
            options = [
                discord.SelectOption(
                    label=f"#{c.name}",
                    value=str(c.id),
                    description=f"ID: {c.id}",
                    default=(c.id in self.state.allowed_channels),
                )
                for c in channels
            ]
            self.ch_select: discord.ui.Select | None = discord.ui.Select(
                placeholder="Select channels to allow\u2026",
                options=options,
                min_values=1,
                max_values=len(options),
                row=0,
            )
            self.ch_select.callback = self._on_select
            self.add_item(self.ch_select)
        else:
            self.ch_select = None

        prev_btn = discord.ui.Button(
            label="← Previous",
            style=discord.ButtonStyle.grey,
            disabled=self._page_index == 0,
            row=1,
        )
        prev_btn.callback = self._previous_page
        self.add_item(prev_btn)

        next_btn = discord.ui.Button(
            label="Next →",
            style=discord.ButtonStyle.grey,
            disabled=self._page_index >= self._page_count - 1,
            row=1,
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)

        type_btn = discord.ui.Button(label="\u2328\ufe0f Type Channels", style=discord.ButtonStyle.blurple, row=2)
        type_btn.callback = self._type_channels
        self.add_item(type_btn)

        back = discord.ui.Button(label="\u2190 Back", style=discord.ButtonStyle.grey, row=2)
        back.callback = self._go_back
        self.add_item(back)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(
            title="Add Allowed Channels",
            description=(
                "Select one or more channels the casino should be restricted to.\n"
                "Players will only be able to use the club in these channels.\n\n"
                "Can't find a channel? Press **\u2328\ufe0f Type Channels** and enter #mentions, IDs or names."
            ),
            color=PALETTE_GOLD,
        )
        selected_count = len(self.state.allowed_channels)
        e.add_field(
            name="Selection Progress",
            value=f"Page **{self._page_index + 1} / {self._page_count}**\nSelected channels: **{selected_count}**",
            inline=False,
        )
        if not self._channels:
            e.add_field(name="Available Channels", value="No text channels found in this server.", inline=False)
        e.set_footer(text="Select channels on this page, then use Previous/Next to browse the rest.")
        return e

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This menu isn't for you.", ephemeral=True)
            return False
        return True

    async def _on_select(self, interaction: discord.Interaction) -> None:
        for val in self.ch_select.values:
            cid = int(val)
            if cid not in self.state.allowed_channels:
                self.state.allowed_channels.append(cid)
        self._add_components()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _type_channels(self, interaction: discord.Interaction) -> None:
        modal = _ChannelEntryModal("Add Allowed Channels", multiple=True)
        await interaction.response.send_modal(modal)
        if await modal.wait() or modal.channels is None:
            return
        for channel in modal.channels:
            if channel.id not in self.state.allowed_channels:
                self.state.allowed_channels.append(channel.id)
        self._add_components()
        await safe_edit_original_response(interaction, embed=self._build_embed(), view=self)

    async def _previous_page(self, interaction: discord.Interaction) -> None:
        self._page_index = max(0, self._page_index - 1)
        self._add_components()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _next_page(self, interaction: discord.Interaction) -> None:
        self._page_index = min(self._page_count - 1, self._page_index + 1)
        self._add_components()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page12ChannelLock(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)


# ---------------------------------------------------------------------------
# Page 12 — Channel Lock
# ---------------------------------------------------------------------------

class _Page12ChannelLock(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=12)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()

        add_btn = discord.ui.Button(label="Add Channel", style=discord.ButtonStyle.blurple, row=0)
        add_btn.callback = self._add_channel
        self.add_item(add_btn)

        clear_btn = discord.ui.Button(label="Clear All", style=discord.ButtonStyle.red, row=0)
        clear_btn.callback = self._clear_channels
        self.add_item(clear_btn)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Review & Save →", style=discord.ButtonStyle.green, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(title="Channel Restrictions", color=PALETTE_GOLD)
        if self.state.allowed_channels:
            channel_list = "\n".join(f"<#{c}>" for c in self.state.allowed_channels)
            e.add_field(name="Locked To", value=channel_list, inline=False)
        else:
            e.add_field(name="Locked To", value="All channels allowed", inline=False)
        e.set_footer(text=self._footer())
        return e

    async def _add_channel(self, interaction: discord.Interaction) -> None:
        view = _ChannelAddSelectView(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _clear_channels(self, interaction: discord.Interaction) -> None:
        self.state.allowed_channels.clear()
        self._add_buttons()
        await self._render(interaction)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page11GameToggles(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page13HorseRacing(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 13 — Horse Racing
# ---------------------------------------------------------------------------

# (setting, label, min, max)
_RACE_SETTINGS: list[tuple[str, str, int, int]] = [
    ("horserace_house_cut_pct", "House cut on pools (%)", 0, 25),
    ("horserace_countdown_minutes", "Betting countdown (minutes)", 2, 10),
    ("horserace_cooldown_minutes", "Starter cooldown (minutes)", 0, 1440),
    ("horserace_house_line_return_pct", "Solo race return (%)", 50, 95),
]


class _RaceSettingsModal(discord.ui.Modal):
    """All four Horse Racing numbers in one modal."""

    def __init__(self, state: "_WizardState"):
        super().__init__(title="Horse Racing Settings", timeout=300)
        self.inputs: dict[str, discord.ui.TextInput] = {}
        for key, label, low, high in _RACE_SETTINGS:
            field = discord.ui.TextInput(label=f"{label} ({low}–{high})", default=str(getattr(state, key)), max_length=5)
            self.inputs[key] = field
            self.add_item(field)
        self.values: dict[str, int] | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        values: dict[str, int] = {}
        for key, label, low, high in _RACE_SETTINGS:
            raw = self.inputs[key].value.strip()
            if not raw.isdigit() or not low <= int(raw) <= high:
                await interaction.response.send_message(
                    f"❌ {label} must be a whole number from {low} to {high}. Nothing was changed.", ephemeral=True
                )
                return
            values[key] = int(raw)
        self.values = values
        await interaction.response.defer()


class _Page13HorseRacing(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=13)
        self._add_buttons()

    def _add_buttons(self) -> None:
        self.clear_items()
        select = discord.ui.ChannelSelect(
            placeholder="Choose the race channel…",
            channel_types=[discord.ChannelType.text],
            row=0,
        )
        select.callback = self._on_channel
        self.add_item(select)

        type_btn = discord.ui.Button(label="⌨️ Type Channel", style=discord.ButtonStyle.blurple, row=1)
        type_btn.callback = self._type_channel
        self.add_item(type_btn)
        clear = discord.ui.Button(label="Clear Race Channel", style=discord.ButtonStyle.red, row=1,
                                  disabled=self.state.race_channel_id is None)
        clear.callback = self._clear_channel
        self.add_item(clear)
        edit = discord.ui.Button(label="Edit Race Settings", style=discord.ButtonStyle.blurple, row=1)
        edit.callback = self._edit_settings
        self.add_item(edit)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Next →", style=discord.ButtonStyle.blurple, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        s = self.state
        e = discord.Embed(title="Horse Racing", color=PALETTE_GOLD)
        e.description = (
            "Races are announced and run in the **race channel**, and Horse Racing stays closed until one "
            "is set. Switch the game on in Game Availability (page 11). Bet limits for Win and Place bets "
            "are on the Bet Limits page (page 4). Manage the horses with `hrcset race`."
        )
        channel = f"<#{s.race_channel_id}>" if s.race_channel_id else "Not set (Horse Racing is closed)"
        e.add_field(name="Race Channel", value=channel, inline=False)
        e.add_field(name="House Cut", value=f"{s.horserace_house_cut_pct}% of each pool", inline=True)
        e.add_field(name="Countdown", value=f"{s.horserace_countdown_minutes} min", inline=True)
        e.add_field(name="Starter Cooldown", value=f"{s.horserace_cooldown_minutes} min", inline=True)
        e.add_field(name="Solo Race Return", value=f"{s.horserace_house_line_return_pct}%", inline=True)
        e.set_footer(text=self._footer())
        return e

    async def _on_channel(self, interaction: discord.Interaction) -> None:
        self.state.race_channel_id = int(interaction.data["values"][0])  # type: ignore[index]
        self._add_buttons()
        await self._render(interaction)

    async def _type_channel(self, interaction: discord.Interaction) -> None:
        modal = _ChannelEntryModal("Race Channel", multiple=False)
        await interaction.response.send_modal(modal)
        if await modal.wait() or modal.channels is None:
            return
        self.state.race_channel_id = modal.channels[0].id
        self._add_buttons()
        await safe_edit_original_response(interaction, embed=self._build_embed(), view=self)

    async def _clear_channel(self, interaction: discord.Interaction) -> None:
        self.state.race_channel_id = None
        self._add_buttons()
        await self._render(interaction)

    async def _edit_settings(self, interaction: discord.Interaction) -> None:
        modal = _RaceSettingsModal(self.state)
        await interaction.response.send_modal(modal)
        if await modal.wait() or modal.values is None:
            return
        for key, value in modal.values.items():
            setattr(self.state, key, value)
        await safe_edit_original_response(interaction, embed=self._build_embed(), view=self)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page12ChannelLock(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _Page14Holdem(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Page 14 — Texas Hold'em
# ---------------------------------------------------------------------------

def _holdem_levels_error(tiers: list[HoldemStakeTier]) -> str | None:
    """At least one level must stay on, and Members must be able to open at least one."""
    if not any(t.enabled for t in tiers):
        return "At least one blind level has to stay on."
    if not any(t.enabled and t.min_rank == 1 for t in tiers):
        return "At least one level that's switched on must be open to Members, so everyone can open a table."
    return None


def _holdem_summary(tiers: list[HoldemStakeTier], action_seconds: int, min_bb: int, max_bb: int) -> str:
    on = [f"{t.sb:,}/{t.bb:,}" for t in tiers if t.enabled]
    return f"Levels: {', '.join(on) or 'none'} · {action_seconds}s to act · buy-in {min_bb}–{max_bb} BB"


class _HoldemBlindsModal(discord.ui.Modal):
    def __init__(self, level_no: int, tier: HoldemStakeTier):
        super().__init__(title=f"Hold'em Level {level_no} Blinds", timeout=300)
        self.sb_input = discord.ui.TextInput(label="Small blind", default=str(tier.sb), max_length=12)
        self.bb_input = discord.ui.TextInput(label="Big blind", default=str(tier.bb), max_length=12)
        self.add_item(self.sb_input)
        self.add_item(self.bb_input)
        self.values: tuple[int, int] | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        sb_raw = self.sb_input.value.replace(",", "").strip()
        bb_raw = self.bb_input.value.replace(",", "").strip()
        if not sb_raw.isdigit() or not bb_raw.isdigit() or int(sb_raw) < 1:
            await interaction.response.send_message("❌ Both blinds must be positive whole numbers. Nothing was changed.", ephemeral=True)
            return
        if int(sb_raw) >= int(bb_raw):
            await interaction.response.send_message("❌ The small blind must be less than the big blind. Nothing was changed.", ephemeral=True)
            return
        self.values = (int(sb_raw), int(bb_raw))
        await interaction.response.defer()


class _HoldemSettingsModal(discord.ui.Modal):
    def __init__(self, state: "_WizardState"):
        super().__init__(title="Hold'em Timer & Buy-ins", timeout=300)
        low, high = HOLDEM_ACTION_SECONDS_RANGE
        self.action_input = discord.ui.TextInput(label=f"Seconds to act ({low}–{high})", default=str(state.holdem_action_seconds), max_length=3)
        self.min_input = discord.ui.TextInput(label=f"Minimum buy-in, big blinds ({HOLDEM_BUYIN_FLOOR_BB}–500)", default=str(state.holdem_min_buyin_bb), max_length=4)
        self.max_input = discord.ui.TextInput(label="Maximum buy-in, big blinds (up to 1000)", default=str(state.holdem_max_buyin_bb), max_length=4)
        for item in (self.action_input, self.min_input, self.max_input):
            self.add_item(item)
        self.values: tuple[int, int, int] | None = None

    async def on_submit(self, interaction: discord.Interaction) -> None:
        low, high = HOLDEM_ACTION_SECONDS_RANGE
        raws = [self.action_input.value.strip(), self.min_input.value.strip(), self.max_input.value.strip()]
        if not all(r.isdigit() for r in raws):
            await interaction.response.send_message("❌ All three must be whole numbers. Nothing was changed.", ephemeral=True)
            return
        action, min_bb, max_bb = (int(r) for r in raws)
        error = None
        if not low <= action <= high:
            error = f"Seconds to act must be from {low} to {high}."
        elif not HOLDEM_BUYIN_FLOOR_BB <= min_bb <= 500:
            error = f"The minimum buy-in must be from {HOLDEM_BUYIN_FLOOR_BB} to 500 big blinds."
        elif not min_bb <= max_bb <= 1000:
            error = "The maximum buy-in must be at least the minimum, and at most 1000 big blinds."
        if error:
            await interaction.response.send_message(f"❌ {error} Nothing was changed.", ephemeral=True)
            return
        self.values = (action, min_bb, max_bb)
        await interaction.response.defer()


class _Page14Holdem(_WizardPageBase):
    def __init__(self, ctx, state, cog, selected: int = 0):
        super().__init__(ctx, state, cog, page_index=14)
        self.selected = selected
        self._add_buttons()

    def _tier(self) -> HoldemStakeTier:
        return self.state.holdem_stake_tiers[self.selected]

    def _add_buttons(self) -> None:
        self.clear_items()
        tiers = self.state.holdem_stake_tiers
        pick = discord.ui.Select(
            placeholder="Choose a blind level to edit…",
            options=[
                discord.SelectOption(
                    label=f"Level {i + 1}: {t.sb:,} / {t.bb:,}",
                    description=f"{RANK_NAMES.get(t.min_rank, '?')} and above · {'on' if t.enabled else 'off'}",
                    value=str(i),
                    default=i == self.selected,
                )
                for i, t in enumerate(tiers)
            ],
            row=0,
        )
        pick.callback = self._on_pick
        self.add_item(pick)

        tier = self._tier()
        edit = discord.ui.Button(label=f"Edit Level {self.selected + 1} Blinds", style=discord.ButtonStyle.blurple, row=1)
        edit.callback = self._edit_blinds
        self.add_item(edit)
        toggle = discord.ui.Button(
            label="Switch Off" if tier.enabled else "Switch On",
            style=discord.ButtonStyle.red if tier.enabled else discord.ButtonStyle.green,
            row=1,
        )
        toggle.callback = self._toggle
        self.add_item(toggle)
        reset = discord.ui.Button(label="Reset Levels", style=discord.ButtonStyle.grey, row=1)
        reset.callback = self._reset
        self.add_item(reset)

        rank = discord.ui.Select(
            placeholder=f"Rank needed to open level {self.selected + 1}…",
            options=[
                discord.SelectOption(label=f"{name} and above", value=str(r), default=r == tier.min_rank)
                for r, name in RANK_NAMES.items()
            ],
            row=2,
        )
        rank.callback = self._on_rank
        self.add_item(rank)

        settings = discord.ui.Button(label="Edit Timer & Buy-ins", style=discord.ButtonStyle.blurple, row=3)
        settings.callback = self._edit_settings
        self.add_item(settings)

        back = discord.ui.Button(label="← Back", style=discord.ButtonStyle.grey, row=4)
        back.callback = self._go_back
        self.add_item(back)
        nxt = discord.ui.Button(label="Review & Save →", style=discord.ButtonStyle.green, row=4)
        nxt.callback = self._go_next
        self.add_item(nxt)
        save = discord.ui.Button(label="💾 Save & Exit", style=discord.ButtonStyle.grey, row=4)
        save.callback = self._save_exit
        self.add_item(save)

    def _build_embed(self) -> discord.Embed:
        s = self.state
        e = discord.Embed(title="Texas Hold'em", color=PALETTE_GOLD)
        e.description = (
            "Players open tables at a **blind level**, and their rank sets which levels they can open. "
            "Anyone can join a table they can afford. When rank bet multipliers are off (page 3), only levels "
            "open to Members can be opened. Tables already open keep their blinds until they close. "
            "Switch the game on in Game Availability (page 11)."
        )
        lines = []
        for i, t in enumerate(s.holdem_stake_tiers):
            marker = "▶️ " if i == self.selected else ""
            state = "✅ on" if t.enabled else "⛔ off"
            lines.append(f"{marker}`{i + 1}` **{t.sb:,} / {t.bb:,}** · {RANK_NAMES.get(t.min_rank, '?')} and above · {state}")
        e.add_field(name="Blind Levels", value="\n".join(lines), inline=False)
        e.add_field(name="Time to Act", value=f"{s.holdem_action_seconds} s", inline=True)
        e.add_field(name="Buy-in", value=f"{s.holdem_min_buyin_bb}–{s.holdem_max_buyin_bb} big blinds", inline=True)
        e.set_footer(text=self._footer())
        return e

    async def _on_pick(self, interaction: discord.Interaction) -> None:
        self.selected = int(interaction.data["values"][0])  # type: ignore[index]
        self._add_buttons()
        await self._render(interaction)

    async def _edit_blinds(self, interaction: discord.Interaction) -> None:
        modal = _HoldemBlindsModal(self.selected + 1, self._tier())
        await interaction.response.send_modal(modal)
        if await modal.wait() or modal.values is None:
            return
        tier = self._tier()
        tier.sb, tier.bb = modal.values
        self._add_buttons()
        await safe_edit_original_response(interaction, embed=self._build_embed(), view=self)

    async def _change_levels(self, interaction: discord.Interaction, change) -> None:
        before = copy.deepcopy(self.state.holdem_stake_tiers)
        change()
        error = _holdem_levels_error(self.state.holdem_stake_tiers)
        if error:
            self.state.holdem_stake_tiers = before
            await interaction.response.send_message(f"❌ {error} Nothing was changed.", ephemeral=True)
            return
        self._add_buttons()
        await self._render(interaction)

    async def _toggle(self, interaction: discord.Interaction) -> None:
        def change():
            self._tier().enabled = not self._tier().enabled
        await self._change_levels(interaction, change)

    async def _on_rank(self, interaction: discord.Interaction) -> None:
        rank = int(interaction.data["values"][0])  # type: ignore[index]
        def change():
            self._tier().min_rank = rank
        await self._change_levels(interaction, change)

    async def _reset(self, interaction: discord.Interaction) -> None:
        self.state.holdem_stake_tiers = [HoldemStakeTier(**t) for t in HOLDEM_DEFAULT_STAKE_TIERS]
        self._add_buttons()
        await self._render(interaction)

    async def _edit_settings(self, interaction: discord.Interaction) -> None:
        modal = _HoldemSettingsModal(self.state)
        await interaction.response.send_modal(modal)
        if await modal.wait() or modal.values is None:
            return
        self.state.holdem_action_seconds, self.state.holdem_min_buyin_bb, self.state.holdem_max_buyin_bb = modal.values
        await safe_edit_original_response(interaction, embed=self._build_embed(), view=self)

    async def _go_back(self, interaction: discord.Interaction) -> None:
        view = _Page13HorseRacing(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _go_next(self, interaction: discord.Interaction) -> None:
        view = _PageConfirmSave(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)

    async def _save_exit(self, interaction: discord.Interaction) -> None:
        await _save_and_exit(interaction, self.ctx, self.state, self.cog)


# ---------------------------------------------------------------------------
# Final Confirmation Page — Review & Save
# ---------------------------------------------------------------------------

class _PageConfirmSave(discord.ui.View):
    def __init__(self, ctx: commands.Context, state: _WizardState, cog: MixinMeta):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.state = state
        self.cog = cog

    def _build_embed(self) -> discord.Embed:
        s = self.state
        e = discord.Embed(title="Configuration Summary", color=PALETTE_GOLD)

        mode_str = f"House Chips ({s.discord_currency_conversion_rate:,}:1)" if s.payment_mode == "chips" else "Server Currency"
        e.add_field(name="Payment Mode", value=mode_str, inline=True)
        e.add_field(name="Rank Thresholds", value=f"R2: {s.rank2_threshold} | R3: {s.rank3_threshold} | R4: {s.rank4_threshold}", inline=True)
        e.add_field(name="Prestige Points", value=f"Win: +{s.prestige_win_points} | Loss: -{s.prestige_loss_points}", inline=True)

        mult_str = f"{s.rank1_multiplier}x / {s.rank2_multiplier}x / {s.rank3_multiplier}x / {s.rank4_multiplier}x"
        mult_str += " (Enabled)" if s.bet_multipliers_enabled else " (Disabled)"
        e.add_field(name="Multipliers", value=mult_str, inline=True)

        allin_name = ALLIN_RISK_TIERS[s.allin_max_tier]["name"]
        e.add_field(name="All-In Cap", value=f"Tier {s.allin_max_tier} ({allin_name})", inline=True)

        scratch_str = f"{'Enabled' if s.scratch_enabled else 'Disabled'} — {s.scratch_cooldown_hours}h cooldown"
        e.add_field(name="Scratch Cards", value=scratch_str, inline=True)
        e.add_field(name="Daily Free Spin", value="Enabled" if s.mystery_wheel_enabled else "Disabled", inline=True)
        e.add_field(name="Wheel Cost", value=f"{s.multiplier_wheel_cost:,}", inline=True)
        e.add_field(name="House Segments", value=str(s.big6_house_segments), inline=True)

        disabled = [slug for slug in GAME_SLUGS if not s.games_enabled.get(slug, True)]
        games_str = ", ".join(disabled) + " disabled" if disabled else "All enabled"
        e.add_field(name="Games Enabled", value=games_str, inline=True)

        ch_str = ", ".join(f"<#{c}>" for c in s.allowed_channels) if s.allowed_channels else "All channels"
        e.add_field(name="Channel Lock", value=ch_str, inline=True)

        race_ch = f"<#{s.race_channel_id}>" if s.race_channel_id else "No race channel"
        e.add_field(
            name="Horse Racing",
            value=f"{race_ch} · {s.horserace_house_cut_pct}% cut · {s.horserace_countdown_minutes} min countdown",
            inline=True,
        )
        e.add_field(
            name="Texas Hold'em",
            value=_holdem_summary(s.holdem_stake_tiers, s.holdem_action_seconds, s.holdem_min_buyin_bb, s.holdem_max_buyin_bb),
            inline=False,
        )

        return e

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Only the setup admin can use these buttons.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Save Configuration", style=discord.ButtonStyle.green, row=0)
    async def save_config(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        conf = self.cog.db.get_conf(self.ctx.guild)
        self.state.apply(conf)
        self.cog.save()
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        embed = self._build_embed()
        embed.colour = discord.Colour.green()
        embed.set_footer(text="✅ Configuration saved!")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="← Go Back", style=discord.ButtonStyle.grey, row=0)
    async def go_back(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        view = _Page14Holdem(self.ctx, self.state, self.cog)
        await interaction.response.edit_message(embed=view._build_embed(), view=view)


# ---------------------------------------------------------------------------
# Shared save-and-exit helper
# ---------------------------------------------------------------------------

async def _save_and_exit(
    interaction: discord.Interaction,
    ctx: commands.Context,
    state: _WizardState,
    cog: MixinMeta,
) -> None:
    conf = cog.db.get_conf(ctx.guild)
    state.apply(conf)
    cog.save()
    embed = discord.Embed(
        title="✅ Configuration Saved",
        description=f"Your settings have been saved. Run `{ctx.clean_prefix}highrollerclubset setup` anytime to make changes.",
        color=discord.Colour.green(),
    )
    state._current_view = None
    await interaction.response.edit_message(embed=embed, view=None)


# ---------------------------------------------------------------------------
# Paginated subcommand help view
# ---------------------------------------------------------------------------

class _SubcommandHelpView(discord.ui.View):
    """Paginated in-channel embed listing subcommands for a command group."""

    PER_PAGE = 10
    message: discord.Message | None = None

    def __init__(self, ctx: commands.Context, command: commands.Group) -> None:
        super().__init__(timeout=120)
        self.ctx = ctx
        self.command = command
        self.cmds: list[commands.Command] = sorted(command.commands, key=lambda c: c.name)
        self.page = 0
        self.total_pages = max(1, (len(self.cmds) + self.PER_PAGE - 1) // self.PER_PAGE)
        self._update_buttons()

    def _update_buttons(self) -> None:
        self.prev_btn.disabled = self.page == 0
        self.next_btn.disabled = self.page >= self.total_pages - 1

    def _build_embed(self) -> discord.Embed:
        prefix = self.ctx.clean_prefix
        qualified = self.command.qualified_name
        desc = self.command.help or self.command.brief or ""
        embed = discord.Embed(
            title=f"\U0001f4cb {prefix}{qualified}",
            description=desc or "Subcommands available below.",
            color=PALETTE_GOLD,
        )
        start = self.page * self.PER_PAGE
        page_cmds = self.cmds[start : start + self.PER_PAGE]
        for sub in page_cmds:
            brief = sub.brief or (sub.help.splitlines()[0] if sub.help else "No description.")
            aliases = f"  _(alias: {', '.join(sub.aliases)})_" if sub.aliases else ""
            indicator = " `[group]`" if isinstance(sub, commands.Group) else ""
            embed.add_field(
                name=f"`{prefix}{qualified} {sub.name}`{indicator}{aliases}",
                value=brief,
                inline=False,
            )
        embed.set_footer(text=f"Page {self.page + 1} / {self.total_pages}")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This help menu isn't for you.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="\u25c0 Prev", style=discord.ButtonStyle.grey, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    @discord.ui.button(label="Next \u25b6", style=discord.ButtonStyle.grey, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._build_embed(), view=self)

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except Exception:
                pass


async def _send_subcommand_help(ctx: commands.Context, command: commands.Group) -> None:
    """Send a paginated in-channel embed listing a group's subcommands."""
    view = _SubcommandHelpView(ctx, command)
    view.message = await ctx.send(embed=view._build_embed(), view=view)


# ---------------------------------------------------------------------------
# Admin command class
# ---------------------------------------------------------------------------

class Admin(MixinMeta):
    """Admin configuration commands for HighRollerClub."""

    # -----------------------------------------------------------------------
    # Top-level group
    # -----------------------------------------------------------------------

    @commands.group(name="highrollerclubset", aliases=["hrcset"], invoke_without_command=True)
    @commands.guild_only()
    @commands.admin_or_permissions(manage_guild=True)
    async def hrcset(self, ctx: commands.Context) -> None:
        """Configure the HighRollerClub casino.

        Bot owner: see `highrollerclubset backup` to back up or restore the game data.
        """
        if ctx.invoked_subcommand is None:
            await _send_subcommand_help(ctx, ctx.command)

    # -----------------------------------------------------------------------
    # setup
    # -----------------------------------------------------------------------

    @hrcset.command(name="setup")
    async def hrcset_setup(self, ctx: commands.Context) -> None:
        """Launch the interactive multi-page setup wizard."""
        conf = self.db.get_conf(ctx.guild)
        state = _WizardState(conf)
        view = _Page1PaymentMode(ctx, state, self)
        state._message = await ctx.send(embed=view._build_embed(), view=view)

    # -----------------------------------------------------------------------
    # status
    # -----------------------------------------------------------------------

    @hrcset.command(name="status")
    async def hrcset_status(self, ctx: commands.Context) -> None:
        """Show the current server configuration as a read-only embed."""
        conf = self.db.get_conf(ctx.guild)
        e = discord.Embed(title="HighRollerClub — Server Configuration", color=PALETTE_GOLD)

        mode_str = f"House Chips ({conf.discord_currency_conversion_rate:,}:1)" if conf.payment_mode == "chips" else "Server Currency"
        e.add_field(name="Payment Mode", value=mode_str, inline=True)
        e.add_field(name="Rank Thresholds", value=f"R2: {conf.rank2_threshold} | R3: {conf.rank3_threshold} | R4: {conf.rank4_threshold}", inline=True)
        e.add_field(name="Prestige Points", value=f"Win: +{conf.prestige_win_points} | Loss: -{conf.prestige_loss_points}", inline=True)

        mult_str = f"{conf.rank1_multiplier}x / {conf.rank2_multiplier}x / {conf.rank3_multiplier}x / {conf.rank4_multiplier}x"
        mult_str += " (Enabled)" if conf.bet_multipliers_enabled else " (Disabled)"
        e.add_field(name="Multipliers", value=mult_str, inline=True)

        allin_name = ALLIN_RISK_TIERS[conf.allin_max_tier]["name"]
        e.add_field(name="All-In Cap", value=f"Tier {conf.allin_max_tier} ({allin_name})", inline=True)
        e.add_field(name="Scratch Cards", value=f"{'Enabled' if conf.scratch_enabled else 'Disabled'} — {conf.scratch_cooldown_hours}h cooldown", inline=True)
        e.add_field(name="Daily Free Spin", value="Enabled" if conf.mystery_wheel_enabled else "Disabled", inline=True)
        e.add_field(name="Wheel Cost", value=f"{conf.multiplier_wheel_cost:,}", inline=True)
        e.add_field(name="House Segments", value=str(conf.big6_house_segments), inline=True)

        # RNG overrides summary
        rng_parts = []
        for slug, overrides in conf.game_rng_settings.items():
            for key, val in overrides.items():
                rng_parts.append(f"{slug}: {key}={val}")
        e.add_field(name="RNG Overrides", value=", ".join(rng_parts) if rng_parts else "None (all defaults)", inline=False)

        disabled = [s for s in GAME_SLUGS if not conf.games_enabled.get(s, True)]
        e.add_field(name="Games Enabled", value=(", ".join(disabled) + " disabled") if disabled else "All enabled", inline=True)
        ch_str = ", ".join(f"<#{c}>" for c in conf.allowed_channels) if conf.allowed_channels else "All channels"
        e.add_field(name="Channel Lock", value=ch_str, inline=True)
        race_ch = f"<#{conf.race_channel_id}>" if conf.race_channel_id else "No race channel"
        e.add_field(
            name="Horse Racing",
            value=(
                f"{race_ch} · {conf.horserace_house_cut_pct}% cut · {conf.horserace_countdown_minutes} min countdown · "
                f"{conf.horserace_cooldown_minutes} min cooldown · solo return {conf.horserace_house_line_return_pct}%"
            ),
            inline=False,
        )
        e.add_field(
            name="Texas Hold'em",
            value=_holdem_summary(get_holdem_tiers(conf), conf.holdem_action_seconds, conf.holdem_min_buyin_bb, conf.holdem_max_buyin_bb),
            inline=False,
        )

        await ctx.send(embed=e)

    # -----------------------------------------------------------------------
    # reset
    # -----------------------------------------------------------------------

    @hrcset.command(name="reset")
    async def hrcset_reset(self, ctx: commands.Context) -> None:
        """Reset all guild settings to defaults (with confirmation)."""
        confirm_view = _ResetConfirmView(ctx, self)
        await ctx.send(
            "⚠️ This will reset **all** HighRollerClub settings to defaults. Player data is unaffected. Are you sure?",
            view=confirm_view,
        )

    @hrcset.command(name="wipeplayers")
    async def hrcset_wipeplayers(self, ctx: commands.Context) -> None:
        """Delete all HighRollerClub player data for this guild (with confirmation)."""
        confirm_view = _WipePlayersConfirmView(ctx, self)
        await ctx.send(
            "⚠️ This will delete **all** HighRollerClub player data for this guild. Guild settings will be preserved. Are you sure?",
            view=confirm_view,
        )

    # -----------------------------------------------------------------------
    # set (subgroup)
    # -----------------------------------------------------------------------

    @hrcset.group(name="set", invoke_without_command=True)
    async def hrcset_set(self, ctx: commands.Context) -> None:
        """Directly set a single configuration value."""
        if ctx.invoked_subcommand is None:
            await _send_subcommand_help(ctx, ctx.command)

    @hrcset_set.command(name="paymentmode")
    async def set_paymentmode(self, ctx: commands.Context, mode: str) -> None:
        """Set payment mode: chips or bank."""
        if mode not in ("chips", "bank"):
            await ctx.send("Mode must be `chips` or `bank`.")
            return
        conf = self.db.get_conf(ctx.guild)
        if mode == conf.payment_mode:
            await ctx.send(f"Payment mode is already **{mode}**.")
            return
        conf.payment_mode = mode
        self.save()
        msg = f"✅ Payment mode set to **{mode}**."
        holders = sum(1 for u in conf.users.values() if u.chip_balance > 0)
        if mode == "bank" and holders:
            msg += (
                f"\n⚠️ {holders:,} player(s) still hold chips. Chip balances are kept but can't be used "
                "in bank mode; switch back to `chips` to make them playable again."
            )
        await ctx.send(msg)

    @hrcset_set.command(name="conversionrate")
    async def set_conversionrate(self, ctx: commands.Context, amount: int) -> None:
        """Set the chip-to-currency conversion rate (chips per 1 server currency unit)."""
        if amount < 1:
            await ctx.send("Rate must be at least 1.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.discord_currency_conversion_rate = amount
        self.save()
        await ctx.send(f"✅ Conversion rate set to **{amount:,}** chips per 1 server currency unit.")

    @hrcset_set.command(name="conversion")
    async def set_conversion(self, ctx: commands.Context, state: str) -> None:
        """Enable or disable chip-to-currency conversion (enable/disable)."""
        if state not in ("enable", "disable"):
            await ctx.send("Use `enable` or `disable`.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.discord_currency_conversion_enabled = state == "enable"
        self.save()
        await ctx.send(f"✅ Chip conversion **{'enabled' if state == 'enable' else 'disabled'}**.")

    @hrcset_set.command(name="rankthreshold")
    async def set_rankthreshold(self, ctx: commands.Context, rank: int, amount: int) -> None:
        """Set the prestige point threshold for a rank (rank: 2, 3, or 4)."""
        if rank not in (2, 3, 4):
            await ctx.send("Rank must be 2, 3, or 4.")
            return
        if amount < 1:
            await ctx.send("Threshold must be at least 1.")
            return
        conf = self.db.get_conf(ctx.guild)
        trial = {r: getattr(conf, f"rank{r}_threshold") for r in (2, 3, 4)}
        trial[rank] = amount
        if error := _threshold_order_error(trial[2], trial[3], trial[4]):
            await ctx.send(f"❌ {error}")
            return
        setattr(conf, f"rank{rank}_threshold", amount)
        self.save()
        await ctx.send(f"✅ Rank {rank} ({RANK_NAMES[rank]}) threshold set to **{amount:,}** pts.")

    @hrcset_set.command(name="prestigewin")
    async def set_prestigewin(self, ctx: commands.Context, points: float) -> None:
        """Set prestige points awarded per win (min 0.1)."""
        if points <= 0:
            await ctx.send("Win points must be greater than 0.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.prestige_win_points = points
        self.save()
        await ctx.send(f"✅ Prestige win points set to **{points}**.")

    @hrcset_set.command(name="prestigeloss")
    async def set_prestigeloss(self, ctx: commands.Context, points: float) -> None:
        """Set prestige points removed per loss (min 0.0)."""
        if points < 0:
            await ctx.send("Loss points cannot be negative.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.prestige_loss_points = points
        self.save()
        await ctx.send(f"✅ Prestige loss points set to **{points}**.")

    @hrcset_set.command(name="rankmultipliers")
    async def set_rankmultipliers(self, ctx: commands.Context, state: str) -> None:
        """Enable or disable rank bet multipliers (enable/disable)."""
        if state not in ("enable", "disable"):
            await ctx.send("Use `enable` or `disable`.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.bet_multipliers_enabled = state == "enable"
        self.save()
        await ctx.send(f"✅ Rank bet multipliers **{'enabled' if state == 'enable' else 'disabled'}**.")

    @hrcset_set.command(name="multiplier")
    async def set_multiplier(self, ctx: commands.Context, rank: int, value: float) -> None:
        """Set the bet multiplier for a rank (2–4). Value must be 1.0–10.0. Member is always 1.0x."""
        if rank not in (2, 3, 4):
            await ctx.send("Rank must be 2, 3, or 4. Member (rank 1) always bets at 1.0x, the base limits.")
            return
        if not 1.0 <= value <= 10.0:
            await ctx.send("Multiplier must be between 1.0 and 10.0.")
            return
        conf = self.db.get_conf(ctx.guild)
        setattr(conf, f"rank{rank}_multiplier", value)
        self.save()
        await ctx.send(f"✅ {RANK_NAMES[rank]} multiplier set to **{value}x**.")

    @hrcset_set.command(name="betlimits")
    async def set_betlimits(self, ctx: commands.Context, game_slug: str, min_bet: int, max_bet: int) -> None:
        """Set min and max bet for a game."""
        if game_slug not in DEFAULT_BET_LIMITS:
            await ctx.send(f"`{game_slug}` does not have configurable bet limits.")
            return
        if min_bet < 1 or max_bet < min_bet:
            await ctx.send("Min must be ≥ 1 and max must be ≥ min.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.game_bet_limits[game_slug] = {"min": min_bet, "max": max_bet}
        self.save()
        await ctx.send(f"✅ {game_slug.title()} bet limits set to **{min_bet:,}–{max_bet:,}**.")

    @hrcset_set.command(name="allintier")
    async def set_allintier(self, ctx: commands.Context, tier: int) -> None:
        """Set the maximum All-In risk tier players can access (1–5)."""
        if not 1 <= tier <= 5:
            await ctx.send("Tier must be between 1 and 5.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.allin_max_tier = tier
        self.save()
        await ctx.send(f"✅ All-In cap set to Tier {tier} ({ALLIN_RISK_TIERS[tier]['name']}).")

    @hrcset_set.command(name="rng")
    async def set_rng(self, ctx: commands.Context, game_slug: str, param_key: str, value: str) -> None:
        """Set a configurable RNG parameter for a game."""
        if game_slug in CARD_MATH_GAMES:
            await ctx.send(f"`{game_slug}` uses card math — its win chance is not configurable.")
            return
        if game_slug not in CONFIGURABLE_RNG:
            await ctx.send(f"`{game_slug}` has no configurable RNG parameters.")
            return
        if param_key not in CONFIGURABLE_RNG[game_slug]:
            valid = ", ".join(CONFIGURABLE_RNG[game_slug])
            await ctx.send(f"`{param_key}` is not valid for `{game_slug}`. Valid params: {valid}.")
            return
        meta = CONFIGURABLE_RNG[game_slug][param_key]
        try:
            if meta["type"] is float:
                parsed: int | float | list = float(value)
            elif meta["type"] is int:
                parsed = int(value)
            else:
                parsed = [int(x.strip()) for x in value.split(",")]
        except (ValueError, TypeError):
            await ctx.send(f"Invalid value `{value}` for `{param_key}`.")
            return
        if meta["type"] is list:
            items = parsed  # type: ignore[assignment]
            if len(items) != len(meta["default"]) or any(v < meta["min"] or v > meta["max"] for v in items):  # type: ignore[union-attr]
                await ctx.send(f"List values must each be between {meta['min']} and {meta['max']}, with exactly {len(meta['default'])} entries.")
                return
        else:
            if not (meta["min"] <= parsed <= meta["max"]):  # type: ignore[operator]
                await ctx.send(f"Value must be between {meta['min']} and {meta['max']}.")
                return
        conf = self.db.get_conf(ctx.guild)
        conf.game_rng_settings.setdefault(game_slug, {})[param_key] = parsed
        self.save()
        await ctx.send(f"✅ `{game_slug}.{param_key}` set to **{parsed}**.")

    @hrcset_set.command(name="scratch")
    async def set_scratch(self, ctx: commands.Context, state: str) -> None:
        """Enable or disable Scratch Cards (enable/disable)."""
        if state not in ("enable", "disable"):
            await ctx.send("Use `enable` or `disable`.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.scratch_enabled = state == "enable"
        self.save()
        await ctx.send(f"✅ Scratch Cards **{'enabled' if state == 'enable' else 'disabled'}**.")

    @hrcset_set.command(name="scratchcooldown")
    async def set_scratchcooldown(self, ctx: commands.Context, hours: int) -> None:
        """Set the Scratch Card cooldown in hours (1–168)."""
        if not 1 <= hours <= 168:
            await ctx.send("Hours must be between 1 and 168.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.scratch_cooldown_hours = hours
        self.save()
        await ctx.send(f"✅ Scratch Card cooldown set to **{hours}h**.")

    @hrcset_set.command(name="mysteryspin")
    async def set_mysteryspin(self, ctx: commands.Context, state: str) -> None:
        """Enable or disable the Mystery Wheel daily free spin (enable/disable)."""
        if state not in ("enable", "disable"):
            await ctx.send("Use `enable` or `disable`.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.mystery_wheel_enabled = state == "enable"
        conf.games_enabled["mysteryspin"] = state == "enable"
        self.save()
        await ctx.send(f"✅ Mystery Wheel **{'enabled' if state == 'enable' else 'disabled'}**.")

    @hrcset_set.command(name="timezone")
    async def set_timezone(self, ctx: commands.Context, timezone_string: str) -> None:
        """Set the Mystery Wheel reset timezone (e.g. America/New_York)."""
        if timezone_string not in zoneinfo.available_timezones():
            await ctx.send(f"`{timezone_string}` is not a valid timezone string.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.mystery_wheel_timezone = timezone_string
        self.save()
        await ctx.send(f"✅ Mystery Wheel timezone set to **{timezone_string}**.")

    @hrcset_set.command(name="wheelcost")
    async def set_wheelcost(self, ctx: commands.Context, amount: int) -> None:
        """Set the cost to spin the Multiplier Wheel (min 1)."""
        if amount < 1:
            await ctx.send("Cost must be at least 1.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.multiplier_wheel_cost = amount
        self.save()
        await ctx.send(f"✅ Multiplier Wheel spin cost set to **{amount:,}**.")

    @hrcset_set.command(name="housesegments")
    async def set_housesegments(self, ctx: commands.Context, count: int) -> None:
        """Set the number of house segments on the Big Six Wheel (0, 2, 4, or 6)."""
        if count not in BIG6_HOUSE_SEGMENT_OPTIONS:
            options = ", ".join(str(n) for n in BIG6_HOUSE_SEGMENT_OPTIONS)
            await ctx.send(f"House segments must be one of: {options}.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.big6_house_segments = count
        self.save()
        await ctx.send(f"✅ Big Six house segments set to **{count}**.")

    @hrcset_set.group(name="channel", invoke_without_command=True)
    async def set_channel(self, ctx: commands.Context) -> None:
        """Manage allowed channels for the casino."""
        if ctx.invoked_subcommand is None:
            await _send_subcommand_help(ctx, ctx.command)

    @set_channel.command(name="add")
    async def channel_add(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        """Add a channel to the allowed list."""
        conf = self.db.get_conf(ctx.guild)
        if channel.id not in conf.allowed_channels:
            conf.allowed_channels.append(channel.id)
            self.save()
        await ctx.send(f"✅ {channel.mention} added to allowed channels.")

    @set_channel.command(name="clear")
    async def channel_clear(self, ctx: commands.Context) -> None:
        """Clear all channel restrictions (allow all channels)."""
        conf = self.db.get_conf(ctx.guild)
        conf.allowed_channels.clear()
        self.save()
        await ctx.send("✅ Channel restrictions cleared — all channels are now allowed.")

    @hrcset_set.group(name="blacklist", invoke_without_command=True)
    async def set_blacklist(self, ctx: commands.Context) -> None:
        """Manage the player blacklist."""
        if ctx.invoked_subcommand is None:
            await _send_subcommand_help(ctx, ctx.command)

    @set_blacklist.command(name="add")
    async def blacklist_add(self, ctx: commands.Context, member: discord.Member) -> None:
        """Add a player to the blacklist."""
        conf = self.db.get_conf(ctx.guild)
        if member.id not in conf.blacklisted_users:
            conf.blacklisted_users.append(member.id)
            self.save()
        await ctx.send(f"✅ {member.mention} has been blacklisted.")

    @set_blacklist.command(name="remove")
    async def blacklist_remove(self, ctx: commands.Context, member: discord.Member) -> None:
        """Remove a player from the blacklist."""
        conf = self.db.get_conf(ctx.guild)
        if member.id in conf.blacklisted_users:
            conf.blacklisted_users.remove(member.id)
            self.save()
        await ctx.send(f"✅ {member.mention} has been removed from the blacklist.")

    @set_blacklist.command(name="list")
    async def blacklist_list(self, ctx: commands.Context) -> None:
        """List all currently blacklisted users."""
        conf = self.db.get_conf(ctx.guild)
        if not conf.blacklisted_users:
            await ctx.send("No users are currently blacklisted.")
            return
        lines = []
        for uid in conf.blacklisted_users:
            member = ctx.guild.get_member(uid)
            lines.append(member.mention if member else str(uid))
        await ctx.send("**Blacklisted users:**\n" + "\n".join(lines))

    @hrcset_set.group(name="game", invoke_without_command=True)
    async def set_game(self, ctx: commands.Context) -> None:
        """Enable or disable individual games."""
        if ctx.invoked_subcommand is None:
            await _send_subcommand_help(ctx, ctx.command)

    @set_game.command(name="enable")
    async def game_enable(self, ctx: commands.Context, game_slug: str) -> None:
        """Enable a game by slug."""
        if game_slug not in GAME_SLUGS:
            await ctx.send(f"`{game_slug}` is not a valid game slug.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.games_enabled[game_slug] = True
        if game_slug == "mysteryspin":
            conf.mystery_wheel_enabled = True
        self.save()
        await ctx.send(f"✅ **{game_slug.title()}** is now enabled.")

    @set_game.command(name="disable")
    async def game_disable(self, ctx: commands.Context, game_slug: str) -> None:
        """Disable a game by slug. Players will see it as locked on the Game Floor."""
        if game_slug not in GAME_SLUGS:
            await ctx.send(f"`{game_slug}` is not a valid game slug.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.games_enabled[game_slug] = False
        if game_slug == "mysteryspin":
            conf.mystery_wheel_enabled = False
        self.save()
        await ctx.send(f"✅ **{game_slug.title()}** is now disabled. Players will see it as locked on the Game Floor.")

    @set_game.command(name="list")
    async def game_list(self, ctx: commands.Context) -> None:
        """Show all games and their current enabled state."""
        conf = self.db.get_conf(ctx.guild)
        lines = []
        for slug in GAME_SLUGS:
            enabled = conf.games_enabled.get(slug, True)
            lines.append(f"{'✅' if enabled else '🔒'} {slug.title()}")
        await ctx.send("\n".join(lines))


# ---------------------------------------------------------------------------
# Reset confirmation view
# ---------------------------------------------------------------------------

    # ── Horse Racing ───────────────────────────────────────────────

    @hrcset.group(name="race", invoke_without_command=True)
    async def hrcset_race(self, ctx: commands.Context) -> None:
        """Horse Racing: the race channel, settings and the horses."""
        if ctx.invoked_subcommand is None:
            await _send_subcommand_help(ctx, ctx.command)

    @hrcset_race.command(name="channel")
    async def race_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None) -> None:
        """Set the channel races are announced and run in. Leave it out to clear it (closes Horse Racing)."""
        conf = self.db.get_conf(ctx.guild)
        conf.race_channel_id = channel.id if channel else None
        self.save()
        if channel:
            await ctx.send(f"✅ Races will run in {channel.mention}.")
        else:
            await ctx.send("✅ Race channel cleared. Horse Racing is closed until a new one is set.")

    async def _race_number(self, ctx: commands.Context, key: str, value: int) -> None:
        label, low, high = next((lbl, lo, hi) for k, lbl, lo, hi in _RACE_SETTINGS if k == key)
        if not low <= value <= high:
            await ctx.send(f"❌ {label} must be from {low} to {high}.")
            return
        conf = self.db.get_conf(ctx.guild)
        setattr(conf, key, value)
        self.save()
        await ctx.send(f"✅ {label} set to **{value}**.")

    @hrcset_race.command(name="cut")
    async def race_cut(self, ctx: commands.Context, percent: int) -> None:
        """Set the house cut taken from each pool's new bets (0-25%)."""
        await self._race_number(ctx, "horserace_house_cut_pct", percent)

    @hrcset_race.command(name="countdown")
    async def race_countdown(self, ctx: commands.Context, minutes: int) -> None:
        """Set how long betting stays open before the race runs (2-10 minutes)."""
        await self._race_number(ctx, "horserace_countdown_minutes", minutes)

    @hrcset_race.command(name="cooldown")
    async def race_cooldown(self, ctx: commands.Context, minutes: int) -> None:
        """Set how long a player waits before starting another race (0-1440 minutes)."""
        await self._race_number(ctx, "horserace_cooldown_minutes", minutes)

    @hrcset_race.command(name="houseline")
    async def race_houseline(self, ctx: commands.Context, percent: int) -> None:
        """Set the average return of solo races, which pay fixed house-line odds (50-95%)."""
        await self._race_number(ctx, "horserace_house_line_return_pct", percent)

    @hrcset_race.command(name="horses")
    async def race_horses(self, ctx: commands.Context) -> None:
        """List every horse with its id, stats and record."""
        from ..tasks.horse_races import ensure_horses  # noqa: PLC0415

        conf = self.db.get_conf(ctx.guild)
        horses = ensure_horses(conf)
        lines = []
        for hid, h in sorted(horses.items()):
            lines.append(
                f"`{hid}` **{h.name}** · R{hr.rating(h)} · SPD {h.speed:.0f} STA {h.stamina:.0f} "
                f"TRN {h.turning:.0f} GTE {h.start:.0f} · {h.wins}W {h.places}P in {h.races}"
            )
        custom = sum(1 for h in horses.values() if h.custom)
        e = discord.Embed(title="🐎 Horses", color=PALETTE_GOLD, description="\n".join(lines)[:4000])
        e.set_footer(text=f"Custom horses: {custom}/{hr.MAX_CUSTOM_HORSES} · Default horses (d01-d15) can't be renamed or removed.")
        await ctx.send(embed=e)

    def _find_custom_horse(self, conf: GuildSettings, key: str) -> tuple[str, Horse] | None:
        key = key.strip()
        for hid, horse in conf.horses.items():
            if horse.custom and (hid == key.lower() or horse.name.casefold() == key.casefold()):
                return hid, horse
        return None

    def _horse_in_race(self, conf: GuildSettings, horse_id: str) -> bool:
        return conf.active_race is not None and horse_id in conf.active_race.horse_ids

    @hrcset_race.command(name="addhorse")
    async def race_addhorse(self, ctx: commands.Context, *, name: str) -> None:
        """Add a custom horse (up to 10). It starts with all stats at 0."""
        from ..tasks.horse_races import ensure_horses  # noqa: PLC0415

        conf = self.db.get_conf(ctx.guild)
        horses = ensure_horses(conf)
        name = name.strip()
        free = [hid for hid in hr.CUSTOM_HORSE_IDS if hid not in horses]
        if not free:
            await ctx.send(f"❌ The stable already has {hr.MAX_CUSTOM_HORSES} custom horses. Remove one first.")
            return
        error = hr.validate_horse_name(name, (h.name for h in horses.values()))
        if error:
            await ctx.send(f"❌ {error}")
            return
        horses[free[0]] = Horse(name=name, custom=True)
        self.save()
        await ctx.send(f"✅ **{name}** joined the stable as `{free[0]}`.")

    @hrcset_race.command(name="renamehorse")
    async def race_renamehorse(self, ctx: commands.Context, horse: str, *, new_name: str) -> None:
        """Rename a custom horse. Give its id (like c01) or its current name in quotes."""
        conf = self.db.get_conf(ctx.guild)
        found = self._find_custom_horse(conf, horse)
        if found is None:
            await ctx.send("❌ No custom horse by that id or name. Default horses can't be renamed.")
            return
        hid, target = found
        new_name = new_name.strip()
        error = hr.validate_horse_name(new_name, (h.name for k, h in conf.horses.items() if k != hid))
        if error:
            await ctx.send(f"❌ {error}")
            return
        old = target.name
        target.name = new_name
        self.save()
        await ctx.send(f"✅ **{old}** is now **{new_name}**.")

    @hrcset_race.command(name="removehorse")
    async def race_removehorse(self, ctx: commands.Context, *, horse: str) -> None:
        """Remove a custom horse. Give its id (like c01) or its name."""
        conf = self.db.get_conf(ctx.guild)
        found = self._find_custom_horse(conf, horse)
        if found is None:
            await ctx.send("❌ No custom horse by that id or name. Default horses can't be removed.")
            return
        hid, target = found
        if self._horse_in_race(conf, hid):
            await ctx.send("❌ That horse is in the current race. Try again once it's finished.")
            return
        del conf.horses[hid]
        self.save()
        await ctx.send(f"✅ **{target.name}** has left the stable.")

    @hrcset_race.command(name="resetstats")
    async def race_resetstats(self, ctx: commands.Context, *, horse: str = "all") -> None:
        """Reset horse stats and records to 0: `all`, or one horse's id or name."""
        from ..tasks.horse_races import ensure_horses  # noqa: PLC0415

        conf = self.db.get_conf(ctx.guild)
        if conf.active_race is not None:
            await ctx.send("❌ A race is running. Try again once it's finished.")
            return
        horses = ensure_horses(conf)
        if horse.strip().lower() == "all":
            targets = list(horses)
        else:
            key = horse.strip()
            targets = [hid for hid, h in horses.items() if hid == key.lower() or h.name.casefold() == key.casefold()]
            if not targets:
                await ctx.send("❌ No horse by that id or name.")
                return
        names = "all horses" if len(targets) > 1 else f"**{horses[targets[0]].name}**"
        view = _RaceResetStatsView(ctx, self, targets)
        await ctx.send(f"⚠️ Reset the stats and records of {names} to 0? This can't be undone.", view=view)

    @hrcset_race.command(name="cancel")
    async def race_cancel(self, ctx: commands.Context) -> None:
        """Cancel the current race and refund every bet."""
        conf = self.db.get_conf(ctx.guild)
        refunded = await self.hr_cancel_race(ctx.guild, conf, "Cancelled by an admin. All bets were refunded.")
        if refunded < 0:
            await ctx.send("❌ The race is paying out right now and can't be cancelled.")
        elif conf.active_race is None and refunded == 0:
            await ctx.send("There's no race running.")
        else:
            await ctx.send(f"✅ Race cancelled. {refunded} bet(s) refunded.")

    # ── Data backups (bot owner) ───────────────────────────────────

    @hrcset.group(name="backup", invoke_without_command=True)
    @commands.is_owner()
    async def hrcset_backup(self, ctx: commands.Context):
        """Back up and restore High Roller Club game data (bot owner only).

        All game data is saved to `db.json` in this cog's data folder, and is protected by:
        - **Rotating backups:** up to 3 copies in `backups/`, taken at most every 8 hours as the game saves.
        - **Start-of-session copy:** `db.json.backup`, the file as it was when the cog last loaded.
        - **Manual backups:** made with `backup create`. These are never deleted automatically.
        - **Load guard:** if `db.json` can't be read, saving is switched off so the file is never overwritten, and game commands report that the data failed to load. Restore a backup to recover.

        These commands still work when the data failed to load.
        """
        await _send_subcommand_help(ctx, ctx.command)

    @hrcset_backup.command(name="list")
    async def hrcset_backup_list(self, ctx: commands.Context):
        """List the available backups, newest first.

        Use the number shown with `backup restore`.
        """
        backups = self.list_backups()
        if not backups:
            await ctx.send("No backups yet. One is taken on the first save after the cog loads.")
            return
        lines = [
            f"`{i}` {p.name} — {datetime.fromtimestamp(p.stat().st_mtime):%Y-%m-%d %H:%M}"
            for i, p in enumerate(backups, start=1)
        ]
        await ctx.send(
            "**High Roller Club backups (newest first):**\n" + "\n".join(lines)
            + f"\n\nRestore one with `{ctx.clean_prefix}highrollerclubset backup restore <number>`."
        )

    @hrcset_backup.command(name="restore")
    async def hrcset_backup_restore(self, ctx: commands.Context, backup_number: int = 1):
        """Restore the game data from a backup.

        **Arguments:**
        - `[backup_number]` - Which backup to restore, as numbered by `backup list` (1 = most recent). Default: 1

        The backup is checked to make sure it loads first. The current `db.json` is kept as `db.json.pre-restore`.
        Saving is paused after a restore, so reload the cog straight away to load the restored data: `[p]reload highrollerclub`
        """
        backups = self.list_backups()
        if not backups:
            await ctx.send("No backups found.")
            return
        if not 1 <= backup_number <= len(backups):
            await ctx.send(f"Pick a number from 1 to {len(backups)} (see `{ctx.clean_prefix}highrollerclubset backup list`).")
            return
        source = backups[backup_number - 1]
        try:
            await self.restore_backup(source)
        except Exception as e:
            await ctx.send(f"Restore failed: `{e}`")
            return
        await ctx.send(
            f"✅ Restored **{source.name}**. Saving is paused until you reload, so run "
            f"`{ctx.clean_prefix}reload highrollerclub` now.\n"
            "(The replaced file was kept as `db.json.pre-restore`.)"
        )

    @hrcset_backup.command(name="create")
    async def hrcset_backup_create(self, ctx: commands.Context):
        """Save now and take a manual backup.

        Manual backups ignore the 8-hour spacing and are never deleted automatically.
        Useful before risky changes, like editing the data file or updating the cog.
        """
        try:
            target = await self.create_backup()
        except Exception as e:
            await ctx.send(f"Backup failed: `{e}`")
            return
        await ctx.send(f"✅ Created backup **{target.name}**.")


class _RaceResetStatsView(discord.ui.View):
    def __init__(self, ctx: commands.Context, cog: MixinMeta, horse_ids: list[str]):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog
        self.horse_ids = horse_ids

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Only the admin who ran this command can confirm.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Reset Stats", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        conf = self.cog.db.get_conf(self.ctx.guild)
        if conf.active_race is not None:
            await interaction.response.send_message("A race has started. Try again once it's finished.", ephemeral=True)
            return
        for hid in self.horse_ids:
            horse = conf.horses.get(hid)
            if horse is not None:
                conf.horses[hid] = Horse(name=horse.name, custom=horse.custom)
        self.cog.save()
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="✅ Horse stats reset.", view=self)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="Reset cancelled.", view=self)


_RESET_KEEPS = {
    "users", "horses", "race_carryover", "race_carry_count", "race_pending_refunds", "active_race", "race_notify_ids",
    "holdem_escrow",  # chips held at Hold'em tables belong to players, not settings
}


class _ResetConfirmView(discord.ui.View):
    def __init__(self, ctx: commands.Context, cog: MixinMeta):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Only the admin who ran this command can confirm.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirm Reset", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        conf = self.cog.db.get_conf(self.ctx.guild)
        if await self.cog.hr_cancel_race(self.ctx.guild, conf, "Settings were reset by an admin. All bets were refunded.") < 0:
            await interaction.response.send_message("A horse race is paying out. Try again in a few seconds.", ephemeral=True)
            return
        # Reset the settings in place (player data kept), so open game screens,
        # which hold this same object, pick up the defaults straight away.
        # The horses, carryover and owed refunds are game data, not settings: keep them.
        defaults = type(conf)()
        for field in type(conf).model_fields:
            if field not in _RESET_KEEPS:
                setattr(conf, field, getattr(defaults, field))
        self.cog.save()
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="✅ All settings reset to defaults. Player data preserved.", view=self)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="Reset cancelled.", view=self)


class _WipePlayersConfirmView(discord.ui.View):
    def __init__(self, ctx: commands.Context, cog: MixinMeta):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.cog = cog

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("Only the admin who ran this command can confirm.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Confirm Wipe", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        conf = self.cog.db.get_conf(self.ctx.guild)
        if await self.cog.hr_cancel_race(self.ctx.guild, conf, "Player data was wiped by an admin. All bets were refunded.") < 0:
            await interaction.response.send_message("A horse race is paying out. Try again in a few seconds.", ephemeral=True)
            return
        conf.users.clear()
        conf.race_notify_ids.clear()
        self.cog.save()
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="✅ All HighRollerClub player data has been deleted for this guild. Guild settings preserved.", view=self)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="Player data wipe cancelled.", view=self)
