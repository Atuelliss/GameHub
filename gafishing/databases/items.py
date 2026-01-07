# Items Database for Greenacres Fishing
# Prices and durability can be adjusted as needed
# Rarity options: "common", "uncommon", "rare", "epic", "legendary" (fill in later)

# ==================== RODS ====================
# water_type: "freshwater", "saltwater", "both", "river_only", "ocean_only"
# special: for rods with unique properties (e.g., shark rod only catches sharks)

RODS_DATABASE = {
    "wooden_canepole": {
        "name": "Wooden Canepole",
        "slot": "rod",
        "water_type": "freshwater",
        "special": None,
        "price": 0,
        "durability": 50,
        "rarity": "common",
        "description": "A simple wooden fishing pole for freshwater fishing.",
    },
    "casting_rod": {
        "name": "Casting Rod",
        "slot": "rod",
        "water_type": "freshwater",
        "special": None,
        "price": 150,
        "durability": 100,
        "rarity": "common",
        "description": "A reliable casting rod for freshwater fishing.",
    },
    "spinning_rod": {
        "name": "Spinning Rod",
        "slot": "rod",
        "water_type": "both",
        "special": None,
        "price": 400,
        "durability": 150,
        "rarity": "uncommon",
        "description": "A versatile spinning rod that works in fresh and saltwater.",
    },
    "flyfishing_rod": {
        "name": "Flyfishing Rod",
        "slot": "rod",
        "water_type": "river_only",
        "special": None,
        "price": 300,
        "durability": 100,
        "rarity": "uncommon",
        "description": "A specialized rod designed for river fishing.",
    },
    "shark_rod": {
        "name": "Shark Rod",
        "slot": "rod",
        "water_type": "ocean_only",
        "special": "shark",
        "price": 800,
        "durability": 200,
        "rarity": "rare",
        "description": "A heavy-duty rod built to handle the ocean's apex predators.",
    },
}


# ==================== LURES ====================
# water_type: "freshwater", "saltwater", "both"
# Lures match with fish preferred_bait in fish.py

LURES_DATABASE = {
    "breadballs": {
        "name": "Breadballs",
        "slot": "lure",
        "water_type": "freshwater",
        "bait_id": "breadballs",
        "price": 1,
        "uses": 1,
        "durability": None,
        "rarity": "common",
        "description": "Simple bread rolled into balls. Attracts panfish.",
    },
    "grubs": {
        "name": "Grubs",
        "slot": "lure",
        "water_type": "freshwater",
        "bait_id": "grubs",
        "price": 2,
        "uses": 1,
        "durability": None,
        "rarity": "common",
        "description": "Soft plastic grubs that wiggle enticingly.",
    },
    "rubber_worms": {
        "name": "Rubber Worm",
        "slot": "lure",
        "water_type": "freshwater",
        "bait_id": "rubber_worms",
        "price": 3,
        "uses": 5,
        "durability": None,
        "rarity": "common",
        "description": "Classic rubber worms that bass can't resist.",
    },
    "spinnerbait": {
        "name": "Spinnerbait",
        "slot": "lure",
        "water_type": "freshwater",
        "bait_id": "spinnerbait",
        "price": 5,
        "uses": 5,
        "durability": None,
        "rarity": "uncommon",
        "description": "A flashy lure with spinning blades.",
    },
    "jerkbait": {
        "name": "Jerkbait",
        "slot": "lure",
        "water_type": "freshwater",
        "bait_id": "jerkbait",
        "price": 5,
        "uses": 5,
        "durability": None,
        "rarity": "uncommon",
        "description": "A hard-bodied lure that mimics injured baitfish.",
    },
    "spoons": {
        "name": "Spoons",
        "slot": "lure",
        "water_type": "both",
        "bait_id": "spoons",
        "price": 4,
        "uses": 10,
        "durability": None,
        "rarity": "common",
        "description": "Metal spoon-shaped lures that flash and wobble.",
    },
    "popper": {
        "name": "Popper",
        "slot": "lure",
        "water_type": "both",
        "bait_id": "popper",
        "price": 6,
        "uses": 5,
        "durability": None,
        "rarity": "uncommon",
        "description": "A topwater lure that creates enticing splashes.",
    },
    "shad": {
        "name": "Shad",
        "slot": "lure",
        "water_type": "saltwater",
        "bait_id": "shad",
        "price": 4,
        "uses": 1,
        "durability": None,
        "rarity": "common",
        "description": "Cut shad bait for saltwater fishing.",
    },
    "cut_squid": {
        "name": "Cut Squid",
        "slot": "lure",
        "water_type": "saltwater",
        "bait_id": "cut_squid",
        "price": 6,
        "uses": 1,
        "durability": None,
        "rarity": "uncommon",
        "description": "Fresh squid cut into strips. Grouper and snapper love it.",
    },
    "shrimp": {
        "name": "Shrimp",
        "slot": "lure",
        "water_type": "saltwater",
        "bait_id": "shrimp",
        "price": 5,
        "uses": 1,
        "durability": None,
        "rarity": "common",
        "description": "Live or frozen shrimp. A saltwater staple.",
    },
    "mullet": {
        "name": "Mullet",
        "slot": "lure",
        "water_type": "saltwater",
        "bait_id": "mullet",
        "price": 8,
        "uses": 1,
        "durability": None,
        "rarity": "uncommon",
        "description": "Mullet baitfish for big game fishing.",
    },
}

# ==================== HATS ====================
# Provides luck bonuses

