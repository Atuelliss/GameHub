"""
Memorial view for Petcord cog.
Allows viewing and setting epitaphs for passed pets.
"""

from __future__ import annotations

import math
import discord
from discord.ui import View, Button, Select, Modal, TextInput
from typing import TYPE_CHECKING, Optional

from ..database.species import get_species

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, PetMemorial

# Constants
PETS_PER_PAGE = 10


class MemorialView(View):
    """View for viewing and managing pet memorial with pagination."""
    
    def __init__(
        self, 
        cog: "Petcord", 
        user_data: "User", 
        author_id: int,
        current_page: int = 0,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.current_page = current_page
        self.message: Optional[discord.Message] = None
        
        # Calculate total pages
        total_pets = len(self.user_data.memorial)
        self.total_pages = max(1, math.ceil(total_pets / PETS_PER_PAGE))
        
        # Ensure current page is valid
        if self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1
        if self.current_page < 0:
            self.current_page = 0
        
        # Register with cog for cleanup on reload
        self.cog._active_views.add(self)
        
        self._setup_components()
    
    def _get_page_pets(self) -> list:
        """Get pets for the current page."""
        start = self.current_page * PETS_PER_PAGE
        end = start + PETS_PER_PAGE
        return self.user_data.memorial[start:end]
    
    def _setup_components(self) -> None:
        """Add components based on memorial state."""
        page_pets = self._get_page_pets()
        
        # Row 0: Select dropdown (only if there are pets on this page)
        if page_pets:
            self.add_item(MemorialSelect(page_pets, self.current_page * PETS_PER_PAGE))
        
        # Row 1: Pagination (left arrow, close, right arrow)
        # Only show pagination if there are pets
        if self.user_data.memorial:
            self.add_item(PreviousPageButton(row=1))
            self.add_item(MemorialCloseButton(row=1))
            self.add_item(NextPageButton(row=1))
        else:
            # Just close button if no pets
            self.add_item(MemorialCloseButton(row=1))
        
        # Row 2: Back to Menu button
        self.add_item(BackToMenuButton(row=2))
    
    def build_embed(self) -> discord.Embed:
        """Build the memorial embed for current page."""
        embed = discord.Embed(
            title="🪦 Pet Memorial",
            description="In loving memory of our departed companions...",
            color=discord.Color.dark_grey()
        )
        
        if not self.user_data.memorial:
            embed.add_field(
                name="Empty Memorial",
                value="No pets in memorial yet.\n"
                      "Pets who pass away will be remembered here.",
                inline=False
            )
            embed.set_footer(text="May they rest in peace 🕊️")
            return embed
        
        # Summary stats
        total = len(self.user_data.memorial)
        peaceful = sum(1 for p in self.user_data.memorial if p.death_cause == "old_age")
        lost = total - peaceful
        
        embed.add_field(
            name="📋 Summary",
            value=f"🕊️ Peaceful passings: **{peaceful}**\n"
                  f"💔 Lost to neglect: **{lost}**\n"
                  f"📖 Total remembered: **{total}**",
            inline=False
        )
        
        # List pets for current page
        page_pets = self._get_page_pets()
        pet_lines = []
        start_index = self.current_page * PETS_PER_PAGE
        
        for i, pet in enumerate(page_pets):
            species = get_species(pet.species_id)
            species_emoji = species.emoji if species else "🐾"
            
            icon = "🕊️" if pet.death_cause == "old_age" else "💔"
            medal_emoji = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(pet.medal, "")
            
            if pet.death_cause == "old_age":
                death_text = f"Lived {pet.total_lifespan_days} days"
            else:
                death_text = f"Lost on day {pet.total_lifespan_days}"
            
            epitaph_indicator = "📝" if pet.epitaph else ("✏️" if pet.epitaph_allowed else "")
            
            pet_lines.append(
                f"{icon} {species_emoji} **{pet.name}** {medal_emoji}{epitaph_indicator}\n"
                f"└ {death_text}"
            )
        
        if pet_lines:
            embed.add_field(
                name="🪦 Remembered Pets",
                value="\n".join(pet_lines),
                inline=False
            )
        
        # Page indicator in footer
        embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages} • Select a pet to view details")
        
        return embed
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        self.cog._active_views.discard(self)
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original user can interact."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your memorial to browse!",
                ephemeral=True
            )
            return False
        return True


