# DinoCollector Lure Rewrite Plan (Final)

## Goal
Move DinoCollector to a 3-tier lure system while safely preserving legacy user state.

Final behavior:
- Common Lure: spawns only common and uncommon creatures.
- Rare Lure: spawns only semi_rare and rare creatures.
- Super Lure: spawns only very_rare and super_rare creatures.
- Event creatures are never lure-spawnable.
- Legendary creatures are never lure-spawnable.
- A user may hold only one lure total at a time.
- Legacy lure ownership remains usable via dclure, but legacy lure can no longer be purchased.
- dclure must confirm use and clearly state which lure is being consumed.

## Final Decision Summary
1. No hard rename migration for price_lure or has_lure in phase 1.
2. Keep legacy fields for compatibility.
3. Add new field(s) for new lure system.
4. Disable all legacy lure purchases immediately.
5. Allow existing legacy lure owners to consume their lure once through dclure.
6. Legacy ownership transitions naturally to new model after use.
7. Enforce one-total-lure rule across both legacy and new lure ownership.
8. Exclude event and legendary from all lure outcomes.
9. Remove dcshop buy lure syntax; use only tiered buy syntax.
10. Enforce per-user concurrency guards to prevent double consume/refund races.
11. Treat lure cooldown as global across all lure tiers and communicate that everywhere.
12. Add lightweight structured diagnostics for lure operations.

## Topic 3 Final Decision - Command Compatibility Policy
1. Remove dcshop buy lure as a valid purchase command.
2. Supported lure purchase commands are only:
- dcshop buy common
- dcshop buy rare
- dcshop buy super
3. If users run dcshop buy lure, return a help/error message that points them to the 3 tier commands.
4. Legacy lure remains use-only through dclure and is never purchasable.

## Topic 4 Final Decision - Concurrency and State Safety Policy
1. Only one active lure operation is allowed per user at a time.
2. dclure must use a per-user in-progress guard (lock/set) from command start through completion.
3. If another dclure request arrives while one is active, reject it with a clear message.
4. Confirmation step must re-validate ownership and cooldown before consuming lure.
5. Consumption, cooldown set, usage counter increment, and save must happen in one ordered critical section.
6. Refund logic must restore exactly what was consumed by that operation only.
7. Duplicate confirm/click events after completion must be ignored safely.
8. Lock/guard cleanup must happen in finally blocks so failures do not leave users permanently blocked.

## Topic 5 Final Decision - Cooldown Clarity Policy
1. Lure cooldown is global per user and shared across all lure tiers.
2. Cooldown is not per-lure-type.
3. All user-facing lure surfaces must explicitly state the shared cooldown behavior.
4. Standard cooldown denial text must mention shared cooldown and remaining time.
5. This messaging must be consistent in dcshop, dclure confirmation/denial, dcstats, and dchelp.

## Topic 6 Final Decision - Telemetry and Diagnostics Policy
1. Add lightweight structured logging for lure operations only.
2. Use a consistent log tag prefix:
- LURE_OP
3. Include required fields in each lure operation log event:
- user_id
- guild_id
- lure_source (legacy/common/rare/super/none)
- operation_phase (start/confirm/consume/spawn/refund/end)
- cooldown_remaining
- allowed_rarities
- result (success/cancel/timeout/refund/error/rejected_in_progress)
4. Log guard behavior events:
- lock_acquired
- lock_rejected
- lock_released
5. Keep logs at debug or info level only.
6. Do not log sensitive payloads or full object dumps.
7. Log destination for runtime debugging:
- core/logs/latest.log
8. Rotated historical logs also available in:
- core/logs/previous.log
- core/logs/red-part1.log through red-part5.log

## Topic 7 Final Decision - Documentation and Surface Consistency Policy
1. All user-facing lure text must use one canonical command set:
- dcshop buy common
- dcshop buy rare
- dcshop buy super
2. No user-facing surface may advertise dcshop buy lure as a purchase command.
3. All user-facing lure surfaces must include shared cooldown wording.
4. All user-facing lure surfaces must include one-total-lure wording.
5. Legacy lure must always be described as use-only if owned.
6. Event and legendary lure exclusions must be stated consistently in shop/help/confirmation text.
7. Pre-release gate: fail if any lure-facing surface uses stale command or rule text.

