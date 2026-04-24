"""
Leaderboard view for server-wide rankings.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button, Select
from typing import TYPE_CHECKING, Optional, List, Dict, Tuple

if TYPE_CHECKING:
    from ..abc import CompositeMetaClass
    from ..common.models import User


USERS_PER_PAGE = 10


class LeaderboardView(View):
    """View for displaying server leaderboards."""
    
    def __init__(
        self, 
        cog: "CompositeMetaClass",
        guild_id: int,
        author_id: int,
        *,
        timeout: float = 300.0
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_id = guild_id
        self.author_id = author_id
        self.message: Optional[discord.Message] = None
        
        # Current view state
        self.current_category = "gold_medals"  # Default category
        self.page = 0
        
        self._setup_components()
    
    def _setup_components(self) -> None:
        """Set up view components."""
        self.clear_items()
        
        # Row 0: Category select
        self.add_item(LeaderboardCategorySelect(self.current_category))
        
        # Row 1: Navigation
        self.add_item(PrevPageButton())
        self.add_item(PageIndicator(self.page, self._get_max_pages()))
        self.add_item(NextPageButton())
        self.add_item(BackButton())
    
    def _get_leaderboard_data(self) -> List[Tuple[int, "User", any]]:
        """Get sorted leaderboard data for current category."""
        # Get all users from the database for this guild
        guild_data = self.cog.db.get_conf(self.guild_id)
        if not guild_data or not guild_data.users:
            return []
        
        # Build list of (user_id, user_data, value)
        entries = []
        
        for user_id, user_data in guild_data.users.items():
            # Only include users with some activity
            if user_data.total_pets_owned == 0:
                continue
            
            # Get the relevant stat
            if self.current_category == "gold_medals":
                value = user_data.gold_medals
            elif self.current_category == "total_medals":
                value = user_data.total_medals
            elif self.current_category == "medal_streak":
                value = user_data.best_medal_streak
            elif self.current_category == "pets_graduated":
                value = user_data.total_pets_graduated
            elif self.current_category == "highest_bond":
                value = user_data.highest_bond_achieved
            elif self.current_category == "achievements":
                value = len(user_data.achievements)
            elif self.current_category == "longest_lifespan":
                value = user_data.longest_pet_lifespan
            else:
                value = user_data.gold_medals
            
            if value > 0:
                entries.append((int(user_id), user_data, value))
        
        # Sort by value descending
        entries.sort(key=lambda x: x[2], reverse=True)
        
        return entries
    
    def _get_max_pages(self) -> int:
        """Get maximum page number."""
        data = self._get_leaderboard_data()
        return max(0, (len(data) - 1) // USERS_PER_PAGE)
    
    async def build_embed(self) -> discord.Embed:
        """Build the leaderboard embed."""
        data = self._get_leaderboard_data()
        max_pages = self._get_max_pages()
        
        # Clamp page
        self.page = max(0, min(self.page, max_pages))
        
        # Category display info
        category_info = {
            "gold_medals": ("🥇 Gold Medals", "gold_medals"),
            "total_medals": ("🏅 Total Medals", "total_medals"),
            "medal_streak": ("🔥 Best Streak", "best_medal_streak"),
            "pets_graduated": ("🎓 Pets Graduated", "total_pets_graduated"),
            "highest_bond": ("💕 Highest Bond", "highest_bond_achieved"),
            "achievements": ("🏆 Achievements", "achievements"),
            "longest_lifespan": ("📅 Longest Lifespan", "longest_pet_lifespan")
        }
        
        title, _ = category_info.get(self.current_category, ("🥇 Gold Medals", "gold_medals"))
        
        embed = discord.Embed(
            title=f"🏆 Leaderboard - {title}",
            color=discord.Color.gold()
        )
        
        if not data:
            embed.description = "No players have participated yet!\nBe the first to raise a pet to the top!"
        else:
            # Get current page
            start_idx = self.page * USERS_PER_PAGE
            end_idx = start_idx + USERS_PER_PAGE
            page_data = data[start_idx:end_idx]
            
            lines = []
            for i, (user_id, user_data, value) in enumerate(page_data):
                rank = start_idx + i + 1
                
                # Get rank display
                if rank == 1:
                    rank_display = "🥇"
                elif rank == 2:
                    rank_display = "🥈"
                elif rank == 3:
                    rank_display = "🥉"
                else:
                    rank_display = f"**#{rank}**"
                
                # Format value based on category
                if self.current_category == "longest_lifespan":
                    value_display = f"{value} days"
                elif self.current_category == "highest_bond":
                    value_display = f"{value}%"
                else:
                    value_display = str(value)
                
                lines.append(f"{rank_display} <@{user_id}> — **{value_display}**")
            
            embed.description = "\n".join(lines)
            
            # Add user's rank if they're not on current page
            user_rank = None
            for i, (user_id, _, _) in enumerate(data):
                if user_id == self.author_id:
                    user_rank = i + 1
                    break
            
            if user_rank and (user_rank <= start_idx or user_rank > end_idx):
                user_value = data[user_rank - 1][2]
                if self.current_category == "longest_lifespan":
                    value_display = f"{user_value} days"
                elif self.current_category == "highest_bond":
                    value_display = f"{user_value}%"
                else:
                    value_display = str(user_value)
                embed.add_field(
                    name="Your Rank",
                    value=f"**#{user_rank}** — {value_display}",
                    inline=False
                )
        
        embed.set_footer(text=f"Page {self.page + 1}/{max_pages + 1} • {len(data)} players ranked")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to interact."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your leaderboard! Use your own menu.",
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


class LeaderboardCategorySelect(Select):
    """Dropdown to select leaderboard category."""
    
    def __init__(self, current: str):
        options = [
            discord.SelectOption(
                label="Gold Medals",
                value="gold_medals",
                emoji="🥇",
                description="Most gold medals earned",
                default=(current == "gold_medals")
            ),
            discord.SelectOption(
                label="Total Medals",
                value="total_medals",
                emoji="🏅",
                description="All medals combined",
                default=(current == "total_medals")
            ),
            discord.SelectOption(
                label="Best Streak",
                value="medal_streak",
                emoji="🔥",
                description="Longest gold medal streak",
                default=(current == "medal_streak")
            ),
            discord.SelectOption(
                label="Pets Graduated",
                value="pets_graduated",
                emoji="🎓",
                description="Most pets raised to graduation",
                default=(current == "pets_graduated")
            ),
            discord.SelectOption(
                label="Highest Bond",
                value="highest_bond",
                emoji="💕",
                description="Highest bond achieved with a pet",
                default=(current == "highest_bond")
            ),
            discord.SelectOption(
                label="Achievements",
                value="achievements",
                emoji="🏆",
                description="Most achievements unlocked",
                default=(current == "achievements")
            ),
            discord.SelectOption(
                label="Longest Lifespan",
                value="longest_lifespan",
                emoji="📅",
                description="Longest a pet has lived",
                default=(current == "longest_lifespan")
            )
        ]
        
        super().__init__(
            placeholder="Select category...",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: LeaderboardView = self.view
        
        view.current_category = self.values[0]
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
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: LeaderboardView = self.view
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
            row=1
        )


class NextPageButton(Button):
    """Next page button."""
    
    def __init__(self):
        super().__init__(
            label="▶",
            style=discord.ButtonStyle.secondary,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: LeaderboardView = self.view
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
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: LeaderboardView = self.view
        view.stop()
        
        await interaction.response.edit_message(
            content="Use the `petcord` command to return to the main menu.",
            embed=None,
            view=None
        )
