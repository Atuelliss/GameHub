# 🎰 The High Roller Club

A Vegas-style casino for Red-DiscordBot. Players walk into the club lobby, head to the Game Floor, and play 15 casino games, earning prestige, ranks and titles as they go. Admins control which games are open, the bet limits, the odds and more.

Everything runs from one menu message using buttons, sized to read cleanly on desktop and mobile Discord.

## Getting started

Run `[p]highrollerclub` (or `[p]hrc`) to enter the club. New players in chip mode get a starting stack of chips. From the lobby:
- **🎲 Game Room:** pick a game, visit the **Teller Window** to buy or cash out chips, or claim a **Scratch Card** (if enabled).
- **📊 Your Stats:** your record, rank and titles. Equip titles here.
- **🏆 Leaderboards:** top players per game.
- **❓ Help & Info:** how the club works, plus the rules for every game.

Admins: run `[p]highrollerclubset setup` first to set the club up with a step-by-step wizard.

## Games

- **Card games:** Blackjack, War, Hi-Lo, Video Poker, **Club Poker** (private two-player 5-card draw, one player against another), and **Texas Hold'em** (tables for 2–6 players). See below.
- **Table & wheel games:** Roulette, Big Six Wheel, Keno, and Slots.
- **Risk games:** **All-In** (pick a risk tier) and **Double** (roll to double your pot, then cash out or risk it again).
- **Bonus wheels:** the **Mystery Wheel** (free daily spin) and the **Multiplier Wheel** (pay to boost your next win).
- **Horse Racing:** a multiplayer race in its own channel. See below.

Every game has a How to Play screen in the menu, and admins can turn any game on or off.

## Features

- **Two payment modes:**
  - **House Chips:** players buy chips at the Teller Window with server currency. Cashing chips back out is optional and admin-controlled.
  - **Server Currency:** games use the player's bank balance directly.
- **Ranks & prestige:** win to earn prestige, lose to drop it. The ranks are Member → Regular → High Roller → The Whale. Higher ranks can unlock bigger bets (bet multipliers are optional).
- **Specialty titles:** earned for milestones like big payouts, long win streaks and lots of wins in a game.
- **Bonus tokens:** a Bonus Bet token doubles the winnings of your next eligible game (used up win or lose), and a Free Spin token gives a free Slots pull.
- **Scratch Cards:** a free card every cooldown period (default 24 hours). Scratch the panels to reveal a random reward from the server's prize pool.
- **Mystery Wheel:** a free daily spin that resets at midnight in the server's timezone.
- **Multiplier Wheel:** pay to spin for a multiplier that boosts the profit of your next eligible game (used up win or lose, bonus capped at twice the spin cost).
- **Admin control:** bet limits per game, per-game odds (RNG settings), rank thresholds, channel restrictions, and a player blacklist.

## Horse Racing

- **Starting a race:** a player opens Horse Racing from the Game Room. Ten horses are drawn from the stable, and the player starts the race with one bet: **Win** (the horse finishes 1st) or **Place** (1st or 2nd).
- **Joining:** the race is announced in the server's race channel with a live countdown (5 minutes by default). Other players press **Join the Race** to place their own bet: one bet per player per race. A "60 seconds" warning is posted before the gates open.
- **The race:** it runs in six stages (gate break, turns, straights and the finish) on one message that updates every 5 seconds, then the results are posted and winners are pinged.
- **Payouts:**
  - **Pools:** Win and Place bets go into separate pools, shown on the announcement. The house takes a cut of new bets (10% by default), and the winning tickets share the rest in proportion to their bets. The Place pool is split in half between the backers of the 1st and 2nd horses. A winning ticket always gets at least its bet back.
  - **Carryover:** a pool nobody wins carries over to the next race, for up to 5 races. After that, the house keeps it.
  - **Solo races:** if nobody joins, the starter's bet pays fixed **house-line** odds instead. They're shown in the horse picker and worked out exactly from each horse's chances, returning 80% by default. Near-certain bets show "no odds".
- **The horses:** 15 default horses, plus up to 10 the server adds. Every horse has Speed, Stamina, Turning and Gate stats that start at 0 and change after every race. A horse never runs more than 3 races in a row. The **Stable** screen shows each horse's record and form, and the horse with the most wins is Champion of the Stable. A horse that wins 3 in a row takes the **Triple Crown**.
- **Rules:**
  - The starter waits 30 minutes (by default) before starting another race, but can join other races any time. There's no wait if the race is cancelled.
  - **Race notifications:** players press **🔔 Enable Race Notifications** on the Horse Racing screen to be pinged in the race channel when a race opens for betting (not for races they start). The button turns red (**🔕 Disable Race Notifications**) to turn it off.
  - The starter can cancel while they're the only bettor.
  - No bonuses apply to racing.
  - If the bot restarts mid-race, every bet is refunded.
