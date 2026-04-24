"""
Achievements view for Petcord cog.
Displays earned and unearned achievements.
"""

from __future__ import annotations

import math
import discord
from discord.ui import View, Button, Select
from typing import TYPE_CHECKING, Optional, List

from ..database.achievements import (
    ACHIEVEMENTS,
    get_earned_achievement_ids,
    get_achievements_by_category,
    get_total_achievement_count,
    get_category_display_order,
    AchievementDef
)

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings

# Constants
ACHIEVEMENTS_PER_PAGE = 8


class AchievementsView(View):
    """View for displaying achievements with category filtering."""
    
    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int,
        category: str = "all",
        current_page: int = 0,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.category = category
        self.current_page = current_page
        self.message: Optional[discord.Message] = None
        
        # Get achievements for current filter
        self.achievements = self._get_filtered_achievements()
        self.total_pages = max(1, math.ceil(len(self.achievements) / ACHIEVEMENTS_PER_PAGE))
        
        # Ensure page is valid
        if self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1
        if self.current_page < 0:
            self.current_page = 0
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        self._setup_components()
    
    def _get_filtered_achievements(self) -> List[AchievementDef]:
        """Get achievements filtered by category."""
        if self.category == "all":
            # Return all in display order
            result = []
            for cat in get_category_display_order():
                for ach in ACHIEVEMENTS.values():
                    if ach.category == cat:
                        result.append(ach)
            return result
        else:
            return [a for a in ACHIEVEMENTS.values() if a.category == self.category]
    
    def _get_page_achievements(self) -> List[AchievementDef]:
        """Get achievements for the current page."""
        start = self.current_page * ACHIEVEMENTS_PER_PAGE
        end = start + ACHIEVEMENTS_PER_PAGE
        return self.achievements[start:end]
    
    def _setup_components(self) -> None:
        """Add components to the view."""
        # Row 0: Category selector
        self.add_item(CategorySelect(self.category))
        
        # Row 1: Navigation
        self.add_item(BackToStatsButton(row=1))
        
        # Row 2: Pagination (if needed)
        if len(self.achievements) > ACHIEVEMENTS_PER_PAGE:
            self.add_item(PrevPageButton(row=2))
            self.add_item(AchievementsCloseButton(row=2))
            self.add_item(NextPageButton(row=2))
        else:
            self.add_item(AchievementsCloseButton(row=2))
    
    def build_embed(self) -> discord.Embed:
        """Build the achievements embed."""
        earned_ids = get_earned_achievement_ids(self.user_data)
        total_count = get_total_achievement_count()
        earned_count = len(earned_ids)
        
        # Category display name
        category_names = {
            "all": "All Achievements",
            "adoption": "🐣 Adoption",
            "medals": "🏅 Medals",
            "home": "🏠 Home",
            "care": "💕 Care",
            "special": "⭐ Special"
        }
        category_display = category_names.get(self.category, self.category.title())
        
        embed = discord.Embed(
            title=f"🏆 {category_display}",
            description=f"**{earned_count}/{total_count}** achievements unlocked",
            color=discord.Color.gold()
        )
        
        # Progress bar
        progress_pct = (earned_count / total_count * 100) if total_count > 0 else 0
        progress_bar = self._build_progress_bar(progress_pct)
        embed.add_field(
            name="Progress",
            value=f"{progress_bar} {progress_pct:.1f}%",
            inline=False
        )
        
        # List achievements for current page
        page_achievements = self._get_page_achievements()
        
        if not page_achievements:
            embed.add_field(
                name="No Achievements",
                value="No achievements in this category.",
                inline=False
            )
        else:
            achievement_lines = []
            for ach in page_achievements:
                is_earned = ach.id in earned_ids
                
                if is_earned:
                    # Earned - show full info
                    line = f"{ach.emoji} **{ach.name}** ✅\n└ {ach.description}"
                elif ach.hidden:
                    # Hidden and not earned
                    line = f"❓ **???** 🔒\n└ *Hidden achievement*"
                else:
                    # Not earned but visible
                    line = f"⬜ **{ach.name}** 🔒\n└ {ach.requirement}"
                
                achievement_lines.append(line)
            
            embed.add_field(
                name="Achievements",
                value="\n".join(achievement_lines),
                inline=False
            )
        
        # Footer with page info
        if self.total_pages > 1:
            embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")
        
        return embed
    
    def _build_progress_bar(self, percentage: float, length: int = 10) -> str:
        """Build a visual progress bar."""
        filled = int(percentage / 100 * length)
        empty = length - filled
        return "█" * filled + "░" * empty
    
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
                "These aren't your achievements to view!",
                ephemeral=True
            )
            return False
        return True


class CategorySelect(Select):
    """Dropdown to select achievement category."""
    
    def __init__(self, current_category: str):
        options = [
            discord.SelectOption(
                label="All Achievements",
                value="all",
                emoji="🏆",
                default=(current_category == "all")
            ),
            discord.SelectOption(
                label="Adoption",
                value="adoption",
                emoji="🐣",
                default=(current_category == "adoption")
            ),
            discord.SelectOption(
                label="Medals",
                value="medals",
                emoji="🏅",
                default=(current_category == "medals")
            ),
            discord.SelectOption(
                label="Home",
                value="home",
                emoji="🏠",
                default=(current_category == "home")
            ),
            discord.SelectOption(
                label="Care",
                value="care",
                emoji="💕",
                default=(current_category == "care")
            ),
            discord.SelectOption(
                label="Special",
                value="special",
                emoji="⭐",
                default=(current_category == "special")
            ),
        ]
        
        super().__init__(
            placeholder="Filter by category...",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: AchievementsView = self.view
        new_category = self.values[0]
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create new view with selected category
        new_view = AchievementsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            category=new_category,
            current_page=0  # Reset to first page
        )
        
        embed = new_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
        new_view.message = view.message


class PrevPageButton(Button):
    """Button to go to previous page."""
    def __init__(self, row: int = 2):
        super().__init__(
            label="",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: AchievementsView = self.view
        
        # Wrap around
        if view.current_page == 0:
            new_page = view.total_pages - 1
        else:
            new_page = view.current_page - 1
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create new view with new page
        new_view = AchievementsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            category=view.category,
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
    """Button to go to next page."""
    def __init__(self, row: int = 2):
        super().__init__(
            label="",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: AchievementsView = self.view
        
        # Wrap around
        if view.current_page >= view.total_pages - 1:
            new_page = 0
        else:
            new_page = view.current_page + 1
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create new view with new page
        new_view = AchievementsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            category=view.category,
            current_page=new_page
        )
        
        embed = new_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
        new_view.message = view.message


class BackToStatsButton(Button):
    """Button to go back to stats view."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Back to Stats",
            emoji="🔙",
            style=discord.ButtonStyle.secondary,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .stat_views import StatsView
        
        view: AchievementsView = self.view
        
        # Stop current view
        view.stop()
        view.cog._active_views.discard(view)
        
        # Create stats view
        stats_view = StatsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id
        )
        
        embed = stats_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=stats_view)
        stats_view.message = view.message


class AchievementsCloseButton(Button):
    """Button to close the achievements view."""
    def __init__(self, row: int = 2):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=row
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: AchievementsView = self.view
        
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