## Canonical User-Facing Strings (Ready To Paste)

This section is the single source of truth for lure wording. Reuse this text across all files.

## commands/shop.py

Shop field names and descriptions:
1. Common Lure field name:
- 🥩 Common Lure - {conf.price_common_lure} Coins
2. Common Lure field value:
- Summons a random Common or Uncommon creature in this channel.
- Shared cooldown: {cooldown_display}
- Buy: {ctx.prefix}dcshop buy common

3. Rare Lure field name:
- 🥩 Rare Lure - {conf.price_rare_lure} Coins
4. Rare Lure field value:
- Summons a random Semi-Rare or Rare creature in this channel.
- Shared cooldown: {cooldown_display}
- Buy: {ctx.prefix}dcshop buy rare

5. Super Lure field name:
- 🥩 Super Lure - {conf.price_super_lure} Coins
6. Super Lure field value:
- Summons a random Very Rare or Super Rare creature in this channel.
- Shared cooldown: {cooldown_display}
- Buy: {ctx.prefix}dcshop buy super

7. Shop rules note:
- You can hold only one lure total at a time.
- Lure cooldown is shared across all lure tiers.
- Event and Legendary creatures cannot be spawned by lure.
- Legacy lures can still be used if already owned.

Purchase flow messages:
1. Invalid legacy purchase command:
- That purchase command has been replaced.
- Use one of:
- {ctx.prefix}dcshop buy common
- {ctx.prefix}dcshop buy rare
- {ctx.prefix}dcshop buy super

2. Already owns a lure:
- You already have a lure. You can hold only one lure total.
- Use {ctx.prefix}dclure before buying another.

3. Purchase success:
- You bought a Common Lure for {price} DinoCoins. Use {ctx.prefix}dclure when ready.
- You bought a Rare Lure for {price} DinoCoins. Use {ctx.prefix}dclure when ready.
- You bought a Super Lure for {price} DinoCoins. Use {ctx.prefix}dclure when ready.

## commands/user.py (dclure)

No lure message:
- You do not have a lure.
- Buy one with:
- {ctx.prefix}dcshop buy common
- {ctx.prefix}dcshop buy rare
- {ctx.prefix}dcshop buy super

Confirmation summary template:
1. Title:
- Lure Use Confirmation
2. Body:
- You are about to use: {lure_label}
- Spawn pool: {rarity_pool_label}
- Continue?

Cooldown denied message:
- You must wait {minutes}m {seconds}s before using any lure again.
- Lure cooldown is shared across all lure tiers.

Use start message:
- You placed your {lure_label}... something is approaching!

Failure and refund message:
- The {lure_label} failed to attract anything. It has been returned.

Concurrency denied message:
- You already have a lure action in progress.

## commands/user.py (dcstats)

Stats field name:
- 🥩 Lure

Stats field value template:
- Owned: {Legacy Lure/Common Lure/Rare Lure/Super Lure/None}
- Status: {Ready to use or Cooldown: Xm Ys}
- Rule: One lure total. Cooldown is shared across all lure tiers.

## views/help.py

Help lure section:
1. Common Lure entry:
- Common Lure - {conf.price_common_lure} Coins
- Summons Common/Uncommon creatures.
- Buy: {self.ctx.prefix}dcshop buy common

2. Rare Lure entry:
- Rare Lure - {conf.price_rare_lure} Coins
- Summons Semi-Rare/Rare creatures.
- Buy: {self.ctx.prefix}dcshop buy rare

3. Super Lure entry:
- Super Lure - {conf.price_super_lure} Coins
- Summons Very Rare/Super Rare creatures.
- Buy: {self.ctx.prefix}dcshop buy super

4. Rules:
- You can hold only one lure total at a time.
- Lure cooldown is shared across all lure tiers.
- Event and Legendary creatures cannot be spawned by lure.
- Legacy lures can still be used if already owned.

Commands panel replacement lines:
- {p}dcshop buy common - Buy Common Lure
- {p}dcshop buy rare - Buy Rare Lure
- {p}dcshop buy super - Buy Super Lure
- {p}dclure - Use your lure

## main.py (dccommands and static help snippets)

