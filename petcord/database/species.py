"""
Species database containing all 100 animal species.
"""

import random
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class SpeciesData(BaseModel):
    """Data structure for a species."""
    id: str
    name: str
    emoji: str
    category: str  # "dogs", "cats", "small_mammals", "reptiles", "birds", "aquatic", "exotic"
    rarity: str  # "common", "uncommon", "rare", "very_rare", "legendary", "mythical"
    
    # Behavioral stats
    activity_level: str  # "very_low", "low", "medium", "high", "very_high", "extremely_high"
    social_need: str  # "solitary", "low", "moderate", "high", "very_high", "extremely_high"
    grooming_need: str  # "minimal", "moderate", "frequent", "very_frequent"
    diet_type: str
    lifespan: str  # "short", "medium", "long", "extended"
    care_difficulty: str  # "easy", "medium", "hard", "expert"
    
    # Appearance options
    possible_coats: List[str] = Field(default_factory=list)
    possible_patterns: List[str] = Field(default_factory=list)
    
    # Unique traits
    special_needs: str = ""
    temperament: str = ""
    unique_interaction: str = ""
    unique_interaction_effect: str = ""


# =============================================================================
# SPECIES DATABASE - All 100 Species
# =============================================================================

SPECIES_DATABASE: Dict[str, SpeciesData] = {}


# -----------------------------------------------------------------------------
# DOGS (15 Species) - IDs 1-15
# -----------------------------------------------------------------------------

SPECIES_DATABASE["golden_retriever"] = SpeciesData(
    id="golden_retriever",
    name="Golden Retriever",
    emoji="🐕",
    category="dogs",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="frequent",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Golden", "Cream", "Light Golden", "Dark Golden"],
    possible_patterns=["Solid"],
    special_needs="Daily exercise, swimming optional activity",
    temperament="Friendly, eager to please, playful",
    unique_interaction="Fetch game",
    unique_interaction_effect="+extra Happiness"
)

SPECIES_DATABASE["labrador_retriever"] = SpeciesData(
    id="labrador_retriever",
    name="Labrador Retriever",
    emoji="🐕",
    category="dogs",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Black", "Chocolate", "Yellow", "Fox Red"],
    possible_patterns=["Solid"],
    special_needs="Loves water, high food motivation",
    temperament="Outgoing, active, gentle",
    unique_interaction="Treat training",
    unique_interaction_effect="+Bond bonus"
)

SPECIES_DATABASE["german_shepherd"] = SpeciesData(
    id="german_shepherd",
    name="German Shepherd",
    emoji="🐕‍🦺",
    category="dogs",
    rarity="uncommon",
    activity_level="high",
    social_need="high",
    grooming_need="frequent",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Black/Tan", "Sable", "All Black", "White"],
    possible_patterns=["Saddle", "Bicolor"],
    special_needs="Mental stimulation, training activities",
    temperament="Loyal, intelligent, protective",
    unique_interaction="Training session",
    unique_interaction_effect="+Bond, +Happiness"
)

SPECIES_DATABASE["chihuahua"] = SpeciesData(
    id="chihuahua",
    name="Chihuahua",
    emoji="🐕",
    category="dogs",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="extended",
    care_difficulty="easy",
    possible_coats=["Fawn", "Black", "White", "Chocolate", "Cream"],
    possible_patterns=["Solid", "Bicolor", "Tricolor", "Spotted"],
    special_needs="Temperature sensitive, small portions",
    temperament="Sassy, loyal, alert",
    unique_interaction="Carry in pocket",
    unique_interaction_effect="+Happiness from closeness"
)

SPECIES_DATABASE["husky"] = SpeciesData(
    id="husky",
    name="Husky",
    emoji="🐺",
    category="dogs",
    rarity="uncommon",
    activity_level="very_high",
    social_need="high",
    grooming_need="frequent",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Black/White", "Gray/White", "Red/White", "All White", "Agouti"],
    possible_patterns=["Bicolor with mask markings"],
    special_needs="Extensive exercise, temperature regulation, howling vocal",
    temperament="Energetic, mischievous, talkative",
    unique_interaction="Howl together",
    unique_interaction_effect="+Happiness, +Bond"
)

SPECIES_DATABASE["poodle"] = SpeciesData(
    id="poodle",
    name="Poodle",
    emoji="🐩",
    category="dogs",
    rarity="uncommon",
    activity_level="high",
    social_need="high",
    grooming_need="very_frequent",
    diet_type="omnivore",
    lifespan="extended",
    care_difficulty="medium",
    possible_coats=["Black", "White", "Apricot", "Silver", "Brown", "Cream", "Blue", "Gray"],
    possible_patterns=["Solid", "Phantom", "Parti"],
    special_needs="Professional grooming, mentally stimulating activities",
    temperament="Intelligent, proud, athletic",
    unique_interaction="Grooming styling",
    unique_interaction_effect="+Cleanliness boost, unlockable styles"
)

SPECIES_DATABASE["bulldog"] = SpeciesData(
    id="bulldog",
    name="English Bulldog",
    emoji="🐕",
    category="dogs",
    rarity="uncommon",
    activity_level="low",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="medium",
    care_difficulty="medium",
    possible_coats=["White", "Fawn", "Red"],
    possible_patterns=["Solid", "Brindle", "Piebald"],
    special_needs="Wrinkle cleaning, temperature sensitivity, avoid overexertion",
    temperament="Calm, stubborn, affectionate",
    unique_interaction="Wrinkle cleaning mini-game",
    unique_interaction_effect="+Cleanliness, +Health"
)

SPECIES_DATABASE["beagle"] = SpeciesData(
    id="beagle",
    name="Beagle",
    emoji="🐕",
    category="dogs",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Tricolor", "Lemon/White", "Red/White", "Chocolate"],
    possible_patterns=["Tricolor", "Bicolor"],
    special_needs="Scent enrichment, secure environment (escape artist)",
    temperament="Curious, merry, stubborn",
    unique_interaction="Sniff trail game",
    unique_interaction_effect="+Happiness, +Mental stimulation"
)

SPECIES_DATABASE["corgi"] = SpeciesData(
    id="corgi",
    name="Pembroke Welsh Corgi",
    emoji="🐕",
    category="dogs",
    rarity="uncommon",
    activity_level="high",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Red", "Sable", "Fawn", "Black/Tan", "Tricolor"],
    possible_patterns=["Bicolor with white markings"],
    special_needs="Weight management, back health",
    temperament="Playful, smart, bossy",
    unique_interaction="Herding mini-game",
    unique_interaction_effect="+Happiness"
)

SPECIES_DATABASE["shiba_inu"] = SpeciesData(
    id="shiba_inu",
    name="Shiba Inu",
    emoji="🐕",
    category="dogs",
    rarity="uncommon",
    activity_level="medium",
    social_need="moderate",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Red", "Sesame", "Black/Tan", "Cream"],
    possible_patterns=["Urajiro (light underside markings)"],
    special_needs="Secure area, patience with training",
    temperament="Independent, cat-like, loyal to family",
    unique_interaction="Dramatic scream",
    unique_interaction_effect="+humor (random event)"
)

SPECIES_DATABASE["dachshund"] = SpeciesData(
    id="dachshund",
    name="Dachshund",
    emoji="🐕",
    category="dogs",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="extended",
    care_difficulty="easy",
    possible_coats=["Red", "Cream", "Black/Tan", "Chocolate", "Wild Boar"],
    possible_patterns=["Solid", "Dapple", "Brindle", "Piebald"],
    special_needs="Back protection, no jumping",
    temperament="Clever, stubborn, brave",
    unique_interaction="Burrowing in blankets",
    unique_interaction_effect="+Happiness"
)

SPECIES_DATABASE["border_collie"] = SpeciesData(
    id="border_collie",
    name="Border Collie",
    emoji="🐕",
    category="dogs",
    rarity="rare",
    activity_level="very_high",
    social_need="high",
    grooming_need="frequent",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Black/White", "Red/White", "Blue Merle", "Tricolor"],
    possible_patterns=["Bicolor", "Merle", "Tricolor"],
    special_needs="Intense mental stimulation, job to do",
    temperament="Extremely intelligent, workaholic, sensitive",
    unique_interaction="Advanced trick training",
    unique_interaction_effect="+Bond++, +Happiness"
)

