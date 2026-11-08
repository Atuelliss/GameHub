"""Texas Hold'em admin page and titles (Stage 5): the eight titles unlock at their thresholds, the setup wizard's
Hold'em page edits levels safely and only saves what changed, and the Manage Titles dropdown pages and wraps.

Run from the workspace root:  .venv/Scripts/python.exe -m pytest highrollerclub/tests -q
"""

import asyncio
from types import SimpleNamespace

from highrollerclub.commands.admin_commands import _holdem_levels_error, _Page14Holdem, _WizardState
from highrollerclub.commands.helper_functions import evaluate_specialty_titles, get_holdem_tiers
from highrollerclub.commands.user_commands import TitleSelectView
from highrollerclub.common.constants import HOLDEM_DEFAULT_STAKE_TIERS, SPECIALTY_TITLES
from highrollerclub.common.models import DB, GuildSettings, HoldemStakeTier, User

HOLDEM_TITLES = {
    "grinder": ("holdem_hands_dealt", 250),
    "bluff_master": ("holdem_fold_wins", 25),
    "river_rat": ("holdem_river_comebacks", 5),
    "shove_survivor": ("holdem_allin_wins", 10),
    "monster_pot": ("holdem_best_pot_bb", 100),
    "royal_treatment": ("holdem_royal_flushes", 1),
    "bad_beat": ("holdem_bad_beats", 1),
    "table_captain": ("holdem_tables_hosted", 10),
}


# --------------------------------------------------------------------------- titles

def test_every_holdem_title_has_a_name():
    assert all(slug in SPECIALTY_TITLES for slug in HOLDEM_TITLES)
    assert len(SPECIALTY_TITLES) == 23               # 15 earlier titles + 8 Hold'em


def test_holdem_titles_unlock_exactly_at_their_thresholds():
    for slug, (counter, threshold) in HOLDEM_TITLES.items():
        below = User(**{counter: threshold - 1})
        assert slug not in evaluate_specialty_titles(below), slug
        at = User(**{counter: threshold})
        assert slug in evaluate_specialty_titles(at), slug
        at.earned_titles.append(slug)
        assert slug not in evaluate_specialty_titles(at), f"{slug} awarded twice"


# --------------------------------------------------------------------------- wizard page

class _Response:
    def __init__(self):
        self.sent = []

    async def send_message(self, text, **kwargs):
        self.sent.append(text)

    async def edit_message(self, **kwargs):
        self.sent.append("edited")


def _interaction(values=None):
    return SimpleNamespace(response=_Response(), data={"values": values or []}, user=SimpleNamespace(id=1), message=None)


def test_levels_must_stay_open_to_members():
    tiers = [HoldemStakeTier(**t) for t in HOLDEM_DEFAULT_STAKE_TIERS]
    assert _holdem_levels_error(tiers) is None
    tiers[0].enabled = tiers[1].enabled = False
    assert "Members" in _holdem_levels_error(tiers)
    for t in tiers:
        t.enabled = False
    assert "stay on" in _holdem_levels_error(tiers)


def test_untouched_wizard_leaves_the_defaults_alone():
    conf = GuildSettings()
    _WizardState(conf).apply(conf)
    assert conf.holdem_stake_tiers == []           # still "use the defaults"


def test_wizard_page_edits_and_saves_levels():
    async def go():
        conf = GuildSettings()
        state = _WizardState(conf)
        page = _Page14Holdem(SimpleNamespace(author=SimpleNamespace(id=1)), state, SimpleNamespace(), selected=4)
        assert "1,000 / 1,500" in page._build_embed().fields[0].value

        inter = _interaction(["1"])
        await page._on_rank(inter)                 # Whale level now open to Members
        assert state.holdem_stake_tiers[4].min_rank == 1

        page.selected = 0
        await page._toggle(_interaction())         # level 1 off: level 2 and 5 are still open to Members
        assert not state.holdem_stake_tiers[0].enabled
        page.selected = 1
        await page._toggle(_interaction())
        page.selected = 4
        refused = _interaction()
        await page._toggle(refused)                # would leave Members nothing: refused, nothing changed
        assert "Members" in refused.response.sent[0] and state.holdem_stake_tiers[4].enabled

        assert conf.holdem_stake_tiers == []       # nothing saved until the wizard applies
        state.apply(conf)
        tiers = get_holdem_tiers(conf)
        assert [t.enabled for t in tiers] == [False, False, True, True, True]
        assert tiers[4].min_rank == 1 and isinstance(tiers[4], HoldemStakeTier)
        loaded = GuildSettings.model_validate(conf.model_dump(mode="json"))
        assert [t.enabled for t in get_holdem_tiers(loaded)] == [False, False, True, True, True]

        state2 = _WizardState(conf)
        page2 = _Page14Holdem(SimpleNamespace(author=SimpleNamespace(id=1)), state2, SimpleNamespace())
        await page2._reset(_interaction())
        state2.apply(conf)
        assert [(t.sb, t.bb, t.min_rank, t.enabled) for t in get_holdem_tiers(conf)] == [
            (t["sb"], t["bb"], t["min_rank"], True) for t in HOLDEM_DEFAULT_STAKE_TIERS
        ]
    asyncio.run(go())


def test_wizard_copy_is_separate_from_live_levels():
    conf = GuildSettings(holdem_stake_tiers=[HoldemStakeTier(**t) for t in HOLDEM_DEFAULT_STAKE_TIERS])
    state = _WizardState(conf)
    state.holdem_stake_tiers[0].sb = 150
    assert conf.holdem_stake_tiers[0].sb == 100    # untouched until Save


# --------------------------------------------------------------------------- Manage Titles dropdown

def _title_view(titles, active=None):
    cog = SimpleNamespace(db=DB(), save=lambda: None)
    member = SimpleNamespace(id=7, guild=SimpleNamespace(id=1))
    user = cog.db.get_conf(1).get_user(7)
    user.earned_titles = list(titles)
    user.active_title = active
    return TitleSelectView(member, cog, 0, "chips"), user


def test_title_dropdown_fits_on_one_page():
    async def go():
        view, user = _title_view(list(SPECIALTY_TITLES)[:5], active="grinder")
        select = view.children[0]
        assert [o.label for o in select.options][0] == "No title"
        assert len(select.options) == 6
        assert [b.label for b in view.children[1:]] == ["← Back"]        # no arrows on one page
        await view._on_pick(_interaction(["__none__"]))
        assert user.active_title is None
        await view._on_pick(_interaction(["lucky_star"]))
        assert user.active_title == "lucky_star"
    asyncio.run(go())


def test_title_dropdown_pages_and_wraps():
    async def go():
        titles = list(SPECIALTY_TITLES) + [f"extra_{i}" for i in range(6)]   # 29 titles: 24 + 5
        view, user = _title_view(titles)
        assert len(view.children[0].options) == 25 and view._page_count() == 2
        labels = [b.label for b in view.children[1:]]
        assert labels == ["◀ Prev", "Page 1/2", "Next ▶", "← Back"]
        await view._make_page_cb(1)(_interaction())
        assert len(view.children[0].options) == 1 + 5 and view.children[2].label == "Page 2/2"
        await view._make_page_cb(1)(_interaction())                      # wraps to the first page
        assert view.children[2].label == "Page 1/2"
        await view._make_page_cb(-1)(_interaction())                     # and backwards to the last
        assert view.children[2].label == "Page 2/2"
    asyncio.run(go())