User command list lines:
- dcshop - View the shop.
- dcshop buy upgrade - Buy inventory slots.
- dcshop buy common - Buy Common Lure.
- dcshop buy rare - Buy Rare Lure.
- dcshop buy super - Buy Super Lure.
- dclure - Use a lure you own.

Admin command summary line:
- dcset shop <upgrade_price/common_lure_price/rare_lure_price/super_lure_price/lure_cooldown> - Shop settings.

## Text Audit Checklist (Must Pass)
1. No surface includes dcshop buy lure as a purchase command.
2. Shop, help, stats, and dclure all state shared cooldown.
3. Shop, help, stats, and dclure all state one-total-lure rule.
4. Legacy lure is only described as use-only.
5. Event and legendary lure exclusions are visible in shop/help/confirmation wording.
6. Command names are identical across shop/help/command panels.

## Topic 2 Final Decision - Event and Legendary Policy
1. Event creatures must never spawn from any lure type.
2. Legendary creatures must never spawn from any lure type.
3. This rule applies to legacy lure, common lure, rare lure, and super lure.
4. Event mode only affects normal spawn systems, not lure-driven spawns.
5. Any future change to allow event/legendary via lure must be an explicit new feature, not implicit behavior.

## Data Model Strategy (Topic 1 Finalized)

## User Model
Keep existing legacy field:
- has_lure: bool (legacy ownership flag)

Add new field:
- lure_type: str = "none"

Allowed lure_type values:
- none
- common
- rare
- super

Ownership evaluation helper rule:
- user_has_any_lure = user_conf.has_lure or user_conf.lure_type != "none"

Legacy meaning:
- has_lure == True means the user owns one legacy lure.
- legacy lure is not purchasable, only consumable.

## Guild Settings Model
Keep existing legacy price field:
- price_lure (legacy price, no longer used for purchases)

Use/add new purchasable fields:
- price_common_lure
- price_rare_lure
- price_super_lure

Notes:
- price_lure remains stored for compatibility only.
- shop and new purchase commands must not reference price_lure.

## Migration Process (Non-Destructive)
This rewrite uses a compatibility-first migration, not a destructive rewrite.

At load/use time:
1. If lure_type missing, default to none.
2. Do not auto-convert has_lure True into common lure.
3. Treat has_lure as a distinct legacy state.
4. Do not remove price_lure.
5. Add/use price_common_lure for new common lure purchasing.

Idempotency requirements:
- Running compatibility logic multiple times must not change valid new values.
- No migration step should duplicate or consume lure ownership.

Persistence behavior:
- Save operations should preserve legacy has_lure until it is consumed.
- Once legacy lure is consumed, set has_lure = False and keep lure_type workflow only.

## Legacy Lure Transition Rules
1. Legacy lure cannot be purchased.
2. Legacy lure can be used with dclure.
3. dclure must explicitly say Legacy Lure before confirmation.
4. Recommended spawn pool for legacy lure: common + uncommon.
5. On successful consume:
- has_lure -> False
- lure_type should remain none unless another lure is owned.
6. On failure/refund:
- restore the exact consumed lure source (legacy should restore has_lure True).

## Shop Rewrite Plan
Files:
- commands/shop.py

Required changes:
1. Remove legacy lure listing from dcshop display.
2. Add 3 listings:
- Common Lure (price_common_lure)
- Rare Lure (price_rare_lure)
- Super Lure (price_super_lure)
3. Show one-total-lure ownership rule in dcshop.
4. Add purchase commands:
- dcshop buy common
- dcshop buy rare
- dcshop buy super
5. Block purchase if user_has_any_lure is True.
6. Do not sell legacy lure.
7. If user runs dcshop buy lure, show guided output listing:
- dcshop buy common
- dcshop buy rare
- dcshop buy super

## dclure Rewrite Plan
Files:
- commands/user.py
- views/confirmation.py (reuse)
- databases/gameinfo.py (filtered rarity support)

Required behavior:
1. Determine lure source in this order:
- If has_lure True -> legacy lure
- Else if lure_type != none -> new lure type
- Else no lure
1.5. Acquire per-user lure operation guard before beginning confirmation flow.
1.6. If guard already active, return message:
- "You already have a lure action in progress."
2. Before consume, show confirmation with:
- lure label (Legacy/Common/Rare/Super)
- rarity pool
- cooldown reminder
 - shared cooldown reminder (applies to all lure tiers)
