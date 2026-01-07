# Greenacres Fishing - Game Summary

A Discord fishing simulation game built as a Red-DiscordBot cog. Players can fish in various locations, collect different species, earn points, and progress through the game.

---

## 🎮 Core Gameplay

### Player Stats
- **Total Fish Caught** - Lifetime fishing count
- **Total Fishing Attempts** - Number of casts made
- **Total Fish Sold** - Fish sold to earn currency
- **Total Fishpoints** - In-game currency earned
- **Current Fish Inventory** - Fish currently held
- **Biggest Fish Caught** - Personal record tracker

---

## 🌍 Environments & Locations

### Fishing Locations
| Location | Water Type | Notes |
|----------|-----------|-------|
| **Pond** | Freshwater | Beginner-friendly, panfish |
| **Lake** | Freshwater | Larger freshwater species |
| **River** | Fresh/Brackish | Mixed species, flyfishing |
| **Ocean** | Saltwater | Big game fishing |

### Seasons
- 🌸 **Spring** - Bass season
- ☀️ **Summer** - General fishing
- 🍂 **Autumn** - Panfish peak
- ❄️ **Winter** - Reduced activity

### Weather Conditions
- ☀️ Sunny
- 🌧️ Rainy
- ☁️ Cloudy
- ⛈️ Stormy
- 🌨️ Snowy
- 🧊 Frozen
- 🌫️ Foggy

### Time of Day
- 🌅 Morning
- 🌤️ Afternoon
- 🌆 Evening
- 🌙 Night

---

## 🐟 Fish Species

### Freshwater Fish (12 species)
| Fish | Locations | Max Weight | Best Bait |
|------|-----------|------------|-----------|
| Largemouth Bass | Pond, Lake, River | 17.25 lbs | Rubber Worms, Spinnerbait |
| Spotted Bass | Pond, Lake, River | 8.56 lbs | Jerkbait, Spoons |
| Bluegill | Pond, Lake | 4.75 lbs | Breadballs |
| Brown Bullhead Catfish | Pond, Lake | 7.38 lbs | Any |
| Channel Catfish | Lake, River | 58 lbs | Any |
| Black Crappie | Pond, Lake, River | 5 lbs | Breadballs |
| Yellow Perch | Pond, Lake, River | 4.19 lbs | Breadballs, Rubber Worms |
| Chain Pickerel | Pond, Lake, River | 9.38 lbs | Jerkbait, Spoons |
| Spotted Gar | Pond, Lake, River | 27.25 lbs | Any |
| River Trout | Lake, River | 41 lbs | Grubs |
| Redear Sunfish | Pond, Lake | 6.19 lbs | Grubs |

### Fresh/Saltwater Hybrid
| Fish | Locations | Max Weight | Best Bait |
|------|-----------|------------|-----------|
| Striped Bass | River, Ocean | 81.88 lbs | Rubber Worms, Mullet |

### Saltwater Fish (10 species)
| Fish | Locations | Max Weight | Best Bait |
|------|-----------|------------|-----------|
| Snook | River, Ocean | 53.63 lbs | Shrimp, Mullet |
| Speckled Trout | River, Ocean | 17.44 lbs | Shad, Shrimp |
| Red Drum | Ocean | 94.13 lbs | Shrimp, Mullet |
| Red Grouper | Ocean | 42.25 lbs | Cut Squid |
| Red Snapper | Ocean | 50.25 lbs | Cut Squid, Shad |
| King Mackerel | Ocean | 93 lbs | Mullet |
| Tarpon | Ocean | 286.56 lbs | Mullet |
| Sailfish | Ocean | 225.31 lbs | Mullet |
| Black-tip Shark | Ocean | 270 lbs | Any |

---

## 🎣 Equipment

### Fishing Rods
| Rod | Water Type | Special |
|-----|-----------|---------|
| **Wooden Canepole** | Freshwater | Starter rod |
| **Casting Rod** | Freshwater | Standard freshwater |
| **Spinning Rod** | Both | Versatile option |
| **Flyfishing Rod** | River Only | Specialized for rivers |
| **Shark Rod** | Ocean Only | Required for sharks |

### Lures/Bait
#### Freshwater
- 🍞 **Breadballs** - Panfish attractor
- 🪱 **Grubs** - Soft plastics
- 🐛 **Rubber Worms** - Bass favorite
- 🔄 **Spinnerbait** - Flashy lure
- 🐟 **Jerkbait** - Hard-bodied minnow

#### Saltwater
- 🦐 **Shrimp** - Saltwater staple
- 🐟 **Mullet** - Big game bait
- 🦑 **Cut Squid** - Grouper/Snapper
- 🐟 **Shad** - Cut bait

#### Universal
- 🥄 **Spoons** - Metal flashers
- 💦 **Popper** - Topwater action

---

## 👕 Gear (Luck Bonuses)

### Hats 🎩
| Hat | Luck Bonus |
|-----|------------|
| Baseball Cap | +1 |
| Sun Hat | +2 |
| FishMaster's Hat | +3 |

### Coats 🧥
| Coat | Luck Bonus |
|------|------------|
| Sleeveless Vest | +1 |
| Mesh Fishing Jacket | +2 |
| FishMaster's Coat | +3 |

### Boots 👢
| Boots | Luck Bonus |
|-------|------------|
| Tennis Shoes | +1 |
| Wading Boots | +2 |
| FishMaster's Boots | +3 |

**Maximum Luck Bonus: +9** (Full FishMaster's set)

---

## ⚙️ Admin Features

- **Admin Role Configuration** - Set admin permissions
- **Channel Restrictions** - Limit fishing to specific channels
- **Message Cleanup** - Auto-delete game messages
- **Blacklist System** - Block users from playing
- **Disallowed Names Filter** - Content moderation
- **Discord Currency Integration** - Convert fishpoints to server currency

---

## 📊 Rarity System

Planned rarity tiers (to be implemented):
- ⚪ **Common**
- 🟢 **Uncommon**
- 🔵 **Rare**
- 🟣 **Epic**
- 🟡 **Legendary**

---

## 🏗️ Technical Architecture

```
greenacresfishing/
├── main.py           # Core cog class
├── abc.py            # Abstract base classes
├── commands/         # Command handlers
│   ├── admin_commands.py
│   └── user_commands.py
├── common/
│   ├── models.py     # Pydantic data models
│   └── formatting.py # Display utilities
├── databases/
│   ├── fish.py       # Fish species database
│   ├── items.py      # Equipment database
│   └── environment.py # World settings
├── listeners/        # Event handlers
├── tasks/           # Background tasks
└── views/           # Discord UI views
```

### Data Storage
- Uses Pydantic models for type-safe configuration
- JSON-based file storage (db.json)
- Non-blocking save operations
- Per-guild configuration support

---

## 🚀 Development Status

**Version:** 0.0.1 (Early Development)

### Completed
- ✅ Fish species database (22+ fish)
- ✅ Equipment database (rods, lures, gear)
- ✅ Environment system (seasons, weather, locations)
- ✅ User data model
- ✅ Guild configuration system
- ✅ Core cog structure

### Pending
- ⏳ User commands implementation
- ⏳ Admin commands implementation
- ⏳ Fish catching mechanics
- ⏳ Shop system
- ⏳ Inventory management
- ⏳ Rarity assignment
- ⏳ Pricing configuration
- ⏳ Durability system
