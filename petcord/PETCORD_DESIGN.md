# Petcord Discord Cog - Design Document

## Overview

A virtual pet game for Discord where users can adopt, care for, and nurture randomized animals. Each pet requires daily interaction through feeding, grooming, playing, and other species-specific care activities. Users find new pets through the main menu interface, and may only have one growing pet at a time.

---

## Core Game Mechanics

### Main Menu Access
- Users access the game via `[p]petcord` (or `[p]pcpet`)
- The Main Menu embed displays different content based on pet ownership status
- All interactions after the initial command are button-based

### Pet Finding System
When a user has **no current pet**, the Main Menu shows a "🔍 Find a Pet" button.

**Finding Process:**
1. User clicks "🔍 Find a Pet" button
2. System generates a random pet with pre-rolled species, coat color, and pattern
3. Pet is displayed as a "potential adoptee" with all its details
4. User has two options:
   - **✅ Adopt**: Accept this pet and begin the adoption process
   - **❌ Pass**: Decline this pet and wait for another

**Cooldown System:**
- If user clicks "❌ Pass", they must wait **30 minutes** before viewing another pet
- Cooldown is per-user, tracked in their user data
- The Main Menu will show remaining cooldown time if they try again too soon
- If user clicks "✅ Adopt", no cooldown is applied (successful adoption)

### Pet Adoption
- Upon adopting, user is prompted to name their new pet via a modal
- The pet's appearance (coat/pattern) is locked at adoption
- Name restrictions apply (no profanity, length limits, etc.)
- Once named, the pet appears on the Main Menu with full status and interaction buttons

### One Pet Per User Rule (Growing Phase)
- Users may only have one **actively growing** pet at a time
- Growing pets require daily care and attention (Baby → Juvenile stages)
- When a pet reaches **Adult** stage, it becomes **ready to graduate**
- **Graduation requires user interaction** - pet stays with user until they acknowledge
- Upon next interaction, a graduation celebration is shown with medal award
- User must choose to **"Send to Home"** to complete graduation
- Only after sending to Home can the user adopt a new pet
- Releasing a pet during growth phase forfeits any potential medal

### The Home System
The **Home** is a personal sanctuary where mature pets live after completing their growth phase.

**Home Features:**
- **Graduation Ceremony**: When pet reaches Adult, user sees celebration embed on next interaction
  - Shows medal earned (Gold/Silver/Bronze)
  - Displays final growth stats and care summary
  - "Send to Home" button to complete graduation
- **No Required Care**: Pets in Home no longer have mandatory daily needs
- **Optional Interactions**: Users can still visit and interact with Home pets:
  - Petting (+Happiness, +Bond - no decay penalty if skipped)
  - Grooming (+Cleanliness - purely cosmetic/fun)
  - Treats (+Happiness, +Bond - special bonding moments)
- **Continued Aging**: Pets in Home continue to age through Adult → Senior stages
- **Natural Lifespan**: Pets will eventually pass away based on their species' longevity
- **Memorial Tab**: Accessible via button in Home menu - shows passed pets with stats and medals

**Home Capacity:**
- Default: 5 pets maximum in Home
- Can be expanded through achievements or server settings
- Oldest pets beyond capacity may need to be "rehomed" (released to shelter)

---

## Daily Care Tracking & Rating System

### How Daily Tracking Works
Each day (24-hour period from adoption time), the system tracks how well the user meets their growing pet's needs.

**Tracked Metrics:**
| Need | Requirement | Weight |
|------|-------------|--------|
| Feeding | Fed before hunger drops below 40 | 30% |
| Happiness | Maintained above 50 average | 25% |
| Cleanliness | Groomed before dropping below 30 | 20% |
| Energy | Allowed rest when exhausted | 15% |
| Bonus Interaction | Any extra petting/play | 10% |

### Daily Rating Scale
At the end of each day (or when checking status), users receive a rating:

| Rating | Score Range | Description |
|--------|-------------|-------------|
| ⭐⭐⭐⭐⭐ Perfect | 95-100% | Exceptional care, all needs exceeded |
| ⭐⭐⭐⭐ Excellent | 80-94% | Great care, most needs met promptly |
| ⭐⭐⭐ Good | 60-79% | Adequate care, some delays |
| ⭐⭐ Fair | 40-59% | Needs improvement, pet struggled |
| ⭐ Poor | 20-39% | Neglectful, pet suffered |
| 💀 Critical | 0-19% | Severe neglect, health impacted |

### Daily Score Calculation
```
Daily Score = (Feeding Score × 0.30) + (Happiness Score × 0.25) + 
              (Cleanliness Score × 0.20) + (Energy Score × 0.15) + 
              (Bonus Score × 0.10)

Where each component score (0-100) is based on:
- Time spent in healthy range vs critical range
- Promptness of care when needs arose
- Species-specific need multipliers
```

---

## Growth Medal System

### Overview
When a pet reaches adulthood and graduates to the Home, the user receives a **medal** based on their overall care performance throughout the pet's growth phase.

### Medal Tiers

| Medal | Requirement | Reward |
|-------|-------------|--------|
| 🥇 **Gold Medal** | Average daily rating ≥ 85% | +Special title, +Achievement, +Bonus bond |
| 🥈 **Silver Medal** | Average daily rating ≥ 70% | +Achievement, +Moderate bond bonus |
| 🥉 **Bronze Medal** | Average daily rating ≥ 50% | +Achievement, +Small bond bonus |
| ❌ **No Medal** | Average daily rating < 50% | Pet graduates but no medal earned |

### Medal Calculation
```
Final Medal Score = Sum(All Daily Scores) / Number of Growth Days

Growth Days = Days from adoption until reaching Adult stage
(Varies by species lifespan - typically 7-21 real days)
```

### Medal Bonuses
- **Gold**: Pet enters Home with +20 Bond, unlocks "Golden Caretaker" flair
- **Silver**: Pet enters Home with +10 Bond, unlocks "Devoted Owner" flair  
- **Bronze**: Pet enters Home with +5 Bond, unlocks "Caring Heart" flair

### Medal Display
- Medals are permanently attached to the pet's profile
- Visible when viewing pets in Home
- Shown in Memorial for passed pets
- Tracked in user statistics

---

## Pet Status System

### Core Stats (0-100 scale)
| Stat | Description | Decay Rate | Critical Threshold |
|------|-------------|------------|-------------------|
| **Hunger** | How fed the pet is | Species-dependent | Below 20 = starving |
| **Happiness** | Overall mood | Species-dependent | Below 20 = depressed |
| **Cleanliness** | Hygiene level | Species-dependent | Below 20 = dirty/sick risk |
| **Energy** | Rest/activity balance | Decreases with activity | Below 20 = exhausted |
| **Health** | Physical wellbeing | Affected by other stats | Below 20 = critical |
| **Bond** | Affection with owner | Increases with positive interactions | N/A |

### Stat Interactions
- **Low Hunger** → Decreases Happiness and Health
- **Low Cleanliness** → Increases disease chance, decreases Happiness
- **Low Energy** → Decreases effectiveness of play activities
- **Low Happiness** → Slower Bond gain, may refuse activities
- **High Bond** → Unlocks special interactions, cosmetic rewards

### Pet Age & Lifecycle
- Pets age in real-time (1 real day = 1 pet day)
- Life stages: Baby → Juvenile → **Adult (→ Home)** → Senior → Passed
- Each species has different lifespans and growth rates
- **Growth Phase** (Baby + Juvenile): Requires active daily care, tracked for medal
- **Home Phase** (Adult + Senior): No required care, optional interactions only
- Senior pets in Home have slightly faster natural aging
- Pets can pass away from two causes (see Death System below)

### Death System

Pets can pass away from two distinct causes, which are tracked separately:

#### 💔 Death from Neglect (During Growth Phase Only)
**Trigger:** Pet's Health stat reaches 0 during Baby/Juvenile stage
- Health decreases when Hunger stays below 20 for extended periods
- Health decreases when multiple stats are critically low simultaneously
- Configurable by server admins (`[p]pcset death on/off`)

**Consequences:**
- Pet does NOT graduate or earn a medal
- Pet is moved directly to Memorial with "neglect" cause
- User's medal streak is broken
- User's `pets_lost_to_neglect` counter increments
- No epitaph can be set (somber reminder)
- Memorial shows 💔 icon instead of 🕊️

**Prevention:** Keep all stats above critical thresholds. Warnings appear when stats drop below 30.

#### 🕊️ Death from Old Age (Home Pets Only)
**Trigger:** Pet reaches end of natural lifespan in Home
- Each species has a defined lifespan range
- Senior pets age faster than Adults
- Death occurs naturally, not from neglect

**Consequences:**
- Pet lived a full, happy life!
- Pet is moved to Memorial with "old_age" cause
- User's `pets_passed_naturally` counter increments
- Epitaph CAN be set (celebration of life)
- Memorial shows 🕊️ icon (peaceful)
- Achievement potential: "Gentle Goodbye", "Centenarian", etc.

#### Visual Indicators in Memorial
| Death Cause | Icon | Memorial Text | Epitaph Allowed |
|-------------|------|---------------|------------------|
| Old Age | 🕊️ | "Passed peacefully after X days" | ✅ Yes |
| Neglect | 💔 | "Lost on day X" | ❌ No |

---

## Interaction System

### Universal Actions (All Pets)
| Action | Effect | Cooldown | Details |
|--------|--------|----------|---------|
| `feed` | +Hunger | 4-8 hours | Different food types per species |
| `pet` | +Happiness, +Bond | 1 hour | Quick affection boost |
| `play` | +Happiness, -Energy | 2 hours | Species-specific games |
| `clean/groom` | +Cleanliness | 4-12 hours | Bathing, brushing, etc. |
| `rest` | +Energy, +Health | 8 hours | Put pet to sleep |
| `checkup` | View all stats | None | Detailed status embed |
| `treat` | ++Happiness, +Bond | 24 hours | Special reward item |

### Species-Specific Actions
Certain animals require unique care:
- **Aquatic pets**: Tank cleaning, water quality check
- **Reptiles**: Heat lamp adjustment, humidity control
- **Birds**: Cage cleaning, flight time
- **Furry mammals**: Brushing frequency varies by coat length
- **Exotic pets**: Specialized diet, enrichment activities

---

## Appearance System

### Coat Colors
Each species has a pool of possible base colors and pattern overlays.

**Color Categories:**
- **Natural**: Brown, Black, White, Gray, Tan, Cream, Golden
- **Rare**: Albino, Melanistic, Leucistic, Piebald
- **Mythical** (very rare): Rainbow, Galaxy, Crystal, Shadow

**Pattern Types:**
- Solid, Spotted, Striped, Tabby, Brindle, Merle, Calico, Tuxedo, Bicolor, Tricolor, Gradient

### Rarity System
| Rarity | Spawn Weight | Visual Indicator |
|--------|--------------|------------------|
| Common | 40% | ⭐ |
| Uncommon | 30% | ⭐⭐ |
| Rare | 18% | ⭐⭐⭐ |
| Very Rare | 8% | ⭐⭐⭐⭐ |
| Legendary | 3.5% | ⭐⭐⭐⭐⭐ |
| Mythical | 0.5% | 🌟 |

