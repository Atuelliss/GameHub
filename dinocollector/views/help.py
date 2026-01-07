import discord
from redbot.core import commands
from ..databases.gameinfo import rarity_chances, buddy_bonuses, all_modifiers, type_normal_mod, type_rare_mod, type_special_mod
from ..databases.constants import common_value, uncommon_value, semi_rare_value, rare_value, very_rare_value, super_rare_value, legendary_value, event_value
from ..databases.creatures import creature_library


class HelpView(discord.ui.View):
    def __init__(self, ctx: commands.Context, cog, timeout: int = 120):
        super().__init__(timeout=timeout)
        self.ctx = ctx
        self.cog = cog
        self.message: discord.Message = None
        self.current_view = "main"
        
        # Dynamic rarity data mapping
        self.rarity_values = {
            "common": common_value,
            "uncommon": uncommon_value,
            "semi_rare": semi_rare_value,
            "rare": rare_value,
            "very_rare": very_rare_value,
            "super_rare": super_rare_value,
            "legendary": legendary_value,
            "event": event_value
        }
        
        # Rarity display names and emojis
        self.rarity_display = {
            "common": ("Common", "⚪"),
            "uncommon": ("Uncommon", "🟢"),
            "semi_rare": ("Semi-Rare", "🔵"),
            "rare": ("Rare", "🟣"),
            "very_rare": ("Very Rare", "🟠"),
            "super_rare": ("Super Rare", "🔴"),
            "legendary": ("Legendary", "🟡"),
            "event": ("Event", "🎃")
        }

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
            # Row 0 - Primary topic buttons
            self.capturing_button.row = 0
            self.buddy_button.row = 0
            self.rarity_button.row = 0
            self.stats_button.row = 0
            self.add_item(self.capturing_button)
            self.add_item(self.buddy_button)
            self.add_item(self.rarity_button)
            self.add_item(self.stats_button)
            # Row 1 - Secondary topic buttons
            self.shop_button.row = 1
            self.trading_button.row = 1
            self.events_button.row = 1
            self.commands_button.row = 1
            self.add_item(self.shop_button)
            self.add_item(self.trading_button)
            self.add_item(self.events_button)
            self.add_item(self.commands_button)
            # Row 2 - Close button
            self.close_button.row = 2
            self.add_item(self.close_button)
        else:
            # Sub-view navigation
            self.back_button.row = 0
            self.close_button.row = 0
            self.add_item(self.back_button)
            self.add_item(self.close_button)

    def get_main_embed(self) -> discord.Embed:
        """Generate the main help embed."""
        # Count total creatures dynamically
        total_creatures = len(creature_library)
        non_event_creatures = len([c for c in creature_library.values() if c.get("version") != "event" and c.get("version") not in ["valentines", "easter", "halloween", "christmas"]])
        
        embed = discord.Embed(title="🦖 Welcome to DinoCollector!", color=discord.Color.green())
        embed.description = (
            "This is an Ark-themed collection game! Dinosaurs from ASE and ASA will spawn in designated channels "
            "with a Capture button. Click fast - they will flee or others may grab them!\n\n"
            f"**{total_creatures}** unique dinosaurs to discover ({non_event_creatures} standard + event exclusives)\n\n"
            "Use the buttons below to learn more about the game!"
        )
        embed.set_footer(text="Select a topic to learn more")
        return embed

    @discord.ui.button(label="🦖 Capturing", style=discord.ButtonStyle.primary)
    async def capturing_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = self.cog.db.get_conf(self.ctx.guild)
        
        embed = discord.Embed(title="🦖 Capturing Dinosaurs", color=discord.Color.blue())
        embed.description = (
            "Dinosaurs spawn randomly in enabled channels. When one appears, "
            "you'll see a **Capture** button - click it before anyone else!\n\n"
            "**What happens when you capture:**\n"
            "• The dino goes into your **Inventory** (`[p]dcinv`)\n"
            "• It's recorded in your **Explorer Log** (`[p]dclog`)\n"
            "• You can sell it, trade it, or set it as your Buddy!\n\n"
            "**Spawn Settings:**\n"
            f"• Capture Timeout: **90** seconds before dino flees\n"
            f"• Base Inventory Size: **{conf.base_inventory_size}** slots"
        ).replace("[p]", self.ctx.prefix)
        
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Be quick! Others are competing for the same dino\n"
                "• Rarer dinos are worth more DinoCoins\n"
                "• Use a Buddy to earn bonus coins when selling"
            ),
            inline=False
        )
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🐾 Buddy System", style=discord.ButtonStyle.primary)
    async def buddy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🐾 Buddy System", color=discord.Color.teal())
        embed.description = (
            "Set one of your captured dinos as your **Buddy** to earn bonus DinoCoins "
            "whenever you sell other dinosaurs!\n\n"
            "**Commands:**\n"
            f"• `{self.ctx.prefix}dcbuddy set <inventory_id>` - Set a buddy\n"
            f"• `{self.ctx.prefix}dcbuddy name <name>` - Name your buddy\n"
            f"• `{self.ctx.prefix}dcbuddy clear` - Remove your buddy\n"
            f"• `{self.ctx.prefix}dcbuddy` - View your current buddy"
        )
        
        # Build buddy bonus table dynamically
        bonus_text = ""
        for rarity_key in ["common", "uncommon", "semi_rare", "rare", "very_rare", "super_rare", "legendary", "event"]:
            display_name, emoji = self.rarity_display.get(rarity_key, (rarity_key.title(), "⚪"))
            bonus = buddy_bonuses.get(rarity_key, 0)
            bonus_text += f"{emoji} **{display_name}**: +{bonus}%\n"
        
        embed.add_field(
            name="📈 Buddy Bonus by Rarity",
            value=bonus_text,
            inline=False
        )
        
        embed.set_footer(text="Higher rarity buddies = more bonus coins!")
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⭐ Rarity Guide", style=discord.ButtonStyle.primary)
    async def rarity_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="⭐ Rarity Guide", color=discord.Color.gold())
        embed.description = "Dinosaurs come in different rarities. Rarer dinos are harder to find but worth more!"
        
        # Build rarity table dynamically
        rarity_text = ""
        for rarity_key in ["common", "uncommon", "semi_rare", "rare", "very_rare", "super_rare", "legendary", "event"]:
            display_name, emoji = self.rarity_display.get(rarity_key, (rarity_key.title(), "⚪"))
            chance = rarity_chances.get(rarity_key, 0)
            values = self.rarity_values.get(rarity_key, [0, 0])
            rarity_text += f"{emoji} **{display_name}**: {chance}% spawn | {values[0]}-{values[1]} coins\n"
        
        embed.add_field(
            name="📊 Spawn Chances & Values",
            value=rarity_text,
            inline=False
        )
        
        # Build modifier table dynamically
        normal_mods = ", ".join([f"{k} ({'+' if v >= 0 else ''}{v})" for k, v in type_normal_mod.items()])
        rare_mods = ", ".join([f"{k} ({'+' if v >= 0 else ''}{v})" for k, v in type_rare_mod.items()])
        special_mods = ", ".join([f"{k} ({'+' if v >= 0 else ''}{v})" for k, v in type_special_mod.items()])
        
        embed.add_field(
            name="✨ Dino Modifiers",
            value=(
                f"**Normal (70%):** {normal_mods}\n"
                f"**Rare (20%):** {rare_mods}\n"
                f"**Special (10%):** {special_mods}\n\n"
                "*Modifiers adjust the final coin value when selling!*"
            ),
            inline=False
        )
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📊 Stats & Progress", style=discord.ButtonStyle.primary)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = self.cog.db.get_conf(self.ctx.guild)
        
        # Count creatures dynamically
        total_creatures = len(creature_library)
        non_event_creatures = len([c for c in creature_library.values() if c.get("version") not in ["event", "valentines", "easter", "halloween", "christmas"]])
        
        embed = discord.Embed(title="📊 Stats & Progress", color=discord.Color.blue())
        embed.description = (
            "Track your dinosaur collection journey with these features!"
        )
        
        embed.add_field(
            name="📖 Explorer Log",
            value=(
                f"Your personal Dino-dex! Tracks every unique species you've discovered.\n"
                f"• **{non_event_creatures}** standard dinos to discover\n"
                f"• Complete the log to unlock the ability to **sell it** for a huge reward!\n"
                f"• Command: `{self.ctx.prefix}dclog`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎒 Inventory",
            value=(
                f"Your captured dinos waiting to be sold or traded.\n"
                f"• Base size: **{conf.base_inventory_size}** slots\n"
                f"• Upgradeable by **{conf.inventory_per_upgrade}** slots (max {conf.maximum_upgrade_amount} upgrades)\n"
                f"• Command: `{self.ctx.prefix}dcinv`"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📈 Your Stats",
            value=(
                f"View your personal statistics including:\n"
                f"• Total dinos captured\n"
                f"• DinoCoins earned\n"
                f"• Current buddy and more!\n"
                f"• Command: `{self.ctx.prefix}dcstats`"
            ),
            inline=False
        )
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="💰 Shop", style=discord.ButtonStyle.success)
    async def shop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = self.cog.db.get_conf(self.ctx.guild)
        user_conf = conf.get_user(self.ctx.author)
        
        current_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        max_size = conf.base_inventory_size + (conf.maximum_upgrade_amount * conf.inventory_per_upgrade)
        
        embed = discord.Embed(title="💰 DinoCollector Shop", color=discord.Color.gold())
        embed.description = (
            f"Spend your hard-earned DinoCoins on upgrades and items!\n\n"
            f"**Your Balance:** 🪙 **{user_conf.has_dinocoins}** DinoCoins\n"
            f"Command: `{self.ctx.prefix}dcshop`"
        )
        
        if user_conf.current_inventory_upgrade_level < conf.maximum_upgrade_amount:
            upgrade_status = f"Current: {current_size} → Next: {current_size + conf.inventory_per_upgrade} (Max: {max_size})"
            embed.add_field(
                name=f"🎒 Inventory Upgrade - {conf.price_upgrade} Coins",
                value=f"+{conf.inventory_per_upgrade} inventory slots\n{upgrade_status}\n`{self.ctx.prefix}dcshop buy upgrade`",
                inline=False
            )
        else:
            embed.add_field(
                name="🎒 Inventory Upgrade (MAXED OUT!)",
                value=f"You've reached the maximum inventory size of **{max_size}** slots!",
                inline=False
            )
        
        # Format cooldown nicely
        cooldown_mins = conf.lure_cooldown // 60
        cooldown_display = f"{cooldown_mins} minute{'s' if cooldown_mins != 1 else ''}"
        
        embed.add_field(
            name=f"🥩 Dino Lure - {conf.price_lure} Coins",
            value=f"Instantly spawn a random dino in the current channel!\nCooldown: {cooldown_display}\n`{self.ctx.prefix}dcshop buy lure`",
            inline=False
        )
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🤝 Trading", style=discord.ButtonStyle.success)
    async def trading_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🤝 Trading", color=discord.Color.purple())
        embed.description = (
            "Trade dinosaurs with other players safely! All trades require confirmation from both parties.\n\n"
            f"**View someone's inventory:** `{self.ctx.prefix}dcinv @user`"
        )
        
        embed.add_field(
            name="🎁 Gift Trade (Free)",
            value=f"`{self.ctx.prefix}dctrade @user <your_dino_id> free`\nGive a dino as a gift!",
            inline=False
        )
        
        embed.add_field(
            name="🪙 Coin Trade",
            value=f"`{self.ctx.prefix}dctrade @user <your_dino_id> coin <amount>`\nSell your dino for DinoCoins!",
            inline=False
        )
        
        embed.add_field(
            name="🦕 Dino Swap",
            value=f"`{self.ctx.prefix}dctrade @user <your_dino_id> dino <their_dino_id>`\nSwap dinos with another player!",
            inline=False
        )
        
        embed.set_footer(text="The other player must confirm all trades")
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🎃 Events", style=discord.ButtonStyle.success)
    async def events_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        conf = self.cog.db.get_conf(self.ctx.guild)
        
        # Get event creature counts dynamically
        event_types = {
            "valentines": ("💕 Love Evolved", 0),
            "easter": ("🐰 Easter", 0),
            "halloween": ("🎃 Fear Evolved", 0),
            "christmas": ("🎄 Winter Wonderland", 0)
        }
        
        for creature in creature_library.values():
            version = creature.get("version", "")
            if version in event_types:
                name, count = event_types[version]
                event_types[version] = (name, count + 1)
        
        # Check current event status
        current_event = conf.event_mode if hasattr(conf, 'event_mode') and conf.event_mode else None
        
        embed = discord.Embed(title="🎃 Seasonal Events", color=discord.Color.magenta())
        embed.description = (
            "DinoCollector features seasonal events inspired by Ark! "
            "When an event is active, special event-exclusive dinosaurs can spawn.\n\n"
            "**Event dinos are the rarest and most valuable!**"
        )
        
        # Show event values dynamically
        event_vals = self.rarity_values.get("event", [0, 0])
        event_bonus = buddy_bonuses.get("event", 0)
        
        embed.add_field(
            name="✨ Event Dino Stats",
            value=(
                f"• **Value:** {event_vals[0]}-{event_vals[1]} DinoCoins\n"
                f"• **Buddy Bonus:** +{event_bonus}%\n"
                f"• **Spawn Chance:** {rarity_chances.get('event', 0)}% (when event active)"
            ),
            inline=False
        )
        
        # List all events with creature counts
        events_list = ""
        for event_key, (event_name, count) in event_types.items():
            events_list += f"{event_name}: **{count}** exclusive dinos\n"
        
        embed.add_field(
            name="📅 Available Events",
            value=events_list if events_list else "No event creatures configured",
            inline=False
        )
        
        if current_event:
            embed.add_field(
                name="🔔 Current Event",
                value=f"**{current_event.title()}** is currently active!",
                inline=False
            )
        else:
            embed.set_footer(text="Keep an eye out for event announcements!")
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="📜 Commands", style=discord.ButtonStyle.secondary)
    async def commands_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.ctx.prefix
        
        embed = discord.Embed(title="📜 Command Reference", color=discord.Color.greyple())
        embed.description = "Quick reference for all player commands!"
        
        basic_cmds = (
            f"`{p}dchelp` - This help menu\n"
            f"`{p}dcinv [user]` - View inventory\n"
            f"`{p}dclog` - View Explorer Log\n"
            f"`{p}dcstats [user]` - View stats\n"
            f"`{p}dcleaderboard` - Server leaderboard"
        )
        embed.add_field(name="📋 Basic Commands", value=basic_cmds, inline=False)
        
        dino_cmds = (
            f"`{p}dcsell <id>` - Sell a specific dino\n"
            f"`{p}dcsell all` - Sell all dinos\n"
            f"`{p}dcsell <rarity>` - Sell all of a rarity\n"
            f"`{p}dclog sell` - Sell completed log"
        )
        embed.add_field(name="💵 Selling", value=dino_cmds, inline=True)
        
        buddy_cmds = (
            f"`{p}dcbuddy` - View buddy\n"
            f"`{p}dcbuddy set <id>` - Set buddy\n"
            f"`{p}dcbuddy name <name>` - Name buddy\n"
            f"`{p}dcbuddy clear` - Clear buddy"
        )
        embed.add_field(name="🐾 Buddy", value=buddy_cmds, inline=True)
        
        trade_cmds = (
            f"`{p}dctrade @user <id> free`\n"
            f"`{p}dctrade @user <id> coin <amt>`\n"
            f"`{p}dctrade @user <id> dino <id>`"
        )
        embed.add_field(name="🤝 Trading", value=trade_cmds, inline=False)
        
        shop_cmds = (
            f"`{p}dcshop` - View shop\n"
            f"`{p}dcshop buy upgrade` - Buy slots\n"
            f"`{p}dcshop buy lure` - Buy lure\n"
            f"`{p}dclure` - Use a lure"
        )
        embed.add_field(name="🛒 Shop & Lures", value=shop_cmds, inline=True)
        
        self.update_buttons("sub")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="◀ Back", style=discord.ButtonStyle.secondary)
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = self.get_main_embed()
        self.update_buttons("main")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="✖", style=discord.ButtonStyle.danger)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.stop()
        await interaction.message.delete()
