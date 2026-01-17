from .creatures import creature_library
from .constants import common_value, uncommon_value, semi_rare_value, rare_value, very_rare_value, super_rare_value, legendary_value, event_value
import random
from discord import Embed

# Creature Type Modifiers
type_modifiers = { "shiny", "corrupted", "sickly", "muscular", "young", "withered"}
type_normal_mod = {
    "normal": 0,
    "muscular": 5,
    "young": -1,
}
type_rare_mod = {    
    "sickly": -5,    
    "withered": -3,
    "irradiated": -2,
}
type_special_mod = {
    "shiny": 25,
    "corrupted": 5,
    "aberrant": 3,
}
modifier_effect_group = [type_normal_mod, type_rare_mod, type_special_mod]
mod_chance = [70, 20, 10]  # Chances for normal, rare, special modifiers

# Combined modifiers for lookup
all_modifiers = {}
for group in modifier_effect_group:
    all_modifiers.update(group)

# Event Types
type_events = { "valentines", "easter", "halloween", "christmas" }

# DinoCoin value for creatures in creature_library
dino_coin_value = [common_value, uncommon_value, semi_rare_value, rare_value, very_rare_value, super_rare_value, legendary_value, event_value]

# Rarity selection chances (percentages)
rarity_chances = {
    "common": 80,
    "uncommon": 70,
    "semi_rare": 50,
    "rare": 20,
    "very_rare": 15,
    "super_rare": 10,
    "legendary": 5,
    "event": 30
}

# Rarity Bonus during Buddy-usage (percentage)
buddy_bonuses = {
    "common": 0,
    "uncommon": 1,
    "semi_rare": 2,
    "rare": 3,
    "very_rare": 4,
    "super_rare": 5,
    "legendary": 6,
    "event": 7
}

def get_effective_rarity(creature):
    """Get the effective rarity for selection, treating event creatures as 'event' rarity."""
    if creature.get("version") == "event":
        return "event"
    return creature["rarity"]

def select_random_creature(event_mode_enabled=False, event_active_type="", force_rarity=None, force_modifier=None):
    """Select a random creature from creature_library based on rarity chances.
    
    If event_mode_enabled is False, excludes creatures with version 'event' or specific event types.
    If event_mode_enabled is True, includes creatures matching event_active_type.
    Always includes 'core' and 'asa' versions.
    Returns a Discord embed with the selected creature and modifier.
    """
    # Filter creatures based on event_mode_enabled and event_active_type
    available_creatures = {}
    for k, v in creature_library.items():
        version = v.get("version", "core")
        if version in ["core", "asa"]:
            available_creatures[k] = v
        elif event_mode_enabled and version == event_active_type:
            available_creatures[k] = v
    
    if not available_creatures:
        return None

    # Group creatures by rarity
    creatures_by_rarity = {}
    for name, creature in available_creatures.items():
        rarity = get_effective_rarity(creature)
        if rarity not in creatures_by_rarity:
            creatures_by_rarity[rarity] = []
        creatures_by_rarity[rarity].append(name)

    # Select Rarity
    if force_rarity:
        if force_rarity not in creatures_by_rarity:
            return None # Invalid rarity or no creatures of this rarity
        selected_rarity = force_rarity
    else:
        # Prepare weights for available rarities
        available_rarities = list(creatures_by_rarity.keys())
        weights = [rarity_chances.get(r, 0) for r in available_rarities]

        if not available_rarities:
            return None

        # 1. Select Rarity Tier first
        selected_rarity = random.choices(available_rarities, weights=weights, k=1)[0]

    # 2. Select Random Creature from that Tier
    selected_name = random.choice(creatures_by_rarity[selected_rarity])
    creature = creature_library[selected_name]
    
    # Select random value from the creature's value range
    min_val, max_val = creature["value"]
    base_value = random.randint(min_val, max_val)
    
    # Select Modifier
    if force_modifier:
        if force_modifier not in all_modifiers:
             # If user passed invalid modifier, maybe default to normal?
             modifier = "normal"
             modifier_value = 0
        else:
            modifier = force_modifier
            modifier_value = all_modifiers[modifier]
    else:
        # Select modifier group based on mod_chance
        group_index = random.choices(range(len(modifier_effect_group)), weights=mod_chance)[0]
        selected_group = modifier_effect_group[group_index]
        
        # Select random modifier from the group
        modifier = random.choice(list(selected_group.keys()))
        modifier_value = selected_group[modifier]
    
    # Calculate total value
    total_value = base_value + modifier_value
    if total_value < 1:
        total_value = 1
    
    # Prepare the embed
    embed = Embed(title=f"A {modifier} {creature['name']} has appeared!")
    if creature["image"]:
        embed.set_thumbnail(url=creature["image"])
    
    # Optionally add the total value as a field (not specified, but useful)
    embed.add_field(name="DinoCoin Value", value=str(total_value), inline=True)
    
    creature_data = {
        "name": creature["name"],
        "modifier": modifier,
        "rarity": creature["rarity"],
        "value": total_value,
        "image": creature["image"]
    }
    
    return embed, creature_data
