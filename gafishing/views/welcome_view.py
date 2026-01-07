"""
Welcome view for first-time players.
"""

import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView, MainMenuView
from .main_menu import create_main_menu_embed
from ..commands.helper_functions import setup_new_player


class WelcomeView(BaseView):
    """View shown to first-time players."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member
    ):
        super().__init__(cog=cog, author=author)
    
    @discord.ui.button(label="Start Fishing!", style=discord.ButtonStyle.success, emoji="🎣")
    async def start_fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Accept the welcome and set up the player."""
        # Set up the new player
        await setup_new_player(self.cog.db, interaction.guild, self.author)
        self.cog.save()
        
        # Transition to main menu
        new_view = MainMenuView(cog=self.cog, author=self.author)
        embed = await create_main_menu_embed(self.cog, interaction.guild, self.author)
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.secondary, emoji="❌")
    async def close_welcome(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the welcome message without joining."""
        self.stop()
        await interaction.response.edit_message(
            content="Come back anytime when you're ready to start fishing! 🎣",
            embed=None,
            view=None
        )
