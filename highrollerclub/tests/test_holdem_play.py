"""Texas Hold'em hand play at a table (Stage 4), driven without Discord: dealing, the button moving, stacks and
escrow after each hand, stats with the 3-player prestige rule, title counters, show/muck, timeouts and sitting
out, leaving or joining mid-hand, closing mid-hand, busting, Table Captain, and the private controls.

Run from the workspace root:  .venv/Scripts/python.exe -m pytest highrollerclub/tests -q
"""

import asyncio

import pytest

from types import SimpleNamespace

import highrollerclub.games.holdem as holdem_logic
from highrollerclub.tests.test_holdem import stacked
from highrollerclub.tests.test_holdem_tables import GUILD, FakeCog, member
from highrollerclub.views.holdem_view import HoldemPrivateView, HoldemTable


def make_table(stacks, seats=6):
    """A table with players 1..n seated (player 1 hosts), each with 100,000 chips before buying in."""
    cog = FakeCog()
    conf = cog.db.get_conf(GUILD)
    table = HoldemTable(cog, GUILD, SimpleNamespace(id=10), member(1), 100, 200, seats, "chips")
    cog.hd_tables()[table.key] = table
    for uid, stack in enumerate(stacks, start=1):
        conf.get_user(uid).chip_balance = 100_000
    return cog, conf, table


async def seat_all(table, stacks):
    for uid, stack in enumerate(stacks, start=1):
        assert await table.sit(member(uid), stack) is None


def total_money(conf, ids):
    return sum(conf.get_user(u).chip_balance for u in ids) + sum(e.amount for e in conf.holdem_escrow.values())


def escrow_matches(conf, table):
    return {u: e.amount for u, e in conf.holdem_escrow.items()} == {s.member.id: s.stack for s in table.seats}


@pytest.fixture
def deck(monkeypatch):
    """deck(holes, board) makes the next deal use those cards (holes listed by seat, button = first player dealt)."""
    def use(holes, board, button=0):
        monkeypatch.setattr(holdem_logic, "Deck", lambda: stacked(holes, board, button))
    return use


def test_heads_up_fold_moves_chips_but_not_prestige():
    async def go():
        cog, conf, table = make_table([4000, 4000])
        await seat_all(table, [4000, 4000])
        for uid in (1, 2):
            conf.get_user(uid).prestige_points = 10.0
        assert await table.deal(1) is None
        assert table.phase == "hand" and table.hand.to_act_id == 1     # button posts SB, acts first heads-up
        assert await table.act(2, "call") == "It isn't your turn."
        assert await table.act(1, "fold") is None
        assert table.phase == "waiting"
        assert [s.stack for s in table.seats] == [3900, 4100]
        assert escrow_matches(conf, table)
        assert conf.get_user(1).game_loss_counts["holdem"] == 1 and conf.get_user(2).game_win_counts["holdem"] == 1
        assert conf.get_user(1).prestige_points == 10.0 and conf.get_user(2).prestige_points == 10.0
        assert conf.get_user(2).holdem_fold_wins == 0                    # heads-up: no title progress
        assert total_money(conf, (1, 2)) == 200_000
    asyncio.run(go())


def test_three_handed_showdown_counts_and_show_muck(deck):
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        deck(["As Ad", "Ks Kd", "2c 7h"], "Ac 9s 4d 3h Jc")
        for uid in (1, 2, 3):
            conf.get_user(uid).prestige_points = 10.0
        assert await table.deal(1) is None
        assert table.hand.to_act_id == 1
        await table.act(1, "call"); await table.act(2, "call"); await table.act(3, "check")
        for _ in range(3):                                   # check it down: SB, BB, button
            await table.act(2, "check"); await table.act(3, "check"); await table.act(1, "check")
        assert table.phase == "showdown"
        assert [s.stack for s in table.seats] == [5400, 4800, 4800]
        assert escrow_matches(conf, table)
        assert conf.get_user(1).prestige_points == 10.0 + conf.prestige_win_points
        assert conf.get_user(2).prestige_points == 10.0 - conf.prestige_loss_points
        assert all(conf.get_user(u).holdem_hands_dealt == 1 for u in (1, 2, 3))
        assert table.reveal == {2: "pending", 3: "pending"}
        assert "deciding" in table.build_embed().description
        assert await table.choose_reveal(2, "show") is None
        assert await table.choose_reveal(2, "muck") is not None          # already chosen
        assert await table.choose_reveal(3, "muck") is None
        assert table.phase == "waiting"
        text = table.build_embed().description
        assert "mucked" in text and "Kings" not in text                  # names come from CP_HAND_NAMES
        assert total_money(conf, (1, 2, 3)) == 300_000
    asyncio.run(go())