class MemorialSelect(Select):
    """Select dropdown to choose a memorial entry."""
    
    def __init__(self, page_pets: list, start_index: int):
        """
        Args:
            page_pets: List of pets on the current page
            start_index: The index of the first pet in the full memorial list
        """
        self.start_index = start_index
        options = []
        
        for i, pet in enumerate(page_pets):
            species = get_species(pet.species_id)
            species_name = species.name if species else pet.species_id.replace("_", " ").title()
            
            description = "Passed peacefully" if pet.death_cause == "old_age" else "Lost to neglect"
            if pet.epitaph:
                description = f'"{pet.epitaph[:50]}"' if len(pet.epitaph) <= 50 else f'"{pet.epitaph[:47]}..."'
            
            options.append(
                discord.SelectOption(
                    label=pet.name,
                    description=description,
                    value=str(i),  # Index within this page
                    emoji="🕊️" if pet.death_cause == "old_age" else "💔"
                )
            )
        
        super().__init__(
            placeholder="Select a pet to view details...",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MemorialView = self.view
        page_index = int(self.values[0])
        actual_index = self.start_index + page_index
        pet = view.user_data.memorial[actual_index]
        
        # Build detail embed
        species = get_species(pet.species_id)
        species_name = species.name if species else pet.species_id.replace("_", " ").title()
        species_emoji = species.emoji if species else "🐾"
        
        icon = "🕊️" if pet.death_cause == "old_age" else "💔"
        
        embed = discord.Embed(
            title=f'{icon} In Memory of "{pet.name}"',
            color=discord.Color.dark_grey() if pet.death_cause == "old_age" else discord.Color.dark_red()
        )
        
        # Pet info
        embed.add_field(
            name="Species",
            value=f"{species_emoji} {species_name}",
            inline=True
        )
        embed.add_field(
            name="Rarity",
            value=pet.rarity.replace("_", " ").title(),
            inline=True
        )
        embed.add_field(
            name="Appearance",
            value=f"{pet.coat_color.replace('_', ' ').title()} / {pet.pattern.replace('_', ' ').title()}",
            inline=True
        )
        
        # Life summary
        if pet.death_cause == "old_age":
            death_text = f"Passed peacefully after **{pet.total_lifespan_days}** wonderful days"
        else:
            death_text = f"Lost on day **{pet.total_lifespan_days}** due to neglect"
        
        embed.add_field(
            name="Life Summary",
            value=death_text,
            inline=False
        )
        
        # Achievements (for pets that made it to home)
        if pet.reached_home:
            medal_display = {"gold": "🥇 Gold", "silver": "🥈 Silver", "bronze": "🥉 Bronze"}.get(pet.medal, "No Medal")
            embed.add_field(
                name="Achievements",
                value=f"🎖️ Medal: {medal_display}\n"
                      f"💕 Final Bond: {pet.final_bond}",
                inline=False
            )
        
        # Epitaph
        if pet.epitaph:
            embed.add_field(
                name="📜 Epitaph",
                value=f'*"{pet.epitaph}"*',
                inline=False
            )
        elif pet.epitaph_allowed:
            embed.add_field(
                name="📜 Epitaph",
                value="*No epitaph set. Click the button below to add one.*",
                inline=False
            )
        else:
            embed.add_field(
                name="📜 Epitaph",
                value="*Epitaph not available for pets lost to neglect.*",
                inline=False
            )
        
        # Create a sub-view for this pet
        detail_view = MemorialDetailView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            memorial_index=actual_index,
            parent_view=view
        )
        
        await interaction.response.edit_message(embed=embed, view=detail_view)
        detail_view.message = view.message


class PreviousPageButton(Button):
    """Button to go to previous page (wraps to last page from first)."""
    def __init__(self, row: int = 2):
        super().__init__(
            label="",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MemorialView = self.view
        
        # Wrap from first page to last page
        if view.current_page == 0:
            new_page = view.total_pages - 1
        else:
            new_page = view.current_page - 1
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create new view with updated page
        new_view = MemorialView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            current_page=new_page
        )
        
        embed = new_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
        new_view.message = view.message


class NextPageButton(Button):
    """Button to go to next page (wraps to first page from last)."""
    def __init__(self, row: int = 2):
        super().__init__(
            label="",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MemorialView = self.view
        
        # Wrap from last page to first page
        if view.current_page >= view.total_pages - 1:
            new_page = 0
        else:
            new_page = view.current_page + 1
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create new view with updated page
        new_view = MemorialView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            current_page=new_page
        )
        
        embed = new_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
        new_view.message = view.message


class MemorialDetailView(View):
    """View for a single memorial entry with epitaph options."""
    
    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        memorial_index: int,
        parent_view: MemorialView,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.memorial_index = memorial_index
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        self._setup_buttons()
    
    def _setup_buttons(self) -> None:
        """Setup buttons based on pet state."""
        pet = self.user_data.memorial[self.memorial_index]
        
        # Add epitaph button if allowed and not set
        if pet.epitaph_allowed and not pet.epitaph:
            self.add_item(SetEpitaphButton())
        
        # Back to list button
        self.add_item(BackToListButton())
        
        # Close button
        self.add_item(MemorialCloseButton())
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        self.cog._active_views.discard(self)
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original user can interact."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your memorial to browse!",
                ephemeral=True
            )
            return False
        return True


