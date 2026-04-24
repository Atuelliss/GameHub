"""
Pet lifecycle utilities - life stages, aging, graduation readiness.
"""

from typing import Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from ..common.models import Pet

from .species import get_species
from ..common.constants import STAGE_THRESHOLDS


def get_life_stage(pet: "Pet") -> str:
    """Determine pet's life stage based on age and species lifespan."""
    species = get_species(pet.species_id)
    if not species:
        return "baby"
    
    thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
    
    # Check stages in reverse order (highest first)
    if pet.age_days >= thresholds.get("senior", 999):
        return "senior"
    elif pet.age_days >= thresholds.get("adult", 999):
        return "adult"
    elif pet.age_days >= thresholds.get("juvenile", 999):
        return "juvenile"
    else:
        return "baby"


def check_stage_transition(pet: "Pet") -> Tuple[bool, str, str]:
    """
    Check if pet should transition to a new life stage.
    
    Returns:
        (changed, old_stage, new_stage) tuple
    """
    new_stage = get_life_stage(pet)
    
    if new_stage != pet.life_stage:
        old_stage = pet.life_stage
        return (True, old_stage, new_stage)
    
    return (False, pet.life_stage, pet.life_stage)


def get_stage_emoji(stage: str) -> str:
    """Get emoji for a life stage."""
    emojis = {
        "baby": "🍼",
        "juvenile": "🌱",
        "adult": "🌟",
        "senior": "👴"
    }
    return emojis.get(stage, "❓")


def get_stage_display(pet: "Pet") -> str:
    """Get full display text for pet's current stage."""
    stage = pet.life_stage
    emoji = get_stage_emoji(stage)
    return f"{stage.title()} {emoji}"


def get_stage_progress(pet: "Pet") -> str:
    """Get display text showing progress through current stage."""
    species = get_species(pet.species_id)
    if not species:
        return f"Day {pet.age_days}"
    
    thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
    
    # Determine the end day of current stage
    stage = pet.life_stage
    if stage == "baby":
        start_day = 0
        end_day = thresholds.get("juvenile", 4)
    elif stage == "juvenile":
        start_day = thresholds.get("juvenile", 4)
        end_day = thresholds.get("adult", 10)
    elif stage == "adult":
        start_day = thresholds.get("adult", 10)
        end_day = thresholds.get("senior", 21)
    else:  # senior
        start_day = thresholds.get("senior", 21)
        end_day = thresholds.get("max_age", 28)
    
    days_in_stage = pet.age_days - start_day
    stage_length = end_day - start_day
    
    return f"Day {days_in_stage + 1}/{stage_length}"


def get_days_until_next_stage(pet: "Pet") -> int:
    """Get number of days until pet advances to next stage."""
    species = get_species(pet.species_id)
    if not species:
        return 0
    
    thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
    
    stage = pet.life_stage
    if stage == "baby":
        next_threshold = thresholds.get("juvenile", 4)
    elif stage == "juvenile":
        next_threshold = thresholds.get("adult", 10)
    elif stage == "adult":
        next_threshold = thresholds.get("senior", 21)
    else:  # senior - no next stage
        return 0
    
    return max(0, int(next_threshold - pet.age_days))


def is_ready_for_graduation(pet: "Pet") -> bool:
    """Check if pet is ready to graduate to Home."""
    return (
        pet.life_stage in ("adult", "senior") and 
        not pet.is_in_home and 
        pet.ready_to_graduate
    )
