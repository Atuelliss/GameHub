import discord

class SetupView(discord.ui.View):
    def __init__(self, ctx, timeout=60):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.action = None
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your setup session.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.message:
            try:
                for child in self.children:
                    child.disabled = True
                await self.message.edit(view=self)
            except:
                pass
        self.stop()

    def add_button(self, label, style, custom_id):
        button = discord.ui.Button(label=label, style=style, custom_id=custom_id)
        
        async def callback(interaction: discord.Interaction):
            self.action = custom_id
            self.stop()
            await interaction.response.defer()
            
        button.callback = callback
        self.add_item(button)
