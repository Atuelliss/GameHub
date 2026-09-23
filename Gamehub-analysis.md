# GameHub Workspace Analysis

_Analyzed: 2026-09-23 (branch `main`, commit `33e5134`)_

## 1. Overview

GameHub is a collection of six game cogs for **Red-DiscordBot 3.5.3+** (Python 3.10+). All six come from the same "Advanced Cookiecutter" template (credited to Vertyco). They share one architecture:

- **Pydantic models** as the data layer, stored in a single JSON file per cog under `cog_data_path(self)`. Red's `Config` is not used.
- **Atomic file writes**: `Base.to_file()` writes to a temp file, runs `fsync`, then `replace()`s the original.
- **A non-blocking `self.save()`** that starts a background task.
- **Mixins** (`abc.py` + `commands/`, `listeners/`, `tasks/`) combined into one cog class with `CompositeMetaClass`.
- **discord.py UI Views** (buttons, selects, modals) for most gameplay.

| Cog | Class | Theme | .py files | Python LOC | Data file |
|---|---|---|---|---|---|
| `crimetime` | `CrimeTime` | Mugging/robbery/heist crime game with a black market | 11 | 3,916 | `db.json` |
| `dinocollector` | `DinoCollector` | Ark/Pokemon-style dino spawning, catching, trading | 29 | 7,533 | `dinocollectordb.json` |
| `gafishing` | `GreenacresFishing` | Fishing sim with seasons, weather, time zones | 26 | 10,731 | `db.json` |
| `highrollerclub` | `HighRollerClub` | Casino with 12 games, ranks, prestige | 42 | 16,109 | `db.json` |
| `petcord` | `Petcord` | Virtual pet lifecycle with decay, medals, wardrobe | 40 | 24,154 | `data.json` |
| `russian` | `Russian` | Russian Roulette (solo and challenge), betting | 11 | 2,993 | `db.json` |
| **Total** | | | **159** | **~65,400** | |

The workspace also contains about 12k lines of design docs (`PETCORD_DESIGN.md`, `IMPLEMENTATION_GUIDE.md`, `creation_instructions.MD`, `hrc_concepts.MD`, `GAME_SUMMARY.md`, `LURE_SYSTEM_REWRITE_PLAN.md`), a Jupyter notebook (`dinocollector/calculate_log_value.ipynb`), and 9 PNG thumbnails for HighRollerClub.

---

## 2. Per-Cog Summary

### 2.1 CrimeTime (`crimetime/`)
- **Gameplay:** mugging (`pwin/ploss`), robbery (`rwin/rloss`), and heists (`hwin/hloss`). Players hold cash, gold bars, and gems, and can invest or liquidate (`ctinvest bars|gems|b2g`, `ctliquidate`). A black market rotates on a timer (`blackmarket.py`), and there is a carjack module (`carjack.py`).
- **Admin:** `ctset` (balances, stats, gold/gem values, bank conversion, game mode), `ctevent`, and `ctdatabase download|upload|info` for backing up and restoring the DB.
- **Background:** `blackmarket_cycle_loop` checks every 60s.
- **UI:** `dynamic_menu.py` holds the menus.
- **Notes:** `info.json` has the most complete metadata of the six (short, tags). `end_user_data_statement` is empty.

### 2.2 DinoCollector (`dinocollector/`)
- **Gameplay:** dinos spawn from chat activity (`listeners/messages.py`, `views/spawn.py`). Players catch, sell, and trade them (`dctrade`), keep a buddy dino (`dcbuddy set|clear|name|info`), use lures and upgrades (`dcshop buy upgrade|lure`), fill an Explorer Log (`dclog sell`), and earn achievements. Players can also convert and invest currency with Red's bank.
- **Admin:** `dcsetup` (Quick/Full guided wizard), `dcset` (admin role, blacklist, start/stop game, events, conversion, cleanup, display).
- **Data:** `databases/creatures.py` (1,669 lines of creature definitions), `achievements.py`, and `constants.py`.
- **Background:** tasks wait on `self._db_ready` before they run.
- **Notes:** `test_achievements.py` (892 lines, about 120 `print()` calls) is a standalone script, not a pytest suite. `LURE_SYSTEM_REWRITE_PLAN.md` describes a planned refactor.

### 2.3 Greenacres Fishing (`gafishing/`)
- **Gameplay:** four locations (Pond, Lake, River, Ocean), seasons that depend on the configured time zone and hemisphere, weather (`common/weather.py`), and rods and lures with durability. It also has a bait shop, fish info encyclopedia, inventory, and leaderboard. Everything runs through Views started from `[p]fish`.
- **Admin:** `fishsetup` and `fishset` (timezone, hemisphere, channels, start/stop, conversion, fish points, debug spawn/list/download).
- **Migrations:** `_migrate_inventory_format()` runs at startup and converts the old inventory schema.
- **Notes:** requires `tzdata`. Has its own `.github/copilot-instructions.md` inside the cog folder. It tracks active Views and stops them on unload.

