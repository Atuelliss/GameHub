"""
Appearance generation for pets.
"""

import random
from typing import Tuple

from .species import SpeciesData


# Rare coat variants that can appear on any species (5% chance)
RARE_COATS = ["Albino", "Melanistic", "Leucistic", "Piebald"]

# Mythical coat variants (0.5% chance)
MYTHICAL_COATS = ["Rainbow", "Galaxy", "Crystal", "Shadow"]


def generate_appearance(species: SpeciesData) -> Tuple[str, str, str]:
    """
    Generate random coat color, pattern, and calculate final rarity for a pet.
    
    Args:
        species: The species data for the pet
        
    Returns:
        Tuple of (coat_color, pattern, final_rarity)
    """
    # Roll for special coat variants
    roll = random.random() * 100  # 0-100
    
    if roll < 0.5 and species.category != "aquatic":
        # 0.5% chance for mythical coat (not for aquatic)
        coat = random.choice(MYTHICAL_COATS)
        # Mythical coat upgrades rarity to mythical
        final_rarity = "mythical"
    elif roll < 5.5 and species.category != "aquatic":
        # 5% chance for rare coat variant (not for aquatic - they have specific colorations)
        coat = random.choice(RARE_COATS)
        # Rare coat upgrades rarity by one tier (max legendary)
        final_rarity = _upgrade_rarity(species.rarity)
    else:
        # Normal coat from species pool
        coat = random.choice(species.possible_coats) if species.possible_coats else "Standard"
        final_rarity = species.rarity
    
    # Select pattern
    pattern = random.choice(species.possible_patterns) if species.possible_patterns else "Solid"
    
    return coat, pattern, final_rarity


def _upgrade_rarity(current_rarity: str) -> str:
    """Upgrade rarity by one tier."""
    rarity_order = ["common", "uncommon", "rare", "very_rare", "legendary", "mythical"]
    try:
        current_index = rarity_order.index(current_rarity)
        # Upgrade by one, max at legendary (mythical only from mythical coats)
        new_index = min(current_index + 1, len(rarity_order) - 2)  # Max legendary
        return rarity_order[new_index]
    except ValueError:
        return current_rarity


def get_rarity_emoji(rarity: str) -> str:
    """Get the emoji representation for a rarity level."""
    rarity_emojis = {
        "common": "⭐",
        "uncommon": "⭐⭐",
        "rare": "⭐⭐⭐",
        "very_rare": "⭐⭐⭐⭐",
        "legendary": "⭐⭐⭐⭐⭐",
        "mythical": "🌟",
    }
    return rarity_emojis.get(rarity, "⭐")


def get_rarity_color(rarity: str) -> int:
    """Get the Discord embed color for a rarity level."""
    rarity_colors = {
        "common": 0x9E9E9E,      # Gray
        "uncommon": 0x4CAF50,    # Green
        "rare": 0x2196F3,        # Blue
        "very_rare": 0x9C27B0,   # Purple
        "legendary": 0xFF9800,   # Orange
        "mythical": 0xE91E63,    # Pink
    }
    return rarity_colors.get(rarity, 0x9E9E9E)


def format_appearance(coat: str, pattern: str) -> str:
    """Format coat and pattern into a readable appearance string."""
    if pattern.lower() == "solid":
        return coat
    return f"{coat} ({pattern})"


def is_special_coat(coat: str) -> bool:
    """Check if a coat is a rare or mythical variant."""
    return coat in RARE_COATS or coat in MYTHICAL_COATS


def is_mythical_coat(coat: str) -> bool:
    """Check if a coat is a mythical variant."""
    return coat in MYTHICAL_COATS