---

## Animal Database (100 Species)

### Category Legend
- **Activity Level**: Low / Medium / High (affects Energy decay)
- **Social Need**: Solitary / Moderate / High (affects Happiness from interaction)
- **Grooming Need**: Minimal / Moderate / Frequent (affects Cleanliness decay)
- **Diet Type**: Herbivore / Carnivore / Omnivore / Insectivore / Specialized
- **Lifespan**: Short (1-2 weeks) / Medium (3-4 weeks) / Long (5-8 weeks) / Extended (9+ weeks)
- **Care Difficulty**: Easy / Medium / Hard / Expert

---

## 🐕 DOGS (15 Species)

### 1. Golden Retriever
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Frequent (long coat, shedding)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Golden, Cream, Light Golden, Dark Golden
- **Patterns**: Solid
- **Special Needs**: Daily exercise, swimming optional activity
- **Temperament**: Friendly, eager to please, playful
- **Unique Interaction**: Fetch game (+extra Happiness)

### 2. Labrador Retriever
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Moderate (short coat, moderate shedding)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Black, Chocolate, Yellow, Fox Red
- **Patterns**: Solid
- **Special Needs**: Loves water, high food motivation
- **Temperament**: Outgoing, active, gentle
- **Unique Interaction**: Treat training (+Bond bonus)

### 3. German Shepherd
- **Rarity**: Uncommon
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Frequent (double coat)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Black/Tan, Sable, All Black, White
- **Patterns**: Saddle, Bicolor
- **Special Needs**: Mental stimulation, training activities
- **Temperament**: Loyal, intelligent, protective
- **Unique Interaction**: Training session (+Bond, +Happiness)

### 4. Chihuahua
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Minimal (short coat) / Moderate (long coat)
- **Diet Type**: Omnivore
- **Lifespan**: Extended
- **Care Difficulty**: Easy
- **Possible Coats**: Fawn, Black, White, Chocolate, Cream, Any color
- **Patterns**: Solid, Bicolor, Tricolor, Spotted
- **Special Needs**: Temperature sensitive, small portions
- **Temperament**: Sassy, loyal, alert
- **Unique Interaction**: Carry in pocket (+Happiness from closeness)

### 5. Husky
- **Rarity**: Uncommon
- **Activity Level**: Very High
- **Social Need**: High
- **Grooming Need**: Frequent (heavy shedding)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Black/White, Gray/White, Red/White, All White, Agouti
- **Patterns**: Bicolor with mask markings
- **Special Needs**: Extensive exercise, temperature regulation, howling vocal
- **Temperament**: Energetic, mischievous, talkative
- **Unique Interaction**: Howl together (+Happiness, +Bond)

### 6. Poodle
- **Rarity**: Uncommon
- **Activity Level**: Medium-High
- **Social Need**: High
- **Grooming Need**: Very Frequent (curly coat requires regular trimming)
- **Diet Type**: Omnivore
- **Lifespan**: Extended
- **Care Difficulty**: Medium
- **Possible Coats**: Black, White, Apricot, Silver, Brown, Cream, Blue, Gray
- **Patterns**: Solid, Phantom, Parti
- **Special Needs**: Professional grooming, mentally stimulating activities
- **Temperament**: Intelligent, proud, athletic
- **Unique Interaction**: Grooming styling (+Cleanliness boost, unlockable styles)

### 7. Bulldog (English)
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: High
- **Grooming Need**: Moderate (wrinkle care required)
- **Diet Type**: Omnivore
- **Lifespan**: Medium
- **Care Difficulty**: Medium
- **Possible Coats**: Brindle, White, Fawn, Red, Piebald
- **Patterns**: Solid, Brindle, Piebald
- **Special Needs**: Wrinkle cleaning, temperature sensitivity, avoid overexertion
- **Temperament**: Calm, stubborn, affectionate
- **Unique Interaction**: Wrinkle cleaning mini-game (+Cleanliness, +Health)

### 8. Beagle
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore (high food drive)
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Tricolor, Lemon/White, Red/White, Chocolate
- **Patterns**: Tricolor, Bicolor
- **Special Needs**: Scent enrichment, secure environment (escape artist)
- **Temperament**: Curious, merry, stubborn
- **Unique Interaction**: Sniff trail game (+Happiness, +Mental stimulation)

### 9. Corgi (Pembroke Welsh)
- **Rarity**: Uncommon
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Moderate (fluffy undercoat)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Red, Sable, Fawn, Black/Tan, Tricolor
- **Patterns**: Bicolor with white markings
- **Special Needs**: Weight management, back health
- **Temperament**: Playful, smart, bossy
- **Unique Interaction**: Herding mini-game (+Happiness)

### 10. Shiba Inu
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: Moderate (independent)
- **Grooming Need**: Moderate (seasonal shedding explosions)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Red, Sesame, Black/Tan, Cream
- **Patterns**: Urajiro (light underside markings)
- **Special Needs**: Secure area, patience with training
- **Temperament**: Independent, cat-like, loyal to family
- **Unique Interaction**: Dramatic scream (random event, +humor)

### 11. Dachshund
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Minimal (smooth) / Moderate (wire/long)
- **Diet Type**: Omnivore
- **Lifespan**: Extended
- **Care Difficulty**: Easy
- **Possible Coats**: Red, Cream, Black/Tan, Chocolate, Wild Boar, Dapple
- **Patterns**: Solid, Dapple, Brindle, Piebald
- **Special Needs**: Back protection, no jumping
- **Temperament**: Clever, stubborn, brave
- **Unique Interaction**: Burrowing in blankets (+Happiness)

### 12. Border Collie
- **Rarity**: Rare
- **Activity Level**: Very High
- **Social Need**: High
- **Grooming Need**: Moderate-Frequent
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Black/White, Red/White, Blue Merle, Tricolor
- **Patterns**: Bicolor, Merle, Tricolor
- **Special Needs**: Intense mental stimulation, job to do
- **Temperament**: Extremely intelligent, workaholic, sensitive
- **Unique Interaction**: Advanced trick training (+Bond++, +Happiness)

### 13. Pomeranian
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Frequent (fluffy double coat)
- **Diet Type**: Omnivore
- **Lifespan**: Extended
- **Care Difficulty**: Medium
- **Possible Coats**: Orange, Black, White, Cream, Sable, Merle, Parti
- **Patterns**: Solid, Sable, Parti
- **Special Needs**: Dental care, temperature awareness
- **Temperament**: Bold, vivacious, curious
- **Unique Interaction**: Show off pose (+Happiness from attention)

### 14. Great Dane
- **Rarity**: Rare
- **Activity Level**: Low-Medium
- **Social Need**: High
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore (large portions)
- **Lifespan**: Short
- **Care Difficulty**: Medium
- **Possible Coats**: Black, Blue, Fawn, Brindle, Harlequin, Mantle, Merle
- **Patterns**: Solid, Brindle, Harlequin, Mantle
- **Special Needs**: Joint care, space for size, gentle play
- **Temperament**: Gentle giant, patient, friendly
- **Unique Interaction**: Lean for cuddles (+Bond++)

### 15. Australian Shepherd
- **Rarity**: Uncommon
- **Activity Level**: Very High
- **Social Need**: High
- **Grooming Need**: Frequent
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Black, Red, Blue Merle, Red Merle
- **Patterns**: Merle, Tricolor, Bicolor
- **Special Needs**: Extensive exercise, mental challenges
- **Temperament**: Smart, work-oriented, loyal
- **Unique Interaction**: Frisbee catch (+Happiness++, -Energy)

---

## 🐱 CATS (15 Species)

### 16. Domestic Shorthair
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Moderate
- **Grooming Need**: Minimal (self-grooming)
- **Diet Type**: Carnivore
- **Lifespan**: Extended
- **Care Difficulty**: Easy
- **Possible Coats**: Any color
- **Patterns**: Tabby, Solid, Calico, Tuxedo, Any pattern
- **Special Needs**: Scratching post, vertical space
- **Temperament**: Varied, adaptable
- **Unique Interaction**: Lap sitting (+Bond, +Owner Happiness)

### 17. Siamese
- **Rarity**: Uncommon
- **Activity Level**: High
- **Social Need**: High (very vocal)
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Extended
- **Care Difficulty**: Medium
- **Possible Coats**: Seal Point, Chocolate Point, Blue Point, Lilac Point
- **Patterns**: Color point
- **Special Needs**: Companionship, conversation, mental stimulation
- **Temperament**: Vocal, demanding, affectionate, intelligent
- **Unique Interaction**: Conversation (meowing back and forth, +Happiness)

### 18. Maine Coon
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Frequent (long thick fur)
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Brown Tabby, Black, White, Cream, Silver, Any color
- **Patterns**: Tabby, Solid, Bicolor
- **Special Needs**: Larger food portions, regular brushing
- **Temperament**: Gentle giant, playful, dog-like
- **Unique Interaction**: Play fetch (+Happiness, unique for cats)

### 19. Persian
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: Moderate
- **Grooming Need**: Very Frequent (daily brushing required)
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: White, Black, Blue, Cream, Red, Silver, Golden
- **Patterns**: Solid, Tabby, Bicolor, Shaded
- **Special Needs**: Eye cleaning, mat prevention, flat-face care
- **Temperament**: Quiet, sweet, docile
- **Unique Interaction**: Luxury lounging (+Happiness from comfort)

### 20. Bengal
- **Rarity**: Rare
- **Activity Level**: Very High
- **Social Need**: High
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Brown, Snow, Silver, Charcoal
- **Patterns**: Spotted, Rosette, Marble
- **Special Needs**: Intense play, climbing structures, water play
- **Temperament**: Wild, energetic, curious, athletic
- **Unique Interaction**: Water play (+Happiness++, -Cleanliness)

### 21. Ragdoll
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: High
- **Grooming Need**: Moderate
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Seal, Blue, Chocolate, Lilac, Flame, Cream
- **Patterns**: Colorpoint, Mitted, Bicolor
- **Special Needs**: Gentle handling, follows owner around
- **Temperament**: Docile, calm, floppy when held, affectionate
- **Unique Interaction**: Go limp in arms (+Bond++, relaxation)

### 22. Scottish Fold
- **Rarity**: Rare
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Moderate
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Any color
- **Patterns**: Any pattern
- **Special Needs**: Joint health monitoring, ear care
- **Temperament**: Sweet, adaptable, quiet
- **Unique Interaction**: Buddha sit pose (+Happiness from cute)

### 23. Sphynx
- **Rarity**: Rare
- **Activity Level**: High
- **Social Need**: Very High
- **Grooming Need**: Frequent (skin care, bathing)
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Hairless - Black, White, Pink, Lavender, Any pigment
- **Patterns**: Solid, Bicolor, Any pigment pattern
- **Special Needs**: Regular baths, temperature regulation, sun protection
- **Temperament**: Extroverted, energetic, attention-seeking
- **Unique Interaction**: Warmth seeking (snuggle bonus, +Bond)

