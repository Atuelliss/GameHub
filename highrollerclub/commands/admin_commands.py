from __future__ import annotations

import zoneinfo

import discord
from redbot.core import commands

from ..abc import MixinMeta
from ..commands.helper_functions import check_is_admin
from ..common.constants import (
    ALLIN_RISK_TIERS,
    BIG6_DEFAULT_SEGMENTS,
    BIG6_PAYOUTS,
    CARD_MATH_GAMES,
    CONFIGURABLE_RNG,
    DEFAULT_BET_LIMITS,
    GAME_SLUGS,
    PALETTE_GOLD,
    RANK_NAMES,
    SCRATCH_REWARD_OPTIONS,
)
from ..common.models import GuildSettings


# ---------------------------------------------------------------------------
# Shared modal helpers
# ---------------------------------------------------------------------------

class _SingleInputModal(discord.ui.Modal):
    """Generic single-text-input modal reused across wizard pages."""

    def __init__(self, title: str, label: str, placeholder: str = "", default: str = ""):
        super().__init__(title=title)
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

    def apply(self, conf: GuildSettings) -> None:
        """Write all pending state into the live GuildSettings object."""
        conf.payment_mode = self.payment_mode
        conf.discord_currency_conversion_rate = self.discord_currency_conversion_rate
        conf.discord_currency_conversion_enabled = self.discord_currency_conversion_enabled

        conf.rank2_threshold = self.rank2_threshold
        conf.rank3_threshold = self.rank3_threshold
        conf.rank4_threshold = self.rank4_threshold
        conf.prestige_win_points = self.prestige_win_points
        conf.prestige_loss_points = self.prestige_loss_points

        conf.bet_multipliers_enabled = self.bet_multipliers_enabled
        conf.rank1_multiplier = self.rank1_multiplier
        conf.rank2_multiplier = self.rank2_multiplier
        conf.rank3_multiplier = self.rank3_multiplier
        conf.rank4_multiplier = self.rank4_multiplier

        conf.game_bet_limits = self.game_bet_limits

        conf.allin_max_tier = self.allin_max_tier

        conf.scratch_enabled = self.scratch_enabled
        conf.scratch_cooldown_hours = self.scratch_cooldown_hours
        conf.scratch_reward_pool = self.scratch_reward_pool

        conf.mystery_wheel_enabled = self.mystery_wheel_enabled
        conf.mystery_wheel_timezone = self.mystery_wheel_timezone
        conf.mystery_wheel_reward_pool = self.mystery_wheel_reward_pool

        conf.multiplier_wheel_cost = self.multiplier_wheel_cost
        conf.multiplier_wheel_expiry_minutes = self.multiplier_wheel_expiry_minutes

        conf.big6_house_segments = self.big6_house_segments

        conf.game_rng_settings = self.game_rng_settings

        conf.games_enabled = self.games_enabled

        conf.allowed_channels = self.allowed_channels


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
        total_pages: int = 12,
    ):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.state = state
        self.cog = cog
        self.page_index = page_index
        self.total_pages = total_pages

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
        await interaction.edit_original_response(embed=embed, view=self)

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
                    setattr(self.state, attr, val)
                except ValueError:
                    pass
            embed = self._build_embed()
            await interaction.edit_original_response(embed=embed, view=self)
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
        await interaction.edit_original_response(embed=embed, view=self)

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
        await interaction.edit_original_response(embed=embed, view=self)

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
            await interaction.edit_original_response(embed=embed, view=self)
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

_BET_LIMIT_GAMES = [s for s in GAME_SLUGS if s in DEFAULT_BET_LIMITS]