- **Titles:** Railbird, Longshot, Big Payday, Steady Eddie, Hot Streak, Race Promoter and Called It.

## Texas Hold'em

- **Tables:** a player opens a table from the Game Room at a blind level their rank allows, picks 2–6 seats, and buys in. The table is posted in the channel, and other players press **Join** to buy in. Anyone can join a table they can afford. One table per channel, and one seat per player.
- **Blind levels (defaults):** 100/200 and 200/500 for everyone, 500/750 from Regular, 750/1,000 from High Roller, and 1,000/1,500 for The Whale. When rank bet multipliers are off, only the levels open to Members can be opened. Admins can edit, switch off or re-rank levels on the Hold'em page of `hrcset setup`.
- **Buy-ins:** 20 to 100 big blinds by default (admin-adjustable). Players top up between hands and cash out by pressing **Leave**.
- **Play:** standard No-Limit Hold'em. The host presses **Deal** for each hand, and **My Seat** opens a player's private cards and betting buttons (Fold, Check, Call, quick raises, Custom, All-In). Side pots and split pots are handled, and the dealer button moves every hand.
- **Timer:** 60 seconds to act by default. On timeout a player checks if they can, otherwise folds. Timing out in 2 hands in a row sits a player out until they press **Sit Out / I'm Back**.
- **Showdown:** winning hands are shown. Losing hands get 15 seconds to show or muck. All-in run-outs are always face up.
- **Rules:**
  - Only hands with 3 or more players change prestige and count toward the Hold'em titles, so two players can't trade wins to climb ranks.
  - No bonuses apply: no Lucky Streak, Bonus Bet Token or Multiplier Wheel. The house takes nothing.
  - Leaving during a hand folds it; the player is cashed out when it ends. A player who runs out of chips leaves the table and can join again.
  - A table with no hand dealt for 10 minutes closes. Closing a table, or a bot restart, returns every stack (a hand in progress is cancelled).
- **Titles:** Grinder, Bluff Master, River Rat, Shove Survivor, Monster Pot, Royal Treatment, Bad Beat and Table Captain.

## Game balance

Every game pays back less than it takes in on average, so the house always keeps an edge and no strategy can grow money forever. Return to player at default settings:

| Game | Return | Notes |
|---|---|---|
| Video Poker | ~99.5% | Only with perfect strategy; real players get less. |
| War | ~97% | |
| Hi-Lo | 97% per guess | Each guess pays its odds less 3%, so longer chains return less. |
| Blackjack | ~99% | Dealer hits soft 17; blackjack pays 3:2. |
| Roulette | 94.7% | American wheel; admins can pick European (97.3%) or triple-zero. |
| Double | 94% per roll | |
| Keno | 89–92% | Depending on how many spots you pick. |
| Slots | 90% | Admin setting `house_edge_pct` is the real edge (2–40%). |
| All-In | 88–91% | Each tier; admin win chances are capped below 100% return. |
| Big Six | 76–87% | Depending on the segment. |
| Club Poker | 100% | Player vs player; the house takes nothing. |
| Texas Hold'em | 100% | Player vs player; the house takes nothing. |
| Horse Racing | ~90% (pools), 80% (solo) | The pools return everything but the house cut (10% default, 0–25%). Solo races pay the house line (default 80%, 50–95%). |

Bonuses (Lucky Streak, Bonus Bet Token, Multiplier Wheel) are paid on winnings, never on your returned stake.

## Commands

### Player commands
| Command | Description |
|---|---|
| `[p]highrollerclub` | Enter the club. Alias: `hrc`. Everything else is buttons. |

### Admin commands
Require Manage Server, Red admin, or bot owner. The group alias is `hrcset`.

