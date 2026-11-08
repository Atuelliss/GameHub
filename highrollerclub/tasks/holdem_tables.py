"""Texas Hold'em: money safety for table stacks.

Players' table stacks are chips the cog is holding for them outside their
balance. GuildSettings.holdem_escrow records, per player, how much is held and
in which payment mode it was taken. Rules:

- The table layer (views/holdem_view.py) writes a player's entry when they sit,
  top up or leave, and at the end of every hand (their settled stack). It never
  writes mid-hand, so the record is always "stack at the start of this hand".
- On unload, every entry is refunded (open tables close).
- On load, any entry still there means a table was open when the bot stopped:
  it is refunded and cleared. A hand in progress is effectively voided.
- A refund that fails with a retryable error (a bank error) stays in escrow and
  is retried on the next load. A player who has left the server can't be paid
  in bank mode; that entry is dropped and logged, as Horse Racing does.

Pure game logic is in games/holdem.py.
"""

from __future__ import annotations

import asyncio
import logging

import discord

from ..abc import CompositeMetaClass
from ..commands.helper_functions import deduct_balance
from ..common.models import GuildSettings, HoldemEscrow, User

log = logging.getLogger("red.highrollerclub.holdem")

_RESTART_NOTICE = (
    "♣️ **Texas Hold'em table closed.** The casino restarted, so every seated player "
    "got back their stack from the start of the last hand."
)


class HoldemTableKeeper(metaclass=CompositeMetaClass):
    """Cog mixin: escrow bookkeeping and refunds for Texas Hold'em tables."""

    # ------------------------------------------------------------------
    # Live tables (in memory only; their chips are in escrow)
    # ------------------------------------------------------------------

    def _hd_runtime(self) -> dict:
        state = getattr(self, "_hd_state", None)
        if state is None:
            state = self._hd_state = {"tables": {}, "locks": {}}
        return state

    def hd_lock(self, guild_id: int) -> asyncio.Lock:
        """Per-server lock for opening tables and taking seats (one seat per player, one table per channel)."""
        return self._hd_runtime()["locks"].setdefault(guild_id, asyncio.Lock())

    def hd_tables(self) -> dict:
        """(guild id, channel id) -> live table object (views/holdem_view.py HoldemTable)."""
        return self._hd_runtime()["tables"]

    def hd_table_in(self, guild_id: int, channel_id: int):
        return self.hd_tables().get((guild_id, channel_id))

    def hd_is_seated(self, conf: GuildSettings, guild_id: int, user_id: int) -> bool:
        """True if the player has chips at a table (or a refund waiting) in this server."""
        if user_id in conf.holdem_escrow:
            return True
        return any(
            key[0] == guild_id and table.seat_of(user_id) is not None
            for key, table in self.hd_tables().items()
        )

    # ------------------------------------------------------------------
    # Money in and out of a table. Every chip goes through these two.
    # ------------------------------------------------------------------

    async def hd_buy_in(
        self, member: discord.Member, conf: GuildSettings, user: User, amount: int, channel_id: int | None
    ) -> bool:
        """Take `amount` from the player's balance into their table stack. False takes nothing."""
        entry = conf.holdem_escrow.get(member.id)
        if entry is not None and entry.payment_mode != conf.payment_mode:
            return False  # payment mode changed since they sat down: don't mix currencies
        if not await deduct_balance(member, conf, user, amount):
            return False
        held = entry.amount if entry is not None else 0
        self.hd_escrow_set(conf, member.id, held + int(amount), conf.payment_mode, channel_id)
        return True

    async def hd_cash_out(self, guild: discord.Guild | None, conf: GuildSettings, user_id: int) -> tuple[int, bool]:
        """Pay a player everything held for them, in the mode it was taken in.

        Returns (amount, paid). When paid is False the entry stays in escrow and is
        retried on the next load.
        """
        entry = conf.holdem_escrow.pop(user_id, None)
        if entry is None:
            return 0, True
        ok = await self._hr_credit(guild, conf, entry.payment_mode, user_id, entry.amount, label="Texas Hold'em")
        if not ok:
            conf.holdem_escrow[user_id] = entry
        self.save()
        return entry.amount, ok

    # ------------------------------------------------------------------
    # Escrow bookkeeping (called by the table layer)
    # ------------------------------------------------------------------

    def hd_escrow_set(
        self, conf: GuildSettings, user_id: int, amount: int, payment_mode: str, channel_id: int | None
    ) -> None:
        """Record what the cog holds for a player. 0 or less removes the entry. Saves."""
        if amount > 0:
            conf.holdem_escrow[user_id] = HoldemEscrow(
                amount=int(amount), payment_mode=payment_mode, channel_id=channel_id
            )
        else:
            conf.holdem_escrow.pop(user_id, None)
        self.save()

    def hd_escrow_amount(self, conf: GuildSettings, user_id: int) -> int:
        entry = conf.holdem_escrow.get(user_id)
        return entry.amount if entry else 0

    # ------------------------------------------------------------------
    # Refunds
    # ------------------------------------------------------------------

    async def _hd_refund_escrow(self, guild: discord.Guild | None, conf: GuildSettings) -> set[int]:
        """Refund every escrow entry of one server. Returns the table channel ids refunded.

        Each entry is removed before its credit and put back if the credit fails, so a
        crash can't pay the same entry twice from memory.
        """
        channels: set[int] = set()
        for user_id in list(conf.holdem_escrow):
            entry = conf.holdem_escrow.pop(user_id)
            ok = await self._hr_credit(guild, conf, entry.payment_mode, user_id, entry.amount, label="Texas Hold'em")
            if ok:
                if entry.channel_id:
                    channels.add(entry.channel_id)
                log.info("Texas Hold'em: refunded %s to %s in guild %s", entry.amount, user_id, getattr(guild, "id", "?"))
            else:
                conf.holdem_escrow[user_id] = entry  # retried on the next load
            self.save()
        return channels

    async def _hd_announce(self, guild: discord.Guild | None, channel_ids: set[int]) -> None:
        if guild is None:
            return
        for channel_id in channel_ids:
            channel = guild.get_channel(channel_id)
            if not isinstance(channel, discord.abc.Messageable):
                continue
            try:
                await asyncio.wait_for(channel.send(_RESTART_NOTICE), timeout=5)
            except Exception:
                pass

    async def hd_recover(self) -> None:
        """On load: refund every stack left in escrow by a restart."""
        for guild_id, conf in self.db.configs.items():
            if not conf.holdem_escrow:
                continue
            guild = self.bot.get_guild(guild_id)
            channels = await self._hd_refund_escrow(guild, conf)
            await self._hd_announce(guild, channels)

    async def hd_shutdown(self) -> None:
        """On unload: close every live table (cashing everyone out), then refund any escrow left."""
        for table in list(self.hd_tables().values()):
            # No timeout here: cutting a cash-out off between taking the escrow entry
            # and crediting it would lose the chips. close() times out only its message edit.
            try:
                await table.close("The casino is restarting.")
            except Exception:
                log.exception("Texas Hold'em: closing a table on unload failed; its escrow is refunded below")
        self.hd_tables().clear()
        for guild_id, conf in self.db.configs.items():
            if not conf.holdem_escrow:
                continue
            guild = self.bot.get_guild(guild_id)
            try:
                channels = await self._hd_refund_escrow(guild, conf)
            except Exception:
                log.exception("Texas Hold'em: refund on unload failed in guild %s; it will be retried on load", guild_id)
                continue
            await self._hd_announce(guild, channels)
