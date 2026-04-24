"""
Statistics view for Petcord cog.
Displays user stats, achievements, and navigation to Home/Memorial.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings


class StatsView(View):
    """Main statistics view."""
    
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
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup on reload
        self.cog._active_views.add(self)
        
        self._setup_buttons()
    
    def _setup_buttons(self) -> None:
        """Add navigation buttons."""
        # Row 0: Main navigation
        self.add_item(ViewHomeButton())
        self.add_item(ViewMemorialButton())
        self.add_item(ViewAchievementsButton())
        
        # Row 1: How-To and Notifications
        self.add_item(HowToButton(row=1))
        self.add_item(NotificationsButton(self.user_data, row=1))
        
        # Row 2: Navigation
        self.add_item(BackToMenuButton(row=2))
        self.add_item(StatsCloseButton(row=2))
    
    def build_embed(self) -> discord.Embed:
        """Build the full stats embed."""
        user = self.user_data
        
        embed = discord.Embed(
            title="📊 Petcord Statistics",
            color=discord.Color.blue()
        )
        
        # Medals section
        medal_streak_display = "🥇" * min(user.current_medal_streak, 10) if user.current_medal_streak else "None"
        if user.current_medal_streak > 10:
            medal_streak_display += f" (+{user.current_medal_streak - 10})"
        
        embed.add_field(
            name="🏅 Medals Earned",
            value=f"🥇 Gold: **{user.gold_medals}** • 🥈 Silver: **{user.silver_medals}** • 🥉 Bronze: **{user.bronze_medals}**\n"
                  f"Total: **{user.total_medals}** medals\n"
                  f"Current Streak: {medal_streak_display}\n"
                  f"Best Streak: **{user.best_medal_streak}** Gold",
            inline=True
        )
        
        # Petcoin section
        lifetime_petcoin = user.most_petcoin_earned + user.petcoin_earned_from_medals
        embed.add_field(
            name="💰 Petcoins",
            value=f"Balance: **{user.current_petcoin:,}**\n"
                  f"Lifetime Earned: **{lifetime_petcoin:,}**",
            inline=True
        )
        
        # Legendarycoin section
        next_legendary = 5 - (user.total_pets_graduated % 5)
        if next_legendary == 5 and user.total_pets_graduated > 0 and user.total_pets_graduated % 5 == 0:
            next_legendary = 5  # Just earned one, next is in 5 more
        embed.add_field(
            name="✨ Legendarycoins",
            value=f"Balance: **{user.legendarycoin:,}**\n"
                  f"Lifetime Earned: **{user.most_legendarycoin_earned:,}**\n"
                  f"Next in: **{next_legendary}** graduations",
            inline=True
        )
        
        # Lifetime stats section
        embed.add_field(
            name="📈 Pet History",
            value=f"🐾 Pets Raised: **{user.total_pets_owned}**\n"
                  f"🎓 Graduated: **{user.total_pets_graduated}**\n"
                  f"🏠 In Home: **{len(user.home_pets)}**/{user.effective_home_capacity}\n"
                  f"🕊️ Passed Peacefully: **{user.pets_passed_naturally}**\n"
                  f"💔 Lost to Neglect: **{user.pets_lost_to_neglect}**\n"
                  f"📦 Released: **{user.total_pets_released}**\n"
                  f"🚪 Abandoned: **{user.pets_abandoned}**",
            inline=True
        )
        
        # Care performance section
        total_needs = user.total_needs_met + user.total_needs_failed
        success_rate = (user.total_needs_met / total_needs * 100) if total_needs > 0 else 0
        
        # Calculate per-stat rates
        def stat_rate(met, failed):
            total = met + failed
            return f"{(met / total * 100):.0f}%" if total > 0 else "--"
        
        embed.add_field(
            name="💕 Care Performance",
            value=f"🍖 Hunger: {stat_rate(user.hunger_needs_met, user.hunger_needs_failed)} ({user.hunger_needs_met}/{user.hunger_needs_met + user.hunger_needs_failed})\n"
                  f"😊 Happiness: {stat_rate(user.happiness_needs_met, user.happiness_needs_failed)} ({user.happiness_needs_met}/{user.happiness_needs_met + user.happiness_needs_failed})\n"
                  f"🧹 Cleanliness: {stat_rate(user.cleanliness_needs_met, user.cleanliness_needs_failed)} ({user.cleanliness_needs_met}/{user.cleanliness_needs_met + user.cleanliness_needs_failed})\n"
                  f"😴 Energy: {stat_rate(user.energy_needs_met, user.energy_needs_failed)} ({user.energy_needs_met}/{user.energy_needs_met + user.energy_needs_failed})\n"
                  f"📊 **Overall: {success_rate:.1f}%**",
            inline=True
        )
        
        # Interaction stats section
        embed.add_field(
            name="🎮 Interactions",
            value=f"Total: **{user.total_interactions:,}**\n"
                  f"🍖 Feedings: **{user.total_feedings:,}**\n"
                  f"🎾 Play: **{user.total_play_sessions:,}**\n"
                  f"🧹 Groom: **{user.total_grooming_sessions:,}**\n"
                  f"😴 Rest: **{user.total_rest_sessions:,}**\n"
                  f"🍬 Treats: **{user.total_treats_given:,}**\n"
                  f"🤗 Petting: **{user.total_petting_sessions:,}**",
            inline=True
        )
        
        # Records section - use dynamic achievement count
        from ..database.achievements import get_total_achievement_count
        total_achievements = get_total_achievement_count()
        
        embed.add_field(
            name="🏆 Records",
            value=f"💕 Highest Bond: **{user.highest_bond_achieved}**\n"
                  f"📅 Longest Lifespan: **{user.longest_pet_lifespan}** days\n"
                  f"🎖️ Achievements: **{len(user.achievements)}**/{total_achievements}",
            inline=True
        )
        
        # Memorial count (center column)
        embed.add_field(
            name="🪦 Memorial",
            value=f"**{len(user.memorial)}** pets remembered",
            inline=True
        )
        
        # Spacer for alignment
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        
        embed.set_footer(text="Use the buttons below to navigate")
        
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
                "These aren't your stats to view!",
                ephemeral=True
            )
            return False
        return True


class ViewHomeButton(Button):
    """Button to navigate to Home view."""
    def __init__(self):
        super().__init__(
            label="View Home",
            emoji="🏠",
            style=discord.ButtonStyle.primary,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .home_views import HomeListView
        
        view: StatsView = self.view
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create home list view
        home_view = HomeListView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            guild_settings=view.guild_settings,
            author=interaction.user
        )
        
        embed = home_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=home_view)
        home_view.message = view.message


class ViewMemorialButton(Button):
    """Button to navigate to Memorial view."""
    def __init__(self):
        super().__init__(
            label="Memorial",
            emoji="🪦",
            style=discord.ButtonStyle.secondary,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .memorial import MemorialView
        
        view: StatsView = self.view
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create memorial view
        memorial_view = MemorialView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id
        )
        
        embed = memorial_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=memorial_view)
        memorial_view.message = view.message


class ViewAchievementsButton(Button):
    """Button to view achievements."""
    def __init__(self):
        super().__init__(
            label="Achievements",
            emoji="🏆",
            style=discord.ButtonStyle.secondary,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .achievements import AchievementsView
        
        view: StatsView = self.view
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create achievements view
        achievements_view = AchievementsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id
        )
        
        embed = achievements_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=achievements_view)
        achievements_view.message = view.message


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
        
        view: StatsView = self.view
        
        # Stop this view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create main menu view
        main_view = MainMenuView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id
        )
        
        embed = await main_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=main_view)
        main_view.message = view.message


class StatsCloseButton(Button):
    """Button to close the stats view."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: StatsView = self.view
        
        # Stop the view
        view.stop()
        view.cog._active_views.discard(view)
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)


