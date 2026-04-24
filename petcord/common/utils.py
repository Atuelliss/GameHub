"""
Utility functions for Petcord cog.
"""

import time
from typing import Tuple, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from redbot.core.bot import Red
    import discord


async def get_prefix(bot: "Red", guild: "discord.Guild") -> str:
    """
    Get the bot's prefix for a specific guild.
    
    Args:
        bot: The Red bot instance
        guild: The Discord guild
        
    Returns:
        The prefix string (e.g., "!" or ".")
    """
    try:
        prefixes = await bot.get_prefix(None)  # Get default prefixes
        if isinstance(prefixes, list) and prefixes:
            # Filter out mention prefixes and get the first text prefix
            for p in prefixes:
                if not p.startswith("<@"):
                    return p
            return prefixes[0]
        return str(prefixes) if prefixes else "[p]"
    except Exception:
        return "[p]"


def format_stat_bar(value: float, max_val: float = 100, length: int = 10) -> str:
    """
    Create a visual stat bar using block characters.
    
    Args:
        value: Current stat value (can be float)
        max_val: Maximum stat value
        length: Number of characters in the bar
        
    Returns:
        String like "████████░░" representing the percentage
    """
    value = max(0, min(value, max_val))
    filled = int((value / max_val) * length)
    empty = length - filled
    return "█" * filled + "░" * empty


def format_timestamp(timestamp: float) -> str:
    """
    Format a Unix timestamp as a readable date string.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Formatted date string like "Jan 15, 2026"
    """
    if timestamp <= 0:
        return "Never"
    
    from datetime import datetime
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%b %d, %Y")


def format_timestamp_relative(timestamp: float) -> str:
    """
    Format a Unix timestamp as relative time.
    
    Args:
        timestamp: Unix timestamp
        
    Returns:
        Relative time string like "2 hours ago" or "3 days ago"
    """
    if timestamp <= 0:
        return "Never"
    
    elapsed = time.time() - timestamp
    
    if elapsed < 60:
        return "Just now"
    elif elapsed < 3600:
        minutes = int(elapsed / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif elapsed < 86400:
        hours = int(elapsed / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(elapsed / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"


def calculate_cooldown_remaining(last_action: float, cooldown_minutes: int) -> int:
    """
    Calculate remaining cooldown time in seconds.
    
    Args:
        last_action: Timestamp of last action
        cooldown_minutes: Cooldown duration in minutes
        
    Returns:
        Remaining seconds (0 if cooldown expired)
    """
    if last_action <= 0:
        return 0
    
    cooldown_seconds = cooldown_minutes * 60
    elapsed = time.time() - last_action
    remaining = cooldown_seconds - elapsed
    
    return max(0, int(remaining))


def format_cooldown(seconds: int) -> str:
    """
    Format cooldown seconds as a readable string.
    
    Args:
        seconds: Number of seconds remaining
        
    Returns:
        Formatted string like "5m 30s" or "1h 15m"
    """
    if seconds <= 0:
        return "Ready"
    
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def get_warning_icon(value: int, critical: int = 20, warning: int = 40) -> str:
    """
    Get warning icon based on stat value.
    
    Args:
        value: Current stat value
        critical: Threshold for critical (red) warning
        warning: Threshold for warning (yellow) icon
        
    Returns:
        Warning icon string or empty string
    """
    if value < critical:
        return " 🔴"
    elif value < warning:
        return " ⚠️"
    return ""


def get_rarity_display(rarity: str) -> str:
    """
    Get display string with stars for rarity.
    
    Args:
        rarity: Rarity key (common, uncommon, rare, etc.)
        
    Returns:
        Formatted rarity display like "⭐⭐⭐ Rare"
    """
    displays = {
        "common": "⭐ Common",
        "uncommon": "⭐⭐ Uncommon",
        "rare": "⭐⭐⭐ Rare",
        "very_rare": "⭐⭐⭐⭐ Very Rare",
        "legendary": "⭐⭐⭐⭐⭐ Legendary",
        "mythical": "🌟 Mythical",
    }
    return displays.get(rarity, "⭐ Common")


def get_rating_from_score(score: float) -> str:
    """
    Get rating string from daily care score.
    
    Args:
        score: Daily care score (0-100)
        
    Returns:
        Rating key (perfect, excellent, good, fair, poor, critical)
    """
    if score >= 95:
        return "perfect"
    elif score >= 80:
        return "excellent"
    elif score >= 60:
        return "good"
    elif score >= 40:
        return "fair"
    elif score >= 20:
        return "poor"
    else:
        return "critical"


def get_rating_display(rating: str) -> str:
    """
    Get emoji display for rating.
    
    Args:
        rating: Rating key
        
    Returns:
        Formatted rating display with stars
    """
    displays = {
        "perfect": "⭐⭐⭐⭐⭐ Perfect",
        "excellent": "⭐⭐⭐⭐ Excellent",
        "good": "⭐⭐⭐ Good",
        "fair": "⭐⭐ Fair",
        "poor": "⭐ Poor",
        "critical": "💀 Critical",
    }
    return displays.get(rating, "Unknown")


def get_medal_display(medal: str) -> str:
    """
    Get display string for medal.
    
    Args:
        medal: Medal key (gold, silver, bronze, or empty)
        
    Returns:
        Formatted medal display
    """
    displays = {
        "gold": "🥇 Gold",
        "silver": "🥈 Silver",
        "bronze": "🥉 Bronze",
    }
    return displays.get(medal, "No Medal")


def get_medal_emoji(medal: str) -> str:
    """
    Get just the emoji for a medal.
    
    Args:
        medal: Medal key (gold, silver, bronze, or empty)
        
    Returns:
        Medal emoji or empty string
    """
    emojis = {
        "gold": "🥇",
        "silver": "🥈",
        "bronze": "🥉",
    }
    return emojis.get(medal, "")


def clamp(value: int, min_val: int = 0, max_val: int = 100) -> int:
    """
    Clamp a value between min and max.
    
    Args:
        value: Value to clamp
        min_val: Minimum value
        max_val: Maximum value
        
    Returns:
        Clamped value
    """
    return max(min_val, min(value, max_val))


async def is_allowed_channel(
    ctx,
    allowed_channel_id: int | None
) -> bool:
    """
    Check if a command is being run in the allowed channel.
    
    If no allowed channel is set (None), all channels are allowed.
    If an allowed channel is set, only that channel is allowed.
    Admins (bot owner, Red admin, or Manage Server permission) bypass this restriction.
    
    Args:
        ctx: The command context
        allowed_channel_id: The ID of the allowed channel (or None if not set)
        
    Returns:
        True if the channel is allowed or user is admin, False otherwise
    """
    # No channel restriction set - allow all
    if allowed_channel_id is None:
        return True
    
    # Check if in allowed channel
    if ctx.channel.id == allowed_channel_id:
        return True
    
    # Admin bypass - check if user is bot owner, Red admin, or has Manage Server
    if await ctx.bot.is_owner(ctx.author):
        return True
    
    if ctx.guild and ctx.author.guild_permissions.manage_guild:
        return True
    
    if ctx.guild and await ctx.bot.is_admin(ctx.author):
        return True
    
    return False
