"""
Daily Freebie system for Petcord clothing shop.
Handles daily free item distribution based on server timezone.
"""

from __future__ import annotations

import random
import time
from datetime import datetime
from typing import TYPE_CHECKING, Optional, Tuple
from zoneinfo import ZoneInfo

from .petshop import SHOP_DATABASE
from ..common.models import InventoryItem

if TYPE_CHECKING:
    from ..common.models import User, GuildSettings


# =============================================================================
# FREEBIE ITEM POOL
# =============================================================================

def get_freebie_eligible_items() -> list[dict]:
    """
    Get all items eligible for daily freebie.
    Returns uncommon and rare rarity items only.
    Excludes holiday items.
    """
    eligible_items = []
    for item_id, item_data in SHOP_DATABASE.items():
        rarity = item_data.get("rarity", "common")
        # Only uncommon and rare, exclude holiday items
        if rarity in ("uncommon", "rare") and "holiday" not in item_data:
            eligible_items.append({
                "item_id": item_id,
                **item_data
            })
    return eligible_items


def select_random_freebie() -> Optional[dict]:
    """
    Select a random item from the freebie pool.
    Returns the item dict with item_id included, or None if no items available.
    """
    eligible_items = get_freebie_eligible_items()
    if not eligible_items:
        return None
    return random.choice(eligible_items)


# =============================================================================
# TIME HELPERS
# =============================================================================

def get_server_midnight(guild_settings: "GuildSettings") -> datetime:
    """
    Get today's midnight in the server's timezone.
    Returns the most recent midnight (start of current day).
    """
    tz = ZoneInfo(guild_settings.discord_server_timezone)
    now = datetime.now(tz)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_next_midnight(guild_settings: "GuildSettings") -> datetime:
    """
    Get the next midnight in the server's timezone.
    """
    from datetime import timedelta
    midnight = get_server_midnight(guild_settings)
    return midnight + timedelta(days=1)


def has_claimed_today(user_data: "User", guild_settings: "GuildSettings") -> bool:
    """
    Check if the user has already claimed their daily freebie today.
    Compares last claim timestamp against today's midnight in server timezone.
    """
    last_claim = getattr(user_data, 'last_daily_freebie_claim', 0.0)
    if last_claim == 0.0:
        return False
    
    # Get today's midnight in server timezone
    midnight = get_server_midnight(guild_settings)
    midnight_timestamp = midnight.timestamp()
    
    # If last claim was after today's midnight, they've already claimed
    return last_claim >= midnight_timestamp


def get_time_until_next_freebie(guild_settings: "GuildSettings") -> int:
    """
    Get seconds until next daily freebie is available (next midnight).
    """
    next_midnight = get_next_midnight(guild_settings)
    return max(0, int(next_midnight.timestamp() - time.time()))


def format_time_remaining(seconds: int) -> str:
    """
    Format seconds into a human-readable string (e.g., "5h 32m").
    """
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m"
    else:
        return f"{secs}s"


# =============================================================================
# FREEBIE CLAIM LOGIC
# =============================================================================

def user_owns_item(user_data: "User", item_id: str) -> bool:
    """Check if user already owns a specific item."""
    return any(inv.item_id == item_id for inv in user_data.current_item_inventory)


def can_track_freebie(user_data: "User") -> bool:
    """
    Check if the freebie tracking field exists on the user model.
    Returns False if bot needs restart for new model fields.
    """
    try:
        # Try to access the field - will raise if it doesn't exist
        _ = user_data.last_daily_freebie_claim
        return True
    except (ValueError, AttributeError):
        return False


def claim_daily_freebie(
    user_data: "User",
    guild_settings: "GuildSettings"
) -> Tuple[bool, str, Optional[dict], int]:
    """
    Attempt to claim the daily freebie for a user.
    
    Returns:
        Tuple of (success, message, item_data, petcoin_awarded)
        - success: Whether the claim was processed
        - message: Status message for display
        - item_data: The item dict (with item_id) if an item was given
        - petcoin_awarded: Amount of petcoins given if duplicate (0 otherwise)
    """
    # Check if the model supports freebie tracking (bot may need restart)
    if not can_track_freebie(user_data):
        return (
            False,
            "Daily Freebie feature requires a **bot restart** to activate. Please ask an admin to restart the bot.",
            None,
            0
        )
    
    # Check if already claimed today
    if has_claimed_today(user_data, guild_settings):
        time_remaining = get_time_until_next_freebie(guild_settings)
        time_str = format_time_remaining(time_remaining)
        return (
            False,
            f"You've already claimed your daily freebie! Next one available in **{time_str}**.",
            None,
            0
        )
    
    # Select random item
    item = select_random_freebie()
    if item is None:
        return (
            False,
            "No items are available for the daily freebie. Please contact an admin.",
            None,
            0
        )
    
    item_id = item["item_id"]
    item_name = item.get("name", item_id)
    item_value = item.get("value", 10)
    item_rarity = item.get("rarity", "uncommon")
    item_emoji = item.get("emoji", "🎁")
    
    # Update claim timestamp and counter
    # Use try/except for backward compatibility with existing User objects
    try:
        user_data.last_daily_freebie_claim = time.time()
    except (ValueError, AttributeError):
        # Field doesn't exist yet - bot needs restart for new model fields
        pass
    
    try:
        current_freebies = getattr(user_data, 'total_freebies_claimed', 0)
        user_data.total_freebies_claimed = current_freebies + 1
    except (ValueError, AttributeError):
        pass
    
    # Check if user already owns this item
    if user_owns_item(user_data, item_id):
        # Give petcoin value instead
        user_data.current_petcoin += item_value
        try:
            current_earned = getattr(user_data, 'most_petcoin_earned', 0)
            user_data.most_petcoin_earned = current_earned + item_value
        except (ValueError, AttributeError):
            pass
        
        return (
            True,
            f"You already own **{item_name}**! You received **{item_value:,}** Petcoins instead.",
            item,
            item_value
        )
    
    # Add item to inventory
    new_item = InventoryItem(
        item_id=item_id,
        acquired_timestamp=time.time(),
        acquired_via="daily_freebie"
    )
    user_data.current_item_inventory.append(new_item)
    
    # Build rarity display
    rarity_stars = {
        "uncommon": "⭐⭐",
        "rare": "⭐⭐⭐"
    }.get(item_rarity, "⭐")
    
    return (
        True,
        f"You received **{item_emoji} {item_name}**!\n{rarity_stars} {item_rarity.title()}",
        item,
        0
    )


# =============================================================================
# FREEBIE STATUS FOR UI
# =============================================================================

def get_freebie_button_state(
    user_data: "User",
    guild_settings: "GuildSettings"
) -> Tuple[bool, str]:
    """
    Get the button state for the daily freebie button.
    
    Returns:
        Tuple of (disabled, label)
        - disabled: Whether the button should be disabled
        - label: The label to display on the button
    """
    # Check if tracking is available (bot may need restart)
    if not can_track_freebie(user_data):
        return (True, "Restart Required")
    
    if has_claimed_today(user_data, guild_settings):
        time_remaining = get_time_until_next_freebie(guild_settings)
        time_str = format_time_remaining(time_remaining)
        return (True, f"Freebie ({time_str})")
    else:
        return (False, "Daily Freebie")
