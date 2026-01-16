import discord
import logging
import random
import asyncio
from typing import List, Optional

log = logging.getLogger("red.rroulette")

class SoloGameView(discord.ui.View):
    def __init__(self, ctx, cog, bet, cylinder, reward_pool, rounds_won=0, timeout=180):
        super().__init__(timeout=timeout)  # 3 minute timeout
        self.ctx = ctx
        self.cog = cog
        self.bet = bet
        self.cylinder = cylinder
        log.debug(f"Cylinder initialized for {ctx.author.name}: {self.cylinder}")  # Debug log to check cylinder contents
        self.reward_pool = reward_pool
        self.rounds_won = rounds_won
        self.message = None
        self.result = None
        self.winnings = 0
        self.cylinder_size = len(cylinder)  # Store the original cylinder size

    async def interaction_check(self, interaction):
        # Only allow the player who started the game to interact
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True
        
    def disable_all_items(self):
        """Helper method to disable all buttons in the view"""
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="Pull Trigger", style=discord.ButtonStyle.danger)
    async def pull_trigger(self, interaction, button):
        # Get game log
        embed = interaction.message.embeds[0]
        game_log = embed.fields[2].value.split('\n')
        
        # Check if the cylinder is empty
        if not self.cylinder:
            # If cylinder is empty, the player has survived all rounds
            # Tell them they need to stop playing
            await interaction.response.send_message(
                "The cylinder is empty! You've survived all rounds and must collect your winnings.",
                ephemeral=True
            )
            return
        
        # Debug log current cylinder state before pulling trigger
        log.debug(f"Current cylinder state for {self.ctx.author.name} before pull: {self.cylinder}")
            
        # Pull from the cylinder (from the front to match challenge mode)
        outcome = self.cylinder.pop(0)  # Changed from pop() to pop(0) for consistency
        
        # Debug log what was pulled and remaining cylinder
        log.debug(f"Pulled: {outcome}, Remaining cylinder: {self.cylinder}")
        
        if outcome == "bullet":
            # Player got the bullet - no payout
            game_log.append(f"🔴 💥 **BANG! {self.ctx.author.mention} pulled the trigger and lost!** 💥 🔴")
            
            # Update embed
            embed.description = f"Game over! {self.ctx.author.mention} lost."
            embed.set_field_at(1, name="Current Reward", value="Lost", inline=True)
            embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
            
            # Disable all buttons
            self.disable_all_items()
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Set result for processing after view closes
            self.result = "death"
            self.stop()
        else:
            # Player survived
            self.rounds_won += 1
            current_reward = self.reward_pool * self.rounds_won
            game_log.append(f"🔄 Click! {self.ctx.author.mention} survived round {self.rounds_won}. Reward: {current_reward} coins.")
            
            # Update the embed
            embed.description = f"Round {self.rounds_won} complete."
            embed.set_field_at(1, name="Current Reward", value=f"{current_reward} coins", inline=True)
            embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
            
            # If this was the last empty chamber, auto-disable the pull trigger button
            # and force the player to take their winnings
            if not self.cylinder:
                game_log.append(f"🎯 The cylinder is empty! {self.ctx.author.mention} survived all chambers!")
                embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
                
                # Modify button to show it's disabled
                button.disabled = True
                button.label = "No More Rounds"
            
            await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Stop Playing", style=discord.ButtonStyle.secondary)
    async def stop_playing(self, interaction, button):
        # Player chose to cash out (but only if they've won at least one round)
        if self.rounds_won == 0:
            await interaction.response.send_message("You need to pull the trigger at least once!", ephemeral=True)
            return
            
        # Calculate winnings
        calc_total = self.reward_pool * self.rounds_won
        self.winnings = calc_total + self.bet  # Include the original bet in winnings
        
        # Get game log
        embed = interaction.message.embeds[0]
        game_log = embed.fields[2].value.split('\n')
        
        # Add empty line for separation
        game_log.append("")  
        
        # Update the game log
        game_log.append(f"🏆 **{self.ctx.author.mention} ended the game! Collected {self.winnings} credits.** 💰")
        
        # Update the embed
        embed.description = f"Game ended. {self.ctx.author.mention} collected their winnings."
        embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
        
        # Disable all buttons
        self.disable_all_items()
        await interaction.response.edit_message(embed=embed, view=self)
        
        # Set result for processing after view closes
        self.result = "win"
        self.stop()
    
    async def on_timeout(self):
        """Handle what happens when the view times out after 3 minutes"""
        try:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            # Update embed to show timeout
            message = await self.message.fetch()
            embed = message.embeds[0]
            game_log = embed.fields[2].value.split('\n')
            game_log.append(f"⏰ Game timed out after 3 minutes of inactivity!")
            embed.set_field_at(2, name="Game Log", value="\n".join(game_log), inline=False)
            
            # Update the message with disabled buttons
            await self.message.edit(embed=embed, view=self)
            
            # Handle timeout same as stopping - player keeps what they've won
            if self.rounds_won > 0:
                self.result = "win"
                self.winnings = self.reward_pool * self.rounds_won + self.bet
            else:
                self.result = "chicken"
        except Exception as e:
            log.error(f"Error handling game timeout: {e}")