### 24. British Shorthair
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: Moderate
- **Grooming Need**: Moderate (dense coat)
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Blue (most famous), White, Black, Cream, Silver, Golden
- **Patterns**: Solid, Tabby, Bicolor
- **Special Needs**: Weight management, doesn't like being carried
- **Temperament**: Calm, easygoing, dignified, not lap cat
- **Unique Interaction**: Side-by-side sitting (+Bond, respects space)

### 25. Abyssinian
- **Rarity**: Uncommon
- **Activity Level**: Very High
- **Social Need**: High
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Ruddy, Sorrel, Blue, Fawn
- **Patterns**: Ticked tabby (agouti)
- **Special Needs**: Climbing, high perches, interactive toys
- **Temperament**: Curious, playful, acrobatic, mischievous
- **Unique Interaction**: High jump competition (+Happiness)

### 26. Russian Blue
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: Moderate (shy with strangers)
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Extended
- **Care Difficulty**: Easy
- **Possible Coats**: Blue (silver-tipped)
- **Patterns**: Solid
- **Special Needs**: Routine, quiet environment, predictability
- **Temperament**: Gentle, reserved, loyal to owner
- **Unique Interaction**: Secret spot discovery (+Bond from trust)

### 27. Norwegian Forest Cat
- **Rarity**: Rare
- **Activity Level**: Medium
- **Social Need**: Moderate
- **Grooming Need**: Frequent (waterproof double coat)
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Any color
- **Patterns**: Tabby, Solid, Bicolor, Any
- **Special Needs**: Climbing trees, seasonal coat changes
- **Temperament**: Friendly, independent, adventurous
- **Unique Interaction**: Tree climbing observation (+Happiness)

### 28. Savannah Cat
- **Rarity**: Very Rare
- **Activity Level**: Extremely High
- **Social Need**: High
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Expert
- **Possible Coats**: Golden, Silver, Smoke, Black
- **Patterns**: Spotted (wild markings)
- **Special Needs**: Large enclosure, leash training, water, extreme enrichment
- **Temperament**: Wild, loyal, dog-like, very intelligent
- **Unique Interaction**: Leash walking (+Happiness++, +Energy burn)

### 29. Oriental Shorthair
- **Rarity**: Uncommon
- **Activity Level**: High
- **Social Need**: Very High
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Over 300 color combinations!
- **Patterns**: Solid, Smoke, Shaded, Tabby, Bicolor
- **Special Needs**: Constant companionship, dislikes being alone
- **Temperament**: Vocal, demanding, loyal, playful
- **Unique Interaction**: Shoulder perching (+Bond, +Happiness)

### 30. Domestic Longhair
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Moderate
- **Grooming Need**: Frequent
- **Diet Type**: Carnivore
- **Lifespan**: Extended
- **Care Difficulty**: Easy
- **Possible Coats**: Any color
- **Patterns**: Any pattern
- **Special Needs**: Regular brushing to prevent mats
- **Temperament**: Varied, adaptable
- **Unique Interaction**: Brushing session (+Cleanliness, +Bond)

---

## 🐰 SMALL MAMMALS (15 Species)

### 31. Holland Lop Rabbit
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore (hay, vegetables)
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Broken, Solid - White, Black, Blue, Chocolate, Orange, Tort
- **Patterns**: Broken, Solid, Tricolor
- **Special Needs**: Hay supply, nail trimming, space to binky
- **Temperament**: Friendly, calm, cuddly
- **Unique Interaction**: Binky (happy jump, +Happiness indicator)

### 32. Netherland Dwarf Rabbit
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: Moderate
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Over 20 colors
- **Patterns**: Solid, Shaded, Tan, AOV
- **Special Needs**: Gentle handling due to size
- **Temperament**: Energetic, sometimes skittish, curious
- **Unique Interaction**: Nose bonks (+Bond)

### 33. Syrian Hamster
- **Rarity**: Common
- **Activity Level**: High (nocturnal)
- **Social Need**: Solitary (must be alone)
- **Grooming Need**: Minimal (self-grooming)
- **Diet Type**: Omnivore
- **Lifespan**: Short
- **Care Difficulty**: Easy
- **Possible Coats**: Golden, Cream, White, Black, Gray, Cinnamon
- **Patterns**: Solid, Banded, Dominant Spot
- **Special Needs**: Large wheel, burrowing substrate, single housing
- **Temperament**: Friendly when tamed, curious, cheek-stuffer
- **Unique Interaction**: Wheel running observation (+Activity tracking)

### 34. Dwarf Hamster (Roborovski)
- **Rarity**: Uncommon
- **Activity Level**: Extremely High
- **Social Need**: Can be paired (carefully)
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore
- **Lifespan**: Short
- **Care Difficulty**: Medium
- **Possible Coats**: Sandy, White-faced, Husky
- **Patterns**: Solid with eyebrow markings
- **Special Needs**: Secure cage (tiny escape artists), sand bath
- **Temperament**: Speedy, less handleable, entertaining to watch
- **Unique Interaction**: Speed run observation (+Entertainment)

### 35. Guinea Pig
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Very High (needs companion)
- **Grooming Need**: Moderate (varies by coat)
- **Diet Type**: Herbivore (high vitamin C need)
- **Lifespan**: Medium
- **Care Difficulty**: Easy
- **Possible Coats**: White, Black, Brown, Orange, Cream, Tricolor
- **Patterns**: Solid, Tricolor, Dutch, Himalayan, Roan
- **Special Needs**: Vitamin C supplements, floor time, hay
- **Temperament**: Social, vocal, affectionate
- **Unique Interaction**: Wheeking (excited vocalization, +Happiness indicator)

### 36. Ferret
- **Rarity**: Uncommon
- **Activity Level**: Very High
- **Social Need**: High
- **Grooming Need**: Moderate (bathing, ear cleaning)
- **Diet Type**: Carnivore
- **Lifespan**: Medium
- **Care Difficulty**: Medium
- **Possible Coats**: Sable, Albino, Silver, Chocolate, Black
- **Patterns**: Solid, Mitt, Blaze, Panda
- **Special Needs**: Ferret-proofed play area, hide spots, sleep 18hrs/day
- **Temperament**: Playful, curious, mischievous, theft-prone
- **Unique Interaction**: War dance (happy jumping dance, +Happiness++)

### 37. Chinchilla
- **Rarity**: Uncommon
- **Activity Level**: High (crepuscular)
- **Social Need**: Moderate
- **Grooming Need**: Frequent (dust baths, no water!)
- **Diet Type**: Herbivore (specialized)
- **Lifespan**: Extended (15-20 years equivalent)
- **Care Difficulty**: Medium
- **Possible Coats**: Standard Gray, White, Beige, Black Velvet, Violet
- **Patterns**: Solid, Mosaic
- **Special Needs**: Dust bath, cool temperatures, no moisture
- **Temperament**: Soft, bouncy, somewhat aloof, nocturnal
- **Unique Interaction**: Dust bath (+Cleanliness++, +Happiness)

### 38. Hedgehog
- **Rarity**: Uncommon
- **Activity Level**: Medium (nocturnal)
- **Social Need**: Solitary
- **Grooming Need**: Moderate (foot baths, quill cleaning)
- **Diet Type**: Insectivore/Omnivore
- **Lifespan**: Medium
- **Care Difficulty**: Medium
- **Possible Coats**: Salt & Pepper, Chocolate, Albino, Cinnamon, Pinto
- **Patterns**: Solid, Snowflake, Pinto
- **Special Needs**: Wheel, warm environment, insect treats
- **Temperament**: Shy initially, curious once comfortable, huffs when annoyed
- **Unique Interaction**: Anointing (self-protection behavior, unique animation)

### 39. Sugar Glider
- **Rarity**: Rare
- **Activity Level**: High (nocturnal)
- **Social Need**: Very High (needs colony or constant attention)
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore (specialized diet)
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Classic Gray, White-faced Blonde, Leucistic, Albino, Platinum
- **Patterns**: Stripe on back
- **Special Needs**: Bonding pouch, tall cage, colony or constant bonding
- **Temperament**: Bonded, social, gliding, vocal at night
- **Unique Interaction**: Gliding to owner (+Bond++, +Happiness)

### 40. Rat (Fancy)
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: Very High (needs companion)
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore
- **Lifespan**: Short
- **Care Difficulty**: Easy
- **Possible Coats**: Agouti, Black, White, Gray, Blue, Siamese, Himalayan
- **Patterns**: Solid, Hooded, Berkshire, Capped, Variegated
- **Special Needs**: Cage mates, climbing, mental enrichment
- **Temperament**: Intelligent, affectionate, trainable, social
- **Unique Interaction**: Trick training (+Bond, +Happiness)

### 41. Gerbil
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: High (needs same-sex pair)
- **Grooming Need**: Minimal (sand bath)
- **Diet Type**: Omnivore
- **Lifespan**: Short
- **Care Difficulty**: Easy
- **Possible Coats**: Agouti, Black, White, Slate, Dove, Lilac, Argente
- **Patterns**: Solid, Spotted, Pied
- **Special Needs**: Deep bedding for burrowing, sand bath
- **Temperament**: Curious, active, burrowers, rarely bite
- **Unique Interaction**: Tunnel building (+Enrichment)

### 42. Mouse (Fancy)
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: High (females together, males solitary)
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore
- **Lifespan**: Short
- **Care Difficulty**: Easy
- **Possible Coats**: White, Black, Brown, Tan, Silver, Champagne
- **Patterns**: Solid, Banded, Dutch, Marked
- **Special Needs**: Climbing opportunities, secure lid
- **Temperament**: Curious, quick, can be hand-tamed
- **Unique Interaction**: Climbing obstacle course (+Happiness)

### 43. Degu
- **Rarity**: Uncommon
- **Activity Level**: Very High
- **Social Need**: Very High (needs group)
- **Grooming Need**: Moderate (dust bath)
- **Diet Type**: Herbivore (no sugar!)
- **Lifespan**: Medium
- **Care Difficulty**: Medium
- **Possible Coats**: Agouti, Blue, Sand, Cream
- **Patterns**: Solid
- **Special Needs**: No sugar (diabetic prone), dust bath, exercise wheel
- **Temperament**: Social, vocal, intelligent, curious
- **Unique Interaction**: Chirping conversation (+Bond)

### 44. Rex Rabbit
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Minimal (velvet coat)
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Castor, Black, Blue, White, Chocolate, Lilac
- **Patterns**: Solid, Broken
- **Special Needs**: Soft bedding (sensitive feet)
- **Temperament**: Calm, friendly, excellent pets
- **Unique Interaction**: Velvet petting (+Happiness from texture)

### 45. Lionhead Rabbit
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Frequent (mane maintenance)
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Any color
- **Patterns**: Any pattern
- **Special Needs**: Daily mane brushing, dental check
- **Temperament**: Friendly, energetic, good-natured
- **Unique Interaction**: Mane styling (+Cleanliness, +Appearance variety)

---

## 🦎 REPTILES (12 Species)

