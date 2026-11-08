"""Texas Hold'em rules, checked against games/holdem.py with no Discord: hand ranking, betting order, minimum
raises, short all-ins, side pots, split pots, leaving mid-hand, the title triggers, and two seeded random runs
(15,000 hands) that check chips are always conserved and every hand ends.

Run from the workspace root:  .venv/Scripts/python.exe -m pytest highrollerclub/tests -q
"""

import random

import pytest

from highrollerclub.games.holdem import HoldemError, HoldemHand, best_hand
from highrollerclub.games.poker import Card, Deck

RANKS = {"A": 1, "K": 13, "Q": 12, "J": 11, "T": 10, **{str(n): n for n in range(2, 10)}}
SUITS = {"s": "♠", "h": "♥", "d": "♦", "c": "♣"}
TIERS = [(100, 200), (200, 500), (500, 750), (750, 1000), (1000, 1500)]


def cards(text):
    return [Card(RANKS[t[0]], SUITS[t[1]]) for t in text.split()]


def stacked(holes, board, button=0):
    """A deck that deals the given hole cards (one string per seat) and then the board.
    Hole cards go out one at a time starting left of the button, as the game deals them."""
    n = len(holes)
    order = [cards(holes[(button + off) % n])[rnd] for rnd in range(2) for off in range(1, n + 1)]
    order += cards(board)
    rest = [card for card in Deck()._cards if card not in set(order)]
    deck = Deck()
    deck._cards = rest + list(reversed(order))  # draw() pops from the end
    return deck


def hand(stacks, button=0, blinds=(100, 200), deck=None):
    players = [(i + 1, s) for i, s in enumerate(stacks)]
    return HoldemHand(players, button=button, small_blind=blinds[0], big_blind=blinds[1], deck=deck)


# --------------------------------------------------------------------------- hand ranking

def test_straights_rank_correctly():
    wheel = best_hand(cards("As 2d 3c 4h 5s Kd Qc"))
    six_high = best_hand(cards("2d 3c 4h 5s 6d Kd Qc"))
    ace_high = best_hand(cards("As Kd Qc Jh Ts 2d 3c"))
    assert wheel.rank == "straight"
    assert wheel.key < six_high.key < ace_high.key


def test_best_five_of_seven():
    assert best_hand(cards("Ah Kh Qh Jh Th 2c 3d")).rank == "royal_flush"
    assert best_hand(cards("2c 2d 2h 9s 9d")).rank == "full_house"


def test_kicker_decides_and_board_can_play():
    assert best_hand(cards("As Ad Kc 7h 2s 9d 4c")).key > best_hand(cards("Ah Ac Qc 7h 2s 9d 4c")).key
    assert best_hand(cards("2c 3d Ah Kh Qs Jd Tc")).key == best_hand(cards("4c 5d Ah Kh Qs Jd Tc")).key


# --------------------------------------------------------------------------- order of play

def test_heads_up_order():
    h = hand([10000, 10000])
    assert h.seats[0].hand_total == 100 and h.seats[1].hand_total == 200   # button posts the small blind
    assert h.to_act_id == 1                                                # button acts first pre-flop
    h.act(1, "call")
    assert h.to_act_id == 2 and h.legal_actions(2).can_check and h.legal_actions(2).can_raise  # BB option
    h.act(2, "check")
    assert h.street == "flop" and len(h.board) == 3
    assert h.to_act_id == 2                                                # BB acts first after the flop


def test_three_handed_order_and_minimum_raises():
    h = hand([10000, 10000, 10000])
    assert h.to_act_id == 1                                     # left of the big blind
    la = h.legal_actions(1)
    assert la.min_to == 400 and la.max_to == 10000
    h.act(1, "raise", 600)
    assert h.legal_actions(2).min_to == 1000                    # re-raise must be another 400
    with pytest.raises(HoldemError):
        h.act(2, "raise", 900)
    with pytest.raises(HoldemError):
        h.act(3, "fold")                                        # out of turn
    with pytest.raises(HoldemError):
        h.act(2, "check")                                       # facing a bet
    assert h.default_action(2) == "fold"
    h.act(2, "fold")
    h.act(3, "call")
    assert h.street == "flop" and h.to_act_id == 3
    assert h.default_action(3) == "check"
    assert h.legal_actions(3).min_to == 200 and h.legal_actions(3).is_bet


