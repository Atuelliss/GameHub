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
        if allowed_channels:
            pass
#            channels_str = ", ".join(allowed_channels)
#            await ctx.send(f"❌ Russian Roulette commands can only be used in these channels: {channels_str}")

        else:
            pass
#            await ctx.send("❌ Russian Roulette commands cannot be used in this channel.")
        
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
        target_user = guildsettings.get_user(target)
        if not target:
            await ctx.send("Please specify a user to wipe data for.")
            return
         
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
        
###################
    # Game logic methods
    async def solo_play(self, ctx, bet: int):
        """Solo Russian Roulette game mode"""
        # Mark user as in a game
        self.active_games[ctx.author.id] = True
        
        # Check which betting mode is active
        is_token_mode = self.db.is_token_mode(ctx.guild.id)
        
        # Get user data if in token mode
        user_data = None
        if is_token_mode:
            user_data = self.db.get_conf(ctx.guild.id).get_user(ctx.author)
            # Check if user has enough tokens
            if user_data.get_token_balance() < bet:
                await ctx.send(f"You don't have enough tokens for this bet! You have {user_data.get_token_balance()} tokens.")
                self.active_games.pop(ctx.author.id, None)
                return
            # Deduct tokens
            user_data.remove_tokens(bet)
            self.save()  # Save token changes immediately
        else:
            # Withdraw using the bank system
            try:
                await bank.withdraw_credits(ctx.author, bet)
            except ValueError:
                await ctx.send(f"You don't have enough credits for this bet!")
                self.active_games.pop(ctx.author.id, None)
                return
        
        pistols = {
            1: {"name": "Colt 6-shooter", "cylinder": 6},
            2: {"name": "H&R 32 Double-action", "cylinder": 5},
            3: {"name": "Vainne's 3-and-Done", "cylinder": 3}
        }

        game_log = []  # Store game events for display in the embed
        game_log.append(f"💰 {ctx.author.mention} placed a bet of {bet} coins.")
        
        # Create initial embed
        embed = discord.Embed(
            title="Solo Russian Roulette", 
            description=f"{ctx.author.mention} needs to choose a pistol:\n\nTime remaining: 30 seconds"
        )
        for num, pistol in pistols.items():
            embed.add_field(name=f"[{num}] {pistol['name']}", value=f"{pistol['cylinder']} rounds", inline=False)
        
        embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
        
        # Send the initial message - this message will be updated throughout the game
        game_message = await ctx.send(embed=embed)

        # Add reaction options
        for num in pistols.keys():
            await game_message.add_reaction(str(num) + "\N{COMBINING ENCLOSING KEYCAP}")

        # Create a task for countdown display
        countdown_task = asyncio.create_task(self.update_countdown(game_message, embed, ctx.author, 30))
        
        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji)[0].isdigit() and reaction.message.id == game_message.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            choice = int(str(reaction.emoji)[0])
            # Remove the user's reaction but keep the bot's
            try:
                await game_message.remove_reaction(reaction.emoji, user)
            except Forbidden:
                # Bot lacks "Manage Messages" permission, continue without removing the reaction
                log.debug(f"Missing 'Manage Messages' permission to remove reactions in {ctx.channel.name}")
                pass
            except Exception as e:
                log.error(f"Error removing reaction: {e}")
            # Cancel countdown task once selection is made
            countdown_task.cancel()
        except (asyncio.TimeoutError, ValueError):
            # Update embed with timeout message
            embed.description = f"{ctx.author.mention} took too long to choose!"
            game_log.append(f"⏰ Timed out! Refunding {bet} coins.")
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Refund the bet amount
            await bank.deposit_credits(ctx.author, bet)
            
            # Remove user from active games
            self.active_games.pop(ctx.author.id, None)
            # Set a timeout to clear reactions after 5 minutes
            asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))
            try:
                countdown_task.cancel()
            except:
                pass
            return

        if choice not in pistols:
            # Update embed with invalid choice message
            embed.description = f"{ctx.author.mention} made an invalid choice."
            game_log.append(f"❌ Invalid choice! Refunding {bet} coins.")
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Refund the bet amount
            await bank.deposit_credits(ctx.author, bet)
            
            # Remove user from active games
            self.active_games.pop(ctx.author.id, None)
            # Set a timeout to clear reactions after 5 minutes
            asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))
            return

        chosen_pistol = pistols[choice]
        cylinder = ["empty"] * (chosen_pistol["cylinder"] - 1) + ["bullet"]
        random.shuffle(cylinder)

        reward_pool = bet // (chosen_pistol["cylinder"] - 1)
        
        # Update embed for game start
        embed = discord.Embed(
            title=f"Solo Russian Roulette - {chosen_pistol['name']}", 
            description=f"Loading the cylinder...\n\n**Only {ctx.author.display_name} can interact with this message.**"
        )
        game_log.append(f"🔫 {ctx.author.mention} chose the {chosen_pistol['name']}!")
        
        # Clear fields and add game info
        embed.clear_fields()
        embed.add_field(name="Bet", value=f"{bet} coins", inline=True)
        embed.add_field(name="Potential Reward", value=f"{reward_pool} coins per round", inline=True)
        
        # Add game log to embed
        embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
        
        # Update message with new embed
        await self.ensure_field_limits(embed)
        await game_message.edit(embed=embed)
        await game_message.clear_reactions()
        await game_message.add_reaction("🔫")
        await game_message.add_reaction("❌")

        rounds_won = 0

        while True:
            def check_react(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ["🔫", "❌"] and reaction.message.id == game_message.id

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check_react)
                
                # Remove the user's reaction but keep the bot's
                try:
                    await game_message.remove_reaction(reaction.emoji, user)
                except Forbidden:
                    # Bot lacks "Manage Messages" permission, continue without removing the reaction
                    log.debug(f"Missing 'Manage Messages' permission to remove reactions in {ctx.channel.name}")
                    pass
                except Exception as e:
                    log.error(f"Error removing reaction: {e}")
                
                if str(reaction.emoji) == "❌":
                    # Player decided to end the game and take their winnings
                    calc_total = reward_pool * rounds_won
                    winnings = calc_total + bet  # Include the original bet in winnings 
                    
                    # Credit the player based on mode
                    if is_token_mode:
                        user_data.add_tokens(winnings)
                        self.save()  # Save token changes
                    else:
                        await bank.deposit_credits(ctx.author, winnings)
                    
                    # Update the game log
                    game_log.append("")  # Blank line for separation
                    currency_type = "tokens" if is_token_mode else "credits"
                    game_log.append(f"🏆 **{ctx.author.mention} ended the game! Collected {winnings} {currency_type}.** 💰")
                    
                    # Update the embed
                    embed.description = f"Game ended. {ctx.author.mention} collected their winnings."
                    embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                    await game_message.edit(embed=embed)
                    
                    # Update leaderboard
                    self.db.update_leaderboard(ctx.guild.id, ctx.author.id, "win", bet)
                    self.save()
                    break

                # Player pulled the trigger
                outcome = cylinder.pop()
                if outcome == "bullet":
                    # Player died - no payout
                    game_log.append(f"🔴 💥 **BANG! {ctx.author.mention} pulled the trigger and lost!** 💥 🔴")
                    
                    # Update the embed
                    embed.description = f"Game over! {ctx.author.mention} lost."
                    embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                    await game_message.edit(embed=embed)
                    
                    # Update leaderboard
                    self.db.update_leaderboard(ctx.guild.id, ctx.author.id, "death", bet)
                    self.save()
                    break
                else:
                    # Player survived
                    rounds_won += 1
                    current_reward = reward_pool * rounds_won
                    game_log.append(f"🔄 Click! {ctx.author.mention} survived round {rounds_won}. Reward: {current_reward} coins.")
                    
                    # Update the embed
                    embed.description = f"Round {rounds_won} complete."
                    embed.set_field_at(1, name="Current Reward", value=f"{current_reward} coins", inline=True)
                    embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                    await game_message.edit(embed=embed)
                    
            except asyncio.TimeoutError:
                # Player took too long - treat as chickening out with winnings
                calc_total = reward_pool * rounds_won
                winnings = calc_total + bet
                
                # Credit the player with winnings
                if rounds_won > 0:
                    await bank.deposit_credits(ctx.author, winnings)
                
                # Update game log
                game_log.append(f"⏰ {ctx.author.mention} took too long to decide and chickened out!")
                if rounds_won > 0:
                    game_log.append(f"💰 Collected {winnings} coins.")
                
                # Update the embed
                embed.description = f"Game ended due to timeout."
                embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                await game_message.edit(embed=embed)
                
                # Update leaderboard
                self.db.update_leaderboard(ctx.guild.id, ctx.author.id, "chicken", bet)
                self.save()
                break
        
        # Remove user from active games
        self.active_games.pop(ctx.author.id, None)
        
        # Set a timeout to clear reactions after 5 minutes
        asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))

    async def challenge_play(self, ctx, bet: int, players: List[discord.Member]):
        """Challenge mode Russian Roulette game"""
        if not players:
            await ctx.send("You need to challenge at least one player.")
            return
            
        # Mark initiator as in a game
        self.active_games[ctx.author.id] = True
        
        # Update challenger stats
        for _ in players:
            self.db.update_leaderboard(ctx.guild.id, ctx.author.id, "challenge")
        self.save()
    
        # Check which betting mode is active
        is_token_mode = self.db.is_token_mode(ctx.guild.id)
    
        # Handle challenger's bet based on mode
        if is_token_mode:
            user_data = self.db.get_conf(ctx.guild.id).get_user(ctx.author)
            if user_data.get_token_balance() < bet:
                await ctx.send(f"⚠️ **{ctx.author.mention} DOESN'T HAVE ENOUGH TOKENS!** ⚠️ (You have {user_data.get_token_balance()})")
                self.active_games.pop(ctx.author.id, None)
                return
            # Deduct tokens
            user_data.remove_tokens(bet)
            self.save()
        else:
            # Use bank system
            try:
                await bank.withdraw_credits(ctx.author, bet)
            except ValueError:
                await ctx.send(f"⚠️ **{ctx.author.mention} DOESN'T HAVE ENOUGH CREDITS!** ⚠️")
                self.active_games.pop(ctx.author.id, None)
                return
            
        # Create a list of tagged players for the message
        player_mentions = " ".join([player.mention for player in players])
        
        # Start a game log to track events
        game_log = []
        game_log.append(f"🎮 {ctx.author.mention} has challenged {player_mentions} to Russian Roulette!")
        game_log.append(f"💰 {ctx.author.mention} placed a bet of {bet} coins.")
        
        # Create initial embed
        embed = discord.Embed(
            title="Russian Roulette Challenge",
            description=f"{ctx.author.mention} has challenged {player_mentions} to Russian Roulette!\n\nReact with ✅ to accept or ❌ to decline."
        )
        embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
        
        # Send the initial message - this message will be updated throughout the game
        game_message = await ctx.send(embed=embed)
        
        # Add reaction options
        await game_message.add_reaction("✅")
        await game_message.add_reaction("❌")
        
        # Wait for players to accept/decline
        confirmations = {}
        challenger = ctx.author
        
        for player in players:
            # Check if player is already in a game
            if player.id in self.active_games:
                game_log.append(f"❌ {player.mention} is already in another game!")
                embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
                await game_message.edit(embed=embed)
                confirmations[player] = False
                continue
                
            # Check if player has enough credits/tokens
            if is_token_mode:
                player_data = self.db.get_conf(ctx.guild.id).get_user(player)
                has_enough = player_data.get_token_balance() >= bet
                currency_type = "tokens"
                balance = player_data.get_token_balance()
            else:
                balance = await bank.get_balance(player)
                has_enough = balance >= bet
                currency_type = "credits"
                
            if not has_enough:
                game_log.append(f"❌ **{player.mention} DOESN'T HAVE ENOUGH {currency_type.upper()} FOR THE BET!** ❌ (Has {balance})")
                embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
                await game_message.edit(embed=embed)
                confirmations[player] = False
                continue
                
            def check(reaction, user):
                return user == player and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == game_message.id

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
                confirmations[player] = str(reaction.emoji) == "✅"
                
                # Remove the user's reaction but keep the bot's
                try:
                    await game_message.remove_reaction(reaction.emoji, user)
                except Forbidden:
                    # Bot lacks "Manage Messages" permission, continue without removing the reaction
                    log.debug(f"Missing 'Manage Messages' permission to remove reactions in {ctx.channel.name}")
                    pass
                except Exception as e:
                    log.error(f"Error removing reaction: {e}")
                
                # Add to game log
                if confirmations[player]:
                    # Withdraw bet from player that accepted
                    await bank.withdraw_credits(player, bet)
                    game_log.append(f"✅ {player.mention} accepted the challenge and placed a bet of {bet} coins.")
                    # Mark this player as in a game
                    self.active_games[player.id] = True
                else:
                    game_log.append(f"❌ {player.mention} declined the challenge!")
                    # Update rejection stat for the player
                    self.db.update_leaderboard(ctx.guild.id, player.id, "rejection")
                    self.save()
                
                # Update embed
                embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
                await game_message.edit(embed=embed)
                
            except asyncio.TimeoutError:
                confirmations[player] = False
                game_log.append(f"⏰ {player.mention} didn't respond in time!")
                # Count timeout as rejection
                self.db.update_leaderboard(ctx.guild.id, player.id, "rejection")
                self.save()
                embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
                await game_message.edit(embed=embed)
    
        # Create the list of accepting players
        accepting_players = [challenger] + [p for p, accepted in confirmations.items() if accepted]
        initial_player_count = len(accepting_players)  # Store initial count for pot calculation
        
        if initial_player_count < 2:
            game_log.append(f"❌ Not enough players accepted the challenge!")
            embed.description = "Challenge failed - not enough players accepted."
            embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Refund the challenger's bet
            await bank.deposit_credits(challenger, bet)
            game_log.append(f"💰 Refunded {bet} coins to {challenger.mention}.")
            embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Remove all users from active games
            self.active_games.pop(challenger.id, None)
            for player, accepted in confirmations.items():
                if accepted:
                    self.active_games.pop(player.id, None)
                    
            # Set a timeout to clear reactions after 5 minutes
            asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))
            return

        pistols = {
            1: {"name": "Colt 6-shooter", "cylinder": 6},
            2: {"name": "H&R 32 Double-action", "cylinder": 5},
            3: {"name": "Vainne's 3-and-Done", "cylinder": 3}
        }

        # Update embed for pistol selection
        embed = discord.Embed(
            title="Challenge Mode Russian Roulette",
            description=f"{challenger.mention} needs to choose a pistol:\n\nTime remaining: 30 seconds"
        )
        
        # Add pistol choices
        for num, pistol in pistols.items():
            embed.add_field(name=f"[{num}] {pistol['name']}", value=f"{pistol['cylinder']} rounds", inline=False)
            
        # Add game log
        embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
        
        # Update message
        await self.ensure_field_limits(embed)
        await game_message.edit(embed=embed)
        await game_message.clear_reactions()
        
        # Add number reactions
        for num in pistols.keys():
            await game_message.add_reaction(str(num) + "\N{COMBINING ENCLOSING KEYCAP}")

        # Create countdown task
        countdown_task = asyncio.create_task(self.update_countdown(game_message, embed, challenger, 30))
        
        def check(reaction, user):
            return user == challenger and str(reaction.emoji)[0].isdigit() and reaction.message.id == game_message.id

        try:
            reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            choice = int(str(reaction.emoji)[0])
            # Remove the user's reaction but keep the bot's
            try:
                await game_message.remove_reaction(reaction.emoji, user)
            except Forbidden:
                # Bot lacks "Manage Messages" permission, continue without removing the reaction
                log.debug(f"Missing 'Manage Messages' permission to remove reactions in {ctx.channel.name}")
                pass
            except Exception as e:
                log.error(f"Error removing reaction: {e}")
            # Cancel countdown task once selection is made
            countdown_task.cancel()
        except asyncio.TimeoutError:
            game_log.append(f"⏰ {challenger.mention} took too long to choose a pistol!")
            embed.description = "Game cancelled - host took too long to choose a pistol."
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Refund all bets
            for player in accepting_players:
                await bank.deposit_credits(player, bet)
                game_log.append(f"💰 Refunded {bet} coins to {player.mention}.")
            
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Remove all users from active games
            for player in accepting_players:
                self.active_games.pop(player.id, None)
                    
            # Set a timeout to clear reactions after 5 minutes
            asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))
            try:
                countdown_task.cancel()
            except:
                pass
            return
        except ValueError:
            game_log.append(f"❌ {challenger.mention} made an invalid choice!")
            embed.description = "Game cancelled - host made an invalid choice."
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Refund all bets
            for player in accepting_players:
                await bank.deposit_credits(player, bet)
                game_log.append(f"💰 Refunded {bet} coins to {player.mention}.")
            
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Remove all users from active games
            for player in accepting_players:
                self.active_games.pop(player.id, None)
                    
            # Set a timeout to clear reactions after 5 minutes
            asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))
            try:
                countdown_task.cancel()
            except:
                pass
            return

        if choice not in pistols:
            game_log.append(f"❌ {challenger.mention} made an invalid choice!")
            embed.description = "Game cancelled - host made an invalid choice."
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Refund all bets
            for player in accepting_players:
                await bank.deposit_credits(player, bet)
                game_log.append(f"💰 Refunded {bet} coins to {player.mention}.")
            
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Remove all users from active games
            for player in accepting_players:
                self.active_games.pop(player.id, None)
                    
            # Set a timeout to clear reactions after 5 minutes
            asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))
            return

        chosen_pistol = pistols[choice]
        cylinder_size = chosen_pistol["cylinder"]
        game_log.append(f"🔫 {challenger.mention} chose the {chosen_pistol['name']}!")
        
        # Initialize the cylinder with one bullet
        cylinder = ["empty"] * (cylinder_size - 1) + ["bullet"]
        random.shuffle(cylinder)

        current_index = random.randint(0, len(accepting_players) - 1)
        
        # Update embed for game start
        embed = discord.Embed(
            title=f"Challenge Russian Roulette - {chosen_pistol['name']}", 
            description=f"Game in progress! Players: {', '.join([p.mention for p in accepting_players])}"
        )
        
        # Calculate total pot
        total_pot = bet * initial_player_count
        
        # Clear fields and add game info
        embed.clear_fields()
        embed.add_field(name="Bet Per Player", value=f"{bet} coins", inline=True)
        embed.add_field(name="Total Pot", value=f"{total_pot} coins", inline=True)
        
        # Add game log to embed
        embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
        
        # Update message with new embed
        await self.ensure_field_limits(embed)
        await game_message.edit(embed=embed)
        await game_message.clear_reactions()
        
        # Game loop
        while len(accepting_players) > 1:
            player = accepting_players[current_index]
            
            # Update the embed for this player's turn
            embed.description = f"It's {player.mention}'s turn to pull the trigger or chicken out!\n\n**Only {player.display_name} can interact with this message.**"
            await game_message.edit(embed=embed)
            
            # Add reaction options
            await game_message.clear_reactions()
            await game_message.add_reaction("🔫")
            await game_message.add_reaction("❌")
            
            def check_player_react(reaction, user):
                return user == player and str(reaction.emoji) in ["🔫", "❌"] and reaction.message.id == game_message.id

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check_player_react)
                
                # Remove the user's reaction but keep the bot's
                try:
                    await game_message.remove_reaction(reaction.emoji, user)
                except Forbidden:
                    # Bot lacks "Manage Messages" permission, continue without removing the reaction
                    log.debug(f"Missing 'Manage Messages' permission to remove reactions in {ctx.channel.name}")
                    pass
                except Exception as e:
                    log.error(f"Error removing reaction: {e}")
                
                if str(reaction.emoji) == "❌":
                    # Player chickened out - no refund
                    game_log.append(f"🐔 {player.mention} chickened out!")
                    embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                    await game_message.edit(embed=embed)
                    
                    accepting_players.remove(player)
                    
                    # Update leaderboard
                    self.db.update_leaderboard(ctx.guild.id, player.id, "chicken")
                    self.save()
                    
                    # Remove from active games
                    self.active_games.pop(player.id, None)
                    
                    # Update current_index if needed
                    if accepting_players:
                        current_index = current_index % len(accepting_players)
                    continue
                
                # Player decided to pull the trigger
                outcome = cylinder.pop(0) # Take from the front to simplify reloading
                
                if outcome == "bullet":
                    # Player got the bullet - no refund
                    game_log.append(f"🔴 💥 **BANG! {player.mention} pulled the trigger and lost!** 💥 🔴")
                    embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                    await game_message.edit(embed=embed)
                    
                    accepting_players.remove(player)
                    
                    # Update leaderboard
                    self.db.update_leaderboard(ctx.guild.id, player.id, "death")
                    self.save()
                    
                    # Remove from active games
                    self.active_games.pop(player.id, None)
                    
                    # Reload the cylinder with a new bullet only if the game continues
                    if len(accepting_players) > 1:
                        # Add message about challenger reloading the gun
                        game_log.append(f"🔄 {challenger.mention} reloads a live round into the gun and spins the cylinder!!")
                        embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                        await game_message.edit(embed=embed)
                        
                        # Reload the cylinder with a new bullet
                        cylinder = ["empty"] * (cylinder_size - 1) + ["bullet"]
                        random.shuffle(cylinder)
                    
                    # Update current_index if needed
                    if accepting_players:
                        current_index = current_index % len(accepting_players)
                else:
                    # Player survived
                    game_log.append(f"🔄 Click! {player.mention} survived this round!")
                    embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                    await game_message.edit(embed=embed)
                    
                    # Move to next player
                    current_index = (current_index + 1) % len(accepting_players)
            
            except asyncio.TimeoutError:
                # If a player doesn't respond in time, treat as chickening out - no refund
                game_log.append(f"⏰ {player.mention} took too long to decide and chickened out!")
                embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                await game_message.edit(embed=embed)
                
                accepting_players.remove(player)
                
                # Update leaderboard
                self.db.update_leaderboard(ctx.guild.id, player.id, "chicken")
                self.save()
                
                # Remove from active games
                self.active_games.pop(player.id, None)
                
                # Update current_index if needed
                if accepting_players:
                    current_index = current_index % len(accepting_players)

        # We have a winner
        winner = accepting_players[0]
        pot = bet * initial_player_count  # Calculate pot based on initial player count
        
        # Award the pot to the winner based on mode
        if is_token_mode:
            winner_data = self.db.get_conf(ctx.guild.id).get_user(winner)
            winner_data.add_tokens(pot)
            self.save()
            currency_type = "tokens"
        else:
            await bank.deposit_credits(winner, pot)
            currency_type = "coins"

        # Add an empty line for spacing and use bold formatting with celebratory emoji
        game_log.append("")  # Blank line for separation
        game_log.append(f"💚 🏆 **{winner.mention} WINS THE POT OF {pot} {currency_type.upper()}!** 💰 💚")

        # Update final embed
        embed.description = f"Game Over! {winner.mention} has won!"
        embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
        await game_message.edit(embed=embed)
        
        # Remove winner from active games
        self.active_games.pop(winner.id, None)
        
        # Update leaderboard
        self.db.update_leaderboard(ctx.guild.id, winner.id, "win")
        self.save()
        
        # Set a timeout to clear reactions after 5 minutes
        asyncio.create_task(self.clear_reactions_after_timeout(game_message, 300))

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