### 46. Leopard Gecko
- **Rarity**: Common
- **Activity Level**: Low (crepuscular)
- **Social Need**: Solitary
- **Grooming Need**: Minimal (moist hide for shedding)
- **Diet Type**: Insectivore
- **Lifespan**: Extended (20+ years equivalent)
- **Care Difficulty**: Easy
- **Possible Coats**: Normal, High Yellow, Tangerine, Albino, Blizzard, Mack Snow
- **Patterns**: Spotted, Jungle, Patternless, Bold
- **Special Needs**: Heat mat, calcium dusting, moist hide
- **Temperament**: Docile, handleable, slow-moving, tail waving
- **Unique Interaction**: Tail wag (excited for food, +Happiness indicator)

### 47. Bearded Dragon
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Solitary (tolerates handling)
- **Grooming Need**: Moderate (baths for shedding)
- **Diet Type**: Omnivore (insects + vegetables)
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Normal, Citrus, Red, Orange, Hypo, Leatherback, Silkback
- **Patterns**: Tiger, Dunner, Translucent
- **Special Needs**: UVB lighting, basking spot, varied diet
- **Temperament**: Friendly, arm waving, head bobbing, chill
- **Unique Interaction**: Arm wave greeting (+Bond, +Humor)

### 48. Ball Python
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: Solitary
- **Grooming Need**: Minimal (humidity for shedding)
- **Diet Type**: Carnivore (rodents)
- **Lifespan**: Extended (30+ years)
- **Care Difficulty**: Medium
- **Possible Coats**: Normal, Spider, Pastel, Piebald, Albino, Banana, Clown
- **Patterns**: Alien head pattern, reduced pattern, striped
- **Special Needs**: Humidity, hides, infrequent feeding
- **Temperament**: Shy, curls into ball when scared, handleable
- **Unique Interaction**: Ball curling (stress indicator)

### 49. Corn Snake
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Solitary
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore (rodents)
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Classic, Amelanistic, Anerythristic, Snow, Ghost, Lavender
- **Patterns**: Normal, Motley, Stripe, Diffused
- **Special Needs**: Secure lid (escape artists), climbing
- **Temperament**: Docile, curious, excellent first snake
- **Unique Interaction**: Exploring wrap (comfortable handling, +Bond)

### 50. Crested Gecko
- **Rarity**: Common
- **Activity Level**: Medium (nocturnal)
- **Social Need**: Can be housed together (carefully)
- **Grooming Need**: Minimal (misting)
- **Diet Type**: Omnivore (fruit diet + insects)
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Buckskin, Flame, Harlequin, Dalmatian, Phantom, Lilly White
- **Patterns**: Dalmatian spots, pin stripes, tiger
- **Special Needs**: High humidity, no tail regeneration!
- **Temperament**: Jumpy, handleable, sticky toe pads
- **Unique Interaction**: Wall climbing observation (+Entertainment)

### 51. Blue-Tongued Skink
- **Rarity**: Uncommon
- **Activity Level**: Low-Medium
- **Social Need**: Solitary
- **Grooming Need**: Moderate (bathing)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Northern, Indonesian, Irian Jaya, Merauke
- **Patterns**: Banded
- **Special Needs**: UVB, varied diet, burrowing substrate
- **Temperament**: Docile, bluffs with blue tongue, food motivated
- **Unique Interaction**: Tongue display (+Humor, defensive bluff)

### 52. Russian Tortoise
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: Solitary
- **Grooming Need**: Moderate (shell care, baths)
- **Diet Type**: Herbivore (leafy greens)
- **Lifespan**: Extended (50+ years equivalent)
- **Care Difficulty**: Medium
- **Possible Coats**: Brown, Tan, Yellow, Dark
- **Patterns**: Scute patterns vary
- **Special Needs**: UVB, outdoor time, burrow area
- **Temperament**: Determined, digger, personable
- **Unique Interaction**: Outdoor grazing (+Happiness++)

### 53. Red-Eared Slider
- **Rarity**: Common
- **Activity Level**: High (in water)
- **Social Need**: Can cohabitate
- **Grooming Need**: Moderate (shell/water quality)
- **Diet Type**: Omnivore
- **Lifespan**: Extended (30+ years)
- **Care Difficulty**: Medium
- **Possible Coats**: Green/Yellow with red ear marking
- **Patterns**: Striped
- **Special Needs**: Large aquarium, basking dock, UVB
- **Temperament**: Active, begging for food, can bite
- **Unique Interaction**: Basking observation (+Health)

### 54. Chameleon (Veiled)
- **Rarity**: Rare
- **Activity Level**: Low
- **Social Need**: Solitary (stress from handling)
- **Grooming Need**: Minimal (misting)
- **Diet Type**: Insectivore
- **Lifespan**: Medium
- **Care Difficulty**: Hard
- **Possible Coats**: Green base with bands
- **Patterns**: Banding that changes color based on mood
- **Special Needs**: Screen enclosure, live plants, misting system, minimal handling
- **Temperament**: Territorial, color-changing, observational pet
- **Unique Interaction**: Color mood indicator (dynamic color display)

### 55. Uromastyx
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: Solitary or pair
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Yellow, Orange, Red, Green, Blue (varies by species)
- **Patterns**: Banded, spotted
- **Special Needs**: Very hot basking (120°F+), no humidity, seed diet
- **Temperament**: Docile, basking-focused, tail whip defense
- **Unique Interaction**: Tail whip (defensive, humor)

### 56. Gargoyle Gecko
- **Rarity**: Uncommon
- **Activity Level**: Medium (nocturnal)
- **Social Need**: Can cohabitate carefully
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Red, Orange, Yellow, White, Striped, Reticulated
- **Patterns**: Striped, Blotched, Reticulated
- **Special Needs**: Similar to crested gecko, can regenerate tail
- **Temperament**: Calm, slightly nippier than cresties
- **Unique Interaction**: Horn observation (+Entertainment)

### 57. Argentine Black and White Tegu
- **Rarity**: Very Rare
- **Activity Level**: High
- **Social Need**: Bonds with owner
- **Grooming Need**: Moderate (baths, nail trims)
- **Diet Type**: Omnivore
- **Lifespan**: Extended (15-20 years)
- **Care Difficulty**: Expert
- **Possible Coats**: Black/White, Blue, Red
- **Patterns**: Banded
- **Special Needs**: Large enclosure, substrate to burrow, varied diet, taming
- **Temperament**: Dog-like when tamed, intelligent, large
- **Unique Interaction**: Tegu training (+Bond++, +Intelligence display)

---

## 🐦 BIRDS (15 Species)

### 58. Budgerigar (Budgie)
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: Very High (needs flock/interaction)
- **Grooming Need**: Minimal (misting, nail trims)
- **Diet Type**: Herbivore (seeds, pellets, vegetables)
- **Lifespan**: Medium
- **Care Difficulty**: Easy
- **Possible Coats**: Green, Blue, Yellow, White, Violet, Gray
- **Patterns**: Normal, Pied, Spangled, Clearwing, Opaline
- **Special Needs**: Cage time outside, toys, social interaction
- **Temperament**: Playful, talkative, social, acrobatic
- **Unique Interaction**: Speech training (+Bond, unlock phrases)

### 59. Cockatiel
- **Rarity**: Common
- **Activity Level**: Medium-High
- **Social Need**: High
- **Grooming Need**: Moderate (dusty, needs baths)
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Gray, Lutino, Pearl, Cinnamon, Pied, Whiteface
- **Patterns**: Pearl, Pied, Solid
- **Special Needs**: Whistling enrichment, crest mood indicator
- **Temperament**: Affectionate, whistlers, cuddly, crest shows mood
- **Unique Interaction**: Whistle duet (+Happiness, +Bond)

### 60. Lovebird
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: Very High
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore
- **Lifespan**: Medium
- **Care Difficulty**: Medium
- **Possible Coats**: Peach-faced, Fischer's, Masked (Green, Blue, Lutino, Opaline)
- **Patterns**: Solid, Pied, Opaline
- **Special Needs**: Pair bonding (to bird or human), shredding toys
- **Temperament**: Feisty, bonded, territorial, playful
- **Unique Interaction**: Cuddle preening (+Bond++)

### 61. Parrotlet
- **Rarity**: Uncommon
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Green, Blue, Yellow, White, Turquoise
- **Patterns**: Solid, Fallow, Marbled
- **Special Needs**: Small but mighty personality, training
- **Temperament**: Fearless, big personality in tiny body, nippy if untamed
- **Unique Interaction**: Shoulder buddy (+Bond, +Happiness)

### 62. Conure (Green-Cheeked)
- **Rarity**: Uncommon
- **Activity Level**: High
- **Social Need**: Very High
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Normal, Cinnamon, Pineapple, Yellow-sided, Turquoise
- **Patterns**: Marbled breast, solid
- **Special Needs**: Play time, cuddling, can be loud
- **Temperament**: Clownish, cuddly, acrobatic, LOUD
- **Unique Interaction**: Upside-down hanging (+Entertainment)

### 63. Canary
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Low-Moderate (fine alone)
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore
- **Lifespan**: Medium
- **Care Difficulty**: Easy
- **Possible Coats**: Yellow, Orange, White, Red, Variegated
- **Patterns**: Solid, Variegated
- **Special Needs**: Males sing, flight space, no handling needed
- **Temperament**: Independent, cheerful singers, observational
- **Unique Interaction**: Morning song (+Owner Happiness, +Pet Happiness)

### 64. Finch (Zebra)
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: High (needs flock)
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore (seeds)
- **Lifespan**: Medium
- **Care Difficulty**: Easy
- **Possible Coats**: Gray, Fawn, White, Pied, Penguin
- **Patterns**: Zebra stripes on male, cheek patches
- **Special Needs**: Flight space, multiple birds, no handling
- **Temperament**: Active, social, beep constantly, fly about
- **Unique Interaction**: Flock observation (+Entertainment)

### 65. Quaker Parrot
- **Rarity**: Uncommon
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Green, Blue, Pallid, Albino
- **Patterns**: Solid with gray chest
- **Special Needs**: Very vocal, excellent talkers, nest building
- **Temperament**: Talkers, can be territorial, intelligent
- **Unique Interaction**: Word learning (+Bond, unlock vocabulary)

### 66. African Grey Parrot
- **Rarity**: Very Rare
- **Activity Level**: Medium
- **Social Need**: Very High
- **Grooming Need**: Moderate (dusty)
- **Diet Type**: Herbivore
- **Lifespan**: Extended (50+ years)
- **Care Difficulty**: Expert
- **Possible Coats**: Gray with red tail
- **Patterns**: Solid gray
- **Special Needs**: Extreme mental stimulation, emotional bond, routine
- **Temperament**: Genius-level intelligence, sensitive, talkers, anxious if neglected
- **Unique Interaction**: Contextual conversation (+Bond++, +Intelligence)

### 67. Cockatoo (Umbrella)
- **Rarity**: Very Rare
- **Activity Level**: High
- **Social Need**: Extremely High
- **Grooming Need**: Frequent (dusty, baths)
- **Diet Type**: Herbivore
- **Lifespan**: Extended (60+ years)
- **Care Difficulty**: Expert
- **Possible Coats**: White with yellow crest undertones
- **Patterns**: Solid white
- **Special Needs**: Constant attention, destruction toys, very loud
- **Temperament**: Velcro bird, screamer if lonely, cuddly, dramatic
- **Unique Interaction**: Crest mood dance (+Happiness indicator, +Entertainment)

