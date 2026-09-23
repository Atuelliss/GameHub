# Petcord Currency Conversion - Design Discussion

_Updated 2026-09-23. This replaces the earlier medal-conversion draft: the proposal is now to convert **petcoin**, not medals, into the server's Discord currency._

---

## 1. Why petcoin is a better fit than medals

| | Converting medals | Converting petcoin |
|---|---|---|
| New data needed | A separate count of unconverted medals per tier, plus migration | **None.** `current_petcoin` is already the spendable balance |
| Leaderboard / achievements | Must be protected from conversion | Unaffected. Medal counters are never touched |
| Reflects effort | Tier only (gold, silver, bronze) | Medal tier **and** growth days **and** species lifespan |
| Existing settings | New ones needed | `petcoin_conversion_enabled` and `petcoin_conversion_rate` already exist on the server settings |
| Existing players | Must decide how to handle past medals | Their current balance is already there. Admins can adjust it with `[p]pcset setpcoin` |

Petcoin is already the reward for raising a pet well, so converting it rewards the same thing medals measure without touching the rankings.

---

## 2. How petcoin is earned today (after the latest fixes)

### Graduation (the main source)
```
petcoin = ((growth days × 2) + medal base) × lifespan multiplier
```
- **Medal base:** gold 50, silver 20, bronze 5. No medal pays **0**.
- **Growth days** are capped at the species' adult age, so delaying graduation no longer pays more.
- **Lifespan multiplier:** short 1.0×, medium 1.5×, long 2.0×, extended 2.5×.
- Medal scoring now stops when the pet reaches adulthood, so "Keep Growing" can't change the medal either.

Example payouts:

| Lifespan (adult at day) | 🥇 Gold | 🥈 Silver | 🥉 Bronze |
|---|---|---|---|
| Short (5) | 60 | 30 | 15 |
| Medium (10) | 105 | 60 | 37 |
| Long (21) | 184 | 124 | 94 |
| Extended (30) | 275 | 200 | 162 |

**Worth deciding:** because of the day bonus and the multiplier, lifespan affects the payout more than the medal. An extended-lifespan **bronze** pays more than a short-lifespan **gold**. Is that intended?
- Longer pets do take much more real time: 30 pet days versus 5, and one pet day is `growth_day_length_hours` real hours.
- If medal quality should matter more, raise the medal bases, for example gold 150, silver 60, bronze 15.
- Or apply the multiplier to the medal base only.

### Other sources
- **Daily freebie:** a duplicate item pays its petcoin value. This is a daily source of petcoin that doesn't depend on caring for a pet.
- **Admin grants:** `[p]pcset setpcoin`.

### Where petcoin is spent (the things it's used up on)
The treats, vitamins, clothing and ambrosia shops. Conversion competes with these. That's healthy: players choose between in-game perks and server currency.

---

## 3. Settings

The server settings model (`GuildSettings`) already has:
```python
petcoin_conversion_enabled: bool = False
petcoin_conversion_rate: int = 10   # petcoin per 1 server currency
```
These settings are for petcoin → server currency only. Petcoin does not convert to Legendarycoin; Legendarycoin is earned only through graduations (1 per 5) and admin grants.

**Proposed settings** (replacing the single integer with an X → Y ratio):
```python
petcoin_conversion_enabled: bool = False
petcoin_conversion_petcoin: int = 10      # X petcoin ...
petcoin_conversion_currency: int = 1      # ... = Y server currency
petcoin_conversion_minimum: int = 10      # smallest amount allowed per conversion
petcoin_conversion_daily_cap: int = 0     # max server currency per user per day (0 = none)
petcoin_conversion_cooldown_hours: int = 0
```
- A ratio covers both "10 petcoin = 1 credit" and "1 petcoin = 25 credits" without fractions.
- **Migration:** existing servers keep their current `petcoin_conversion_rate` as `X`, with `Y = 1`.

