"""
SlotsView — Discord UI for the Slots game in HighRollerClub.

Handles:
  - Bet input modal
  - Full per-game checklist (deduct → spin → payout → bonuses → record → save)
  - ASCII reel display embed
  - Play Again / Back to Floor navigation

Pure game logic (symbols, spin, payout, ASCII art) lives in games/slots.py.
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
    consume_free_spin,
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
from ..games.slots import (
    build_idle_display,
    build_reel_display,
    calculate_payout,
    spin_reels,
)

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_FLAVOR: list[str] = [
    "The reels align — and the chips flow.",
    "Fortune favors the bold.",
    "The house didn't win this round.",
    "You read the reels like a seasoned pro.",
    "Another notch on the winner's belt.",
    "Luck is on your side tonight.",
    "The Club smiles upon you.",
]

_LOSS_FLAVOR: list[str] = [
    "So close, yet so far.",
    "The house always wins... most of the time.",
    "Not your spin — but there's always another.",
    "The reels have spoken.",
    "Shake it off and try again.",
    "Every legend has a losing streak.",
    "The Club will be here when you're ready.",
]


# ---------------------------------------------------------------------------
# Bet modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Place Your Bet — Slots"):
    def __init__(self, view: SlotsView, min_bet: int, max_bet: int) -> None:
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
        await self._view._resolve(interaction, int(raw))


# ---------------------------------------------------------------------------
# Main Slots View
# ---------------------------------------------------------------------------

class SlotsView(discord.ui.View):
    """Discord UI view for the Slots game.

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
        # interaction.user is a discord.Member in guild context
        self._member: discord.Member = interaction.user  # type: ignore[assignment]
        self._conf = conf
        self._user = user
        self._cog = cog

        # Balance cache — kept current after every resolve so _build_embed stays sync.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Tracks the last placed bet so "Spin Same Bet" can skip the modal.
        self._last_bet: int | None = None

        self._add_spin_buttons()

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
    # Button layout
    # ------------------------------------------------------------------

    def _add_spin_buttons(self) -> None:
        spin = discord.ui.Button(label="🎰 Spin!", style=discord.ButtonStyle.green, row=0)
        spin.callback = self._on_spin
        self.add_item(spin)

        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1)
        info.callback = self._show_info
        self.add_item(info)

    def _add_result_buttons(self) -> None:
        again = discord.ui.Button(label="🎰 Change Bet", style=discord.ButtonStyle.blurple, row=0)
        again.callback = self._play_again
        self.add_item(again)

        if self._last_bet is not None:
            same = discord.ui.Button(
                label=f"🎰 Spin ({self._last_bet:,})",
                style=discord.ButtonStyle.green,
                row=0,
            )
            same.callback = self._spin_same_bet
            self.add_item(same)

        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1)
        info.callback = self._show_info
        self.add_item(info)

    # ------------------------------------------------------------------
    # Access guard
    # ------------------------------------------------------------------

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        """Returns True if the player may spin.  Sends an ephemeral error and
        returns False if the channel is restricted or the game is disabled.
        Callers must return immediately when this returns False.
        """
        conf = self._conf

        if not is_allowed_channel(conf, interaction.channel_id):
            await interaction.response.send_message(
                "Slots can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not conf.games_enabled.get("slots", True):
            await interaction.response.send_message(
                "Slots is currently disabled on this server.",
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
        min_bet, max_bet = get_bet_limits(self._conf, "slots", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _spin_same_bet(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._resolve(interaction, self._last_bet)

    async def _play_again(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        self.clear_items()
        self._add_spin_buttons()
        await safe_response_edit_message(interaction, embed=self._build_embed(), view=self)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🎰 How to Play — High Roller Slots", color=PALETTE_GOLD)
        e.description = (
            "The reels spin a **3×3 grid**. Two types of paylines are evaluated on every spin:"
        )

        e.add_field(
            name="🟧 Horizontal Center Row (primary)",
            value=(
                "The middle row is the main payline. "
                "Match **3-of-a-kind** or **2-of-a-kind** left-to-right:\n"
                "```\n"
                "Symbol   ×3     ×2\n"
                "───────────────────\n"
                "777      50×    —  \n"
                "BAR      15×    —  \n"
                "BEL      10×    4× \n"
                "DIA       6×    3× \n"
                "CHR       4×    2× \n"
                "---       —     —  \n"
                "```"
                "Payout = bet × multiplier. E.g. a 50 chip bet on CHR ×2 returns **100 chips**."
            ),
            inline=False,
        )

        e.add_field(
            name="🟦 Vertical Columns (secondary)",
            value=(
                "Each of the three reel columns is checked independently. "
                "If **all three rows** in a column show the same paying symbol, that column pays too. "
                "Multiple columns can pay on the same spin, stacking with the center row:\n"
                "```\n"
                "Symbol   Column ×3\n"
                "───────────────────\n"
                "777          25×\n"
                "BAR           7×\n"
                "BEL           5×\n"
                "DIA           3×\n"
                "CHR           2×\n"
                "---           — \n"
                "```"
            ),
            inline=False,
        )

        e.add_field(
            name="ℹ️ Notes",
            value=(
                "• **---** (blank reel) never pays, even on a full match.\n"
                "• Center row and columns are evaluated simultaneously — you can win from both on the same spin.\n"
                "• Payouts shown are **gross return** (bet is included). A CHR ×2 at 50 chips returns 100 chips \u2014 profit is 50.\n"
                "• Bonuses (Lucky Streak, Multiplier Wheel, Bonus Bet Token) stack on top of the base payout."
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

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
    # Embed builder  (sync — uses cached balance)
    # ------------------------------------------------------------------

    def _build_embed(self, result: dict | None = None) -> discord.Embed:
        conf = self._conf
        user = self._user
        e = discord.Embed(title="🎰 High Roller Slots", color=PALETTE_GOLD)

        if result is None:
            # --- Idle / ready state ---
            reel_art = build_idle_display()
            desc = f"```\n{reel_art}\n```\n**Place your bet and hit Spin!**"

            if user.free_spins_available > 0:
                desc += (
                    f"\n🎟️ You have **{user.free_spins_available}** free spin(s) — "
                    "your next spin is on the house!"
                )
            mul = get_pending_multiplier(user)
            if mul is not None:
                desc += f"\n⚡ Bonus snapshot: **{mul}×** multiplier if it is still active on your next win."
            if has_bonus_bet_token(user):
                desc += "\n🎫 Bonus snapshot: Bonus Bet Token doubles payout if it is still unused when a win resolves."
        else:
            # --- Result state ---
            grid = result["grid"]
            bet: int = result["bet"]
            payout: int = result["payout"]
            outcome_label: str = result["outcome_label"]
            is_win: bool = result["is_win"]
            using_free_spin: bool = result["using_free_spin"]

            reel_art = build_reel_display(grid)
            cur = self._cached_currency
            desc = f"```\n{reel_art}\n```"

            if is_win:
                free_note = " *(free spin!)*" if using_free_spin else ""
                desc += f"\n✅ **{outcome_label}**"
                desc += (
                    f"\nBet: **{bet:,}** {cur}{free_note} "
                    f"→ Payout: **{payout:,}** {cur}"
                )
                desc += f"\n*{random.choice(_WIN_FLAVOR)}*"
            else:
                free_note = " *(free spin used)*" if using_free_spin else ""
                desc += f"\n❌ **{outcome_label}**"
                desc += f"\nBet: **{bet:,}** {cur}{free_note}"
                desc += f"\n*{random.choice(_LOSS_FLAVOR)}*"

            if result.get("streak_cancelled"):
                desc += "\n💔 **Your lucky streak has ended.**"

            if result.get("rank_changed"):
                old_name = RANK_NAMES.get(result["old_rank"], "Unknown")
                new_name = RANK_NAMES.get(result["new_rank"], "Unknown")
                if result["new_rank"] > result["old_rank"]:
                    desc += f"\n🏆 **Rank Up!** You are now a **{new_name}**!"
                else:
                    desc += f"\n📉 **Rank Down.** You have dropped to **{old_name}** → **{new_name}**."

            for slug in result.get("new_titles", []):
                title_str = SPECIALTY_TITLES.get(slug, slug)
                desc += f"\n🎖️ **New title unlocked:** {title_str}"

        e.description = desc

        # Thumbnail (activated once the asset is uploaded)
        if url := embed_image("slots"):
            e.set_thumbnail(url=url)

        # Balance footer
        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")

        return e

    # ------------------------------------------------------------------
    # Game resolution  (called from BetModal.on_submit)
    # ------------------------------------------------------------------

    async def _resolve(self, interaction: discord.Interaction, bet: int) -> None:
        member  = self._member
        conf    = self._conf
        user    = self._user
        cog     = self._cog

        # 1. Free spin check — must happen before validate/deduct.
        using_free_spin = consume_free_spin(user)

        # 2. Bet validation.
        #    For a free spin: skip the balance sufficiency check by passing
        #    `bet` as the available balance — the bet amount is still used
        #    for payout scaling but nothing is actually deducted.
        balance = await get_balance(member, conf, user)
        effective_balance = bet if using_free_spin else balance
        error = validate_bet(conf, user, "slots", bet, effective_balance)
        if error:
            if using_free_spin:
                # Restore the consumed free spin — the play was rejected.
                user.free_spins_available += 1
            await interaction.followup.send(error, ephemeral=True)
            return

        # Store the validated bet so "Spin Same Bet" can reuse it.
        self._last_bet = bet

        # 3. Deduct (skipped for free spin).
        if not using_free_spin:
            await deduct_balance(member, conf, user, bet)

        # 4. Bonus Bet Token — consume before resolution so the token cannot
        #    be re-used if something goes wrong mid-resolve.
        token_active = False
        if has_bonus_bet_token(user):
            token_active = consume_bonus_bet_token(user, "slots")

        # 5. Spin the reels.
        house_edge = get_game_rng(conf, "slots", "house_edge_pct")
        grid, payline = spin_reels(house_edge)

        # 6. Calculate raw payout from the payline.
        raw_payout, outcome_label = calculate_payout(bet, grid)
        is_win = raw_payout > 0

        streak_cancelled = False

        if is_win:
            total_payout = raw_payout

            # 7a. Lucky Streak bonus (+25 % of raw payout).
            if has_lucky_streak(user):
                total_payout += apply_lucky_streak_bonus(raw_payout)

            # 7b. Multiplier Wheel — only consume if this game is eligible.
            if "slots" in MULTIPLIER_ELIGIBLE_GAMES:
                multiplier = consume_multiplier(user)
                if multiplier is not None:
                    profit = total_payout - bet
                    total_payout += int(profit * (multiplier - 1.0))

            # 7c. Bonus Bet Token doubles total payout on a win.
            if token_active:
                total_payout *= 2

            await credit_balance(member, conf, user, total_payout)
            record_win(conf, user, "slots", total_payout, bet)

        else:
            total_payout = 0

            # On loss: cancel any active lucky streak.
            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True

            record_loss(conf, user, "slots", bet)

        # 8. Rank evaluation.
        new_rank  = evaluate_rank(conf, user)
        old_rank  = user.rank
        rank_changed = new_rank != old_rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        # 9. Specialty title evaluation.
        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        # 10. Save.
        cog.save()

        # 11. Refresh cached balance for the embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # 12. Build result payload and update the message.
        result = {
            "grid":           grid,
            "bet":            bet,
            "payout":         total_payout,
            "outcome_label":  outcome_label,
            "is_win":         is_win,
            "using_free_spin": using_free_spin,
            "streak_cancelled": streak_cancelled,
            "rank_changed":   rank_changed,
            "old_rank":       old_rank,
            "new_rank":       new_rank,
            "new_titles":     new_titles,
        }

        self.clear_items()
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_embed(result=result), view=self)
