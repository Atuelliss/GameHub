# Horse Racing: build plan for HighRollerClub

Instructions for Claude for building the Horse Racing game into this cog. The design below was agreed with the owner on 2026-10-10. **Read this whole file before writing any code**, then read the existing code it points to. Anything marked **OPEN** needs the owner's answer before you build that part.

This file is local-only (listed in the repo's `.gitignore`). Don't commit it.

> **Status (2026-10-10): BUILT.** Everything below is implemented. Where the build differs from the plan:
>
> - **Odds:** house-line odds are computed **exactly** (numerical integration over the race model in `games/horse_racing.py`), not from 5,000 simulated races. Checked against 100,000 simulated races, the largest difference was 0.2%, and it removes the sampling error that could have pushed a long shot over 100% at the 95% setting.
> - **Stat changes:** finishing-position changes that roughly cancel out, plus a 4% pull toward 50 each race (`REVERSION`), tuned by simulation. The best horse wins about 25% of races, and ratings settle between 33 and 77.
> - **Cooldown range:** the admin range for the starter cooldown is 0–1,440 minutes.
> - **`reset` keeps** the horses, carryover and owed refunds (game data, not settings), after refunding any open race.
> - **Live test still to do:** see §7.

---

## 0. Ground rules for the build

- Follow the cog's existing layout and idioms:
  - Pure logic goes in `games/`, the Discord UI in `views/`, and settings in `common/models.py`.
  - Constants go in `common/constants.py`, and admin commands and the wizard in `commands/admin_commands.py`.
- Reuse the shared helpers:
  - `one_at_a_time`, `safe_defer`, `safe_edit_original_response`, `expire_view`, `not_your_session` and `session_expired` from `common/interactions.py`.
  - `get_balance`, `deduct_balance`, `credit_balance`, `validate_bet`, `get_bet_limits`, `record_win`, `record_loss`, `evaluate_rank`, `apply_rank_change`, `evaluate_specialty_titles` and `is_blacklisted` from `commands/helper_functions.py`.
- The working copy uses CRLF line endings. Keep them when editing.
- Lint with `.venv/Scripts/python.exe -m pyflakes highrollerclub`.
- Smoke-test the pure logic with plain Python scripts in the scratchpad before writing any views.
- Don't commit unless the owner asks.
- Build in this order: the pure logic and its simulations, then the models and constants, then the money-safety layer, then the admin settings, then the views, then help, stats and titles.

---

## 1. Agreed design

### 1.1 Horses
- **The 15 default horses** have names that ship with the cog and never change.
- **Up to 10 custom slots:** the server owner (admin) can add, rename or remove horses there.
- **Starting stats:** every horse starts with all stats at **0**.
- **Stats:**
  - `speed`: base pace, which matters most on the straights.
  - `stamina`: reduces how much a horse fades in the later stages.
  - `turning`: matters most in the turn stages.
  - `start`: gate break, which matters in stage 1.
- **Career record per horse:** races run, wins, places (2nd), the last 5 finishes, and the current consecutive-race streak.
- **Stats are public.** The horse-picker dropdown shows each horse's stats and recent form. Because the payout is a shared pool, showing them doesn't make the game exploitable: the crowd sets the odds.

### 1.2 Field selection (10 horses a race)
- Draw 10 horses at random from all enabled horses (the defaults plus any custom ones).
- **Rotation rule:** a horse can't run more than **3 races in a row**. Any horse whose consecutive-race streak is 3 is left out of the draw.
- **Streaks:** after a race, the streak goes up by 1 for each horse that ran and resets to 0 for each horse that sat out.
- **Verified by simulation on 2026-10-10:** I ran 100,000 races with 15, 20 and 25 horses.
  - There were always at least 10 eligible horses.
  - Every horse ran an equal share of races: about 67% with 15 horses, 50% with 20 and 40% with 25.
  - Keep a fallback anyway: if fewer than 10 are eligible (for example, horses deleted mid-cycle), fill the field with the horses that have the lowest streaks.
- **Minimum horses:** racing needs at least 10 enabled horses. The 15 defaults guarantee this unless the code later lets admins disable default horses. If it does, block racing below 10.

### 1.3 Stats after a race (keeping the field competitive)
The rotation rule spreads races evenly, but it does **not** stop a strong horse from getting stronger: winners gain the most every time they run. To keep races from becoming predictable, also do the following:
- **Gains shrink as the stat rises**, for example `gain = base × (1 − stat / STAT_CAP)`, with a hard cap.
- **Finishing order sets the gain:** the top finishers gain the most, mid-pack gains a little, and the bottom finishers lose a little, never going below 0.
- **Every runner gains a small amount of experience**, so horses don't stall at 0.
- **Randomness stays dominant enough** that the favourite loses often.

**Tuning target:** simulate 1,000 races and check two things:
- The horse with the best stats wins between about 20% and 35% of the time, against a 10% baseline.
- No horse's win rate keeps climbing toward certainty.

Do the tuning with simulations in the scratchpad before any UI exists. Report the numbers to the owner.

### 1.4 The race
- **At least 5 stages.** I suggest 6: Gate break, First turn, Backstretch, Far turn, Home stretch, Finish.
- **Each stage:** every horse moves `distance += weighted(stats for this stage) + random roll`. Weight `start` in stage 1, `turning` in the turns, `speed` on the straights, and `stamina` more in the later stages (it reduces a late fade).
- **Positions:** sort the horses by total distance.
- **Updates:** after each stage, edit **one** race message in the race channel every **5 seconds** with a small text track (position, horse, and a progress bar). Edit it rather than posting a new message each stage, so the channel doesn't fill up.
- **Results:** at the end, post a **new** message with:
  - The finishing order.
  - Each horse's stat changes.
  - The payouts.
  - A ping for the winners.

### 1.5 Bets
- **Bet types:** **Win** (the horse finishes 1st) or **Place** (the horse finishes **1st or 2nd**).
  - Say "Place pays if your horse finishes 1st or 2nd" in the bet picker, on the race announcement, on the race message and in How to Play.
- **One bet per player per race:** one type, one horse, one amount. No changing it after you confirm.
- **Default limits:**
  - Win: max **1,500**.
  - Place: max **750**.
  - Min: suggest 10.
  - **Rank multipliers apply** to the max, as in every other game.
- **Bet-limit slugs:** use two, `horserace_win` and `horserace_place`. Add them to `DEFAULT_BET_LIMITS` and make them editable through the existing bet-limits wizard page and the `set limits` command.
- **No bonuses at all:** no Lucky Streak, Bonus Bet Token or Multiplier Wheel. Don't add `horserace*` to `MULTIPLIER_ELIGIBLE_GAMES` or `BONUS_BET_TOKEN_ELIGIBLE_GAMES`, and never call the bonus helpers in this game.
- **When money is taken:** each bet is deducted **at confirmation**.

### 1.6 Pools and payouts
- **Two pools:**
  - All Win stakes go into the **Win pool**.
  - All Place stakes go into the **Place pool**.
- **Pools on screen:** the announcement message shows both pools and the number of bettors. It updates every time a bet is confirmed.
- **House cut:** **10% by default**. Admins can change it; suggest allowing 0–25%. It's taken from each pool's player stakes before payout.
- **Win pool payout:** `net = pool − cut`. Each winning ticket gets `net × its stake ÷ total stake on the winner`.
- **Place pool payout:** the net Place pool is **split in half**, one half for the 1st-place horse's backers and one half for the 2nd-place horse's backers. Each half is split in proportion to stake, the standard racetrack method.
  - If only one of the two horses was backed, its backers take the whole net Place pool.
- **Rounding:** round payouts down to whole chips. The leftover crumbs go to the house.
- **A payout never drops below the stake:** a winning ticket always gets at least its stake back. If the maths would pay less (for example, everyone on the winner), raise it to the stake; the house covers the difference.

### 1.7 Solo races: the house line
Decided with the owner on 2026-10-10. This replaces the earlier seed ideas (a flat 500 seed, then matching the bet). Both were rejected: the flat seed made min-bet solo races profitable, and the matched bet returned only about 19% (Win) or 38% (Place).

- **When it applies:** when betting closes, if the starter is the only bettor, the race is paid on the **house line**: fixed odds set by the house instead of the pool.
  - **If anyone joins**, the race uses the normal pools (§1.6). The announcement says which payout mode applies and updates when it changes.
- **Working out the chances:** when the field is drawn, simulate **5,000 races** of that exact field with the same race function `games/horse_racing.py` uses for real races. Count each horse's chance of winning and of finishing top 2. Cache the result on the race.
  - **Use the same code.** The odds must come from the same function the real race uses, so knowing the stats gives no edge.
- **The payout:** `multiplier = target return ÷ chance`, rounded down to 2 decimals.
  - **Target return:** the new setting `horserace_house_line_return_pct`. **Default 80**; suggest an admin range of 50–95.
  - **Cap:** **30×** for Win and **15×** for Place (constants).
  - **Floor (confirmed by the owner on 2026-10-10):** if a multiplier would be below **1.05×**, that bet isn't offered on that horse; the picker shows "no odds" and the option can't be selected. So a win never pays less than the stake, and near-certain horses don't drift above the target. Don't floor at 1.0× instead, because that would push the return on near-certain horses up toward 90%+.
  - **No bettable horse:** if every horse ends up below the floor for a bet type, which is very unlikely, hide that bet type for the solo race and say why.
  - **The pool house cut does not apply** to house-line races; the target return already sets the house's share.
- **What players see:** the horse picker shows each horse's multiplier for the chosen bet type (for example "×7.85"), the same way Hi-Lo shows its multipliers. The starter's confirmation shows "Pays ×N if it wins (house line: solo race)". Once someone joins, the picker shows the current pools instead.
- **Money:** a house-line win pays `int(stake × multiplier)`. The house funds it; nothing comes from or goes to the carryover. A losing house-line bet doesn't add to the carryover either.
- **Expected value check (simulation):** for every horse and both bet types, the average return is at most the target return plus sampling noise. Every horse must come out below 100% at the 95% maximum setting.

### 1.8 Carryover
- **When it happens:** if nobody backed the winner (Win pool) or neither of the top two horses (Place pool), that pool's net amount carries over **into the same pool type** of the server's next race.
- **Stack limit:** it can build up for at most **5 races in a row**. On the race that would make it a 6th stack, the house keeps the carryover and the counter resets.
  - Track `carry_count` and the amount for each pool type.
- **House-line races never touch the carryover**; it waits for the next pool race.
- **The house cut is taken only once.** It's taken from a pool's new player stakes, and carryover money isn't cut again.
- **On screen:** the announcement shows the carryover, for example "Win pool: 2,400 (includes 900 carried over)".

### 1.9 Flow and timers
1. **Opening the game:** Horse Racing goes on the **Game Room**, as a normal game button that can be enabled or disabled like the others.
2. **Opening screen (private):**
   - **A race is already running on the server:** say so and show when it ends. Offer a link to the announcement so they can join, if betting is still open.
   - **No race is running:** show "Start a Race?" with the 10 horses already drawn. Keep that draw in memory until the player confirms or leaves the screen.
3. **Starter's betting steps:** Bet type → horse (a dropdown of 10 with stats and form) → amount (a modal showing the min and max for their rank) → confirmation.
   - On confirmation, deduct the bet, save the race to disk (§2) and post the announcement.
   - **Only one race per server at a time.** Lock it with an `asyncio.Lock` per server.
   - **Start/start race:** two players can press Start at the same moment, so the lock must be taken at confirmation, and the race's existence checked again inside it.
4. **Announcement (public, in the race channel):** "🏇 Horse Races about to Begin!!" Show:
   - The 10 horses.
   - The Win pool and Place pool, including any carryover.
   - The number of bettors.
   - A live countdown using a Discord timestamp, `<t:{unix}:R>`. Discord updates it on every screen by itself, so **don't** edit the message every second.
   - A **Join** button.
5. **Joining:** the same steps as the starter, privately.
   - **Checks:** the race channel, a blacklist check, and an "already bet in this race" check.
   - **Balance:** validated against the player's live balance at confirmation.
   - **If betting has closed** while they were choosing: reject the confirmation, and no money is taken.
6. **Countdown:** **5 minutes** by default; suggest letting admins set 2–10 minutes. At **1 minute left**, post one "Races start in 60 seconds!" message.
7. **At 0:00:** close betting by disabling the Join button. Then fix the payout mode (house line if solo, otherwise pools), run the stages (§1.4), pay out (§1.6), apply the carryover (§1.8) and update the horses' stats.
8. **Cooldown:** the starter gets a **1-hour** cooldown on *starting* races; suggest letting admins change it. **The cooldown only starts when the race actually runs.**
   - **No cooldown** if the starter cancels or the race never runs (refund, crash or disabled).
   - The starter can always join other players' races during their cooldown.
9. **Cancelling:**
   - **The starter cancels:** they can cancel their bet, and with it the race, **only while they're still the only bettor**. They get a full refund and no cooldown.
   - **Others have joined:** the race goes ahead.
   - **Admins** get a command to cancel the active race (§2).

### 1.10 The countdown has to run as a background task
- **The timer:** run the countdown and the race as an `asyncio.Task` owned by the cog, not as a button view's timeout.
- **Where the task lives:** keep the tasks in a dict on the cog, `{guild_id: task}`.
- **On cog unload:** cancel them, and refund (§2).

---

## 2. Money safety: restarts, reloads and errors

Players' money stays in limbo for more than 5 minutes, so this is the most important part to get right.

- **Persist the active race in the database** on `GuildSettings` (for example `active_race: HorseRace | None`). Save it on creation and after every confirmed bet, using `cog.save()`.
  - **What it holds:** the horse IDs in the field, the announcement message ID and channel ID, the start timestamp, the starter's ID, the carryover snapshot, and a bets list.
  - **Each bet:** `user_id`, `type`, `horse_id`, `amount`, and `currency_amount`, the amount actually taken in bank mode.
- **On cog load (`_init`):** if any server has an `active_race`, **refund every bet**, clear it, save, and post "The race was cancelled by a bot restart; all bets were refunded." in the race channel if possible. Don't start a cooldown.
- **On cog unload (`cog_unload`):**
  - Cancel the race tasks and refund the open bets before `_final_save`.
  - A refund that fails, for example because of a bank error, must be logged and the race **kept** in the database, so the next load retries it.
- **A race that's already paying out:** mark the race `phase = "paying"` before paying. When loading, a race found in that phase must refund only the bets that **haven't been paid**. Track a `paid` flag on each bet, set right after its credit succeeds, and save after each credit.
- **Admin cancel:** `[p]hrcset race cancel` refunds and clears the active race.
- **Refund method:** credit back exactly what was taken, using `credit_balance`. Use the stored amount, and don't convert again in bank mode.
- **Data deletion:** `red_delete_data_for_user` must drop the user's open bet and refund nothing. `red_get_data_for_user` should include their horse-racing stats.

---

## 3. Settings and admin

### 3.1 New `GuildSettings` fields (`common/models.py`)
Every new field must have a default, so existing `db.json` files still load.
- `race_channel_id: int | None = None`. **Horse Racing stays unavailable until this is set.**
- `horserace_house_cut_pct: int = 10`
- `horserace_countdown_minutes: int = 5`
- `horserace_cooldown_minutes: int = 30`
- `horserace_house_line_return_pct: int = 80`, the average return on solo house-line races (§1.7).
- `horses: dict[str, Horse]`, keyed by a stable ID: `d01`–`d15` for the defaults and `c01`–`c10` for custom horses.
  - **The defaults are created lazily**, the first time racing is used or on load.
  - **Horse model:** `name`, `custom: bool`, `speed`, `stamina`, `turning`, `start` (floats, starting at 0), `races`, `wins`, `places`, `last5: list[int]`, `streak: int`.
- **Carryover:** `race_carryover: dict[str, int]` (`{"win": 0, "place": 0}`) and `race_carry_count: dict[str, int]`.
- `active_race: HorseRace | None = None`. See §2.
- **Add `"horserace": False` to `games_enabled`.** It's off by default, like the other games.

### 3.2 New `User` fields
- `last_race_start: str | None`, an ISO UTC time, matching how `last_scratch_date` is stored.
- **Racing stats:** races bet, Win bets cashed, Place bets cashed, and the best single-race profit. The rest can come from the generic `game_*` dicts via `record_win` / `record_loss` with the slug `horserace`.
- **Title counters:** whatever the titles in §5 need, for example `race_win_streak` and `races_started_with_3_bettors`.

### 3.3 Setup wizard
- **Add a race-channel step.** It's either a new page or part of the channel page (`_Page12ChannelLock`). Use a single text-channel select, and include a "clear" option.
- **Add `horserace` to the game toggles page** (`_Page11GameToggles`).
- **Bet limits:** add the two `horserace_*` slugs to the bet-limits page.
- **New "Horse Racing" page:** house cut (0–25%), countdown minutes, cooldown minutes and the house-line return (50–95%). Use modals like `_BetLimitsModal`, and validate the ranges.
- **Write only changed fields** (see `_WizardState.apply`).

### 3.4 Admin commands (under `hrcset`)
- `race channel <#channel|clear>`
- `race cut <0-25>`, `race countdown <2-10>`, `race cooldown <minutes>`, `race houseline <50-95>`
- `race horses`: list every horse with its stats and record.
- `race addhorse <name>`, `race renamehorse <id|name> <new name>`, `race removehorse <id|name>`. These work on custom slots only, with a maximum of 10.
- **Horse name rules:** 2–20 characters, unique ignoring case, no `@`, `<`, `>` or backticks, and must not start with a markdown character. Strip spaces from the ends.
- **Removing a horse:** blocked while that horse is in the active race.
- `race resetstats [all|<horse>]`, with a confirmation view like `_ResetConfirmView`.
- `race cancel`: refund and clear the active race.
- **Check `reset` / `wipeplayers` against the active race:**
  - `reset` resets settings in place, so it must not orphan an active race. Refund the race first, or block `reset` while one is running. The refund is simplest.
  - `wipeplayers` clears users. Refund the bets first, or block the wipe.

---

## 4. Views

### 4.1 `views/horse_racing_view.py`: `HorseRacingView(interaction, conf, user, cog)`
- **Registering it:**
  - Add it to `_GAME_MODULE`, `_GAME_DISPLAY` and `GAME_SLUGS`, and give it a Game Room button.
  - Add `horserace` to the `_GAME_HELP` entry, and to `views/__init__.py`.
- **Required pieces:** `interaction_check` (using `not_your_session`), `on_timeout` (using `expire_view`), `_build_embed`, `_show_info` and `_back_to_floor`, plus a `_check_access` that calls `session_expired` first.
- **Access checks:**
  - The race channel is set.
  - `games_enabled["horserace"]`.
  - The allowed-channel check: the private screen opens wherever the club opens, but the announcement always goes to the race channel.
  - Not blacklisted.
- **Opening screen:** the "Start a Race?" or "Race in progress" state, as in §1.9. Show the starter cooldown if one is running (the `time_until_ready`-style helper in `games/scratch_card.py` is a good model).
- **Betting steps:** use a `discord.ui.Select` for the bet type (2 options) and for the horse (10 options; the description line holds the stats and the last 5 finishes), then an amount modal, then confirmation.
- **Before you take the money:** call `session_expired` and run `validate_bet(conf, user, slug, amount, balance)` before `deduct_balance`.

### 4.2 The public race UI (the race channel)
- **Announcement view:** a Join button, with the view timeout longer than the countdown. Pressing it opens the same betting steps, sent privately.
- **The race's message ID is stored**, so that if the message is deleted, the race still runs and the results are posted as a new message.
- **Handling errors:** use `discord.HTTPException` when posting to and editing the race channel. If the channel is gone or the bot lacks permission: refund, clear the race, and tell the starter privately if possible.
- **Permissions:** the race channel needs Send Messages and Embed Links. Those are already listed in `info.json`.

### 4.3 Text shown to players
- **How to Play** must cover:
  - Win vs Place, saying that Place pays on **1st or 2nd**.
  - How the pools, house cut and carryover work, the 5-race carryover limit, and that a solo race pays fixed house-line odds (shown in the picker) instead of the pool.
  - One bet per race, and the rotation rule.
  - That stats change after every race.
  - That no bonuses apply.
  - The starter cooldown, and that cancelling costs no cooldown.
- **Every amount on screen comes from the live settings,** never hard-coded.
- **Mobile:** keep embeds readable on a phone, as the owner prefers. Keep the text track display narrow, about 30 characters.

---

## 5. Specialty titles

Add them to `SPECIALTY_TITLES` in `common/constants.py` and to `evaluate_specialty_titles` in `commands/helper_functions.py`, with threshold constants next to the existing ones. The owner confirmed all seven on 2026-10-10.

| Slug | Title | Condition |
|---|---|---|
| `railbird` | 🏇 Railbird | Bet on 25 races. |
| `longshot` | 🎯 Longshot | Win a Win bet that returned 10× the stake or more. |
| `big_payday` | 💰 Big Payday | Profit of 5,000 or more from a single race. |
| `steady_eddie` | 🥈 Steady Eddie | Cash 10 Place bets. |
| `hot_streak` | 🔥 Hot Streak | Win Win bets in 3 races in a row. |
| `race_promoter` | 🎪 Race Promoter | Start 15 races that had at least 3 bettors. |
| `called_it` | 🏆 Called It | Win a Win bet as the only player who backed the winner. |

Records and badges for the horses themselves (show these on a "🐎 Stable" screen reachable from the racing view):
- **Career record:** races, wins, places and the last 5 finishes.
- **Champion of the Stable:** the horse with the most wins.
- **Triple Crown:** a horse that wins 3 races in a row gets an announcement in the race-results message.

---

## 6. Stats, leaderboards and docs

- **Recording results:** each settled bet calls `record_win(conf, user, "horserace", payout, stake)` or `record_loss(conf, user, "horserace", stake)`, then the usual rank and title checks.
  - `record_win` records profit (payout minus stake).
  - `record_loss` uses up the Multiplier Wheel only for `MULTIPLIER_ELIGIBLE_GAMES`, so don't add `horserace` there.
- **Refunds** call neither `record_win` nor `record_loss`.
- **Leaderboards:** add `horserace` to the per-game leaderboard. Check how `game_total_payout` and the other per-game keys are listed in `commands/user_commands.py` (around the `("💰 Total Winnings", ...)` table).
- **README:** a game section, the commands, and a line in the balance table. Expected return per bet is about 1 − house cut. Solo races return the house-line setting (80% by default).
- **`HRC-needs-work.md`:** add a status line when it's done.

---

## 7. Testing checklist

**Pure logic, in scratchpad scripts:**
- **Rotation:** no horse ever runs 4 races in a row, and the fallback works when horses are removed.
- **Stat balance:** 1,000+ simulated races, against the targets in §1.3.
- **Pool maths:**
  - Solo races, for Win and for Place.
  - Nobody backed the winner (carryover).
  - The 6th stack (the house keeps it).
  - Everyone on one horse (the minimum is the stake back).
  - Place with only one of the top two backed.
  - Rounding.
  - The house cut set to 0% and to 25%.
- **Expected value:** the return to the player is below 100% for every bet size, including solo races with the min bet. Check house-line odds for every horse at 50%, 80% and 95% (§1.7).

**Money safety:**
- Simulate a reload during the countdown and during payout. Every bet must be refunded or paid exactly once.

**Live, on a test server:**
- Two accounts starting a race at the same moment.
- A join after betting closes.
- Running out of balance between picking a horse and confirming.
- The announcement message being deleted.
- The race channel being deleted.
- Bank mode and chip mode.
- How the race message and the countdown timestamp look on mobile.
