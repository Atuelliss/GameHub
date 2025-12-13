import discord

class TradeView(discord.ui.View):
    def __init__(self, sender: discord.User, recipient: discord.User):
        super().__init__(timeout=120)
        self.sender = sender
        self.recipient = recipient
        self.confirmed = False
        self.message: discord.Message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.recipient.id:
            return True
        if interaction.user.id == self.sender.id:
            # Sender can only cancel
            if interaction.data.get("custom_id") == "trade_cancel":
                return True
            await interaction.response.send_message("You cannot accept your own trade request!", ephemeral=True)
            return False
            
        await interaction.response.send_message("This trade is not for you!", ephemeral=True)
        return False

    @discord.ui.button(label="Accept Trade", style=discord.ButtonStyle.green, custom_id="trade_accept")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.recipient.id:
             await interaction.response.send_message("Only the recipient can accept the trade.", ephemeral=True)
             return
        self.confirmed = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="Decline/Cancel", style=discord.ButtonStyle.red, custom_id="trade_cancel")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
