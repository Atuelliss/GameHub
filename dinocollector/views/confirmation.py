import discord

class ConfirmationView(discord.ui.View):
    def __init__(self, author: discord.User, timeout: int = 60):
        super().__init__(timeout=timeout)
        self.author = author
        self.confirmed = False
        self.message: discord.Message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This is not your confirmation!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer() # Acknowledge, but let the command handle the rest

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()

    async def on_timeout(self):
        if self.message:
            # Disable buttons on timeout
            for child in self.children:
                child.disabled = True
            try:
                await self.message.edit(view=self)
            except:
                pass
