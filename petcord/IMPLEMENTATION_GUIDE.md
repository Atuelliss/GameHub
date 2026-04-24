# Petcord Cog - Implementation Guide

## Purpose
This document provides step-by-step instructions for an AI assistant to build the Petcord cog in **modular, independent phases**. Each phase is self-contained and can be **tested immediately** after completion before moving to the next phase.

**Reference Document:** `PETCORD_DESIGN.md` (v1.5)

---

## Project Structure Overview

```
petcord/
├── __init__.py                 # Cog loader (setup function)
├── main.py                     # Main cog class, mixes in command groups
├── abc.py                      # Abstract base class (MixinMeta pattern)
├── PETCORD_DESIGN.md        # Design specification
├── IMPLEMENTATION_GUIDE.md     # This file
├── commands/
│   ├── __init__.py
│   ├── user_commands.py        # [p]petcord, [p]pcstat commands
│   ├── helper_functions.py     # Utility functions for player features
│   └── admin_commands.py       # [p]pcset admin command group
├── common/
│   ├── __init__.py
│   ├── models.py               # Pydantic data models
│   ├── constants.py            # Game constants, species data
│   └── utils.py                # Shared utility functions
├── databases/
│   ├── __init__.py
│   └── database.py             # Database management class
├── views/
│   ├── __init__.py
│   ├── main_menu.py            # Main menu view (dashboard)
│   ├── pet_actions.py          # Pet interaction buttons
│   ├── find_pet.py             # Find/adopt pet flow
│   ├── home_views.py           # Home management views
│   ├── stat_views.py           # Statistics views
│   └── modals.py               # Discord modals (naming, epitaph)
├── tasks/
│   ├── __init__.py
│   └── decay_task.py           # Background stat decay task
└── listeners/
    ├── __init__.py
    └── interaction_listener.py  # Button/interaction handlers
```

---

## Phase Overview

| Phase | Name | Description | Testable Output |
|-------|------|-------------|-----------------|
| 1 | Foundation | Project structure, models, database | Load cog, save/retrieve data |
| 2 | Species Data | 100 species with stats | View species list via debug command |
| 3 | Main Menu | Basic `[p]petcord` command | Display empty menu embed |
| 4 | Find a Pet | Pet finding flow with buttons | Find, view, adopt/decline pet |
| 5 | Pet Naming | Modal-based naming | Name pet, see on dashboard |
| 6 | Pet Display | Current pet status display | View stats, bars, info |
| 7 | Core Actions | Feed, Play, Groom, Rest, Pet | Interact, see stat changes |
| 8 | Stat Decay | Background decay task | Stats decrease over time |
| 9 | Daily Tracking | Care scoring system | View daily rating |
| 10 | Life Stages | Age progression system | Pet grows through stages |
| 11 | Graduation | Adult → Home transition | Graduate pet, earn medal |
| 12 | Home System | Home pet management | View/interact with Home pets |
| 13 | Aging & Death | Senior stage, natural passing | Pet passes to Memorial |
| 14 | Memorial | Memorial viewing | View passed pets, set epitaph |
| 15 | Statistics | `[p]pcstat` command | View all user stats |
| 16 | Admin Commands | `[p]pcset` group | Configure server settings |
| 17 | Achievements | Achievement system | Earn and view achievements |
| 18 | Polish | Final refinements | Complete game loop |

---

# PHASE 1: Foundation

## Objective
Create the basic project structure, Pydantic models, and database management. The cog should load without errors.

## Files to Create

### 1.1 `__init__.py` (Root)
```python
from .main import Petcord

async def setup(bot):
    await bot.add_cog(Petcord(bot))
```

### 1.2 `abc.py`
Create the abstract base class for mixin pattern (reference DinoCollector/GAFishing for exact pattern).

**Key Elements:**
- `MixinMeta` class combining ABCMeta with discord.cog.CogMeta
- Abstract properties: `bot`, `config`, `db`
- Type hints for Red config

### 1.3 `common/models.py`
Create Pydantic models from design doc:

**Models to implement:**
1. `GuildSettings` - Server configuration
2. `User` - Player data with all tracking fields
3. `Pet` - Pet data with stats, lifecycle, medals
4. `DailyCareScore` - Daily tracking data
5. `PetMemorial` - Passed pet record
6. `PetHistoryEntry` - Released pet record (simple)
7. `Achievement` - Achievement data

**Important Fields (from PETCORD_DESIGN.md):**
- Include `last_pet_declined` in User for cooldown
- Include `death_cause` in Pet and PetMemorial
- Include `epitaph_allowed` in PetMemorial

### 1.4 `common/constants.py`
```python
# Game timing constants
DEFAULT_FIND_COOLDOWN_MINUTES = 30
DEFAULT_HOME_CAPACITY = 5
MAX_HOME_CAPACITY = 20

# Stat thresholds
CRITICAL_THRESHOLD = 20
WARNING_THRESHOLD = 40

# Medal thresholds
GOLD_THRESHOLD = 85.0
SILVER_THRESHOLD = 70.0
BRONZE_THRESHOLD = 50.0

# Decay base rates (per hour, before species multipliers)
BASE_HUNGER_DECAY = 5.0
BASE_HAPPINESS_DECAY = 3.0
BASE_CLEANLINESS_DECAY = 2.0
BASE_ENERGY_DECAY = 4.0

# Species category decay multipliers (add in Phase 2)
DECAY_MULTIPLIERS = {}
```

### 1.5 `common/utils.py`
Basic utility functions:
- `format_stat_bar(value: int, max_val: int = 100) -> str` - Create visual bar
- `format_timestamp(ts: float) -> str` - Format for display
- `calculate_cooldown_remaining(last_declined: float, cooldown_minutes: int) -> int` - Seconds remaining

### 1.6 `databases/database.py`
Database management class (reference DinoCollector pattern):

**Methods needed:**
- `get_guild_settings(guild_id: int) -> GuildSettings`
- `save_guild_settings(guild_id: int, settings: GuildSettings)`
- `get_user(guild_id: int, user_id: int) -> User`
- `save_user(guild_id: int, user_id: int, user: User)`
- `get_all_users(guild_id: int) -> Dict[int, User]`

### 1.7 `main.py`
Main cog class:
```python
class Petcord(commands.Cog):
    """A virtual pet game for Discord."""
    
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=UNIQUE_ID)
        self.db = DatabaseManager(self.config)
        
    async def cog_load(self):
        # Initialize any required setup
        pass
        
    async def cog_unload(self):
        # Clean up tasks
        pass
```

### 1.8 `commands/__init__.py`, `common/__init__.py`, etc.
Empty `__init__.py` files for all subpackages.

## Testing Phase 1
1. Load cog: `[p]load petcord`
2. Verify no errors in console
3. Create a debug command to test database:
   ```python
   @commands.command()
   @commands.is_owner()
   async def pcdebug(self, ctx):
       user = await self.db.get_user(ctx.guild.id, ctx.author.id)
       await ctx.send(f"User data: {user}")
   ```
4. Run debug command, verify user object created
5. Unload/reload cog, verify data persists

---

# PHASE 2: Species Data

## Objective
Implement the full species database with all 100 animals and their behavioral data.

## Files to Create/Modify

### 2.1 `common/species.py`
Create comprehensive species database:

```python
from typing import Dict, List
from pydantic import BaseModel

class SpeciesData(BaseModel):
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
    possible_coats: List[str]
    possible_patterns: List[str]
    
    # Unique traits
    special_needs: str
    temperament: str
    unique_interaction: str
    unique_interaction_effect: str

# All 100 species from design doc
SPECIES_DATABASE: Dict[str, SpeciesData] = {
    "golden_retriever": SpeciesData(
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
    ),
    # ... continue for all 100 species from PETCORD_DESIGN.md
}

# Category-based decay multipliers
DECAY_MULTIPLIERS = {
    "dogs": {"hunger": 1.5, "happiness": 1.2, "cleanliness": 1.0, "energy": 1.3},
    "cats": {"hunger": 1.0, "happiness": 0.8, "cleanliness": 0.5, "energy": 0.8},
    "small_mammals": {"hunger": 2.0, "happiness": 1.0, "cleanliness": 1.0, "energy": 1.5},
    "reptiles": {"hunger": 0.3, "happiness": 0.5, "cleanliness": 0.8, "energy": 0.5},
    "birds": {"hunger": 1.8, "happiness": 1.5, "cleanliness": 1.2, "energy": 1.0},
    "aquatic": {"hunger": 1.0, "happiness": 0.6, "cleanliness": 1.5, "energy": 0.5},
    "exotic": {"hunger": 1.0, "happiness": 1.0, "cleanliness": 1.0, "energy": 1.0},  # Default
}

# Rarity weights for random selection
RARITY_WEIGHTS = {
    "common": 40,
    "uncommon": 30,
    "rare": 18,
    "very_rare": 8,
    "legendary": 3.5,
    "mythical": 0.5,
}

def get_species(species_id: str) -> SpeciesData:
    """Get species data by ID."""
    return SPECIES_DATABASE.get(species_id)

def get_random_species() -> SpeciesData:
    """Get a weighted random species."""
    # Implement weighted random selection
    pass

def get_species_by_category(category: str) -> List[SpeciesData]:
    """Get all species in a category."""
    return [s for s in SPECIES_DATABASE.values() if s.category == category]
```

