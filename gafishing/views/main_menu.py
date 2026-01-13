"""
Main menu embed and view creation.
"""

import discord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from ..commands.helper_functions import (
    get_game_calendar,
    get_game_time_of_day,
    get_game_time_display,
)
from ..common.weather import get_weather_for_guild, get_weather_display, get_weather_fishing_message


async def create_main_menu_embed(
    cog: "GreenacresFishing",
    guild: discord.Guild,
    user: discord.Member,
    prefix: str = "!"
) -> discord.Embed:
    """
    Create the main menu embed with current game time, weather, and user stats.
    
    Args:
        cog: The GreenacresFishing cog instance
        guild: The Discord guild
        user: The Discord member
        prefix: The command prefix for the server
    
    Returns:
        A Discord embed for the main menu
    """
    conf = cog.db.get_conf(guild)
    user_data = conf.get_user(user)
    
    # Get game time info
    calendar = get_game_calendar(cog.db, guild)
    time_of_day = get_game_time_of_day(cog.db, guild)
    time_display = get_game_time_display(cog.db, guild)
    
    # Get weather info
    weather = get_weather_for_guild(
        cog.db, 
        guild, 
        calendar['season'], 
        time_of_day['name'],
        calendar['total_game_days']
    )
    weather_display = get_weather_display(weather)
    fishing_conditions = get_weather_fishing_message(weather)
    
    # Create embed
    embed = discord.Embed(
        title="🎣 Greenacres Fishing",
        description=(
            f"Welcome back, **{user.display_name}**!\n\n"
            f"What would you like to do today?"
        ),
        color=discord.Color.blue()
    )
    
    # Add time and weather field
    embed.add_field(
        name="📅 Current Conditions",
        value=(
            f"**Time:** {time_display}\n"
            f"**Weather:** {weather_display}\n"
            f"{weather['description']}\n\n"
            f"{fishing_conditions}"
        ),
        inline=False
    )
    
    # Add player stats field
    embed.add_field(
        name="📊 Your Stats",
        value=(
            f"🐟 Fish Caught: **{user_data.total_fish_ever_caught}**\n"
            f"🎣 Fishing Attempts: **{user_data.total_fishing_attempts}**\n"
            f"💰 FishPoints: **{user_data.total_fishpoints:,}**\n"
            f"🎖️ FishMaster Tokens: **{user_data.current_fishmaster_tokens}**\n"
            f"🏪 Fish Sold: **{user_data.total_fish_sold}**"
        ),
        inline=True
    )
    
    # Add inventory summary field
    rod_count = len(user_data.current_rod_inventory)
    lure_count = len(user_data.current_lure_inventory)
    fish_count = len(user_data.current_fish_inventory)
    
    embed.add_field(
        name="🎒 Inventory",
        value=(
            f"🎣 Rods: **{rod_count}**\n"
            f"🪝 Lures: **{lure_count}**\n"
            f"🐟 Fish: **{fish_count}**"
        ),
        inline=True
    )
    
    # Set footer
    embed.set_footer(text=f"Select an option below to get started! Or use the `{prefix}fishinfo` command for help.")
    
    return embed
