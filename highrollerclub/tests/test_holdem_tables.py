"""Texas Hold'em tables (Stage 3), driven without Discord: seating and buy-ins, one seat per player, full tables,
top-ups, leaving and host hand-over, closing, the idle close, and that escrow always equals the chips at the table.

The table code runs against a stand-in cog that uses the real escrow functions from tasks/holdem_tables.py.

Run from the workspace root:  .venv/Scripts/python.exe -m pytest highrollerclub/tests -q
"""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from highrollerclub.common.models import DB
from highrollerclub.tasks.holdem_tables import HoldemTableKeeper
from highrollerclub.views.holdem_view import HoldemTable

GUILD = SimpleNamespace(id=1)


class FakeCog:
    """Just enough cog for HoldemTable: the real Hold'em money functions, chips mode, no Discord."""

    _hd_runtime = HoldemTableKeeper._hd_runtime
    hd_lock = HoldemTableKeeper.hd_lock
    hd_tables = HoldemTableKeeper.hd_tables
    hd_table_in = HoldemTableKeeper.hd_table_in
    hd_is_seated = HoldemTableKeeper.hd_is_seated
    hd_buy_in = HoldemTableKeeper.hd_buy_in
    hd_cash_out = HoldemTableKeeper.hd_cash_out
    hd_escrow_set = HoldemTableKeeper.hd_escrow_set

    def __init__(self):
        self.db = DB()
        self.fail_pay: set[int] = set()

    def save(self):
        pass

    async def _hr_credit(self, guild, conf, mode, user_id, amount, label="Horse Racing"):
        if user_id in self.fail_pay:
            return False
        conf.get_user(user_id).chip_balance += amount
        return True


def member(uid):
    return SimpleNamespace(id=uid, mention=f"<@{uid}>", display_name=f"P{uid}")


def setup(balances, channel_id=10, blinds=(100, 200), seats=6):
    cog = FakeCog()
    conf = cog.db.get_conf(GUILD)
    for uid, chips in balances.items():
        conf.get_user(uid).chip_balance = chips
    table = HoldemTable(cog, GUILD, SimpleNamespace(id=channel_id), member(1), blinds[0], blinds[1], seats, "chips")
    cog.hd_tables()[table.key] = table
    return cog, conf, table


def run(coro):
    return asyncio.run(coro)


def escrow_matches(conf, table):
    return {uid: e.amount for uid, e in conf.holdem_escrow.items()} == {s.member.id: s.stack for s in table.seats}


def test_sit_takes_the_buy_in_into_escrow():
    cog, conf, table = setup({1: 50_000, 2: 50_000})
    assert run(table.sit(member(1), 4000)) is None
    assert run(table.sit(member(2), 20_000)) is None
    assert conf.get_user(1).chip_balance == 46_000 and conf.get_user(2).chip_balance == 30_000
    assert escrow_matches(conf, table)
    assert conf.holdem_escrow[1].payment_mode == "chips" and conf.holdem_escrow[1].channel_id == 10


def test_buy_in_limits_and_balance():
    cog, conf, table = setup({1: 50_000, 2: 3000})
    assert "4,000–20,000" in run(table.sit(member(1), 3999))
    assert "4,000–20,000" in run(table.sit(member(1), 20_001))
    assert "enough" in run(table.sit(member(2), 4000))
    assert conf.get_user(2).chip_balance == 3000 and not conf.holdem_escrow


def test_one_seat_per_player_per_server():
    cog, conf, table = setup({1: 50_000})
    run(table.sit(member(1), 4000))
    assert "already at this table" in run(table.sit(member(1), 4000))
    other = HoldemTable(cog, GUILD, SimpleNamespace(id=11), member(1), 100, 200, 6, "chips")
    cog.hd_tables()[other.key] = other
    assert "another Hold'em table" in run(other.sit(member(1), 4000))
    assert conf.get_user(1).chip_balance == 46_000


