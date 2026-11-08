"""Texas Hold'em settings and money safety (Stage 2): blind levels and who can open them, buy-in ranges, the
prestige switch on record_win/record_loss, the game starting switched off on existing servers, and escrow refunds.

Run from the workspace root:  .venv/Scripts/python.exe -m pytest highrollerclub/tests -q
"""

import asyncio
from types import SimpleNamespace

from highrollerclub.commands.helper_functions import (
    get_holdem_tiers,
    holdem_buyin_range,
    holdem_tier_unlocked,
    record_loss,
    record_win,
)
from highrollerclub.common.constants import CARD_MATH_GAMES, GAME_SLUGS, HOLDEM_DEFAULT_STAKE_TIERS
from highrollerclub.common.models import GuildSettings, HoldemStakeTier
from highrollerclub.tasks.holdem_tables import HoldemTableKeeper


def test_slug_sits_right_after_club_poker():
    assert GAME_SLUGS[GAME_SLUGS.index("clubpoker") + 1] == "holdem"
    assert "holdem" in CARD_MATH_GAMES
    assert len(GAME_SLUGS) == 15


def test_default_levels_and_rank_unlocks():
    conf = GuildSettings()
    tiers = get_holdem_tiers(conf)
    assert [(t.sb, t.bb, t.min_rank) for t in tiers] == [
        (100, 200, 1), (200, 500, 1), (500, 750, 2), (750, 1000, 3), (1000, 1500, 4)
    ]
    opens = {rank: [t.bb for t in tiers if holdem_tier_unlocked(conf, t, rank)] for rank in range(1, 5)}
    assert opens == {1: [200, 500], 2: [200, 500, 750], 3: [200, 500, 750, 1000], 4: [200, 500, 750, 1000, 1500]}


def test_rank_stakes_off_means_member_levels_only():
    conf = GuildSettings(bet_multipliers_enabled=False)
    tiers = get_holdem_tiers(conf)
    assert [t.bb for t in tiers if holdem_tier_unlocked(conf, t, 4)] == [200, 500]
    # ...unless an admin re-ranks a bigger level to Member
    conf.holdem_stake_tiers = [HoldemStakeTier(**t) for t in HOLDEM_DEFAULT_STAKE_TIERS]
    conf.holdem_stake_tiers[4].min_rank = 1
    assert [t.bb for t in get_holdem_tiers(conf) if holdem_tier_unlocked(conf, t, 1)] == [200, 500, 1500]


def test_switched_off_level_is_closed_to_everyone():
    conf = GuildSettings(holdem_stake_tiers=[HoldemStakeTier(**t) for t in HOLDEM_DEFAULT_STAKE_TIERS])
    conf.holdem_stake_tiers[0].enabled = False
    assert not holdem_tier_unlocked(conf, get_holdem_tiers(conf)[0], 4)


def test_edited_levels_are_returned_in_place():
    conf = GuildSettings(holdem_stake_tiers=[HoldemStakeTier(**t) for t in HOLDEM_DEFAULT_STAKE_TIERS])
    get_holdem_tiers(conf)[1].sb = 250
    assert conf.holdem_stake_tiers[1].sb == 250


def test_buyin_range():
    conf = GuildSettings()
    assert holdem_buyin_range(conf, 200) == (4000, 20000)
    assert holdem_buyin_range(conf, 1500) == (30000, 150000)
    conf.holdem_min_buyin_bb = 5          # below the 10 BB floor
    conf.holdem_max_buyin_bb = 8          # and below the minimum
    assert holdem_buyin_range(conf, 200) == (2000, 2000)


def test_award_prestige_switch():
    conf = GuildSettings()
    user = conf.get_user(1)
    user.prestige_points = 10.0
    record_win(conf, user, "holdem", 600, 200, award_prestige=False)
    record_loss(conf, user, "holdem", 200, award_prestige=False)
    assert user.prestige_points == 10.0
    assert user.game_win_counts["holdem"] == 1 and user.game_loss_counts["holdem"] == 1
    assert user.total_wins == 1 and user.total_payout_earned == 400
    record_win(conf, user, "holdem", 600, 200)
    assert user.prestige_points == 10.0 + conf.prestige_win_points


def test_existing_servers_start_with_holdem_off():
    # An admin enabled Club Poker before Hold'em existed (saves only store changed settings)
    saved = {"games_enabled": {"clubpoker": True, "horserace": True}}
    conf = GuildSettings.model_validate(saved)
    assert conf.games_enabled["holdem"] is False and conf.games_enabled["clubpoker"] is True


def test_escrow_round_trips_through_save():
    conf = GuildSettings()
    keeper = SimpleNamespace(save=lambda: None)
    HoldemTableKeeper.hd_escrow_set(keeper, conf, 42, 5000, "chips", 777)
    loaded = GuildSettings.model_validate(conf.model_dump(mode="json"))
    assert loaded.holdem_escrow[42].amount == 5000 and loaded.holdem_escrow[42].payment_mode == "chips"
    HoldemTableKeeper.hd_escrow_set(keeper, conf, 42, 0, "chips", 777)
    assert 42 not in conf.holdem_escrow


def _fake_keeper(fail_ids=()):
    paid = []

    async def credit(guild, conf, mode, user_id, amount, label="Horse Racing"):
        if user_id in fail_ids:
            return False
        paid.append((user_id, amount, mode))
        if mode == "chips":
            conf.get_user(user_id).chip_balance += amount
        return True

    return SimpleNamespace(save=lambda: None, _hr_credit=credit), paid


def test_refund_pays_everyone_and_keeps_failures_for_retry():
    conf = GuildSettings()
    keeper, paid = _fake_keeper(fail_ids={3})
    for uid, amount, mode in [(1, 4000, "chips"), (2, 9000, "bank"), (3, 6000, "bank")]:
        HoldemTableKeeper.hd_escrow_set(keeper, conf, uid, amount, mode, 555)
    channels = asyncio.run(HoldemTableKeeper._hd_refund_escrow(keeper, None, conf))
    assert sorted(paid) == [(1, 4000, "chips"), (2, 9000, "bank")]
    assert conf.get_user(1).chip_balance == 4000
    assert list(conf.holdem_escrow) == [3]          # failed refund kept for the next load
    assert channels == {555}

    keeper2, paid2 = _fake_keeper()
    asyncio.run(HoldemTableKeeper._hd_refund_escrow(keeper2, None, conf))
    assert paid2 == [(3, 6000, "bank")] and not conf.holdem_escrow
