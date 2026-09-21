"""WarView — Discord UI for the War card game in HighRollerClub.

Game flow
---------
Phase 1 (idle)   : Player sees the bet prompt with active bonus indicators.
                   Buttons: Deal Cards | Back to Floor | How to Play

Phase 2 (result) : Cards are drawn and the game resolves in one step.
                   On a tie, the War round is drawn automatically and both
                   the initial and war outcomes are shown in a single embed.
                   Buttons: Change Bet | Deal (last bet) | Back to Floor

War round
---------
If the initial draw ties, an additional equal bet is deducted automatically
and both sides draw again.  The higher card takes the whole pot.

  War win  : gross return = 4× original bet  (net profit = 2× original bet).
  War loss : both bets forfeited (2× original bet lost).
  Second tie: treated as a War win in the player's favour.

If the player cannot afford the additional war bet at the time of the tie
(e.g. they wagered their exact remaining balance), the original bet is
recorded as a loss and the War round is skipped with a clear notification.

Bonus stacking order (same on normal win and War win)
------------------------------------------------------
  1. Compute raw_payout from game logic.
  2. Add lucky_streak_bonus = apply_lucky_streak_bonus(raw_payout) if active.
  3. total_payout = raw_payout + lucky_streak_bonus.
  4. If Multiplier Wheel active: profit = total_payout - amount_deducted;
     total_payout += int(profit × (multiplier − 1.0)).
  5. If Bonus Bet Token active: total_payout × 2.

The Bonus Bet Token is consumed before the initial draw.  On a loss or War
loss the token is consumed without effect — consistent with Slots behaviour.

Pure game logic (Card, draw_card, compare, payouts) lives in games/war.py.
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
    get_pending_multiplier,
    has_bonus_bet_token,
    has_lucky_streak,
    is_allowed_channel,
    record_loss,
    record_win,
    validate_bet,
)
from ..games.war import Card, compare, draw_card, normal_payout, war_payout

# ---------------------------------------------------------------------------
# Flavor text
# ---------------------------------------------------------------------------

_WIN_FLAVOR: list[str] = [
    "A high card at the right moment — the hallmark of fortune.",
    "The house revealed its hand, and yours was better.",
    "Clean, decisive, undeniable.",
    "A lesser card for the house — a richer wallet for you.",
    "Not luck — destiny.",
    "The Club bows to the better draw.",
    "Even the dealers nod in respect.",
]

_LOSS_FLAVOR: list[str] = [
    "The house pulls ahead — for now.",
    "A sharp card from the dealer. Better luck next round.",
    "The deck has no allegiances.",
    "Sometimes the cards decide. They decided quickly.",
    "The house remembers every loss.",
    "Fortune favors the persistent.",
    "The Club will be here when you're ready to try again.",
]

_WAR_WIN_FLAVOR: list[str] = [
    "You charged into battle and emerged victorious.",
    "The second draw was yours — and the pot followed.",
    "A war fought, a war won.",
    "They matched you card for card — until they couldn't.",
    "Double the stakes, double the triumph.",
    "The battlefield cleared, and you stood on top.",
    "Nerves and a good card — a winning combination.",
]

_WAR_LOSS_FLAVOR: list[str] = [
    "The war was costly, and the house claimed the spoils.",
    "Two rounds fought, two bets lost.",
    "The dealer's second card proved decisive.",
    "Not every war can be won — but every war teaches something.",
    "The house doesn't blink in battle.",
    "High stakes, higher price.",
    "A valiant charge that the cards did not reward.",
]

_TIE_FLAVOR: list[str] = [
    "A dead heat. The war must decide it.",
    "Matched card for card — going to War!",
    "Equal hands demand an equal test.",
    "No one wins a tie in this Club. Draw again.",
]


# ---------------------------------------------------------------------------
# Bet modal
# ---------------------------------------------------------------------------

class BetModal(discord.ui.Modal, title="Place Your Bet — War"):
    def __init__(self, view: WarView, min_bet: int, max_bet: int) -> None:
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
# Main War View
# ---------------------------------------------------------------------------

class WarView(discord.ui.View):
    """Discord UI view for the War card game.

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

        # Balance cache — refreshed after every resolve so _build_embed stays sync.
        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        # Last validated bet — enables the "Deal Same Bet" shortcut button.
        self._last_bet: int | None = None

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
        deal = discord.ui.Button(
            label="⚔️ Deal Cards", style=discord.ButtonStyle.green, row=0
        )
        deal.callback = self._on_deal
        self.add_item(deal)

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

    def _add_result_buttons(self) -> None:
        change = discord.ui.Button(
            label="⚔️ Change Bet", style=discord.ButtonStyle.blurple, row=0
        )
        change.callback = self._play_again
        self.add_item(change)

        if self._last_bet is not None:
            same = discord.ui.Button(
                label=f"⚔️ Deal ({self._last_bet:,})",
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
                "War can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False

        if not conf.games_enabled.get("war", True):
            await interaction.response.send_message(
                "War is currently disabled on this server.",
                ephemeral=True,
            )
            return False

        return True

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------

    async def _on_deal(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        min_bet, max_bet = get_bet_limits(self._conf, "war", self._user.rank)
        await interaction.response.send_modal(BetModal(self, min_bet, max_bet))

    async def _deal_same_bet(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await safe_defer(interaction)
        await self._resolve(interaction, self._last_bet)

    async def _play_again(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        self.clear_items()
        self._add_idle_buttons()
        await safe_response_edit_message(interaction, embed=self._build_embed(), view=self)

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="⚔️ How to Play — War", color=PALETTE_GOLD)
        e.description = (
            "A classic card showdown. Both you and the house draw one card. "
            "The higher card wins. Aces are the highest card in the deck."
        )

        e.add_field(
            name="Outcomes",
            value=(
                "```\n"
                "Win    Higher card → 1:1 payout (2× your bet returned)\n"
                "Lose   Lower card  → Bet is lost\n"
                "Tie    Equal ranks → War! (automatic, see below)\n"
                "```"
            ),
            inline=False,
        )

        e.add_field(
            name="⚔️ War Round (automatic on tie)",
            value=(
                "On a tie, an additional equal bet is placed automatically. "
                "Both you and the house draw again. The higher card takes the whole pot.\n\n"
                "**War Win:** Returns 2× the total wagered (**4× your original bet**)\n"
                "**War Loss:** Both bets are lost (**2× your original bet**)\n"
                "**Second Tie:** Treated as a War win."
            ),
            inline=False,
        )

        e.add_field(
            name="Bonuses",
            value=(
                "• **Bonus Bet Token** — doubles payout on any win (normal or War). "
                "Consumed before the deal; no effect on a loss.\n"
                "• **Multiplier Wheel** — applies to profit on any win\n"
                "• **Lucky Streak** — adds 25% to raw payout on any win; "
                "cancelled on any loss"
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
        user = self._user
        e = discord.Embed(title="⚔️ High Roller — War", color=PALETTE_GOLD)

        if result is None:
            # ---- Idle / ready state ----
            desc = (
                "**Draw a card. Beat the house. Win the hand.**\n\n"
                "Place your bet and click **Deal Cards** to play.\n"
                "On a tie, the War round fires automatically — "
                "an additional equal bet is deducted and both sides draw again."
            )

            mul = get_pending_multiplier(user)
            if mul is not None:
                desc += f"\n⚡ Bonus snapshot: **{mul}×** multiplier if it is still active on your next win."
            if has_bonus_bet_token(user):
                desc += "\n🎫 Bonus snapshot: Bonus Bet Token doubles payout if it is still unused when a win resolves."

        else:
            # ---- Result state ----
            bet         = result["bet"]
            outcome     = result["outcome"]  # "win" | "loss" | "war_win" | "war_loss" | "war_forfeit"
            player_card: Card = result["player_card"]
            house_card: Card  = result["house_card"]
            payout      = result["payout"]
            cur         = self._cached_currency

            card_block = (
                f"```\n"
                f"  You  : {player_card.label}\n"
                f"  House: {house_card.label}\n"
                f"```"
            )

            if outcome in ("war_win", "war_loss"):
                war_player: Card = result["war_player_card"]
                war_house: Card  = result["war_house_card"]
                war_block = (
                    f"```\n"
                    f"  ⚔️  WAR ROUND\n"
                    f"  You  : {war_player.label}\n"
                    f"  House: {war_house.label}\n"
                    f"```"
                )
            else:
                war_block = ""

            if outcome == "win":
                desc = (
                    f"{card_block}"
                    f"\n✅ **Your {player_card.label} beats the house {house_card.label}!**"
                    f"\nBet: **{bet:,}** {cur} → Payout: **{payout:,}** {cur}"
                    f"\n*{random.choice(_WIN_FLAVOR)}*"
                )
            elif outcome == "loss":
                desc = (
                    f"{card_block}"
                    f"\n❌ **House {house_card.label} beats your {player_card.label}.**"
                    f"\nBet of **{bet:,}** {cur} lost."
                    f"\n*{random.choice(_LOSS_FLAVOR)}*"
                )
            elif outcome == "war_win":
                tie_flavor = random.choice(_TIE_FLAVOR)
                war_player = result["war_player_card"]
                war_house  = result["war_house_card"]
                desc = (
                    f"{card_block}"
                    f"\n⚔️ *{tie_flavor}*"
                    f"\n{war_block}"
                    f"\n✅ **War Won! Your {war_player.label} over the house {war_house.label}.**"
                    f"\nTotal wagered: **{bet * 2:,}** {cur} → Payout: **{payout:,}** {cur}"
                    f"\n*{random.choice(_WAR_WIN_FLAVOR)}*"
                )
            elif outcome == "war_loss":
                tie_flavor = random.choice(_TIE_FLAVOR)
                war_player = result["war_player_card"]
                war_house  = result["war_house_card"]
                desc = (
                    f"{card_block}"
                    f"\n⚔️ *{tie_flavor}*"
                    f"\n{war_block}"
                    f"\n❌ **War Lost. House {war_house.label} over your {war_player.label}.**"
                    f"\nBoth bets lost — **{bet * 2:,}** {cur} gone."
                    f"\n*{random.choice(_WAR_LOSS_FLAVOR)}*"
                )
            else:  # war_forfeit
                desc = (
                    f"{card_block}"
                    f"\n⚔️ **Tie! But not enough chips to cover the War bet.**"
                    f"\nOriginal bet of **{bet:,}** {cur} is lost."
                    f"\n*The house takes the forfeit.*"
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

        if url := embed_image("war"):
            e.set_thumbnail(url=url)

        if self._cached_balance is not None:
            e.set_footer(
                text=f"Balance: {self._cached_balance:,} {self._cached_currency}"
            )

        return e

    # ------------------------------------------------------------------
    # Game resolution  (called from BetModal.on_submit and _deal_same_bet)
    # ------------------------------------------------------------------

    async def _resolve(self, interaction: discord.Interaction, bet: int) -> None:
        member = self._member
        conf   = self._conf
        user   = self._user
        cog    = self._cog

        # 1. Validate bet against current balance.
        balance = await get_balance(member, conf, user)
        error = validate_bet(conf, user, "war", bet, balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        # Store for the "Deal Same Bet" shortcut button.
        self._last_bet = bet

        # 2. Consume Bonus Bet Token before drawing — consistent with the
        #    rest of the codebase (consumed regardless of outcome; only pays
        #    out on a win).
        token_active = False
        if has_bonus_bet_token(user):
            token_active = consume_bonus_bet_token(user, "war")

        # 3. Deduct initial bet.
        await deduct_balance(member, conf, user, bet)

        # 4. Draw the initial cards and compare.
        player_card = draw_card()
        house_card  = draw_card()
        initial_result = compare(player_card, house_card)

        streak_cancelled = False
        war_player_card: Card | None = None
        war_house_card: Card | None = None
        total_payout: int = 0
        outcome: str

        if initial_result == "win":
            # ----------------------------------------------------------------
            # Normal win — 1:1 payout.
            # ----------------------------------------------------------------
            raw_payout   = normal_payout(bet)
            total_payout = raw_payout

            if has_lucky_streak(user):
                total_payout += apply_lucky_streak_bonus(raw_payout)

            if "war" in MULTIPLIER_ELIGIBLE_GAMES:
                multiplier = consume_multiplier(user)
                if multiplier is not None:
                    profit = total_payout - bet
                    total_payout += int(profit * (multiplier - 1.0))

            if token_active:
                total_payout *= 2

            await credit_balance(member, conf, user, total_payout)
            record_win(conf, user, "war", total_payout, bet)
            outcome = "win"

        elif initial_result == "loss":
            # ----------------------------------------------------------------
            # Normal loss.
            # ----------------------------------------------------------------
            if has_lucky_streak(user):
                cancel_lucky_streak(user)
                streak_cancelled = True

            record_loss(conf, user, "war", bet)
            outcome = "loss"

        else:
            # ----------------------------------------------------------------
            # Tie — War round fires automatically.
            # ----------------------------------------------------------------
            post_bet_balance = await get_balance(member, conf, user)

            if post_bet_balance < bet:
                # Cannot afford the additional war bet; forfeit original bet.
                if has_lucky_streak(user):
                    cancel_lucky_streak(user)
                    streak_cancelled = True
                record_loss(conf, user, "war", bet)
                outcome = "war_forfeit"
            else:
                # Deduct the war bet (equal to original bet).
                await deduct_balance(member, conf, user, bet)
                total_wagered = bet * 2

                # Draw war-round cards.
                war_player_card = draw_card()
                war_house_card  = draw_card()
                war_result      = compare(war_player_card, war_house_card)

                if war_result in ("win", "tie"):
                    # War win (second tie also resolves as a win for the player).
                    raw_payout   = war_payout(bet)   # = 4 × original_bet
                    total_payout = raw_payout

                    if has_lucky_streak(user):
                        total_payout += apply_lucky_streak_bonus(raw_payout)

                    if "war" in MULTIPLIER_ELIGIBLE_GAMES:
                        multiplier = consume_multiplier(user)
                        if multiplier is not None:
                            profit = total_payout - total_wagered
                            total_payout += int(profit * (multiplier - 1.0))

                    if token_active:
                        total_payout *= 2

                    await credit_balance(member, conf, user, total_payout)
                    record_win(conf, user, "war", total_payout, total_wagered)
                    outcome = "war_win"

                else:
                    # War loss — both bets gone.
                    if has_lucky_streak(user):
                        cancel_lucky_streak(user)
                        streak_cancelled = True

                    record_loss(conf, user, "war", total_wagered)
                    outcome = "war_loss"

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
        cog.save()

        # 8. Refresh cached balance for the embed footer.
        self._cached_balance = await get_balance(member, conf, user)
        if conf.payment_mode != "chips":
            self._cached_currency = await bank.get_currency_name(member.guild)

        # 9. Build result payload and update the message.
        result = {
            "bet":             bet,
            "outcome":         outcome,
            "player_card":     player_card,
            "house_card":      house_card,
            "war_player_card": war_player_card,
            "war_house_card":  war_house_card,
            "payout":          total_payout,
            "streak_cancelled": streak_cancelled,
            "rank_changed":    rank_changed,
            "old_rank":        old_rank,
            "new_rank":        new_rank,
            "new_titles":      new_titles,
        }

        self.clear_items()
        self._add_result_buttons()
        await safe_edit_original_response(interaction, embed=self._build_embed(result=result), view=self)
