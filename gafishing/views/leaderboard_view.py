"""
Leaderboard view - View server fishing rankings.
"""

import discord
from typing import TYPE_CHECKING, List, Tuple, Optional
import math

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView, BackToMenuMixin
from ..databases.fish import FISH_DATABASE

USERS_PER_PAGE = 20


class LeaderboardView(BackToMenuMixin, BaseView):
    """Main leaderboard view showing recent catches and category buttons."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member
    ):
        super().__init__(cog=cog, author=author)
    
    async def create_leaderboard_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the main leaderboard embed with recent catches."""
        conf = self.cog.db.get_conf(guild)
        
        embed = discord.Embed(
            title="🏆 Greenacres Fishing Leaderboards",
            description=(
                "Welcome to the Greenacres Fishing Hall of Fame!\n"
                "Track the greatest anglers and their legendary catches.\n\n"
                "Select a category below to view detailed rankings."
            ),
            color=discord.Color.gold()
        )
        
        # Get recent catches from all users (last 5 fish caught across the server)
        # We'll need to track this - for now show stats summary
        total_fish = sum(u.total_fish_ever_caught for u in conf.users.values())
        total_sold = sum(u.total_fish_sold for u in conf.users.values())
        total_anglers = len([u for u in conf.users.values() if u.first_join])
        
        embed.add_field(
            name="📊 Server Stats",
            value=(
                f"🎣 Active Anglers: **{total_anglers}**\n"
                f"🐟 Total Fish Caught: **{total_fish:,}**\n"
                f"🏪 Total Fish Sold: **{total_sold:,}**"
            ),
            inline=False
        )
        
        embed.set_footer(text="Choose a category to see the leaderboard!")
        
        return embed
    
    # Row 0: First set of leaderboards
    @discord.ui.button(label="Total Catches", style=discord.ButtonStyle.primary, emoji="🐟", row=0)
    async def total_catches(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View total fish caught leaderboard."""
        view = PaginatedLeaderboardView(
            cog=self.cog, 
            author=self.author, 
            board_type="total_catches",
            guild=interaction.guild
        )
        embed = await view.create_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Total Sold", style=discord.ButtonStyle.primary, emoji="🏪", row=0)
    async def total_sold(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View total fish sold leaderboard."""
        view = PaginatedLeaderboardView(
            cog=self.cog, 
            author=self.author, 
            board_type="total_sold",
            guild=interaction.guild
        )
        embed = await view.create_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Total Attempts", style=discord.ButtonStyle.primary, emoji="🎣", row=0)
    async def total_attempts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View total fishing attempts leaderboard."""
        view = PaginatedLeaderboardView(
            cog=self.cog, 
            author=self.author, 
            board_type="total_attempts",
            guild=interaction.guild
        )
        embed = await view.create_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)
    
    # Row 1: Second set of leaderboards
    @discord.ui.button(label="Total FishPoints", style=discord.ButtonStyle.secondary, emoji="💰", row=1)
    async def total_fishpoints(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View current FishPoints leaderboard."""
        view = PaginatedLeaderboardView(
            cog=self.cog, 
            author=self.author, 
            board_type="total_fishpoints",
            guild=interaction.guild
        )
        embed = await view.create_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="Most FishPoints Ever", style=discord.ButtonStyle.secondary, emoji="👑", row=1)
    async def most_fishpoints(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View highest FishPoints ever achieved leaderboard."""
        view = PaginatedLeaderboardView(
            cog=self.cog, 
            author=self.author, 
            board_type="most_fishpoints_ever",
            guild=interaction.guild
        )
        embed = await view.create_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="By Fish", style=discord.ButtonStyle.secondary, emoji="🐠", row=1)
    async def by_fish(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View leaderboards by specific fish species."""
        view = FishTypeSelectView(cog=self.cog, author=self.author)
        embed = view.create_embed()
        await self.stop_and_update(interaction, view, embed)


class BackToLeaderboardMixin:
    """Mixin to add a Back to Leaderboards button."""
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="🔙", row=3)
    async def back_to_leaderboard(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to the main leaderboard."""
        view = LeaderboardView(cog=self.cog, author=self.author)
        embed = await view.create_leaderboard_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)


class PaginatedLeaderboardView(BackToLeaderboardMixin, BaseView):
    """Paginated view for a specific leaderboard type."""
    
    BOARD_CONFIG = {
        "total_catches": {
            "title": "🐟 Total Fish Caught",
            "field": "total_fish_ever_caught",
            "label": "fish",
            "color": discord.Color.blue()
        },
        "total_sold": {
            "title": "🏪 Total Fish Sold", 
            "field": "total_fish_sold",
            "label": "sold",
            "color": discord.Color.green()
        },
        "total_attempts": {
            "title": "🎣 Total Fishing Attempts",
            "field": "total_fishing_attempts", 
            "label": "casts",
            "color": discord.Color.teal()
        },
        "total_fishpoints": {
            "title": "💰 Current FishPoints",
            "field": "total_fishpoints",
            "label": "FP",
            "color": discord.Color.gold()
        },
        "most_fishpoints_ever": {
            "title": "👑 Most FishPoints Ever",
            "field": "most_fishpoints_ever",
            "label": "FP",
            "color": discord.Color.purple()
        }
    }
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        board_type: str,
        guild: discord.Guild
    ):
        super().__init__(cog=cog, author=author)
        self.board_type = board_type
        self.guild = guild
        self.page = 0
        self.data: List[Tuple[int, int]] = []
        self._load_data()
    
    def _load_data(self):
        """Load and sort leaderboard data."""
        conf = self.cog.db.get_conf(self.guild)
        config = self.BOARD_CONFIG.get(self.board_type, {})
        field = config.get("field", "total_fish_ever_caught")
        
        self.data = [
            (uid, getattr(user, field, 0))
            for uid, user in conf.users.items()
            if getattr(user, field, 0) > 0
        ]
        self.data.sort(key=lambda x: x[1], reverse=True)
    
    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(len(self.data) / USERS_PER_PAGE))
    
    async def create_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the paginated leaderboard embed."""
        config = self.BOARD_CONFIG.get(self.board_type, {})
        
        embed = discord.Embed(
            title=config.get("title", "🏆 Leaderboard"),
            color=config.get("color", discord.Color.gold())
        )
        
        if not self.data:
            embed.description = "*No data yet - be the first to fish!*"
        else:
            start_idx = self.page * USERS_PER_PAGE
            end_idx = start_idx + USERS_PER_PAGE
            page_data = self.data[start_idx:end_idx]
            
            lines = []
            for i, (user_id, value) in enumerate(page_data, start=start_idx + 1):
                member = guild.get_member(user_id)
                name = member.display_name if member else f"User {user_id}"
                
                # Add medal for top 3
                if i == 1:
                    prefix = "🥇"
                elif i == 2:
                    prefix = "🥈"
                elif i == 3:
                    prefix = "🥉"
                else:
                    prefix = f"**{i}.**"
                
                label = config.get("label", "")
                lines.append(f"{prefix} {name}  -  **{value:,}** {label}")
            
            embed.description = "\n".join(lines)
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
        
        return embed
    
    async def _update_page(self, interaction: discord.Interaction):
        """Update the embed with the current page."""
        embed = await self.create_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, row=2)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page (wraps to last)."""
        self.page = (self.page - 1) % self.total_pages
        await self._update_page(interaction)
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page (wraps to first)."""
        self.page = (self.page + 1) % self.total_pages
        await self._update_page(interaction)


