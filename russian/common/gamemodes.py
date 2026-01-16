import asyncio
import random
import discord
import logging
from typing import List, Optional
from discord.errors import Forbidden
from redbot.core import bank

from ..abc import MixinMeta
from .gameviewclasses import SoloGameView, ChallengeGameView, PistolSelectionView, ChallengeAcceptView

log = logging.getLogger("red.rroulette")

class GameModes(MixinMeta):
    """Game mode implementations for Russian Roulette"""
    
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
            description=f"{ctx.author.mention} needs to choose a pistol:"
        )
        for num, pistol in pistols.items():
            embed.add_field(name=f"[{num}] {pistol['name']}", value=f"{pistol['cylinder']} rounds", inline=False)
        
        embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
        
        # Create and display the pistol selection view
        pistol_view = PistolSelectionView(ctx, pistols)
        pistol_message = await ctx.send(embed=embed, view=pistol_view)
        pistol_view.message = pistol_message
        
        # Wait for pistol selection
        await pistol_view.wait()
        
        # If no pistol was selected (timeout or closed)
        if pistol_view.selected_pistol is None:
            # Update embed with timeout message
            embed.description = f"{ctx.author.mention} took too long to choose!"
            game_log.append(f"⏰ Timed out! Refunding {bet} coins.")
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await pistol_message.edit(embed=embed, view=None)
            
            # Refund the bet amount based on betting mode
            if is_token_mode:
                user_data.add_tokens(bet)
                self.save()
            else:
                await bank.deposit_credits(ctx.author, bet)
            
            # Remove user from active games
            self.active_games.pop(ctx.author.id, None)
            return

        choice = pistol_view.selected_pistol
        if choice not in pistols:
            # Update embed with invalid choice message
            embed.description = f"{ctx.author.mention} made an invalid choice."
            game_log.append(f"❌ Invalid choice! Refunding {bet} coins.")
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await pistol_message.edit(embed=embed, view=None)
            
            # Refund the bet amount based on betting mode
            if is_token_mode:
                user_data.add_tokens(bet)
                self.save()
            else:
                await bank.deposit_credits(ctx.author, bet)
            
            # Remove user from active games
            self.active_games.pop(ctx.author.id, None)
            return

        chosen_pistol = pistols[choice]
        # Create cylinder with one bullet and the rest empty chambers
        cylinder = ["empty"] * (chosen_pistol["cylinder"] - 1) + ["bullet"]
        # Log before shuffling to verify bullet is added
        log.debug(f"Cylinder before shuffle: {cylinder}")
        random.shuffle(cylinder)
        # Log after shuffling to verify randomization
        log.debug(f"Cylinder after shuffle: {cylinder}")

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
        
        # Create the Solo Game View
        solo_view = SoloGameView(ctx, self, bet, cylinder, reward_pool)
        await pistol_message.edit(embed=embed, view=solo_view)
        solo_view.message = pistol_message
        
        # Wait for the game to complete
        await solo_view.wait()
        
        # Process the game result
        if solo_view.result == "win":
            # Player won/stopped - Pay out winnings
            if is_token_mode:
                user_data.add_tokens(solo_view.winnings)
                self.save()
            else:
                await bank.deposit_credits(ctx.author, solo_view.winnings)
            
            # Update leaderboard
            self.db.update_leaderboard(ctx.guild.id, ctx.author.id, "win", bet)
        elif solo_view.result == "death":
            # Player lost
            self.db.update_leaderboard(ctx.guild.id, ctx.author.id, "death", bet)
        else:
            # Player chickened out or game timed out
            self.db.update_leaderboard(ctx.guild.id, ctx.author.id, "chicken", bet)
            # If they won any rounds, we need to pay out
            if solo_view.winnings > 0:
                if is_token_mode:
                    user_data.add_tokens(solo_view.winnings)
                    self.save()
                else:
                    await bank.deposit_credits(ctx.author, solo_view.winnings)
        
        # Save changes to database
        self.save()
            
        # Remove user from active games
        self.active_games.pop(ctx.author.id, None)

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
        
        # Send the initial message
        game_message = await ctx.send(embed=embed)
        
        # Wait for players to accept/decline using views
        confirmations = {}
        challenger = ctx.author
        accepting_players = [challenger]  # Challenger is automatically included
        
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
            
            # Create a challenge acceptance view for this player
            accept_view = ChallengeAcceptView(ctx, player)
            player_embed = discord.Embed(
                title="Russian Roulette Challenge",
                description=f"{challenger.mention} has challenged you to Russian Roulette with a bet of {bet} {currency_type}!\n\n"
                            f"Do you accept?",
                color=discord.Color.red()
            )
            player_embed.set_footer(text="This challenge will expire in 60 seconds")
            
            # Send the challenge view to the player
            accept_message = await ctx.send(content=player.mention, embed=player_embed, view=accept_view)
            accept_view.message = accept_message
            
            # Wait for player response
            await accept_view.wait()
            
            # Process player's response
            if accept_view.accepted:
                confirmations[player] = True
                # Deduct bet from player that accepted
                if is_token_mode:
                    player_data = self.db.get_conf(ctx.guild.id).get_user(player)
                    player_data.remove_tokens(bet)
                    self.save()
                else:
                    await bank.withdraw_credits(player, bet)
                
                game_log.append(f"✅ {player.mention} accepted the challenge and placed a bet of {bet} coins.")
                # Add player to accepting players list
                accepting_players.append(player)
                # Mark this player as in a game
                self.active_games[player.id] = True
            else:
                confirmations[player] = False
                game_log.append(f"❌ {player.mention} declined the challenge!")
                # Update rejection stat for the player
                self.db.update_leaderboard(ctx.guild.id, player.id, "rejection")
                self.save()
            
            # Update main embed
            embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Clean up the acceptance message
            try:
                await accept_message.delete()
            except:
                pass
    
        # Store initial player count for pot calculation
        initial_player_count = len(accepting_players)
        
        if initial_player_count < 2:
            game_log.append(f"❌ Not enough players accepted the challenge!")
            embed.description = "Challenge failed - not enough players accepted."
            embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Refund the challenger's bet based on betting mode
            if is_token_mode:
                user_data = self.db.get_conf(ctx.guild.id).get_user(challenger)
                user_data.add_tokens(bet)
                self.save()
            else:
                await bank.deposit_credits(challenger, bet)
                
            game_log.append(f"💰 Refunded {bet} coins to {challenger.mention}.")
            embed.set_field_at(0, name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Remove all users from active games
            for player in accepting_players:
                self.active_games.pop(player.id, None)
            return

        pistols = {
            1: {"name": "Colt 6-shooter", "cylinder": 6},
            2: {"name": "H&R 32 Double-action", "cylinder": 5},
            3: {"name": "Vainne's 3-and-Done", "cylinder": 3}
        }

        # Update embed for pistol selection
        embed = discord.Embed(
            title="Challenge Mode Russian Roulette",
            description=f"{challenger.mention} needs to choose a pistol:"
        )
        
        # Add pistol choices
        for num, pistol in pistols.items():
            embed.add_field(name=f"[{num}] {pistol['name']}", value=f"{pistol['cylinder']} rounds", inline=False)
            
        # Add game log
        embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
        
        # Create pistol selection view for challenger
        pistol_view = PistolSelectionView(ctx, pistols)
        await game_message.edit(embed=embed, view=pistol_view)
        pistol_view.message = game_message
        
        # Wait for pistol selection
        await pistol_view.wait()
        
        # Handle pistol selection result
        if pistol_view.selected_pistol is None:
            game_log.append(f"⏰ {challenger.mention} took too long to choose a pistol!")
            embed.description = "Game cancelled - host took too long to choose a pistol."
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed, view=None)
            
            # Refund all bets
            for player in accepting_players:
                if player == challenger:
                    if is_token_mode:
                        user_data = self.db.get_conf(ctx.guild.id).get_user(player)
                        user_data.add_tokens(bet)
                        self.save()
                    else:
                        await bank.deposit_credits(player, bet)
                else:
                    if is_token_mode:
                        player_data = self.db.get_conf(ctx.guild.id).get_user(player)
                        player_data.add_tokens(bet)
                        self.save()
                    else:
                        await bank.deposit_credits(player, bet)
                game_log.append(f"💰 Refunded {bet} coins to {player.mention}.")
            
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Remove all users from active games
            for player in accepting_players:
                self.active_games.pop(player.id, None)
            return

        choice = pistol_view.selected_pistol
        if choice not in pistols:
            game_log.append(f"❌ {challenger.mention} made an invalid choice!")
            embed.description = "Game cancelled - invalid pistol selection."
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed, view=None)
            
            # Refund all bets
            for player in accepting_players:
                if is_token_mode:
                    player_data = self.db.get_conf(ctx.guild.id).get_user(player)
                    player_data.add_tokens(bet)
                    self.save()
                else:
                    await bank.deposit_credits(player, bet)
                game_log.append(f"💰 Refunded {bet} coins to {player.mention}.")
            
            embed.set_field_at(len(pistols), name="Game Log", value="\n".join(game_log), inline=False)
            await game_message.edit(embed=embed)
            
            # Remove all users from active games
            for player in accepting_players:
                self.active_games.pop(player.id, None)
            return

        chosen_pistol = pistols[choice]
        cylinder_size = chosen_pistol["cylinder"]
        game_log.append(f"🔫 {challenger.mention} chose the {chosen_pistol['name']}!")
        
        # Initialize the cylinder with one bullet
        cylinder = ["empty"] * (cylinder_size - 1) + ["bullet"]
        random.shuffle(cylinder)

        # Randomly select starting player
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
        
        # Create Challenge Game View
        game_view = ChallengeGameView(ctx, self, accepting_players, current_index, cylinder, bet)
        await game_message.edit(embed=embed, view=game_view)
        game_view.message = game_message
        
        # Start the countdown for the initial player
        game_view.start_countdown()
        
        # Game loop - process rounds until we have a winner or the game ends
        # We'll keep a master game log here to ensure all messages are preserved
        master_game_log = game_log.copy()
        
        while len(accepting_players) > 1:
            # Wait for a player to take their turn
            await game_view.wait()
            
            # Process the result of this turn
            if game_view.result is None:
                # View closed without result (shouldn't happen normally)
                break
                
            elif game_view.result == "death":
                # Player died
                eliminated_player = game_view.eliminated_player
                accepting_players.remove(eliminated_player)
                
                # Update leaderboard
                self.db.update_leaderboard(ctx.guild.id, eliminated_player.id, "death")
                self.save()
                
                # Remove from active games
                self.active_games.pop(eliminated_player.id, None)
                
                # If we have more than 1 player left, set up for next round
                if len(accepting_players) > 1:
                    try:
                        # Get game log from message with safety checks
                        updated_embed = game_view.message.embeds[0]
                        
                        # Extract current game log from the embed
                        game_log_field_index = -1
                        for i, field in enumerate(updated_embed.fields):
                            if field.name == "Game Log":
                                game_log_field_index = i
                                break
                        
                        if game_log_field_index >= 0:
                            current_log = updated_embed.fields[game_log_field_index].value.split('\n')
                            # Update master log with any new entries
                            for entry in current_log:
                                if entry not in master_game_log:
                                    master_game_log.append(entry)
                        
                        # Add message about challenger reloading the gun
                        master_game_log.append(f"🔄 {challenger.mention} reloads a live round into the gun and spins the cylinder!!")
                        
                        # Use the master game log for consistency
                        if game_log_field_index >= 0:
                            updated_embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(master_game_log), inline=False)
                        else:
                            updated_embed.add_field(name="Game Log", value="\n".join(master_game_log), inline=False)
                        
                        # Reload the cylinder with a new bullet
                        new_cylinder = ["empty"] * (cylinder_size - 1) + ["bullet"]
                        random.shuffle(new_cylinder)
                        
                        # Update current_index if needed
                        current_index = current_index % len(accepting_players)
                        
                        # Create a new game view for the next round
                        game_view = ChallengeGameView(ctx, self, accepting_players, current_index, new_cylinder, bet)
                        await game_message.edit(embed=updated_embed, view=game_view)
                        game_view.message = game_message
                        game_view.start_countdown()
                        
                    except Exception as e:
                        log.error(f"Error updating game after player death: {e}")
                        # Create a new embed as a fallback
                        new_embed = discord.Embed(
                            title=f"Challenge Russian Roulette", 
                            description=f"Game in progress! Players: {', '.join([p.mention for p in accepting_players])}\n\n"
                                       f"🔄 {challenger.mention} reloads a live round into the gun and spins the cylinder!!"
                        )
                        new_embed.add_field(name="Bet Per Player", value=f"{bet} coins", inline=True)
                        new_embed.add_field(name="Total Pot", value=f"{bet * initial_player_count} coins", inline=True)
                        new_embed.add_field(name="Game Log", value="\n".join(master_game_log), inline=False)
                        
                        # Create a new game view for the next round
                        new_cylinder = ["empty"] * (cylinder_size - 1) + ["bullet"]
                        random.shuffle(new_cylinder)
                        current_index = current_index % len(accepting_players)
                        game_view = ChallengeGameView(ctx, self, accepting_players, current_index, new_cylinder, bet)
                        await game_message.edit(embed=new_embed, view=game_view)
                        game_view.message = game_message
                        game_view.start_countdown()
            
            elif game_view.result == "chicken":
                # Player chickened out or timed out
                eliminated_player = game_view.eliminated_player
                accepting_players.remove(eliminated_player)
                
                # If this was from a timeout, add the timeout message to master log
                if hasattr(game_view, 'timeout_message'):
                    master_game_log.append(game_view.timeout_message)
                
                # Update leaderboard
                self.db.update_leaderboard(ctx.guild.id, eliminated_player.id, "chicken")
                self.save()
                
                # Remove from active games
                self.active_games.pop(eliminated_player.id, None)
                
                # If we have more than 1 player left, set up for next round
                if len(accepting_players) > 1:
                    try:
                        # Extract current game log from the message
                        updated_embed = game_view.message.embeds[0]
                        
                        # Find game log field
                        game_log_field_index = -1
                        for i, field in enumerate(updated_embed.fields):
                            if field.name == "Game Log":
                                game_log_field_index = i
                                break
                        
                        if game_log_field_index >= 0:
                            current_log = updated_embed.fields[game_log_field_index].value.split('\n')
                            # Update master log with any new entries
                            for entry in current_log:
                                if entry not in master_game_log:
                                    master_game_log.append(entry)
                        
                        # Update current_index
                        current_index = current_index % len(accepting_players)
                        
                        # Create a new game view for the next player
                        new_view = ChallengeGameView(ctx, self, accepting_players, current_index, cylinder, bet)
                        
                        # Use the master game log for consistency
                        if game_log_field_index >= 0:
                            updated_embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(master_game_log), inline=False)
                            await game_message.edit(embed=updated_embed, view=new_view)
                        else:
                            # Create a basic embed with essential info if we couldn't find the Game Log
                            basic_embed = discord.Embed(
                                title="Challenge Russian Roulette",
                                description=f"Game continues with {len(accepting_players)} players.\n\n" +
                                           f"It's {accepting_players[current_index].mention}'s turn!"
                            )
                            basic_embed.add_field(name="Bet Per Player", value=f"{bet} coins", inline=True)
                            basic_embed.add_field(name="Total Pot", value=f"{bet * initial_player_count} coins", inline=True)
                            basic_embed.add_field(name="Game Log", value="\n".join(master_game_log), inline=False)
                            
                            await game_message.edit(embed=basic_embed, view=new_view)
                        
                        new_view.message = game_message
                        game_view = new_view
                        game_view.start_countdown()
                        
                    except Exception as e:
                        log.error(f"Error updating game after player chickened out: {e}")
                        # Create a new simple embed as a fallback
                        simple_embed = discord.Embed(
                            title="Challenge Russian Roulette",
                            description=f"Game continues with {len(accepting_players)} players.\n\n" +
                                       f"It's {accepting_players[current_index].mention}'s turn!"
                        )
                        simple_embed.add_field(name="Bet Per Player", value=f"{bet} coins", inline=True)
                        simple_embed.add_field(name="Total Pot", value=f"{bet * initial_player_count} coins", inline=True)
                        simple_embed.add_field(name="Game Log", value="\n".join(master_game_log), inline=False)
                        
                        # Create a new view as a fallback
                        current_index = current_index % len(accepting_players)
                        new_view = ChallengeGameView(ctx, self, accepting_players, current_index, cylinder, bet)
                        await game_message.edit(embed=simple_embed, view=new_view)
                        new_view.message = game_message
                        game_view = new_view
                        game_view.start_countdown()

        # We have a winner or the game ended unexpectedly
        if len(accepting_players) == 1:
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

            # Get updated embed and game log
            updated_embed = game_message.embeds[0]
            
            # Find the Game Log field by name rather than assuming position
            game_log_field_index = -1
            game_log_text = ""
            
            for i, field in enumerate(updated_embed.fields):
                if field.name == "Game Log":
                    game_log_text = field.value
                    game_log_field_index = i
                    break
            
            # If we didn't find the Game Log field, create a new one with basic info
            if game_log_field_index == -1:
                game_log = ["Game log was lost, but we have a winner!"]
            else:
                game_log = game_log_text.split('\n')

            # Add an empty line for spacing and use bold formatting with celebratory emoji
            game_log.append("")  # Blank line for separation
            game_log.append(f"💚 🏆 **{winner.mention} WINS THE POT OF {pot} {currency_type.upper()}!** 💰 💚")

            # Update final embed
            updated_embed.description = f"Game Over! {winner.mention} has won!"
            
            # Update or add the game log field
            if game_log_field_index >= 0:
                updated_embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(game_log), inline=False)
            else:
                updated_embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
                
            await game_message.edit(embed=updated_embed, view=None)
            
            # Remove winner from active games
            self.active_games.pop(winner.id, None)
            
            # Update leaderboard
            self.db.update_leaderboard(ctx.guild.id, winner.id, "win")
            self.save()

        else:
            # Game ended unexpectedly (everyone left/timed out)
            try:
                updated_embed = game_message.embeds[0]
                
                # Find the Game Log field by name rather than assuming position
                game_log_field_index = -1
                game_log_text = ""
                
                for i, field in enumerate(updated_embed.fields):
                    if field.name == "Game Log":
                        game_log_text = field.value
                        game_log_field_index = i
                        break
                
                # If we didn't find the Game Log field, create a new one
                if game_log_field_index == -1:
                    game_log = ["Game ended unexpectedly - no winner."]
                else:
                    game_log = game_log_text.split('\n')
                    game_log.append("❌ Game ended unexpectedly - no winner.")
                
                updated_embed.description = "Game ended without a winner."
                
                # Update or add the game log field
                if game_log_field_index >= 0:
                    updated_embed.set_field_at(game_log_field_index, name="Game Log", value="\n".join(game_log), inline=False)
                else:
                    updated_embed.add_field(name="Game Log", value="\n".join(game_log), inline=False)
                    
                await game_message.edit(embed=updated_embed, view=None)
            except Exception as e:
                log.error(f"Error updating final game state: {e}")
                # Try a simple update if detailed update fails
                try:
                    simple_embed = discord.Embed(
                        title="Challenge Russian Roulette",
                        description="Game ended without a winner.",
                        color=discord.Color.red()
                    )
                    await game_message.edit(embed=simple_embed, view=None)
                except:
                    pass
            
            # Remove any remaining players from active games
            for player in accepting_players:
                self.active_games.pop(player.id, None)