### 2.2 Populate All 100 Species
Using the data from PETCORD_DESIGN.md, populate the full `SPECIES_DATABASE` dictionary. Include:
- 15 Dogs (IDs 1-15)
- 15 Cats (IDs 16-30)
- 15 Small Mammals (IDs 31-45)
- 12 Reptiles (IDs 46-57)
- 15 Birds (IDs 58-72)
- 10 Aquatic (IDs 73-82)
- 18 Exotic (IDs 83-100)

### 2.3 `common/appearance.py`
```python
import random
from typing import Tuple

# Color rarities
RARE_COATS = ["Albino", "Melanistic", "Leucistic", "Piebald"]
MYTHICAL_COATS = ["Rainbow", "Galaxy", "Crystal", "Shadow"]

def generate_appearance(species: SpeciesData) -> Tuple[str, str, str]:
    """Generate random coat, pattern, and rarity for a species."""
    # 5% chance for rare coat if applicable
    # 0.5% chance for mythical coat
    # Otherwise random from species pool
    
    coat = random.choice(species.possible_coats)
    pattern = random.choice(species.possible_patterns)
    rarity = species.rarity
    
    return coat, pattern, rarity
```

## Testing Phase 2
1. Create debug command:
   ```python
   @commands.command()
   @commands.is_owner()
   async def pcspecies(self, ctx, species_id: str = None):
       if species_id:
           species = get_species(species_id)
           await ctx.send(f"Species: {species}")
       else:
           await ctx.send(f"Total species: {len(SPECIES_DATABASE)}")
   ```
2. Verify all 100 species load correctly
3. Test random species selection
4. Verify decay multipliers for each category

---

# PHASE 3: Main Menu (Empty State)

## Objective
Implement the `[p]petcord` command that displays the main menu embed with "No Pet" state.

## Files to Create/Modify

### 3.1 `views/main_menu.py`
```python
import discord
from discord.ui import View, Button

class MainMenuView(View):
    """Main pet dashboard view."""
    
    def __init__(self, cog, user_data, guild_settings, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.message = None
        self.setup_buttons()
    
    def setup_buttons(self):
        """Add buttons based on user state."""
        if self.user_data.current_pet is None:
            # No pet state - add Find a Pet button
            self.add_item(FindPetButton(self.cog))
            self.add_item(SpeciesGuideButton())
            self.add_item(LeaderboardButton())
        else:
            # Has pet state - handled in later phases
            pass
    
    async def build_embed(self) -> discord.Embed:
        """Build the main menu embed."""
        if self.user_data.current_pet is None:
            return await self._build_no_pet_embed()
        else:
            # Has pet - handled in Phase 6
            pass
    
    async def _build_no_pet_embed(self) -> discord.Embed:
        """Build embed for no pet state."""
        # Check cooldown
        cooldown_remaining = calculate_cooldown_remaining(
            self.user_data.last_pet_declined,
            self.guild_settings.find_cooldown_minutes
        )
        
        embed = discord.Embed(
            title="🐾 Petcord - Welcome!",
            color=discord.Color.blue()
        )
        
        if cooldown_remaining > 0:
            # On cooldown
            embed.description = "You don't have a pet yet."
            minutes, seconds = divmod(cooldown_remaining, 60)
            embed.add_field(
                name="⏳ Cooldown Active",
                value=f"You recently passed on a pet.\nYou can search again in: **{minutes}m {seconds}s**",
                inline=False
            )
            # Disable Find button
            for item in self.children:
                if isinstance(item, FindPetButton):
                    item.disabled = True
        else:
            embed.description = "You don't have a pet yet.\nClick below to find a new companion!"
        
        embed.add_field(
            name="📋 Tip",
            value="Use `[p]pcstat` to view your Home, Memorial, and lifetime statistics!",
            inline=False
        )
        
        return embed


class FindPetButton(Button):
    """Button to initiate pet finding."""
    def __init__(self, cog):
        super().__init__(
            label="Find a Pet",
            emoji="🔍",
            style=discord.ButtonStyle.primary
        )
        self.cog = cog
    
    async def callback(self, interaction: discord.Interaction):
        # Handled in Phase 4
        await interaction.response.send_message("Finding pet... (Phase 4)", ephemeral=True)


class SpeciesGuideButton(Button):
    """Button to view species guide."""
    def __init__(self):
        super().__init__(
            label="Species Guide",
            emoji="📖",
            style=discord.ButtonStyle.secondary
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Species guide coming soon!", ephemeral=True)


class LeaderboardButton(Button):
    """Button to view leaderboard."""
    def __init__(self):
        super().__init__(
            label="Leaderboard",
            emoji="🏆",
            style=discord.ButtonStyle.secondary
        )
    
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Leaderboard coming soon!", ephemeral=True)
```

### 3.2 `commands/user_commands.py`
```python
import discord
from redbot.core import commands
from ..abc import MixinMeta
from ..views.main_menu import MainMenuView

class UserCommands(MixinMeta):
    """Player-facing commands."""
    
    @commands.command(name="Petcord", aliases=["pcpet"])
    @commands.guild_only()
    async def Petcord(self, ctx: commands.Context):
        """Open the Petcord pet dashboard."""
        guild_settings = await self.db.get_guild_settings(ctx.guild.id)
        
        if not guild_settings.game_is_enabled:
            return await ctx.send("Petcord is not enabled on this server.")
        
        user_data = await self.db.get_user(ctx.guild.id, ctx.author.id)
        
        view = MainMenuView(self, user_data, guild_settings)
        embed = await view.build_embed()
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message
```

### 3.3 Update `main.py`
Mix in the UserCommands class:
```python
from .commands.user_commands import UserCommands

class Petcord(UserCommands, commands.Cog):
    ...
```

## Testing Phase 3
1. Enable game: Create temp admin command `[p]pcenable` to set `game_is_enabled = True`
2. Run `[p]petcord`
3. Verify embed displays with:
   - Title "🐾 Petcord - Welcome!"
   - "You don't have a pet yet." message
   - Find a Pet button (enabled)
   - Species Guide button
   - Leaderboard button
4. Verify buttons are clickable (show placeholder messages)

---

# PHASE 4: Find a Pet

## Objective
Implement the pet finding flow where users can search for and be offered a random pet.

## Files to Create/Modify

### 4.1 `views/find_pet.py`
```python
import discord
from discord.ui import View, Button
from ..common.species import get_random_species, SPECIES_DATABASE
from ..common.appearance import generate_appearance

class PetFoundView(View):
    """View for pet adoption decision."""
    
    def __init__(self, cog, user_data, guild_settings, offered_pet_data, timeout=300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.offered_pet = offered_pet_data  # Dict with species, coat, pattern, rarity
        self.message = None
    
    def build_embed(self) -> discord.Embed:
        """Build the pet offer embed."""
        species = self.offered_pet["species"]
        
        # Rarity display
        rarity_display = {
            "common": "⭐ Common",
            "uncommon": "⭐⭐ Uncommon",
            "rare": "⭐⭐⭐ Rare",
            "very_rare": "⭐⭐⭐⭐ Very Rare",
            "legendary": "⭐⭐⭐⭐⭐ Legendary",
            "mythical": "🌟 Mythical"
        }
        
        embed = discord.Embed(
            title="🔍 A Pet Needs a Home!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name=f"{species.emoji} {species.name}",
            value=f"Rarity: {rarity_display[species.rarity]}\nCoat: {self.offered_pet['coat']} | Pattern: {self.offered_pet['pattern']}",
            inline=False
        )
        
        embed.add_field(
            name="📋 Species Info",
            value=f"• Activity Level: {species.activity_level.title()}\n"
                  f"• Grooming Needs: {species.grooming_need.title()}\n"
                  f"• Diet: {species.diet_type.title()}\n"
                  f"• Lifespan: {species.lifespan.title()}\n"
                  f"• Special Trait: {species.temperament}",
            inline=False
        )
        
        embed.add_field(
            name="Would you like to adopt this pet?",
            value="*(Passing starts a 30 minute cooldown)*",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="Adopt", emoji="✅", style=discord.ButtonStyle.success)
    async def adopt_button(self, interaction: discord.Interaction, button: Button):
        """User wants to adopt this pet."""
        # Move to naming phase (Phase 5)
        await interaction.response.send_message("Moving to naming... (Phase 5)", ephemeral=True)
    
    @discord.ui.button(label="Pass", emoji="❌", style=discord.ButtonStyle.danger)
    async def pass_button(self, interaction: discord.Interaction, button: Button):
        """User declines this pet."""
        import time
        
        # Set cooldown
        self.user_data.last_pet_declined = time.time()
        await self.cog.db.save_user(
            interaction.guild.id, 
            interaction.user.id, 
            self.user_data
        )
        
        # Disable buttons
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="🐾 Maybe Next Time",
            description=f"You passed on the {self.offered_pet['species'].name}.\n\n"
                       f"⏳ You can search for another pet in **{self.guild_settings.find_cooldown_minutes} minutes**.",
            color=discord.Color.grey()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)


async def generate_offered_pet():
    """Generate a random pet to offer."""
    species = get_random_species()
    coat, pattern, rarity = generate_appearance(species)
    
    return {
        "species": species,
        "coat": coat,
        "pattern": pattern,
        "rarity": rarity
    }
```

