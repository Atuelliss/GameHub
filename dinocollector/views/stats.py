import discord
from redbot.core import commands
from ..databases.achievements import achievement_library

class StatsView(discord.ui.View):
    def __init__(self, ctx: commands.Context, target: discord.Member, cog, stats_embed: discord.Embed):
        super().__init__(timeout=120)
        self.ctx = ctx
        self.target = target
        self.cog = cog
        self.stats_embed = stats_embed
        self.message: discord.Message = None
        
        # We define buttons as methods decorated with @discord.ui.button, 
        # so they are already in self.children.
        # However, we want to toggle between them.
        # The 'achievements_button' is added by default because of the decorator.
        # The 'back_button' is also added by default.
        # We should remove 'back_button' initially.
        
        self.remove_item(self.back_button)
        self.remove_item(self.prev_button)
        self.remove_item(self.next_button)
        
        self.ach_embeds = []
        self.current_ach_page = 0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        allowed_ids = {self.ctx.author.id}
        if self.target.id != self.ctx.author.id:
            allowed_ids.add(self.target.id)
            
        if interaction.user.id not in allowed_ids:
            await interaction.response.send_message("You cannot interact with this menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            for child in self.children:
                child.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass

    def update_ach_buttons(self):
        if self.current_ach_page == 0:
            self.prev_button.disabled = True
            self.next_button.disabled = False
        else:
            self.prev_button.disabled = False
            self.next_button.disabled = True

    @discord.ui.button(label="Achievements", emoji="🏆", style=discord.ButtonStyle.secondary)
    async def achievements_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = self.cog.db.get_conf(self.ctx.guild)
        user_conf = conf.get_user(self.target)
        
        unlocked = user_conf.achievement_log
        total_achievements = len(achievement_library)
        
        # --- Page 1: Unlocked ---
        embed_unlocked = discord.Embed(title=f"Achievements: {self.target.display_name}", color=discord.Color.gold())
        unlocked_desc = ""
        count = 0
        unlocked_ids = set()
        
        if unlocked:
            sorted_log = sorted(unlocked, key=lambda x: x["timestamp"])
            for ach in sorted_log:
                ach_id = ach["id"]
                if ach_id in achievement_library:
                    unlocked_ids.add(ach_id)
                    data = achievement_library[ach_id]
                    unlocked_desc += f"**{data['name']}**\n{data['description']}\n\n"
                    count += 1
        
        if not unlocked_desc:
            unlocked_desc = "No achievements unlocked yet!"
            
        embed_unlocked.description = f"**Unlocked: {count}/{total_achievements}**\n\n{unlocked_desc}"
        embed_unlocked.set_footer(text="Page 1/2: Unlocked Achievements")

        # --- Page 2: Locked ---
        embed_locked = discord.Embed(title=f"Achievements: {self.target.display_name}", color=discord.Color.greyple())
        locked_desc = ""
        
        for ach_id, data in achievement_library.items():
            if ach_id not in unlocked_ids:
                hint = data.get("hint", "Keep playing to unlock this achievement.")
                locked_desc += f"**???**\nHint: {hint}\n\n"
                
        if not locked_desc:
            locked_desc = "All achievements unlocked! Congratulations!"
            
        embed_locked.description = f"**Locked Achievements**\n\n{locked_desc}"
        embed_locked.set_footer(text="Page 2/2: Locked Achievements")
        
        self.ach_embeds = [embed_unlocked, embed_locked]
        self.current_ach_page = 0
        
        # Switch buttons
        self.remove_item(self.achievements_button)
        self.add_item(self.prev_button)
        self.add_item(self.back_button)
        self.add_item(self.next_button)
        
        self.update_ach_buttons()
        
        await interaction.response.edit_message(embed=self.ach_embeds[0], view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_ach_page = 0
        self.update_ach_buttons()
        await interaction.response.edit_message(embed=self.ach_embeds[0], view=self)

    @discord.ui.button(label="Back to Stats", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Switch buttons
        self.remove_item(self.prev_button)
        self.remove_item(self.back_button)
        self.remove_item(self.next_button)
        self.add_item(self.achievements_button)
        
        await interaction.response.edit_message(embed=self.stats_embed, view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_ach_page = 1
        self.update_ach_buttons()
        await interaction.response.edit_message(embed=self.ach_embeds[1], view=self)
