"""
Modal dialogs for Petcord cog.
"""

from __future__ import annotations

import time
import discord
from discord.ui import Modal, TextInput
from typing import TYPE_CHECKING

from ..common.models import Pet

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings
    from ..database.species import SpeciesData


class PetNamingModal(Modal):
    """Modal for naming a new pet."""
    
    def __init__(
        self, 
        cog: "Petcord", 
        user_data: "User", 
        pet_data: dict,
        guild_settings: "GuildSettings",
        original_message: discord.Message,
        parent_view=None
    ):
        super().__init__(title="🐾 Name Your New Pet!")
        self.cog = cog
        self.user_data = user_data
        self.pet_data = pet_data
        self.guild_settings = guild_settings
        self.original_message = original_message
        self.parent_view = parent_view  # Reference to PetFoundView to stop on success
        
        self.name_input = TextInput(
            label="Pet Name",
            placeholder="Enter a name for your pet...",
            min_length=2,
            max_length=32,
            required=True
        )
        self.add_item(self.name_input)
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Handle name submission."""
        name = self.name_input.value.strip()
        
        # Validate name (blacklist check)
        disallowed = [w.lower() for w in self.guild_settings.disallowed_names]
        if name.lower() in disallowed:
            await interaction.response.send_message(
                "❌ That name is not allowed. Please try again with a different name.",
                ephemeral=True
            )
            return
        
        # Additional name validation
        if not name.replace(" ", "").replace("-", "").replace("'", "").isalnum():
            await interaction.response.send_message(
                "❌ Pet names can only contain letters, numbers, spaces, hyphens, and apostrophes.",
                ephemeral=True
            )
            return
        
        # Create pet object
        species: "SpeciesData" = self.pet_data["species"]
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
        self.cog.schedule_save()
        
        # Stop the parent view now that adoption is successful
        if self.parent_view:
            self.parent_view.stop()
        
        # Send success message
        embed = discord.Embed(
            title="🎉 Welcome to the Family!",
            description=f"**{name}** the {species.emoji} {species.name} is now your pet!",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="📊 Starting Stats",
            value="🍖 Hunger: 100%\n"
                  "😊 Happiness: 100%\n"
                  "✨ Cleanliness: 100%\n"
                  "⚡ Energy: 100%",
            inline=True
        )
        
        embed.add_field(
            name="📋 Pet Info",
            value=f"**Coat:** {self.pet_data['coat'].replace('_', ' ').title()}\n"
                  f"**Pattern:** {self.pet_data['pattern'].replace('_', ' ').title()}\n"
                  f"**Rarity:** {self.pet_data['rarity'].replace('_', ' ').title()}\n"
                  f"**Stage:** Baby 🍼",
            inline=True
        )
        
        embed.add_field(
            name="💡 What's Next?",
            value="Use the `petcord` command to view your pet's status and care for them!\n"
                  "Keep their stats high to earn medals when they grow up!",
            inline=False
        )
        
        embed.set_footer(text=f"Pet #{self.user_data.total_pets_owned} adopted")
        
        # Create a view with back button to main menu
        from .main_menu import MainMenuView
        
        view = AdoptionSuccessView(
            cog=self.cog,
            user_data=self.user_data,
            guild_settings=self.guild_settings,
            author_id=interaction.user.id
        )
        
        # Edit the original message to show success with back button
        # Check for new achievements
        from ..database.achievements import check_and_award_achievements, build_achievement_unlock_embed
        new_achievements = await check_and_award_achievements(self.user_data)
        achievement_embed = build_achievement_unlock_embed(new_achievements)
        
        try:
            await self.original_message.edit(embed=embed, view=view)
            view.message = self.original_message
            
            # Send adoption success + any achievements
            if achievement_embed:
                await interaction.response.send_message(
                    f"🎊 Congratulations! You adopted **{name}**!",
                    embeds=[achievement_embed],
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"🎊 Congratulations! You adopted **{name}**!",
                    ephemeral=True
                )
        except discord.NotFound:
            # Original message was deleted, send new one
            await interaction.response.send_message(embed=embed, view=view)
    
    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors."""
        await interaction.response.send_message(
            "❌ Something went wrong. Please try again.",
            ephemeral=True
        )
        raise error


class AdoptionSuccessView(discord.ui.View):
    """View with back button after successful pet adoption."""
    
    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.message: discord.Message = None
        
        # Register with cog for cleanup on reload
        self.cog._active_views.add(self)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your pet! Use the `petcord` command to see your own.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="View Pet", emoji="🐾", style=discord.ButtonStyle.primary, row=0)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to main menu with new pet."""
        from .main_menu import MainMenuView
        
        # Stop this view
        self.stop()
        
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
    
    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
    
    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()
