"""
Species Guide view for browsing all available species.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button, Select
from typing import TYPE_CHECKING, Optional, List

from ..database.species import (
    SPECIES_DATABASE, 
    SpeciesData, 
    get_species_by_category,
    get_all_categories,
    get_species_by_rarity,
    get_all_rarities
)

if TYPE_CHECKING:
    from ..abc import CompositeMetaClass


SPECIES_PER_PAGE = 5


def get_rarity_emoji(rarity: str) -> str:
    """Get emoji for rarity level."""
    return {
        "common": "⚪",
        "uncommon": "🟢",
        "rare": "🔵",
        "very_rare": "🟣",
        "legendary": "🟡",
        "mythical": "🌈"
    }.get(rarity, "⚪")


def get_category_emoji(category: str) -> str:
    """Get emoji for category."""
    return {
        "dogs": "🐕",
        "cats": "🐱",
        "small_mammals": "🐹",
        "reptiles": "🦎",
        "birds": "🐦",
        "aquatic": "🐠",
        "exotic": "🦄"
    }.get(category, "🐾")


def get_difficulty_display(difficulty: str) -> str:
    """Get display string for care difficulty."""
    displays = {
        "easy": "🟢 Easy",
        "medium": "🟡 Medium",
        "hard": "🟠 Hard",
        "expert": "🔴 Expert"
    }
    return displays.get(difficulty, difficulty.title())


class SpeciesGuideView(View):
    """View for browsing species."""
    
    def __init__(
        self, 
        cog: "CompositeMetaClass",
        author_id: int,
        *,
        timeout: float = 300.0
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.author_id = author_id
        self.message: Optional[discord.Message] = None
        
        # Filtering state
        self.current_category: Optional[str] = None  # None = all
        self.current_rarity: Optional[str] = None  # None = all
        self.page = 0
        
        self._setup_components()
    
    def _setup_components(self) -> None:
        """Set up view components."""
        self.clear_items()
        
        # Row 0: Category filter
        self.add_item(CategorySelect(self.current_category))
        
        # Row 1: Rarity filter
        self.add_item(RaritySelect(self.current_rarity))
        
        # Row 2: Navigation
        self.add_item(PrevPageButton())
        self.add_item(PageIndicator(self.page, self._get_max_pages()))
        self.add_item(NextPageButton())
        self.add_item(BackButton())
    
    def _get_filtered_species(self) -> List[SpeciesData]:
        """Get species filtered by current selections."""
        species_list = list(SPECIES_DATABASE.values())
        
        if self.current_category:
            species_list = [s for s in species_list if s.category == self.current_category]
        
        if self.current_rarity:
            species_list = [s for s in species_list if s.rarity == self.current_rarity]
        
        # Sort by category, then rarity, then name
        rarity_order = ["common", "uncommon", "rare", "very_rare", "legendary", "mythical"]
        species_list.sort(key=lambda s: (s.category, rarity_order.index(s.rarity) if s.rarity in rarity_order else 99, s.name))
        
        return species_list
    
    def _get_max_pages(self) -> int:
        """Get maximum page number."""
        species = self._get_filtered_species()
        return max(0, (len(species) - 1) // SPECIES_PER_PAGE)
    
    async def build_embed(self) -> discord.Embed:
        """Build the species guide embed."""
        species_list = self._get_filtered_species()
        max_pages = self._get_max_pages()
        
        # Clamp page
        self.page = max(0, min(self.page, max_pages))
        
        # Get current page species
        start_idx = self.page * SPECIES_PER_PAGE
        end_idx = start_idx + SPECIES_PER_PAGE
        page_species = species_list[start_idx:end_idx]
        
        # Build title with filters
        title_parts = ["📖 Species Guide"]
        if self.current_category:
            title_parts.append(f"({get_category_emoji(self.current_category)} {self.current_category.replace('_', ' ').title()})")
        if self.current_rarity:
            title_parts.append(f"({get_rarity_emoji(self.current_rarity)} {self.current_rarity.replace('_', ' ').title()})")
        
        embed = discord.Embed(
            title=" ".join(title_parts),
            color=discord.Color.teal()
        )
        
        if not species_list:
            embed.description = "No species match your filters. Try adjusting the category or rarity filter."
        else:
            embed.description = f"Showing {len(species_list)} species"
            
            for species in page_species:
                # Build field for each species
                rarity_emoji = get_rarity_emoji(species.rarity)
                difficulty = get_difficulty_display(species.care_difficulty)
                
                field_value = (
                    f"{rarity_emoji} **{species.rarity.replace('_', ' ').title()}** • {difficulty}\n"
                    f"🎯 *{species.temperament}*\n"
                    f"⚡ Activity: {species.activity_level.replace('_', ' ').title()} • "
                    f"💕 Social: {species.social_need.replace('_', ' ').title()}"
                )
                
                if species.unique_interaction:
                    field_value += f"\n✨ Special: {species.unique_interaction}"
                
                embed.add_field(
                    name=f"{species.emoji} {species.name}",
                    value=field_value,
                    inline=False
                )
        
        embed.set_footer(text=f"Page {self.page + 1}/{max_pages + 1} • {len(SPECIES_DATABASE)} total species")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to interact."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your species guide! Use your own menu.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


class CategorySelect(Select):
    """Dropdown to filter by category."""
    
    def __init__(self, current: Optional[str]):
        options = [
            discord.SelectOption(
                label="All Categories",
                value="all",
                emoji="📋",
                default=(current is None)
            )
        ]
        
        categories = [
            ("dogs", "🐕", "Dogs"),
            ("cats", "🐱", "Cats"),
            ("small_mammals", "🐹", "Small Mammals"),
            ("reptiles", "🦎", "Reptiles"),
            ("birds", "🐦", "Birds"),
            ("aquatic", "🐠", "Aquatic"),
            ("exotic", "🦄", "Exotic")
        ]
        
        for cat_id, emoji, name in categories:
            options.append(discord.SelectOption(
                label=name,
                value=cat_id,
                emoji=emoji,
                default=(current == cat_id)
            ))
        
        super().__init__(
            placeholder="Filter by category...",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: SpeciesGuideView = self.view
        
        selected = self.values[0]
        view.current_category = None if selected == "all" else selected
        view.page = 0  # Reset to first page
        
        view._setup_components()
        embed = await view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class RaritySelect(Select):
    """Dropdown to filter by rarity."""
    
    def __init__(self, current: Optional[str]):
        options = [
            discord.SelectOption(
                label="All Rarities",
                value="all",
                emoji="📋",
                default=(current is None)
            )
        ]
        
        rarities = [
            ("common", "⚪", "Common"),
            ("uncommon", "🟢", "Uncommon"),
            ("rare", "🔵", "Rare"),
            ("very_rare", "🟣", "Very Rare"),
            ("legendary", "🟡", "Legendary"),
            ("mythical", "🌈", "Mythical")
        ]
        
        for rarity_id, emoji, name in rarities:
            options.append(discord.SelectOption(
                label=name,
                value=rarity_id,
                emoji=emoji,
                default=(current == rarity_id)
            ))
        
        super().__init__(
            placeholder="Filter by rarity...",
            options=options,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: SpeciesGuideView = self.view
        
        selected = self.values[0]
        view.current_rarity = None if selected == "all" else selected
        view.page = 0  # Reset to first page
        
        view._setup_components()
        embed = await view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PrevPageButton(Button):
    """Previous page button."""
    
    def __init__(self):
        super().__init__(
            label="◀",
            style=discord.ButtonStyle.secondary,
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: SpeciesGuideView = self.view
        max_pages = view._get_max_pages()
        
        # Wrap around
        if view.page <= 0:
            view.page = max_pages
        else:
            view.page -= 1
        
        view._setup_components()
        embed = await view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class PageIndicator(Button):
    """Disabled button showing current page."""
    
    def __init__(self, page: int, max_pages: int):
        super().__init__(
            label=f"{page + 1}/{max_pages + 1}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=2
        )


class NextPageButton(Button):
    """Next page button."""
    
    def __init__(self):
        super().__init__(
            label="▶",
            style=discord.ButtonStyle.secondary,
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: SpeciesGuideView = self.view
        max_pages = view._get_max_pages()
        
        # Wrap around
        if view.page >= max_pages:
            view.page = 0
        else:
            view.page += 1
        
        view._setup_components()
        embed = await view.build_embed()
        await interaction.response.edit_message(embed=embed, view=view)


class BackButton(Button):
    """Back to main menu button."""
    
    def __init__(self):
        super().__init__(
            label="Back",
            emoji="🔙",
            style=discord.ButtonStyle.danger,
            row=2
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: SpeciesGuideView = self.view
        view.stop()
        
        await interaction.response.edit_message(
            content="Use the `petcord` command to return to the main menu.",
            embed=None,
            view=None
        )