class SetEpitaphButton(Button):
    """Button to set epitaph via modal."""
    def __init__(self):
        super().__init__(
            label="Set Epitaph",
            emoji="✏️",
            style=discord.ButtonStyle.primary,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MemorialDetailView = self.view
        pet = view.user_data.memorial[view.memorial_index]
        
        modal = EpitaphModal(
            cog=view.cog,
            user_data=view.user_data,
            memorial_index=view.memorial_index,
            pet_name=pet.name,
            detail_view=view
        )
        await interaction.response.send_modal(modal)


class BackToListButton(Button):
    """Button to go back to memorial list."""
    def __init__(self):
        super().__init__(
            label="Back to List",
            emoji="📋",
            style=discord.ButtonStyle.secondary,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MemorialDetailView = self.view
        
        # Stop this view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Go back to parent view
        parent = view.parent_view
        
        # Rebuild parent components (in case epitaph was set)
        parent.clear_items()
        parent._setup_components()
        
        embed = parent.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=parent)


class BackToMenuButton(Button):
    """Button to go back to main menu."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Back to Menu",
            emoji="🔙",
            style=discord.ButtonStyle.secondary,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .main_menu import MainMenuView
        
        view: MemorialView = self.view
        
        # Stop this view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Get guild settings for main menu
        guild_settings = view.cog.db.get_conf(interaction.guild)
        
        # Create main menu view
        main_view = MainMenuView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=guild_settings,
            author_id=view.author_id
        )
        
        embed = await main_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=main_view)
        main_view.message = view.message


class MemorialCloseButton(Button):
    """Button to close the memorial view."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: View = self.view
        
        # Stop the view
        view.stop()
        if hasattr(view, 'cog'):
            view.cog._active_views.discard(view)
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)


class EpitaphModal(Modal):
    """Modal for setting a pet's epitaph."""
    
    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        memorial_index: int,
        pet_name: str,
        detail_view: MemorialDetailView
    ):
        super().__init__(title=f"Epitaph for {pet_name}")
        self.cog = cog
        self.user_data = user_data
        self.memorial_index = memorial_index
        self.detail_view = detail_view
        
        self.epitaph_input = TextInput(
            label="Write a memorial message",
            placeholder="A beloved companion who brought joy to every day...",
            style=discord.TextStyle.paragraph,
            max_length=100,
            required=True
        )
        self.add_item(self.epitaph_input)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        # Save the epitaph
        self.user_data.memorial[self.memorial_index].epitaph = self.epitaph_input.value
        
        # Save to database
        await self.cog.save()
        
        # Rebuild the detail view (remove epitaph button since it's now set)
        pet = self.user_data.memorial[self.memorial_index]
        species = get_species(pet.species_id)
        species_name = species.name if species else pet.species_id.replace("_", " ").title()
        species_emoji = species.emoji if species else "🐾"
        
        icon = "🕊️" if pet.death_cause == "old_age" else "💔"
        
        embed = discord.Embed(
            title=f'{icon} In Memory of "{pet.name}"',
            color=discord.Color.dark_grey()
        )
        
        embed.add_field(
            name="Species",
            value=f"{species_emoji} {species_name}",
            inline=True
        )
        embed.add_field(
            name="Rarity",
            value=pet.rarity.replace("_", " ").title(),
            inline=True
        )
        embed.add_field(
            name="Appearance",
            value=f"{pet.coat_color.replace('_', ' ').title()} / {pet.pattern.replace('_', ' ').title()}",
            inline=True
        )
        
        death_text = f"Passed peacefully after **{pet.total_lifespan_days}** wonderful days"
        embed.add_field(
            name="Life Summary",
            value=death_text,
            inline=False
        )
        
        if pet.reached_home:
            medal_display = {"gold": "🥇 Gold", "silver": "🥈 Silver", "bronze": "🥉 Bronze"}.get(pet.medal, "No Medal")
            embed.add_field(
                name="Achievements",
                value=f"🎖️ Medal: {medal_display}\n"
                      f"💕 Final Bond: {pet.final_bond}",
                inline=False
            )
        
        embed.add_field(
            name="📜 Epitaph",
            value=f'*"{pet.epitaph}"*',
            inline=False
        )
        
        # Create new detail view without epitaph button
        new_view = MemorialDetailView(
            cog=self.cog,
            user_data=self.user_data,
            author_id=self.detail_view.author_id,
            memorial_index=self.memorial_index,
            parent_view=self.detail_view.parent_view
        )
        
        # Stop old view
        self.detail_view.stop()
        self.cog._active_views.discard(self.detail_view)
        
        await interaction.response.edit_message(embed=embed, view=new_view)
        new_view.message = self.detail_view.message