### 2.4 HighRollerClub (`highrollerclub/`)
- **Games (12):** All-In, Big 6 Wheel, Blackjack, Double, Hi-Lo, Keno, Multiplier Wheel, Mystery Wheel, Poker (plus Club Poker view), Roulette, Slots, War. Game logic lives in `games/` and is kept apart from the UI in `views/`, which is the cleanest split in the workspace.
- **Systems:** ranks and prestige, rank multipliers, bet limits, All-In tiers, scratch cards with cooldowns, daily mystery spins, lucky streaks and timed multipliers (expired ones are cleared at startup), and a Red bank or internal-currency payment mode.
- **Admin:** `highrollerclubset` has a large settings tree (paymentmode, rng, betlimits, housesegments, per-game enable/disable, channels, blacklist, wipe/reset).
- **Notes:** `info.json` has an empty `description` and `short`. The README is still the unmodified cookiecutter README.

### 2.5 Petcord (`petcord/`)
- **Gameplay:** players find and adopt randomized pets (`database/species.py`, `appearance.py`) and raise them through lifecycle stages. Stats decay over time (`tasks/decay_task.py`). Pets graduate to a Home, earn growth medals from daily care ratings, and can die (with a memorial) unless immortal mode is on. There are also treats, vitamins, and clothing shops, a wardrobe, gifts, achievements, and a leaderboard.
- **Admin:** `pcset` has about 30 subcommands (enable/disable, timers, stats, decay trigger, death/immortal, medals, blacklist, `backup list|restore|create`).
- **Robustness:** this cog has the most defensive persistence in the workspace:
  - It copies the DB to a backup before loading.
  - **It disables saving if the load fails**, so corrupt data is never overwritten.
  - Saves take an `asyncio.Lock`, retry up to 3 times, and keep rotating backups about 8h apart.
  - It registers a persistent "stale view" handler so old buttons answer after a restart.
- **Notes:** the largest cog (24k LOC; `admin_commands.py` alone is 3,029 lines). It is the only cog with a filled-in `end_user_data_statement`.

### 2.6 Russian Roulette (`russian/`)
- **Gameplay:** solo play and challenge play, with min/max bets, betting mode (Red bank or tokens), token/Discord currency conversion (`rrconvert`), stats, and a leaderboard.
- **Admin:** `rrset` (bets, mode, channels, wipe, display, convert).
- **Notes:** its `__init__.py` is simpler than the others and does not set `__red_end_user_data_statement__`. `models.py` has leftover migration comments (`# Changed from self.dict()...`). Tags: `["prototype"]`.

---

## 3. Shared Code and Duplication

`common/__init__.py` (the pydantic `Base` with `model_dump` / `from_file` / `to_file`) is **copied into all six cogs** and the copies have drifted:

- `dinocollector` and `highrollerclub` (and `gafishing`) create a default file when it is missing.
- `crimetime` and `russian` raise `FileNotFoundError`.
- The version check `VERSION >= "2.0.1"` compares strings, not versions. It works for pydantic 2.x but is fragile.

`abc.py`, `formatting.py`, the `save()` pattern, and the leaderboard and pagination Views are also repeated in most cogs. Red requires each cog to be self-contained, so some duplication can't be avoided. Still, keeping one canonical `Base` and syncing it into every cog would stop behavior from diverging.

---

## 4. Findings and Risks

Ordered roughly by severity.

### 4.1 Save coalescing can drop writes (gafishing, highrollerclub, russian)
```python
async def _save():
    if self._saving:
        return          # this request is silently dropped
```
If `save()` is called while a write is in progress, the newer state is **not written** until some later save happens. After a burst of game actions followed by a crash or restart, the most recent changes can be lost. `dinocollector` fixes this with a `_save_retry` loop, `crimetime` with `_save_pending`, and `petcord` with a lock. The three affected cogs should use one of those patterns.

### 4.2 Fire-and-forget tasks are not referenced
`asyncio.create_task(_save())` and `asyncio.create_task(self.initialize())` are called without keeping a reference to the task. The event loop only keeps weak references, so a pending task can be garbage-collected. Exceptions inside `initialize()` are also never surfaced.

### 4.3 Load failures can wipe data (crimetime, russian)
Both cogs catch *any* load exception and replace the data with an empty `DB()`. The next `save()` then overwrites the corrupt but recoverable `db.json` with empty data. Petcord already avoids this (§2.5) and its approach could be reused.

### 4.4 Unhandled startup errors (dinocollector, gafishing, highrollerclub)
`initialize()` has no `try/except` around `DB.from_file`. If the JSON is corrupt:
- **dinocollector:** `_db_ready` is never set, so background tasks hang forever.
- **highrollerclub:** background tasks never start. `cog_unload` then writes the empty in-memory `DB()` over the file.
- **gafishing:** migrations never run, and the cog keeps running on an empty DB.