class FishTypeSelectView(BackToLeaderboardMixin, BaseView):
    """View for selecting water type for fish leaderboards."""
    
    def __init__(self, cog: "GreenacresFishing", author: discord.Member):
        super().__init__(cog=cog, author=author)
        self._add_water_type_select()
    
    def _add_water_type_select(self):
        """Add water type dropdown."""
        options = [
            discord.SelectOption(
                label="Freshwater",
                value="freshwater",
                emoji="🏞️",
                description="Bass, Catfish, Bluegill, and more"
            ),
            discord.SelectOption(
                label="Saltwater", 
                value="saltwater",
                emoji="🌊",
                description="Snook, Grouper, Shark, and more"
            ),
        ]
        
        select = discord.ui.Select(
            placeholder="Select water type...",
            options=options,
            row=0
        )
        select.callback = self._water_type_selected
        self.add_item(select)
    
    async def _water_type_selected(self, interaction: discord.Interaction):
        """Handle water type selection."""
        water_type = interaction.data["values"][0]
        view = FishSelectView(cog=self.cog, author=self.author, water_type=water_type)
        embed = view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🐠 Fish Records Leaderboard",
            description=(
                "View records for specific fish species!\n\n"
                "First, select a water type to filter the fish list."
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {self.author.display_name}")
        return embed


class FishSelectView(BackToLeaderboardMixin, BaseView):
    """View for selecting a specific fish species with pagination support."""
    
    FISH_PER_PAGE = 25  # Discord's select menu limit
    
    def __init__(
        self, 
        cog: "GreenacresFishing", 
        author: discord.Member, 
        water_type: str,
        page: int = 0
    ):
        super().__init__(cog=cog, author=author)
        self.water_type = water_type
        self.page = page
        
        # Build the full list of fish for this water type
        self.all_fish = []
        for fish_id, fish_data in FISH_DATABASE.items():
            if fish_data.get("water_type") == self.water_type:
                self.all_fish.append((fish_id, fish_data))
        
        # Sort alphabetically by name
        self.all_fish.sort(key=lambda x: x[1]["name"])
        
        # Calculate total pages
        self.total_pages = max(1, (len(self.all_fish) + self.FISH_PER_PAGE - 1) // self.FISH_PER_PAGE)
        
        # Ensure page is within bounds
        self.page = max(0, min(self.page, self.total_pages - 1))
        
        self._add_fish_select()
        self._add_pagination_buttons()
    
    def _add_fish_select(self):
        """Add fish species dropdown for current page."""
        start_idx = self.page * self.FISH_PER_PAGE
        end_idx = start_idx + self.FISH_PER_PAGE
        page_fish = self.all_fish[start_idx:end_idx]
        
        options = []
        for fish_id, fish_data in page_fish:
            options.append(discord.SelectOption(
                label=fish_data["name"],
                value=fish_id,
                description=f"{fish_data['rarity'].title()} | {fish_data['water_type'].title()}"
            ))
        
        if not options:
            # Fallback if somehow no fish (shouldn't happen)
            options.append(discord.SelectOption(
                label="No fish available",
                value="none",
                description="No fish found for this water type"
            ))
        
        select = discord.ui.Select(
            placeholder="Select a fish species...",
            options=options,
            row=0
        )
        select.callback = self._fish_selected
        self.add_item(select)
    
    def _add_pagination_buttons(self):
        """Add Previous/Next buttons if there are multiple pages."""
        if self.total_pages <= 1:
            return  # No pagination needed
        
        # Previous button
        prev_btn = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page == 0),
            row=1
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)
        
        # Page indicator (disabled button showing current page)
        page_btn = discord.ui.Button(
            label=f"Page {self.page + 1}/{self.total_pages}",
            style=discord.ButtonStyle.secondary,
            disabled=True,
            row=1
        )
        self.add_item(page_btn)
        
        # Next button
        next_btn = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.page >= self.total_pages - 1),
            row=1
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)
    
    async def _prev_page(self, interaction: discord.Interaction):
        """Go to previous page."""
        new_view = FishSelectView(
            cog=self.cog,
            author=self.author,
            water_type=self.water_type,
            page=self.page - 1
        )
        embed = new_view.create_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    async def _next_page(self, interaction: discord.Interaction):
        """Go to next page."""
        new_view = FishSelectView(
            cog=self.cog,
            author=self.author,
            water_type=self.water_type,
            page=self.page + 1
        )
        embed = new_view.create_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    async def _fish_selected(self, interaction: discord.Interaction):
        """Handle fish selection."""
        fish_id = interaction.data["values"][0]
        if fish_id == "none":
            await interaction.response.send_message("No fish available to select.", ephemeral=True)
            return
        
        view = SortTypeSelectView(
            cog=self.cog, 
            author=self.author, 
            fish_id=fish_id,
            water_type=self.water_type
        )
        embed = view.create_embed()
        await self.stop_and_update(interaction, view, embed)
    
    def create_embed(self) -> discord.Embed:
        water_emoji = "🏞️" if self.water_type == "freshwater" else "🌊"
        
        # Show fish count and page info
        total_fish = len(self.all_fish)
        start_idx = self.page * self.FISH_PER_PAGE + 1
        end_idx = min((self.page + 1) * self.FISH_PER_PAGE, total_fish)
        
        description = "Select a fish species to view records."
        if self.total_pages > 1:
            description += f"\n\n*Showing {start_idx}-{end_idx} of {total_fish} species*"
        
        embed = discord.Embed(
            title=f"{water_emoji} {self.water_type.title()} Fish",
            description=description,
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {self.author.display_name}")
        return embed


class SortTypeSelectView(BackToLeaderboardMixin, BaseView):
    """View for selecting sort type (weight or length)."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing", 
        author: discord.Member,
        fish_id: str,
        water_type: str
    ):
        super().__init__(cog=cog, author=author)
        self.fish_id = fish_id
        self.water_type = water_type
        self.fish_name = FISH_DATABASE.get(fish_id, {}).get("name", fish_id)
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🐠 {self.fish_name} Records",
            description="How would you like to sort the leaderboard?",
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Requested by {self.author.display_name}")
        return embed
    
    @discord.ui.button(label="By Weight", style=discord.ButtonStyle.primary, emoji="⚖️", row=0)
    async def sort_by_weight(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Sort by heaviest fish."""
        view = FishRecordLeaderboardView(
            cog=self.cog,
            author=self.author,
            fish_id=self.fish_id,
            sort_by="weight",
            guild=interaction.guild
        )
        embed = await view.create_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)
    
    @discord.ui.button(label="By Length", style=discord.ButtonStyle.primary, emoji="📏", row=0)
    async def sort_by_length(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Sort by longest fish."""
        view = FishRecordLeaderboardView(
            cog=self.cog,
            author=self.author,
            fish_id=self.fish_id,
            sort_by="length",
            guild=interaction.guild
        )
        embed = await view.create_embed(interaction.guild)
        await self.stop_and_update(interaction, view, embed)


class FishRecordLeaderboardView(BackToLeaderboardMixin, BaseView):
    """Paginated leaderboard for a specific fish species."""
    
    def __init__(
        self,
        cog: "GreenacresFishing",
        author: discord.Member,
        fish_id: str,
        sort_by: str,  # "weight" or "length"
        guild: discord.Guild
    ):
        super().__init__(cog=cog, author=author)
        self.fish_id = fish_id
        self.sort_by = sort_by
        self.guild = guild
        self.page = 0
        self.fish_name = FISH_DATABASE.get(fish_id, {}).get("name", fish_id)
        self.data: List[Tuple[int, float]] = []
        self._load_data()
    
    def _load_data(self):
        """Load and sort fish record data."""
        conf = self.cog.db.get_conf(self.guild)
        
        field = f"max_{self.sort_by}"
        
        self.data = []
        for uid, user in conf.users.items():
            record = user.fish_records.get(self.fish_id)
            if record and record.get(field, 0) > 0:
                self.data.append((uid, record[field]))
        
        self.data.sort(key=lambda x: x[1], reverse=True)
    
    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(len(self.data) / USERS_PER_PAGE))
    
    async def create_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the paginated fish record embed."""
        sort_emoji = "⚖️" if self.sort_by == "weight" else "📏"
        
        embed = discord.Embed(
            title=f"{sort_emoji} {self.fish_name} - {self.sort_by.title()} Records",
            color=discord.Color.gold()
        )
        
        if not self.data:
            embed.description = f"*No one has caught a {self.fish_name} yet!*"
        else:
            start_idx = self.page * USERS_PER_PAGE
            end_idx = start_idx + USERS_PER_PAGE
            page_data = self.data[start_idx:end_idx]
            
            lines = []
            for i, (user_id, value) in enumerate(page_data, start=start_idx + 1):
                member = guild.get_member(user_id)
                name = member.display_name if member else f"User {user_id}"
                
                # Add medal for top 3
                if i == 1:
                    prefix = "🥇"
                elif i == 2:
                    prefix = "🥈"
                elif i == 3:
                    prefix = "🥉"
                else:
                    prefix = f"**{i}.**"
                
                # Format value based on sort type
                if self.sort_by == "weight":
                    # Weight is stored in oz, convert to lbs for display
                    if value >= 16:
                        display_value = f"{value / 16:.2f} lbs"
                    else:
                        display_value = f"{value:.2f} oz"
                else:
                    # Length is in inches
                    display_value = f"{value:.2f} in"
                
                lines.append(f"{prefix} {name}  -  **{display_value}**")
            
            embed.description = "\n".join(lines)
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages}")
        
        return embed
    
    async def _update_page(self, interaction: discord.Interaction):
        """Update the embed with the current page."""
        embed = await self.create_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="◀", style=discord.ButtonStyle.primary, row=2)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page (wraps to last)."""
        self.page = (self.page - 1) % self.total_pages
        await self._update_page(interaction)
    
    @discord.ui.button(label="▶", style=discord.ButtonStyle.primary, row=2)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page (wraps to first)."""
        self.page = (self.page + 1) % self.total_pages
        await self._update_page(interaction)