### 4.2 Update `views/main_menu.py`
Update the FindPetButton callback:
```python
async def callback(self, interaction: discord.Interaction):
    from .find_pet import PetFoundView, generate_offered_pet
    
    # Check cooldown
    cooldown_remaining = calculate_cooldown_remaining(
        self.cog.user_data.last_pet_declined,
        self.cog.guild_settings.find_cooldown_minutes
    )
    
    if cooldown_remaining > 0:
        minutes, seconds = divmod(cooldown_remaining, 60)
        return await interaction.response.send_message(
            f"⏳ You can search again in **{minutes}m {seconds}s**",
            ephemeral=True
        )
    
    # Generate random pet
    offered_pet = await generate_offered_pet()
    
    # Create offer view
    view = PetFoundView(
        self.cog, 
        self.cog.user_data, 
        self.cog.guild_settings, 
        offered_pet
    )
    embed = view.build_embed()
    
    await interaction.response.edit_message(embed=embed, view=view)
```

## Testing Phase 4
1. Run `[p]petcord`
2. Click "Find a Pet" button
3. Verify pet offer embed displays with:
   - Random species name and emoji
   - Rarity display (stars)
   - Coat and pattern
   - Species info (activity, grooming, diet, lifespan, trait)
   - Adopt and Pass buttons
4. Click "Pass", verify:
   - Cooldown message appears
   - Buttons disabled
   - User data updated with cooldown timestamp
5. Run `[p]petcord` again, verify cooldown is shown
6. Wait or reset cooldown, verify can search again

---

# PHASE 5: Pet Naming

## Objective
Implement the naming modal after adoption, creating the pet in the database.

## Files to Create/Modify

### 5.1 `views/modals.py`
```python
import discord
from discord.ui import Modal, TextInput

class PetNamingModal(Modal):
    """Modal for naming a new pet."""
    
    def __init__(self, cog, user_data, pet_data, guild_settings):
        super().__init__(title="Name Your New Pet!")
        self.cog = cog
        self.user_data = user_data
        self.pet_data = pet_data
        self.guild_settings = guild_settings
        
        self.name_input = TextInput(
            label="Pet Name",
            placeholder="Enter a name for your pet...",
            min_length=2,
            max_length=32,
            required=True
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        import time
        from ..common.models import Pet
        
        name = self.name_input.value.strip()
        
        # Validate name (blacklist check)
        if name.lower() in [w.lower() for w in self.guild_settings.disallowed_names]:
            return await interaction.response.send_message(
                "❌ That name is not allowed. Please try again.",
                ephemeral=True
            )
        
        # Create pet object
        species = self.pet_data["species"]
        new_pet = Pet(
            name=name,
            species_id=species.id,
            coat_color=self.pet_data["coat"],
            pattern=self.pet_data["pattern"],
            rarity=self.pet_data["rarity"],
            hunger=100,
            happiness=100,
            cleanliness=100,
            energy=100,
            health=100,
            bond=0,
            age_days=0,
            life_stage="baby",
            adopted_timestamp=time.time(),
            last_interaction=time.time()
        )
        
        # Save to user
        self.user_data.current_pet = new_pet
        self.user_data.total_pets_owned += 1
        await self.cog.db.save_user(
            interaction.guild.id,
            interaction.user.id,
            self.user_data
        )
        
        # Send success message
        embed = discord.Embed(
            title="🎉 Welcome to the Family!",
            description=f"**{name}** the {species.name} is now your pet!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="What's Next?",
            value="Use `[p]petcord` to view your pet's status and care for them!",
            inline=False
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
```

### 5.2 Update `views/find_pet.py`
Update the adopt button callback:
```python
@discord.ui.button(label="Adopt", emoji="✅", style=discord.ButtonStyle.success)
async def adopt_button(self, interaction: discord.Interaction, button: Button):
    """User wants to adopt this pet."""
    from .modals import PetNamingModal
    
    modal = PetNamingModal(
        self.cog,
        self.user_data,
        self.offered_pet,
        self.guild_settings
    )
    await interaction.response.send_modal(modal)
```

## Testing Phase 5
1. Find a pet and click "Adopt"
2. Verify modal appears with name input field
3. Enter a valid name, submit
4. Verify success message shows pet name
5. Run `[p]petcord`, verify you now have a pet (Phase 6 will show it)
6. Test name blacklist by adding word via debug and trying to use it

---

# PHASE 6: Pet Display

## Objective
Display the current pet's status with stats bars and info when user has a pet.

## Files to Create/Modify

### 6.1 Update `views/main_menu.py`
Add the pet display state:

```python
async def _build_pet_embed(self) -> discord.Embed:
    """Build embed for current pet."""
    pet = self.user_data.current_pet
    species = get_species(pet.species_id)
    
    # Stage display
    stage_days = self._get_stage_day_info(pet)
    
    # Rarity stars
    rarity_display = self._format_rarity(pet.rarity)
    
    embed = discord.Embed(
        title=f'{species.emoji} "{pet.name}" - {species.name}',
        description=f"Stage: {pet.life_stage.title()} ({stage_days}) {rarity_display}\n"
                   f"Coat: {pet.coat_color} | Pattern: {pet.pattern}",
        color=self._get_health_color(pet.health)
    )
    
    # Stats with bars
    stats_text = (
        f"❤️ Health: {format_stat_bar(pet.health)} {pet.health}%\n"
        f"🍖 Hunger: {format_stat_bar(pet.hunger)} {pet.hunger}%{self._warning_icon(pet.hunger)}\n"
        f"😊 Happiness: {format_stat_bar(pet.happiness)} {pet.happiness}%{self._warning_icon(pet.happiness)}\n"
        f"✨ Cleanliness: {format_stat_bar(pet.cleanliness)} {pet.cleanliness}%\n"
        f"💤 Energy: {format_stat_bar(pet.energy)} {pet.energy}%\n"
        f"💕 Bond: {format_stat_bar(pet.bond)} {pet.bond}"
    )
    embed.add_field(name="Stats", value=stats_text, inline=False)
    
    # Daily rating (Phase 9)
    if self.user_data.current_day_scores:
        score = self.user_data.current_day_scores.final_score
        rating = self._get_rating_display(score)
        embed.add_field(
            name="Today's Rating",
            value=f"{rating} ({score:.0f}%)",
            inline=True
        )
    
    return embed

def _format_rarity(self, rarity: str) -> str:
    """Format rarity as stars."""
    mapping = {
        "common": "⭐",
        "uncommon": "⭐⭐",
        "rare": "⭐⭐⭐",
        "very_rare": "⭐⭐⭐⭐",
        "legendary": "⭐⭐⭐⭐⭐",
        "mythical": "🌟"
    }
    return mapping.get(rarity, "⭐")

def _warning_icon(self, value: int) -> str:
    """Return warning icon if stat is low."""
    if value < 20:
        return " 🔴"
    elif value < 40:
        return " ⚠️"
    return ""

def _get_health_color(self, health: int) -> discord.Color:
    """Get embed color based on health."""
    if health < 20:
        return discord.Color.red()
    elif health < 50:
        return discord.Color.orange()
    else:
        return discord.Color.green()
```

### 6.2 Update button setup for pet state
```python
def setup_buttons(self):
    """Add buttons based on user state."""
    if self.user_data.current_pet is None:
        # No pet state
        self.add_item(FindPetButton(self.cog))
        self.add_item(SpeciesGuideButton())
        self.add_item(LeaderboardButton())
    else:
        # Has pet - add interaction buttons
        # Row 1: Care actions
        self.add_item(FeedButton())
        self.add_item(PlayButton())
        self.add_item(GroomButton())
        self.add_item(RestButton())
        # Row 2: More actions
        self.add_item(TreatButton())
        self.add_item(PetButton())
        self.add_item(DetailsButton())
        # Row 3: Settings
        self.add_item(SettingsButton())
```

### 6.3 Create button placeholders for pet actions
```python
class FeedButton(Button):
    def __init__(self):
        super().__init__(label="Feed", emoji="🍖", style=discord.ButtonStyle.primary, row=0)
    
    async def callback(self, interaction):
        await interaction.response.send_message("Feeding... (Phase 7)", ephemeral=True)

# ... similar for PlayButton, GroomButton, RestButton, TreatButton, PetButton, DetailsButton, SettingsButton
```

## Testing Phase 6
1. Have a pet from Phase 5
2. Run `[p]petcord`
3. Verify embed shows:
   - Pet name and species with emoji
   - Life stage and day
   - Rarity stars
   - Coat and pattern
   - All 6 stat bars with percentages
   - Warning icons if any stat is low
4. Verify all action buttons appear:
   - Feed, Play, Groom, Rest (Row 1)
   - Treat, Pet, Details (Row 2)
   - Settings (Row 3)
5. Verify buttons respond with placeholder messages

---

# PHASE 7: Core Actions

## Objective
Implement the core pet care actions: Feed, Play, Groom, Rest, Treat, Pet.

## Files to Create/Modify