class _Page4BetLimits(_WizardPageBase):
    def __init__(self, ctx, state, cog):
        super().__init__(ctx, state, cog, page_index=4)
        self._selected_game: str | None = None
        self._add_items()

    def _add_items(self) -> None:
        self.clear_items()

        options = [
            discord.SelectOption(label=slug.title(), value=slug)
            for slug in _BET_LIMIT_GAMES
        ]
        select = discord.ui.Select(placeholder="Select a game to configure limits…", options=options, row=0)
        select.callback = self._on_game_select
        self.add_item(select)

        if self._selected_game:
            edit_btn = discord.ui.Button(label=f"Edit {self._selected_game.title()} Limits", style=discord.ButtonStyle.blurple, row=1)
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
            lines.append(f"**{slug.title()}**: {limits['min']:,} – {limits['max']:,}")
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

        min_modal = _SingleInputModal(f"{slug.title()} Min Bet", "Minimum bet", placeholder="e.g. 10", default=str(current["min"]))
        await interaction.response.send_modal(min_modal)
        await min_modal.wait()

        max_modal = _SingleInputModal(f"{slug.title()} Max Bet", "Maximum bet", placeholder="e.g. 500", default=str(current["max"]))
        # Follow-up modal for max — use a new message interaction isn't possible; we'll re-prompt via button
        # For now store min if valid and prompt user to click Edit again for max
        # A full dual-modal flow requires two separate interactions; we handle min first then max.
        try:
            min_val = int(min_modal.value or "")
            if min_val < 1:
                raise ValueError
        except (ValueError, TypeError):
            min_val = current["min"]

        await interaction.followup.send(
            f"Min bet set to **{min_val:,}**. Click **Edit {slug.title()} Limits** again to set the max bet.",
            ephemeral=True,
        )
        self.state.game_bet_limits[slug] = {"min": min_val, "max": current["max"]}
        self._add_items()
        embed = self._build_embed()
        await interaction.edit_original_response(embed=embed, view=self)

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
            lines.append(f"{marker} Tier {tier_num}: {tier_data['name']} — {int(tier_data['win_chance']*100)}% win, {tier_data['payout']}x payout")
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
        await interaction.edit_original_response(embed=embed, view=self)

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
                await interaction.edit_original_response(embed=view._build_embed(), view=view)
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
        await interaction.edit_original_response(embed=embed, view=self)

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
        await interaction.edit_original_response(embed=embed, view=self)

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
        for count in [6, 8, 10, 12]:
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
        total = house + 46
        e = discord.Embed(title="Big Six Wheel — House Edge", color=PALETTE_GOLD)
        e.add_field(name="House Segments", value=str(house), inline=True)
        e.add_field(name="Total Segments", value=str(total), inline=True)

        prob_lines = []
        for seg_name, count in BIG6_DEFAULT_SEGMENTS.items():
            if seg_name == "house":
                continue
            pct = count / total * 100
            payout = BIG6_PAYOUTS.get(seg_name, 0)
            prob_lines.append(f"{seg_name}: {pct:.1f}% → {payout}x payout")
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
            await interaction.edit_original_response(embed=embed, view=self)
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
        e.description = "All games are enabled by default. Disable any that don't fit your server. Disabled games appear locked on the Game Floor — player stats for those games are preserved."
        disabled = [s for s in GAME_SLUGS if not self.state.games_enabled.get(s, True)]
        e.add_field(name="Disabled Games", value=", ".join(disabled) if disabled else "None — all enabled", inline=False)
        e.set_footer(text=self._footer())
        return e

    def _make_toggle_cb(self, slug: str):
        async def cb(interaction: discord.Interaction) -> None:
            self.state.games_enabled[slug] = not self.state.games_enabled.get(slug, True)
            self._add_buttons()
            await self._render(interaction)
        return cb

    async def _enable_all(self, interaction: discord.Interaction) -> None:
        for slug in GAME_SLUGS:
            self.state.games_enabled[slug] = True
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

        back = discord.ui.Button(label="\u2190 Back", style=discord.ButtonStyle.grey, row=2)
        back.callback = self._go_back
        self.add_item(back)

    def _build_embed(self) -> discord.Embed:
        e = discord.Embed(
            title="Add Allowed Channels",
            description=(
                "Select one or more channels the casino should be restricted to.\n"
                "Players will only be able to use `[p]highrollerclub` in these channels."
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
        view = _Page12ChannelLock(self.ctx, self.state, self.cog)
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
        description="Your settings have been saved. Run `[p]highrollerclubset setup` anytime to make changes.",
        color=discord.Colour.green(),
    )
    for item in interaction.message.components:
        pass  # disable handled by editing view=None
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

    @commands.group(name="highrollerclubset", aliases=["hrcset"], guild_only=True)
    async def hrcset(self, ctx: commands.Context) -> None:
        """Configure the HighRollerClub casino."""
        if ctx.invoked_subcommand is None:
            await _send_subcommand_help(ctx, ctx.command)

    @hrcset.before_invoke
    async def _before_hrcset(self, ctx: commands.Context) -> None:
        if not await check_is_admin(ctx):
            raise commands.CheckFailure("Admin or Manage Server permission required.")

    # -----------------------------------------------------------------------
    # setup
    # -----------------------------------------------------------------------

    @hrcset.command(name="setup")
    async def hrcset_setup(self, ctx: commands.Context) -> None:
        """Launch the interactive multi-page setup wizard."""
        conf = self.db.get_conf(ctx.guild)
        state = _WizardState(conf)
        view = _Page1PaymentMode(ctx, state, self)
        await ctx.send(embed=view._build_embed(), view=view)

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

    @hrcset.group(name="set")
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
        conf.payment_mode = mode
        self.save()
        await ctx.send(f"✅ Payment mode set to **{mode}**.")

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
        """Set the bet multiplier for a rank (1–4). Value must be 1.0–10.0."""
        if rank not in (1, 2, 3, 4):
            await ctx.send("Rank must be 1, 2, 3, or 4.")
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
        """Set the number of house segments on the Big Six Wheel (6, 8, 10, or 12)."""
        if count not in (6, 8, 10, 12):
            await ctx.send("House segments must be 6, 8, 10, or 12.")
            return
        conf = self.db.get_conf(ctx.guild)
        conf.big6_house_segments = count
        self.save()
        await ctx.send(f"✅ Big Six house segments set to **{count}**.")

    @hrcset_set.group(name="channel")
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

    @hrcset_set.group(name="blacklist")
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

    @hrcset_set.group(name="game")
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
        # Preserve users dict — only reset config fields
        users = conf.users
        new_conf = type(conf)()
        new_conf.users = users
        self.cog.db.configs[self.ctx.guild.id] = new_conf
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
        conf.users.clear()
        self.cog.save()
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="✅ All HighRollerClub player data has been deleted for this guild. Guild settings preserved.", view=self)

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        for item in self.children:
            item.disabled = True  # type: ignore[attr-defined]
        await interaction.response.edit_message(content="Player data wipe cancelled.", view=self)