SPECIES_DATABASE["pomeranian"] = SpeciesData(
    id="pomeranian",
    name="Pomeranian",
    emoji="🐕",
    category="dogs",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="frequent",
    diet_type="omnivore",
    lifespan="extended",
    care_difficulty="medium",
    possible_coats=["Orange", "Black", "White", "Cream", "Merle"],
    possible_patterns=["Solid", "Sable", "Parti"],
    special_needs="Dental care, temperature awareness",
    temperament="Bold, vivacious, curious",
    unique_interaction="Show off pose",
    unique_interaction_effect="+Happiness from attention"
)

SPECIES_DATABASE["great_dane"] = SpeciesData(
    id="great_dane",
    name="Great Dane",
    emoji="🐕",
    category="dogs",
    rarity="rare",
    activity_level="medium",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="medium",
    possible_coats=["Black", "Blue", "Fawn", "Merle"],
    possible_patterns=["Solid", "Brindle", "Harlequin", "Mantle"],
    special_needs="Joint care, space for size, gentle play",
    temperament="Gentle giant, patient, friendly",
    unique_interaction="Lean for cuddles",
    unique_interaction_effect="+Bond++"
)

SPECIES_DATABASE["australian_shepherd"] = SpeciesData(
    id="australian_shepherd",
    name="Australian Shepherd",
    emoji="🐕",
    category="dogs",
    rarity="uncommon",
    activity_level="very_high",
    social_need="high",
    grooming_need="frequent",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Black", "Red", "Blue Merle", "Red Merle"],
    possible_patterns=["Merle", "Tricolor", "Bicolor"],
    special_needs="Extensive exercise, mental challenges",
    temperament="Smart, work-oriented, loyal",
    unique_interaction="Frisbee catch",
    unique_interaction_effect="+Happiness++, -Energy"
)

SPECIES_DATABASE["red_nose_pitbull"] = SpeciesData(
    id="red_nose_pitbull",
    name="Red Nose Pitbull",
    emoji="🐕",
    category="dogs",
    rarity="uncommon",
    activity_level="high",
    social_need="very_high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["White", "Tan", "Grey", "Brown"],
    possible_patterns=["Solid", "Brindle", "Bicolor"],
    special_needs="Early socialization, consistent training, daily exercise",
    temperament="Loyal, affectionate, energetic, eager to please",
    unique_interaction="Tug-of-war game",
    unique_interaction_effect="+Happiness, +Bond"
)

SPECIES_DATABASE["blue_nose_pitbull"] = SpeciesData(
    id="blue_nose_pitbull",
    name="Blue Nose Pitbull",
    emoji="🐕",
    category="dogs",
    rarity="rare",
    activity_level="high",
    social_need="very_high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["White", "Tan", "Grey", "Brown"],
    possible_patterns=["Solid", "Brindle", "Bicolor"],
    special_needs="Early socialization, consistent training, daily exercise",
    temperament="Loyal, affectionate, energetic, eager to please",
    unique_interaction="Agility training",
    unique_interaction_effect="+Happiness, +Bond, -Energy"
)

SPECIES_DATABASE["bull_terrier"] = SpeciesData(
    id="bull_terrier",
    name="English Bull Terrier",
    emoji="🐕",
    category="dogs",
    rarity="uncommon",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["White", "Red", "Fawn", "Black", "Tan", "Brown", "Tricolor"],
    possible_patterns=["Solid", "Bicolor", "Brindle"],
    special_needs="Mental stimulation, early socialization, experienced owner preferred",
    temperament="Courageous, playful, stubborn, fun-loving",
    unique_interaction="Egg-head boops",
    unique_interaction_effect="+Happiness, +Bond"
)


# -----------------------------------------------------------------------------
# CATS (15 Species) - IDs 16-30
# -----------------------------------------------------------------------------

SPECIES_DATABASE["domestic_shorthair"] = SpeciesData(
    id="domestic_shorthair",
    name="Domestic Shorthair",
    emoji="🐱",
    category="cats",
    rarity="common",
    activity_level="medium",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="extended",
    care_difficulty="easy",
    possible_coats=["Black", "White", "Orange", "Gray", "Brown", "Cream"],
    possible_patterns=["Tabby", "Solid", "Calico", "Tuxedo", "Bicolor"],
    special_needs="Scratching post, vertical space",
    temperament="Varied, adaptable",
    unique_interaction="Lap sitting",
    unique_interaction_effect="+Bond, +Owner Happiness"
)

SPECIES_DATABASE["siamese"] = SpeciesData(
    id="siamese",
    name="Siamese",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="extended",
    care_difficulty="medium",
    possible_coats=["Seal Point", "Chocolate Point", "Blue Point", "Lilac Point"],
    possible_patterns=["Color point"],
    special_needs="Companionship, conversation, mental stimulation",
    temperament="Vocal, demanding, affectionate, intelligent",
    unique_interaction="Conversation",
    unique_interaction_effect="+Happiness (meowing back and forth)"
)

SPECIES_DATABASE["maine_coon"] = SpeciesData(
    id="maine_coon",
    name="Maine Coon",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="medium",
    social_need="high",
    grooming_need="frequent",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Brown Tabby", "Black", "White", "Cream", "Silver", "Red"],
    possible_patterns=["Tabby", "Solid", "Bicolor"],
    special_needs="Larger food portions, regular brushing",
    temperament="Gentle giant, playful, dog-like",
    unique_interaction="Play fetch",
    unique_interaction_effect="+Happiness (unique for cats)"
)

SPECIES_DATABASE["persian"] = SpeciesData(
    id="persian",
    name="Persian",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="low",
    social_need="moderate",
    grooming_need="very_frequent",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["White", "Black", "Blue", "Cream", "Red", "Silver", "Golden"],
    possible_patterns=["Solid", "Tabby", "Bicolor", "Shaded"],
    special_needs="Eye cleaning, mat prevention, flat-face care",
    temperament="Quiet, sweet, docile",
    unique_interaction="Luxury lounging",
    unique_interaction_effect="+Happiness from comfort"
)

SPECIES_DATABASE["bengal"] = SpeciesData(
    id="bengal",
    name="Bengal",
    emoji="🐆",
    category="cats",
    rarity="rare",
    activity_level="very_high",
    social_need="high",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Brown", "Snow", "Silver", "Charcoal"],
    possible_patterns=["Spotted", "Rosette", "Marble"],
    special_needs="Intense play, climbing structures, water play",
    temperament="Wild, energetic, curious, athletic",
    unique_interaction="Water play",
    unique_interaction_effect="+Happiness++, -Cleanliness"
)

SPECIES_DATABASE["ragdoll"] = SpeciesData(
    id="ragdoll",
    name="Ragdoll",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="low",
    social_need="high",
    grooming_need="moderate",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Seal", "Blue", "Chocolate", "Lilac", "Flame", "Cream"],
    possible_patterns=["Colorpoint", "Mitted", "Bicolor"],
    special_needs="Gentle handling, follows owner around",
    temperament="Docile, calm, floppy when held, affectionate",
    unique_interaction="Go limp in arms",
    unique_interaction_effect="+Bond++, relaxation"
)

SPECIES_DATABASE["scottish_fold"] = SpeciesData(
    id="scottish_fold",
    name="Scottish Fold",
    emoji="🐱",
    category="cats",
    rarity="rare",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["White", "Black", "Blue", "Red", "Cream", "Silver"],
    possible_patterns=["Solid", "Tabby", "Bicolor", "Calico"],
    special_needs="Joint health monitoring, ear care",
    temperament="Sweet, adaptable, quiet",
    unique_interaction="Buddha sit pose",
    unique_interaction_effect="+Happiness from cute"
)

SPECIES_DATABASE["sphynx"] = SpeciesData(
    id="sphynx",
    name="Sphynx",
    emoji="🐱",
    category="cats",
    rarity="rare",
    activity_level="high",
    social_need="very_high",
    grooming_need="frequent",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Black", "White", "Pink", "Lavender", "Gray"],
    possible_patterns=["Solid", "Bicolor"],
    special_needs="Regular baths, temperature regulation, sun protection",
    temperament="Extroverted, energetic, attention-seeking",
    unique_interaction="Warmth seeking",
    unique_interaction_effect="+Bond (snuggle bonus)"
)

