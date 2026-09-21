"""
AllInView â€” Discord UI for the All-In game in HighRollerClub.

Game flow
---------
Phase 1 (idle)  : Player sees the risk tier table and their full balance (the bet).
                  Tier buttons are shown immediately â€” no bet modal.
Phase 2 (result): Flip resolves; the player's entire balance was wagered.

The bet is always the player's full balance at the moment the tier is selected.
There is no partial bet option.

Pure game logic lives in games/all_in.py.
"""
from __future__ import annotations

import random

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.constants import (
    ALLIN_RISK_TIERS,
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
    credit_balance,
    deduct_balance,
    evaluate_rank,
    evaluate_specialty_titles,
    get_balance,
    get_game_rng,
    get_pending_multiplier,
    has_bonus_bet_token,
    has_lucky_streak,
    is_allowed_channel,
    record_loss,
    record_win,
)
from ..games.all_in import calculate_payout, flip

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_FLAVOR: list[str] = [
    "Nerves of steel â€” and the chips to show for it.",
    "A bold move, brilliantly executed.",
    "The house blinked first.",
    "Risk is just another word for opportunity.",
    "Fortune favors the reckless.",
    "The Club tips its hat.",
    "One flip, one legend.",
]

_LOSS_FLAVOR: list[str] = [
    "The house never forgets.",
    "High risk, high consequence.",
    "A coin has no memory â€” try again.",
    "Not this time. But the Club respects the nerve.",
    "The odds demanded their due.",
    "Fortunes are built on losses like this.",
    "The Club awaits your return.",
]

# Tier-specific opener lines shown above the result.
_TIER_FLAVOR: dict[int, str] = {
    1: "Standard? A sensible choice.",
    2: "Bold? The stakes rise.",
    3: "Reckless? The Club holds its breath.",
    4: "Desperate? Madness â€” or genius.",
    5: "Suicidal? Even the dealers look away.",
}

_COIN_WIN  = "[ H E A D S ]"
_COIN_LOSS = "[ T A I L S ]"


# ---------------------------------------------------------------------------
# Main All-In View
# ---------------------------------------------------------------------------

