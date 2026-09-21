# High Roller Club — Concept Document

## Overview

**Cog Name:** `HighRollerClub` or `TheVaultHRC`

*An ultra-exclusive members-only Vegas casino with a tiered prestige system.*

**Gimmick:** Players accumulate **Prestige Points** alongside winnings. Enough prestige unlocks higher bet limits and cosmetic titles (Member → Regular → High Roller → The Whale). Currency is **House Chips**.

This concept is the most scalable — as you add games over time, each one slots naturally into the club's identity without needing a theme overhaul. The tiered rank system gives a built-in progression framework. Each game already has a conceptual home within the club — the high-stakes blackjack table, the private poker room, the main floor slots — making naming and flavor text intuitive for players without requiring explanation.

**House Chips** work universally regardless of what the server owner names their RedBot bank currency. In chip mode, players exchange server currency for House Chips at the front desk (configurable rate set by the server owner). In currency mode, bets are placed directly against the server bank — the prestige system still functions identically either way, since Prestige Points are tracked separately from balance.

**Palette:** Black, champagne gold, white — `0xD4AF37`, `0x0D0D0D`

---

## Rank System

All games are available to **everyone from day one**. Ranks are earned through performance, not time-gating. There are **4 main ranks** that increase betting limits, plus **specialty titles** that are cosmetic and reflect what a player is known for.

### The 4 Main Ranks (Betting Limit Multipliers)

| Rank | Title | How Earned | Bet Limit Multiplier |
|---|---|---|---|
| 1 | **Member** | Default — everyone starts here | 1x (base limits) |
| 2 | **Regular** | Accumulate wins or total payout earned | 1.5x (configurable) |
| 3 | **High Roller** | Significant wins or large single-game payouts | 2x (configurable) |
| 4 | **The Whale** | Elite-level cumulative performance | 3x (configurable) |

Server owners set the multiplier values and the thresholds (e.g., how many total wins or how much total payout earned to reach each rank). Tracking is done via a per-member `Config` entry storing wins, total payout earned, and current rank.

---

### Specialty Titles (Cosmetic)

These sit alongside the main rank and reflect a player's game history. Only one displays at a time; the player can toggle which one shows. They appear in the embed footer or next to the player's name in game results.

> *🃏 **Card Shark** | High Roller | Balance: 4,800 chips*

| Title | Earned By |
|---|---|
| **Card Shark** | High win rate across Blackjack, Video Poker, and Hi-Lo combined |
| **Lucky Star** | High number of Slots or Keno wins |
| **Daredevil** | Winning on Reckless tier or higher in All-In multiple times |
| **The Closer** | Winning a large Blackjack hand at max bet |
| **Numbers Man** | High Keno wins or consistent Roulette number picks that hit |

---

## Games

All games are played in embed views with button-driven actions.

### Slots — *"The Main Floor"*
- Open to all Members
- Entry-level game, fully instant (no interaction after bet)

### War — *"The Entry Table"* (Solo or 2-Player)
- Open to all Members
- Simplest card game, good for new Members
- **Solo mode:** Player's card vs. dealer's card — highest wins
- **2-Player mode:** Player challenges another player with `!war @player <bet>`
  - Both players must bet the same amount; both bets form the pot
  - Challenged player accepts via button — both balances validated at acceptance, not at challenge time
  - Both cards are flipped simultaneously in a single embed reveal
  - Highest card wins the full pot
  - **On a tie:** Both players get their bet back, or optionally trigger sudden death — a second flip for double-or-nothing (configurable by server owner)

### All-In — *"The High Stakes Toss"*
- Open to all Members
- All-or-nothing bet with player-selected **Risk Tier**
- Player selects tier via buttons before the flip resolves
- Flavor text escalates with risk: *"Standard? A sensible choice."* vs *"Suicidal? The Club holds its breath."*
- Server owner can optionally cap which tiers are available

**Risk Tiers:**

| Risk Tier | Name | Win Chance | Payout |
|---|---|---|---|
| 1 | **Standard** | 50% | 2x |
| 2 | **Bold** | 33% | 3x |
| 3 | **Reckless** | 25% | 4x |
| 4 | **Desperate** | 15% | 6x |
| 5 | **Suicidal** | 10% | 9x |

### Blackjack — *"The 21 Lounge"*
- Two-phase interaction: deal → hit/stand → resolve
- Standard blackjack rules (dealer hits on soft 16)

### Hi-Lo — *"The Prediction Parlor"*
- Press-your-luck chain mechanic
- Dealer reveals a card, player guesses higher or lower each round
- Can chain multiple correct guesses with escalating multipliers

