"""
Abandon messages for shaming users who abandon their pets.
"""

import random
from typing import List, Optional

# Pool of shame messages for pet abandonment
# Placeholders: {user} = user mention, {species} = pet species name, {name} = pet name
ABANDON_MESSAGES: List[str] = [
    "🚪 {user} has dropped their {species} **{name}** off in a dark alley. What a horrible thing to do!",
    "💔 {user} just left their {species} **{name}** at a bus stop and drove away. Absolutely heartless!",
    "😱 {user} abandoned their {species} **{name}** in the middle of nowhere. The audacity!",
    "🗑️ {user} tossed their {species} **{name}** out like yesterday's garbage. Shame on them!",
    "🌧️ {user} left their {species} **{name}** out in the rain and never looked back. Monster!",
    "🚗 {user} drove 50 miles just to abandon their {species} **{name}** where no one would find them. Despicable!",
    "📦 {user} put their {species} **{name}** in a cardboard box and walked away. How could they?!",
    "🏚️ {user} left their {species} **{name}** at an abandoned building. True villain behavior!",
    "🛣️ {user} dumped their {species} **{name}** on the side of the highway. Unforgivable!",
    "🌲 {user} released their {species} **{name}** into the wild with no survival skills. Cruel!",
    "🚪 {user} locked their {species} **{name}** outside and changed all the locks. Cold-blooded!",
    "🎭 {user} pretended to take their {species} **{name}** for a walk... and never came back. Betrayal!",
    "🏪 {user} \"forgot\" their {species} **{name}** at a gas station 3 towns over. Sure, \"forgot\"...",
    "🌑 {user} waited until midnight to sneak their {species} **{name}** out of the house. Coward!",
    "🎪 {user} tried to sell their {species} **{name}** to a traveling circus. It didn't work out, so they just left.",
]

# Track last used message index to avoid repeats
_last_message_index: Optional[int] = None


def get_random_abandon_message(user_mention: str, species_name: str, pet_name: str) -> str:
    """
    Get a random shame message for abandoning a pet.
    Avoids picking the same message twice in a row.
    
    Args:
        user_mention: The Discord mention string for the user (e.g., "<@123456>")
        species_name: The species of the abandoned pet
        pet_name: The name of the abandoned pet
        
    Returns:
        A formatted shame message
    """
    global _last_message_index
    
    # Build list of valid indices (exclude last used)
    valid_indices = list(range(len(ABANDON_MESSAGES)))
    if _last_message_index is not None and len(valid_indices) > 1:
        valid_indices.remove(_last_message_index)
    
    # Pick a random index from valid options
    chosen_index = random.choice(valid_indices)
    _last_message_index = chosen_index
    
    message = ABANDON_MESSAGES[chosen_index]
    return message.format(user=user_mention, species=species_name, name=pet_name)