def test_button_moves_each_hand():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        buttons = []
        for _ in range(4):
            await table.deal(1)
            buttons.append(table.button_pos)
            while table.phase == "hand":
                await table.act(table.hand.to_act_id, "fold")
            table.phase = "waiting" if table.phase == "showdown" else table.phase
        assert buttons == [0, 1, 2, 0]
    asyncio.run(go())


def test_all_in_run_out_is_face_up_and_counts_titles(deck):
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        deck(["Ks Kd", "As Ad", "2c 3d"], "2h 7h 9s 4d Kc")             # river king: comeback for player 1
        await table.deal(1)
        await table.act(1, "allin"); await table.act(2, "allin"); await table.act(3, "fold")
        assert table.phase == "waiting"                                    # run-out: no show/muck window
        assert conf.get_user(1).holdem_river_comebacks == 1
        assert conf.get_user(1).holdem_allin_wins == 1
        assert conf.get_user(1).holdem_best_pot_bb == 51                   # 5,000 + 5,000 + the folded 200 big blind
        assert table.seat_of(2) is None                                    # busted, left the table
        assert any("out of chips" in note for note in table.notes)
        assert 2 not in conf.holdem_escrow and conf.get_user(2).chip_balance == 95_000
    asyncio.run(go())


def test_leaving_mid_hand_folds_then_cashes_out_after():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        await table.deal(1)
        await table.act(1, "call")
        outcome, _ = await table.request_leave(3)                          # big blind leaves out of turn
        assert outcome == "after_hand" and table.seat_of(3) is not None
        assert table.hand.to_act_id == 2
        await table.act(2, "fold")
        assert table.phase == "waiting" and table.seat_of(3) is None
        assert conf.get_user(3).chip_balance == 95_000 + 4800             # lost the big blind, cashed out the rest
        assert escrow_matches(conf, table)
        assert total_money(conf, (1, 2, 3)) == 300_000
    asyncio.run(go())


def test_leaving_keeps_the_acting_players_clock():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        await table.deal(1)
        token, deadline = table.turn_token, table.turn_deadline
        await table.request_leave(3)                                       # player 1 is still to act
        assert table.turn_token == token and table.turn_deadline == deadline
    asyncio.run(go())


def test_closing_mid_hand_voids_it():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        await table.deal(1)
        await table.act(1, "raise", 2000)
        await table.close("Closed by the host.")
        assert "cancelled" in table.close_reason
        assert [conf.get_user(u).chip_balance for u in (1, 2, 3)] == [100_000] * 3
        assert not conf.holdem_escrow
    asyncio.run(go())


def test_timeouts_check_or_fold_and_two_hands_sit_out():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        for hand in range(2):
            await table.deal(1)
            while table.phase == "hand" and table.hand.to_act_id != 2:
                await table.act(table.hand.to_act_id, "call" if table.hand.legal_actions(table.hand.to_act_id).can_call else "check")
            if table.phase == "hand":
                await table.on_turn_timeout(table.turn_token)
                assert "(timed out)" in " ".join(table.log_lines)
            while table.phase == "hand":
                uid = table.hand.to_act_id
                if uid == 2:
                    await table.on_turn_timeout(table.turn_token)
                else:
                    await table.act(uid, "check" if table.hand.legal_actions(uid).can_check else "fold")
            table.phase = "waiting"
        assert 2 in table.sat_out
        assert [s.member.id for s in table.ready_seats()] == [1, 3]
        assert table.toggle_sit_out(2) is False and 2 not in table.sat_out
    asyncio.run(go())


def test_stale_timer_does_nothing():
    async def go():
        cog, conf, table = make_table([5000, 5000])
        await seat_all(table, [5000, 5000])
        await table.deal(1)
        old = table.turn_token
        await table.act(1, "call")
        await table.on_turn_timeout(old)
        assert table.hand.to_act_id == 2 and not table.timed_out_this_hand
    asyncio.run(go())


def test_joining_mid_hand_waits_for_the_next_one():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000])
        await table.deal(1)
        assert await table.sit(member(3), 5000) is None
        assert not table.in_hand(3) and "next hand" in table.build_embed().description
        await table.act(1, "fold")
        await table.deal(1)
        assert table.in_hand(3)
    asyncio.run(go())


