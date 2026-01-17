import discord
import math
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
        total_pages = len(self.ach_embeds)
        self.prev_button.disabled = self.current_ach_page == 0
        self.next_button.disabled = self.current_ach_page >= total_pages - 1

    @discord.ui.button(label="Achievements", emoji="🏆", style=discord.ButtonStyle.secondary)
    async def achievements_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = self.cog.db.get_conf(self.ctx.guild)
        user_conf = conf.get_user(self.target)
        
        unlocked_log = user_conf.achievement_log
        total_achievements = len(achievement_library)
        unlocked_ids = {ach["id"] for ach in unlocked_log if ach["id"] in achievement_library}
        unlocked_count = len(unlocked_ids)
        
        # Build combined list: unlocked first (sorted by unlock time), then locked
        achievement_entries = []
        
        # Unlocked achievements (sorted by timestamp)
        if unlocked_log:
            sorted_log = sorted(unlocked_log, key=lambda x: x["timestamp"])
            for ach in sorted_log:
                ach_id = ach["id"]
                if ach_id in achievement_library:
                    data = achievement_library[ach_id]
                    achievement_entries.append({
                        "type": "unlocked",
                        "name": data["name"],
                        "text": data["description"]
                    })
        
        # Locked achievements
        for ach_id, data in achievement_library.items():
            if ach_id not in unlocked_ids:
                hint = data.get("hint", "Keep playing to unlock this achievement.")
                achievement_entries.append({
                    "type": "locked",
                    "name": "???",
                    "text": f"Hint: {hint}"
                })
        
        # Paginate with 15 entries per page
        per_page = 15
        total_pages = max(1, math.ceil(len(achievement_entries) / per_page))
        
        self.ach_embeds = []
        for page_num in range(total_pages):
            start = page_num * per_page
            end = start + per_page
            chunk = achievement_entries[start:end]
            
            # Determine embed color based on content
            has_unlocked = any(e["type"] == "unlocked" for e in chunk)
            has_locked = any(e["type"] == "locked" for e in chunk)
            
            if has_unlocked and has_locked:
                color = discord.Color.blue()
            elif has_unlocked:
                color = discord.Color.gold()
            else:
                color = discord.Color.greyple()
            
            embed = discord.Embed(
                title=f"🏆 Achievements: {self.target.display_name}",
                color=color
            )
            
            description = f"**Progress: {unlocked_count}/{total_achievements}**\n\n"
            
            for entry in chunk:
                if entry["type"] == "unlocked":
                    description += f"✅ **{entry['name']}**\n{entry['text']}\n\n"
                else:
                    description += f"🔒 **{entry['name']}**\n{entry['text']}\n\n"
            
            embed.description = description
            embed.set_footer(text=f"Page {page_num + 1}/{total_pages}")
            self.ach_embeds.append(embed)
        
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
        if self.current_ach_page > 0:
            self.current_ach_page -= 1
        self.update_ach_buttons()
        await interaction.response.edit_message(embed=self.ach_embeds[self.current_ach_page], view=self)

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
        if self.current_ach_page < len(self.ach_embeds) - 1:
            self.current_ach_page += 1
        self.update_ach_buttons()
        await interaction.response.edit_message(embed=self.ach_embeds[self.current_ach_page], view=self)