### 4.5 No final save on unload (crimetime, gafishing, russian)
`crimetime.cog_unload` only cancels the black market task. Pending saves are not flushed. `highrollerclub` and `petcord` do a final synchronous save, and the other three should too.

### 4.6 GDPR / Red data-API stubs
In five cogs, `red_delete_data_for_user` and `red_get_data_for_user` just `return` (petcord doesn't define them at all). Every cog stores per-user data, so `[p]mydata forgetme` and owner deletion requests do nothing. Five `info.json` files also have an empty `end_user_data_statement`. This matters if the cogs are published.

### 4.7 Exception handling
| Cog | bare `except:` | `except Exception` |
|---|---|---|
| crimetime | 0 | 9 |
| dinocollector | 10 | 11 |
| gafishing | 4 | 11 |
| highrollerclub | 0 | 3 |
| petcord | 2 | 44 |
| russian | 3 | 16 |

A bare `except:` also catches `asyncio.CancelledError` and `KeyboardInterrupt`, which can block task cancellation on unload. Most of these wrap Discord message edits and should be narrowed to `discord.HTTPException` / `discord.NotFound`.

### 4.8 Concurrency on currency
Only `highrollerclub` and `petcord` use an `asyncio.Lock`. The economy cogs change balances in memory across `await` points (bank calls, View callbacks). Nothing locks per user, so two fast button clicks or two commands at once can double-spend or double-pay. This applies especially to trades (`dctrade`), conversion/invest commands, and roulette challenge payouts. Every such path should be audited.

### 4.9 RNG
All games use the `random` module (23 imports in `highrollerclub` alone). That is fine for a Discord game. If real-money-equivalent Red bank credits are at stake and fairness matters, consider `random.SystemRandom`. Note that `highrollerclub` already exposes an `rng` admin setting.

### 4.10 Repository / packaging
- **No top-level `info.json`.** Red's Downloader (`[p]repo add`) needs a repo-level `info.json`. Without it the repo can't be installed from Git.
- `info.json` metadata is inconsistent. Authors appear as `"Jayar"`, `"Jayar/Vainne"`, and `["Jayar","Vertyco"]`. `highrollerclub` has an empty description, and several cogs have empty `short` and `tags`.
- The `highrollerclub/README.md` and `dinocollector/README.md` sections are still template boilerplate ("Advanced Cookiecutter").
- There are three separate `copilot-instructions.md` files (root, `gafishing/.github/`, `russian/.github/`). The nested `.github` folders have no effect there.
- `.gitignore` has no newline at the end of the file. That is harmless.

### 4.11 Maintainability
- Several files are very large: `petcord/commands/admin_commands.py` (3.0k lines), `crimetime/main.py` (2.3k lines, which mixes commands, logic, and tasks in one file instead of following the mixin layout), `petcord/species.py` (2.2k), `highrollerclub/admin_commands.py` (2.1k), and `petcord/clothing_shop.py` (2.1k). They would be easier to work with if split up.
- There is no automated test suite. `dinocollector/test_achievements.py` is a script that prints its results. A small pytest suite for the pure logic (payout math, decay, season calculation, `games/*.py` in HRC) would pay off quickly, because that logic is already separated from Discord.
- There is no linter or formatter config (ruff/black) and no CI.

---

## 5. Strengths

- A consistent architecture across all cogs makes it easy to move between them.
- Atomic, fsync'd JSON writes are better than the naive `json.dump`.
- Typed pydantic models instead of raw dicts.
- Game logic is separate from the UI in HighRollerClub.
- Guided setup wizards (`dcsetup`, `fishsetup`, `petsetup`, `hrcset setup`) make the cogs easy for server admins to set up.
- Petcord's persistence (backups, load-failure guard, retries, stale-view handler) is a good model for the other cogs.
- Views are tracked and stopped on unload (gafishing, petcord), which avoids orphaned interactive messages.
- The design docs are extensive.

---

## 6. Recommended Next Steps (priority order)

1. Fix the dropped-save pattern in `gafishing`, `highrollerclub`, and `russian` (§4.1).
2. Guard DB loading in every cog. Never save over a file that failed to load (§4.3, §4.4).
3. Keep references to background tasks, and flush a final save on unload (§4.2, §4.5).
4. Add per-user locks around balance-changing operations (§4.8).
5. Implement `red_delete_data_for_user` and fill in `end_user_data_statement` (§4.6).
6. Add a repo-level `info.json` and clean up per-cog metadata and READMEs (§4.10).
7. Replace bare `except:` with specific exceptions (§4.7).
8. Add pytest coverage for the pure game logic, and add ruff (§4.11).
