"""Club Poker -- private two-player 5-card draw poker.

Flow
----
1. Challenger posts a public challenge for one opponent and ante amount.
2. Opponent accepts publicly; both antes are deducted.
3. Both players privately view 5-card hands via ephemeral controls.
4. Each player privately selects holds and locks in their draw.
5. Once both lock, redraws are applied from a shared deck in fixed order:
   challenger first, challenged second.
6. One fixed betting round follows:
   - Challenger acts first.
   - If no bet is open: Stay or Bet.
   - If a bet is open: Call or Fold.
   - No raises.
7. If no fold occurs, showdown compares both final hands.
8. The winning hand is always shown publicly. The losing player gets
    15 seconds to Show Hand or Muck Hand. Timeout defaults to muck.
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field

import discord
from redbot.core import bank

from ..abc import MixinMeta
from ..common.interactions import safe_defer, safe_edit_original_response, safe_response_edit_message
from ..common.constants import PALETTE_GOLD, RANK_NAMES, SPECIALTY_TITLES, embed_image
from ..common.models import GuildSettings, User
from ..commands.helper_functions import (
    apply_lucky_streak_bonus,
    apply_rank_change,
    cancel_lucky_streak,
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
from ..games.poker import CP_HAND_NAMES, Card, Deck, compare_cp_showdown, evaluate_cp_hand


_CP_WIN_FLAVOR: dict[str, str] = {
    "royal_flush": "An historic hand. The table will talk about this for years.",
    "straight_flush": "Five in sequence, same suit. A beautiful hand.",
    "four_of_a_kind": "Four of a kind. Dominant from the start.",
    "full_house": "Full house. There was no coming back from that.",
    "flush": "A flush at exactly the right moment.",
    "straight": "Straight. The better hand, cleanly dealt.",
    "three_of_a_kind": "Three of a kind held the edge tonight.",
    "two_pair": "Two pair was enough this time.",
    "pair": "A pair sealed the win.",
    "high_card": "High card takes it when no one makes a hand.",
}

_CP_TIE_FLAVOR: list[str] = [
    "Identical hands. The pot splits down the middle.",
    "Dead even. Both wagers come back home.",
    "A standoff. No winner, no loser tonight.",
]


@dataclass
class _ClubPokerPlayerState:
    member: discord.Member
    user: User
    hand: list[Card] = field(default_factory=list)
    held: list[bool] = field(default_factory=lambda: [False, False, False, False, False])
    draw_locked: bool = False
    cards_replaced: int = 0
    extra_committed: int = 0

    @property
    def committed_total(self) -> int:
        return self.extra_committed


class _ClubPokerSession:
    def __init__(
        self,
        challenger: discord.Member,
        challenger_user: User,
        challenged: discord.Member,
        challenged_user: User,
        conf: GuildSettings,
        cog: MixinMeta,
        ante: int,
        currency: str,
    ) -> None:
        self.challenger = _ClubPokerPlayerState(challenger, challenger_user)
        self.challenged = _ClubPokerPlayerState(challenged, challenged_user)
        self.conf = conf
        self.cog = cog
        self.ante = ante
        self.currency = currency
        self.deck = Deck()
        self.lock = asyncio.Lock()
        self.phase = "draw"
        self.turn_user_id = challenger.id
        self.bet_open = False
        self.bettor_id: int | None = None
        self.first_check_complete = False
        self.public_message: discord.Message | None = None
        self.public_view: ClubPokerSessionView | None = None
        self.result: dict | None = None
        self.loser_visibility: str | None = None
        self.loser_user_id: int | None = None
        self._muck_task: asyncio.Task | None = None
        self._resolved = False

        self.challenger.hand = self.deck.deal(5)
        self.challenged.hand = self.deck.deal(5)

    def all_players(self) -> list[_ClubPokerPlayerState]:
        return [self.challenger, self.challenged]

    def is_participant(self, user_id: int) -> bool:
        return user_id in {self.challenger.member.id, self.challenged.member.id}

    def player_for(self, user_id: int) -> _ClubPokerPlayerState:
        if user_id == self.challenger.member.id:
            return self.challenger
        if user_id == self.challenged.member.id:
            return self.challenged
        raise KeyError(f"Unknown player id: {user_id}")

    def other_player(self, user_id: int) -> _ClubPokerPlayerState:
        if user_id == self.challenger.member.id:
            return self.challenged
        if user_id == self.challenged.member.id:
            return self.challenger
        raise KeyError(f"Unknown player id: {user_id}")

    def total_pot(self) -> int:
        return (self.ante * 2) + self.challenger.extra_committed + self.challenged.extra_committed

    def committed_total_for(self, player: _ClubPokerPlayerState) -> int:
        return self.ante + player.extra_committed

    def _challenger_hand_text(self) -> tuple[str, str]:
        return (
            "  ".join(card.label for card in self.challenger.hand),
            CP_HAND_NAMES[evaluate_cp_hand(self.challenger.hand)],
        )

    def _challenged_hand_text(self) -> tuple[str, str]:
        return (
            "  ".join(card.label for card in self.challenged.hand),
            CP_HAND_NAMES[evaluate_cp_hand(self.challenged.hand)],
        )

    def replacement_count_for(self, user_id: int) -> int:
        return self.player_for(user_id).cards_replaced

    def _status_line(self) -> str:
        if self.phase == "draw":
            return (
                f"{self.challenger.member.mention}: {'locked' if self.challenger.draw_locked else 'choosing cards'}\n"
                f"{self.challenged.member.mention}: {'locked' if self.challenged.draw_locked else 'choosing cards'}"
            )
        if self.phase == "betting":
            actor = self.player_for(self.turn_user_id).member.mention
            if self.bet_open and self.bettor_id is not None:
                bettor = self.player_for(self.bettor_id).member.mention
                return f"Betting round: {bettor} opened betting for **{self.ante:,} {self.currency}**. Waiting on {actor}."
            return f"Betting round: it is {actor}'s turn."
        if self.phase == "muck_choice":
            if self.loser_user_id is None:
                return "The losing player has 15 seconds to show or muck their hand."
            loser = self.player_for(self.loser_user_id).member.mention
            return f"{loser} has 15 seconds to show or muck their hand."
        if self.phase == "cancelled":
            return "The hand was cancelled and all committed bets were refunded."
        return "Hand resolved."

    def build_public_embed(self) -> discord.Embed:
        if self.result is None:
            embed = discord.Embed(title="🃏 Club Poker", color=PALETTE_GOLD)
            embed.description = (
                f"**Players:** {self.challenger.member.mention} vs {self.challenged.member.mention}\n"
                f"**Ante:** {self.ante:,} {self.currency} each\n"
                f"**Pot:** {self.total_pot():,} {self.currency}\n\n"
                "Both players must open their private hand, choose holds, and lock in their draw.\n\n"
                f"{self._status_line()}"
            )
            if url := embed_image("clubpoker"):
                embed.set_thumbnail(url=url)
            return embed

        challenger_cards, challenger_hand_name = self._challenger_hand_text()
        challenged_cards, challenged_hand_name = self._challenged_hand_text()

        outcome = self.result["outcome"]
        winner = self.result["winner"]
        total_payout = self.result["total_payout"]
        net_profit = self.result["net_profit"]
        streak_bonus = self.result["streak_bonus"]
        streak_cancelled = self.result["streak_cancelled"]
        fold_user = self.result["fold_user"]

        challenged_section: str
        challenged_is_loser = self.loser_user_id == self.challenged.member.id
        if not challenged_is_loser:
            challenged_section = f"**{self.challenged.member.mention}:**\n{challenged_cards}\n*{challenged_hand_name}*"
        elif self.loser_visibility == "show":
            challenged_section = f"**{self.challenged.member.mention}:**\n{challenged_cards}\n*{challenged_hand_name}*"
        elif self.loser_visibility == "muck":
            challenged_section = f"**{self.challenged.member.mention}:**\n🂠 Hand mucked."
        else:
            challenged_section = f"**{self.challenged.member.mention}:**\n🂠 Hand hidden pending reveal choice."

        challenger_is_loser = self.loser_user_id == self.challenger.member.id
        if not challenger_is_loser:
            challenger_section = f"**{self.challenger.member.mention}:**\n{challenger_cards}\n*{challenger_hand_name}*"
        elif self.loser_visibility == "show":
            challenger_section = f"**{self.challenger.member.mention}:**\n{challenger_cards}\n*{challenger_hand_name}*"
        elif self.loser_visibility == "muck":
            challenger_section = f"**{self.challenger.member.mention}:**\n🂠 Hand mucked."
        else:
            challenger_section = f"**{self.challenger.member.mention}:**\n🂠 Hand hidden pending reveal choice."

        lines = [
            challenger_section,
            challenged_section,
            "",
        ]

        if outcome == "tie":
            lines.append(f"🤝 **Tie!** Both players get their committed bets back.")
            lines.append(f"*{random.choice(_CP_TIE_FLAVOR)}*")
        elif outcome == "fold":
            assert winner is not None
            lines.append(f"🏆 **{winner.mention} wins by fold.**")
            if fold_user is not None:
                lines.append(f"{fold_user.mention} folded during the betting round.")
            lines.append(
                f"Pot: **{self.total_pot():,}** {self.currency} → Payout: **{total_payout:,}** {self.currency} *(+{net_profit:,} profit)*"
            )
            lines.append(f"*{_CP_WIN_FLAVOR.get(self.result['winner_rank'], 'The better line took the pot.')}*")
        else:
            assert winner is not None
            lines.append(f"🏆 **{winner.mention} wins at showdown.**")
            lines.append(
                f"Pot: **{self.total_pot():,}** {self.currency} → Payout: **{total_payout:,}** {self.currency} *(+{net_profit:,} profit)*"
            )
            lines.append(f"*{_CP_WIN_FLAVOR.get(self.result['winner_rank'], 'The better hand wins.')}*")

        if streak_bonus > 0:
            lines.append(f"🔥 **Lucky Streak Bonus:** +{streak_bonus:,} {self.currency}")
        if streak_cancelled is not None:
            lines.append(f"💔 {streak_cancelled.mention}'s lucky streak ended.")
        if self.phase == "muck_choice" and self.loser_visibility is None:
            lines.append("⏳ Waiting for the losing player to show or muck their hand.")

        embed = discord.Embed(
            title="🃏 Club Poker -- Result",
            color=PALETTE_GOLD if self.phase != "cancelled" else discord.Color.red(),
            description="\n".join(lines),
        )
        if url := embed_image("clubpoker"):
            embed.set_thumbnail(url=url)
        return embed

    async def refresh_public(self) -> None:
        if self.public_message is None or self.public_view is None:
            return
        self.public_view.sync_items()
        await self.public_message.edit(embed=self.build_public_embed(), view=self.public_view)

    async def cancel_and_refund(self, reason: str) -> None:
        if self._resolved:
            return
        if self.phase != "draw" and self.phase != "betting":
            return
        self._resolved = True
        self.phase = "cancelled"
        await credit_balance(self.challenger.member, self.conf, self.challenger.user, self.committed_total_for(self.challenger))
        await credit_balance(self.challenged.member, self.conf, self.challenged.user, self.committed_total_for(self.challenged))
        self.result = {
            "outcome": "cancelled",
            "winner": None,
            "winner_rank": None,
            "total_payout": 0,
            "net_profit": 0,
            "streak_bonus": 0,
            "streak_cancelled": None,
            "fold_user": None,
            "reason": reason,
        }
        self.cog.save()
        await self.refresh_public()

    async def lock_draw(self, user_id: int) -> None:
        player = self.player_for(user_id)
        player.draw_locked = True
        if not all(p.draw_locked for p in self.all_players()):
            await self.refresh_public()
            return

        for p in (self.challenger, self.challenged):
            p.cards_replaced = 0
            for idx in range(5):
                if not p.held[idx]:
                    p.cards_replaced += 1
                    p.hand[idx] = self.deck.draw()

        self.phase = "betting"
        self.turn_user_id = self.challenger.member.id
        self.bet_open = False
        self.bettor_id = None
        self.first_check_complete = False
        await self.refresh_public()

    async def take_check(self, user_id: int) -> None:
        if self.phase != "betting" or self.bet_open or self.turn_user_id != user_id:
            return
        if user_id == self.challenger.member.id and not self.first_check_complete:
            self.first_check_complete = True
            self.turn_user_id = self.challenged.member.id
            await self.refresh_public()
            return
        await self.resolve_hand()

    async def open_bet(self, user_id: int) -> str | None:
        if self.phase != "betting" or self.bet_open or self.turn_user_id != user_id:
            return None
        player = self.player_for(user_id)
        balance = await get_balance(player.member, self.conf, player.user)
        if balance < self.ante:
            return f"You no longer have enough {self.currency} to open betting for **{self.ante:,}**."
        await deduct_balance(player.member, self.conf, player.user, self.ante)
        player.extra_committed += self.ante
        self.bet_open = True
        self.bettor_id = user_id
        self.turn_user_id = self.other_player(user_id).member.id
        await self.refresh_public()
        return None

    async def call_bet(self, user_id: int) -> str | None:
        if self.phase != "betting" or not self.bet_open or self.turn_user_id != user_id:
            return None
        player = self.player_for(user_id)
        balance = await get_balance(player.member, self.conf, player.user)
        if balance < self.ante:
            return f"You no longer have enough {self.currency} to call **{self.ante:,}**."
        await deduct_balance(player.member, self.conf, player.user, self.ante)
        player.extra_committed += self.ante
        await self.resolve_hand()
        return None

    async def fold_hand(self, user_id: int) -> None:
        if self.phase != "betting" or not self.bet_open or self.turn_user_id != user_id:
            return
        await self.resolve_hand(fold_user_id=user_id)

    async def resolve_hand(self, fold_user_id: int | None = None) -> None:
        if self._resolved:
            return

        challenger_rank = evaluate_cp_hand(self.challenger.hand)
        challenged_rank = evaluate_cp_hand(self.challenged.hand)

        streak_bonus = 0
        streak_cancelled: discord.Member | None = None
        total_payout = 0
        net_profit = 0
        winner: discord.Member | None = None
        winner_player: _ClubPokerPlayerState | None = None
        loser_player: _ClubPokerPlayerState | None = None
        outcome: str

        if fold_user_id is not None:
            loser_player = self.player_for(fold_user_id)
            winner_player = self.other_player(fold_user_id)
            winner = winner_player.member
            outcome = "fold"
            total_payout = self.total_pot()
            if has_lucky_streak(winner_player.user):
                streak_bonus = apply_lucky_streak_bonus(total_payout)
                total_payout += streak_bonus
            await credit_balance(winner_player.member, self.conf, winner_player.user, total_payout)
            winner_bet = self.committed_total_for(winner_player)
            loser_bet = self.committed_total_for(loser_player)
            record_win(self.conf, winner_player.user, "clubpoker", total_payout, winner_bet)
            record_loss(self.conf, loser_player.user, "clubpoker", loser_bet)
            if has_lucky_streak(loser_player.user):
                cancel_lucky_streak(loser_player.user)
                streak_cancelled = loser_player.member
            net_profit = total_payout - winner_bet
        else:
            comparison = compare_cp_showdown(self.challenger.hand, self.challenged.hand)
            if comparison == 0:
                outcome = "tie"
                await credit_balance(self.challenger.member, self.conf, self.challenger.user, self.committed_total_for(self.challenger))
                await credit_balance(self.challenged.member, self.conf, self.challenged.user, self.committed_total_for(self.challenged))
            else:
                winner_player = self.challenger if comparison > 0 else self.challenged
                loser_player = self.challenged if comparison > 0 else self.challenger
                winner = winner_player.member
                outcome = "showdown"
                total_payout = self.total_pot()
                if has_lucky_streak(winner_player.user):
                    streak_bonus = apply_lucky_streak_bonus(total_payout)
                    total_payout += streak_bonus
                await credit_balance(winner_player.member, self.conf, winner_player.user, total_payout)
                winner_bet = self.committed_total_for(winner_player)
                loser_bet = self.committed_total_for(loser_player)
                record_win(self.conf, winner_player.user, "clubpoker", total_payout, winner_bet)
                record_loss(self.conf, loser_player.user, "clubpoker", loser_bet)
                if has_lucky_streak(loser_player.user):
                    cancel_lucky_streak(loser_player.user)
                    streak_cancelled = loser_player.member
                net_profit = total_payout - winner_bet

        for player in self.all_players():
            old_rank = player.user.rank
            new_rank = evaluate_rank(self.conf, player.user)
            if new_rank != old_rank:
                apply_rank_change(player.user, new_rank)
            new_titles = evaluate_specialty_titles(player.user)
            player.user.earned_titles.extend(new_titles)

        self.cog.save()

        self.result = {
            "outcome": outcome,
            "winner": winner,
            "winner_rank": challenger_rank if winner == self.challenger.member else challenged_rank,
            "challenger_rank": challenger_rank,
            "challenged_rank": challenged_rank,
            "total_payout": total_payout,
            "net_profit": net_profit,
            "streak_bonus": streak_bonus,
            "streak_cancelled": streak_cancelled,
            "fold_user": self.player_for(fold_user_id).member if fold_user_id is not None else None,
        }

        self.phase = "muck_choice"
        self.turn_user_id = None
        self.bet_open = False
        self.bettor_id = None
        self._resolved = True
        self.loser_user_id = loser_player.member.id if loser_player is not None else None
        self.loser_visibility = None
        if outcome == "tie" or self.loser_user_id is None:
            self.phase = "resolved"
        else:
            if self._muck_task is not None:
                self._muck_task.cancel()
            self._muck_task = asyncio.create_task(self._auto_muck())
        await self.refresh_public()

    async def _auto_muck(self) -> None:
        try:
            await asyncio.sleep(15)
        except asyncio.CancelledError:
            return
        async with self.lock:
            if self.phase == "muck_choice" and self.loser_visibility is None:
                self.loser_visibility = "muck"
                self.phase = "resolved"
                await self.refresh_public()

    async def set_loser_visibility(self, visibility: str) -> None:
        if self.phase != "muck_choice" or self.loser_visibility is not None:
            return
        self.loser_visibility = visibility
        self.phase = "resolved"
        if self._muck_task is not None:
            self._muck_task.cancel()
            self._muck_task = None
        await self.refresh_public()


class ClubPokerChallengeModal(discord.ui.Modal, title="Club Poker: Challenge a Player"):
    def __init__(self, view: "ClubPokerView") -> None:
        super().__init__()
        self._view = view
        min_bet, max_bet = get_bet_limits(view._conf, "clubpoker", view._user.rank)
        self.bet_input = discord.ui.TextInput(
            label=f"Ante Amount (min {min_bet:,} · max {max_bet:,})",
            placeholder=f"Enter {min_bet:,} to {max_bet:,}",
            min_length=1,
            max_length=10,
        )
        self.opponent_input = discord.ui.TextInput(
            label="Opponent (@mention, exact name, or user ID)",
            placeholder="@username  or  Display Name  or  123456789012345678",
            min_length=2,
            max_length=50,
        )
        self.add_item(self.bet_input)
        self.add_item(self.opponent_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await safe_defer(interaction)
        await self._view._process_challenge(
            interaction,
            self.bet_input.value,
            self.opponent_input.value,
        )


class ClubPokerView(discord.ui.View):
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

        if conf.payment_mode == "chips":
            self._cached_balance: int | None = user.chip_balance
            self._cached_currency: str = "chips"
        else:
            self._cached_balance = None
            self._cached_currency = ""

        self._add_idle_buttons()

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

    def _add_idle_buttons(self) -> None:
        self.clear_items()
        challenge_btn = discord.ui.Button(label="🃏 Challenge a Player", style=discord.ButtonStyle.green, row=0)
        challenge_btn.callback = self._on_challenge
        self.add_item(challenge_btn)

        back = discord.ui.Button(label="↩ Back to Floor", style=discord.ButtonStyle.grey, row=0)
        back.callback = self._back_to_floor
        self.add_item(back)

        info = discord.ui.Button(label="ℹ️ How to Play", style=discord.ButtonStyle.grey, row=1)
        info.callback = self._show_info
        self.add_item(info)

    async def _check_access(self, interaction: discord.Interaction) -> bool:
        if not is_allowed_channel(self._conf, interaction.channel_id):
            await interaction.response.send_message(
                "Club Poker can only be played in the designated casino channel(s).",
                ephemeral=True,
            )
            return False
        if not self._conf.games_enabled.get("clubpoker", True):
            await interaction.response.send_message(
                "Club Poker is currently disabled on this server.",
                ephemeral=True,
            )
            return False
        return True

    async def _on_challenge(self, interaction: discord.Interaction) -> None:
        if not await self._check_access(interaction):
            return
        await interaction.response.send_modal(ClubPokerChallengeModal(self))

    async def _show_info(self, interaction: discord.Interaction) -> None:
        e = discord.Embed(title="🃏 How to Play: Club Poker", color=PALETTE_GOLD)
        e.description = (
            "**Heads-up private 5-card draw with one betting round.**\n\n"
            "1. Challenge one player for an ante amount.\n"
            "2. On accept, both antes are locked in.\n"
            "3. Both players privately choose which cards to hold.\n"
            "4. After both lock in, replacement cards are drawn from the same deck.\n"
            "5. One betting round follows: Stay or Bet, then Call or Fold. No raises.\n"
            "6. If neither player folds, the best 5-card hand wins.\n\n"
            "The winning hand is always shown publicly. The losing player gets 15 seconds to show or muck their hand."
        )
        await interaction.response.send_message(embed=e, ephemeral=True)

    async def _back_to_floor(self, interaction: discord.Interaction) -> None:
        from ..commands.user_commands import GameRoomView  # noqa: PLC0415

        await safe_defer(interaction)
        balance = await get_balance(self._member, self._conf, self._user)
        if self._conf.payment_mode == "chips":
            currency_name = "chips"
        else:
            currency_name = await bank.get_currency_name(self._member.guild)
        view = GameRoomView(self._member, self._cog, balance, currency_name)
        await safe_edit_original_response(interaction, embed=view._build_embed(), view=view)

    async def _process_challenge(self, interaction: discord.Interaction, bet_raw: str, opponent_raw: str) -> None:
        raw = bet_raw.strip().replace(",", "")
        if not raw.isdigit() or int(raw) <= 0:
            await interaction.followup.send("Please enter a valid positive whole number for the ante.", ephemeral=True)
            return
        bet = int(raw)

        guild = interaction.guild
        opponent_str = opponent_raw.strip()
        challenged_member: discord.Member | None = None
        if opponent_str.startswith("<@") and opponent_str.endswith(">"):
            id_str = opponent_str.lstrip("<@!").rstrip(">")
        else:
            id_str = opponent_str.lstrip("@")

        if id_str.isdigit():
            challenged_member = guild.get_member(int(id_str))
            if challenged_member is None:
                try:
                    challenged_member = await guild.fetch_member(int(id_str))
                except Exception:
                    challenged_member = None
        else:
            needle = opponent_str.lstrip("@").casefold()
            matches: list[discord.Member] = []
            for member in guild.members:
                candidates = {member.display_name.casefold(), member.name.casefold()}
                if member.global_name:
                    candidates.add(member.global_name.casefold())
                if needle in candidates:
                    matches.append(member)
            if len(matches) == 1:
                challenged_member = matches[0]
            elif len(matches) > 1:
                await interaction.followup.send(
                    "Multiple members match that name. Use an @mention or paste their user ID instead.",
                    ephemeral=True,
                )
                return

        if challenged_member is None:
            await interaction.followup.send(
                "That user couldn't be found in this server. Use an @mention, exact name, or user ID.",
                ephemeral=True,
            )
            return
        if challenged_member.id == self._member.id:
            await interaction.followup.send("You can't challenge yourself.", ephemeral=True)
            return
        if challenged_member.bot:
            await interaction.followup.send("You can't challenge a bot.", ephemeral=True)
            return

        challenger_balance = await get_balance(self._member, self._conf, self._user)
        error = validate_bet(self._conf, self._user, "clubpoker", bet, challenger_balance)
        if error:
            await interaction.followup.send(error, ephemeral=True)
            return

        challenged_user = self._conf.get_user(challenged_member.id)
        challenged_balance = await get_balance(challenged_member, self._conf, challenged_user)
        if challenged_balance < bet:
            await interaction.followup.send(
                f"{challenged_member.display_name} doesn't have enough {self._cached_currency or 'chips'} to cover a **{bet:,}** ante.",
                ephemeral=True,
            )
            return

        challenge_embed = discord.Embed(
            title="🃏 Club Poker Challenge",
            color=PALETTE_GOLD,
            description=(
                f"{self._member.mention} challenges {challenged_member.mention} to **Club Poker**!\n\n"
                f"**Ante:** {bet:,} {self._cached_currency or 'chips'} each\n"
                "Private 5-card draw, then one betting round.\n\n"
                f"{challenged_member.mention} -- accept or decline below.\n"
                "*This challenge expires in 5 minutes.*"
            ),
        )
        if url := embed_image("clubpoker"):
            challenge_embed.set_thumbnail(url=url)

        challenge_view = ClubPokerChallengeView(
            challenger=self._member,
            challenger_user=self._user,
            challenged=challenged_member,
            challenged_user=challenged_user,
            conf=self._conf,
            cog=self._cog,
            ante=bet,
            currency=self._cached_currency or "chips",
        )
        challenge_message = await interaction.followup.send(embed=challenge_embed, view=challenge_view, wait=True)
        challenge_view._message = challenge_message

        waiting_embed = discord.Embed(
            title="🃏 High Roller: Club Poker",
            color=PALETTE_GOLD,
            description=f"⏳ Challenge sent to {challenged_member.mention}! Waiting for their response...",
        )
        if url := embed_image("clubpoker"):
            waiting_embed.set_thumbnail(url=url)
        self.clear_items()
        await safe_edit_original_response(interaction, embed=waiting_embed, view=self)

    def _build_idle_embed(self) -> discord.Embed:
        e = discord.Embed(title="🃏 High Roller: Club Poker", color=PALETTE_GOLD)
        desc = (
            "**Heads-up private 5-card draw poker.**\n\n"
            "Challenge one other player. Both players ante the same amount, privately choose holds, draw replacements, then play one fixed betting round with **Stay**, **Bet**, **Call**, or **Fold**.\n\n"
            "The winning hand is always shown. The losing hand may be shown or mucked."
        )
        if mul := get_pending_multiplier(self._user):
            desc += f"\n\n⚡ Bonus snapshot: **{mul}x** multiplier is stored on your account, but Club Poker does not use it."
        if has_bonus_bet_token(self._user):
            desc += "\n🎫 Bonus snapshot: Bonus Bet Token is stored on your account, but Club Poker does not use it."
        if has_lucky_streak(self._user):
            desc += "\n🔥 Bonus snapshot: Lucky Streak adds +25% if it is still active when you win."
        e.description = desc
        if url := embed_image("clubpoker"):
            e.set_thumbnail(url=url)
        if self._cached_balance is not None:
            e.set_footer(text=f"Balance: {self._cached_balance:,} {self._cached_currency}")
        return e

    def _build_embed(self) -> discord.Embed:
        return self._build_idle_embed()


class ClubPokerChallengeView(discord.ui.View):
    def __init__(
        self,
        challenger: discord.Member,
        challenger_user: User,
        challenged: discord.Member,
        challenged_user: User,
        conf: GuildSettings,
        cog: MixinMeta,
        ante: int,
        currency: str,
    ) -> None:
        super().__init__(timeout=300)
        self._challenger = challenger
        self._challenger_user = challenger_user
        self._challenged = challenged
        self._challenged_user = challenged_user
        self._conf = conf
        self._cog = cog
        self._ante = ante
        self._currency = currency
        self._resolved = False
        self._message: discord.Message | None = None

        accept_btn = discord.ui.Button(label="✅ Accept", style=discord.ButtonStyle.green, row=0)
        accept_btn.callback = self._on_accept
        self.add_item(accept_btn)
        decline_btn = discord.ui.Button(label="❌ Decline", style=discord.ButtonStyle.red, row=0)
        decline_btn.callback = self._on_decline
        self.add_item(decline_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._challenged.id:
            await interaction.response.send_message(
                f"Only {self._challenged.display_name} can respond to this challenge.",
                ephemeral=True,
            )
            return False
        return True

    async def on_timeout(self) -> None:
        self._resolved = True
        self.clear_items()
        if self._message is not None:
            expired = discord.Embed(
                title="🃏 Club Poker Challenge -- Expired",
                color=discord.Color.dark_grey(),
                description="The challenge expired before it was accepted. No money changed hands.",
            )
            if url := embed_image("clubpoker"):
                expired.set_thumbnail(url=url)
            await self._message.edit(embed=expired, view=self)

    async def _on_accept(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message("This challenge has already been resolved.", ephemeral=True)
            return
        self._resolved = True
        await safe_defer(interaction)

        challenger_balance = await get_balance(self._challenger, self._conf, self._challenger_user)
        challenged_balance = await get_balance(self._challenged, self._conf, self._challenged_user)
        if challenger_balance < self._ante or challenged_balance < self._ante:
            self.clear_items()
            cancelled = discord.Embed(
                title="🃏 Club Poker -- Cancelled",
                color=discord.Color.red(),
                description="One of the players no longer has enough balance to cover the ante.",
            )
            if url := embed_image("clubpoker"):
                cancelled.set_thumbnail(url=url)
            await safe_edit_original_response(interaction, embed=cancelled, view=self)
            return

        await deduct_balance(self._challenger, self._conf, self._challenger_user, self._ante)
        await deduct_balance(self._challenged, self._conf, self._challenged_user, self._ante)

        session = _ClubPokerSession(
            challenger=self._challenger,
            challenger_user=self._challenger_user,
            challenged=self._challenged,
            challenged_user=self._challenged_user,
            conf=self._conf,
            cog=self._cog,
            ante=self._ante,
            currency=self._currency,
        )
        session.public_message = interaction.message
        session_view = ClubPokerSessionView(session)
        session.public_view = session_view
        await safe_edit_original_response(interaction, embed=session.build_public_embed(), view=session_view)

    async def _on_decline(self, interaction: discord.Interaction) -> None:
        if self._resolved:
            await interaction.response.send_message("This challenge has already been resolved.", ephemeral=True)
            return
        self._resolved = True
        self.clear_items()
        declined_embed = discord.Embed(
            title="🃏 Club Poker Challenge -- Declined",
            color=discord.Color.dark_grey(),
            description=(
                f"{self._challenged.mention} declined the challenge from {self._challenger.mention}.\n"
                "No money changed hands."
            ),
        )
        if url := embed_image("clubpoker"):
            declined_embed.set_thumbnail(url=url)
        await safe_response_edit_message(interaction, embed=declined_embed, view=self)


class ClubPokerSessionView(discord.ui.View):
    def __init__(self, session: _ClubPokerSession) -> None:
        super().__init__(timeout=600)
        self._session = session
        self.sync_items()

    def sync_items(self) -> None:
        self.clear_items()
        if self._session.phase in {"draw", "betting", "muck_choice"}:
            if self._session.phase == "draw":
                label = "🂠 Draw Private Hand"
            elif self._session.phase == "betting":
                label = "➡️ Move to Next Round"
            else:
                label = "🂠 Review Private Hand"
            open_btn = discord.ui.Button(label=label, style=discord.ButtonStyle.blurple, row=0)
            open_btn.callback = self._open_private
            self.add_item(open_btn)

    async def _open_private(self, interaction: discord.Interaction) -> None:
        if not self._session.is_participant(interaction.user.id):
            await interaction.response.send_message("Only the two players in this hand can open private controls.", ephemeral=True)
            return
        view = ClubPokerPrivateView(self._session, interaction.user.id)
        await interaction.response.send_message(embed=view.build_embed(), view=view, ephemeral=True)

    async def on_timeout(self) -> None:
        async with self._session.lock:
            if self._session.phase == "muck_choice" and self._session.loser_visibility is None:
                self._session.loser_visibility = "muck"
                self._session.phase = "resolved"
                self.sync_items()
                if self._session.public_message is not None:
                    await self._session.public_message.edit(embed=self._session.build_public_embed(), view=self)
                return
            if self._session.phase in {"draw", "betting"}:
                await self._session.cancel_and_refund("timed out")
                self.sync_items()


class ClubPokerPrivateView(discord.ui.View):
    def __init__(self, session: _ClubPokerSession, user_id: int) -> None:
        super().__init__(timeout=180)
        self._session = session
        self._user_id = user_id
        self.sync_items()

    def _player(self) -> _ClubPokerPlayerState:
        return self._session.player_for(self._user_id)

    def sync_items(self) -> None:
        self.clear_items()
        player = self._player()

        if self._session.phase == "draw" and not player.draw_locked:
            for idx, card in enumerate(player.hand):
                held = player.held[idx]
                label = f"[HOLD] {card.label}" if held else card.label
                button = discord.ui.Button(
                    label=label,
                    style=discord.ButtonStyle.green if held else discord.ButtonStyle.grey,
                    row=0,
                )
                button.callback = self._make_hold_callback(idx)
                self.add_item(button)

            lock_btn = discord.ui.Button(label="🔒 Lock Draw", style=discord.ButtonStyle.blurple, row=1)
            lock_btn.callback = self._lock_draw
            self.add_item(lock_btn)

        elif self._session.phase == "betting" and self._session.turn_user_id == self._user_id:
            if self._session.bet_open:
                call_btn = discord.ui.Button(label=f"📞 Call ({self._session.ante:,})", style=discord.ButtonStyle.green, row=0)
                call_btn.callback = self._call_bet
                self.add_item(call_btn)
                fold_btn = discord.ui.Button(label="🚪 Fold", style=discord.ButtonStyle.red, row=0)
                fold_btn.callback = self._fold_hand
                self.add_item(fold_btn)
            else:
                stay_btn = discord.ui.Button(label="✋ Stay", style=discord.ButtonStyle.grey, row=0)
                stay_btn.callback = self._take_check
                self.add_item(stay_btn)
                bet_btn = discord.ui.Button(label=f"💰 Bet ({self._session.ante:,})", style=discord.ButtonStyle.green, row=0)
                bet_btn.callback = self._open_bet
                self.add_item(bet_btn)

        elif (
            self._session.phase == "muck_choice"
            and self._user_id == self._session.loser_user_id
            and self._session.loser_visibility is None
        ):
            show_btn = discord.ui.Button(label="🪞 Show Hand", style=discord.ButtonStyle.green, row=0)
            show_btn.callback = self._show_hand
            self.add_item(show_btn)
            muck_btn = discord.ui.Button(label="🂠 Muck Hand", style=discord.ButtonStyle.grey, row=0)
            muck_btn.callback = self._muck_hand
            self.add_item(muck_btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self._user_id:
            await interaction.response.send_message("These private controls aren't for you.", ephemeral=True)
            return False
        return True

    async def on_timeout(self) -> None:
        self.clear_items()

    def build_embed(self) -> discord.Embed:
        player = self._player()
        embed = discord.Embed(title="🃏 Club Poker -- Private Hand", color=PALETTE_GOLD)
        hand_text = "  ".join(
            f"**[{card.label}]**" if player.held[idx] else card.label
            for idx, card in enumerate(player.hand)
        )
        embed.description = f"**Your hand:**\n{hand_text}\n\n"

        if self._session.phase == "draw":
            if player.draw_locked:
                embed.description += "🔒 Your draw is locked in. Waiting for the other player."
            else:
                held_count = sum(player.held)
                embed.description += (
                    f"Select which cards to **hold**. Currently holding **{held_count}/5** card(s).\n"
                    "When ready, click **Lock Draw**."
                )
        elif self._session.phase == "betting":
            replaced = self._session.replacement_count_for(self._user_id)
            draw_text = f"You drew **{replaced}** new card(s) from the cards you did not keep.\n\n"
            embed.description += draw_text
            if self._session.turn_user_id == self._user_id:
                if self._session.bet_open:
                    bettor = self._session.player_for(self._session.bettor_id).member.mention
                    embed.description += f"{bettor} opened betting for **{self._session.ante:,} {self._session.currency}**. Choose **Call** or **Fold**."
                else:
                    embed.description += f"It's your turn. Choose **Stay** or open betting for **{self._session.ante:,} {self._session.currency}**."
            else:
                actor = self._session.player_for(self._session.turn_user_id).member.mention
                embed.description += f"Waiting on {actor} to act."
        elif self._session.phase == "muck_choice":
            if self._user_id == self._session.loser_user_id and self._session.loser_visibility is None:
                embed.description += "You may **Show Hand** or **Muck Hand**. If you do nothing for 15 seconds, your hand is mucked."
            else:
                embed.description += "The hand has been resolved."
        else:
            embed.description += "The hand has been resolved."

        return embed

    def _make_hold_callback(self, idx: int):
        async def callback(interaction: discord.Interaction) -> None:
            async with self._session.lock:
                if self._session.phase != "draw" or self._player().draw_locked:
                    view = ClubPokerPrivateView(self._session, self._user_id)
                    await interaction.response.edit_message(embed=view.build_embed(), view=view)
                    return
                self._player().held[idx] = not self._player().held[idx]
                view = ClubPokerPrivateView(self._session, self._user_id)
                await interaction.response.edit_message(embed=view.build_embed(), view=view)

        return callback

    async def _lock_draw(self, interaction: discord.Interaction) -> None:
        async with self._session.lock:
            await self._session.lock_draw(self._user_id)
            view = ClubPokerPrivateView(self._session, self._user_id)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def _take_check(self, interaction: discord.Interaction) -> None:
        async with self._session.lock:
            await self._session.take_check(self._user_id)
            view = ClubPokerPrivateView(self._session, self._user_id)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def _open_bet(self, interaction: discord.Interaction) -> None:
        async with self._session.lock:
            error = await self._session.open_bet(self._user_id)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            view = ClubPokerPrivateView(self._session, self._user_id)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def _call_bet(self, interaction: discord.Interaction) -> None:
        async with self._session.lock:
            error = await self._session.call_bet(self._user_id)
            if error:
                await interaction.response.send_message(error, ephemeral=True)
                return
            view = ClubPokerPrivateView(self._session, self._user_id)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def _fold_hand(self, interaction: discord.Interaction) -> None:
        async with self._session.lock:
            await self._session.fold_hand(self._user_id)
            view = ClubPokerPrivateView(self._session, self._user_id)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def _show_hand(self, interaction: discord.Interaction) -> None:
        async with self._session.lock:
            await self._session.set_loser_visibility("show")
            view = ClubPokerPrivateView(self._session, self._user_id)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)

    async def _muck_hand(self, interaction: discord.Interaction) -> None:
        async with self._session.lock:
            await self._session.set_loser_visibility("muck")
            view = ClubPokerPrivateView(self._session, self._user_id)
            await interaction.response.edit_message(embed=view.build_embed(), view=view)