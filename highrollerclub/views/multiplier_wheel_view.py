"""MultiplierWheelView -- Discord UI for the Multiplier Wheel in HighRollerClub.

Game flow
---------
Phase 1 (idle)    : Player sees spin cost, active multiplier status, and balance.
                    Buttons: Spin the Wheel | Back to Floor | How to Play

Phase 2 (result)  : Spin cost deducted; new multiplier applied to user profile.
                    Shows the multiplier won and its expiry window.
                    Buttons: Spin Again | Back to Floor

Access guard
------------
_check_access() is called at the top of every action button callback.
Checks:
  1. is_allowed_channel(conf, interaction.channel_id)
  2. conf.games_enabled.get("multiplierwheel", True)
Callers return immediately when False.

Economy rules
-------------
- Deduct conf.multiplier_wheel_cost on every spin (no bet range -- flat cost only).
- There is no win/loss: every spin guarantees a multiplier outcome.
- No record_win / record_loss / evaluate_rank / evaluate_specialty_titles calls.
- No Lucky Streak interaction (the wheel awards a multiplier, not a win).
- No Bonus Bet Token interaction ("multiplierwheel" NOT in BONUS_BET_TOKEN_ELIGIBLE_GAMES).
- get_game_rng(conf, "multiplierwheel", "weights") provides the spin weight list.
- If a multiplier is already active, it is silently replaced. The idle embed warns
  the player before they spin so they can make an informed decision.

Pure game logic lives in games/multiplier_wheel.py.
"""

from __future__ import annotations

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.interactions import safe_defer, safe_edit_original_response
from ..common.constants import (
    MULTIPLIER_WHEEL_OUTCOMES,
    PALETTE_GOLD,
    embed_image,
)
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    apply_rank_change,
    credit_balance,
    deduct_balance,
    evaluate_rank,
    get_balance,
    get_game_rng,
    get_pending_multiplier,
    is_allowed_channel,
)
from ..games.multiplier_wheel import (
    compute_expiry,
    format_time_remaining,
    spin_multiplier_wheel,
)

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_SPIN_FLAVOR: dict[str, str] = {
    "1.25x": "A modest boost — every edge counts.",
    "1.5x":  "Solid. Your next eligible win pays out half again.",
    "1.75x": "Nice pull. The wheel has been generous.",
    "2.0x":  "Double the profit on your next win. Hit it right.",
    "2.5x":  "A strong result. The wheel favors you today.",
    "3.0x":  "Maximum multiplier. The room takes notice.",
}

_ELIGIBLE_GAME_NAMES = "Slots, War, Blackjack, Hi-Lo, or Keno"


# ===========================================================================
# MultiplierWheelView
# ===========================================================================