### 68. Dove (Ringneck)
- **Rarity**: Common
- **Activity Level**: Low
- **Social Need**: Moderate
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore (seeds)
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Fawn, White, Pied, Tangerine
- **Patterns**: Solid with neck ring
- **Special Needs**: Gentle, cooing vocalizations, flight time
- **Temperament**: Calm, gentle, cooing, pair bonds
- **Unique Interaction**: Peaceful cooing (+Relaxation bonus)

### 69. Amazon Parrot
- **Rarity**: Rare
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore
- **Lifespan**: Extended (50+ years)
- **Care Difficulty**: Hard
- **Possible Coats**: Green with species-specific head markings (Blue-front, Yellow-nape, etc.)
- **Patterns**: Green with colored accents
- **Special Needs**: Vocal, can be moody, excellent singers
- **Temperament**: Bold, operatic singers, can be nippy, personality plus
- **Unique Interaction**: Opera singing (+Entertainment++)

### 70. Eclectus Parrot
- **Rarity**: Rare
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore (fresh foods focused)
- **Lifespan**: Extended (40+ years)
- **Care Difficulty**: Hard
- **Possible Coats**: Male: Green, Female: Red/Purple (extreme dimorphism)
- **Patterns**: Solid with color blocking
- **Special Needs**: Fresh food diet, sensitive to additives
- **Temperament**: Calm, gentle, less noisy than other parrots
- **Unique Interaction**: Gender reveal upon adoption (+Surprise element)

### 71. Macaw (Blue and Gold)
- **Rarity**: Legendary
- **Activity Level**: High
- **Social Need**: Extremely High
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore (nuts, fruits, vegetables)
- **Lifespan**: Extended (60+ years)
- **Care Difficulty**: Expert
- **Possible Coats**: Blue upper, Gold under, Green head
- **Patterns**: Standard macaw coloring
- **Special Needs**: Huge space, destruction toys, very loud, lifelong commitment
- **Temperament**: Majestic, dramatic, loud, deeply bonded
- **Unique Interaction**: Majestic wing spread (+Entertainment++, +Bond)

### 72. Pigeon (Fancy)
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: High (pair bonds)
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore (seeds, grains)
- **Lifespan**: Medium
- **Care Difficulty**: Easy
- **Possible Coats**: White, Blue, Black, Red, Fantail, Pouter, Tumbler varieties
- **Patterns**: Check, Bar, Solid, Pied
- **Special Needs**: Flight space or aviary, pairs
- **Temperament**: Gentle, cooing, home-oriented
- **Unique Interaction**: Head bobbing strut (+Entertainment)

---

## 🐠 AQUATIC (10 Species)

### 73. Betta Fish
- **Rarity**: Common
- **Activity Level**: Low
- **Social Need**: Solitary (males)
- **Grooming Need**: Tank maintenance
- **Diet Type**: Carnivore (pellets, bloodworms)
- **Lifespan**: Short
- **Care Difficulty**: Easy
- **Possible Coats**: Red, Blue, Purple, White, Black, Orange, Multicolor
- **Patterns**: Solid, Marble, Koi, Galaxy, Butterfly
- **Special Needs**: Heated tank, single male, surface access
- **Temperament**: Curious, flaring at threats, personality
- **Unique Interaction**: Flare display (+Defense, +Entertainment)

### 74. Goldfish (Fancy)
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Social (needs tankmates)
- **Grooming Need**: Tank maintenance
- **Diet Type**: Omnivore
- **Lifespan**: Long (20+ years properly kept)
- **Care Difficulty**: Medium
- **Possible Coats**: Orange, White, Black, Calico, Red/White
- **Patterns**: Solid, Calico, Bicolor
- **Special Needs**: Large tank (no bowls!), cold water, filtration
- **Temperament**: Social, begging for food, personable
- **Unique Interaction**: Food dance (+Entertainment)

### 75. Axolotl
- **Rarity**: Rare
- **Activity Level**: Low
- **Social Need**: Can cohabitate (carefully)
- **Grooming Need**: Tank maintenance
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Wild, Leucistic, Albino, Golden, GFP, Melanoid, Copper
- **Patterns**: Solid, Speckled
- **Special Needs**: Cold water, no gravel, dim lighting
- **Temperament**: Derpy, permanent smile, regenerates limbs
- **Unique Interaction**: Gill flutter (+Cuteness, +Entertainment)

### 76. Hermit Crab
- **Rarity**: Common
- **Activity Level**: Medium (nocturnal)
- **Social Need**: Social (needs colony)
- **Grooming Need**: Habitat maintenance
- **Diet Type**: Omnivore
- **Lifespan**: Long (20+ years)
- **Care Difficulty**: Medium
- **Possible Coats**: Purple Pincher, Ecuadorian (various shell options)
- **Patterns**: Shell selection provides variety
- **Special Needs**: Humidity, salt water, shell selection, deep substrate
- **Temperament**: Curious, climbers, shell shoppers
- **Unique Interaction**: Shell change (+Appearance change, +Happiness)

### 77. Clownfish
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: Pair or small group
- **Grooming Need**: Tank maintenance
- **Diet Type**: Omnivore
- **Lifespan**: Medium
- **Care Difficulty**: Medium
- **Possible Coats**: Orange/White, Black/White, Maroon
- **Patterns**: Striped bands
- **Special Needs**: Saltwater, anemone optional, established tank
- **Temperament**: Bold, anemone guarding, hosting behavior
- **Unique Interaction**: Anemone wiggle (+Happiness, +Entertainment)

### 78. African Dwarf Frog
- **Rarity**: Common
- **Activity Level**: Medium
- **Social Need**: Social (needs friends)
- **Grooming Need**: Tank maintenance
- **Diet Type**: Carnivore
- **Lifespan**: Medium
- **Care Difficulty**: Easy
- **Possible Coats**: Olive, Spotted
- **Patterns**: Mottled spots
- **Special Needs**: Fully aquatic, surface access for breathing
- **Temperament**: Goofy, zen pose floating, singing males
- **Unique Interaction**: Zen float pose (+Entertainment)

### 79. Shrimp (Cherry)
- **Rarity**: Common
- **Activity Level**: High
- **Social Need**: Colony
- **Grooming Need**: Tank maintenance
- **Diet Type**: Omnivore (algae, biofilm)
- **Lifespan**: Short
- **Care Difficulty**: Medium
- **Possible Coats**: Red, Blue, Yellow, Black, Crystal varieties
- **Patterns**: Solid, Tiger stripes, Rili
- **Special Needs**: Planted tank, stable parameters
- **Temperament**: Busy, grazing constantly, breeding
- **Unique Interaction**: Molt observation (+Growth indicator)

### 80. Oscar Fish
- **Rarity**: Uncommon
- **Activity Level**: Medium
- **Social Need**: Can be solo or paired
- **Grooming Need**: Heavy tank maintenance
- **Diet Type**: Carnivore
- **Lifespan**: Long (15+ years)
- **Care Difficulty**: Hard
- **Possible Coats**: Tiger, Albino, Red, Lemon, Lutino
- **Patterns**: Tiger pattern
- **Special Needs**: Large tank (75+ gal), strong filtration, tankmate caution
- **Temperament**: Dog-like personality, recognizes owner, begging
- **Unique Interaction**: Owner recognition (+Bond++)

### 81. Snail (Mystery/Apple)
- **Rarity**: Common
- **Activity Level**: Low
- **Social Need**: Can cohabitate
- **Grooming Need**: Tank maintenance
- **Diet Type**: Herbivore (algae, vegetables)
- **Lifespan**: Short
- **Care Difficulty**: Easy
- **Possible Coats**: Gold, Blue, Purple, Ivory, Magenta, Jade
- **Patterns**: Solid
- **Special Needs**: Calcium for shell, copper-free
- **Temperament**: Peaceful, grazing, shell surfing
- **Unique Interaction**: Shell cleaning (+Cleanliness)

### 82. Koi Fish
- **Rarity**: Rare
- **Activity Level**: Medium
- **Social Need**: School
- **Grooming Need**: Pond maintenance
- **Diet Type**: Omnivore
- **Lifespan**: Extended (decades)
- **Care Difficulty**: Hard
- **Possible Coats**: Kohaku, Sanke, Showa, Ogon, Tancho
- **Patterns**: Elaborate patterns specific to variety
- **Special Needs**: Large pond (no tanks), filtration, winter care
- **Temperament**: Personable, hand-feeding, showpiece
- **Unique Interaction**: Hand feeding (+Bond++, +Trust)

---

## 🦔 EXOTIC & UNUSUAL (18 Species)

### 83. Axolotl (Repeat - see #75)
*Included in Aquatic section*

### 83. Tarantula (Chilean Rose)
- **Rarity**: Uncommon
- **Activity Level**: Very Low
- **Social Need**: Solitary
- **Grooming Need**: Minimal (habitat maintenance)
- **Diet Type**: Carnivore (insects)
- **Lifespan**: Extended (females 20+ years)
- **Care Difficulty**: Easy
- **Possible Coats**: Rose/Brown, Red, Burgundy
- **Patterns**: Solid with rose hairs
- **Special Needs**: Humid hide, infrequent feeding, handle with care
- **Temperament**: Docile, slow-moving, flick hairs if stressed
- **Unique Interaction**: Molt collection (+Achievement, +Growth)

### 84. Praying Mantis
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: Solitary
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore (live insects)
- **Lifespan**: Short
- **Care Difficulty**: Medium
- **Possible Coats**: Green, Brown, Orchid (species dependent)
- **Patterns**: Mimicry patterns
- **Special Needs**: Live food, humidity, climbing space
- **Temperament**: Alien-like, watching, striking at prey
- **Unique Interaction**: Hunting observation (+Entertainment)

### 85. Stick Insect
- **Rarity**: Common
- **Activity Level**: Very Low
- **Social Need**: Can cohabitate
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore (bramble, rose leaves)
- **Lifespan**: Short
- **Care Difficulty**: Easy
- **Possible Coats**: Brown, Green, Tan
- **Patterns**: Twig-like camouflage
- **Special Needs**: Fresh leaves, misting, tall enclosure
- **Temperament**: Zen, swaying, perfect camo
- **Unique Interaction**: Camo hide and seek (+Entertainment)

### 86. Scorpion (Emperor)
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: Can be kept in groups (carefully)
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore (insects)
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Black, Dark Blue sheen
- **Patterns**: Solid
- **Special Needs**: Humid, burrowing substrate, minimal handling
- **Temperament**: Defensive, grasps with claws, mild venom
- **Unique Interaction**: UV glow observation (+Entertainment)

### 87. Hermit Crab (Land - Repeat)
*See #76*

### 87. Millipede (Giant African)
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: Can cohabitate
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore (decaying plants, vegetables)
- **Lifespan**: Medium
- **Care Difficulty**: Easy
- **Possible Coats**: Black, Red-banded
- **Patterns**: Segmented bands
- **Special Needs**: Moist substrate, leaf litter, calcium
- **Temperament**: Docile, curls when stressed, many legs
- **Unique Interaction**: Leg counting (joke interaction, +Entertainment)