# --------------------------------------------------------------------------- short all-ins

def test_short_all_in_does_not_reopen_betting():
    h = hand([10000, 10000, 1500])
    h.act(1, "call"); h.act(2, "call"); h.act(3, "check")
    assert h.to_act_id == 2
    h.act(2, "raise", 1000)
    h.act(3, "allin")                    # 1300: a raise of only 300
    assert h.current_bet == 1300
    assert h.legal_actions(1).can_raise  # hasn't acted yet, so may raise
    h.act(1, "call")
    la = h.legal_actions(2)
    assert not la.can_raise and la.can_call and la.call_amount == 300
    with pytest.raises(HoldemError):
        h.act(2, "allin")                # only a call is allowed
    h.act(2, "call")
    assert h.street == "turn"


def test_short_all_ins_below_a_full_raise_together_do_not_reopen():
    h = hand([10000, 10000, 1350, 1600])
    h.act(4, "call"); h.act(1, "call"); h.act(2, "call"); h.act(3, "check")
    h.act(2, "raise", 1000)
    h.act(3, "allin")                    # +150
    h.act(4, "allin")                    # +250, 400 in all
    h.act(1, "call")
    assert not h.legal_actions(2).can_raise


def test_short_all_ins_adding_up_to_a_full_raise_reopen():
    h = hand([10000, 10000, 1700, 2400])
    h.act(4, "call"); h.act(1, "call"); h.act(2, "call"); h.act(3, "check")
    h.act(2, "raise", 1000)
    h.act(3, "allin")                    # +500
    h.act(4, "allin")                    # +700, 1200 in all
    h.act(1, "call")
    assert h.legal_actions(2).can_raise


def test_short_blinds():
    h = hand([50, 5000])                 # small blind can't cover it; the big blind already covers that
    assert h.is_complete and h.result.ran_out
    assert sum(h.final_stacks().values()) == 5050
    h = hand([5000, 150])                # big blind short
    la = h.legal_actions(1)
    assert la.call_amount == 100 and not la.can_raise
    h.act(1, "call")
    assert h.is_complete and sum(h.final_stacks().values()) == 5150


# --------------------------------------------------------------------------- pots

def test_side_pots():
    deck = stacked(["As Ad", "Ks Kd", "2c 7h"], "Ac 9s 4d 3h Jc")
    h = hand([1000, 3000, 5000], deck=deck)
    h.act(1, "allin"); h.act(2, "allin"); h.act(3, "call")
    r = h.result
    assert r.pots[0].amount == 3000 and r.pots[0].winners == (1,)
    assert r.pots[1].amount == 4000 and r.pots[1].winners == (2,)
    assert len(r.pots) == 2
    assert r.payouts == {1: 3000, 2: 4000, 3: 0}
    assert h.final_stacks()[3] == 2000   # only called 3000, so keeps the rest
    assert r.ran_out
    assert r.allin_showdown_wins == {1}


def test_split_pot_odd_chip_goes_left_of_button():
    deck = stacked(["2c 3d", "4c 5d", "6c 7d"], "Ah Kh Qs Jd Tc")
    h = hand([5000, 5000, 5000], blinds=(51, 101), deck=deck)
    h.act(1, "call"); h.act(2, "fold"); h.act(3, "check")
    for _ in range(3):
        h.act(3, "check"); h.act(1, "check")
    r = h.result
    assert set(r.main_pot_winners) == {1, 3}
    assert r.payouts == {1: 126, 2: 0, 3: 127}


def test_fold_win_returns_uncalled_bet():
    h = hand([5000, 5000])
    h.act(1, "allin"); h.act(2, "fold")
    r = h.result
    assert r.fold_win and r.fold_winner == 1 and not r.showdown_hands
    assert r.payouts[1] == 5200 and r.net[1] == 200
    assert r.pot_won_bb[1] == 2          # the uncalled 4,800 doesn't count toward Monster Pot