class NotificationsButton(Button):
    """Button to toggle danger warning notifications."""
    def __init__(self, user_data: "User", row: int = 1):
        enabled = user_data.warning_notifications
        super().__init__(
            label="Notifications",
            emoji="🔔" if enabled else "🔕",
            style=discord.ButtonStyle.success if enabled else discord.ButtonStyle.danger,
            row=row
        )
        self.enabled = enabled
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: StatsView = self.view
        
        # Toggle the setting
        view.user_data.warning_notifications = not view.user_data.warning_notifications
        new_state = view.user_data.warning_notifications
        
        # Update button appearance
        self.enabled = new_state
        self.emoji = "🔔" if new_state else "🔕"
        self.style = discord.ButtonStyle.success if new_state else discord.ButtonStyle.danger
        
        # Schedule save
        view.cog.schedule_save()
        
        # Send confirmation
        status = "enabled" if new_state else "disabled"
        await interaction.response.edit_message(view=view)
        await interaction.followup.send(
            f"🔔 Danger warning notifications are now **{status}**!",
            ephemeral=True
        )


class HowToButton(Button):
    """Button to open the How-To help guide."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="How-To",
            emoji="❓",
            style=discord.ButtonStyle.secondary,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .howto_views import HowToView
        
        view: StatsView = self.view
        
        # Build current embed to return to
        return_embed = view.build_embed()
        return_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        # Create How-To view with return capability
        howto_view = HowToView(
            cog=view.cog,
            author_id=view.author_id,
            guild_settings=view.guild_settings,
            return_view=view,
            return_embed=return_embed
        )
        
        embed = howto_view.get_main_help_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=howto_view)
        howto_view.message = view.message