def test_table_captain_after_ten_counted_hands():
    async def go():
        cog, conf, table = make_table([20000, 20000, 20000])
        await seat_all(table, [20000, 20000, 20000])
        for _ in range(10):
            await table.deal(1)
            while table.phase == "hand":
                await table.act(table.hand.to_act_id, "fold")
        assert conf.get_user(1).holdem_tables_hosted == 1
        await table.deal(1)
        while table.phase == "hand":
            await table.act(table.hand.to_act_id, "fold")
        assert conf.get_user(1).holdem_tables_hosted == 1                  # once per table
    asyncio.run(go())


def test_only_the_host_deals_unless_sitting_out():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        assert await table.deal(2) == "Only the host can deal."
        table.toggle_sit_out(1)
        assert await table.deal(2) is None
        assert not table.in_hand(1)
    asyncio.run(go())


def test_private_controls_show_the_right_buttons():
    async def go():
        cog, conf, table = make_table([5000, 5000, 5000])
        await seat_all(table, [5000, 5000, 5000])
        await table.deal(1)
        mine = HoldemPrivateView(table, 1)
        labels = [b.label for b in mine.children]
        assert labels[:3] == ["Fold", "Call 200", "All-In (5,000)"]
        assert "Raise to 400 (Min)" in labels and "Custom…" in labels
        assert "Your turn" in mine.build_embed().description
        waiting = HoldemPrivateView(table, 2)
        assert not waiting.children and "Waiting on <@1>" in waiting.build_embed().description
        assert "Your cards" in waiting.build_embed().description
    asyncio.run(go())


def test_random_table_session_never_loses_money():
    """Hundreds of hands with random actions, timeouts, players leaving and rejoining mid-hand, sitting out
    and busting. Total money (balances + escrow) never changes, and escrow matches the stacks between hands."""
    import random

    async def go():
        rng = random.Random(42)
        random.seed(42)                                   # the table's decks shuffle with the global random
        ids = list(range(1, 7))
        cog, conf, table = make_table([0] * 6)
        for uid in ids:
            conf.get_user(uid).chip_balance = 100_000
        await seat_all(table, [rng.randint(4000, 20000) for _ in ids])
        start = total_money(conf, ids)
        hands = 0
        for _ in range(400):
            if table.phase == "closed":                      # everyone left: open a fresh table
                table = HoldemTable(cog, GUILD, SimpleNamespace(id=10), member(1), 100, 200, 6, "chips")
                cog.hd_tables()[table.key] = table
            if table.phase == "showdown":
                for uid, choice in list(table.reveal.items()):
                    if choice == "pending":
                        await table.choose_reveal(uid, rng.choice(["show", "muck"]))
            # between hands: people come and go
            for uid in ids:
                if table.seat_of(uid) is None and rng.random() < 0.3 and conf.get_user(uid).chip_balance >= 4000:
                    await table.sit(member(uid), rng.randint(4000, min(20000, conf.get_user(uid).chip_balance)))
                elif table.seat_of(uid) is not None and rng.random() < 0.05:
                    table.toggle_sit_out(uid)
            if table.host_id in table.sat_out:
                table.toggle_sit_out(table.host_id)
            if table.seat_of(table.host_id) is None and table.seats:
                table.host_id = table.seats[0].member.id
            if len(table.ready_seats()) < 2:
                continue
            assert await table.deal(table.host_id) is None
            hands += 1
            while table.phase == "hand":
                hand = table.hand
                uid = hand.to_act_id
                roll = rng.random()
                if roll < 0.05:
                    await table.on_turn_timeout(table.turn_token)
                elif roll < 0.08:
                    await table.request_leave(rng.choice([s.member.id for s in table.seats]))
                elif roll < 0.10:
                    joiner = rng.choice(ids)
                    if table.seat_of(joiner) is None and conf.get_user(joiner).chip_balance >= 4000:
                        await table.sit(member(joiner), 4000)
                else:
                    la = hand.legal_actions(uid)
                    options = (["fold"] if la.can_call else []) + (["check"] * 3 if la.can_check else [])
                    options += (["call"] * 4 if la.can_call else []) + (["raise", "allin"] if la.can_raise else [])
                    action = rng.choice(options)
                    amount = rng.randint(la.min_to, la.max_to) if action == "raise" else None
                    assert await table.act(uid, action, amount) is None
                assert total_money(conf, ids) == start
            if table.phase != "closed":
                assert escrow_matches(conf, table)
            assert total_money(conf, ids) == start
        assert hands > 150
    asyncio.run(go())