3. On cancel/timeout:
- no consume
- no cooldown
 - release per-user operation guard
4. On confirm:
 - re-check lure ownership/source and cooldown before consume
- consume correct lure source
- set cooldown and increment total_lures_used
5. Spawn pool mapping:
- Legacy: common + uncommon
- Common: common + uncommon
- Rare: semi_rare + rare
- Super: very_rare + super_rare
6. Exclusion rule:
- Event rarity must be excluded from all lure pool filters.
- Legendary rarity must be excluded from all lure pool filters.
7. Failure refund must restore exact source:
- legacy refund restores has_lure
- common/rare/super refund restores lure_type
8. Guard lifecycle:
- always release guard in finally logic
- no code path should exit with guard still active
9. Diagnostics:
- emit LURE_OP logs at each critical phase transition
- include required operation context fields

## Stats and Help Updates
Files:
- commands/user.py
- views/help.py
- main.py (static command text)

dcstats requirements:
1. Show lure ownership as one of:
- Legacy Lure
- Common Lure
- Rare Lure
- Super Lure
- None
2. Keep cooldown display.
3. Include one-total-lure note.
4. Include shared cooldown note (global per user, all tiers).

dchelp requirements:
1. Show all 3 purchasable lure types with pools and prices.
2. Explicitly state one-total-lure rule.
3. Mention that legacy lures may still be used if owned.
4. Update command reference text to exactly:
- dcshop buy common
- dcshop buy rare
- dcshop buy super
5. Explicitly state that lure cooldown is shared across all lure tiers.

## Admin Settings Plan
Files:
- main.py

Required admin commands:
1. Add or use:
- dcset shop common_lure_price
- dcset shop rare_lure_price
- dcset shop super_lure_price
2. Keep:
- dcset shop lure_cooldown
3. displayshop must show:
- Common Lure Price
- Rare Lure Price
- Super Lure Price
4. Legacy price_lure is compatibility-only and should not be presented as active shop price.

## Achievements and Sync Compatibility
Files:
- main.py
- test_achievements.py

Rules:
1. first_lure_purchase compatibility check should treat either state as valid:
- has_lure True
- lure_type != none
- last_lure_use > 0
2. first_lure_use and lure_10 logic remain based on use counters/timestamp.
3. Update tests to cover mixed legacy + new ownership conditions.

## Validation Checklist
- Legacy user with has_lure True can still run dclure.
- Legacy user cannot buy any new lure until legacy lure is used.
- User with new lure_type cannot buy another lure.
- dcshop no longer offers legacy lure.
- dcshop buy lure is rejected with guided command output.
- dclure confirmation correctly identifies lure source.
- Cancelled confirmation does not consume lure.
- Cooldown starts only after confirmed consume.
- Cooldown denial text explicitly states cooldown is shared across all lure tiers.
- Spawn pools match lure type mapping exactly.
- No lure type can ever spawn event rarity.
- No lure type can ever spawn legendary rarity.
- Refund restores exact consumed lure source.
- Concurrent dclure attempts for same user never consume more than one lure.
- Double confirmation clicks cannot apply duplicate consume/refund state changes.
- Guard always clears after success, cancel, timeout, or exception.
- dcstats reflects Legacy/Common/Rare/Super/None correctly.
- dchelp and command lists match implemented commands.
- displayshop shows 3 active lure prices.
- LURE_OP logs are present for success, cancel, timeout, refund, and rejected_in_progress paths.
- LURE_OP lines include user_id, guild_id, lure_source, phase, and result.

## Implementation Order
1. Models and compatibility helpers
2. Shop command rewrite
3. dclure source detection + confirmation + consume/refund
4. Spawn filtering support
5. Stats/help/admin messaging updates
6. Achievement sync updates
7. Test updates and validation pass

## Future Retirement Plan (Optional)
After adoption period:
1. Measure how many users still have has_lure True.
2. If near zero, schedule phase 2 cleanup.
3. In cleanup phase, remove legacy field usage and legacy logic.
4. Keep a final one-time migration note in release docs.