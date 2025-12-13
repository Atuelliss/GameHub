import discord
from redbot.core import commands

class HelpView(discord.ui.View):
    def __init__(self, ctx: commands.Context, cog, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.cog = cog
        self.message: discord.Message = None
        self.current_view = "main"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This is not your help menu!", ephemeral=True)
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

    def update_buttons(self, view_type: str):
        self.clear_items()
        if view_type == "main":
            self.add_item(self.capturing_button)
            self.add_item(self.info_button)
            self.add_item(self.shop_button)
            self.add_item(self.trading_button)
            self.add_item(self.events_button)
            self.add_item(self.close_button)
        else:
            self.add_item(self.back_button)
            self.add_item(self.close_button)

    @discord.ui.button(label="Capturing", style=discord.ButtonStyle.primary)
    async def capturing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Capturing Dinosaurs", color=discord.Color.blue())
        embed.description = (
            "To capture dinosaurs, simply click the blue Capture button before someone else. "
            "If successfull it will go into your inventory `[p]dcinv` and be updated in your Explorer Log `[p]dclog`! "
            "You can then sell the dino for DinoCoins `[p]dcsell <#>`, trade it, or make it your Buddy `[p]dcbuddy set <#>`!\n\n"
            "It's important to make use of a Buddy Dino, as they grant you a Buddy-Bonus to DinoCoins you gain when you sell dinos.\n\n"
            "You can also sell your Explorer Log once you have discovered ALL the Non-Event Dinosaurs. This can be done with `[p]dclog sell`."
        ).replace("[p]", self.ctx.prefix)
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Info", style=discord.ButtonStyle.primary)
    async def info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="DinoCollector Commands", color=discord.Color.green())
        embed.description = "All Commands that are available to you!"
        
        user_cmds = (
            "**dccommands** - List all available commands.\n"
            "**dcinv** - View your inventory.\n"
            "**dclog** - View your Explorer Log.\n"
            "**dcstats** - View your stats.\n"
            "**dcsell <item/all/rarity>** - Sell dinos.\n"
            "**dcbuddy set <id> / clear** - Manage your buddy dino.\n"
            "**dctrade <user> <id> [price]** - Trade dinos.\n"
            "**dclure** - Use a lure.\n"
            "**dcshop** - View the shop.\n"
            "**dcshop buy upgrade** - Buy inventory slots.\n"
            "**dcshop buy lure** - Buy a lure."
        )
        embed.add_field(name="**User Commands**", value=user_cmds, inline=False)
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Shop", style=discord.ButtonStyle.primary)
    async def shop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = self.cog.db.get_conf(self.ctx.guild)
        user_conf = conf.get_user(self.ctx.author)
        
        current_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        max_size = conf.base_inventory_size + (conf.maximum_upgrade_amount * conf.inventory_per_upgrade)
        
        embed = discord.Embed(title="DinoCollector Shop", color=discord.Color.gold())
        embed.description = (
            "The DinoCollector Shop is where you can obtain inventory upgrades and/or a Dino Lure! "
            "Both of these are purchases with DinoCoins and can be accesed using the `[p]dcshop` command.\n\n"
            f"You have **{user_conf.has_dinocoins}** DinoCoins."
        ).replace("[p]", self.ctx.prefix)
        
        if user_conf.current_inventory_upgrade_level < conf.maximum_upgrade_amount:
            embed.add_field(
                name=f"🎒 Inventory Upgrade (+{conf.inventory_per_upgrade} Slots) - {conf.price_upgrade} Coins",
                value=f"Current Size: {current_size} | Max: {max_size}\nCommand: `{self.ctx.prefix}dcshop buy upgrade`",
                inline=False
            )
        else:
            embed.add_field(
                name="🎒 Inventory Upgrade (MAXED)",
                value=f"You have reached the maximum inventory size of {max_size}!",
                inline=False
            )
            
        embed.add_field(
            name=f"🥩 Lure - {conf.price_lure} Coins",
            value=f"Instantly spawn a dino in this channel!\nCooldown: {conf.lure_cooldown // 60} minutes\nCommand: `{self.ctx.prefix}dcshop buy lure`",
            inline=False
        )
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Trading", style=discord.ButtonStyle.primary)
    async def trading_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Trading", color=discord.Color.purple())
        embed.description = (
            "Trading can be very helpful and profitable for Players(and is safe too)! "
            "You can trade a dino to another Player as a Gift, for Coins, or for one of their Dinos"
            "(use `[p]dcinv` on them to see what they've got). The other Player will need to confirm the transaction."
        ).replace("[p]", self.ctx.prefix)
        
        embed.add_field(
            name="Usage",
            value=(
                f"`{self.ctx.prefix}dctrade <user> <your_dino_id> free`\n"
                f"`{self.ctx.prefix}dctrade <user> <your_dino_id> coin <amount>`\n"
                f"`{self.ctx.prefix}dctrade <user> <your_dino_id> dino <their_dino_id>`"
            ),
            inline=False
        )
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Events", style=discord.ButtonStyle.primary)
    async def events_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Events", color=discord.Color.magenta())
        embed.description = (
            "Events in DinoCollector follow the same format as in Ark. "
            "Love Evolved, Easter, Fear Evolved, and Christmas can be enabled to allow the special creatures "
            "from those Events to spawn into the capture-pool of the game! "
            "Keep an eye out for them, as Event dinos are worth the most DinoCoins and grant the highest Buddy-Bonus!"
        )
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="Welcome to DinoCollector!", color=discord.Color.green())
        embed.description = (
            "This is an Ark-themed collection game. Dinosaurs from ASE and ASA will both spawn in user-set channels with a Capture button. "
            "Click them fast, as they will flee or others may grab them."
        )
        
        self.update_buttons("main")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.message.delete()