### 88. Frog (Pacman/Horned)
- **Rarity**: Uncommon
- **Activity Level**: Very Low
- **Social Need**: Solitary
- **Grooming Need**: Minimal (spot cleaning)
- **Diet Type**: Carnivore (mice, insects)
- **Lifespan**: Long
- **Care Difficulty**: Easy
- **Possible Coats**: Green, Albino, Strawberry, Samurai, Fantasy
- **Patterns**: Ornate patterns
- **Special Needs**: Ambush predator, burrowing, humid
- **Temperament**: Grumpy blob, bite-y, sit and wait
- **Unique Interaction**: Feeding ambush (+Entertainment)

### 89. Salamander (Fire)
- **Rarity**: Uncommon
- **Activity Level**: Low
- **Social Need**: Solitary
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Medium
- **Possible Coats**: Black with Yellow/Orange
- **Patterns**: Spotted/Striped
- **Special Needs**: Cool, moist, land with water access
- **Temperament**: Secretive, toxic skin (no handling)
- **Unique Interaction**: Spot observation (unique pattern per individual)

### 90. Poison Dart Frog
- **Rarity**: Rare
- **Activity Level**: Medium
- **Social Need**: Species dependent
- **Grooming Need**: Vivarium maintenance
- **Diet Type**: Insectivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Blue, Yellow-banded, Strawberry, Green/Black
- **Patterns**: Warning coloration (aposematic)
- **Special Needs**: Bioactive vivarium, isopods, not toxic in captivity
- **Temperament**: Bold, diurnal, colorful display
- **Unique Interaction**: Color display (+Entertainment)

### 91. Fennec Fox
- **Rarity**: Very Rare
- **Activity Level**: Very High (nocturnal)
- **Social Need**: Bonds with owner
- **Grooming Need**: Minimal
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Expert
- **Possible Coats**: Cream/Tan
- **Patterns**: Solid with white underside
- **Special Needs**: Legal requirements, escape proofing, dig box, loud
- **Temperament**: Energetic, screechy, dog-cat hybrid behavior
- **Unique Interaction**: Ear radar observation (+Entertainment++)

### 92. Capybara
- **Rarity**: Legendary
- **Activity Level**: Low-Medium
- **Social Need**: Extremely High (herd animal)
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore (grasses, aquatic plants)
- **Lifespan**: Long
- **Care Difficulty**: Expert
- **Possible Coats**: Brown, Tan
- **Patterns**: Solid
- **Special Needs**: Pool, grazing area, herd or constant companion
- **Temperament**: Zen master, chill, social with all animals
- **Unique Interaction**: Pool floating (+Relaxation++, +Happiness++)

### 93. Wallaby
- **Rarity**: Legendary
- **Activity Level**: High
- **Social Need**: High
- **Grooming Need**: Minimal
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Expert
- **Possible Coats**: Gray, Red, Albino
- **Patterns**: Solid
- **Special Needs**: Large outdoor space, fencing, legal requirements
- **Temperament**: Curious, bouncy, can be shy
- **Unique Interaction**: Pouch check (if female, +Surprise)

### 94. Pygmy Goat
- **Rarity**: Rare
- **Activity Level**: High
- **Social Need**: Very High (herd animal)
- **Grooming Need**: Moderate (hoof care)
- **Diet Type**: Herbivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Black, White, Caramel, Agouti, Multicolor
- **Patterns**: Solid, Patterned
- **Special Needs**: Outdoor space, climbing structures, companion goat
- **Temperament**: Playful, mischievous, escape artist
- **Unique Interaction**: Parkour climbing (+Entertainment)

### 95. Miniature Pig
- **Rarity**: Rare
- **Activity Level**: Medium
- **Social Need**: High
- **Grooming Need**: Moderate (skin care, hooves)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Pink, Black, Spotted, Red
- **Patterns**: Solid, Spotted, Belted
- **Special Needs**: Rooting area, outdoor time, intelligence
- **Temperament**: Smart, stubborn, food-obsessed, affectionate
- **Unique Interaction**: Trick training (+Bond++, +Intelligence)

### 96. Kinkajou
- **Rarity**: Legendary
- **Activity Level**: High (nocturnal)
- **Social Need**: Bonds with owner
- **Grooming Need**: Minimal
- **Diet Type**: Frugivore/Omnivore
- **Lifespan**: Long (20+ years)
- **Care Difficulty**: Expert
- **Possible Coats**: Golden/Honey brown
- **Patterns**: Solid
- **Special Needs**: Large cage, climbing, nocturnal schedule, specialized diet
- **Temperament**: Curious, can be nippy, prehensile tail
- **Unique Interaction**: Hanging by tail (+Entertainment)

### 97. Serval
- **Rarity**: Legendary
- **Activity Level**: Very High
- **Social Need**: Bonds with owner (wild tendencies)
- **Grooming Need**: Minimal
- **Diet Type**: Carnivore
- **Lifespan**: Long
- **Care Difficulty**: Expert
- **Possible Coats**: Spotted golden
- **Patterns**: Leopard spots
- **Special Needs**: Huge enclosure, raw diet, legal restrictions, not domesticated
- **Temperament**: Wild, athletic jumper, can be affectionate but unpredictable
- **Unique Interaction**: High jump display (+Entertainment++, athletic)

### 98. Skunk (Domesticated)
- **Rarity**: Very Rare
- **Activity Level**: Medium
- **Social Need**: Bonds with owner
- **Grooming Need**: Moderate (bathing, nail trims)
- **Diet Type**: Omnivore
- **Lifespan**: Long
- **Care Difficulty**: Hard
- **Possible Coats**: Black/White, Chocolate/White, Lavender, Albino, Apricot
- **Patterns**: Striped, Chipped, Star
- **Special Needs**: Descented, legal requirements, digging enrichment
- **Temperament**: Curious, stomping when upset (no spray if descented), cat-like
- **Unique Interaction**: Stomp warning dance (+Humor)

### 99. Opossum
- **Rarity**: Rare
- **Activity Level**: Medium (nocturnal)
- **Social Need**: Solitary (but bonds with rescuer)
- **Grooming Need**: Moderate
- **Diet Type**: Omnivore
- **Lifespan**: Short
- **Care Difficulty**: Medium
- **Possible Coats**: Gray, Leucistic
- **Patterns**: Solid with lighter face
- **Special Needs**: Must be rehab/educational animal, pouch for joeys
- **Temperament**: Misunderstood, gentle, plays dead, gaping mouth display
- **Unique Interaction**: Play dead (+Humor, +Defense mechanism)

### 100. Red Panda
- **Rarity**: Mythical
- **Activity Level**: Medium
- **Social Need**: Solitary/Pair
- **Grooming Need**: Moderate
- **Diet Type**: Herbivore (bamboo specialist)
- **Lifespan**: Long
- **Care Difficulty**: Expert (zoo animals)
- **Possible Coats**: Red/Orange with white face
- **Patterns**: Ringed tail
- **Special Needs**: Zoo/sanctuary only, bamboo diet, climbing, temperature
- **Temperament**: Adorable, elusive, standing threat pose
- **Unique Interaction**: Standing pose (+Cuteness++, +Entertainment)

---

## Stat Decay Rates by Species Category

### Decay Multipliers (per hour)
| Category | Hunger | Happiness | Cleanliness | Energy |
|----------|--------|-----------|-------------|--------|
| Dogs | 1.5x | 1.2x | 1.0x | 1.3x |
| Cats | 1.0x | 0.8x | 0.5x | 0.8x |
| Small Mammals | 2.0x | 1.0x | 1.0x | 1.5x |
| Reptiles | 0.3x | 0.5x | 0.8x | 0.5x |
| Birds | 1.8x | 1.5x | 1.2x | 1.0x |
| Aquatic | 1.0x | 0.6x | 1.5x (tank) | 0.5x |
| Exotic | Varies | Varies | Varies | Varies |

---

## Database Schema Overview

### GuildSettings
```python
class GuildSettings(Base):
    users: Dict[int, User]
    game_is_enabled: bool = False
    
    # Pet Finding Settings
    find_cooldown_minutes: int = 30  # Cooldown after declining a pet
    
    # Game Settings
    pet_death_enabled: bool = False  # Whether GROWING pets can die from neglect
    abandoned_pet_shelter: bool = True  # Released pets go to shelter
    
    # Home Settings
    default_home_capacity: int = 5  # Starting home capacity for users
    max_home_capacity: int = 20  # Maximum achievable home capacity
    
    # Growth & Medal Settings
    growth_day_length_hours: int = 24  # Real hours per pet day
    medal_gold_threshold: float = 85.0  # Minimum average for gold
    medal_silver_threshold: float = 70.0  # Minimum average for silver
    medal_bronze_threshold: float = 50.0  # Minimum average for bronze
    
    # Admin Settings
    admin_role_id: int = None
    disallowed_names: List[str] = []
```

### User
```python
class User(Base):
    # Current Growing Pet (Baby/Juvenile stage)
    current_pet: Optional[Pet] = None
    
    # Pet Finding Cooldown
    last_pet_declined: float = 0.0  # Timestamp of last declined pet
    # If current_time - last_pet_declined < cooldown, user cannot search for new pet
    
    # Home - Mature pets (Adult/Senior stage)
    home_pets: List[Pet] = []  # Max capacity configurable
    home_capacity: int = 5
    
    # Memorial - Passed pets
    memorial: List[PetMemorial] = []
    
    # History (released/abandoned pets)
    pet_history: List[PetHistoryEntry] = []
    total_pets_owned: int = 0
    total_pets_released: int = 0
    total_pets_graduated: int = 0  # Successfully raised to adulthood
    
    # Death Tracking (separated by cause)
    pets_passed_naturally: int = 0  # Pets that died of old age in Home (good!)
    pets_lost_to_neglect: int = 0  # Pets that died from neglect during growth (bad)
    total_pets_passed: int = 0  # Sum of above two (for quick reference)
    
    # Medal Tracking
    gold_medals: int = 0
    silver_medals: int = 0
    bronze_medals: int = 0
    total_medals: int = 0
    
    # Daily Care Stats (for current growing pet)
    current_day_start: float = 0.0  # Timestamp when current day started
    current_day_scores: DailyCareScore = None  # Today's tracking
    care_history: List[DailyCareScore] = []  # All days for current pet
    
    # Care Performance Tracking
    total_needs_met: int = 0  # Times user successfully met a pet's need
    total_needs_failed: int = 0  # Times user failed to meet a pet's need
    # Success rate = total_needs_met / (total_needs_met + total_needs_failed)
    
    # Lifetime Stats
    total_interactions: int = 0
    total_feedings: int = 0
    total_play_sessions: int = 0
    total_grooming_sessions: int = 0
    total_rest_sessions: int = 0
    total_treats_given: int = 0
    total_petting_sessions: int = 0
    longest_pet_lifespan: int = 0
    highest_bond_achieved: int = 0
    best_medal_streak: int = 0  # Consecutive gold medals
    current_medal_streak: int = 0
    
    # Achievements
    achievements: List[Achievement] = []
```