SPECIES_DATABASE["british_shorthair"] = SpeciesData(
    id="british_shorthair",
    name="British Shorthair",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="low",
    social_need="moderate",
    grooming_need="moderate",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Blue", "White", "Black", "Cream", "Silver", "Golden"],
    possible_patterns=["Solid", "Tabby", "Bicolor"],
    special_needs="Weight management, doesn't like being carried",
    temperament="Calm, easygoing, dignified, not lap cat",
    unique_interaction="Side-by-side sitting",
    unique_interaction_effect="+Bond (respects space)"
)

SPECIES_DATABASE["abyssinian"] = SpeciesData(
    id="abyssinian",
    name="Abyssinian",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="very_high",
    social_need="high",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Ruddy", "Sorrel", "Blue", "Fawn"],
    possible_patterns=["Ticked tabby (agouti)"],
    special_needs="Climbing, high perches, interactive toys",
    temperament="Curious, playful, acrobatic, mischievous",
    unique_interaction="High jump competition",
    unique_interaction_effect="+Happiness"
)

SPECIES_DATABASE["russian_blue"] = SpeciesData(
    id="russian_blue",
    name="Russian Blue",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="medium",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="extended",
    care_difficulty="easy",
    possible_coats=["Blue (silver-tipped)"],
    possible_patterns=["Solid"],
    special_needs="Routine, quiet environment, predictability",
    temperament="Gentle, reserved, loyal to owner",
    unique_interaction="Secret spot discovery",
    unique_interaction_effect="+Bond from trust"
)

SPECIES_DATABASE["norwegian_forest_cat"] = SpeciesData(
    id="norwegian_forest_cat",
    name="Norwegian Forest Cat",
    emoji="🐱",
    category="cats",
    rarity="rare",
    activity_level="medium",
    social_need="moderate",
    grooming_need="frequent",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Brown Tabby", "Black", "White", "Red", "Blue", "Cream"],
    possible_patterns=["Tabby", "Solid", "Bicolor"],
    special_needs="Climbing trees, seasonal coat changes",
    temperament="Friendly, independent, adventurous",
    unique_interaction="Tree climbing observation",
    unique_interaction_effect="+Happiness"
)

SPECIES_DATABASE["savannah_cat"] = SpeciesData(
    id="savannah_cat",
    name="Savannah Cat",
    emoji="🐆",
    category="cats",
    rarity="very_rare",
    activity_level="extremely_high",
    social_need="high",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="expert",
    possible_coats=["Golden", "Silver", "Smoke", "Black"],
    possible_patterns=["Spotted (wild markings)"],
    special_needs="Large enclosure, leash training, water, extreme enrichment",
    temperament="Wild, loyal, dog-like, very intelligent",
    unique_interaction="Leash walking",
    unique_interaction_effect="+Happiness++, +Energy burn"
)

SPECIES_DATABASE["oriental_shorthair"] = SpeciesData(
    id="oriental_shorthair",
    name="Oriental Shorthair",
    emoji="🐱",
    category="cats",
    rarity="uncommon",
    activity_level="high",
    social_need="very_high",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Black", "White", "Blue", "Chestnut", "Lavender", "Cinnamon"],
    possible_patterns=["Solid", "Smoke", "Shaded", "Tabby", "Bicolor"],
    special_needs="Constant companionship, dislikes being alone",
    temperament="Vocal, demanding, loyal, playful",
    unique_interaction="Shoulder perching",
    unique_interaction_effect="+Bond, +Happiness"
)

SPECIES_DATABASE["domestic_longhair"] = SpeciesData(
    id="domestic_longhair",
    name="Domestic Longhair",
    emoji="🐱",
    category="cats",
    rarity="common",
    activity_level="medium",
    social_need="moderate",
    grooming_need="frequent",
    diet_type="carnivore",
    lifespan="extended",
    care_difficulty="easy",
    possible_coats=["Black", "White", "Orange", "Gray", "Brown", "Cream"],
    possible_patterns=["Tabby", "Solid", "Calico", "Bicolor"],
    special_needs="Regular brushing to prevent mats",
    temperament="Varied, adaptable",
    unique_interaction="Brushing session",
    unique_interaction_effect="+Cleanliness, +Bond"
)


# -----------------------------------------------------------------------------
# SMALL MAMMALS (15 Species) - IDs 31-45
# -----------------------------------------------------------------------------

SPECIES_DATABASE["holland_lop_rabbit"] = SpeciesData(
    id="holland_lop_rabbit",
    name="Holland Lop Rabbit",
    emoji="🐰",
    category="small_mammals",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["White", "Black", "Blue", "Chocolate", "Orange", "Tort"],
    possible_patterns=["Broken", "Solid", "Tricolor"],
    special_needs="Hay supply, nail trimming, space to binky",
    temperament="Friendly, calm, cuddly",
    unique_interaction="Binky",
    unique_interaction_effect="+Happiness indicator (happy jump)"
)

SPECIES_DATABASE["netherland_dwarf_rabbit"] = SpeciesData(
    id="netherland_dwarf_rabbit",
    name="Netherland Dwarf Rabbit",
    emoji="🐰",
    category="small_mammals",
    rarity="common",
    activity_level="high",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["White", "Black", "Blue", "Chocolate", "Orange", "Lilac"],
    possible_patterns=["Solid", "Shaded", "Tan"],
    special_needs="Gentle handling due to size",
    temperament="Energetic, sometimes skittish, curious",
    unique_interaction="Nose bonks",
    unique_interaction_effect="+Bond"
)

SPECIES_DATABASE["syrian_hamster"] = SpeciesData(
    id="syrian_hamster",
    name="Syrian Hamster",
    emoji="🐹",
    category="small_mammals",
    rarity="common",
    activity_level="high",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="easy",
    possible_coats=["Golden", "Cream", "White", "Black", "Gray", "Cinnamon"],
    possible_patterns=["Solid", "Banded", "Dominant Spot"],
    special_needs="Large wheel, burrowing substrate, single housing",
    temperament="Friendly when tamed, curious, cheek-stuffer",
    unique_interaction="Wheel running observation",
    unique_interaction_effect="+Activity tracking"
)

SPECIES_DATABASE["roborovski_hamster"] = SpeciesData(
    id="roborovski_hamster",
    name="Roborovski Hamster",
    emoji="🐹",
    category="small_mammals",
    rarity="uncommon",
    activity_level="extremely_high",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="medium",
    possible_coats=["Sandy", "White-faced", "Husky"],
    possible_patterns=["Solid with eyebrow markings"],
    special_needs="Secure cage (tiny escape artists), sand bath",
    temperament="Speedy, less handleable, entertaining to watch",
    unique_interaction="Speed run observation",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["guinea_pig"] = SpeciesData(
    id="guinea_pig",
    name="Guinea Pig",
    emoji="🐹",
    category="small_mammals",
    rarity="common",
    activity_level="medium",
    social_need="very_high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="easy",
    possible_coats=["White", "Black", "Brown", "Orange", "Cream", "Tricolor"],
    possible_patterns=["Solid", "Tricolor", "Dutch", "Himalayan", "Roan"],
    special_needs="Vitamin C supplements, floor time, hay",
    temperament="Social, vocal, affectionate",
    unique_interaction="Wheeking",
    unique_interaction_effect="+Happiness indicator (excited vocalization)"
)

SPECIES_DATABASE["ferret"] = SpeciesData(
    id="ferret",
    name="Ferret",
    emoji="🦡",
    category="small_mammals",
    rarity="uncommon",
    activity_level="very_high",
    social_need="high",
    grooming_need="moderate",
    diet_type="carnivore",
    lifespan="medium",
    care_difficulty="medium",
    possible_coats=["Sable", "Albino", "Silver", "Chocolate", "Black"],
    possible_patterns=["Solid", "Mitt", "Blaze", "Panda"],
    special_needs="Ferret-proofed play area, hide spots, sleep 18hrs/day",
    temperament="Playful, curious, mischievous, theft-prone",
    unique_interaction="War dance",
    unique_interaction_effect="+Happiness++ (happy jumping dance)"
)

SPECIES_DATABASE["chinchilla"] = SpeciesData(
    id="chinchilla",
    name="Chinchilla",
    emoji="🐭",
    category="small_mammals",
    rarity="uncommon",
    activity_level="high",
    social_need="moderate",
    grooming_need="frequent",
    diet_type="herbivore",
    lifespan="extended",
    care_difficulty="medium",
    possible_coats=["Standard Gray", "White", "Beige", "Black Velvet", "Violet"],
    possible_patterns=["Solid", "Mosaic"],
    special_needs="Dust bath, cool temperatures, no moisture",
    temperament="Soft, bouncy, somewhat aloof, nocturnal",
    unique_interaction="Dust bath",
    unique_interaction_effect="+Cleanliness++, +Happiness"
)

SPECIES_DATABASE["hedgehog"] = SpeciesData(
    id="hedgehog",
    name="Hedgehog",
    emoji="🦔",
    category="small_mammals",
    rarity="uncommon",
    activity_level="medium",
    social_need="solitary",
    grooming_need="moderate",
    diet_type="insectivore",
    lifespan="medium",
    care_difficulty="medium",
    possible_coats=["Salt & Pepper", "Chocolate", "Albino", "Cinnamon", "Pinto"],
    possible_patterns=["Solid", "Snowflake", "Pinto"],
    special_needs="Wheel, warm environment, insect treats",
    temperament="Shy initially, curious once comfortable, huffs when annoyed",
    unique_interaction="Anointing",
    unique_interaction_effect="unique animation (self-protection behavior)"
)

SPECIES_DATABASE["sugar_glider"] = SpeciesData(
    id="sugar_glider",
    name="Sugar Glider",
    emoji="🐿️",
    category="small_mammals",
    rarity="rare",
    activity_level="high",
    social_need="very_high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Classic Gray", "White-faced Blonde", "Leucistic", "Albino", "Platinum"],
    possible_patterns=["Stripe on back"],
    special_needs="Bonding pouch, tall cage, colony or constant bonding",
    temperament="Bonded, social, gliding, vocal at night",
    unique_interaction="Gliding to owner",
    unique_interaction_effect="+Bond++, +Happiness"
)

