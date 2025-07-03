import asyncio
import random
import discord
from discord.errors import Forbidden  # Add this import
from redbot.core import commands, bank, checks
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
from typing import List, Optional, Dict, Any, Tuple
import logging

log = logging.getLogger("red.rroulette")

def channel_check():
    """Check if the command is being used in an allowed channel"""
    async def predicate(ctx):
        # Only allow commands in guilds (not DMs)
        if ctx.guild is None:
            return False
            
        # Skip check for guild owner and bot owner
        if await ctx.bot.is_owner(ctx.author) or ctx.author == ctx.guild.owner:
            return True
        
        cog = ctx.cog
        guild_settings = cog.db.get_conf(ctx.guild)
        
        # If there are no channel restrictions, allow the command
        if not guild_settings.allowed_channels:
            return True
            
        # Check if the current channel is allowed
        if guild_settings.is_channel_allowed(ctx.channel.id):
            return True
            
        # Get the list of allowed channels for the error message
        allowed_channels = []
        for channel_id in guild_settings.allowed_channels:
            channel = ctx.guild.get_channel(channel_id)
            if channel:
                allowed_channels.append(channel.mention)
        
        # Format allowed channels for the error message
#        if allowed_channels:
#            channels_str = ", ".join(allowed_channels)
#            await ctx.send(f"❌ Russian Roulette commands can only be used in these channels: {channels_str}")
#        else:
#            await ctx.send("❌ Russian Roulette commands cannot be used in this channel.")
#        
        return False
        
    return commands.check(predicate)

