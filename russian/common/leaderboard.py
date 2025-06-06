import math
import discord
from discord.ui import View, button
from redbot.core import commands
import logging
from typing import Optional, Dict, List, Tuple, Any
from .commands import channel_check  # Import the channel check

log = logging.getLogger("red.rroulette")

class LeaderboardView(View):
    def __init__(self, ctx, cog, timeout=180):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.cog = cog
        self.message: Optional[discord.Message] = None
        self.current_stat = "overview"

    async def interaction_check(self, interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This menu is not for you.", ephemeral=True)
            return False
        return True
        
    async def show_leaderboard(self, stat_type="overview", interaction=None):
        """Show the requested leaderboard type"""
        if stat_type == "overview":
            embed = await self.create_overview_embed()
        else:
            embed = await self.create_stat_embed(stat_type)
    
        self.current_page = stat_type
    
        if interaction:
            await interaction.response.defer()
            if not interaction.message:
                self.message = await interaction.followup.send(embed=embed, view=self)
            else:
                await interaction.edit_original_response(embed=embed, view=self)
                self.message = interaction.message
        else:
            self.message = await self.ctx.send(embed=embed, view=self)
    
        return self.message

    async def create_overview_embed(self):
        """Create the overview leaderboard embed showing top user for each category"""
        leaderboard = self.cog.db.get_leaderboard(self.ctx.guild.id)
        
        # Initialize embed
        embed = discord.Embed(
            title="🎯 Russian Roulette Leaderboard",
            description="See who's the bravest (or luckiest) in your server!",
            color=discord.Color.red()
        )
        
        # Get user data for all categories
        if leaderboard:
            # For each category, find the single top user
            categories = {
                "Most Wins": {"stat": "wins", "emoji": "🏆"},
                "Most Deaths": {"stat": "deaths", "emoji": "💀"},
                "Most Chickens": {"stat": "chickens", "emoji": "🐔"},
                "Most Challenges": {"stat": "challenges", "emoji": "⚔️"},
                "Most Rejections": {"stat": "rejections", "emoji": "❌"},
                "Most Games": {"stat": "games_played", "emoji": "🎮"},
                "Most Credits Won": {"stat": "total_won", "emoji": "💰"},
                "Most Credits Lost": {"stat": "total_lost", "emoji": "💸"}
            }
            
            for category, data in categories.items():
                stat = data["stat"]
                emoji = data["emoji"]
                
                # Find the user with the highest value for this stat
                top_user_id = max(leaderboard, key=lambda x: leaderboard[x].get(stat, 0), default=None)
                
                if top_user_id and leaderboard[top_user_id].get(stat, 0) > 0:
                    # Get user object and format their entry
                    try:
                        user = self.ctx.guild.get_member(int(top_user_id))
                        username = user.display_name if user else "Unknown User"
                        value = f"{emoji} **{username}**: {leaderboard[top_user_id].get(stat, 0)}"
                        embed.add_field(name=category, value=value, inline=True)
                    except Exception as e:
                        embed.add_field(name=category, value=f"Error: {e}", inline=True)
                else:
                    embed.add_field(name=category, value=f"{emoji} No data available", inline=True)
        else:
            embed.description = "No games have been played yet!"
        
        # Add instructions for button usage
        embed.set_footer(text="Click the buttons below to view detailed stats")
        return embed
        
    async def create_stat_embed(self, stat_type):
        """Create an embed for a specific stat leaderboard"""
        guild = self.ctx.guild
        leaderboard_data = self.cog.db.get_leaderboard(guild.id)
        
        # Define stat display names
        stat_displays = {
            "wins": "Most Wins",
            "deaths": "Most Deaths",
            "chickens": "Biggest Chickens",
            "total_won": "Most Credits Won",
            "total_lost": "Most Credits Lost",
            "games_played": "Most Games Played",
            "challenges": "Most Challenges Sent",
            "rejections": "Most Challenges Rejected"
        }
        
        title = stat_displays.get(stat_type, "Leaderboard")
        embed = discord.Embed(title=title, color=discord.Color.gold())
        
        # Check for empty leaderboard
        if not leaderboard_data:
            embed.description = "No one has played Russian Roulette yet! Be the first!"
            return embed
            
        # Filter and sort users by the selected stat
        users_with_stat = [(uid, data) for uid, data in leaderboard_data.items() 
                          if data.get(stat_type, 0) > 0]
        
        # If no users have this stat, show empty message
        if not users_with_stat:
            embed.description = f"No players have any {stat_type.replace('_', ' ')} yet!"
            return embed
            
        # Sort users by the stat
        sorted_users = sorted(users_with_stat, 
                             key=lambda x: x[1].get(stat_type, 0), 
                             reverse=True)[:10]  # Show top 10
        
        # Build leaderboard text
        leaderboard_text = ""
        for i, (uid, data) in enumerate(sorted_users):
            member = guild.get_member(uid)
            if member:
                # Format value based on stat type
                if "total_" in stat_type:
                    value = f"{data.get(stat_type, 0):,} credits"
                else:
                    value = str(data.get(stat_type, 0))
                leaderboard_text += f"{i+1}. {member.display_name}: {value}\n"
        
        # If we found no valid members, show empty message
        if not leaderboard_text:
            leaderboard_text = "No valid players found!"
            
        embed.description = leaderboard_text
        embed.set_footer(text="Click 'Overview' to return to the main menu")
        return embed

    @button(label="Overview", style=discord.ButtonStyle.primary, row=0)
    async def overview_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("overview", interaction)

    @button(label="Wins", style=discord.ButtonStyle.success, row=0)
    async def wins_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("wins", interaction)
        
    @button(label="Losses", style=discord.ButtonStyle.danger, row=0)
    async def losses_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("deaths", interaction)
        
    @button(label="Chickens", style=discord.ButtonStyle.secondary, row=0)
    async def chickens_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("chickens", interaction)
        
    @button(label="Games Played", style=discord.ButtonStyle.primary, row=1)
    async def games_played_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("games_played", interaction)

    @button(label="Total $ Won", style=discord.ButtonStyle.success, row=1)
    async def money_won_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("total_won", interaction)
        
    @button(label="Total $ Lost", style=discord.ButtonStyle.danger, row=1)
    async def money_lost_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("total_lost", interaction)
        
    @button(label="Challenges Sent", style=discord.ButtonStyle.secondary, row=2)
    async def challenges_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("challenges", interaction)

    @button(label="Challenges Rejected", style=discord.ButtonStyle.secondary, row=2)
    async def rejections_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_leaderboard("rejections", interaction)

    async def on_timeout(self):
        """Handle what happens when the view times out after 3 minutes"""
        try:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Update the embed to indicate timeout
            if self.current_page == "overview":
                embed = await self.create_overview_embed()
            else:
                embed = await self.create_stat_embed(self.current_page)
            
            embed.set_footer(text=f"Leaderboard buttons timed out after 3 minutes. Use {self.ctx.prefix}rrlb for a fresh leaderboard.")
            
            # Update the message with disabled buttons
            if self.message:
                await self.message.edit(embed=embed, view=self)
        except Exception as e:
            log.error(f"Error handling leaderboard timeout: {e}")

class Leaderboard:
    """Mixin for Russian Roulette cog that handles leaderboard functionality"""
    
    @commands.command(name="russianlb", aliases=["rrlb"])
    @channel_check()  # Apply the channel check here
    async def russianlb_command(self, ctx):
        """Show the interactive Russian Roulette leaderboard"""
        view = LeaderboardView(ctx, self)
        await view.show_leaderboard("overview")