### 7.1 `views/pet_actions.py`
```python
import discord
from discord.ui import Button
import time

class ActionButton(Button):
    """Base class for pet action buttons."""
    
    def __init__(self, label, emoji, action_name, stat_changes, cooldown_attr, cooldown_hours, **kwargs):
        super().__init__(label=label, emoji=emoji, style=discord.ButtonStyle.primary, **kwargs)
        self.action_name = action_name
        self.stat_changes = stat_changes  # Dict of stat: change
        self.cooldown_attr = cooldown_attr
        self.cooldown_hours = cooldown_hours
    
    async def callback(self, interaction: discord.Interaction):
        view = self.view
        pet = view.user_data.current_pet
        
        # Check cooldown
        last_used = getattr(pet, self.cooldown_attr, 0)
        cooldown_seconds = self.cooldown_hours * 3600
        time_since = time.time() - last_used
        
        if time_since < cooldown_seconds:
            remaining = cooldown_seconds - time_since
            minutes = int(remaining // 60)
            return await interaction.response.send_message(
                f"⏳ You can {self.action_name} again in **{minutes} minutes**.",
                ephemeral=True
            )
        
        # Apply stat changes
        changes_text = []
        for stat, change in self.stat_changes.items():
            current = getattr(pet, stat)
            new_val = max(0, min(100, current + change))
            setattr(pet, stat, new_val)
            
            arrow = "📈" if change > 0 else "📉"
            changes_text.append(f"{arrow} {stat.title()}: {current} → {new_val}")
        
        # Update cooldown and interaction time
        setattr(pet, self.cooldown_attr, time.time())
        pet.last_interaction = time.time()
        
        # Update user stats
        view.user_data.total_interactions += 1
        if self.action_name == "feed":
            view.user_data.total_feedings += 1
        elif self.action_name == "play":
            view.user_data.total_play_sessions += 1
        # ... etc
        
        # Save
        await view.cog.db.save_user(
            interaction.guild.id,
            interaction.user.id,
            view.user_data
        )
        
        # Show result
        embed = discord.Embed(
            title=f"{self.emoji} {self.action_name.title()}!",
            description="\n".join(changes_text),
            color=discord.Color.green()
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Refresh main view
        new_embed = await view.build_embed()
        await view.message.edit(embed=new_embed)


class FeedButton(ActionButton):
    def __init__(self):
        super().__init__(
            label="Feed",
            emoji="🍖",
            action_name="feed",
            stat_changes={"hunger": 30, "happiness": 5},
            cooldown_attr="last_fed",
            cooldown_hours=4,
            row=0
        )


class PlayButton(ActionButton):
    def __init__(self):
        super().__init__(
            label="Play",
            emoji="🎾",
            action_name="play",
            stat_changes={"happiness": 25, "energy": -15, "bond": 3},
            cooldown_attr="last_played",
            cooldown_hours=2,
            row=0
        )


class GroomButton(ActionButton):
    def __init__(self):
        super().__init__(
            label="Groom",
            emoji="🛁",
            action_name="groom",
            stat_changes={"cleanliness": 35, "happiness": 5},
            cooldown_attr="last_groomed",
            cooldown_hours=6,
            row=0
        )


class RestButton(ActionButton):
    def __init__(self):
        super().__init__(
            label="Rest",
            emoji="💤",
            action_name="rest",
            stat_changes={"energy": 40, "health": 5},
            cooldown_attr="last_rested",
            cooldown_hours=8,
            row=0
        )


class TreatButton(ActionButton):
    def __init__(self):
        super().__init__(
            label="Treat",
            emoji="🍬",
            action_name="treat",
            stat_changes={"happiness": 20, "bond": 5},
            cooldown_attr="last_treated",
            cooldown_hours=24,
            row=1
        )


class PetActionButton(ActionButton):
    """Named differently to avoid conflict with Pet model."""
    def __init__(self):
        super().__init__(
            label="Pet",
            emoji="✋",
            action_name="pet",
            stat_changes={"happiness": 10, "bond": 2},
            cooldown_attr="last_petted",  # Add to Pet model
            cooldown_hours=1,
            row=1
        )
```

### 7.2 `commands/helper_functions.py`
```python
def calculate_stat_change(base_change: int, species_id: str, stat_name: str) -> int:
    """Calculate stat change with species modifiers."""
    species = get_species(species_id)
    category = species.category
    
    # High activity pets get more from play, etc.
    modifiers = {
        "high": 1.2,
        "very_high": 1.3,
        "low": 0.8,
        "very_low": 0.7
    }
    
    # Apply activity modifier to happiness/energy changes
    if stat_name in ["happiness", "energy"]:
        modifier = modifiers.get(species.activity_level, 1.0)
        return int(base_change * modifier)
    
    return base_change
```

## Testing Phase 7
1. Run `[p]petcord` with a pet
2. Click "Feed" - verify:
   - Hunger increases by ~30
   - Happiness increases by ~5
   - Message shows changes
   - Main embed updates
3. Click "Feed" again immediately - verify cooldown message
4. Test all actions: Play, Groom, Rest, Treat, Pet
5. Verify each has correct stat effects and cooldowns
6. Verify user stats increment (total_feedings, etc.)

---

# PHASE 8: Stat Decay

## Objective
Implement background task that decays pet stats over time based on species.

## Files to Create/Modify

### 8.1 `tasks/decay_task.py`
```python
import discord
from redbot.core import commands
import asyncio
import time
from ..common.species import DECAY_MULTIPLIERS, get_species
from ..common.constants import (
    BASE_HUNGER_DECAY, 
    BASE_HAPPINESS_DECAY, 
    BASE_CLEANLINESS_DECAY, 
    BASE_ENERGY_DECAY,
    CRITICAL_THRESHOLD
)

class DecayTask:
    """Background task for stat decay."""
    
    def __init__(self, cog):
        self.cog = cog
        self.task = None
        self.decay_interval = 300  # 5 minutes between decay checks
    
    def start(self):
        """Start the decay task."""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._decay_loop())
    
    def stop(self):
        """Stop the decay task."""
        if self.task:
            self.task.cancel()
    
    async def _decay_loop(self):
        """Main decay loop."""
        while True:
            try:
                await self._process_all_guilds()
            except Exception as e:
                print(f"Decay task error: {e}")
            
            await asyncio.sleep(self.decay_interval)
    
    async def _process_all_guilds(self):
        """Process decay for all guilds."""
        for guild in self.cog.bot.guilds:
            settings = await self.cog.db.get_guild_settings(guild.id)
            if not settings.game_is_enabled:
                continue
            
            users = await self.cog.db.get_all_users(guild.id)
            for user_id, user_data in users.items():
                if user_data.current_pet and not user_data.current_pet.is_in_home:
                    await self._decay_pet(guild.id, user_id, user_data, settings)
    
    async def _decay_pet(self, guild_id, user_id, user_data, settings):
        """Apply decay to a single pet."""
        pet = user_data.current_pet
        species = get_species(pet.species_id)
        multipliers = DECAY_MULTIPLIERS.get(species.category, {})
        
        # Calculate time-based decay
        hours_since_interaction = (time.time() - pet.last_interaction) / 3600
        decay_factor = min(hours_since_interaction, 12) / 12  # Cap at 12 hours
        
        # Apply decays
        hunger_decay = BASE_HUNGER_DECAY * multipliers.get("hunger", 1.0) * decay_factor
        happiness_decay = BASE_HAPPINESS_DECAY * multipliers.get("happiness", 1.0) * decay_factor
        cleanliness_decay = BASE_CLEANLINESS_DECAY * multipliers.get("cleanliness", 1.0) * decay_factor
        energy_decay = BASE_ENERGY_DECAY * multipliers.get("energy", 1.0) * decay_factor
        
        pet.hunger = max(0, pet.hunger - hunger_decay)
        pet.happiness = max(0, pet.happiness - happiness_decay)
        pet.cleanliness = max(0, pet.cleanliness - cleanliness_decay)
        pet.energy = max(0, pet.energy - energy_decay)
        
        # Health impact from critical stats
        health_damage = 0
        if pet.hunger < CRITICAL_THRESHOLD:
            health_damage += 2
        if pet.happiness < CRITICAL_THRESHOLD:
            health_damage += 1
        if pet.cleanliness < CRITICAL_THRESHOLD:
            health_damage += 1
        
        pet.health = max(0, pet.health - health_damage)
        
        # Check for death (if enabled)
        if settings.pet_death_enabled and pet.health <= 0:
            await self._handle_pet_death(guild_id, user_id, user_data, "neglect")
            return
        
        await self.cog.db.save_user(guild_id, user_id, user_data)
    
    async def _handle_pet_death(self, guild_id, user_id, user_data, cause):
        """Handle pet death from neglect."""
        from ..common.models import PetMemorial
        import time
        
        pet = user_data.current_pet
        
        memorial = PetMemorial(
            name=pet.name,
            species_id=pet.species_id,
            coat_color=pet.coat_color,
            pattern=pet.pattern,
            rarity=pet.rarity,
            adopted_timestamp=pet.adopted_timestamp,
            graduated_timestamp=0.0,
            passed_timestamp=time.time(),
            total_lifespan_days=pet.age_days,
            death_cause=cause,
            medal="",
            medal_score=0.0,
            final_bond=pet.bond,
            reached_home=False,
            epitaph_allowed=False
        )
        
        user_data.memorial.append(memorial)
        user_data.current_pet = None
        user_data.pets_lost_to_neglect += 1
        user_data.total_pets_passed += 1
        
        await self.cog.db.save_user(guild_id, user_id, user_data)
```

