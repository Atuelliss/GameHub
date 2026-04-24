"""
Find pet view for Petcord cog.
"""

from __future__ import annotations

import time
import discord
from discord.ui import View, Button
from typing import TYPE_CHECKING, Optional, Dict, Any

from ..database.species import get_random_species, SpeciesData
from ..database.appearance import generate_appearance, get_rarity_emoji

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings


class BackConfirmView(View):
    """Confirmation view for leaving pet offer with cooldown penalty."""
    
    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        parent_view: "PetFoundView",
        original_message: Optional[discord.Message] = None,
        timeout: float = 60
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.parent_view = parent_view
        self.message = original_message
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your decision to make!",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Proceed", emoji="✅", style=discord.ButtonStyle.danger, row=0)
    async def proceed_button(self, interaction: discord.Interaction, button: Button):
        """Accept cooldown and go back to main menu."""
        # Apply the cooldown
        self.user_data.last_pet_declined = time.time()
        self.cog.schedule_save()
        
        # Stop both views
        self.stop()
        self.parent_view.stop()
        
        # Import here to avoid circular import
        from .main_menu import MainMenuView
        
        # Create new main menu view
        view = MainMenuView(
            cog=self.cog,
            user_data=self.user_data,
            guild_settings=self.guild_settings,
            author_id=self.author_id
        )
        
        embed = await view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = self.message
    
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary, row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        """Cancel and go back to the pet offer."""
        # Stop this confirmation view
        self.stop()
        
        # Restore the pet offer view
        embed = self.parent_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=self.parent_view)
    
    async def on_timeout(self) -> None:
        """Handle view timeout - go back to pet offer."""
        self.cog._active_views.discard(self)
        
        if self.message:
            try:
                # Restore pet offer view on timeout
                embed = self.parent_view.build_embed()
                await self.message.edit(embed=embed, view=self.parent_view)
            except discord.NotFound:
                pass
    
    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class PetFoundView(View):
    """View for pet adoption decision."""
    
    def __init__(
        self, 
        cog: "Petcord", 
        user_data: "User", 
        guild_settings: "GuildSettings",
        offered_pet: Dict[str, Any],
        author_id: int,
        timeout: float = 300
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.offered_pet = offered_pet  # Dict with species, coat, pattern, rarity
        self.author_id = author_id
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup on reload
        self.cog._active_views.add(self)
    
    def build_embed(self) -> discord.Embed:
        """Build the pet offer embed."""
        species: SpeciesData = self.offered_pet["species"]
        coat = self.offered_pet["coat"]
        pattern = self.offered_pet["pattern"]
        rarity = self.offered_pet["rarity"]
        
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
            value=f"**Rarity:** {rarity_display.get(rarity, rarity.title())}\n"
                  f"**Coat:** {coat.replace('_', ' ').title()}\n"
                  f"**Pattern:** {pattern.replace('_', ' ').title()}",
            inline=False
        )
        
        embed.add_field(
            name="📋 Species Info",
            value=f"• **Activity Level:** {species.activity_level.replace('_', ' ').title()}\n"
                  f"• **Care Difficulty:** {species.care_difficulty.title()}\n"
                  f"• **Social Need:** {species.social_need.replace('_', ' ').title()}\n"
                  f"• **Lifespan:** {species.lifespan.title()}\n"
                  f"• **Temperament:** {species.temperament}",
            inline=False
        )
        
        embed.add_field(
            name="✨ Special Trait",
            value=f"**{species.unique_interaction}** - {species.unique_interaction_effect}",
            inline=False
        )
        
        embed.add_field(
            name="Would you like to adopt this pet?",
            value=f"*(Passing starts a {self.guild_settings.find_cooldown_minutes} minute cooldown)*",
            inline=False
        )
        
        embed.set_footer(text="This offer expires in 5 minutes")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your pet to adopt! Use the `petcord` command to find your own.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Adopt", emoji="✅", style=discord.ButtonStyle.success, row=0)
    async def adopt_button(self, interaction: discord.Interaction, button: Button):
        """User wants to adopt this pet."""
        from .modals import PetNamingModal
        
        # Don't stop the view here - user might cancel the modal
        # The view will be stopped when the modal completes successfully
        
        modal = PetNamingModal(
            cog=self.cog,
            user_data=self.user_data,
            pet_data=self.offered_pet,
            guild_settings=self.guild_settings,
            original_message=self.message,
            parent_view=self  # Pass reference so modal can stop view on success
        )
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Pass", emoji="❌", style=discord.ButtonStyle.danger, row=0)
    async def pass_button(self, interaction: discord.Interaction, button: Button):
        """User declines this pet."""
        # Set cooldown
        self.user_data.last_pet_declined = time.time()
        self.cog.schedule_save()
        
        # Disable only Adopt and Pass buttons, keep Back enabled
        self.adopt_button.disabled = True
        self.pass_button.disabled = True
        
        species: SpeciesData = self.offered_pet["species"]
        
        embed = discord.Embed(
            title="🐾 Maybe Next Time",
            description=f"You passed on the {species.emoji} {species.name}.\n\n"
                       f"⏳ You can search for another pet in **{self.guild_settings.find_cooldown_minutes} minutes**.",
            color=discord.Color.greyple()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Back", emoji="◀️", style=discord.ButtonStyle.secondary, row=0)
    async def back_button(self, interaction: discord.Interaction, button: Button):
        """Go back to main menu - with cooldown confirmation."""
        # Show confirmation view warning about cooldown
        confirm_view = BackConfirmView(
            cog=self.cog,
            user_data=self.user_data,
            guild_settings=self.guild_settings,
            author_id=self.author_id,
            parent_view=self,
            original_message=self.message
        )
        
        embed = discord.Embed(
            title="⚠️ Leave Without Adopting?",
            description=(
                f"If you go back now, you'll receive a **{self.guild_settings.find_cooldown_minutes} minute** "
                f"cooldown before you can search for another pet.\n\n"
                f"This is to prevent repeatedly searching until you find a specific pet.\n\n"
                f"**Proceed** - Accept cooldown and return to menu\n"
                f"**Cancel** - Stay here and adopt this pet"
            ),
            color=discord.Color.orange()
        )
        
        await interaction.response.edit_message(embed=embed, view=confirm_view)
        confirm_view.message = self.message
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        # Unregister from cog
        self.cog._active_views.discard(self)
        
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                species: SpeciesData = self.offered_pet["species"]
                embed = discord.Embed(
                    title="⏰ Offer Expired",
                    description=f"The {species.emoji} {species.name} found another home.\n"
                               f"Use the `petcord` command to search for another pet!",
                    color=discord.Color.greyple()
                )
                await self.message.edit(embed=embed, view=self)
            except discord.NotFound:
                pass
    
    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


async def generate_offered_pet() -> Dict[str, Any]:
    """Generate a random pet to offer."""
    species = get_random_species()
    coat, pattern, rarity = generate_appearance(species)
    
    return {
        "species": species,
        "coat": coat,
        "pattern": pattern,
        "rarity": rarity
    }