class Commands:
    @commands.group(name="russian", invoke_without_command=True)
    @channel_check()
    async def russian(self, ctx, mode: str, bet: int, *players: discord.Member):
        """Russian Roulette game for Solo or Challenge mode!! (Up to 3 total Players)\n
        Usage: `russian solo <bet>`
        Usage: `russian challenge <bet> [@player1] [@player2]`\n
        \n
        Other Commands: `russianlb` or `rrlb` to bring up the leaderboard.\n
        """
        minbet = self.db.get_min_bet(ctx.guild.id)
        maxbet = self.db.get_max_bet(ctx.guild.id)

        if bet < minbet or bet > maxbet:
            await ctx.send(f"Bets must be between {minbet} and {maxbet}.")
            return

        # Check if user is already in a game
        if ctx.author.id in self.active_games:
            await ctx.send(f"{ctx.author.mention} is already in a game of Russian Roulette!")
            return
            
        # Check if user has enough credits
        balance = await bank.get_balance(ctx.author)
        if balance < bet:
            await ctx.send(f"⚠️ **{ctx.author.mention} DOESN'T HAVE ENOUGH CREDITS TO PLACE THAT BET!** ⚠️")
            return

        if mode.lower() == "solo":
            await self.solo_play(ctx, bet)
        elif mode.lower() == "challenge":
            # Enforce maximum of 2 challenged players
            if len(players) > 2:
                await ctx.send("You can challenge up to 2 players maximum.")
                return
            await self.challenge_play(ctx, bet, players)
        else:
            await ctx.send("Invalid mode. Use `solo` or `challenge`.")

    @commands.command(name="rrstats", aliases=["russianstats"])
    @channel_check()
    async def russian_stats(self, ctx, member: discord.Member = None):
        """
        View your Russian Roulette stats or another player's stats
    
        Examples:
          [p]rrstats
          [p]rrstats @player
        """
        # Default to command author if no member specified
        target = member or ctx.author
    
        # Get user data from database
        guild_settings = self.db.get_conf(ctx.guild.id)
        user_data = guild_settings.get_user(target)
    
        # Create embed
        embed = discord.Embed(
            title=f"Russian Roulette Stats: {target.display_name}",
            color=discord.Color.dark_red()
        )
    
        # Add player's avatar if available
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
    
        # Game stats section
        games_played = user_data.player_total_games_played
        wins = user_data.player_wins
        deaths = user_data.player_deaths
        chickens = user_data.player_chickens
    
        # Calculate win rate if games played
        win_rate = f"{(wins / games_played) * 100:.1f}%" if games_played > 0 else "N/A"
        death_rate = f"{(deaths / games_played) * 100:.1f}%" if games_played > 0 else "N/A"
    
        embed.add_field(
            name="Game Stats", 
            value=(
                f"🎮 **Games Played:** {games_played}\n"
                f"🏆 **Wins:** {wins} ({win_rate})\n"
                f"💀 **Deaths:** {deaths} ({death_rate})\n"
                f"🐔 **Chickened Out:** {chickens}\n"
            ),
            inline=False
        )
    
        # Social stats section
        embed.add_field(
            name="Social Stats", 
            value=(
                f"🤝 **Challenges Made:** {user_data.player_total_challenges}\n"
                f"👎 **Challenges Rejected:** {user_data.player_total_rejections}\n"
            ),
            inline=False
        )
    
        # Financial stats section
        embed.add_field(
            name="Financial Stats", 
            value=(
                f"💰 **Total Won:** {user_data.total_amount_won}\n"
                f"💸 **Total Lost:** {user_data.total_amount_lost}\n"
            ),
            inline=False
        )
    
        # Show token balance if token mode is enabled
        if guild_settings.token_mode_enabled:
            embed.add_field(
                name="Token Balance", 
                value=f"🪙 **Current Tokens:** {user_data.token_mode_tokens}",
                inline=False
            )
    
        # Footer with betting mode info
        betting_mode = "Token Mode" if guild_settings.token_mode_enabled else "Direct Mode"
        embed.set_footer(text=f"Server using: {betting_mode}")
    
        await ctx.send(embed=embed)

    @commands.group(name="rrconvert", aliases=["russianconvert"], invoke_without_command=True)
    @channel_check()
    async def rr_convert(self, ctx):
        """Convert between tokens and Discord credits
    
        Use the subcommands:
        [p]rrconvert token <amount> - Convert tokens to Discord credits
        [p]rrconvert discord <amount> - Convert Discord credits to tokens
        """
        await ctx.send_help(ctx.command)

    @rr_convert.command(name="token")
    @channel_check()
    async def convert_token(self, ctx, amount: int):
        """Convert tokens to Discord credits
    
        Example:
        [p]rrconvert token 500
        """
        guild_settings = self.db.get_conf(ctx.guild.id)
        
        # Check if conversions are allowed
        if not guild_settings.convert_allowed:
            await ctx.send("❌ Conversions are currently disabled by the server administrator.")
            return
        
        user_data = guild_settings.get_user(ctx.author)
        
        # Check if amount is positive
        if amount <= 0:
            await ctx.send("❌ Please enter a positive amount to convert.")
            return
        
        # Check if user has enough tokens
        if user_data.token_mode_tokens < amount:
            await ctx.send(f"❌ You don't have enough tokens. Current balance: {user_data.token_mode_tokens} tokens")
            return
        
        # Calculate credits to receive
        ratio = guild_settings.token_to_discord_ratio
        credits = amount // ratio
        
        # If no credits would be received
        if credits <= 0:
            await ctx.send(f"❌ You need at least {ratio} tokens to convert to 1 credit.")
            return
        
        # Actual tokens that will be used (remove remainder)
        tokens_used = credits * ratio
        
        # Ask for confirmation
        msg = (f"💱 **Token Conversion**\n\n"
               f"Convert {tokens_used} tokens to {credits} Discord credits?\n\n"
               f"Type 'yes' to confirm or 'no' to cancel.")
        await ctx.send(msg)
        
        # Wait for confirmation
        try:
            response = await self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"],
                timeout=30.0
            )
            
            if response.content.lower() != "yes":
                await ctx.send("❌ Conversion cancelled.")
                return
            
            # Process conversion
            if user_data.remove_tokens(tokens_used):
                await bank.deposit_credits(ctx.author, credits)
                self.save()  # Save the database
                
                await ctx.send(f"✅ Successfully converted {tokens_used} tokens to {credits} Discord credits!")
            else:
                await ctx.send(f"❌ Conversion failed. Not enough tokens.")
        
        except asyncio.TimeoutError:
            await ctx.send("❌ Conversion cancelled due to timeout.")

    @rr_convert.command(name="discord")
    @channel_check()
    async def convert_discord(self, ctx, amount: int):
        """Convert Discord credits to tokens
    
        Example:
        [p]rrconvert discord 10
        """
        guild_settings = self.db.get_conf(ctx.guild.id)
        
        # Check if conversions are allowed
        if not guild_settings.convert_allowed:
            await ctx.send("❌ Conversions are currently disabled by the server administrator.")
            return
    
        # Check if token mode is enabled with improved message
        if not guild_settings.token_mode_enabled:
            await ctx.send("❌ The game is not currently in Token-Mode and as such you cannot convert discord currency to Tokens. You may still convert Tokens to Discord Currency however.")
            return
        
        user_data = guild_settings.get_user(ctx.author)
        
        # Check if amount is positive
        if amount <= 0:
            await ctx.send("❌ Please enter a positive amount to convert.")
            return
        
        # Check if user has enough Discord credits
        if await bank.get_balance(ctx.author) < amount:
            await ctx.send(f"❌ You don't have enough Discord credits.")
            return
        
        # Calculate tokens to receive
        ratio = guild_settings.token_to_discord_ratio
        tokens = amount * ratio
        
        # Ask for confirmation
        msg = (f"💱 **Discord Credit Conversion**\n\n"
               f"Convert {amount} Discord credits to {tokens} tokens?\n\n"
               f"Type 'yes' to confirm or 'no' to cancel.")
        await ctx.send(msg)
        
        # Wait for confirmation
        try:
            response = await self.bot.wait_for(
                "message",
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ["yes", "no"],
                timeout=30.0
            )
            
            if response.content.lower() != "yes":
                await ctx.send("❌ Conversion cancelled.")
                return
            
            # Process conversion
            try:
                await bank.withdraw_credits(ctx.author, amount)
                user_data.add_tokens(tokens)
                self.save()  # Save the database
                
                await ctx.send(f"✅ Successfully converted {amount} Discord credits to {tokens} tokens!")
            except ValueError:
                await ctx.send("❌ Conversion failed. Not enough Discord credits.")
        
        except asyncio.TimeoutError:
            await ctx.send("❌ Conversion cancelled due to timeout.")

    @commands.command(name="russiancommands", aliases=["rrcommands"])
    @channel_check()
    async def rr_commands(self, ctx):
        """Display all Russian Roulette commands you have access to"""
        # Check if user is admin
        is_admin = await self.bot.is_admin(ctx.author) or ctx.author == ctx.guild.owner
    
        # Create the base embed
        embed = discord.Embed(
            title="Russian Roulette Commands",
            description="Here are all the commands you can use with Russian Roulette:",
            color=discord.Color.dark_red()
        )
    
        # Add user commands section
        user_cmds = [
            "`russian solo <bet>` - Play a solo game of Russian Roulette",
            "`russian challenge <bet> [@player1] [@player2]` - Challenge up to 2 players",
            "`rrstats [@player]` - View your stats or another player's stats",
            "`russianlb` or `rrlb` - View the leaderboard",
            "`russianconvert` - Convert Tokens/Discord Credits between each other in Token-mode.",
        ]
    
        # Check if token mode is enabled to show conversion commands
        guild_settings = self.db.get_conf(ctx.guild)
        if guild_settings.token_mode_enabled:
            user_cmds.extend([
                "",
                "**Token Conversion:**",
                "`rrconvert token <amount>` - Convert tokens to Discord credits",
                "`rrconvert discord <amount>` - Convert Discord credits to tokens"
            ])
        embed.add_field(
            name="🎮 Player Commands",
            value="\n".join(user_cmds),
            inline=False
        )
    
        # Add admin commands if the user is an admin
        if is_admin:
            admin_cmds = [
                "**Betting Settings:**",
                "`rrset minbet <amount>` - Set minimum bet",
                "`rrset maxbet <amount>` - Set maximum bet",
                "`rrset default` - Reset to default betting limits",
                "`rrset mode <direct|token>` - Toggle between direct and token mode",
                "`rrset convert <on|off>` - Enable or disable currency conversion",
                "",
                "**Channel Management:**",
                "`rrset channels [#channel1] [#channel2]` - Set allowed channels",
                "`rrset listchannels` - List allowed channels",
                "",
                "**Player Data Management:**",
                "`rrset wipe @player` - Wipe a player's statistics",
                "`rrset clearusers` - Clear ALL user data (dangerous)",
                "",
                "**Information:**",
                "`rrset display` - Show current Russian Roulette settings"
            ]
            
            embed.add_field(
                name="⚙️ Admin Commands",
                value="\n".join(admin_cmds),
                inline=False
            )
    
        # Add a footer with version info
        embed.set_footer(text=f"Russian Roulette v{self.__version__}")
    
        # Ensure the embed respects Discord's limits
        await self.ensure_field_limits(embed)
        await ctx.send(embed=embed)

    # Helper methods needed by multiple files
    async def update_countdown(self, message, embed, user, seconds):
        """Updates the embed with a countdown timer"""
        try:
            for i in range(seconds-1, -1, -1):
                # Update the description
                new_description = embed.description.split("\n\nTime remaining:")[0] + f"\n\nTime remaining: {i} seconds"
                embed.description = new_description
                
                try:
                    # Edit the message with updated countdown
                    await message.edit(embed=embed)
                except discord.NotFound:
                    # Message was deleted, stop the countdown
                    return
                
                # Wait 1 second
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            # Task was cancelled, do nothing
            return
        except Exception as e:
            # Fixed logger reference
            log.error(f"Error in countdown: {e}")

    async def clear_reactions_after_timeout(self, message, seconds):
        """Clear reactions after specified seconds"""
        await asyncio.sleep(seconds)
        try:
            await message.clear_reactions()
        except:
            pass  # Ignore errors if the message is gone or permissions changed

    def split_field_content(self, content: str, max_length: int = 1000) -> list[str]:
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