### 8.2 Update `main.py`
```python
from .tasks.decay_task import DecayTask

class Petcord(UserCommands, commands.Cog):
    def __init__(self, bot):
        # ... existing init
        self.decay_task = DecayTask(self)
    
    async def cog_load(self):
        self.decay_task.start()
    
    async def cog_unload(self):
        self.decay_task.stop()
```

## Testing Phase 8
1. Adopt a pet, note initial stats
2. Wait 5+ minutes (or reduce interval for testing)
3. Run `[p]petcord`, verify stats decreased
4. Verify different species decay at different rates
5. Let stats drop to critical, verify health decreases
6. Enable death, let health hit 0, verify:
   - Pet moved to memorial
   - Death cause is "neglect"
   - User's pets_lost_to_neglect incremented
   - current_pet is None

---

# PHASE 9: Daily Tracking

## Objective
Implement the daily care tracking system that monitors care quality.

## Files to Create/Modify

### 9.1 Add tracking logic to `commands/helper_functions.py`
```python
import time
from ..common.models import DailyCareScore
from ..common.constants import (
    WARNING_THRESHOLD,
    CRITICAL_THRESHOLD
)

def initialize_daily_tracking(user_data):
    """Start tracking for a new day."""
    day_number = user_data.current_pet.age_days + 1
    
    user_data.current_day_start = time.time()
    user_data.current_day_scores = DailyCareScore(
        day_number=day_number,
        date_timestamp=time.time()
    )

def update_daily_tracking(user_data, pet, action: str):
    """Update tracking based on action performed."""
    if not user_data.current_day_scores:
        initialize_daily_tracking(user_data)
    
    scores = user_data.current_day_scores
    
    # Track action counts
    if action == "feed":
        scores.times_fed += 1
    elif action == "play":
        scores.times_played += 1
    elif action == "groom":
        scores.times_groomed += 1
    elif action == "rest":
        scores.times_rested += 1
    elif action == "pet":
        scores.times_petted += 1
    elif action == "treat":
        scores.times_treated += 1
    
    # Update need tracking
    if pet.hunger < 40:
        user_data.total_needs_failed += 1
    else:
        user_data.total_needs_met += 1

def calculate_daily_score(user_data, pet) -> float:
    """Calculate the daily care score."""
    if not user_data.current_day_scores:
        return 0.0
    
    scores = user_data.current_day_scores
    
    # Feeding score: Did they keep hunger above 40?
    feeding_score = 100 if scores.times_fed >= 2 else (50 if scores.times_fed >= 1 else 0)
    
    # Happiness score: Based on current + times played/petted
    happiness_score = min(100, pet.happiness + (scores.times_played * 10) + (scores.times_petted * 5))
    
    # Cleanliness score: Did they groom?
    cleanliness_score = 100 if scores.times_groomed >= 1 else (pet.cleanliness if pet.cleanliness > 50 else 30)
    
    # Energy score: Did they let pet rest?
    energy_score = 100 if scores.times_rested >= 1 else (pet.energy if pet.energy > 30 else 20)
    
    # Bonus score: Extra interactions
    bonus_interactions = scores.times_petted + scores.times_treated
    bonus_score = min(100, bonus_interactions * 25)
    
    # Weighted average
    final_score = (
        feeding_score * 0.30 +
        happiness_score * 0.25 +
        cleanliness_score * 0.20 +
        energy_score * 0.15 +
        bonus_score * 0.10
    )
    
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
```

### 9.2 Add daily rollover to decay task
```python
async def _check_daily_rollover(self, guild_id, user_id, user_data, settings):
    """Check if a new day has started and roll over tracking."""
    if not user_data.current_day_start:
        return
    
    hours_per_day = settings.growth_day_length_hours
    seconds_per_day = hours_per_day * 3600
    
    if time.time() - user_data.current_day_start >= seconds_per_day:
        # Day complete - finalize score
        final_score = calculate_daily_score(user_data, user_data.current_pet)
        
        # Add to history
        user_data.care_history.append(user_data.current_day_scores)
        user_data.current_pet.growth_daily_scores.append(user_data.current_day_scores)
        
        # Update running average
        all_scores = [s.final_score for s in user_data.current_pet.growth_daily_scores]
        user_data.current_pet.growth_average_score = sum(all_scores) / len(all_scores)
        user_data.current_pet.growth_total_days = len(all_scores)
        
        # Age the pet
        user_data.current_pet.age_days += 1
        
        # Start new day
        initialize_daily_tracking(user_data)
```

## Testing Phase 9
1. Adopt a pet
2. Perform various care actions
3. Run `[p]petcord`, verify daily rating shows
4. Check rating reflects actions taken
5. Wait for day rollover (or reduce day length for testing)
6. Verify score saved to history
7. Verify pet aged by 1 day

---

# PHASE 10: Life Stages

## Objective
Implement age progression and life stage transitions.

## Files to Create/Modify

### 10.1 `common/lifecycle.py`
```python
from ..common.species import get_species

# Stage definitions (in pet days)
STAGE_THRESHOLDS = {
    "short": {"baby": 2, "juvenile": 5, "adult": 10, "senior": 14},
    "medium": {"baby": 4, "juvenile": 10, "adult": 21, "senior": 28},
    "long": {"baby": 7, "juvenile": 21, "adult": 42, "senior": 56},
    "extended": {"baby": 10, "juvenile": 30, "adult": 60, "senior": 90}
}

def get_life_stage(pet) -> str:
    """Determine pet's life stage based on age and species."""
    species = get_species(pet.species_id)
    thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
    
    if pet.age_days < thresholds["baby"]:
        return "baby"
    elif pet.age_days < thresholds["juvenile"]:
        return "juvenile"
    elif pet.age_days < thresholds["adult"]:
        return "adult"
    else:
        return "senior"

def check_stage_transition(pet) -> tuple[bool, str, str]:
    """Check if pet should transition stages. Returns (changed, old_stage, new_stage)."""
    new_stage = get_life_stage(pet)
    
    if new_stage != pet.life_stage:
        old_stage = pet.life_stage
        return (True, old_stage, new_stage)
    
    return (False, pet.life_stage, pet.life_stage)

def get_stage_day_info(pet) -> str:
    """Get display text for stage progress."""
    species = get_species(pet.species_id)
    thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
    
    if pet.life_stage == "baby":
        max_day = thresholds["baby"]
    elif pet.life_stage == "juvenile":
        max_day = thresholds["juvenile"]
    elif pet.life_stage == "adult":
        max_day = thresholds["adult"]
    else:
        max_day = thresholds["senior"]
    
    return f"Day {pet.age_days}/{max_day}"
```

### 10.2 Update decay task to check transitions
```python
async def _decay_pet(self, guild_id, user_id, user_data, settings):
    # ... existing decay code ...
    
    # Check for stage transition
    from ..common.lifecycle import check_stage_transition
    import time
    
    changed, old_stage, new_stage = check_stage_transition(pet)
    if changed:
        pet.life_stage = new_stage
        
        # Check for graduation readiness
        if new_stage == "adult" and not pet.is_in_home:
            pet.ready_to_graduate = True
            pet.reached_adult_timestamp = time.time()
```

## Testing Phase 10
1. Adopt a pet
2. Reduce day length to test quickly (e.g., 1 minute)
3. Wait for days to pass
4. Verify pet transitions: baby → juvenile → adult
5. Verify stage display updates correctly
6. Verify `ready_to_graduate` becomes True at adult

---

# PHASE 11: Graduation

## Objective
Implement the graduation ceremony when pets reach adulthood.

## Files to Create/Modify