### Pet
```python
class Pet(Base):
    name: str
    species_id: str
    
    # Appearance
    coat_color: str
    pattern: str
    rarity: str
    
    # Stats (0-100)
    hunger: int = 100
    happiness: int = 100
    cleanliness: int = 100
    energy: int = 100
    health: int = 100
    bond: int = 0
    
    # Lifecycle
    age_days: int = 0
    life_stage: str = "baby"  # baby, juvenile, adult, senior
    ready_to_graduate: bool = False  # True when reached adult, waiting for user interaction
    is_in_home: bool = False  # True once user confirms graduation to Home
    adopted_timestamp: float
    reached_adult_timestamp: float = 0.0  # When pet first reached adult stage
    graduated_timestamp: float = 0.0  # When user confirmed move to Home
    passed_timestamp: float = 0.0  # When passed away (0 = alive)
    death_cause: str = ""  # "old_age", "neglect", or "" (alive)
    last_interaction: float
    
    # Growth Phase Tracking (only tracked during Baby/Juvenile)
    growth_daily_scores: List[DailyCareScore] = []  # Each day's care rating
    growth_average_score: float = 0.0  # Running average
    growth_total_days: int = 0  # Days spent in growth phase
    
    # Medal (awarded upon graduation)
    medal: str = ""  # "gold", "silver", "bronze", "" (none)
    medal_score: float = 0.0  # Final average that determined medal
    
    # Cooldowns
    last_fed: float = 0.0
    last_played: float = 0.0
    last_groomed: float = 0.0
    last_rested: float = 0.0
    last_treated: float = 0.0
```

### DailyCareScore
```python
class DailyCareScore(Base):
    """Tracks care quality for a single day."""
    day_number: int  # Which day of the pet's life
    date_timestamp: float  # When this day started
    
    # Component Scores (0-100 each)
    feeding_score: float = 0.0
    happiness_score: float = 0.0
    cleanliness_score: float = 0.0
    energy_score: float = 0.0
    bonus_score: float = 0.0
    
    # Tracking data for calculations
    times_fed: int = 0
    times_played: int = 0
    times_groomed: int = 0
    times_rested: int = 0
    times_petted: int = 0
    times_treated: int = 0
    
    # Time tracking
    minutes_hungry: int = 0  # Minutes below 40 hunger
    minutes_unhappy: int = 0  # Minutes below 50 happiness
    minutes_dirty: int = 0  # Minutes below 30 cleanliness
    minutes_exhausted: int = 0  # Minutes below 20 energy
    
    # Final calculated score
    final_score: float = 0.0  # Weighted average
    rating: str = ""  # "perfect", "excellent", "good", "fair", "poor", "critical"
```

### PetMemorial
```python
class PetMemorial(Base):
    """Record of a passed pet for the memorial."""
    name: str
    species_id: str
    coat_color: str
    pattern: str
    rarity: str
    
    # Life summary
    adopted_timestamp: float
    graduated_timestamp: float  # 0.0 if died before graduation
    passed_timestamp: float
    total_lifespan_days: int
    
    # Death information
    death_cause: str  # "old_age" or "neglect"
    # old_age = peaceful passing in Home after full life
    # neglect = health reached 0 during growth phase
    
    # Achievements (only applicable for old_age deaths)
    medal: str  # "" if death_cause == "neglect" (never graduated)
    medal_score: float
    final_bond: int
    reached_home: bool = False  # True if pet made it to Home
    
    # Optional epitaph (only allowed for old_age deaths)
    epitaph: str = ""  # User can set a short memorial message
    epitaph_allowed: bool = True  # False if death_cause == "neglect"
```

---

## Command Structure

### Design Philosophy: Button-Based Interactions
All game interactions after the initial command are handled through **Discord UI buttons and select menus**. This provides:
- Cleaner, more intuitive user experience
- Reduced command spam in channels
- Visual feedback and organized menus
- Persistent interactive embeds

---

### File Organization Requirements

**Player Code** (`commands/` folder):
| File | Contents |
|------|----------|
| `user_commands.py` | All player-facing commands (`Petcord`/`pcpet`, `pcstat`) |
| `helper_functions.py` | All helper/utility functions used by player commands |

**Admin Code** (`commands/` folder):
| File | Contents |
|------|----------|
| `admin_commands.py` | All admin commands and subcommands (`pcset` group) |

**Structure:**
```
commands/
├── __init__.py
├── user_commands.py      # Player commands: Petcord, pcstat
├── helper_functions.py   # Utility functions for player features
└── admin_commands.py     # Admin command group: pcset
```

---

### Player Commands (2 Total)

#### `[p]petcord` (alias: `[p]pcpet`)
The main game command. Opens the **Pet Dashboard** - an interactive embed with buttons for all pet-related actions.

**Dashboard States:**

**State 1: No Pet - Ready to Find (New User or Post-Graduation)**
```
┌─────────────────────────────────────────────┐
│  🐾 Petcord - Welcome!                   │
│  You don't have a pet yet.                  │
│  Click below to find a new companion!       │
├─────────────────────────────────────────────┤
│  Use [p]pcstat to view your Home, Memorial, │
│  and lifetime statistics!                   │
├─────────────────────────────────────────────┤
│  [🔍 Find a Pet]                            │
│  [📖 Species Guide]  [🏆 Leaderboard]       │
└─────────────────────────────────────────────┘
```

**State 1b: No Pet - On Cooldown (After Declining)**
```
┌─────────────────────────────────────────────┐
│  🐾 Petcord                              │
│  You don't have a pet yet.                  │
├─────────────────────────────────────────────┤
│  ⏳ You recently passed on a pet.           │
│  You can search again in: 24m 15s           │
├─────────────────────────────────────────────┤
│  Use [p]pcstat to view your Home, Memorial, │
│  and lifetime statistics!                   │
├─────────────────────────────────────────────┤
│  [🔍 Find a Pet] (disabled)                 │
│  [📖 Species Guide]  [🏆 Leaderboard]       │
└─────────────────────────────────────────────┘
```

**State 1c: Pet Found - Awaiting Decision**
```
┌─────────────────────────────────────────────┐
│  🔍 A Pet Needs a Home!                     │
├─────────────────────────────────────────────┤
│  🐰 Holland Lop Rabbit                      │
│  Rarity: ⭐⭐ Uncommon                       │
│  Coat: Chocolate | Pattern: Spotted         │
├─────────────────────────────────────────────┤
│  📋 Species Info:                           │
│  • Activity Level: Moderate                 │
│  • Grooming Needs: Medium                   │
│  • Diet: Herbivore                          │
│  • Lifespan: 8-12 years                     │
│  • Special Trait: Floppy ears!              │
├─────────────────────────────────────────────┤
│  Would you like to adopt this pet?          │
├─────────────────────────────────────────────┤
│  [✅ Adopt]  [❌ Pass]                       │
│  (Passing starts a 30 minute cooldown)      │
└─────────────────────────────────────────────┘
```

**State 1d: Naming New Pet (After Adopting)**
```
┌─────────────────────────────────────────────┐
│  🎉 Congratulations!                        │
│  You've adopted a Holland Lop Rabbit!       │
├─────────────────────────────────────────────┤
│  🐰 Your new friend is waiting for a name!  │
│  Coat: Chocolate | Pattern: Spotted         │
├─────────────────────────────────────────────┤
│  [✏️ Name Your Pet]                         │
└─────────────────────────────────────────────┘

(Clicking opens a modal for entering the pet's name)
```

**State 2: Growing Pet (Baby/Juvenile)**
```
┌─────────────────────────────────────────────┐
│  🐕 "Buddy" - Golden Retriever              │
│  Stage: Baby (Day 3/7)  ⭐⭐⭐ Rare          │
│  Coat: Golden | Pattern: Solid              │
├─────────────────────────────────────────────┤
│  ❤️ Health: ████████░░ 80%                  │
│  🍖 Hunger: ██████░░░░ 60%  ⚠️              │
│  😊 Happiness: █████████░ 90%               │
│  ✨ Cleanliness: ███████░░░ 70%             │
│  💤 Energy: ████░░░░░░ 40%                  │
│  💕 Bond: ██░░░░░░░░ 20                     │
├─────────────────────────────────────────────┤
│  Today's Rating: ⭐⭐⭐⭐ Excellent (82%)    │
│  Projected Medal: 🥈 Silver                 │
├─────────────────────────────────────────────┤
│  [🍖 Feed]  [🎾 Play]  [🛁 Groom]  [💤 Rest]│
│  [🍬 Treat] [✋ Pet]   [📋 Details]         │
├─────────────────────────────────────────────┤
│  [⚙️ Settings]                              │
└─────────────────────────────────────────────┘
```

**State 3: Pet Ready to Graduate (Reached Adult)**
```
┌─────────────────────────────────────────────┐
│  🎉 CONGRATULATIONS! 🎉                     │
│  "Buddy" has grown into an Adult!           │
├─────────────────────────────────────────────┤
│  🏅 Medal Earned: 🥇 GOLD                   │
│  Final Score: 87.3%                         │
│  Growth Days: 14                            │
├─────────────────────────────────────────────┤
│  Care Summary:                              │
│  • Perfect Days: 8                          │
│  • Excellent Days: 5                        │
│  • Good Days: 1                             │
│  • Final Bond: 75                           │
├─────────────────────────────────────────────┤
│  "Buddy" is ready to move to your Home!    │
│  You'll still be able to visit and interact │
│  with them anytime.                         │
├─────────────────────────────────────────────┤
│  [🏠 Send to Home]  [👋 Say Goodbye First]  │
└─────────────────────────────────────────────┘
```

**Button Actions (Growing Pet):**
| Button | Action |
|--------|--------|
| 🍖 Feed | Opens food selection menu, feeds pet |
| 🎾 Play | Opens activity selection, plays with pet |
| 🛁 Groom | Grooms/cleans the pet |
| 💤 Rest | Puts pet to sleep for energy recovery |
| 🍬 Treat | Gives special treat (daily cooldown) |
| ✋ Pet | Quick affection interaction |
| 📋 Details | Shows detailed stats, care history, species info |
| ⚙️ Settings | Pet settings (rename, release with confirmation) |

> **Note:** Home, Memorial, and Stats are accessed via `[p]pcstat` command

---

#### `[p]pcstat`
Displays the user's **Petcord Statistics**, **Home**, and **Memorial** - similar to `[p]dcstat` from DinoCollector. This is the hub for viewing lifetime stats, managing Home pets, and honoring passed pets.

**Main Stats View:**
```
┌─────────────────────────────────────────────┐
│  📊 Petcord Stats - @Username            │
├─────────────────────────────────────────────┤
│  🏅 Medals Earned                           │
│  🥇 Gold: 5  🥈 Silver: 3  🥉 Bronze: 2    │
│  Current Streak: 🥇🥇🥇 (3 Gold)            │
│  Best Streak: 5 Gold                        │
├─────────────────────────────────────────────┤
│  📈 Lifetime Stats                          │
│  Pets Raised: 12                            │
│  Pets Graduated to Adulthood: 10            │
│  Pets Released: 2                           │
│  🕊️ Passed Peacefully: 4                    │
│  💔 Lost to Neglect: 1                       │
│  Currently in Home: 3/5                     │
├─────────────────────────────────────────────┤
│  💕 Care Performance                        │
│  Needs Successfully Met: 847                │
│  Needs Failed to Meet: 42                   │
│  Success Rate: 95.3%                        │
├─────────────────────────────────────────────┤
│  🎮 Interaction Stats                       │
│  Total Interactions: 1,247                  │
│  Total Feedings: 389                        │
│  Total Play Sessions: 245                   │
│  Highest Bond Ever: 98                      │
│  Longest Pet Lifespan: 156 days             │
├─────────────────────────────────────────────┤
│  🏆 Achievements: 24/50 unlocked            │
├─────────────────────────────────────────────┤
│  [🏠 View Home]  [🪦 Memorial]             │
│  [🏆 Achievements]  [🏅 Medal Details]     │
│  [📜 Release History]  [🏆 Leaderboard]     │
└─────────────────────────────────────────────┘
```