class ChallengeGameView(discord.ui.View):
    def __init__(self, ctx, cog, players, current_index, cylinder, bet, timeout=60.0):  # Changed timeout to 60 seconds
        super().__init__(timeout=timeout)  # 60 second timeout for each turn
        self.ctx = ctx
        self.cog = cog
        self.players = players
        self.current_index = current_index
        self.cylinder = cylinder
        self.bet = bet
        self.message = None
        self.result = None
        self.eliminated_player = None
        self.countdown_task = None
        
    def disable_all_items(self):
        """Helper method to disable all buttons in the view"""
        for item in self.children:
            item.disabled = True
            
    def start_countdown(self):
        """Start the countdown timer display in the embed"""
        if self.countdown_task:
            self.countdown_task.cancel()
        self.countdown_task = asyncio.create_task(self.update_countdown())
            
    async def update_countdown(self):
        """Updates the countdown display in the embed"""
        try:
            current_player = self.players[self.current_index]
            start_time = asyncio.get_event_loop().time()
            end_time = start_time + self.timeout
            
            while True:
                # Calculate remaining time
                now = asyncio.get_event_loop().time()
                remaining = max(0, int(end_time - now))
                
                # Every 10 seconds, update the embed
                if remaining % 10 == 0 or remaining <= 5:
                    try:
                        embed = self.message.embeds[0]
                        # Find description and update it
                        if "seconds remaining" not in embed.description:
                            embed.description = (f"{embed.description}\n\n"
                                              f"⏱️ {remaining} seconds remaining for {current_player.mention}")
                        else:
                            # Replace the countdown part
                            desc_parts = embed.description.split("\n\n⏱️")
                            embed.description = (f"{desc_parts[0]}\n\n"
                                              f"⏱️ {remaining} seconds remaining for {current_player.mention}")
                        
                        await self.message.edit(embed=embed)
                    except Exception as e:
                        log.error(f"Error updating countdown: {e}")
                        break
                
                # Stop when time is up
                if remaining <= 0:
                    break
                    
                # Sleep for a second before checking again
                await asyncio.sleep(1)
                
        except asyncio.CancelledError:
            # Task was cancelled - stop the countdown
            pass
        except Exception as e:
            log.error(f"Error in countdown timer: {e}")

    async def interaction_check(self, interaction):
        current_player = self.players[self.current_index]
        if interaction.user != current_player:
            await interaction.response.send_message(
                f"It's {current_player.display_name}'s turn!", 
                ephemeral=True
            )
            return False
        
        # Cancel the countdown if we receive valid interaction
        if self.countdown_task and not self.countdown_task.done():
            self.countdown_task.cancel()
            
        return True

    @discord.ui.button(label="Pull Trigger", style=discord.ButtonStyle.danger)
    async def pull_trigger(self, interaction, button):
        # Get current player
        current_player = self.players[self.current_index]
        
        # Get game log from embed with safety checks
        embed = interaction.message.embeds[0]
        
        # Find the Game Log field by name rather than position
        game_log_field_index = -1
        for i, field in enumerate(embed.fields):
            if field.name == "Game Log":
                game_log_field_index = i
                break
        
        # If we didn't find the Game Log field, create one with basic info
        if game_log_field_index == -1:
            game_log = []
            embed.add_field(name="Game Log", value="Game log started.", inline=False)
            game_log_field_index = len(embed.fields) - 1
        else:
            game_log = embed.fields[game_log_field_index].value.split('\n')
        
        # Pull from cylinder
        outcome = self.cylinder.pop(0)  # Take from front to simplify reloading
        
        if outcome == "bullet":
            # Player got the bullet and is eliminated
            game_log.append(f"🔴 💥 **BANG! {current_player.mention} pulled the trigger and lost!** 💥 🔴")
            
            # Update embed
            embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(game_log), inline=False)
            await interaction.response.edit_message(embed=embed)
            
            # Set result for processing after view closes
            self.result = "death"
            self.eliminated_player = current_player
            self.stop()
        else:
            # Player survived, move to next player
            game_log.append(f"🔄 Click! {current_player.mention} survived this round!")
            
            # Move to next player
            self.current_index = (self.current_index + 1) % len(self.players)
            next_player = self.players[self.current_index]
            
            # Update embed
            embed.description = f"It's {next_player.mention}'s turn to pull the trigger or chicken out!\n\n**Only {next_player.display_name} can interact with this message.**"
            embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(game_log), inline=False)
            await interaction.response.edit_message(embed=embed, view=self)

            # After a successful button press, immediately start the countdown for the next player
            if outcome == "empty":
                # Start countdown for the next player after UI updates
                self.start_countdown()

    @discord.ui.button(label="Chicken Out", style=discord.ButtonStyle.secondary)
    async def chicken_out(self, interaction, button):
        # Get current player
        current_player = self.players[self.current_index]
        
        # Get game log from embed with safety checks
        embed = interaction.message.embeds[0]
        
        # Find the Game Log field by name rather than position
        game_log_field_index = -1
        for i, field in enumerate(embed.fields):
            if field.name == "Game Log":
                game_log_field_index = i
                break
        
        # If we didn't find the Game Log field, create one with basic info
        if game_log_field_index == -1:
            game_log = []
            embed.add_field(name="Game Log", value="Game log started.", inline=False)
            game_log_field_index = len(embed.fields) - 1
        else:
            game_log = embed.fields[game_log_field_index].value.split('\n')
        
        # Player chickened out
        game_log.append(f"🐔 {current_player.mention} chickened out!")
        
        # Update embed
        embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(game_log), inline=False)
        await interaction.response.edit_message(embed=embed)
        
        # Set result for processing after view closes
        self.result = "chicken"
        self.eliminated_player = current_player
        self.stop()
    
    async def on_timeout(self):
        """Handle what happens when the view times out after the countdown"""
        try:
            # Get the current player who timed out
            current_player = self.players[self.current_index]
            
            # Update embed to show timeout
            try:
                message = await self.message.fetch()
                embed = message.embeds[0]
                
                # Find the Game Log field
                game_log_field_index = -1
                for i, field in enumerate(embed.fields):
                    if field.name == "Game Log":
                        game_log_field_index = i
                        break
                
                if game_log_field_index >= 0:
                    game_log = embed.fields[game_log_field_index].value.split('\n')
                    timeout_message = f"⏰ {current_player.mention} took too long to decide and forfeited!"
                    game_log.append(timeout_message)
                    embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(game_log), inline=False)
                
                # Update the message but don't disable buttons yet, since we'll rebuild the view if needed
                await self.message.edit(embed=embed)
                
                # Store the timeout message in a class attribute so it can be retrieved by the game loop
                self.timeout_message = timeout_message
            except Exception as e:
                log.error(f"Error updating embed on timeout: {e}")
                self.timeout_message = f"⏰ {current_player.mention} took too long to decide and forfeited!"
            
            # Mark player as eliminated (same as chicken out)
            self.result = "chicken"
            self.eliminated_player = current_player
            
            # Stop the view - this will signal back to the challenge_play method
            self.stop()
            
        except Exception as e:
            log.error(f"Error handling game timeout: {e}")