### 11.1 `views/graduation.py`
```python
import discord
from discord.ui import View, Button
from ..common.constants import GOLD_THRESHOLD, SILVER_THRESHOLD, BRONZE_THRESHOLD

class GraduationView(View):
    """View for pet graduation ceremony."""
    
    def __init__(self, cog, user_data, guild_settings):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.message = None
    
    def build_embed(self) -> discord.Embed:
        """Build graduation celebration embed."""
        pet = self.user_data.current_pet
        
        # Calculate medal
        avg_score = pet.growth_average_score
        if avg_score >= GOLD_THRESHOLD:
            medal = "🥇 GOLD"
            medal_key = "gold"
        elif avg_score >= SILVER_THRESHOLD:
            medal = "🥈 SILVER"
            medal_key = "silver"
        elif avg_score >= BRONZE_THRESHOLD:
            medal = "🥉 BRONZE"
            medal_key = "bronze"
        else:
            medal = "❌ No Medal"
            medal_key = ""
        
        embed = discord.Embed(
            title="🎉 CONGRATULATIONS! 🎉",
            description=f'**"{pet.name}"** has grown into an Adult!',
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🏅 Medal Earned",
            value=f"{medal}\nFinal Score: {avg_score:.1f}%\nGrowth Days: {pet.growth_total_days}",
            inline=False
        )
        
        # Care summary
        scores = pet.growth_daily_scores
        perfect = len([s for s in scores if s.rating == "perfect"])
        excellent = len([s for s in scores if s.rating == "excellent"])
        good = len([s for s in scores if s.rating == "good"])
        
        embed.add_field(
            name="Care Summary",
            value=f"• Perfect Days: {perfect}\n"
                  f"• Excellent Days: {excellent}\n"
                  f"• Good Days: {good}\n"
                  f"• Final Bond: {pet.bond}",
            inline=False
        )
        
        embed.add_field(
            name="🏠 Ready for Home!",
            value=f'"{pet.name}" is ready to move to your Home!\n'
                  "You'll still be able to visit and interact with them anytime.",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="Send to Home", emoji="🏠", style=discord.ButtonStyle.success)
    async def send_to_home(self, interaction: discord.Interaction, button: Button):
        """Graduate pet to Home."""
        import time
        
        pet = self.user_data.current_pet
        
        # Calculate and set medal
        avg_score = pet.growth_average_score
        if avg_score >= GOLD_THRESHOLD:
            pet.medal = "gold"
            bond_bonus = 20
            self.user_data.gold_medals += 1
        elif avg_score >= SILVER_THRESHOLD:
            pet.medal = "silver"
            bond_bonus = 10
            self.user_data.silver_medals += 1
        elif avg_score >= BRONZE_THRESHOLD:
            pet.medal = "bronze"
            bond_bonus = 5
            self.user_data.bronze_medals += 1
        else:
            pet.medal = ""
            bond_bonus = 0
        
        pet.medal_score = avg_score
        pet.bond = min(100, pet.bond + bond_bonus)
        pet.is_in_home = True
        pet.ready_to_graduate = False
        pet.graduated_timestamp = time.time()
        
        # Move pet to home
        self.user_data.home_pets.append(pet)
        self.user_data.current_pet = None
        self.user_data.total_pets_graduated += 1
        self.user_data.total_medals += 1 if pet.medal else 0
        
        # Update medal streak
        if pet.medal == "gold":
            self.user_data.current_medal_streak += 1
            self.user_data.best_medal_streak = max(
                self.user_data.best_medal_streak,
                self.user_data.current_medal_streak
            )
        else:
            self.user_data.current_medal_streak = 0
        
        await self.cog.db.save_user(
            interaction.guild.id,
            interaction.user.id,
            self.user_data
        )
        
        embed = discord.Embed(
            title="🏠 Welcome Home!",
            description=f'"{pet.name}" is now living in your Home!\n\n'
                       f"Use `[p]pcstat` and click **View Home** to visit them.",
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
```

### 11.2 Update main menu to show graduation
```python
async def build_embed(self) -> discord.Embed:
    """Build the main menu embed."""
    if self.user_data.current_pet is None:
        return await self._build_no_pet_embed()
    elif self.user_data.current_pet.ready_to_graduate:
        # Show graduation view instead
        return None  # Signal to use GraduationView
    else:
        return await self._build_pet_embed()
```

## Testing Phase 11
1. Raise a pet to adult stage
2. Run `[p]petcord`
3. Verify graduation embed shows:
   - Celebration message
   - Medal based on average score
   - Care summary (perfect/excellent/good days)
   - Final bond
4. Click "Send to Home"
5. Verify pet moved to home_pets list
6. Verify user stats updated (medals, graduated count)
7. Run `[p]petcord`, verify no pet state

---

# PHASE 12: Home System

## Objective
Implement Home pet viewing and optional interactions.

## Files to Create/Modify

### 12.1 `views/home_views.py`
```python
import discord
from discord.ui import View, Button, Select

class HomeListView(View):
    """View for home pet list."""
    
    def __init__(self, cog, user_data):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.message = None
        
        if user_data.home_pets:
            self.add_item(PetSelect(user_data.home_pets))
    
    def build_embed(self) -> discord.Embed:
        """Build home list embed."""
        embed = discord.Embed(
            title=f"🏠 Your Home - {len(self.user_data.home_pets)}/{self.user_data.home_capacity} Pets",
            color=discord.Color.blue()
        )
        
        if not self.user_data.home_pets:
            embed.description = "Your home is empty.\nRaise a pet to adulthood to add them here!"
            return embed
        
        for i, pet in enumerate(self.user_data.home_pets, 1):
            medal_display = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(pet.medal, "")
            embed.add_field(
                name=f'{i}. "{pet.name}" - {pet.species_id.replace("_", " ").title()} {medal_display}',
                value=f"{pet.life_stage.title()} • Day {pet.age_days} • Bond: {pet.bond}",
                inline=False
            )
        
        return embed
    
    @discord.ui.button(label="Back to Stats", emoji="◀️", style=discord.ButtonStyle.secondary, row=2)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        # Return to stats view
        pass


class PetSelect(Select):
    """Dropdown to select a home pet."""
    
    def __init__(self, pets):
        options = [
            discord.SelectOption(
                label=pet.name,
                description=f"{pet.species_id.replace('_', ' ').title()} - {pet.life_stage.title()}",
                value=str(i)
            )
            for i, pet in enumerate(pets)
        ]
        super().__init__(placeholder="Select a pet to view...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        pet_index = int(self.values[0])
        # Show individual pet view
        pass


class HomePetView(View):
    """View for individual home pet."""
    
    def __init__(self, cog, user_data, pet_index):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.pet_index = pet_index
        self.pet = user_data.home_pets[pet_index]
    
    def build_embed(self) -> discord.Embed:
        """Build individual pet embed."""
        pet = self.pet
        species = get_species(pet.species_id)
        medal_display = {"gold": "🥇 Gold", "silver": "🥈 Silver", "bronze": "🥉 Bronze"}.get(pet.medal, "")
        
        embed = discord.Embed(
            title=f'{species.emoji} "{pet.name}" - {species.name}',
            description=f"Stage: {pet.life_stage.title()} • Living in Home\n"
                       f"Medal: {medal_display} ({pet.medal_score:.1f}%)" if pet.medal else "",
            color=discord.Color.green()
        )
        
        # Simplified stats for home pets
        embed.add_field(
            name="Status",
            value=f"😊 Happiness: {pet.happiness}%\n"
                  f"✨ Cleanliness: {pet.cleanliness}%\n"
                  f"💕 Bond: {pet.bond}",
            inline=False
        )
        
        # Calculate time since graduation
        days_in_home = (time.time() - pet.graduated_timestamp) / 86400
        embed.add_field(
            name="With you for",
            value=f"{int(days_in_home)} days\nGraduated: {format_timestamp(pet.graduated_timestamp)}",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="Pet", emoji="✋", style=discord.ButtonStyle.primary)
    async def pet_button(self, interaction: discord.Interaction, button: Button):
        self.pet.happiness = min(100, self.pet.happiness + 10)
        self.pet.bond = min(100, self.pet.bond + 2)
        await self._save_and_respond(interaction, "You petted your companion!")
    
    @discord.ui.button(label="Groom", emoji="🛁", style=discord.ButtonStyle.primary)
    async def groom_button(self, interaction: discord.Interaction, button: Button):
        self.pet.cleanliness = min(100, self.pet.cleanliness + 25)
        await self._save_and_respond(interaction, "You groomed your companion!")
    
    @discord.ui.button(label="Treat", emoji="🍬", style=discord.ButtonStyle.primary)
    async def treat_button(self, interaction: discord.Interaction, button: Button):
        self.pet.happiness = min(100, self.pet.happiness + 15)
        self.pet.bond = min(100, self.pet.bond + 3)
        await self._save_and_respond(interaction, "You gave your companion a treat!")
    
    async def _save_and_respond(self, interaction, message):
        await self.cog.db.save_user(
            interaction.guild.id,
            interaction.user.id,
            self.user_data
        )
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
```

## Testing Phase 12
1. Have a pet in Home (from Phase 11)
2. Access Home via pcstat (Phase 15) or debug command
3. Verify home list shows all home pets
4. Select a pet, verify individual view
5. Test Pet, Groom, Treat buttons
6. Verify stats update correctly
7. Verify no cooldowns for home pets (optional interactions)

---

# PHASE 13: Aging & Death (Old Age)

## Objective
Implement continued aging in Home and natural death from old age.

## Files to Create/Modify

### 13.1 Update decay task for home pets
```python
async def _process_home_pets(self, guild_id, user_id, user_data, settings):
    """Process aging for home pets."""
    from ..common.lifecycle import STAGE_THRESHOLDS, get_species
    import time
    
    for i, pet in enumerate(user_data.home_pets[:]):  # Copy list for safe iteration
        # Slow decay for home pets (cosmetic only)
        pet.happiness = max(50, pet.happiness - 1)  # Never drops below 50
        pet.cleanliness = max(40, pet.cleanliness - 0.5)
        
        # Age the pet (home pets age slower)
        hours_since_check = self.decay_interval / 3600
        pet.age_days += hours_since_check / 24  # Fractional aging
        
        # Check stage transition
        changed, old_stage, new_stage = check_stage_transition(pet)
        if changed:
            pet.life_stage = new_stage
        
        # Check for natural death
        species = get_species(pet.species_id)
        thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
        max_age = thresholds["senior"] * 1.5  # 50% beyond senior threshold
        
        if pet.age_days >= max_age:
            await self._handle_natural_death(guild_id, user_id, user_data, pet, i)
            continue
    
    await self.cog.db.save_user(guild_id, user_id, user_data)

async def _handle_natural_death(self, guild_id, user_id, user_data, pet, index):
    """Handle natural death from old age."""
    from ..common.models import PetMemorial
    import time
    
    memorial = PetMemorial(
        name=pet.name,
        species_id=pet.species_id,
        coat_color=pet.coat_color,
        pattern=pet.pattern,
        rarity=pet.rarity,
        adopted_timestamp=pet.adopted_timestamp,
        graduated_timestamp=pet.graduated_timestamp,
        passed_timestamp=time.time(),
        total_lifespan_days=int(pet.age_days),
        death_cause="old_age",
        medal=pet.medal,
        medal_score=pet.medal_score,
        final_bond=pet.bond,
        reached_home=True,
        epitaph_allowed=True
    )
    
    user_data.memorial.append(memorial)
    user_data.home_pets.pop(index)
    user_data.pets_passed_naturally += 1
    user_data.total_pets_passed += 1
    user_data.longest_pet_lifespan = max(user_data.longest_pet_lifespan, int(pet.age_days))
```

