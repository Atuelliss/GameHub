"""
Achievement system for Petcord cog.
Defines all achievements and provides checking logic.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Dict, Callable, Optional, Any
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..common.models import User, Achievement
    import discord


@dataclass
class AchievementDef:
    """Definition of an achievement."""
    id: str
    name: str
    description: str
    category: str  # "adoption", "care", "medals", "home", "special"
    emoji: str
    requirement: str  # Human-readable requirement
    hidden: bool = False  # Hidden until unlocked


# Achievement check functions
def check_first_friend(user: "User") -> bool:
    """Adopt your first pet."""
    return user.total_pets_owned >= 1


def check_growing_family(user: "User") -> bool:
    """Adopt 5 pets."""
    return user.total_pets_owned >= 5


def check_pet_collector(user: "User") -> bool:
    """Adopt 10 pets."""
    return user.total_pets_owned >= 10


def check_dedicated_caretaker(user: "User") -> bool:
    """Adopt 25 pets."""
    return user.total_pets_owned >= 25


def check_pet_whisperer(user: "User") -> bool:
    """Adopt 50 pets."""
    return user.total_pets_owned >= 50


def check_first_gold(user: "User") -> bool:
    """Earn your first Gold Medal."""
    return user.gold_medals >= 1


def check_gold_collector(user: "User") -> bool:
    """Earn 5 Gold Medals."""
    return user.gold_medals >= 5


def check_gold_master(user: "User") -> bool:
    """Earn 10 Gold Medals."""
    return user.gold_medals >= 10


def check_first_silver(user: "User") -> bool:
    """Earn your first Silver Medal."""
    return user.silver_medals >= 1


def check_first_bronze(user: "User") -> bool:
    """Earn your first Bronze Medal."""
    return user.bronze_medals >= 1


def check_medal_streak_3(user: "User") -> bool:
    """Achieve a 3 Gold Medal streak."""
    return user.best_medal_streak >= 3


def check_medal_streak_5(user: "User") -> bool:
    """Achieve a 5 Gold Medal streak."""
    return user.best_medal_streak >= 5


def check_medal_streak_10(user: "User") -> bool:
    """Achieve a 10 Gold Medal streak."""
    return user.best_medal_streak >= 10


def check_homeowner(user: "User") -> bool:
    """Graduate your first pet to Home."""
    return user.total_pets_graduated >= 1


def check_full_house(user: "User") -> bool:
    """Have 5 pets in your Home at once."""
    return len(user.home_pets) >= 5


def check_pet_mansion(user: "User") -> bool:
    """Have 10 pets in your Home at once."""
    return len(user.home_pets) >= 10


def check_gentle_goodbye(user: "User") -> bool:
    """Have a pet pass peacefully of old age."""
    return user.pets_passed_naturally >= 1


def check_many_farewells(user: "User") -> bool:
    """Have 5 pets pass peacefully of old age."""
    return user.pets_passed_naturally >= 5


def check_caring_heart(user: "User") -> bool:
    """Meet 100 pet needs."""
    return user.total_needs_met >= 100


def check_devoted_owner(user: "User") -> bool:
    """Meet 500 pet needs."""
    return user.total_needs_met >= 500


def check_legendary_caretaker(user: "User") -> bool:
    """Meet 1000 pet needs."""
    return user.total_needs_met >= 1000


def check_feeding_frenzy(user: "User") -> bool:
    """Feed pets 50 times."""
    return user.total_feedings >= 50


def check_master_chef(user: "User") -> bool:
    """Feed pets 200 times."""
    return user.total_feedings >= 200


def check_play_time(user: "User") -> bool:
    """Play with pets 50 times."""
    return user.total_play_sessions >= 50


def check_entertainer(user: "User") -> bool:
    """Play with pets 200 times."""
    return user.total_play_sessions >= 200


def check_clean_freak(user: "User") -> bool:
    """Groom pets 50 times."""
    return user.total_grooming_sessions >= 50


def check_spa_master(user: "User") -> bool:
    """Groom pets 200 times."""
    return user.total_grooming_sessions >= 200


def check_best_friends(user: "User") -> bool:
    """Achieve maximum bond (100) with a pet."""
    return user.highest_bond_achieved >= 100


def check_strong_bond(user: "User") -> bool:
    """Achieve 75+ bond with a pet."""
    return user.highest_bond_achieved >= 75


def check_long_life(user: "User") -> bool:
    """Have a pet live for 30 days."""
    return user.longest_pet_lifespan >= 30


def check_elder_care(user: "User") -> bool:
    """Have a pet live for 50 days."""
    return user.longest_pet_lifespan >= 50


def check_treat_giver(user: "User") -> bool:
    """Give 25 treats."""
    return user.total_treats_given >= 25


def check_treat_master(user: "User") -> bool:
    """Give 100 treats."""
    return user.total_treats_given >= 100


def check_affectionate(user: "User") -> bool:
    """Pet your pets 50 times."""
    return user.total_petting_sessions >= 50


def check_total_interactions(user: "User") -> bool:
    """Perform 500 total interactions."""
    return user.total_interactions >= 500


def check_interaction_master(user: "User") -> bool:
    """Perform 2000 total interactions."""
    return user.total_interactions >= 2000


# Master achievement registry
ACHIEVEMENTS: Dict[str, AchievementDef] = {
    # Adoption achievements
    "first_friend": AchievementDef(
        id="first_friend",
        name="First Friend",
        description="Adopt your first pet",
        category="adoption",
        emoji="🐣",
        requirement="Adopt 1 pet"
    ),
    "growing_family": AchievementDef(
        id="growing_family",
        name="Growing Family",
        description="Build a growing pet family",
        category="adoption",
        emoji="👨‍👩‍👧‍👦",
        requirement="Adopt 5 pets"
    ),
    "pet_collector": AchievementDef(
        id="pet_collector",
        name="Pet Collector",
        description="You really love adopting pets!",
        category="adoption",
        emoji="📦",
        requirement="Adopt 10 pets"
    ),
    "dedicated_caretaker": AchievementDef(
        id="dedicated_caretaker",
        name="Dedicated Caretaker",
        description="A truly dedicated pet owner",
        category="adoption",
        emoji="💝",
        requirement="Adopt 25 pets"
    ),
    "pet_whisperer": AchievementDef(
        id="pet_whisperer",
        name="Pet Whisperer",
        description="You have a special connection with animals",
        category="adoption",
        emoji="✨",
        requirement="Adopt 50 pets"
    ),
    
    # Medal achievements
    "first_gold": AchievementDef(
        id="first_gold",
        name="Golden Touch",
        description="Earn your first Gold Medal",
        category="medals",
        emoji="🥇",
        requirement="Earn 1 Gold Medal"
    ),
    "gold_collector": AchievementDef(
        id="gold_collector",
        name="Gold Collector",
        description="Consistently excellent care",
        category="medals",
        emoji="🏆",
        requirement="Earn 5 Gold Medals"
    ),
    "gold_master": AchievementDef(
        id="gold_master",
        name="Gold Master",
        description="Master of pet care",
        category="medals",
        emoji="👑",
        requirement="Earn 10 Gold Medals"
    ),
    "first_silver": AchievementDef(
        id="first_silver",
        name="Silver Start",
        description="Earn your first Silver Medal",
        category="medals",
        emoji="🥈",
        requirement="Earn 1 Silver Medal"
    ),
    "first_bronze": AchievementDef(
        id="first_bronze",
        name="Bronze Beginning",
        description="Earn your first Bronze Medal",
        category="medals",
        emoji="🥉",
        requirement="Earn 1 Bronze Medal"
    ),
    "medal_streak_3": AchievementDef(
        id="medal_streak_3",
        name="Hot Streak",
        description="3 Gold Medals in a row!",
        category="medals",
        emoji="🔥",
        requirement="3 Gold Medal streak"
    ),
    "medal_streak_5": AchievementDef(
        id="medal_streak_5",
        name="On Fire",
        description="5 Gold Medals in a row!",
        category="medals",
        emoji="💫",
        requirement="5 Gold Medal streak"
    ),
    "medal_streak_10": AchievementDef(
        id="medal_streak_10",
        name="Unstoppable",
        description="10 Gold Medals in a row!",
        category="medals",
        emoji="🌟",
        requirement="10 Gold Medal streak",
        hidden=True
    ),
    
    # Home achievements
    "homeowner": AchievementDef(
        id="homeowner",
        name="Homeowner",
        description="Graduate your first pet to Home",
        category="home",
        emoji="🏠",
        requirement="Graduate 1 pet"
    ),
    "full_house": AchievementDef(
        id="full_house",
        name="Full House",
        description="Your home is getting crowded!",
        category="home",
        emoji="🏡",
        requirement="Have 5 pets in Home"
    ),
    "pet_mansion": AchievementDef(
        id="pet_mansion",
        name="Pet Mansion",
        description="A mansion full of happy pets",
        category="home",
        emoji="🏰",
        requirement="Have 10 pets in Home"
    ),
    "gentle_goodbye": AchievementDef(
        id="gentle_goodbye",
        name="Gentle Goodbye",
        description="A pet passed peacefully of old age",
        category="home",
        emoji="🕊️",
        requirement="1 peaceful passing"
    ),
    "many_farewells": AchievementDef(
        id="many_farewells",
        name="Many Farewells",
        description="You've said goodbye to many old friends",
        category="home",
        emoji="🪦",
        requirement="5 peaceful passings"
    ),
    
    # Care achievements
    "caring_heart": AchievementDef(
        id="caring_heart",
        name="Caring Heart",
        description="You truly care for your pets",
        category="care",
        emoji="💕",
        requirement="Meet 100 needs"
    ),
    "devoted_owner": AchievementDef(
        id="devoted_owner",
        name="Devoted Owner",
        description="Exceptionally devoted to pet care",
        category="care",
        emoji="💖",
        requirement="Meet 500 needs"
    ),
    "legendary_caretaker": AchievementDef(
        id="legendary_caretaker",
        name="Legendary Caretaker",
        description="A legend in pet care",
        category="care",
        emoji="🌈",
        requirement="Meet 1000 needs"
    ),
    "feeding_frenzy": AchievementDef(
        id="feeding_frenzy",
        name="Feeding Frenzy",
        description="Your pets never go hungry",
        category="care",
        emoji="🍖",
        requirement="Feed 50 times"
    ),
    "master_chef": AchievementDef(
        id="master_chef",
        name="Master Chef",
        description="A culinary expert for pets",
        category="care",
        emoji="👨‍🍳",
        requirement="Feed 200 times"
    ),
    "play_time": AchievementDef(
        id="play_time",
        name="Play Time",
        description="Fun is your middle name",
        category="care",
        emoji="🎾",
        requirement="Play 50 times"
    ),
    "entertainer": AchievementDef(
        id="entertainer",
        name="Entertainer",
        description="The ultimate pet entertainer",
        category="care",
        emoji="🎪",
        requirement="Play 200 times"
    ),
    "clean_freak": AchievementDef(
        id="clean_freak",
        name="Clean Freak",
        description="Cleanliness is next to... pet happiness",
        category="care",
        emoji="🧹",
        requirement="Groom 50 times"
    ),
    "spa_master": AchievementDef(
        id="spa_master",
        name="Spa Master",
        description="Your pets are always pristine",
        category="care",
        emoji="💆",
        requirement="Groom 200 times"
    ),
    "treat_giver": AchievementDef(
        id="treat_giver",
        name="Treat Giver",
        description="Spreading sweetness",
        category="care",
        emoji="🍬",
        requirement="Give 25 treats"
    ),
    "treat_master": AchievementDef(
        id="treat_master",
        name="Treat Master",
        description="The treat dispensing champion",
        category="care",
        emoji="🍭",
        requirement="Give 100 treats"
    ),
    "affectionate": AchievementDef(
        id="affectionate",
        name="Affectionate",
        description="Your pets feel so loved",
        category="care",
        emoji="🤗",
        requirement="Pet 50 times"
    ),
    
    # Special achievements
    "best_friends": AchievementDef(
        id="best_friends",
        name="Best Friends Forever",
        description="Achieve maximum bond with a pet",
        category="special",
        emoji="💯",
        requirement="100 bond"
    ),
    "strong_bond": AchievementDef(
        id="strong_bond",
        name="Strong Bond",
        description="Your pet really trusts you",
        category="special",
        emoji="💗",
        requirement="75+ bond"
    ),
    "long_life": AchievementDef(
        id="long_life",
        name="Long Life",
        description="Your pet lived a long, happy life",
        category="special",
        emoji="📅",
        requirement="Pet lives 30 days"
    ),
    "elder_care": AchievementDef(
        id="elder_care",
        name="Elder Care",
        description="Expert at caring for senior pets",
        category="special",
        emoji="👴",
        requirement="Pet lives 50 days"
    ),
    "total_interactions": AchievementDef(
        id="total_interactions",
        name="Dedicated",
        description="500 total interactions with pets",
        category="special",
        emoji="🎮",
        requirement="500 interactions"
    ),
    "interaction_master": AchievementDef(
        id="interaction_master",
        name="Interaction Master",
        description="2000 total interactions with pets",
        category="special",
        emoji="⚡",
        requirement="2000 interactions",
        hidden=True
    ),
}

# Map achievement IDs to their check functions
ACHIEVEMENT_CHECKS: Dict[str, Callable[["User"], bool]] = {
    "first_friend": check_first_friend,
    "growing_family": check_growing_family,
    "pet_collector": check_pet_collector,
    "dedicated_caretaker": check_dedicated_caretaker,
    "pet_whisperer": check_pet_whisperer,
    "first_gold": check_first_gold,
    "gold_collector": check_gold_collector,
    "gold_master": check_gold_master,
    "first_silver": check_first_silver,
    "first_bronze": check_first_bronze,
    "medal_streak_3": check_medal_streak_3,
    "medal_streak_5": check_medal_streak_5,
    "medal_streak_10": check_medal_streak_10,
    "homeowner": check_homeowner,
    "full_house": check_full_house,
    "pet_mansion": check_pet_mansion,
    "gentle_goodbye": check_gentle_goodbye,
    "many_farewells": check_many_farewells,
    "caring_heart": check_caring_heart,
    "devoted_owner": check_devoted_owner,
    "legendary_caretaker": check_legendary_caretaker,
    "feeding_frenzy": check_feeding_frenzy,
    "master_chef": check_master_chef,
    "play_time": check_play_time,
    "entertainer": check_entertainer,
    "clean_freak": check_clean_freak,
    "spa_master": check_spa_master,
    "treat_giver": check_treat_giver,
    "treat_master": check_treat_master,
    "affectionate": check_affectionate,
    "best_friends": check_best_friends,
    "strong_bond": check_strong_bond,
    "long_life": check_long_life,
    "elder_care": check_elder_care,
    "total_interactions": check_total_interactions,
    "interaction_master": check_interaction_master,
}


def get_achievement(achievement_id: str) -> Optional[AchievementDef]:
    """Get an achievement definition by ID."""
    return ACHIEVEMENTS.get(achievement_id)


def get_earned_achievement_ids(user: "User") -> List[str]:
    """Get list of achievement IDs the user has earned."""
    return [a.id for a in user.achievements]


def check_new_achievements(user: "User") -> List[str]:
    """
    Check for newly earned achievements.
    
    Returns list of newly earned achievement IDs (not already in user.achievements).
    """
    earned_ids = get_earned_achievement_ids(user)
    new_achievements = []
    
    for ach_id, check_func in ACHIEVEMENT_CHECKS.items():
        if ach_id not in earned_ids:
            try:
                if check_func(user):
                    new_achievements.append(ach_id)
            except Exception:
                # Skip if check fails
                pass
    
    return new_achievements


def award_achievement(user: "User", achievement_id: str) -> bool:
    """
    Award an achievement to the user.
    
    Returns True if awarded, False if already had it.
    """
    from ..common.models import Achievement
    
    earned_ids = get_earned_achievement_ids(user)
    if achievement_id in earned_ids:
        return False
    
    if achievement_id not in ACHIEVEMENTS:
        return False
    
    user.achievements.append(Achievement(
        id=achievement_id,
        timestamp=time.time()
    ))
    return True


def get_achievements_by_category() -> Dict[str, List[AchievementDef]]:
    """Get all achievements organized by category."""
    by_category: Dict[str, List[AchievementDef]] = {}
    
    for ach in ACHIEVEMENTS.values():
        if ach.category not in by_category:
            by_category[ach.category] = []
        by_category[ach.category].append(ach)
    
    return by_category


def get_total_achievement_count() -> int:
    """Get total number of achievements."""
    return len(ACHIEVEMENTS)


def get_category_display_order() -> List[str]:
    """Get the display order for achievement categories."""
    return ["adoption", "medals", "home", "care", "special"]


async def check_and_award_achievements(user: "User") -> List[str]:
    """
    Check for new achievements and award them.
    
    Returns list of newly awarded achievement IDs.
    """
    new_ids = check_new_achievements(user)
    awarded = []
    
    for ach_id in new_ids:
        if award_achievement(user, ach_id):
            awarded.append(ach_id)
    
    return awarded


def build_achievement_unlock_embed(achievement_ids: List[str]) -> Optional["discord.Embed"]:
    """
    Build an embed showing newly unlocked achievements.
    
    Returns None if no achievements provided.
    """
    import discord
    
    if not achievement_ids:
        return None
    
    if len(achievement_ids) == 1:
        ach = ACHIEVEMENTS.get(achievement_ids[0])
        if not ach:
            return None
        
        embed = discord.Embed(
            title="🏆 Achievement Unlocked!",
            description=f"{ach.emoji} **{ach.name}**\n{ach.description}",
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Requirement: {ach.requirement}")
    else:
        # Multiple achievements
        lines = []
        for ach_id in achievement_ids:
            ach = ACHIEVEMENTS.get(ach_id)
            if ach:
                lines.append(f"{ach.emoji} **{ach.name}** — {ach.description}")
        
        embed = discord.Embed(
            title=f"🏆 {len(achievement_ids)} Achievements Unlocked!",
            description="\n".join(lines),
            color=discord.Color.gold()
        )
    
    return embed