---

**Home Menu (Button in pcstat):**
```
┌─────────────────────────────────────────────┐
│  🏠 Your Home - 3/5 Pets                    │
├─────────────────────────────────────────────┤
│  1. "Max" - Beagle 🥇                       │
│     Adult • Day 45 • Bond: 92               │
│  2. "Luna" - Siamese 🥈                     │
│     Senior • Day 78 • Bond: 88              │
│  3. "Pip" - Hamster 🥉                      │
│     Adult • Day 12 • Bond: 65               │
├─────────────────────────────────────────────┤
│  [Select Pet ▼] to view and interact        │
├─────────────────────────────────────────────┤
│  [◀️ Back to Stats]                         │
└─────────────────────────────────────────────┘
```

**Home Pet Selected (Interaction View):**
```
┌─────────────────────────────────────────────┐
│  🐕 "Max" - Beagle                          │
│  Stage: Adult • Living in Home              │
│  Medal: 🥇 Gold (89.2%)                     │
├─────────────────────────────────────────────┤
│  😊 Happiness: █████████░ 90%               │
│  ✨ Cleanliness: ████████░░ 80%             │
│  💕 Bond: █████████░ 92                     │
├─────────────────────────────────────────────┤
│  With you for 45 days                       │
│  Graduated on: Jan 15, 2026                 │
├─────────────────────────────────────────────┤
│  [✋ Pet]  [🛁 Groom]  [🍬 Treat]           │
│  [✏️ Rename]  [🏡 Rehome]                   │
├─────────────────────────────────────────────┤
│  [◀️ Back to Home List]                     │
└─────────────────────────────────────────────┘
```

---

**Memorial (Button in pcstat):**
```
┌─────────────────────────────────────────────┐
│  🪦 Pet Memorial                            │
│  In loving memory...                        │
├─────────────────────────────────────────────┤
│  🕊️ "Whiskers" - Persian 🥇                │
│     Passed peacefully after 156 days        │
│     "The fluffiest friend I ever had"       │
│                                             │
│  🕊️ "Spike" - Hedgehog 🥈                  │
│     Passed peacefully after 89 days         │
│     (Click to set epitaph)                  │
│                                             │
│  💔 "Bubbles" - Betta Fish                  │
│     Lost on day 4                           │
│     (Epitaph not available)                 │
├─────────────────────────────────────────────┤
│  [Select Pet ▼] to view details/set epitaph │
├─────────────────────────────────────────────┤
│  [◀️ Back to Stats]                         │
└─────────────────────────────────────────────┘
```

**Legend:**
- 🕊️ = Passed peacefully of old age (in Home)
- 💔 = Lost to neglect (during growth phase)

---

### Admin Command Group (1 Total)

#### `[p]pcset`
Admin command group for server configuration. Similar to `[p]dcset` from DinoCollector.

| Subcommand | Description |
|------------|-------------|
| `[p]pcset display` | Show current server settings |
| `[p]pcset toggle` | Enable/disable the game for the server |
| `[p]pcset channel add <#channel>` | Add an allowed spawn channel |
| `[p]pcset channel remove <#channel>` | Remove an allowed spawn channel |
| `[p]pcset channel list` | List all allowed channels |
| `[p]pcset spawn interval <min> <max>` | Set spawn interval range (minutes) |
| `[p]pcset spawn duration <seconds>` | Set how long spawns stay claimable |
| `[p]pcset spawn count <1-3>` | Set animals per spawn event |
| `[p]pcset spawn force` | Force an immediate spawn event |
| `[p]pcset home capacity <default> <max>` | Set default and max home capacity |
| `[p]pcset medals <gold> <silver> <bronze>` | Set medal score thresholds |
| `[p]pcset death <on/off>` | Enable/disable pet death from neglect |
| `[p]pcset blacklist add <word>` | Add word to name blacklist |
| `[p]pcset blacklist remove <word>` | Remove word from blacklist |
| `[p]pcset blacklist list` | Show blacklisted words |
| `[p]pcset shelter` | View/manage community shelter |
| `[p]pcset adminrole <role>` | Set admin role for game management |

---

### Spawn Event UI (Appears in Allowed Channels)
```
┌─────────────────────────────────────────────┐
│  🌟 Wild Animals Appeared!                  │
│  Quick! Choose one to adopt!                │
├─────────────────────────────────────────────┤
│  1. 🐕 Golden Retriever ⭐⭐ Uncommon       │
│     Coat: Cream | Pattern: Solid            │
│                                             │
│  2. 🐱 Bengal ⭐⭐⭐ Rare                    │
│     Coat: Snow | Pattern: Rosette           │
│                                             │
│  3. 🐹 Syrian Hamster ⭐ Common             │
│     Coat: Golden | Pattern: Banded          │
├─────────────────────────────────────────────┤
│  ⏱️ Expires in 4:32                         │
├─────────────────────────────────────────────┤
│  [Adopt #1]  [Adopt #2]  [Adopt #3]         │
└─────────────────────────────────────────────┘
```

**After Adoption (Name Input Modal):**
- Clicking adopt opens a Discord Modal
- User enters pet name
- Validation runs (length, blacklist, profanity)
- Success shows welcome message with new pet

---

## Achievement System (Examples)

### Adoption & Basics
| Achievement | Requirement |
|-------------|-------------|
| First Friend | Adopt your first pet |
| Species Collector | Own 10 different species over time |
| Legendary Keeper | Own a legendary rarity pet |
| Mythical Encounter | Own a mythical rarity pet |
| Rainbow Collection | Own pets of 7 different coat colors |
| Early Bird | Interact with pet within 1 minute of spawn |

### Care & Daily Ratings
| Achievement | Requirement |
|-------------|-------------|
| Perfect Day | Achieve a 100% daily care rating |
| Perfect Week | 7 consecutive days of 95%+ ratings |
| Consistent Caretaker | 30 days without a "Poor" rating |
| Night Owl | Care for a nocturnal pet 10 times at night |
| Morning Routine | Feed your pet within 1 hour of daily reset 7 times |
| Dedicated Parent | Complete all care activities in a single day 50 times |

### Medal Achievements
| Achievement | Requirement |
|-------------|-------------|
| First Gold | Earn your first Gold Medal |
| Golden Touch | Earn 5 Gold Medals |
| Medal Collector | Earn 10 medals of any type |
| Gold Standard | Earn 10 Gold Medals |
| Perfectionist | Earn a Gold Medal with 95%+ average |
| Gold Streak x3 | Earn 3 Gold Medals in a row |
| Gold Streak x5 | Earn 5 Gold Medals in a row |
| Platinum Caretaker | Earn 25 Gold Medals |

### Home Achievements
| Achievement | Requirement |
|-------------|-------------|
| Homeowner | Graduate your first pet to Home |
| Full House | Have 5 pets living in your Home at once |
| Retirement Home | Have a pet reach Senior stage in Home |
| Centenarian | Have a pet live for 100 days total |
| Max Bond | Reach 100 bond with any pet |
| Gentle Goodbye | Have a pet pass away peacefully of old age |
| Memorial Keeper | Add an epitaph to a pet's memorial |
| Legacy Builder | Graduate 25 pets to Home over your lifetime |

### Special Achievements
| Achievement | Requirement |
|-------------|-------------|
| Comeback Kid | Earn a Gold Medal after previously earning no medal |
| Improvement Arc | Earn a better medal than your previous pet |
| Jack of All Trades | Raise 5 different species categories to adulthood |

---

## Future Expansion Ideas

1. **Pet Breeding** - Two users can breed compatible pets for offspring
2. **Pet Shows** - Server competitions for best-looking pets
3. **Pet Tricks** - Trainable tricks that increase bond
4. **Pet Items** - Toys, beds, accessories from a shop
5. **Seasonal Events** - Special holiday pets and costumes
6. **Pet Trading** - Trade pets with other users
7. **Pet Sanctuary** - Community shelter for released pets
8. **Pet Battles** - Friendly stat-based competitions
9. **Pet Aging Cosmetics** - Visual changes as pets age
10. **Cross-Server Events** - Global pet events

---

## Implementation Priority

### Phase 1: Core System
- [ ] Database models (Pet, User, DailyCareScore, PetMemorial)
- [ ] Pet spawning system
- [ ] Basic adoption flow with naming
- [ ] Stat decay system
- [ ] Core interactions (feed, play, groom, rest)

### Phase 2: Growth & Tracking
- [ ] Daily care tracking system
- [ ] Daily score calculation
- [ ] Daily rating display
- [ ] Growth progress tracking
- [ ] Life stage transitions (Baby → Juvenile → Adult)

### Phase 3: Home & Graduation
- [ ] Home system implementation
- [ ] Automatic graduation on reaching Adult
- [ ] Medal calculation and awarding
- [ ] Home pet interactions (optional care)
- [ ] Senior aging and natural passing
- [ ] Memorial system

### Phase 4: Polish
- [ ] Full species database implementation
- [ ] Appearance randomization
- [ ] Embed formatting with pet displays
- [ ] Cooldown system
- [ ] Health/death mechanics for growing pets

### Phase 5: Engagement
- [ ] Achievement system (including medal achievements)
- [ ] Leaderboards (medals, streaks, bond scores)
- [ ] Pet history/memorial viewing
- [ ] Species encyclopedia
- [ ] Advanced species-specific interactions

### Phase 6: Expansion
- [ ] Shop/items
- [ ] Home capacity upgrades
- [ ] Events
- [ ] Additional features based on feedback

---

*Document Version: 1.5*
*Created: February 2026*
*Last Updated: February 1, 2026*
*Author: Design Document for Petcord Discord Cog*

**Changelog:**
- v1.5: Replaced channel-based spawning with button-based "Find a Pet" system; user initiates search, accepts/declines offered pet, 30-minute cooldown on decline
- v1.4: Added death cause differentiation (old_age vs neglect), separate tracking for each death type, epitaph restrictions based on death cause, visual indicators in memorial
- v1.3: Added file organization requirements (user_commands.py, helper_functions.py, admin_commands.py), moved Home/Memorial to pcstat command, added needs met/failed tracking, expanded lifetime stats
- v1.2: Consolidated to 3 commands (`petcord`/`pcpet`, `pcstat`, `pcset`), made all interactions button-based, graduation now requires user interaction, memorial moved to Home menu button
- v1.1: Added Home system, Daily Care Tracking, Medal system, Memorial system