SPECIES_DATABASE["fancy_rat"] = SpeciesData(
    id="fancy_rat",
    name="Fancy Rat",
    emoji="🐀",
    category="small_mammals",
    rarity="common",
    activity_level="high",
    social_need="very_high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="easy",
    possible_coats=["Agouti", "Black", "White", "Gray", "Blue", "Siamese", "Himalayan"],
    possible_patterns=["Solid", "Hooded", "Berkshire", "Capped", "Variegated"],
    special_needs="Cage mates, climbing, mental enrichment",
    temperament="Intelligent, affectionate, trainable, social",
    unique_interaction="Trick training",
    unique_interaction_effect="+Bond, +Happiness"
)

SPECIES_DATABASE["gerbil"] = SpeciesData(
    id="gerbil",
    name="Gerbil",
    emoji="🐹",
    category="small_mammals",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="easy",
    possible_coats=["Agouti", "Black", "White", "Slate", "Dove", "Lilac", "Argente"],
    possible_patterns=["Solid", "Spotted", "Pied"],
    special_needs="Deep bedding for burrowing, sand bath",
    temperament="Curious, active, burrowers, rarely bite",
    unique_interaction="Tunnel building",
    unique_interaction_effect="+Enrichment"
)

SPECIES_DATABASE["fancy_mouse"] = SpeciesData(
    id="fancy_mouse",
    name="Fancy Mouse",
    emoji="🐭",
    category="small_mammals",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="easy",
    possible_coats=["White", "Black", "Brown", "Tan", "Silver", "Champagne"],
    possible_patterns=["Solid", "Banded", "Dutch", "Marked"],
    special_needs="Climbing opportunities, secure lid",
    temperament="Curious, quick, can be hand-tamed",
    unique_interaction="Climbing obstacle course",
    unique_interaction_effect="+Happiness"
)

SPECIES_DATABASE["degu"] = SpeciesData(
    id="degu",
    name="Degu",
    emoji="🐿️",
    category="small_mammals",
    rarity="uncommon",
    activity_level="very_high",
    social_need="very_high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="medium",
    possible_coats=["Agouti", "Blue", "Sand", "Cream"],
    possible_patterns=["Solid"],
    special_needs="No sugar (diabetic prone), dust bath, exercise wheel",
    temperament="Social, vocal, intelligent, curious",
    unique_interaction="Chirping conversation",
    unique_interaction_effect="+Bond"
)

SPECIES_DATABASE["rex_rabbit"] = SpeciesData(
    id="rex_rabbit",
    name="Rex Rabbit",
    emoji="🐰",
    category="small_mammals",
    rarity="uncommon",
    activity_level="medium",
    social_need="high",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Castor", "Black", "Blue", "White", "Chocolate", "Lilac"],
    possible_patterns=["Solid", "Broken"],
    special_needs="Soft bedding (sensitive feet)",
    temperament="Calm, friendly, excellent pets",
    unique_interaction="Velvet petting",
    unique_interaction_effect="+Happiness from texture"
)

SPECIES_DATABASE["lionhead_rabbit"] = SpeciesData(
    id="lionhead_rabbit",
    name="Lionhead Rabbit",
    emoji="🐰",
    category="small_mammals",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="frequent",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["White", "Black", "Blue", "Chocolate", "Orange", "Tortoise"],
    possible_patterns=["Solid", "Broken", "Shaded"],
    special_needs="Daily mane brushing, dental check",
    temperament="Friendly, energetic, good-natured",
    unique_interaction="Mane styling",
    unique_interaction_effect="+Cleanliness, +Appearance variety"
)


# -----------------------------------------------------------------------------
# REPTILES (12 Species) - IDs 46-57
# -----------------------------------------------------------------------------

SPECIES_DATABASE["leopard_gecko"] = SpeciesData(
    id="leopard_gecko",
    name="Leopard Gecko",
    emoji="🦎",
    category="reptiles",
    rarity="common",
    activity_level="low",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="insectivore",
    lifespan="extended",
    care_difficulty="easy",
    possible_coats=["Normal", "High Yellow", "Tangerine", "Albino", "Blizzard", "Mack Snow"],
    possible_patterns=["Spotted", "Jungle", "Patternless", "Bold"],
    special_needs="Heat mat, calcium dusting, moist hide",
    temperament="Docile, handleable, slow-moving, tail waving",
    unique_interaction="Tail wag",
    unique_interaction_effect="+Happiness indicator (excited for food)"
)

SPECIES_DATABASE["bearded_dragon"] = SpeciesData(
    id="bearded_dragon",
    name="Bearded Dragon",
    emoji="🦎",
    category="reptiles",
    rarity="common",
    activity_level="medium",
    social_need="solitary",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Normal", "Citrus", "Red", "Orange", "Hypo", "Leatherback", "Silkback"],
    possible_patterns=["Tiger", "Dunner", "Translucent"],
    special_needs="UVB lighting, basking spot, varied diet",
    temperament="Friendly, arm waving, head bobbing, chill",
    unique_interaction="Arm wave greeting",
    unique_interaction_effect="+Bond, +Humor"
)

SPECIES_DATABASE["ball_python"] = SpeciesData(
    id="ball_python",
    name="Ball Python",
    emoji="🐍",
    category="reptiles",
    rarity="uncommon",
    activity_level="low",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="extended",
    care_difficulty="medium",
    possible_coats=["Normal", "Spider", "Pastel", "Piebald", "Albino", "Banana", "Clown"],
    possible_patterns=["Alien head", "Reduced pattern", "Striped"],
    special_needs="Humidity, hides, infrequent feeding",
    temperament="Shy, curls into ball when scared, handleable",
    unique_interaction="Ball curling",
    unique_interaction_effect="stress indicator"
)

SPECIES_DATABASE["corn_snake"] = SpeciesData(
    id="corn_snake",
    name="Corn Snake",
    emoji="🐍",
    category="reptiles",
    rarity="common",
    activity_level="medium",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Classic", "Amelanistic", "Anerythristic", "Snow", "Ghost", "Lavender"],
    possible_patterns=["Normal", "Motley", "Stripe", "Diffused"],
    special_needs="Secure lid (escape artists), climbing",
    temperament="Docile, curious, excellent first snake",
    unique_interaction="Exploring wrap",
    unique_interaction_effect="+Bond (comfortable handling)"
)