class PistolSelectionView(discord.ui.View):
    """View for selecting a pistol at the start of the game"""
    def __init__(self, ctx, pistols, timeout=30.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.pistols = pistols
        self.selected_pistol = None
        self.message = None
        
        # Create buttons for each pistol with simplified labels
        for num, pistol in pistols.items():
            # Extract the number of shots from the pistol data
            shots = pistol["cylinder"]
            
            # Create button with new concise format
            button = discord.ui.Button(
                label=f"[{num}] {shots}-Shot",
                style=discord.ButtonStyle.primary,
                custom_id=f"pistol_{num}"
            )
            button.callback = self.make_callback(num)
            self.add_item(button)
            
    def make_callback(self, num):
        async def button_callback(interaction):
            # Only allow the player who started the game to interact
            if interaction.user != self.ctx.author:
                await interaction.response.send_message("This isn't your game!", ephemeral=True)
                return
                
            self.selected_pistol = num
            await interaction.response.defer()
            self.stop()
        return button_callback
        
    async def on_timeout(self):
        """Handle what happens when the view times out"""
        try:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
                
            if self.message:
                await self.message.edit(view=self)
        except Exception as e:
            log.error(f"Error handling pistol selection timeout: {e}")

class ChallengeAcceptView(discord.ui.View):
    """View for accepting or rejecting a challenge"""
    def __init__(self, ctx, target_player, timeout=60.0):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.target_player = target_player
        self.message = None
        self.accepted = None
        
    def disable_all_items(self):
        """Helper method to disable all buttons in the view"""
        for item in self.children:
            item.disabled = True

    async def interaction_check(self, interaction):
        # Only allow the challenged player to interact
        if interaction.user != self.target_player:
            await interaction.response.send_message(
                f"Only {self.target_player.display_name} can respond to this challenge!", 
                ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction, button):
        self.accepted = True
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction, button):
        self.accepted = False
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.stop()
    
    async def on_timeout(self):
        """Handle what happens when the view times out"""
        try:
            # Disable all buttons
            for item in self.children:
                item.disabled = True
            
            if self.message:
                await self.message.edit(view=self)
            
            self.accepted = False
        except Exception as e:
            log.error(f"Error handling challenge acceptance timeout: {e}")