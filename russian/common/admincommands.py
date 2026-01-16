import asyncio
import discord
import logging
from redbot.core import commands, checks
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from typing import Optional

log = logging.getLogger("red.rroulette")

class AdminCommands:
    @commands.group(name="rrset", invoke_without_command=True)
    @checks.admin()
    async def rrset(self, ctx):
        """Set the betting limits for Russian Roulette"""
        await ctx.send("Use `.rrsetbet minbet #` or `.rrsetbet maxbet #` to set bet limits.")

    @rrset.command(name="minbet")
    async def set_minbet(self, ctx, amount: int):
        self.db.set_min_bet(ctx.guild.id, amount)
        self.save()
        await ctx.send(f"Minimum bet set to {amount}.")

    @rrset.command(name="maxbet")
    async def set_maxbet(self, ctx, amount: int):
        self.db.set_max_bet(ctx.guild.id, amount)
        self.save()
        await ctx.send(f"Maximum bet set to {amount}.")

    @rrset.command(name="default")
    async def reset_bets(self, ctx):
        self.db.set_min_bet(ctx.guild.id, 100)
        self.db.set_max_bet(ctx.guild.id, 3000)
        self.save()
        await ctx.send("Bet limits reset to default (min: 100, max: 3000).")

    @rrset.command(name="mode")
    async def set_betting_mode(self, ctx, mode: str):
        """Set the betting mode for Russian Roulette
    
        Available modes:
        - `direct` - Uses Red's economy system directly
        - `token` - Uses a token-based system for this channel only
    
        Examples:
          [p]rrset mode direct
          [p]rrset mode token
        """
        try:
            self.db.set_betting_mode(ctx.guild.id, mode.lower())
            self.save()
            
            if mode.lower() == "token":
                await ctx.send("Betting mode set to **Token Mode**. Players will use tokens instead of credits.")
            else:
                await ctx.send("Betting mode set to **Direct Mode**. Players will use the bot's economy system directly.")
        except ValueError as e:
            await ctx.send(str(e))

    @rrset.command(name="wipe")
    async def wipe_player_data(self, ctx, target: Optional[discord.Member] = None):
        """Wipe a player's Russian Roulette statistics"""
        guildsettings = self.db.get_conf(ctx.guild)
        
        if not target:
            await ctx.send("Please specify a user to wipe data for.")
            return
        
        target_user = guildsettings.get_user(target)
         
        # Reset all statistics to 0
        target_user.player_wins = 0
        target_user.player_deaths = 0
        target_user.player_chickens = 0
        target_user.player_total_challenges = 0
        target_user.player_total_rejections = 0
        target_user.player_total_games_played = 0
    
        # Financial tracking
        target_user.total_amount_won = 0
        target_user.total_amount_lost = 0
        self.save()
        
        await ctx.send(f"{target.mention}'s data has been wiped from the Roulette system.")

    @rrset.command(name="channels")
    @checks.admin()
    async def set_allowed_channels(self, ctx, *channels: discord.TextChannel):
        """Toggle channels where Russian Roulette commands can be used
        
        - With no arguments: clear all channel restrictions
        - With channel arguments: toggle each channel's restriction status
          (adds the channel if not in the list, removes it if already in the list)
        
        Examples:
          rrset channels          - Allow commands in all channels
          rrset channels #gaming  - Toggle #gaming channel restriction
        """
        guild_settings = self.db.get_conf(ctx.guild)
        
        # If no channels provided, clear all restrictions
        if not channels:
            guild_settings.allowed_channels = []
            await ctx.send("Russian Roulette commands can now be used in all channels.")
            self.save()
            return
            
        # Toggle each provided channel
        changes = []
        for channel in channels:
            if channel.id in guild_settings.allowed_channels:
                # Remove channel if already in list
                guild_settings.allowed_channels.remove(channel.id)
                changes.append(f"➖ Removed {channel.mention}")
            else:
                # Add channel if not in list
                guild_settings.allowed_channels.append(channel.id)
                changes.append(f"➕ Added {channel.mention}")
        
        self.save()
        
        # Format response message
        response = "\n".join(changes)
        
        if guild_settings.allowed_channels:
            allowed_channels = []
            for channel_id in guild_settings.allowed_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    allowed_channels.append(channel.mention)
            
            channels_str = ", ".join(allowed_channels)
            response += f"\n\nRussian Roulette commands can now only be used in: {channels_str}"
        else:
            response += "\n\nNo restrictions - Russian Roulette commands can be used in all channels."
            
        await ctx.send(response)
        
    @rrset.command(name="listchannels")
    @checks.admin()
    async def list_allowed_channels(self, ctx):
        """List all channels where Russian Roulette commands can be used"""
        guild_settings = self.db.get_conf(ctx.guild)
        
        if not guild_settings.allowed_channels:
            await ctx.send("Russian Roulette commands can be used in all channels.")
            return
        
        # Get channel mentions for all valid channels
        allowed_channels = []
        for channel_id in guild_settings.allowed_channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                allowed_channels.append(channel.mention)
            
        if allowed_channels:
            channels_str = ", ".join(allowed_channels)
            await ctx.send(f"Russian Roulette commands can only be used in these channels: {channels_str}")
        else:
            await ctx.send("No valid channels are configured. Commands can be used in all channels.")
            # Clean up invalid channels
            guild_settings.allowed_channels = []
            self.save()

    @rrset.command(name="clearusers")
    @checks.admin()
    async def clear_all_users(self, ctx):
        """Clear all user data from Russian Roulette for this server
    
        This will remove ALL player statistics while preserving server settings 
        like betting limits and channel restrictions.
        """
        guild_settings = self.db.get_conf(ctx.guild)
        
        # Get count of users for confirmation message
        user_count = len(guild_settings.users)
        
        # Confirm before clearing
        confirm_msg = await ctx.send(f"⚠️ **WARNING**: This will delete statistics for **{user_count}** users. "
                                   f"Server settings like bet limits and channel restrictions will be preserved.\n\n"
                                   f"Are you sure? Reply with `yes` to confirm.")
        
        def check(msg):
            return msg.author == ctx.author and msg.channel == ctx.channel and msg.content.lower() == "yes"
        
        try:
            await self.bot.wait_for("message", check=check, timeout=30.0)
        except asyncio.TimeoutError:
            await confirm_msg.edit(content="Operation cancelled - you didn't confirm in time.")
            return
        
        # Clear all users while preserving other settings
        guild_settings.users = {}
        self.save()
        
        await ctx.send(f"✅ Success! All Russian Roulette user data for this server has been cleared. "
                      f"Server settings have been preserved.")

    @rrset.command(name="display")
    @checks.admin()
    async def display_settings(self, ctx):
        """Display current Russian Roulette settings"""
        guild_settings = self.db.get_conf(ctx.guild.id)
        
        min_bet = guild_settings.min_bet
        max_bet = guild_settings.max_bet
        
        # Determine the active mode
        if guild_settings.token_mode_enabled:
            mode = "Token Mode"
            mode_description = "Players use tokens that are tracked separately from the bot's economy"
            currency = "tokens"
        else:
            mode = "Direct Mode" 
            mode_description = "Players use credits directly from the bot's economy system"
            currency = "credits"
        
        # Create embed
        embed = discord.Embed(
            title="Russian Roulette Settings",
            description="Current configuration for this server",
            color=discord.Color.gold()
        )
        
        embed.add_field(name="Minimum Bet", value=f"{min_bet} {currency}", inline=True)
        embed.add_field(name="Maximum Bet", value=f"{max_bet} {currency}", inline=True)
        embed.add_field(name="Betting Mode", value=f"**{mode}**\n{mode_description}", inline=False)
        
        # Add conversion status
        conversion_status = "Enabled ✅" if guild_settings.convert_allowed else "Disabled ❌"
        embed.add_field(
            name="Currency Conversion",
            value=f"Status: **{conversion_status}**\n" +
                  f"Ratio: {guild_settings.token_to_discord_ratio} tokens = 1 credit",
            inline=False
        )
        
        # Add channel restriction info if applicable
        if guild_settings.allowed_channels:
            channels_text = []
            for channel_id in guild_settings.allowed_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channels_text.append(channel.mention)
        
            if channels_text:
                embed.add_field(
                    name="Channel Restrictions", 
                    value="Commands can only be used in these channels:\n" + ", ".join(channels_text),
                    inline=False
                )
        else:
            embed.add_field(
                name="Channel Restrictions", 
                value="No restrictions - Commands can be used in any channel",
                inline=False
            )
        
        await ctx.send(embed=embed)
        
    @rrset.command(name="convert")
    @checks.admin()
    async def set_conversion(self, ctx, state: str):
        """Enable or disable conversion between tokens and Discord credits
    
        Examples:
        [p]rrset convert on
        [p]rrset convert off
        """
        state = state.lower()
        if state not in ["on", "off"]:
            await ctx.send("❌ Invalid option. Please use 'on' or 'off'.")
            return
        
        guild_settings = self.db.get_conf(ctx.guild.id)
        
        # Update the setting
        if state == "on":
            guild_settings.convert_allowed = True
            await ctx.send("✅ Currency conversion has been **enabled**. Players can now convert between tokens and Discord credits.")
        else:
            guild_settings.convert_allowed = False
            await ctx.send("✅ Currency conversion has been **disabled**. Players can no longer convert between tokens and Discord credits.")
    
        self.save()

    async def ensure_field_limits(self, embed):
        """Ensure all embed fields are within Discord's 1024 character limit"""
        # We need to iterate through a copy of the fields since we'll be modifying the original
        fields_to_process = embed.fields.copy()
        
        # Remove all fields from the embed (we'll add them back properly sized)
        embed.clear_fields()
        
        for field in fields_to_process:
            if len(field.value) > 1024:
                # Split the field value
                chunks = self.split_field_content(field.value, max_length=1024)
                
                # Add fields with properly sized chunks
                for i, chunk in enumerate(chunks):
                    if i == 0:
                        # First chunk keeps the original name
                        embed.add_field(name=field.name, value=chunk, inline=field.inline)
                    else:
                        # Additional chunks get continuation markers
                        embed.add_field(name=f"{field.name} (continued)", value=chunk, inline=field.inline)
            else:
                # Field is within limits, add it as-is
                embed.add_field(name=field.name, value=field.value, inline=field.inline)
        
        return embed

    def split_field_content(self, content: str, max_length: int = 1000) -> list:
        """Split content into chunks that fit within Discord's field value limits"""
        if len(content) <= max_length:
            return [content]
            
        # Split content into multiple fields
        chunks = []
        current_chunk = ""
        
        # Split by lines to keep related content together
        lines = content.split("\n")
        
        for line in lines:
            # If adding this line would exceed the limit, start a new chunk
            if len(current_chunk) + len(line) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = line
            else:
                # Add line to current chunk
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line
        
        # Add the final chunk
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
