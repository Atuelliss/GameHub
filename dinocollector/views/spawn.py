import discord
import time
import random
import asyncio
from ..databases.creatures import creature_library

class SpawnView(discord.ui.View):
    def __init__(self, cog, creature_data):
        super().__init__(timeout=90) # 1 minute 30 seconds
        self.cog = cog
        self.creature_data = creature_data
        self.message: discord.Message = None
        self.clicks: dict[int, int] = {}
        self.captured = False

    @discord.ui.button(label="Capture", style=discord.ButtonStyle.primary)
    async def capture_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.captured:
            await interaction.response.send_message("This creature has already been captured!", ephemeral=True)
            return

        conf = self.cog.db.get_conf(interaction.guild)

        # Check Blacklist
        if interaction.user.id in conf.blacklisted_users:
            await interaction.response.send_message("You are blacklisted from using DinoCollector!", ephemeral=True)
            return

        # Check Inventory Capacity
        user_conf = conf.get_user(interaction.user)
        
        current_inv_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        
        if len(user_conf.current_dino_inv) >= current_inv_size:
            await interaction.response.send_message(
                f"Your inventory is full ({len(user_conf.current_dino_inv)}/{current_inv_size})! Sell some dinos to make space.", 
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        self.clicks[user_id] = self.clicks.get(user_id, 0) + 1
        clicks_needed = 1
        current_clicks = self.clicks[user_id]

        if current_clicks < clicks_needed:
            # Acknowledge the click silently (updates the view state but changes nothing visible)
            await interaction.response.edit_message(view=self)
        else:
            # Defer the interaction to prevent timeout
            await interaction.response.defer()

            # Re-check captured state to prevent race conditions
            if self.captured:
                await interaction.followup.send("This creature has already been captured!", ephemeral=True)
                return

            # Check for failure chance
            fail_chance = conf.spawn_fail_chance
            if random.randint(1, 100) <= fail_chance:
                # Escaped!
                self.captured = True
                # self.stop() # Don't stop, let timeout handle cleanup
                
                # Update stats
                user_conf.total_escaped += 1
                self.cog.save()
                
                # Escaped achievement
                if user_conf.total_escaped >= 10:
                    await self.cog.check_achievement(user_conf, "escaped_10", interaction)
                
                # Always show fled message
                embed = self.message.embeds[0]
                embed.title = f"The {self.creature_data['name']} has fled!!"
                embed.color = discord.Color.red()
                embed.clear_fields()
                embed.set_footer(text=f"It fled from {interaction.user.display_name}!")
                
                # Disable button but keep view attached so timeout runs
                button.disabled = True
                button.label = "Escaped"
                button.style = discord.ButtonStyle.danger
                
                await interaction.message.edit(embed=embed, view=self)
                return

            # Captured!
            self.captured = True
            self.stop() 
            
            # Disable button
            button.disabled = True
            button.label = "Captured"
            button.style = discord.ButtonStyle.success
            
            # Add to inventory
            # (conf and user_conf already fetched above)
            
            # Update Inventory
            user_conf.current_dino_inv.append(self.creature_data)
            
            # Update Explorer Log (Pokedex)
            species_name = self.creature_data["name"]
            already_in_log = any(d.get("name") == species_name for d in user_conf.explorer_log)
            
            if not already_in_log:
                user_conf.explorer_log.append({"name": species_name})
                user_conf.explorer_log.sort(key=lambda x: x["name"])
            
            # Update Stats
            user_conf.total_ever_claimed += 1
            
            # Update First Catch Info
            if not user_conf.first_dino_ever_caught:
                user_conf.first_dino_ever_caught = self.creature_data["name"]
                user_conf.first_dino_caught_timestamp = str(time.time())
                
            self.cog.save()
            
            # Always show captured message
            embed = self.message.embeds[0]
            embed.set_footer(text=f"Captured by {interaction.user.display_name}!")
            embed.color = discord.Color.green()
            
            await interaction.message.edit(embed=embed, view=self)

            # Achievements
            await self.cog.check_achievement(user_conf, "first_capture", interaction)
            
            modifier = self.creature_data.get("modifier", "").lower()
            if modifier == "corrupted":
                await self.cog.check_achievement(user_conf, "first_corrupted", interaction)
            elif modifier == "shiny":
                await self.cog.check_achievement(user_conf, "first_shiny", interaction)
            elif modifier == "aberrant":
                await self.cog.check_achievement(user_conf, "first_aberrant", interaction)
            elif modifier == "muscular":
                await self.cog.check_achievement(user_conf, "first_muscular", interaction)
            elif modifier == "sickly":
                await self.cog.check_achievement(user_conf, "first_sickly", interaction)
            elif modifier == "withered":
                await self.cog.check_achievement(user_conf, "first_withered", interaction)
            elif modifier == "young":
                await self.cog.check_achievement(user_conf, "first_young", interaction)
            elif modifier == "irradiated":
                await self.cog.check_achievement(user_conf, "first_irradiated", interaction)
            
            # Rarity achievements
            rarity = self.creature_data.get("rarity", "").lower()
            if rarity == "legendary":
                user_conf.total_legendary_caught += 1
                await self.cog.check_achievement(user_conf, "first_legendary", interaction)
                if user_conf.total_legendary_caught >= 5:
                    await self.cog.check_achievement(user_conf, "catch_5_legendary", interaction)
            elif rarity == "super_rare":
                await self.cog.check_achievement(user_conf, "first_super_rare", interaction)
            elif rarity == "event":
                await self.cog.check_achievement(user_conf, "first_event", interaction)
            
            # Catch milestone achievements
            if user_conf.total_ever_claimed >= 10:
                await self.cog.check_achievement(user_conf, "catch_10", interaction)
            if user_conf.total_ever_claimed >= 50:
                await self.cog.check_achievement(user_conf, "catch_50", interaction)
            if user_conf.total_ever_claimed >= 100:
                await self.cog.check_achievement(user_conf, "catch_100", interaction)
            if user_conf.total_ever_claimed >= 500:
                await self.cog.check_achievement(user_conf, "catch_500", interaction)
            if user_conf.total_ever_claimed >= 1000:
                await self.cog.check_achievement(user_conf, "catch_1000", interaction)
            
            # Explorer log percentage achievements
            total_species = len(creature_library)
            caught_species = len(user_conf.explorer_log)
            if total_species > 0:
                percentage = (caught_species / total_species) * 100
                if percentage >= 25:
                    await self.cog.check_achievement(user_conf, "log_25_percent", interaction)
                if percentage >= 50:
                    await self.cog.check_achievement(user_conf, "log_50_percent", interaction)
                if percentage >= 75:
                    await self.cog.check_achievement(user_conf, "log_75_percent", interaction)
                if percentage >= 100:
                    await self.cog.check_achievement(user_conf, "log_100_percent", interaction)
                
            # Check full inventory
            current_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
            if len(user_conf.current_dino_inv) >= current_size:
                await self.cog.check_achievement(user_conf, "full_inventory", interaction)

            # Schedule cleanup if enabled
            if conf.message_cleanup_enabled:
                asyncio.create_task(self.delayed_cleanup(interaction.message))

    async def delayed_cleanup(self, message):
        await asyncio.sleep(60)
        try:
            conf = self.cog.db.get_conf(message.guild)
            if conf.message_cleanup_enabled:
                await message.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

    async def on_timeout(self):
        await asyncio.sleep(30)
        if self.message:
            conf = self.cog.db.get_conf(self.message.guild)
            
            # If cleanup is enabled, delete regardless of state
            if conf.message_cleanup_enabled:
                try:
                    await self.message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                return

            # If cleanup disabled, handle "Too Slow" case
            if not self.captured:
                # Update the message
                embed = self.message.embeds[0]
                embed.title = f"The {self.creature_data['name']} has fled!!"
                embed.color = discord.Color.red()
                embed.clear_fields()
                embed.set_footer(text="Too slow!")
                
                try:
                    await self.message.edit(embed=embed, view=None)
                except discord.NotFound:
                    pass # Message was deleted
                except discord.HTTPException:
                    pass