## Testing Phase 13
1. Have a pet in Home
2. Reduce lifespan thresholds for testing
3. Wait for pet to reach max age
4. Verify pet moves to memorial
5. Verify death_cause is "old_age"
6. Verify epitaph_allowed is True
7. Verify user stats updated correctly

---

# PHASE 14: Memorial

## Objective
Implement memorial viewing and epitaph setting.

## Files to Create/Modify

### 14.1 `views/memorial.py`
```python
import discord
from discord.ui import View, Button, Select, Modal, TextInput

class MemorialView(View):
    """View for pet memorial."""
    
    def __init__(self, cog, user_data):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        
        if user_data.memorial:
            self.add_item(MemorialSelect(user_data.memorial))
    
    def build_embed(self) -> discord.Embed:
        """Build memorial embed."""
        embed = discord.Embed(
            title="🪦 Pet Memorial",
            description="In loving memory...",
            color=discord.Color.dark_grey()
        )
        
        if not self.user_data.memorial:
            embed.add_field(
                name="Empty",
                value="No pets in memorial yet.",
                inline=False
            )
            return embed
        
        for pet in self.user_data.memorial:
            icon = "🕊️" if pet.death_cause == "old_age" else "💔"
            medal = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(pet.medal, "")
            
            if pet.death_cause == "old_age":
                death_text = f"Passed peacefully after {pet.total_lifespan_days} days"
            else:
                death_text = f"Lost on day {pet.total_lifespan_days}"
            
            epitaph_text = f'"{pet.epitaph}"' if pet.epitaph else "(Click to set epitaph)" if pet.epitaph_allowed else "(Epitaph not available)"
            
            embed.add_field(
                name=f'{icon} "{pet.name}" - {pet.species_id.replace("_", " ").title()} {medal}',
                value=f"{death_text}\n{epitaph_text}",
                inline=False
            )
        
        return embed


class MemorialSelect(Select):
    """Select to choose a memorial entry."""
    
    def __init__(self, memorial):
        options = [
            discord.SelectOption(
                label=pet.name,
                description=f"{'Passed peacefully' if pet.death_cause == 'old_age' else 'Lost'}",
                value=str(i)
            )
            for i, pet in enumerate(memorial)
        ]
        super().__init__(placeholder="Select pet to view/set epitaph...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        pet = self.view.user_data.memorial[index]
        
        if pet.epitaph_allowed and not pet.epitaph:
            # Show epitaph modal
            modal = EpitaphModal(self.view.cog, self.view.user_data, index)
            await interaction.response.send_modal(modal)
        else:
            # Just show details
            await interaction.response.send_message(
                f"**{pet.name}**\nBond: {pet.final_bond}\n"
                f'Epitaph: "{pet.epitaph}"' if pet.epitaph else "No epitaph set.",
                ephemeral=True
            )


class EpitaphModal(Modal):
    """Modal for setting epitaph."""
    
    def __init__(self, cog, user_data, memorial_index):
        super().__init__(title="Set Epitaph")
        self.cog = cog
        self.user_data = user_data
        self.memorial_index = memorial_index
        
        self.epitaph_input = TextInput(
            label="Epitaph",
            placeholder="Write a short memorial message...",
            max_length=100,
            required=True
        )
        self.add_item(self.epitaph_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.user_data.memorial[self.memorial_index].epitaph = self.epitaph_input.value
        
        await self.cog.db.save_user(
            interaction.guild.id,
            interaction.user.id,
            self.user_data
        )
        
        await interaction.response.send_message(
            "✅ Epitaph saved.",
            ephemeral=True
        )
```

## Testing Phase 14
1. Have pets in memorial (both old_age and neglect)
2. View memorial
3. Verify old_age pets show 🕊️, can set epitaph
4. Verify neglect pets show 💔, cannot set epitaph
5. Set epitaph via modal
6. Verify epitaph persists

---

# PHASE 15: Statistics (pcstat)

## Objective
Implement the `[p]pcstat` command with full statistics display.

## Files to Create/Modify

### 15.1 `views/stat_views.py`
```python
import discord
from discord.ui import View, Button

class StatsView(View):
    """Main statistics view."""
    
    def __init__(self, cog, user_data):
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
    
    def build_embed(self) -> discord.Embed:
        """Build full stats embed."""
        user = self.user_data
        
        embed = discord.Embed(
            title="📊 Petcord Stats",
            color=discord.Color.blue()
        )
        
        # Medals
        embed.add_field(
            name="🏅 Medals Earned",
            value=f"🥇 Gold: {user.gold_medals}  🥈 Silver: {user.silver_medals}  🥉 Bronze: {user.bronze_medals}\n"
                  f"Current Streak: {'🥇' * user.current_medal_streak if user.current_medal_streak else 'None'}\n"
                  f"Best Streak: {user.best_medal_streak} Gold",
            inline=False
        )
        
        # Lifetime stats
        embed.add_field(
            name="📈 Lifetime Stats",
            value=f"Pets Raised: {user.total_pets_owned}\n"
                  f"Pets Graduated: {user.total_pets_graduated}\n"
                  f"Pets Released: {user.total_pets_released}\n"
                  f"🕊️ Passed Peacefully: {user.pets_passed_naturally}\n"
                  f"💔 Lost to Neglect: {user.pets_lost_to_neglect}\n"
                  f"Currently in Home: {len(user.home_pets)}/{user.home_capacity}",
            inline=False
        )
        
        # Care performance
        total_needs = user.total_needs_met + user.total_needs_failed
        success_rate = (user.total_needs_met / total_needs * 100) if total_needs > 0 else 0
        embed.add_field(
            name="💕 Care Performance",
            value=f"Needs Met: {user.total_needs_met}\n"
                  f"Needs Failed: {user.total_needs_failed}\n"
                  f"Success Rate: {success_rate:.1f}%",
            inline=False
        )
        
        # Interaction stats
        embed.add_field(
            name="🎮 Interaction Stats",
            value=f"Total Interactions: {user.total_interactions:,}\n"
                  f"Total Feedings: {user.total_feedings:,}\n"
                  f"Total Play Sessions: {user.total_play_sessions:,}\n"
                  f"Highest Bond: {user.highest_bond_achieved}\n"
                  f"Longest Lifespan: {user.longest_pet_lifespan} days",
            inline=False
        )
        
        # Achievements count
        embed.add_field(
            name="🏆 Achievements",
            value=f"{len(user.achievements)}/50 unlocked",
            inline=False
        )
        
        return embed
    
    @discord.ui.button(label="View Home", emoji="🏠", style=discord.ButtonStyle.primary)
    async def home_button(self, interaction: discord.Interaction, button: Button):
        from .home_views import HomeListView
        view = HomeListView(self.cog, self.user_data)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Memorial", emoji="🪦", style=discord.ButtonStyle.secondary)
    async def memorial_button(self, interaction: discord.Interaction, button: Button):
        from .memorial import MemorialView
        view = MemorialView(self.cog, self.user_data)
        embed = view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)
    
    @discord.ui.button(label="Achievements", emoji="🏆", style=discord.ButtonStyle.secondary)
    async def achievements_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Achievements coming in Phase 17!", ephemeral=True)
    
    @discord.ui.button(label="Leaderboard", emoji="📊", style=discord.ButtonStyle.secondary)
    async def leaderboard_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Leaderboard coming soon!", ephemeral=True)
```

### 15.2 Update `commands/user_commands.py`
```python
@commands.command(name="pcstat")
@commands.guild_only()
async def pcstat(self, ctx: commands.Context):
    """View your Petcord statistics, Home, and Memorial."""
    user_data = await self.db.get_user(ctx.guild.id, ctx.author.id)
    
    view = StatsView(self, user_data)
    embed = view.build_embed()
    
    await ctx.send(embed=embed, view=view)
```

## Testing Phase 15
1. Run `[p]pcstat`
2. Verify all stats display correctly
3. Test View Home button → HomeListView
4. Test Memorial button → MemorialView
5. Verify navigation works between views

---

# PHASE 16: Admin Commands

## Objective
Implement the `[p]pcset` admin command group.

## Files to Create/Modify

