"""
Views for Greenacres Fishing.
All views have a 5-minute timeout by default.
"""

import asyncio
import discord
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import GreenacresFishing

# Default timeout for all views (5 minutes)
DEFAULT_TIMEOUT = 300.0


class BaseView(discord.ui.View):
    """
    Base view class with common functionality.
    All views inherit from this to ensure consistent timeout behavior.
    Timeout is reset on every valid interaction.
    """
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        timeout: float = DEFAULT_TIMEOUT
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.author = author
        self.message: Optional[discord.Message] = None
        self._timeout_duration = timeout  # Store original timeout for reset
        self._is_stopped = False  # Track if view has been stopped/timed out
        
        # Register this view with the cog for tracking
        if hasattr(cog, 'active_views'):
            cog.active_views.add(self)
        
        # Register this view with the cog for tracking
        if hasattr(cog, 'active_views'):
            cog.active_views.add(self)
        
        # Register this view with the cog
        if hasattr(cog, 'active_views'):
            cog.active_views.add(self)
    
    def is_active(self) -> bool:
        """Check if the view is still active (not stopped or timed out)."""
        return not self._is_stopped and not self.is_finished()
    
    def stop(self) -> None:
        """Stop the view and mark it as stopped."""
        self._is_stopped = True
        
        # Unregister this view from the cog
        if hasattr(self.cog, 'active_views'):
            self.cog.active_views.discard(self)
        
        super().stop()
    
    def _reset_timeout(self) -> None:
        """Reset the view's timeout timer. Called on valid interactions."""
        if self._is_stopped:
            return
        # Safely reset the timeout by stopping and restarting with a new timeout
        # This is more reliable than accessing internal attributes
        try:
            # Access the internal timeout tracking if available
            if hasattr(self, '_View__timeout_expiry') and self._View__timeout_expiry is not None:
                loop = asyncio.get_running_loop()
                self._View__timeout_expiry = loop.time() + self._timeout_duration
        except Exception:
            pass  # Silently ignore if timeout reset fails
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original author can interact with the view and game is enabled."""
        # Check if game is enabled
        conf = self.cog.db.get_conf(interaction.guild)
        if not conf.is_game_enabled:
            await interaction.response.send_message(
                "Greenacres Fishing is currently disabled. Please try again later.",
                ephemeral=True
            )
            return False
        
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "This isn't your fishing session!", 
                ephemeral=True
            )
            return False
        
        # Reset timeout on valid interaction
        self._reset_timeout()
        return True
    
    async def on_timeout(self) -> None:
        """Disable all buttons when the view times out."""
        self._is_stopped = True
        
        # Unregister from active views
        if hasattr(self.cog, 'active_views'):
            self.cog.active_views.discard(self)
        
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass
    
    async def stop_and_update(
        self, 
        interaction: discord.Interaction, 
        new_view: "BaseView",
        embed: discord.Embed
    ) -> None:
        """
        Stop this view and update to a new view.
        This prevents overlapping timers and closure problems.
        """
        self.stop()
        new_view.message = self.message
        await interaction.response.edit_message(embed=embed, view=new_view)


class MainMenuView(BaseView):
    """Main fishing menu with Go Fishing, Bait Shop, Inventory, Leaderboards, and Close buttons."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member
    ):
        super().__init__(cog=cog, author=author)
    
    # Row 0: Main actions
    @discord.ui.button(label="Go Fishing", style=discord.ButtonStyle.primary, emoji="🎣", row=0)
    async def go_fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Start a fishing session."""
        # Create location select view
        from .fishing_view import LocationSelectView
        new_view = LocationSelectView(cog=self.cog, author=self.author)
        embed = await new_view.create_location_embed(interaction.guild)
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Bait Shop", style=discord.ButtonStyle.secondary, emoji="🐛", row=0)
    async def bait_shop(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open the bait shop."""
        # Create new bait shop view
        from .bait_shop_view import BaitShopView
        new_view = BaitShopView(cog=self.cog, author=self.author)
        embed = await new_view.create_shop_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Inventory", style=discord.ButtonStyle.secondary, emoji="🎒", row=0)
    async def inventory(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View your inventory."""
        # Create new inventory view
        from .inventory_view import InventoryView
        new_view = InventoryView(cog=self.cog, author=self.author)
        embed = await new_view.create_inventory_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    # Row 1: Secondary actions
    @discord.ui.button(label="Leaderboards", style=discord.ButtonStyle.secondary, emoji="🏆", row=1)
    async def leaderboards(self, interaction: discord.Interaction, button: discord.ui.Button):
        """View the leaderboards."""
        # Create new leaderboards view
        from .leaderboard_view import LeaderboardView
        new_view = LeaderboardView(cog=self.cog, author=self.author)
        embed = await new_view.create_leaderboard_embed(interaction.guild)
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Search Garbage", style=discord.ButtonStyle.secondary, emoji="🗑️", row=1)
    async def search_garbage(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Search garbage for free lures (12 hour cooldown)."""
        import time
        import random
        
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        # Check cooldown (12 hours = 43200 seconds)
        current_time = int(time.time())
        cooldown_seconds = 12 * 60 * 60  # 12 hours
        time_since_last = current_time - user_data.last_scavenge_timestamp
        
        if time_since_last < cooldown_seconds:
            # Still on cooldown
            remaining = cooldown_seconds - time_since_last
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            await interaction.response.send_message(
                f"🗑️ The garbage has already been picked through recently.\n"
                f"Come back in **{hours}h {minutes}m**.",
                ephemeral=True
            )
            return
        
        # Scavenge successful! Determine what they find
        if random.random() < 0.5:
            # 50% chance: 1-7 breadballs
            qty = random.randint(1, 7)
            lure_id = "breadballs"
            lure_name = "Breadballs"
            uses_per_item = 1
        else:
            # 50% chance: 3-5 grubs
            qty = random.randint(3, 5)
            lure_id = "grubs"
            lure_name = "Grubs"
            uses_per_item = 1
        
        # Add to inventory (check if they already have this lure type)
        found_existing = False
        for lure in user_data.current_lure_inventory:
            if lure.get("lure_id") == lure_id:
                lure["quantity"] = lure.get("quantity", 0) + qty
                lure["remaining_uses"] = lure.get("remaining_uses", 0) + (qty * uses_per_item)
                lure["uses_per_item"] = uses_per_item
                found_existing = True
                break
        
        if not found_existing:
            # Add new lure entry
            user_data.current_lure_inventory.append({
                "lure_id": lure_id,
                "quantity": qty,
                "remaining_uses": qty * uses_per_item,
                "uses_per_item": uses_per_item
            })
        
        # Update cooldown
        user_data.last_scavenge_timestamp = current_time
        self.cog.save()
        
        await interaction.response.send_message(
            f"🗑️ You dig through the garbage and find...\n\n"
            f"**{qty}x {lure_name}!** 🎉\n\n"
            f"They've been added to your lure inventory.",
            ephemeral=True
        )
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="❌", row=1)
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the fishing menu."""
        self.stop()
        await interaction.response.edit_message(
            content="Thanks for visiting Greenacres Fishing! 🎣",
            embed=None,
            view=None
        )


class ConfirmView(BaseView):
    """Simple confirm/cancel view for confirmations."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        confirm_callback,
        cancel_callback=None
    ):
        super().__init__(cog=cog, author=author)
        self.confirm_callback = confirm_callback
        self.cancel_callback = cancel_callback
        self.value: Optional[bool] = None
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the action."""
        self.value = True
        self.stop()
        if self.confirm_callback:
            await self.confirm_callback(interaction)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the action."""
        self.value = False
        self.stop()
        if self.cancel_callback:
            await self.cancel_callback(interaction)
        else:
            await interaction.response.edit_message(
                content="Action cancelled.",
                embed=None,
                view=None
            )


class BackToMenuMixin:
    """Mixin that adds a Back button to return to main menu."""
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=4)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to the main menu."""
        from .main_menu import create_main_menu_embed
        
        new_view = MainMenuView(cog=self.cog, author=self.author)
        embed = await create_main_menu_embed(self.cog, interaction.guild, self.author)
        await self.stop_and_update(interaction, new_view, embed)
