"""Database package for Petcord cog."""

from .species import (
    SpeciesData,
    SPECIES_DATABASE,
    DECAY_MULTIPLIERS,
    RARITY_WEIGHTS,
    get_species,
    get_all_species,
    get_species_by_category,
    get_species_by_rarity,
    get_random_species,
    get_decay_multiplier,
    get_species_count,
    get_category_counts,
)

from .appearance import (
    RARE_COATS,
    MYTHICAL_COATS,
    generate_appearance,
    get_rarity_emoji,
    get_rarity_color,
    format_appearance,
    is_special_coat,
    is_mythical_coat,
)

from .lifecycle import (
    get_life_stage,
    check_stage_transition,
    get_stage_emoji,
    get_stage_display,
    get_stage_progress,
    get_days_until_next_stage,
    is_ready_for_graduation,
)

from .achievements import (
    AchievementDef,
    ACHIEVEMENTS,
    ACHIEVEMENT_CHECKS,
    get_achievement,
    get_earned_achievement_ids,
    check_new_achievements,
    award_achievement,
    get_achievements_by_category,
    get_total_achievement_count,
    get_category_display_order,
    check_and_award_achievements,
    build_achievement_unlock_embed,
)

__all__ = [
    # Species
    "SpeciesData",
    "SPECIES_DATABASE",
    "DECAY_MULTIPLIERS",
    "RARITY_WEIGHTS",
    "get_species",
    "get_all_species",
    "get_species_by_category",
    "get_species_by_rarity",
    "get_random_species",
    "get_decay_multiplier",
    "get_species_count",
    "get_category_counts",
    # Appearance
    "RARE_COATS",
    "MYTHICAL_COATS",
    "generate_appearance",
    "get_rarity_emoji",
    "get_rarity_color",
    "format_appearance",
    "is_special_coat",
    "is_mythical_coat",
    # Lifecycle
    "get_life_stage",
    "check_stage_transition",
    "get_stage_emoji",
    "get_stage_display",
    "get_stage_progress",
    "get_days_until_next_stage",
    "is_ready_for_graduation",
    # Achievements
    "AchievementDef",
    "ACHIEVEMENTS",
    "ACHIEVEMENT_CHECKS",
    "get_achievement",
    "get_earned_achievement_ids",
    "check_new_achievements",
    "award_achievement",
    "get_achievements_by_category",
    "get_total_achievement_count",
    "get_category_display_order",
    "check_and_award_achievements",
    "build_achievement_unlock_embed",
]