class AllInView(discord.ui.View):
    """Discord UI view for the All-In game.

    Constructor signature: (interaction, conf, user, cog)
    This matches the protocol expected by _launch_game in user_commands.py.

    The bet is always the player's full balance â€” there is no bet modal.
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

        # Balance cache â€” refreshed after every resolve so _build_embed stays sync.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        self._add_tier_buttons()

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

    def _add_tier_buttons(self) -> None:
        """Show one button per available tier (capped by conf.allin_max_tier) plus
        a Back and Info button."""
        max_tier = self._conf.allin_max_tier

        _TIER_STYLES: dict[int, discord.ButtonStyle] = {
            1: discord.ButtonStyle.green,
            2: discord.ButtonStyle.blurple,
            3: discord.ButtonStyle.blurple,
            4: discord.ButtonStyle.red,
            5: discord.ButtonStyle.red,
        }

        for tier_num, tier_data in ALLIN_RISK_TIERS.items():
            if tier_num > max_tier:
                break
            label = f"Tier {tier_num} - {tier_data['name']} ({tier_data['payout']}x)"
            btn = discord.ui.Button(
                label=label,
                style=_TIER_STYLES.get(tier_num, discord.ButtonStyle.grey),
                row=0,
            )
            btn.callback = self._make_tier_callback(tier_num)
            self.add_item(btn)

        back = discord.ui.Button(
            label="Back to Floor", style=discord.ButtonStyle.grey, row=1
        )
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(
            label="How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    def _add_result_buttons(self) -> None:
        again = discord.ui.Button(
            label="Play Again", style=discord.ButtonStyle.blurple, row=0
        )
        again.callback = self._on_play_again
        self.add_item(again)

        back = discord.ui.Button(
            label="Back to Floor", style=discord.ButtonStyle.grey, row=0
        )
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(
            label="How to Play", style=discord.ButtonStyle.grey, row=1
        )
        info.callback = self._show_info
        self.add_item(info)

    def _make_tier_callback(self, tier: int):
        """Return a button callback that captures ``tier`` correctly."""
        async def callback(interaction: discord.Interaction) -> None:
            await self._on_tier_selected(interaction, tier)
        return callback

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
                "All-In can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not conf.games_enabled.get("allin", True):
            await interaction.response.send_message(
                "All-In is currently disabled on this server.",
                ephemeral=True,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _on_play_again(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        # Refresh balance display before returning to idle.
        self._cached_balance = await get_balance(self._member, self._conf, self._user)
        if self._conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(self._member.guild)
        self.clear_items()
        self._add_tier_buttons()
        await safe_response_edit_message(interaction, embed=self._build_embed(), view=self)

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

    async def _show_info(self, interaction: discord.Interaction) -> None:
        conf = self._conf
        max_tier = conf.allin_max_tier

        e = discord.Embed(title="How to Play - All-In", color=PALETTE_GOLD)
        e.description = (
            "Your **entire balance** is the bet. Pick a tier and one flip decides everything.\n"
            "Win and your balance multiplies. Lose and you walk away with nothing."
        )

        # Build the tier table with live-configured win chances.
        header  = f"{'Tier':<5}  {'Name':<12}  {'Win%':<6}  Payout"
        divider = "-" * len(header)
        rows    = [header, divider]
        for t, data in ALLIN_RISK_TIERS.items():
            if t > max_tier:
                break
            win_chance = get_game_rng(conf, "allin", f"tier{t}_win_chance")
            win_pct    = f"{win_chance * 100:.0f}%"
            rows.append(f"{t:<5}  {data['name']:<12}  {win_pct:<6}  {data['payout']}x")

        nl = "\n"
        e.add_field(
            name="Risk Tiers",
            value=f"```\n{nl.join(rows)}\n```",
            inline=False,
        )

        e.add_field(
            name="Notes",
            value=(
                "Payout shown is gross return (your bet is included). "
                "A 2x win on a 500 chip balance returns 1,000 chips - profit is 500.\n"
                "Bonus Bet Token is eligible on Standard and Bold tiers only (Tier 1-2).\n"
                "Multiplier Wheel bonuses do not apply to All-In.\n"
                "Lucky Streak bonus applies on any winning flip."
            ),
            inline=False,
        )

        await interaction.response.send_message(embed=e, ephemeral=True)

    # ------------------------------------------------------------------
    # Tier selected â†’ resolve
    # ------------------------------------------------------------------

    async def _on_tier_selected(self, interaction: discord.Interaction, tier: int) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._resolve(interaction, tier)

    async def _resolve(self, interaction: discord.Interaction, tier: int) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        cog    = self._cog

        # 1. Fetch live balance â€” this IS the bet.
        bet = await get_balance(member, conf, user)
        if bet <= 0:
            await interaction.followup.send(
                "You have no balance to wager. Earn some chips first!", ephemeral=True
            )
            return

        # 2. Deduct entire balance.
        await deduct_balance(member, conf, user, bet)

        # 3. Bonus Bet Token â€” partially eligible; consume_bonus_bet_token
        #    self-checks tier eligibility (tiers 1â€“2 only).
        token_active = False
        if has_bonus_bet_token(user):
            token_active = consume_bonus_bet_token(user, "allin", allin_tier=tier)

        # 4. Flip using the live-configured win chance for this tier.
        win_chance = get_game_rng(conf, "allin", f"tier{tier}_win_chance")
        won = flip(win_chance)

        # 5. Resolve payout.
        tier_data        = ALLIN_RISK_TIERS[tier]
        payout_mult      = tier_data["payout"]
        tier_name        = tier_data["name"]
        streak_cancelled = False

        if won:
            raw_payout   = calculate_payout(bet, payout_mult)
            total_payout = raw_payout

            # 5a. Lucky Streak bonus (+25% of raw payout).
            if has_lucky_streak(user):
                total_payout += apply_lucky_streak_bonus(raw_payout)

            # 5b. Multiplier Wheel â€” "allin" is NOT in MULTIPLIER_ELIGIBLE_GAMES;
            #     consume_multiplier is intentionally not called here.

            # 5c. Bonus Bet Token doubles total payout on a win.
            if token_active:
                total_payout *= 2

            await credit_balance(member, conf, user, total_payout)
            record_win(conf, user, "allin", total_payout, bet)

        else:
            total_payout = 0

            # On loss: cancel any active lucky streak.
            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True

            record_loss(conf, user, "allin", bet)

        # 6. Rank evaluation.
        new_rank     = evaluate_rank(conf, user)
        old_rank     = user.rank
        rank_changed = new_rank != old_rank
        if rank_changed:
            apply_rank_change(user, new_rank)

        # 7. Specialty titles.
        new_titles = evaluate_specialty_titles(user)
        user.earned_titles.extend(new_titles)

        # 8. Save.
        cog.save()

        # 9. Refresh cached balance for the embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # 10. Build result payload and update the message.
        result = {
            "bet":             bet,
            "tier":            tier,
            "tier_name":       tier_name,
            "payout_mult":     payout_mult,
            "won":             won,
            "total_payout":    total_payout,
            "streak_cancelled": streak_cancelled,
            "rank_changed":    rank_changed,
            "old_rank":        old_rank,
            "new_rank":        new_rank,
            "new_titles":      new_titles,
        }

        self.clear_items()
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_embed(result=result), view=self)

    # ------------------------------------------------------------------
    # Embed builder  (sync â€” uses cached balance)
    # ------------------------------------------------------------------

    def _build_embed(self, result: dict | None = None) -> discord.Embed:
        conf = self._conf
        user = self._user
        e    = discord.Embed(title="High Roller - All-In", color=PALETTE_GOLD)
        nl   = "\n"

        if result is not None:            # ---- Result phase ----
            bet          = result["bet"]
            tier_name    = result["tier_name"]
            payout_mult  = result["payout_mult"]
            won          = result["won"]
            total_payout = result["total_payout"]
            cur          = self._cached_currency

            coin_art = _COIN_WIN if won else _COIN_LOSS
            desc = f"```\n{coin_art}\n```"
            desc += f"\n*{_TIER_FLAVOR.get(result['tier'], '')}*"

            if won:
                desc += f"\n✅ **{tier_name} flip — You won!**"
                desc += (
                    f"\nWagered: **{bet:,}** {cur} at **{payout_mult}×**"
                    f" → Payout: **{total_payout:,}** {cur}"
                )
                desc += f"\n*{random.choice(_WIN_FLAVOR)}*"
            else:
                desc += f"\n❌ **{tier_name} flip — You lost everything.**"
                desc += f"\nWagered: **{bet:,}** {cur} at **{payout_mult}×** — gone."
                desc += f"\n*{random.choice(_LOSS_FLAVOR)}*"

            if result.get("streak_cancelled"):
                desc += "\n💔 **Your lucky streak has ended.**"

            if result.get("rank_changed"):
                old_name = RANK_NAMES.get(result["old_rank"], "Unknown")
                new_name = RANK_NAMES.get(result["new_rank"], "Unknown")
                if result["new_rank"] > result["old_rank"]:
                    desc += f"\n🏆 **Rank Up!** You are now a **{new_name}**!"
                else:
                    desc += (
                        f"\n📉 **Rank Down.** You have dropped to "
                        f"**{old_name}** → **{new_name}**."
                    )

            for slug in result.get("new_titles", []):
                title_str = SPECIALTY_TITLES.get(slug, slug)
                desc += f"\n🎖️ **New title unlocked:** {title_str}"

        else:
            # ---- Idle phase ----
            max_tier = conf.allin_max_tier
            cur      = self._cached_currency
            bal_str  = (
                f"{self._cached_balance:,} {cur}"
                if self._cached_balance is not None
                else "your full balance"
            )

            desc = (
                f"💰 **Your entire balance is on the line: {bal_str}**\n\n"
                "One flip. No take-backs. Choose a tier below and see if fortune favors you.\n"
            )

            header  = f"{'Tier':<5}  {'Name':<12}  {'Win%':<6}  Payout"
            divider = "─" * len(header)
            rows    = [header, divider]
            for t, data in ALLIN_RISK_TIERS.items():
                if t > max_tier:
                    break
                win_chance = get_game_rng(conf, "allin", f"tier{t}_win_chance")
                win_pct    = f"{win_chance * 100:.0f}%"
                rows.append(f"{t:<5}  {data['name']:<12}  {win_pct:<6}  {data['payout']}×")

            desc += f"```\n{nl.join(rows)}\n```"

            mul = get_pending_multiplier(user)
            if mul is not None:
                desc += (
                    f"\n⚡ Bonus snapshot: **{mul}×** multiplier "
                    "*(stored on your account, but Multiplier Wheel does not apply to All-In)*"
                )
            if has_bonus_bet_token(user):
                desc += "\n🎫 Bonus snapshot: Bonus Bet Token doubles payout if it is still unused when a Tier 1-2 win resolves."

        e.description = desc

        if url := embed_image("allin"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e