| Command | Description |
|---|---|
| `[p]hrcset setup` | Interactive multi-page setup wizard. |
| `[p]hrcset status` | Show the current settings. |
| `[p]hrcset set paymentmode <chips\|bank>` | Choose house chips or server currency. |
| `[p]hrcset set conversion <enable\|disable>` | Allow cashing chips back into server currency. |
| `[p]hrcset set conversionrate <amount>` | Chips per 1 unit of server currency. |
| `[p]hrcset set betlimits <game> <min> <max>` | Set a game's minimum and maximum bet. |
| `[p]hrcset set game list \| enable <game> \| disable <game>` | See and toggle games. |
| `[p]hrcset set rng <game> <param> <value>` | Tune a game's odds (Slots, All-In, Roulette, Double, Multiplier Wheel). Limits keep every game below 100% return. |
| `[p]hrcset set rankmultipliers <enable\|disable>` | Turn rank bet multipliers on or off. |
| `[p]hrcset set multiplier <rank> <value>` | Bet multiplier for ranks 2–4 (1.0–10.0). Member is always 1.0×. |
| `[p]hrcset set rankthreshold <rank> <amount>` | Prestige needed for ranks 2–4 (must climb: Regular < High Roller < Whale). |
| `[p]hrcset set prestigewin <points>` / `prestigeloss <points>` | Prestige gained per win and lost per loss. |
| `[p]hrcset set allintier <tier>` | Highest All-In risk tier players can use (1–5). |
| `[p]hrcset set housesegments <count>` | House segments on the Big Six Wheel (0, 2, 4 or 6; default 2). |
| `[p]hrcset set scratch <enable\|disable>` / `scratchcooldown <hours>` | Scratch Cards on/off and their cooldown. |
| `[p]hrcset set mysteryspin <enable\|disable>` / `timezone <tz>` | Mystery Wheel on/off and its reset timezone. |
| `[p]hrcset set wheelcost <amount>` | Cost of a Multiplier Wheel spin. |
| `[p]hrcset set channel add <channel> \| clear` | Restrict the club to certain channels. Staff (the server owner, Manage Server, Red's admin role, or the bot owner) can still use it in any channel. |
| `[p]hrcset set blacklist add <member> \| remove <member> \| list` | Block players from the club. |
| `[p]hrcset race channel [channel]` | Set the race channel (leave it out to clear it). Horse Racing stays closed until one is set. |
| `[p]hrcset race cut <0-25>` / `countdown <2-10>` / `cooldown <minutes>` / `houseline <50-95>` | House cut on the pools, betting countdown, starter cooldown, and solo-race return. |
| `[p]hrcset race horses` | List every horse with its id, stats and record. |
| `[p]hrcset race addhorse <name>` / `renamehorse <id> <name>` / `removehorse <id>` | Manage up to 10 custom horses. |
| `[p]hrcset race resetstats [all\|horse]` | Reset horse stats and records to 0 (asks to confirm). |
| `[p]hrcset race cancel` | Cancel the current race and refund every bet. |
| `[p]hrcset reset` | Reset all settings to defaults (asks to confirm). |
| `[p]hrcset wipeplayers` | Delete all player data for this server (asks to confirm). |
| `[p]hrcset backup …` | Back up and restore game data (bot owner only). See below. |

Game names for `<game>`: `slots`, `war`, `allin`, `blackjack`, `hilo`, `keno`, `roulette`, `videopoker`, `clubpoker`, `holdem`, `big6`, `double`, `mysteryspin`, `multiplierwheel`, `horserace`. For `betlimits`, Horse Racing uses `horserace_win` and `horserace_place` (defaults 10–1,500 and 10–750).

## Requirements

- Red-DiscordBot 3.5.3 or newer
- `pydantic` (installed automatically)
- Red's bank (used for buying chips and for server-currency mode)

## Data & backups

All game data is stored in `db.json` in this cog's Red data folder (`[p]datapath` shows where that is). It is written safely (to a temporary file first, then swapped in), so a crash mid-save can't corrupt it.

**Automatic protection**
- **Load guard:** if `db.json` can't be read when the cog loads (a corrupt file, or data that no longer matches the models after an update), saving is switched off for that session so the file is never overwritten. Game commands reply that the data failed to load, and the error is in the bot's log.
- **Startup wait:** until the file has finished loading, game commands reply "Still loading game data" instead of running on an empty database.
- **No lost saves:** a save requested while another is in progress runs straight after it, and the cog saves once more when it's unloaded or the bot shuts down.
- **Rotating backups:** up to 3 copies in `backups/db_<time>.json`, taken at most every 8 hours as the game saves.
- **Start-of-session copy:** `db.json.backup`, the file as it was when the cog last loaded successfully.

**Backup commands (bot owner only)**
| Command | What it does |
|---|---|
| `[p]highrollerclubset backup list` | List all backups, newest first, numbered from 1. |
| `[p]highrollerclubset backup restore [number]` | Restore a backup (default 1 = newest). The backup is checked to make sure it loads first, and the replaced file is kept as `db.json.pre-restore`. |
| `[p]highrollerclubset backup create` | Save now and take a manual backup (`backups/manual_<time>.json`). Manual backups are never deleted automatically. |

These commands still work when the data failed to load.

**Recovering from "data failed to load"**
1. Check the bot's log for the error. If it's a model/validation error after a code change, fixing the code and reloading may be all that's needed.
2. Otherwise, run `[p]highrollerclubset backup list` and pick a backup.
3. Run `[p]highrollerclubset backup restore <number>`.
4. Reload the cog: `[p]reload highrollerclub`. Saving stays paused after a restore until you do.