# --------------------------------------------------------------------------- leaving mid-hand

def test_leaving_out_of_turn():
    h = hand([5000, 5000, 5000])
    h.fold_player(3)
    assert h.to_act_id == 1
    h.act(1, "fold")
    assert h.is_complete and h.result.fold_winner == 2

    h = hand([5000, 5000, 5000])
    h.act(1, "call"); h.act(2, "call")
    h.fold_player(1)
    assert h.to_act_id == 3 and h.legal_actions(3).can_check  # big blind keeps the option


# --------------------------------------------------------------------------- title triggers

def test_river_comeback_and_all_in_win():
    deck = stacked(["Ks Kd", "As Ad"], "2c 7h 9s 4d Kc")
    h = hand([5000, 5000], deck=deck)
    h.act(1, "allin"); h.act(2, "call")
    r = h.result
    assert r.river_comebacks == {1} and r.main_pot_winners == (1,)
    assert 1 in r.allin_showdown_wins
    assert r.pot_won_bb[1] == 50


def test_royal_flush_and_bad_beat():
    deck = stacked(["Ah Kh", "9s 9d"], "Qh Jh Th 9c 9h")
    h = hand([5000, 5000], deck=deck)
    h.act(1, "allin"); h.act(2, "call")
    r = h.result
    assert r.royal_flushes == {1}
    assert r.bad_beats == {2}
    assert not r.river_comebacks


# --------------------------------------------------------------------------- random runs

def _play_random(seed, count, deep):
    rng = random.Random(seed)
    stats = {"showdowns": 0, "river_betting": 0, "side_pots": 0, "splits": 0}
    for hand_no in range(count):
        n = rng.randint(2, 6)
        sb, bb = (100, 200) if deep else rng.choice(TIERS)
        stacks = [rng.randint(80 * bb, 100 * bb) if deep else rng.randint(1, 100 * bb) for _ in range(n)]
        ids = rng.sample(range(1000, 9999), n)
        button = rng.randrange(n)
        h = HoldemHand(list(zip(ids, stacks)), button=button, small_blind=sb, big_blind=bb)
        first = True
        for _ in range(500):
            if h.is_complete:
                break
            uid = h.to_act_id
            seat = h.seat_for(uid)
            assert seat.can_act and (not seat.acted or seat.street_bet < h.current_bet), f"hand {hand_no}"
            if first and n == 2 and h.street == "preflop":
                assert uid == ids[button], f"hand {hand_no}: heads-up button must act first"
            first = False
            if not deep and rng.random() < 0.01:
                h.fold_player(rng.choice(ids))
                continue
            la = h.legal_actions(uid)
            options = (["fold"] if la.can_call else []) + (["check"] * 4 if la.can_check else [])
            options += (["call"] * 5 if la.can_call else []) + (["raise"] * 2 if la.can_raise else [])
            options += ["allin"] if la.can_raise and not deep else []
            action = rng.choice(options)
            amount = None
            if action == "raise":
                amount = la.min_to if deep else rng.randint(la.min_to, la.max_to)
            h.act(uid, action, amount)
        assert h.is_complete, f"hand {hand_no} didn't end"
        r = h.result
        assert sum(h.final_stacks().values()) == sum(stacks), f"hand {hand_no}: chips not conserved"
        assert sum(r.net.values()) == 0
        assert all(s.stack >= 0 for s in h.seats)
        assert all(set(p.winners) <= set(p.eligible) for p in r.pots)
        if not r.fold_win:
            assert len(r.board) == 5 and len(r.showdown_hands) >= 2
            stats["showdowns"] += 1
            stats["river_betting"] += not r.ran_out
        stats["side_pots"] += any(p.contested for p in r.pots[1:])
        stats["splits"] += len(r.main_pot_winners) > 1
    return stats


def test_random_hands_short_and_all_in_heavy():
    stats = _play_random(seed=20261107, count=10_000, deep=False)
    assert stats["side_pots"] > 1000 and stats["splits"] > 100


def test_random_hands_deep_stacks_bet_every_street():
    stats = _play_random(seed=7, count=5_000, deep=True)
    assert stats["river_betting"] > 4000