HATS_DATABASE = {
    "baseball_cap": {
        "name": "Baseball Cap",
        "slot": "hat",
        "luck_bonus": 1,
        "price": 50,
        "durability": None,
        "rarity": "common",
        "description": "A simple cap that keeps the sun out of your eyes.",
    },
    "sun_hat": {
        "name": "Sun Hat",
        "slot": "hat",
        "luck_bonus": 2,
        "price": 150,
        "durability": None,
        "rarity": "uncommon",
        "description": "A wide-brimmed hat for serious anglers.",
    },
    "fishmasters_hat": {
        "name": "FishMaster's Hat",
        "slot": "hat",
        "luck_bonus": 3,
        "price": 500,
        "durability": None,
        "rarity": "rare",
        "fishmaster_token_cost": 1,
        "description": "The legendary hat worn by master fishermen.",
    },
}

# ==================== COATS ====================
# Provides luck bonuses

COATS_DATABASE = {
    "sleeveless_vest": {
        "name": "Sleeveless Vest",
        "slot": "coat",
        "luck_bonus": 1,
        "price": 75,
        "durability": None,
        "rarity": "common",
        "description": "A light vest with plenty of pockets for tackle.",
    },
    "mesh_fishing_jacket": {
        "name": "Mesh Fishing Jacket",
        "slot": "coat",
        "luck_bonus": 2,
        "price": 200,
        "durability": None,
        "rarity": "uncommon",
        "description": "A breathable jacket designed for long fishing trips.",
    },
    "fishmasters_coat": {
        "name": "FishMaster's Coat",
        "slot": "coat",
        "luck_bonus": 3,
        "price": 600,
        "durability": None,
        "rarity": "rare",
        "fishmaster_token_cost": 1,
        "description": "The legendary coat worn by master fishermen.",
    },
}

# ==================== BOOTS ====================
# Provides luck bonuses

BOOTS_DATABASE = {
    "tennis_shoes": {
        "name": "Tennis Shoes",
        "slot": "boots",
        "luck_bonus": 1,
        "price": 50,
        "durability": None,
        "rarity": "common",
        "description": "Basic shoes. Not ideal for fishing, but they work.",
    },
    "wading_boots": {
        "name": "Wading Boots",
        "slot": "boots",
        "luck_bonus": 2,
        "price": 150,
        "durability": None,
        "rarity": "uncommon",
        "description": "Waterproof boots for wading into the water.",
    },
    "fishmasters_boots": {
        "name": "FishMaster's Boots",
        "slot": "boots",
        "luck_bonus": 3,
        "price": 500,
        "durability": None,
        "rarity": "rare",
        "fishmaster_token_cost": 1,
        "description": "The legendary boots worn by master fishermen.",
    },
}

# ==================== COMBINED LOOKUP ====================

ALL_ITEMS = {
    **RODS_DATABASE,
    **LURES_DATABASE,
    **HATS_DATABASE,
    **COATS_DATABASE,
    **BOOTS_DATABASE,
}

# ==================== HELPER FUNCTIONS ====================

def get_items_by_slot(slot: str) -> dict:
    """Returns all items of a specific slot type (rod, lure, hat, coat, boots)."""
    slot = slot.lower()
    databases = {
        "rod": RODS_DATABASE,
        "lure": LURES_DATABASE,
        "hat": HATS_DATABASE,
        "coat": COATS_DATABASE,
        "boots": BOOTS_DATABASE,
    }
    return databases.get(slot, {})


def get_item_by_id(item_id: str) -> dict | None:
    """Returns a specific item by its ID."""
    return ALL_ITEMS.get(item_id.lower())


def get_lures_by_water_type(water_type: str) -> dict:
    """Returns lures compatible with a specific water type."""
    water_type = water_type.lower()
    if water_type == "freshwater":
        return {k: v for k, v in LURES_DATABASE.items() if v["water_type"] in ["freshwater", "both"]}
    elif water_type == "saltwater":
        return {k: v for k, v in LURES_DATABASE.items() if v["water_type"] in ["saltwater", "both"]}
    else:
        return LURES_DATABASE


def get_rods_by_water_type(water_type: str) -> dict:
    """Returns rods compatible with a specific water type."""
    water_type = water_type.lower()
    if water_type == "freshwater":
        return {k: v for k, v in RODS_DATABASE.items() 
                if v["water_type"] in ["freshwater", "both"]}
    elif water_type == "saltwater":
        return {k: v for k, v in RODS_DATABASE.items() 
                if v["water_type"] in ["saltwater", "both", "ocean_only"]}
    else:
        return RODS_DATABASE


def get_rods_for_location(location: str) -> dict:
    """Returns rods that can be used at a specific location."""
    location = location.lower()
    valid_rods = {}
    
    for rod_id, rod in RODS_DATABASE.items():
        water_type = rod["water_type"]
        
        if water_type == "both":
            valid_rods[rod_id] = rod
        elif water_type == "freshwater" and location in ["pond", "lake", "river"]:
            valid_rods[rod_id] = rod
        elif water_type == "saltwater" and location in ["ocean"]:
            valid_rods[rod_id] = rod
        elif water_type == "river_only" and location == "river":
            valid_rods[rod_id] = rod
        elif water_type == "ocean_only" and location == "ocean":
            valid_rods[rod_id] = rod
    
    return valid_rods


def calculate_total_luck_bonus(equipped_gear: dict) -> int:
    """
    Calculates total luck bonus from equipped gear.
    equipped_gear should be a dict like: {"hat": "baseball_cap", "coat": "sleeveless_vest", ...}
    """
    total_luck = 0
    
    for slot, item_id in equipped_gear.items():
        if item_id and item_id in ALL_ITEMS:
            item = ALL_ITEMS[item_id]
            total_luck += item.get("luck_bonus", 0)
    
    return total_luck