SPECIES_DATABASE["crested_gecko"] = SpeciesData(
    id="crested_gecko",
    name="Crested Gecko",
    emoji="🦎",
    category="reptiles",
    rarity="common",
    activity_level="medium",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Buckskin", "Flame", "Harlequin", "Dalmatian", "Phantom", "Lilly White"],
    possible_patterns=["Dalmatian spots", "Pin stripes", "Tiger"],
    special_needs="High humidity, no tail regeneration!",
    temperament="Jumpy, handleable, sticky toe pads",
    unique_interaction="Wall climbing observation",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["blue_tongued_skink"] = SpeciesData(
    id="blue_tongued_skink",
    name="Blue-Tongued Skink",
    emoji="🦎",
    category="reptiles",
    rarity="uncommon",
    activity_level="medium",
    social_need="solitary",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Northern", "Indonesian", "Irian Jaya", "Merauke"],
    possible_patterns=["Banded"],
    special_needs="UVB, varied diet, burrowing substrate",
    temperament="Docile, bluffs with blue tongue, food motivated",
    unique_interaction="Tongue display",
    unique_interaction_effect="+Humor (defensive bluff)"
)

SPECIES_DATABASE["russian_tortoise"] = SpeciesData(
    id="russian_tortoise",
    name="Russian Tortoise",
    emoji="🐢",
    category="reptiles",
    rarity="uncommon",
    activity_level="medium",
    social_need="solitary",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="extended",
    care_difficulty="medium",
    possible_coats=["Brown", "Tan", "Yellow", "Dark"],
    possible_patterns=["Scute patterns vary"],
    special_needs="UVB, outdoor time, burrow area",
    temperament="Determined, digger, personable",
    unique_interaction="Outdoor grazing",
    unique_interaction_effect="+Happiness++"
)

SPECIES_DATABASE["red_eared_slider"] = SpeciesData(
    id="red_eared_slider",
    name="Red-Eared Slider",
    emoji="🐢",
    category="reptiles",
    rarity="common",
    activity_level="high",
    social_need="moderate",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="extended",
    care_difficulty="medium",
    possible_coats=["Green/Yellow with red ear marking"],
    possible_patterns=["Striped"],
    special_needs="Large aquarium, basking dock, UVB",
    temperament="Active, begging for food, can bite",
    unique_interaction="Basking observation",
    unique_interaction_effect="+Health"
)

SPECIES_DATABASE["veiled_chameleon"] = SpeciesData(
    id="veiled_chameleon",
    name="Veiled Chameleon",
    emoji="🦎",
    category="reptiles",
    rarity="rare",
    activity_level="low",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="insectivore",
    lifespan="medium",
    care_difficulty="hard",
    possible_coats=["Green base with bands"],
    possible_patterns=["Banding (color changes based on mood)"],
    special_needs="Screen enclosure, live plants, misting system, minimal handling",
    temperament="Territorial, color-changing, observational pet",
    unique_interaction="Color mood indicator",
    unique_interaction_effect="dynamic color display"
)

SPECIES_DATABASE["uromastyx"] = SpeciesData(
    id="uromastyx",
    name="Uromastyx",
    emoji="🦎",
    category="reptiles",
    rarity="uncommon",
    activity_level="medium",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Yellow", "Orange", "Red", "Green", "Blue"],
    possible_patterns=["Banded", "Spotted"],
    special_needs="Very hot basking (120°F+), no humidity, seed diet",
    temperament="Docile, basking-focused, tail whip defense",
    unique_interaction="Tail whip",
    unique_interaction_effect="(defensive, humor)"
)

SPECIES_DATABASE["gargoyle_gecko"] = SpeciesData(
    id="gargoyle_gecko",
    name="Gargoyle Gecko",
    emoji="🦎",
    category="reptiles",
    rarity="uncommon",
    activity_level="medium",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Red", "Orange", "Yellow", "White"],
    possible_patterns=["Striped", "Blotched", "Reticulated"],
    special_needs="Similar to crested gecko, can regenerate tail",
    temperament="Calm, slightly nippier than cresties",
    unique_interaction="Horn observation",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["argentine_tegu"] = SpeciesData(
    id="argentine_tegu",
    name="Argentine Black and White Tegu",
    emoji="🦎",
    category="reptiles",
    rarity="very_rare",
    activity_level="high",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="extended",
    care_difficulty="expert",
    possible_coats=["Black/White", "Blue", "Red"],
    possible_patterns=["Banded"],
    special_needs="Large enclosure, substrate to burrow, varied diet, taming",
    temperament="Dog-like when tamed, intelligent, large",
    unique_interaction="Tegu training",
    unique_interaction_effect="+Bond++, +Intelligence display"
)


# -----------------------------------------------------------------------------
# BIRDS (15 Species) - IDs 58-72
# -----------------------------------------------------------------------------

SPECIES_DATABASE["budgerigar"] = SpeciesData(
    id="budgerigar",
    name="Budgerigar",
    emoji="🐦",
    category="birds",
    rarity="common",
    activity_level="high",
    social_need="very_high",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="easy",
    possible_coats=["Green", "Blue", "Yellow", "White", "Violet", "Gray"],
    possible_patterns=["Normal", "Pied", "Spangled", "Clearwing", "Opaline"],
    special_needs="Cage time outside, toys, social interaction",
    temperament="Playful, talkative, social, acrobatic",
    unique_interaction="Speech training",
    unique_interaction_effect="+Bond, unlock phrases"
)

SPECIES_DATABASE["cockatiel"] = SpeciesData(
    id="cockatiel",
    name="Cockatiel",
    emoji="🐦",
    category="birds",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Gray", "Lutino", "Cinnamon", "Whiteface"],
    possible_patterns=["Pearl", "Pied", "Solid"],
    special_needs="Whistling enrichment, crest mood indicator",
    temperament="Affectionate, whistlers, cuddly, crest shows mood",
    unique_interaction="Whistle duet",
    unique_interaction_effect="+Happiness, +Bond"
)

SPECIES_DATABASE["lovebird"] = SpeciesData(
    id="lovebird",
    name="Lovebird",
    emoji="🐦",
    category="birds",
    rarity="common",
    activity_level="high",
    social_need="very_high",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="medium",
    possible_coats=["Peach-faced Green", "Blue", "Lutino"],
    possible_patterns=["Solid", "Pied", "Opaline"],
    special_needs="Pair bonding (to bird or human), shredding toys",
    temperament="Feisty, bonded, territorial, playful",
    unique_interaction="Cuddle preening",
    unique_interaction_effect="+Bond++"
)

SPECIES_DATABASE["parrotlet"] = SpeciesData(
    id="parrotlet",
    name="Parrotlet",
    emoji="🐦",
    category="birds",
    rarity="uncommon",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Green", "Blue", "Yellow", "White", "Turquoise"],
    possible_patterns=["Solid", "Fallow", "Marbled"],
    special_needs="Small but mighty personality, training",
    temperament="Fearless, big personality in tiny body, nippy if untamed",
    unique_interaction="Shoulder buddy",
    unique_interaction_effect="+Bond, +Happiness"
)

SPECIES_DATABASE["green_cheeked_conure"] = SpeciesData(
    id="green_cheeked_conure",
    name="Green-Cheeked Conure",
    emoji="🦜",
    category="birds",
    rarity="uncommon",
    activity_level="high",
    social_need="very_high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Normal", "Cinnamon", "Pineapple", "Yellow-sided", "Turquoise"],
    possible_patterns=["Marbled breast", "Solid"],
    special_needs="Play time, cuddling, can be loud",
    temperament="Clownish, cuddly, acrobatic, LOUD",
    unique_interaction="Upside-down hanging",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["canary"] = SpeciesData(
    id="canary",
    name="Canary",
    emoji="🐦",
    category="birds",
    rarity="common",
    activity_level="medium",
    social_need="low",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="easy",
    possible_coats=["Yellow", "Orange", "White", "Red", "Variegated"],
    possible_patterns=["Solid", "Variegated"],
    special_needs="Males sing, flight space, no handling needed",
    temperament="Independent, cheerful singers, observational",
    unique_interaction="Morning song",
    unique_interaction_effect="+Owner Happiness, +Pet Happiness"
)

SPECIES_DATABASE["zebra_finch"] = SpeciesData(
    id="zebra_finch",
    name="Zebra Finch",
    emoji="🐦",
    category="birds",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="easy",
    possible_coats=["Gray", "Fawn", "White", "Pied", "Penguin"],
    possible_patterns=["Zebra stripes on male", "Cheek patches"],
    special_needs="Flight space, multiple birds, no handling",
    temperament="Active, social, beep constantly, fly about",
    unique_interaction="Flock observation",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["quaker_parrot"] = SpeciesData(
    id="quaker_parrot",
    name="Quaker Parrot",
    emoji="🦜",
    category="birds",
    rarity="uncommon",
    activity_level="high",
    social_need="high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Green", "Blue", "Pallid", "Albino"],
    possible_patterns=["Solid with gray chest"],
    special_needs="Very vocal, excellent talkers, nest building",
    temperament="Talkers, can be territorial, intelligent",
    unique_interaction="Word learning",
    unique_interaction_effect="+Bond, unlock vocabulary"
)

SPECIES_DATABASE["african_grey"] = SpeciesData(
    id="african_grey",
    name="African Grey Parrot",
    emoji="🦜",
    category="birds",
    rarity="very_rare",
    activity_level="medium",
    social_need="very_high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="extended",
    care_difficulty="expert",
    possible_coats=["Gray with red tail"],
    possible_patterns=["Solid gray"],
    special_needs="Extreme mental stimulation, emotional bond, routine",
    temperament="Genius-level intelligence, sensitive, talkers, anxious if neglected",
    unique_interaction="Contextual conversation",
    unique_interaction_effect="+Bond++, +Intelligence"
)

SPECIES_DATABASE["umbrella_cockatoo"] = SpeciesData(
    id="umbrella_cockatoo",
    name="Umbrella Cockatoo",
    emoji="🦜",
    category="birds",
    rarity="very_rare",
    activity_level="high",
    social_need="extremely_high",
    grooming_need="frequent",
    diet_type="herbivore",
    lifespan="extended",
    care_difficulty="expert",
    possible_coats=["White with yellow crest undertones"],
    possible_patterns=["Solid white"],
    special_needs="Constant attention, destruction toys, very loud",
    temperament="Velcro bird, screamer if lonely, cuddly, dramatic",
    unique_interaction="Crest mood dance",
    unique_interaction_effect="+Happiness indicator, +Entertainment"
)

SPECIES_DATABASE["ringneck_dove"] = SpeciesData(
    id="ringneck_dove",
    name="Ringneck Dove",
    emoji="🕊️",
    category="birds",
    rarity="common",
    activity_level="low",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Fawn", "White", "Pied", "Tangerine"],
    possible_patterns=["Solid with neck ring"],
    special_needs="Gentle, cooing vocalizations, flight time",
    temperament="Calm, gentle, cooing, pair bonds",
    unique_interaction="Peaceful cooing",
    unique_interaction_effect="+Relaxation bonus"
)

SPECIES_DATABASE["amazon_parrot"] = SpeciesData(
    id="amazon_parrot",
    name="Amazon Parrot",
    emoji="🦜",
    category="birds",
    rarity="rare",
    activity_level="high",
    social_need="high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="extended",
    care_difficulty="hard",
    possible_coats=["Green with Blue-front", "Yellow-nape", "Double Yellow-head"],
    possible_patterns=["Green with colored accents"],
    special_needs="Vocal, can be moody, excellent singers",
    temperament="Bold, operatic singers, can be nippy, personality plus",
    unique_interaction="Opera singing",
    unique_interaction_effect="+Entertainment++"
)

SPECIES_DATABASE["eclectus_parrot"] = SpeciesData(
    id="eclectus_parrot",
    name="Eclectus Parrot",
    emoji="🦜",
    category="birds",
    rarity="rare",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="extended",
    care_difficulty="hard",
    possible_coats=["Male: Green", "Female: Red/Purple"],
    possible_patterns=["Solid with color blocking"],
    special_needs="Fresh food diet, sensitive to additives",
    temperament="Calm, gentle, less noisy than other parrots",
    unique_interaction="Gender reveal upon adoption",
    unique_interaction_effect="+Surprise element"
)

SPECIES_DATABASE["blue_gold_macaw"] = SpeciesData(
    id="blue_gold_macaw",
    name="Blue and Gold Macaw",
    emoji="🦜",
    category="birds",
    rarity="legendary",
    activity_level="high",
    social_need="extremely_high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="extended",
    care_difficulty="expert",
    possible_coats=["Blue upper, Gold under, Green head"],
    possible_patterns=["Standard macaw coloring"],
    special_needs="Huge space, destruction toys, very loud, lifelong commitment",
    temperament="Majestic, dramatic, loud, deeply bonded",
    unique_interaction="Majestic wing spread",
    unique_interaction_effect="+Entertainment++, +Bond"
)

SPECIES_DATABASE["fancy_pigeon"] = SpeciesData(
    id="fancy_pigeon",
    name="Fancy Pigeon",
    emoji="🕊️",
    category="birds",
    rarity="uncommon",
    activity_level="medium",
    social_need="high",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="easy",
    possible_coats=["White", "Blue", "Black", "Red", "Fantail", "Pouter"],
    possible_patterns=["Check", "Bar", "Solid", "Pied"],
    special_needs="Flight space or aviary, pairs",
    temperament="Gentle, cooing, home-oriented",
    unique_interaction="Head bobbing strut",
    unique_interaction_effect="+Entertainment"
)


# -----------------------------------------------------------------------------
# AQUATIC (10 Species) - IDs 73-82
# -----------------------------------------------------------------------------

SPECIES_DATABASE["betta_fish"] = SpeciesData(
    id="betta_fish",
    name="Betta Fish",
    emoji="🐠",
    category="aquatic",
    rarity="common",
    activity_level="low",
    social_need="solitary",
    grooming_need="moderate",
    diet_type="carnivore",
    lifespan="short",
    care_difficulty="easy",
    possible_coats=["Red", "Blue", "Purple", "White", "Black", "Orange", "Multicolor"],
    possible_patterns=["Solid", "Marble", "Koi", "Galaxy", "Butterfly"],
    special_needs="Heated tank, single male, surface access",
    temperament="Curious, flaring at threats, personality",
    unique_interaction="Flare display",
    unique_interaction_effect="+Defense, +Entertainment"
)

SPECIES_DATABASE["fancy_goldfish"] = SpeciesData(
    id="fancy_goldfish",
    name="Fancy Goldfish",
    emoji="🐠",
    category="aquatic",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Orange", "White", "Black", "Calico", "Red/White"],
    possible_patterns=["Solid", "Calico", "Bicolor"],
    special_needs="Large tank (no bowls!), cold water, filtration",
    temperament="Social, begging for food, personable",
    unique_interaction="Food dance",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["axolotl"] = SpeciesData(
    id="axolotl",
    name="Axolotl",
    emoji="🦎",
    category="aquatic",
    rarity="rare",
    activity_level="low",
    social_need="moderate",
    grooming_need="moderate",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Wild", "Leucistic", "Albino", "Golden", "GFP", "Melanoid", "Copper"],
    possible_patterns=["Solid", "Speckled"],
    special_needs="Cold water, no gravel, dim lighting",
    temperament="Derpy, permanent smile, regenerates limbs",
    unique_interaction="Gill flutter",
    unique_interaction_effect="+Cuteness, +Entertainment"
)

SPECIES_DATABASE["hermit_crab"] = SpeciesData(
    id="hermit_crab",
    name="Hermit Crab",
    emoji="🦀",
    category="aquatic",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Purple Pincher", "Ecuadorian"],
    possible_patterns=["Shell selection provides variety"],
    special_needs="Humidity, salt water, shell selection, deep substrate",
    temperament="Curious, climbers, shell shoppers",
    unique_interaction="Shell change",
    unique_interaction_effect="+Appearance change, +Happiness"
)

SPECIES_DATABASE["clownfish"] = SpeciesData(
    id="clownfish",
    name="Clownfish",
    emoji="🐠",
    category="aquatic",
    rarity="uncommon",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="medium",
    care_difficulty="medium",
    possible_coats=["Orange/White", "Black/White", "Maroon"],
    possible_patterns=["Striped bands"],
    special_needs="Saltwater, anemone optional, established tank",
    temperament="Bold, anemone guarding, hosting behavior",
    unique_interaction="Anemone wiggle",
    unique_interaction_effect="+Happiness, +Entertainment"
)

SPECIES_DATABASE["african_dwarf_frog"] = SpeciesData(
    id="african_dwarf_frog",
    name="African Dwarf Frog",
    emoji="🐸",
    category="aquatic",
    rarity="common",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="carnivore",
    lifespan="medium",
    care_difficulty="easy",
    possible_coats=["Olive", "Spotted"],
    possible_patterns=["Mottled spots"],
    special_needs="Fully aquatic, surface access for breathing",
    temperament="Goofy, zen pose floating, singing males",
    unique_interaction="Zen float pose",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["cherry_shrimp"] = SpeciesData(
    id="cherry_shrimp",
    name="Cherry Shrimp",
    emoji="🦐",
    category="aquatic",
    rarity="common",
    activity_level="high",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="medium",
    possible_coats=["Red", "Blue", "Yellow", "Black", "Crystal"],
    possible_patterns=["Solid", "Tiger stripes", "Rili"],
    special_needs="Planted tank, stable parameters",
    temperament="Busy, grazing constantly, breeding",
    unique_interaction="Molt observation",
    unique_interaction_effect="+Growth indicator"
)

SPECIES_DATABASE["oscar_fish"] = SpeciesData(
    id="oscar_fish",
    name="Oscar Fish",
    emoji="🐟",
    category="aquatic",
    rarity="uncommon",
    activity_level="medium",
    social_need="moderate",
    grooming_need="frequent",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Tiger", "Albino", "Red", "Lemon", "Lutino"],
    possible_patterns=["Tiger pattern"],
    special_needs="Large tank (75+ gal), strong filtration, tankmate caution",
    temperament="Dog-like personality, recognizes owner, begging",
    unique_interaction="Owner recognition",
    unique_interaction_effect="+Bond++"
)

SPECIES_DATABASE["mystery_snail"] = SpeciesData(
    id="mystery_snail",
    name="Mystery Snail",
    emoji="🐌",
    category="aquatic",
    rarity="common",
    activity_level="low",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="short",
    care_difficulty="easy",
    possible_coats=["Gold", "Blue", "Purple", "Ivory", "Magenta", "Jade"],
    possible_patterns=["Solid"],
    special_needs="Calcium for shell, copper-free",
    temperament="Peaceful, grazing, shell surfing",
    unique_interaction="Shell cleaning",
    unique_interaction_effect="+Cleanliness"
)

SPECIES_DATABASE["koi_fish"] = SpeciesData(
    id="koi_fish",
    name="Koi Fish",
    emoji="🐟",
    category="aquatic",
    rarity="rare",
    activity_level="medium",
    social_need="high",
    grooming_need="frequent",
    diet_type="omnivore",
    lifespan="extended",
    care_difficulty="hard",
    possible_coats=["Kohaku", "Sanke", "Showa", "Ogon", "Tancho"],
    possible_patterns=["Elaborate patterns specific to variety"],
    special_needs="Large pond (no tanks), filtration, winter care",
    temperament="Personable, hand-feeding, showpiece",
    unique_interaction="Hand feeding",
    unique_interaction_effect="+Bond++, +Trust"
)


# -----------------------------------------------------------------------------
# EXOTIC & UNUSUAL (18 Species) - IDs 83-100
# -----------------------------------------------------------------------------

SPECIES_DATABASE["chilean_rose_tarantula"] = SpeciesData(
    id="chilean_rose_tarantula",
    name="Chilean Rose Tarantula",
    emoji="🕷️",
    category="exotic",
    rarity="uncommon",
    activity_level="very_low",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="extended",
    care_difficulty="easy",
    possible_coats=["Rose/Brown", "Red", "Burgundy"],
    possible_patterns=["Solid with rose hairs"],
    special_needs="Humid hide, infrequent feeding, handle with care",
    temperament="Docile, slow-moving, flick hairs if stressed",
    unique_interaction="Molt collection",
    unique_interaction_effect="+Achievement, +Growth"
)

SPECIES_DATABASE["praying_mantis"] = SpeciesData(
    id="praying_mantis",
    name="Praying Mantis",
    emoji="🦗",
    category="exotic",
    rarity="uncommon",
    activity_level="low",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="short",
    care_difficulty="medium",
    possible_coats=["Green", "Brown", "Orchid Pink"],
    possible_patterns=["Mimicry patterns"],
    special_needs="Live food, humidity, climbing space",
    temperament="Alien-like, watching, striking at prey",
    unique_interaction="Hunting observation",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["stick_insect"] = SpeciesData(
    id="stick_insect",
    name="Stick Insect",
    emoji="🪵",
    category="exotic",
    rarity="common",
    activity_level="very_low",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="short",
    care_difficulty="easy",
    possible_coats=["Brown", "Green", "Tan"],
    possible_patterns=["Twig-like camouflage"],
    special_needs="Fresh leaves, misting, tall enclosure",
    temperament="Zen, swaying, perfect camo",
    unique_interaction="Camo hide and seek",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["emperor_scorpion"] = SpeciesData(
    id="emperor_scorpion",
    name="Emperor Scorpion",
    emoji="🦂",
    category="exotic",
    rarity="uncommon",
    activity_level="low",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Black", "Dark Blue sheen"],
    possible_patterns=["Solid"],
    special_needs="Humid, burrowing substrate, minimal handling",
    temperament="Defensive, grasps with claws, mild venom",
    unique_interaction="UV glow observation",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["giant_african_millipede"] = SpeciesData(
    id="giant_african_millipede",
    name="Giant African Millipede",
    emoji="🐛",
    category="exotic",
    rarity="uncommon",
    activity_level="low",
    social_need="moderate",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="medium",
    care_difficulty="easy",
    possible_coats=["Black", "Red-banded"],
    possible_patterns=["Segmented bands"],
    special_needs="Moist substrate, leaf litter, calcium",
    temperament="Docile, curls when stressed, many legs",
    unique_interaction="Leg counting",
    unique_interaction_effect="+Entertainment (joke interaction)"
)

SPECIES_DATABASE["pacman_frog"] = SpeciesData(
    id="pacman_frog",
    name="Pacman Frog",
    emoji="🐸",
    category="exotic",
    rarity="uncommon",
    activity_level="very_low",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="easy",
    possible_coats=["Green", "Albino", "Strawberry", "Samurai", "Fantasy"],
    possible_patterns=["Ornate patterns"],
    special_needs="Ambush predator, burrowing, humid",
    temperament="Grumpy blob, bite-y, sit and wait",
    unique_interaction="Feeding ambush",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["fire_salamander"] = SpeciesData(
    id="fire_salamander",
    name="Fire Salamander",
    emoji="🦎",
    category="exotic",
    rarity="uncommon",
    activity_level="low",
    social_need="solitary",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="medium",
    possible_coats=["Black with Yellow/Orange"],
    possible_patterns=["Spotted", "Striped"],
    special_needs="Cool, moist, land with water access",
    temperament="Secretive, toxic skin (no handling)",
    unique_interaction="Spot observation",
    unique_interaction_effect="unique pattern per individual"
)

SPECIES_DATABASE["poison_dart_frog"] = SpeciesData(
    id="poison_dart_frog",
    name="Poison Dart Frog",
    emoji="🐸",
    category="exotic",
    rarity="rare",
    activity_level="medium",
    social_need="moderate",
    grooming_need="moderate",
    diet_type="insectivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Blue", "Yellow-banded", "Strawberry", "Green/Black"],
    possible_patterns=["Warning coloration (aposematic)"],
    special_needs="Bioactive vivarium, isopods, not toxic in captivity",
    temperament="Bold, diurnal, colorful display",
    unique_interaction="Color display",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["fennec_fox"] = SpeciesData(
    id="fennec_fox",
    name="Fennec Fox",
    emoji="🦊",
    category="exotic",
    rarity="very_rare",
    activity_level="very_high",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="expert",
    possible_coats=["Cream/Tan"],
    possible_patterns=["Solid with white underside"],
    special_needs="Legal requirements, escape proofing, dig box, loud",
    temperament="Energetic, screechy, dog-cat hybrid behavior",
    unique_interaction="Ear radar observation",
    unique_interaction_effect="+Entertainment++"
)

SPECIES_DATABASE["capybara"] = SpeciesData(
    id="capybara",
    name="Capybara",
    emoji="🦫",
    category="exotic",
    rarity="legendary",
    activity_level="medium",
    social_need="extremely_high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="expert",
    possible_coats=["Brown", "Tan"],
    possible_patterns=["Solid"],
    special_needs="Pool, grazing area, herd or constant companion",
    temperament="Zen master, chill, social with all animals",
    unique_interaction="Pool floating",
    unique_interaction_effect="+Relaxation++, +Happiness++"
)

SPECIES_DATABASE["wallaby"] = SpeciesData(
    id="wallaby",
    name="Wallaby",
    emoji="🦘",
    category="exotic",
    rarity="legendary",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="expert",
    possible_coats=["Gray", "Red", "Albino"],
    possible_patterns=["Solid"],
    special_needs="Large outdoor space, fencing, legal requirements",
    temperament="Curious, bouncy, can be shy",
    unique_interaction="Pouch check",
    unique_interaction_effect="+Surprise (if female)"
)

SPECIES_DATABASE["pygmy_goat"] = SpeciesData(
    id="pygmy_goat",
    name="Pygmy Goat",
    emoji="🐐",
    category="exotic",
    rarity="rare",
    activity_level="high",
    social_need="very_high",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Black", "White", "Caramel", "Agouti", "Multicolor"],
    possible_patterns=["Solid", "Patterned"],
    special_needs="Outdoor space, climbing structures, companion goat",
    temperament="Playful, mischievous, escape artist",
    unique_interaction="Parkour climbing",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["miniature_pig"] = SpeciesData(
    id="miniature_pig",
    name="Miniature Pig",
    emoji="🐷",
    category="exotic",
    rarity="rare",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Pink", "Black", "Spotted", "Red"],
    possible_patterns=["Solid", "Spotted", "Belted"],
    special_needs="Rooting area, outdoor time, intelligence",
    temperament="Smart, stubborn, food-obsessed, affectionate",
    unique_interaction="Trick training",
    unique_interaction_effect="+Bond++, +Intelligence"
)

SPECIES_DATABASE["kinkajou"] = SpeciesData(
    id="kinkajou",
    name="Kinkajou",
    emoji="🐻",
    category="exotic",
    rarity="legendary",
    activity_level="high",
    social_need="high",
    grooming_need="minimal",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="expert",
    possible_coats=["Golden/Honey brown"],
    possible_patterns=["Solid"],
    special_needs="Large cage, climbing, nocturnal schedule, specialized diet",
    temperament="Curious, can be nippy, prehensile tail",
    unique_interaction="Hanging by tail",
    unique_interaction_effect="+Entertainment"
)

SPECIES_DATABASE["serval"] = SpeciesData(
    id="serval",
    name="Serval",
    emoji="🐆",
    category="exotic",
    rarity="legendary",
    activity_level="very_high",
    social_need="high",
    grooming_need="minimal",
    diet_type="carnivore",
    lifespan="long",
    care_difficulty="expert",
    possible_coats=["Spotted golden"],
    possible_patterns=["Leopard spots"],
    special_needs="Huge enclosure, raw diet, legal restrictions, not domesticated",
    temperament="Wild, athletic jumper, can be affectionate but unpredictable",
    unique_interaction="High jump display",
    unique_interaction_effect="+Entertainment++ (athletic)"
)

SPECIES_DATABASE["domesticated_skunk"] = SpeciesData(
    id="domesticated_skunk",
    name="Domesticated Skunk",
    emoji="🦨",
    category="exotic",
    rarity="very_rare",
    activity_level="medium",
    social_need="high",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="long",
    care_difficulty="hard",
    possible_coats=["Black/White", "Chocolate/White", "Lavender", "Albino", "Apricot"],
    possible_patterns=["Striped", "Chipped", "Star"],
    special_needs="Descented, legal requirements, digging enrichment",
    temperament="Curious, stomping when upset (no spray if descented), cat-like",
    unique_interaction="Stomp warning dance",
    unique_interaction_effect="+Humor"
)

SPECIES_DATABASE["opossum"] = SpeciesData(
    id="opossum",
    name="Opossum",
    emoji="🐭",
    category="exotic",
    rarity="rare",
    activity_level="medium",
    social_need="solitary",
    grooming_need="moderate",
    diet_type="omnivore",
    lifespan="short",
    care_difficulty="medium",
    possible_coats=["Gray", "Leucistic"],
    possible_patterns=["Solid with lighter face"],
    special_needs="Must be rehab/educational animal, pouch for joeys",
    temperament="Misunderstood, gentle, plays dead, gaping mouth display",
    unique_interaction="Play dead",
    unique_interaction_effect="+Humor, +Defense mechanism"
)

SPECIES_DATABASE["red_panda"] = SpeciesData(
    id="red_panda",
    name="Red Panda",
    emoji="🐼",
    category="exotic",
    rarity="mythical",
    activity_level="medium",
    social_need="moderate",
    grooming_need="moderate",
    diet_type="herbivore",
    lifespan="long",
    care_difficulty="expert",
    possible_coats=["Red/Orange with white face"],
    possible_patterns=["Ringed tail"],
    special_needs="Zoo/sanctuary only, bamboo diet, climbing, temperature",
    temperament="Adorable, elusive, standing threat pose",
    unique_interaction="Standing pose",
    unique_interaction_effect="+Cuteness++, +Entertainment"
)


# =============================================================================
# DECAY MULTIPLIERS BY CATEGORY
# =============================================================================

DECAY_MULTIPLIERS: Dict[str, Dict[str, float]] = {
    "dogs": {"hunger": 1.5, "happiness": 1.2, "cleanliness": 1.0, "energy": 1.3},
    "cats": {"hunger": 1.0, "happiness": 0.8, "cleanliness": 0.5, "energy": 0.8},
    "small_mammals": {"hunger": 2.0, "happiness": 1.0, "cleanliness": 1.0, "energy": 1.5},
    "reptiles": {"hunger": 0.3, "happiness": 0.5, "cleanliness": 0.8, "energy": 0.5},
    "birds": {"hunger": 1.8, "happiness": 1.5, "cleanliness": 1.2, "energy": 1.0},
    "aquatic": {"hunger": 1.0, "happiness": 0.6, "cleanliness": 1.5, "energy": 0.5},
    "exotic": {"hunger": 1.0, "happiness": 1.0, "cleanliness": 1.0, "energy": 1.0},
}


# =============================================================================
# RARITY WEIGHTS FOR RANDOM SELECTION
# =============================================================================

RARITY_WEIGHTS: Dict[str, float] = {
    "common": 40.0,
    "uncommon": 30.0,
    "rare": 18.0,
    "very_rare": 8.0,
    "legendary": 3.5,
    "mythical": 0.5,
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_species(species_id: str) -> Optional[SpeciesData]:
    """Get species data by ID."""
    return SPECIES_DATABASE.get(species_id)


def get_all_species() -> List[SpeciesData]:
    """Get all species as a list."""
    return list(SPECIES_DATABASE.values())


def get_species_by_category(category: str) -> List[SpeciesData]:
    """Get all species in a category."""
    return [s for s in SPECIES_DATABASE.values() if s.category == category]


def get_species_by_rarity(rarity: str) -> List[SpeciesData]:
    """Get all species of a specific rarity."""
    return [s for s in SPECIES_DATABASE.values() if s.rarity == rarity]


def get_random_species() -> SpeciesData:
    """Get a weighted random species based on rarity."""
    # Group species by rarity
    species_by_rarity: Dict[str, List[SpeciesData]] = {}
    for species in SPECIES_DATABASE.values():
        if species.rarity not in species_by_rarity:
            species_by_rarity[species.rarity] = []
        species_by_rarity[species.rarity].append(species)
    
    # Calculate total weight
    total_weight = sum(RARITY_WEIGHTS.values())
    
    # Random selection
    roll = random.uniform(0, total_weight)
    cumulative = 0.0
    
    for rarity, weight in RARITY_WEIGHTS.items():
        cumulative += weight
        if roll <= cumulative:
            if rarity in species_by_rarity and species_by_rarity[rarity]:
                return random.choice(species_by_rarity[rarity])
    
    # Fallback to common
    return random.choice(species_by_rarity.get("common", list(SPECIES_DATABASE.values())))


def get_decay_multiplier(category: str, stat: str) -> float:
    """Get the decay multiplier for a category and stat."""
    category_multipliers = DECAY_MULTIPLIERS.get(category, DECAY_MULTIPLIERS["exotic"])
    return category_multipliers.get(stat, 1.0)


def get_species_count() -> int:
    """Get the total number of species."""
    return len(SPECIES_DATABASE)


def get_all_categories() -> List[str]:
    """Get list of all unique categories."""
    return list(set(s.category for s in SPECIES_DATABASE.values()))


def get_all_rarities() -> List[str]:
    """Get list of all unique rarities in order."""
    order = ["common", "uncommon", "rare", "very_rare", "legendary", "mythical"]
    rarities = set(s.rarity for s in SPECIES_DATABASE.values())
    return [r for r in order if r in rarities]


def get_category_counts() -> Dict[str, int]:
    """Get species count per category."""
    counts: Dict[str, int] = {}
    for species in SPECIES_DATABASE.values():
        counts[species.category] = counts.get(species.category, 0) + 1
    return counts