### 16.1 `commands/admin_commands.py`
```python
import discord
from redbot.core import commands
from ..abc import MixinMeta

class AdminCommands(MixinMeta):
    """Admin commands for Petcord configuration."""
    
    @commands.group(name="pcset")
    @commands.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    async def pcset(self, ctx: commands.Context):
        """Petcord server configuration."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    @pcset.command(name="toggle")
    async def pcset_toggle(self, ctx: commands.Context):
        """Enable or disable Petcord for this server."""
        settings = await self.db.get_guild_settings(ctx.guild.id)
        settings.game_is_enabled = not settings.game_is_enabled
        await self.db.save_guild_settings(ctx.guild.id, settings)
        
        state = "enabled" if settings.game_is_enabled else "disabled"
        await ctx.send(f"✅ Petcord is now **{state}** for this server.")
    
    @pcset.command(name="display")
    async def pcset_display(self, ctx: commands.Context):
        """Show current server settings."""
        settings = await self.db.get_guild_settings(ctx.guild.id)
        
        embed = discord.Embed(title="⚙️ Petcord Settings", color=discord.Color.blue())
        embed.add_field(name="Game Enabled", value="✅ Yes" if settings.game_is_enabled else "❌ No")
        embed.add_field(name="Find Cooldown", value=f"{settings.find_cooldown_minutes} minutes")
        embed.add_field(name="Pet Death", value="✅ Enabled" if settings.pet_death_enabled else "❌ Disabled")
        embed.add_field(name="Home Capacity", value=f"Default: {settings.default_home_capacity}, Max: {settings.max_home_capacity}")
        embed.add_field(name="Medal Thresholds", value=f"🥇 {settings.medal_gold_threshold}% | 🥈 {settings.medal_silver_threshold}% | 🥉 {settings.medal_bronze_threshold}%")
        
        await ctx.send(embed=embed)
    
    @pcset.command(name="cooldown")
    async def pcset_cooldown(self, ctx: commands.Context, minutes: int):
        """Set the cooldown after declining a pet (in minutes)."""
        if minutes < 1 or minutes > 1440:
            return await ctx.send("❌ Cooldown must be between 1 and 1440 minutes.")
        
        settings = await self.db.get_guild_settings(ctx.guild.id)
        settings.find_cooldown_minutes = minutes
        await self.db.save_guild_settings(ctx.guild.id, settings)
        
        await ctx.send(f"✅ Find cooldown set to **{minutes} minutes**.")
    
    @pcset.command(name="death")
    async def pcset_death(self, ctx: commands.Context, toggle: bool):
        """Enable or disable pet death from neglect."""
        settings = await self.db.get_guild_settings(ctx.guild.id)
        settings.pet_death_enabled = toggle
        await self.db.save_guild_settings(ctx.guild.id, settings)
        
        state = "enabled" if toggle else "disabled"
        await ctx.send(f"✅ Pet death from neglect is now **{state}**.")
    
    @pcset.command(name="medals")
    async def pcset_medals(self, ctx: commands.Context, gold: float, silver: float, bronze: float):
        """Set medal score thresholds."""
        if not (bronze < silver < gold <= 100):
            return await ctx.send("❌ Invalid thresholds. Must be: bronze < silver < gold ≤ 100")
        
        settings = await self.db.get_guild_settings(ctx.guild.id)
        settings.medal_gold_threshold = gold
        settings.medal_silver_threshold = silver
        settings.medal_bronze_threshold = bronze
        await self.db.save_guild_settings(ctx.guild.id, settings)
        
        await ctx.send(f"✅ Medal thresholds set: 🥇 {gold}% | 🥈 {silver}% | 🥉 {bronze}%")
    
    @pcset.group(name="blacklist")
    async def pcset_blacklist(self, ctx: commands.Context):
        """Manage name blacklist."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    @pcset_blacklist.command(name="add")
    async def blacklist_add(self, ctx: commands.Context, word: str):
        """Add a word to the name blacklist."""
        settings = await self.db.get_guild_settings(ctx.guild.id)
        if word.lower() not in settings.disallowed_names:
            settings.disallowed_names.append(word.lower())
            await self.db.save_guild_settings(ctx.guild.id, settings)
            await ctx.send(f"✅ Added **{word}** to blacklist.")
        else:
            await ctx.send("⚠️ Word already in blacklist.")
    
    @pcset_blacklist.command(name="remove")
    async def blacklist_remove(self, ctx: commands.Context, word: str):
        """Remove a word from the name blacklist."""
        settings = await self.db.get_guild_settings(ctx.guild.id)
        if word.lower() in settings.disallowed_names:
            settings.disallowed_names.remove(word.lower())
            await self.db.save_guild_settings(ctx.guild.id, settings)
            await ctx.send(f"✅ Removed **{word}** from blacklist.")
        else:
            await ctx.send("⚠️ Word not in blacklist.")
    
    @pcset_blacklist.command(name="list")
    async def blacklist_list(self, ctx: commands.Context):
        """Show blacklisted words."""
        settings = await self.db.get_guild_settings(ctx.guild.id)
        if settings.disallowed_names:
            await ctx.send(f"**Blacklisted words:** {', '.join(settings.disallowed_names)}")
        else:
            await ctx.send("No words blacklisted.")
```

### 16.2 Update `main.py` to include AdminCommands
```python
from .commands.admin_commands import AdminCommands

class Petcord(UserCommands, AdminCommands, commands.Cog):
    ...
```

## Testing Phase 16
1. Run `[p]pcset` - verify help shows
2. Test `[p]pcset toggle` - enable/disable game
3. Test `[p]pcset display` - show settings
4. Test `[p]pcset cooldown 60` - change cooldown
5. Test `[p]pcset death true/false` - toggle death
6. Test `[p]pcset medals 90 75 55` - change thresholds
7. Test blacklist commands
8. Verify all settings persist

---

# PHASE 17: Achievements

## Objective
Implement the achievement system.

## Files to Create/Modify

### 17.1 `common/achievements.py`
```python
from typing import List, Dict
from pydantic import BaseModel

class AchievementDef(BaseModel):
    id: str
    name: str
    description: str
    category: str  # "adoption", "care", "medals", "home", "special"
    requirement: str  # Human-readable requirement
    check_function: str  # Name of function to check if earned

ACHIEVEMENTS: Dict[str, AchievementDef] = {
    "first_friend": AchievementDef(
        id="first_friend",
        name="First Friend",
        description="Adopt your first pet",
        category="adoption",
        requirement="Adopt 1 pet",
        check_function="check_first_friend"
    ),
    "first_gold": AchievementDef(
        id="first_gold",
        name="First Gold",
        description="Earn your first Gold Medal",
        category="medals",
        requirement="Earn 1 Gold Medal",
        check_function="check_first_gold"
    ),
    # ... add all achievements from design doc
}

def check_first_friend(user_data) -> bool:
    return user_data.total_pets_owned >= 1

def check_first_gold(user_data) -> bool:
    return user_data.gold_medals >= 1

def check_homeowner(user_data) -> bool:
    return user_data.total_pets_graduated >= 1

def check_gentle_goodbye(user_data) -> bool:
    return user_data.pets_passed_naturally >= 1

# ... implement all check functions

def check_all_achievements(user_data) -> List[str]:
    """Check for newly earned achievements. Returns list of new achievement IDs."""
    earned = [a.id for a in user_data.achievements]
    new_achievements = []
    
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id not in earned:
            check_func = globals().get(ach.check_function)
            if check_func and check_func(user_data):
                new_achievements.append(ach_id)
    
    return new_achievements
```

### 17.2 Integrate achievement checking
Call `check_all_achievements()` after significant actions:
- After adopting a pet
- After graduating a pet
- After pet passes away
- After earning medal

### 17.3 Create achievements view
Display earned/unearned achievements organized by category.

## Testing Phase 17
1. Adopt first pet, check for "First Friend" achievement
2. Graduate pet with gold, check for "First Gold"
3. View achievements list
4. Verify achievement notifications

---

# PHASE 18: Polish

## Objective
Final refinements, bug fixes, and complete integration.

## Tasks

### 18.1 Code Review
- Review all phases for consistency
- Ensure error handling everywhere
- Add logging for debug purposes
- Optimize database calls

### 18.2 UI Polish
- Consistent embed colors
- Clear error messages
- Smooth navigation between views
- Timeout handling for all views

### 18.3 Species Guide Implementation
- Paginated species browser
- Filter by category/rarity
- Show species details

### 18.4 Leaderboard Implementation
- Server leaderboards for:
  - Most gold medals
  - Longest medal streaks
  - Highest total pets raised
  - Highest bond achieved

### 18.5 Final Testing
- Full game loop test:
  1. Enable game (admin)
  2. Find and adopt pet
  3. Name pet
  4. Care for pet over multiple days
  5. Watch pet grow through stages
  6. Graduate to Home
  7. Continue caring in Home
  8. Pet passes naturally
  9. Set epitaph
  10. View all stats
- Edge case testing
- Multi-user testing
- Performance testing

---

## Implementation Notes

### Key Patterns to Follow
1. **Reference existing cogs** - Use DinoCollector and GAFishing as patterns
2. **Pydantic models** - All data structures use Pydantic
3. **Button-based UI** - Minimize commands, maximize buttons
4. **Database management** - Use Config-backed database class
5. **Error handling** - Always handle interaction errors gracefully
6. **View timeouts** - All views should have reasonable timeouts

### Testing Each Phase
After each phase:
1. Load the cog successfully
2. Test the specific feature added
3. Verify no regressions in previous features
4. Check data persistence (reload cog, verify data)
5. Test edge cases

### Phase Dependencies
- Phases 1-6 must be done in order
- Phases 7-10 can be parallelized somewhat
- Phases 11-14 depend on 10
- Phase 15 can be done after 12
- Phase 16 can be done anytime after 1
- Phases 17-18 are final polish

---

*Guide Version: 1.0*
*Created: February 2026*
*For: PETCORD_DESIGN.md v1.5*