def test_table_fills_up():
    cog, conf, table = setup({i: 10_000 for i in range(1, 5)}, seats=3)
    for uid in (1, 2, 3):
        assert run(table.sit(member(uid), 4000)) is None
    assert "full" in run(table.sit(member(4), 4000))


def test_blacklisted_player_cant_sit():
    cog, conf, table = setup({1: 10_000})
    conf.blacklisted_users.append(1)
    assert "can't play" in run(table.sit(member(1), 4000))


def test_top_up_up_to_the_table_maximum():
    cog, conf, table = setup({1: 50_000})
    run(table.sit(member(1), 15_000))
    assert "up to **5,000**" in run(table.top_up(member(1), 6000))
    assert run(table.top_up(member(1), 5000)) is None
    assert table.seat_of(1).stack == 20_000 and conf.get_user(1).chip_balance == 30_000
    assert "maximum" in run(table.top_up(member(1), 1))
    assert escrow_matches(conf, table)


def test_top_up_blocked_after_payment_mode_switch():
    cog, conf, table = setup({1: 50_000})
    run(table.sit(member(1), 4000))
    conf.holdem_escrow[1] = conf.holdem_escrow[1].model_copy(update={"payment_mode": "bank"})
    assert "payment mode" in run(table.top_up(member(1), 1000))
    assert conf.get_user(1).chip_balance == 46_000


def test_leave_cashes_out_and_passes_the_host():
    cog, conf, table = setup({1: 10_000, 2: 10_000})
    run(table.sit(member(1), 4000))
    run(table.sit(member(2), 5000))
    assert run(table.leave(1)) == (4000, True)
    assert conf.get_user(1).chip_balance == 10_000
    assert table.host_id == 2 and table.seat_of(1) is None
    assert escrow_matches(conf, table)
    assert run(table.leave(1)) is None


def test_failed_cash_out_stays_in_escrow():
    cog, conf, table = setup({1: 10_000})
    run(table.sit(member(1), 4000))
    cog.fail_pay.add(1)
    assert run(table.leave(1)) == (4000, False)
    assert conf.holdem_escrow[1].amount == 4000        # retried on the next load
    assert cog.hd_is_seated(conf, GUILD.id, 1)        # so they can't sit again before it's paid


def test_close_returns_every_stack_and_unregisters():
    cog, conf, table = setup({1: 10_000, 2: 10_000, 3: 10_000})
    for uid in (1, 2, 3):
        run(table.sit(member(uid), 4000 + uid))
    run(table.close("Closed by the host."))
    assert table.phase == "closed" and not table.seats and not conf.holdem_escrow
    assert [conf.get_user(uid).chip_balance for uid in (1, 2, 3)] == [10_000] * 3
    assert sorted(table.cash_outs) == [(1, 4001, True), (2, 4002, True), (3, 4003, True)]
    assert cog.hd_table_in(GUILD.id, 10) is None
    run(table.close("again"))                          # closing twice pays nothing more
    assert conf.get_user(1).chip_balance == 10_000
    assert "closed" in run(table.sit(member(1), 4000))


def test_idle_table_closes_itself():
    cog, conf, table = setup({1: 10_000})
    run(table.sit(member(1), 4000))
    table.last_hand_at = datetime.now(timezone.utc) - timedelta(minutes=11)
    run(table._idle_watch())
    assert table.phase == "closed" and conf.get_user(1).chip_balance == 10_000
    assert "No hand was dealt" in table.close_reason


def test_table_embeds_build():
    cog, conf, table = setup({1: 10_000, 2: 10_000})
    run(table.sit(member(1), 4000))
    run(table.sit(member(2), 4000))
    open_embed = table.build_embed()
    assert "100 / 200" in open_embed.title and "**Seats:** 2/6" in open_embed.description
    run(table.close("Closed by the host."))
    assert "Stacks returned" in table.build_embed().description