### Keno — *"The Numbers Room"*
- Player picks numbers from a pool, draws happen, payout scales with matches
- Low interaction cost, naturally async-friendly

### Roulette — *"The Grand Wheel"*
- Highest variety of bet types (color, number, odd/even, etc.)
- One spin resolves everything — no multi-turn interaction needed
- Bet types range from near-even (2:1) to long-shot (35:1)

### Video Poker — *"The Private Card Room"*
- Most skill-involved game (Jacks or Better style)
- Two-phase: deal 5 cards → player holds/discards → draw replacements → payout
- Wins based on poker hand rank

### Club Poker — *"The High Table"* (2–4 Players)
- Multiplayer game where players compete against **each other**, not the house
- Each player posts a flat buy-in bet to enter; all bets form the pot
- Hands are dealt via **DM or ephemeral message** so cards remain hidden from other players
- Single betting round — each player chooses Raise / Call / Fold via buttons, with a per-turn timeout (e.g., 60 seconds auto-fold on idle)
- After all players have acted, hands are revealed and the best poker hand wins the full pot
- No multi-street betting — eliminates most complexity while preserving the core feel
- **Join window:** Game starter opens the table; up to 3 others have 60 seconds to join via button before cards are dealt
- **Planned feature** — recommended as a post-launch addition due to hidden-hand architecture requirements

---

## Scratch Cards — Server Perk (Toggleable)

Scratch Cards are **not a purchasable game**. They are a **toggleable passive reward** the server owner enables (disabled by default). When enabled, players use a command (e.g., `!scratch`) on a configurable cooldown (daily, every 12h, etc.) to reveal a scratch ticket.

### Reward Pool Options (Server Owner Configures)

| Option | Description | Notes |
|---|---|---|
| **House Chips** | A small flat or random chip amount | Simple, keeps economy tight |
| **Bonus Bet Token** | A one-time-use token that doubles the payout on next win | Adds strategy — when to use it? |
| **Rank XP Bonus** | Extra progress toward next rank | Good for player investment |
| **Free Spin** | One free Slots play (no bet required) | Fun, low-impact |
| **Lucky Streak Buff** | Next X game wins pay +25% for a limited time | Adds excitement |
| **Mixed Loot Table** | Random roll across several of the above (weighted odds) | Most engaging, most complex to balance |

A mixed loot table with weighted odds is the strongest choice — most scratchers IRL have a variety of prizes.

---

## Flavor Text Tone

The club speaks to the player like staff addressing a valued guest — professional, slightly flattering, never over-the-top. The house doesn't gloat on losses; it commiserates. It celebrates big wins with measured excitement.

| Moment | Flavor Text |
|---|---|
| Welcome / game start | *"Welcome back to The Club. The table is yours."* |
| Small win | *"A clean win. Well played."* |
| Big win | *"The room notices. A fine evening for you."* |
| Jackpot | *"Extraordinary. The Club will be talking about this one."* |
| Loss | *"The house holds this round. Your next visit awaits."* |
| Rank upgrade | *"Congratulations — your membership has been elevated."* |

---

## Admin Setup Flow (Server Owner)

At setup, the server owner configures:

1. **Payment mode** — House Chips (chip balance stored in `Config`) or direct RedBot bank currency
2. **Chip exchange rate** — e.g., 100 server coins = 1 House Chip (chip mode only)
3. **Rank thresholds** — how many wins or total payout earned required per rank
4. **Rank bet multipliers** — set 1x / 1.5x / 2x / 3x or custom values per rank
5. **Scratch Card toggle** — enable/disable, set cooldown duration
6. **Scratch Card reward pool** — choose which reward types are in the pool
7. **All-In tier cap** — optionally restrict the maximum risk tier available
8. **Base bet limits per game** — floor and ceiling per game before rank multipliers apply
9. **Channel lock** — optionally restrict games to a designated casino channel

### Server Owner Controls Summary

| Setting | Description |
|---|---|
| Rank multipliers | Set custom multiplier per rank |
| Rank thresholds | Set win count or payout totals required per rank |
| Scratch Card toggle | Enable/disable, set cooldown duration |
| Scratch Card reward pool | Choose which reward types are in the pool |
| All-In tier cap | Optionally restrict max risk tier available |
| Base bet limits per game | Floor and ceiling per game before multipliers apply |
| Channel lock | Optionally restrict games to a specific channel |
| Server timezone | Timezone string used for all calendar-day resets (e.g., `"America/New_York"`) |
| Mystery Wheel toggle | Enable/disable the daily free spin |
| Multiplier Wheel cost | Flat chip/currency cost to spin the Multiplier Wheel |