class MultiplierWheelView(discord.ui.View):
    """Multiplier Wheel lobby and spin view.

    Constructor signature: (interaction, conf, user, cog)
    Matches the protocol expected by _launch_game in user_commands.py.
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
        self._last_outcome: dict | None = None  # populated after spin

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
    # Button layout helpers
    # ------------------------------------------------------------------

    def _add_idle_buttons(self) -> None:
        self.clear_items()

        spin_btn = discord.ui.Button(
            label="⚡ Spin the Wheel", style=discord.ButtonStyle.green, row=0
        )
        spin_btn.callback = self._on_spin
        self.add_item(spin_btn)

        back_btn = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back_btn.callback = self._back_to_floor
        self.add_item(back_btn)

        info_btn = discord.ui.Button(
            label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info_btn.callback = self._show_info
        self.add_item(info_btn)

    def _add_result_buttons(self) -> None:
        self.clear_items()

        spin_btn = discord.ui.Button(
            label="⚡ Spin Again", style=discord.ButtonStyle.green, row=0
        )
        spin_btn.callback = self._on_spin
        self.add_item(spin_btn)

        back_btn = discord.ui.Button(
            label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back_btn.callback = self._back_to_floor
        self.add_item(back_btn)

    # ------------------------------------------------------------------
    # Access guard
    # ------------------------------------------------------------------

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if not is_allowed_channel(self._conf, interaction.channel_id):
            await interaction.response.send_message(
                "The Multiplier Wheel can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False
        if not self._conf.games_enabled.get("multiplierwheel", True):
            await interaction.response.send_message(
                "The Multiplier Wheel is currently disabled on this server.",
                ephemeral=True,
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _on_spin(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)

        conf   = self._conf
        user   = self._user
        member = self._member
        cost   = conf.multiplier_wheel_cost

        # --- Verify balance -----------------------------------------------
        balance = await get_balance(member, conf, user)
        if conf.payment_mode == "chips":
            currency = "chips"
        else:
            currency = await bank.get_currency_name(member.guild)

        if balance < cost:
            await interaction.followup.send(
                f"You need at least **{cost:,} {currency}** to spin the Multiplier Wheel. "
                f"Your current balance is **{balance:,} {currency}**.",
                ephemeral=True,
            )
            return

        # --- Deduct cost --------------------------------------------------
        await deduct_balance(member, conf, user, cost)

        # --- Spin ---------------------------------------------------------
        weights: list[int] = get_game_rng(conf, "multiplierwheel", "weights")
        outcome = spin_multiplier_wheel(weights)

        # --- Apply multiplier to user profile -----------------------------
        expiry = compute_expiry(conf.multiplier_wheel_expiry_minutes)
        user.pending_multiplier = outcome["value"]
        user.pending_multiplier_expiry = expiry

        # Rank re-evaluation is skipped -- no prestige points change on a spin.

        self._cog.save()
        self._last_outcome = outcome

        # --- Render result ------------------------------------------------
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_result_embed(outcome, cost, currency, expiry), view=self)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        conf = self._conf
        cost = conf.multiplier_wheel_cost
        expiry_minutes = conf.multiplier_wheel_expiry_minutes

        e = discord.Embed(title="⚡ How to Play: Multiplier Wheel", color=PALETTE_GOLD)
        e.description = (
            f"**Pay {cost:,} chips/credits to spin for a payout multiplier.**\n\n"
            f"Every spin is guaranteed to land on a multiplier. "
            f"The multiplier remains active for **{expiry_minutes} minutes** "
            f"and is automatically applied to your profit on the next eligible win.\n\n"
            f"**Eligible games:** {_ELIGIBLE_GAME_NAMES}\n\n"
            "**How the multiplier works on a win:**\n"
            "``profit × (multiplier − 1.0)`` is added on top of your normal payout.\n"
            "*Example: bet 500 on Slots, win 1,000 (profit = 500). "
            "With a 2x multiplier → bonus profit = 500 × (2.0 − 1.0) = 500 → total payout = 1,500.*\n\n"
            "**Possible outcomes:**\n"
        )
        weights: list[int] = get_game_rng(conf, "multiplierwheel", "weights")
        total_weight = sum(weights)
        lines = []
        for outcome, w in zip(MULTIPLIER_WHEEL_OUTCOMES, weights):
            pct = (w / total_weight) * 100
            lines.append(f"`{outcome['label']}` — {pct:.0f}% chance")
        e.description += "\n".join(lines)
        e.description += "\n\n*Having an active multiplier when you spin replaces the old one.*"
        await interaction.response.send_message(embed=e, ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        await safe_defer(interaction)
        conf = self._conf
        user = self._user
        balance = await get_balance(self._member, conf, user)
        if conf.payment_mode == "chips":
            currency_name = "chips"
        else:
            currency_name = await bank.get_currency_name(self._member.guild)
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    # ------------------------------------------------------------------
    # Embed builders
    # ------------------------------------------------------------------

    def _build_idle_embed(self) -> discord.Embed:
        conf    = self._conf
        user    = self._user
        cost    = conf.multiplier_wheel_cost
        expiry_minutes = conf.multiplier_wheel_expiry_minutes

        e = discord.Embed(title="⚡ High Roller: Multiplier Wheel", color=PALETTE_GOLD)

        desc = (
            "**The Booster — pay to spin for a payout multiplier.**\n\n"
            f"**Spin cost:** {cost:,} chips/credits\n"
            f"**Multiplier duration:** {expiry_minutes} minutes\n"
            f"**Eligible games:** {_ELIGIBLE_GAME_NAMES}\n\n"
            "Every spin is guaranteed to land on a multiplier. "
            "It is applied automatically to your profit on the next eligible win.\n"
            "Possible multipliers: "
        )
        desc += "  ".join(f"`{o['label']}`" for o in MULTIPLIER_WHEEL_OUTCOMES)

        # Show active multiplier status
        active_mul = get_pending_multiplier(user)
        if active_mul is not None and user.pending_multiplier_expiry is not None:
            time_left = format_time_remaining(user.pending_multiplier_expiry)
            desc += (
                f"\n\n⚡ **Bonus snapshot: {active_mul}x multiplier** "
                f"(about {time_left} remaining when this message was rendered)\n"
                "⚠️ Spinning now will **replace** your current multiplier."
            )

        e.description = desc

        if url := embed_image("multiplierwheel"):
            e.set_thumbnail(url=url)

        return e

    def _build_result_embed(
        self,
        outcome: dict,
        cost: int,
        currency: str,
        expiry,
    ) -> discord.Embed:
        label = outcome["label"]
        value = outcome["value"]
        time_left = format_time_remaining(expiry)
        flavor = _SPIN_FLAVOR.get(label, "Your multiplier is set.")
        conf = self._conf

        e = discord.Embed(title="⚡ High Roller: Multiplier Wheel", color=PALETTE_GOLD)
        e.description = (
            f"🎯 **The wheel lands on: {label}!**\n\n"
            f"{flavor}\n\n"
            f"Your next eligible win on {_ELIGIBLE_GAME_NAMES} will earn\n"
            f"``profit × ({value} − 1.0)`` added on top of normal payout.\n\n"
            f"**Multiplier active for:** {time_left}\n"
            f"**Spin cost:** −{cost:,} {currency}"
        )

        # Show outcome probability table as a footer note
        weights: list[int] = get_game_rng(conf, "multiplierwheel", "weights")
        total_weight = sum(weights)
        for w, o in zip(weights, MULTIPLIER_WHEEL_OUTCOMES):
            if o["label"] == label:
                pct = (w / total_weight) * 100
                e.set_footer(text=f"{label} has a {pct:.0f}% chance · spin again to replace")
                break

        if url := embed_image("multiplierwheel"):
            e.set_thumbnail(url=url)

        return e

    def _build_embed(self) -> discord.Embed:
        """Alias for _build_idle_embed -- satisfies the _launch_game protocol."""
        return self._build_idle_embed()
