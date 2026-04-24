"""
Helper functions for daily tracking and care calculations.
"""

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..common.models import User, Pet, DailyCareScore


def award_graduation_petcoins(user_data: "User", pet: "Pet", medal: str) -> int:
    """
    Calculate and award petcoins for graduation based on medal and days raised.
    
    Formula: (days × 2) + base_medal_value
    
    Args:
        user_data: The user data to update
        pet: The pet being graduated
        medal: The medal earned ("gold", "silver", "bronze", or "")
        
    Returns:
        The amount of petcoins awarded
    """
    from ..common.constants import MEDAL_PETCOIN_VALUES
    
    # No medal = no petcoins
    if not medal:
        return 0
    
    # Get base value from medal
    base_value = MEDAL_PETCOIN_VALUES.get(medal, 0)
    if base_value == 0:
        return 0
    
    # Calculate final amount: (days × 2) + base_medal_value
    days_bonus = int(pet.age_days) * 2
    petcoins_earned = days_bonus + base_value
    
    # Update user's petcoin balances
    user_data.current_petcoin += petcoins_earned
    user_data.petcoin_earned_from_medals += petcoins_earned
    
    # Update most_petcoin_earned if this is a new high single-award
    if petcoins_earned > user_data.most_petcoin_earned:
        user_data.most_petcoin_earned = petcoins_earned
    
    return petcoins_earned


def initialize_daily_tracking(user_data: "User") -> None:
    """Start tracking for a new day."""
    from ..common.models import DailyCareScore
    
    pet = user_data.current_pet
    if not pet:
        return
    
    day_number = int(pet.age_days) + 1
    
    user_data.current_day_start = time.time()
    user_data.current_day_scores = DailyCareScore(
        day_number=day_number,
        date_timestamp=time.time()
    )


def update_daily_tracking(user_data: "User", pet: "Pet", action: str) -> None:
    """Update tracking based on action performed."""
    if not user_data.current_day_scores:
        initialize_daily_tracking(user_data)
    
    scores = user_data.current_day_scores
    if not scores:
        return
    
    # Track action counts
    action_map = {
        "feed": "times_fed",
        "play": "times_played",
        "groom": "times_groomed",
        "rest": "times_rested",
        "pet": "times_petted",
        "treat": "times_treated",
    }
    
    if action in action_map:
        attr = action_map[action]
        setattr(scores, attr, getattr(scores, attr, 0) + 1)


def calculate_daily_score(user_data: "User", pet: "Pet") -> float:
    """Calculate the daily care score (0-100)."""
    if not user_data.current_day_scores:
        return 0.0
    
    scores = user_data.current_day_scores
    
    # Feeding score: Did they keep hunger above 40?
    # Ideal: 2+ feedings per day
    if scores.times_fed >= 2:
        feeding_score = 100.0
    elif scores.times_fed >= 1:
        feeding_score = 50.0
    else:
        feeding_score = max(0.0, pet.hunger - 20)  # Some credit if pet isn't starving
    
    # Happiness score: Based on current happiness + interactions
    happiness_base = pet.happiness
    happiness_bonus = (scores.times_played * 10) + (scores.times_petted * 5)
    happiness_score = min(100.0, happiness_base + happiness_bonus)
    
    # Cleanliness score: Did they groom?
    if scores.times_groomed >= 1:
        cleanliness_score = 100.0
    elif pet.cleanliness > 50:
        cleanliness_score = pet.cleanliness
    else:
        cleanliness_score = 30.0
    
    # Energy score: Did they let pet rest?
    if scores.times_rested >= 1:
        energy_score = 100.0
    elif pet.energy > 30:
        energy_score = pet.energy
    else:
        energy_score = 20.0
    
    # Bonus score: Extra interactions (treats, petting)
    bonus_interactions = scores.times_petted + scores.times_treated
    bonus_score = min(100.0, bonus_interactions * 25)
    
    # Weighted average
    final_score = (
        feeding_score * 0.30 +
        happiness_score * 0.25 +
        cleanliness_score * 0.20 +
        energy_score * 0.15 +
        bonus_score * 0.10
    )
    
    # Store component scores
    scores.feeding_score = feeding_score
    scores.happiness_score = happiness_score
    scores.cleanliness_score = cleanliness_score
    scores.energy_score = energy_score
    scores.bonus_score = bonus_score
    scores.final_score = final_score
    scores.rating = get_rating_from_score(final_score)
    
    return final_score


def get_rating_from_score(score: float) -> str:
    """Get rating string from score."""
    if score >= 95:
        return "perfect"
    elif score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "fair"
    elif score >= 20:
        return "poor"
    else:
        return "critical"


def get_rating_display(rating: str) -> str:
    """Get emoji display for rating."""
    displays = {
        "perfect": "⭐⭐⭐⭐⭐ Perfect",
        "excellent": "⭐⭐⭐⭐ Excellent",
        "good": "⭐⭐⭐ Good",
        "fair": "⭐⭐ Fair",
        "poor": "⭐ Poor",
        "critical": "💀 Critical"
    }
    return displays.get(rating, "Unknown")


def get_rating_emoji(rating: str) -> str:
    """Get single emoji for rating."""
    emojis = {
        "perfect": "🌟",
        "excellent": "⭐",
        "good": "✨",
        "fair": "😐",
        "poor": "😟",
        "critical": "💀"
    }
    return emojis.get(rating, "❓")
