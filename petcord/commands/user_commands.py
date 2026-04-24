"""
User commands for Petcord cog.
"""

from __future__ import annotations

import time
import discord
from redbot.core import commands
from redbot.core.commands import Context
from typing import TYPE_CHECKING

from ..abc import MixinMeta
from ..common.utils import is_allowed_channel
from ..views import MainMenuView, StatsView
from ..views.gift_views import PetGiftView, PET_TRANSFER_LOCKOUT_SECONDS

if TYPE_CHECKING:
    pass


class UserCommands(MixinMeta):
    """User-facing commands for Petcord."""
    
    @commands.command(name="petcord", aliases=["pcpet"])
    @commands.guild_only()
    async def petcord_main(self, ctx: Context) -> None:
        """A Pet raising and interaction game!
        
        `[p]petcord` - Main pet menu, pet interaction and access your Home and Memorial.
        `[p]pcstat` - View your pet statistics, medals, and interaction history.
        `[p]pcgift` - Gift a pet from your Home to another user (recipient must accept).

        """
        # Get guild configuration
        guild_settings = self.db.get_conf(ctx.guild)
        
        # Check if command is in allowed channel (silently skip if not, admins bypass)
        if not await is_allowed_channel(ctx, guild_settings.allowed_channel_id):
            return
        
        # Check if game is enabled
        if not guild_settings.game_is_enabled:
            await ctx.send(
                "🎮 Petcord is not enabled in this server. "
                f"An admin can enable it with the `{ctx.clean_prefix}pcset enable` command.",
                delete_after=10
            )
            return
        
        # Get or create user data
        user_data = guild_settings.get_user(ctx.author)
        
        # Create the main menu view
        view = MainMenuView(
            cog=self,
            user_data=user_data,
            guild_settings=guild_settings,
            author_id=ctx.author.id
        )
        
        # Build and send embed
        embed = await view.build_embed()
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name="pcstat", aliases=["pcstats"])
    @commands.guild_only()
    async def pcstat_command(self, ctx: Context, user: discord.Member = None) -> None:
        """View Petcord statistics or another user's pet status.
        
        Without arguments: Shows your medals, lifetime stats, care performance,
        interaction history, and provides navigation to Home and Memorial.
        
        With a user argument: Shows that user's current pet status (view-only).
        
        **Arguments:**
        - `[user]` - Optional. View another user's current pet status.
        """
        # Get guild configuration
        guild_settings = self.db.get_conf(ctx.guild)
        
        # Check if command is in allowed channel (silently skip if not, admins bypass)
        if not await is_allowed_channel(ctx, guild_settings.allowed_channel_id):
            return
        
        # Check if game is enabled
        if not guild_settings.game_is_enabled:
            await ctx.send(
                "🎮 Petcord is not enabled in this server. "
                f"An admin can enable it with the `{ctx.clean_prefix}pcset enable` command.",
                delete_after=10
            )
            return
        
        # If a target user is specified, show their pet status (view-only)
        if user is not None:
            target_data = guild_settings.get_user(user)
            
            if target_data.current_pet is None:
                await ctx.send(f"🐾 **{user.display_name}** doesn't have a current pet.")
                return
            
            # Create a view-only MainMenuView for the target user
            # Pass author_id as None to disable all buttons (view-only mode)
            view = MainMenuView(
                cog=self,
                user_data=target_data,
                guild_settings=guild_settings,
                author_id=None  # View-only mode
            )
            
            # Build and send embed
            embed = await view.build_embed()
            embed.set_author(name=f"{user.display_name}'s Pet", icon_url=user.display_avatar.url)
            embed.set_footer(text=f"Viewed by {ctx.author.display_name}")
            
            # Send without the view (no buttons for viewing others' pets)
            await ctx.send(embed=embed)
            return
        
        # No user specified - show the author's own statistics
        user_data = guild_settings.get_user(ctx.author)
        
        # Create the stats view
        view = StatsView(
            cog=self,
            user_data=user_data,
            guild_settings=guild_settings,
            author_id=ctx.author.id
        )
        
        # Build and send embed
        embed = view.build_embed()
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name="pcgift", aliases=["petgift", "giftpet"])
    @commands.guild_only()
    async def pcgift_command(self, ctx: Context, recipient: discord.Member, *, pet_name: str) -> None:
        """Gift a pet from your Home to another user.
        
        The recipient must accept the gift for the transfer to complete.
        Only pets in your Home (graduated adults) can be gifted.
        
        **Arguments:**
        - `<recipient>` - The user to gift the pet to.
        - `<pet_name>` - The name of the pet to gift.
        
        **Cooldowns:**
        - You must wait between gifts (server configurable, default 6 hours).
        - A pet cannot be re-gifted for 24 hours after being received.
        
        **Examples:**
        - `[p]pcgift @friend Whiskers`
        - `[p]pcgift @friend "Mr Fluffy"` (use quotes for names with spaces)
        """
        # Get guild configuration
        guild_settings = self.db.get_conf(ctx.guild)
        
        # Check if command is in allowed channel (silently skip if not, admins bypass)
        if not await is_allowed_channel(ctx, guild_settings.allowed_channel_id):
            return
        
        # Check if game is enabled
        if not guild_settings.game_is_enabled:
            await ctx.send(
                "🎮 Petcord is not enabled in this server.",
                delete_after=10
            )
            return
        
        # Prevent self-gifting
        if recipient.id == ctx.author.id:
            await ctx.send("❌ You can't gift a pet to yourself!")
            return
        
        # Prevent gifting to bots
        if recipient.bot:
            await ctx.send("❌ You can't gift a pet to a bot!")
            return
        
        # Get user data
        sender_data = guild_settings.get_user(ctx.author)
        recipient_data = guild_settings.get_user(recipient)
        
        # Check if sender has any home pets
        if not sender_data.home_pets:
            await ctx.send("🏠 You don't have any pets in your Home to gift!")
            return
        
        # Find the pet by name (case-insensitive)
        pet_name_lower = pet_name.lower()
        matching_pet = None
        pet_index = -1
        
        for i, pet in enumerate(sender_data.home_pets):
            if pet.name.lower() == pet_name_lower:
                matching_pet = pet
                pet_index = i
                break
        
        if matching_pet is None:
            # List their home pets for convenience
            pet_names = ", ".join(f"`{p.name}`" for p in sender_data.home_pets[:10])
            if len(sender_data.home_pets) > 10:
                pet_names += f" *...and {len(sender_data.home_pets) - 10} more*"
            await ctx.send(
                f"❌ Could not find a pet named `{pet_name}` in your Home.\n"
                f"**Your Home pets:** {pet_names}"
            )
            return
        
        # Check gift sending cooldown
        cooldown_seconds = guild_settings.gift_cooldown_hours * 3600
        time_since_last_gift = time.time() - sender_data.last_gift_sent_timestamp
        
        if time_since_last_gift < cooldown_seconds:
            remaining = cooldown_seconds - time_since_last_gift
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m"
            else:
                time_str = f"{minutes}m"
            
            await ctx.send(
                f"⏳ You must wait **{time_str}** before you can gift another pet.\n"
                f"*(Server gift cooldown: {guild_settings.gift_cooldown_hours} hours)*"
            )
            return
        
        # Check pet transfer lockout (24h after being received)
        time_since_transfer = time.time() - matching_pet.last_transferred_timestamp
        
        if matching_pet.last_transferred_timestamp > 0 and time_since_transfer < PET_TRANSFER_LOCKOUT_SECONDS:
            remaining = PET_TRANSFER_LOCKOUT_SECONDS - time_since_transfer
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m"
            else:
                time_str = f"{minutes}m"
            
            await ctx.send(
                f"⏳ **{matching_pet.name}** was recently received as a gift.\n"
                f"You must wait **{time_str}** before re-gifting this pet.\n"
                f"*(24 hour transfer lockout)*"
            )
            return
        
        # Check recipient's home capacity
        if len(recipient_data.home_pets) >= recipient_data.effective_home_capacity:
            await ctx.send(
                f"❌ **{recipient.display_name}**'s Home is full!\n"
                f"They have **{len(recipient_data.home_pets)}/{recipient_data.effective_home_capacity}** pets."
            )
            return
        
        # Create the gift view
        view = PetGiftView(
            cog=self,
            sender=ctx.author,
            sender_data=sender_data,
            recipient=recipient,
            recipient_data=recipient_data,
            guild_settings=guild_settings,
            pet=matching_pet,
            pet_index=pet_index
        )
        
        # Build and send the offer
        embed = view.build_embed()
        
        view.message = await ctx.send(
            content=f"🎁 {recipient.mention}, you've received a gift offer!",
            embed=embed,
            view=view
        )