**Admin commands** (in the style of the existing `pcset` commands):
```
[p]pcset convert toggle
[p]pcset convert rate <petcoin> <currency>     # e.g. rate 10 1
[p]pcset convert minimum <petcoin>
[p]pcset convert dailycap <currency|0>
[p]pcset convert cooldown <hours|0>
```
`[p]pcset display` should show:
- the rate and the currency name (`bank.get_currency_name`);
- the value of a typical payout, for example "a medium gold graduate ≈ 10 credits", so admins can judge the economy impact.

---

## 4. Player flow

- Add a **"💱 Convert"** button on the Stats view or the Home supply shop, shown only when conversion is enabled. Optionally also add `[p]pcconvert <amount|all>`.
- It opens a view with:
  - the balance and the rate;
  - preset amounts (25%, 50%, all) plus a "custom amount" modal;
  - a live preview: "200 petcoin → **20 credits**";
  - Confirm and Cancel buttons.

**On Confirm, in order:**
1. Check again that conversion is enabled, that the cooldown has passed, and that the daily cap isn't exceeded.
2. Check the balance again. It may have changed in a shop since the view opened.
3. Round down to whole batches of X: convert `floor(amount / X) × X` petcoin and leave the remainder in the balance.
4. Deposit with `await bank.deposit_credits(member, currency)`. If Red raises `BalanceTooHigh`, either convert only the amount that fits, or refuse and show the maximum.
5. **Only after the deposit succeeds**, subtract the petcoin, record the lifetime stats, and call `schedule_save()`.
6. Show a receipt: "Converted 200 petcoin → 20 credits. Remaining: 37 petcoin."

**Safety:**
- **Per-user lock:** use an `asyncio.Lock` per user id around steps 1–5, so a double-click or two open views can't convert twice.
- **Stale-view guard:** use the `parent_view.is_finished()` check added earlier, so the confirm view never redraws a menu the player has left.
- **Global bank:** if Red's bank is global, one server's toggle and rate affect a balance shared across every server. Allow conversion only with a per-server bank, or show a warning in `display`.

**New fields on the player data model (`User`):**
```python
total_petcoin_converted: int = 0
total_currency_from_petcoin: int = 0
last_petcoin_conversion: float = 0.0
petcoin_converted_today: int = 0       # for the daily cap
petcoin_conversion_day: str = ""       # "YYYY-MM-DD" in the server timezone
```

---

## 5. Abuse and economy considerations

| Risk | Mitigation |
|---|---|
| The daily freebie adds petcoin without any pet care | Option A: leave it (the amounts are small). Option B: track the freebie petcoin as a separate, non-convertible balance, so only graduation petcoin converts. |
| Admin `setpcoin` becomes a way to print server currency | That's admin-only anyway, but log each grant (who gave how much to whom) now that petcoin has real value. |
| Choosing long-lived species to farm payouts | They take far longer in real time. Tune the multipliers if needed (see the question in section 2). |
| Alt accounts raising pets and gifting them | Gifting Home pets moves the pet, not the petcoin, and petcoin comes from graduation. So there's no direct exploit. |
| The rate is too generous at launch | Start conversion **disabled** by default (it already is) and pick a low rate. Raising a rate later is easier than lowering it. |
| Rate changes while a player has the convert view open | Recalculate at Confirm and show the rate on the confirm screen. |

---

## 6. Optional extras

- **Reverse conversion** (server currency → petcoin): lets players buy shop items with server money. It's a separate toggle, usually at a worse rate so it can't be abused.
- **Streak bonus:** a small conversion bonus while `current_medal_streak >= N` rewards consistent gold medals without changing the medal system.
- **Conversion history:** show the last few conversions in `[p]pcset display <user>` for admin auditing.
- **Tunable payouts:** move `MEDAL_PETCOIN_VALUES` and `LIFESPAN_PETCOIN_MULTIPLIERS` into the server settings, the same way the medal thresholds were, so each server can tune its economy.

---

## 7. Suggested implementation order

1. Add the ratio, minimum, cap and cooldown settings, with a migration from the old single rate.
2. Add the `pcset convert` admin commands and the `display` output.
3. Build the Convert view and confirm flow with bank deposits, the per-user lock and the receipt.
4. Add the player stats fields and show them on the Stats page.
5. (Optional) Freebie petcoin split, grant logging, reverse conversion and tunable payouts.