---

## Wheel Games

### Big Six Wheel — *"The Grand Wheel"*

A standalone casino game — one bet, one spin, one payout. Player selects a segment type to bet on via buttons, the wheel spins, and they win if it lands on their chosen segment. No player decisions after betting.

The wheel uses **House segments** — slots where every player loses their bet regardless of what they chose. This creates a baseline auto-loss chance before the player's selection even matters, giving the house a meaningful edge beyond just payout ratios.

**Default wheel layout (54 total segments):**

| Segment | Slots | Win Chance (if chosen) | Payout |
|---|---|---|---|
| **House** | 8 | — (automatic loss) | Lose bet |
| $1 | 18 | 33.3% | 1:1 |
| $2 | 12 | 22.2% | 2:1 |
| $5 | 7 | 13.0% | 5:1 |
| $10 | 5 | 9.3% | 10:1 |
| $20 | 3 | 5.6% | 20:1 |
| **Jackpot** | 1 | 1.9% | 40:1 |

The number of House segments is configurable by the server owner — 6 for a lighter house edge, up to 12 for a punishing wheel. Payout labels ($1, $2, etc.) are flavor names for the segment tiers, not literal currency amounts — the actual payout is the multiplier applied to the player's bet.

---

### Mystery Wheel — *"Daily Free Spin"* (Toggleable Server Perk)

A once-per-calendar-day free spin available to all players when enabled by the server owner (disabled by default). Players use a command (e.g., `!dailyspin`) to reveal a prize wheel with a variety of rewards. No bet required.

**Calendar-day reset:** The reset is based on the **server's configured timezone**, not UTC or a 24-hour countdown. The last spin date is stored as a date string per member. On each spin attempt, the current date in the server's timezone is compared to the stored date — if they match, the player is told when midnight resets their spin.

The setup command accepts a timezone string (e.g., `"America/New_York"`, `"Europe/London"`) validated against `zoneinfo`. Invalid strings are rejected with a helpful error listing common options.

**Reward Pool Options (Server Owner Configures):**

| Option | Description | Notes |
|---|---|---|
| **House Chips** | A small flat or random chip amount | Simple, keeps economy tight |
| **Bonus Bet Token** | One-time-use token that doubles payout on next win | Adds strategy — when to use it? |
| **Rank XP Bonus** | Extra progress toward next rank | Good for player investment |
| **Free Spin** | One free Slots play (no bet required) | Fun, low-impact |
| **Lucky Streak Buff** | Next X game wins pay +25% for a limited time | Adds excitement |
| **Mixed Loot Table** | Random roll across several of the above (weighted odds) | Most engaging, most complex to balance |

A mixed loot table with weighted odds is the strongest choice — most scratchers IRL have a variety of prizes.

---

### Multiplier Wheel — *"The Booster"*

A standalone paid spin that grants a **profit multiplier** applied to the player's next eligible game. Run before playing another game — not a button inside another game's UI.

**Flow:**
1. Player runs `!booster` (or similar), pays a flat fee, spins the Multiplier Wheel
2. Result is stored in `Config` per member as a **pending multiplier** (e.g., `2.0x`)
3. A **30-minute expiry timestamp** is stored alongside it
4. When the player plays an eligible game, the multiplier is applied to the **profit only**, then cleared

**Profit-only example:**
> Bet 100 chips, base win is 200 → profit is 100 → 2x multiplier → profit becomes 200 → total payout is **300**, not 400.

**Eligible games (Low/Mid tier only):**

| Tier | Games | Multiplier Eligible? |
|---|---|---|
| Low | Slots, War, All-In (Standard/Bold tiers only) | ✅ Yes |
| Mid | Blackjack, Hi-Lo, Keno | ✅ Yes |
| High | Roulette, Video Poker, All-In (Reckless tier and above) | ❌ No |

If the player plays a high-tier game while a pending multiplier exists, the multiplier is **not consumed** — it sits untouched until they play an eligible game or it expires.

**Full rules:**
- Multiplier applies to **profit only**, not total payout
- Expires **30 minutes** from spin time (stored as UTC timestamp)
- **Consumed on the next eligible game** win or loss — a loss burns the multiplier with nothing gained
- **One pending multiplier at a time** — spinning again while one is active shows a confirmation prompt:
  > *"You already have a {multiplier}x buff expiring in {X} minutes. Spinning again will overwrite it with no refund. Continue?"* — Yes / No buttons
- Overwriting discards the old multiplier immediately; no refund on either spin cost
