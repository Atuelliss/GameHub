import discord

class PaginationView(discord.ui.View):
    def __init__(self, pages: list[discord.Embed], author: discord.User, timeout: float = 60.0):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author = author
        self.current_page = 0
        self.message: discord.Message = None
        self.update_buttons()

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass

    def update_buttons(self):
        self.previous_page.disabled = self.current_page == 0
        self.next_page.disabled = self.current_page == len(self.pages) - 1

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You cannot interact with this menu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="⬅️", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @discord.ui.button(label="X", style=discord.ButtonStyle.danger)
    async def close_view(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        self.stop()

    @discord.ui.button(emoji="➡️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
