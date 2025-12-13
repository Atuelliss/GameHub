from ..abc import MixinMeta
from redbot.core import commands
import discord
import time
from ..databases.gameinfo import select_random_creature
from ..views import SpawnView

class Shop(MixinMeta):
    
    @commands.group(invoke_without_command=True)
    async def dcshop(self, ctx: commands.Context):
        """DinoCollector Shop. Buy upgrades and items!"""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        # Calculate current inventory size dynamically
        current_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        max_size = conf.base_inventory_size + (conf.maximum_upgrade_amount * conf.inventory_per_upgrade)
        
        embed = discord.Embed(title="🦖 DinoCollector Shop", color=discord.Color.gold())
        embed.description = f"You have **{user_conf.has_dinocoins}** DinoCoins."
        
        # Item 1: Inventory Upgrade
        if user_conf.current_inventory_upgrade_level < conf.maximum_upgrade_amount:
            embed.add_field(
                name=f"🎒 Inventory Upgrade (+{conf.inventory_per_upgrade} Slots) - {conf.price_upgrade} Coins",
                value=f"Current Size: {current_size} | Max: {max_size}\nCommand: `{ctx.prefix}dcshop buy upgrade`",
                inline=False
            )
        else:
            embed.add_field(
                name="🎒 Inventory Upgrade (MAXED)",
                value=f"You have reached the maximum inventory size of {max_size}!",
                inline=False
            )
            
        # Item 2: Lure
        embed.add_field(
            name=f"🥩 Lure - {conf.price_lure} Coins",
            value=f"Instantly spawn a dino in this channel!\nCooldown: {conf.lure_cooldown // 60} minutes\nCommand: `{ctx.prefix}dcshop buy lure`",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @dcshop.group(name="buy", invoke_without_command=True)
    async def dcshop_buy(self, ctx: commands.Context):
        """Buy items from the shop."""
        await ctx.send_help(ctx.command)

    @dcshop_buy.command(name="upgrade")
    async def buy_upgrade(self, ctx: commands.Context):
        """Buy an inventory upgrade."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        # Check Max
        if user_conf.current_inventory_upgrade_level >= conf.maximum_upgrade_amount:
            max_size = conf.base_inventory_size + (conf.maximum_upgrade_amount * conf.inventory_per_upgrade)
            await ctx.send(f"You have already reached the maximum inventory size ({max_size})!")
            return
            
        # Check Funds
        price = conf.price_upgrade
        if user_conf.has_dinocoins < price:
            await ctx.send(f"You need **{price}** DinoCoins to buy this upgrade. You have {user_conf.has_dinocoins}.")
            return
            
        # Process Purchase
        user_conf.has_dinocoins -= price
        user_conf.has_spent_dinocoins += price
        user_conf.current_inventory_upgrade_level += 1
        
        # Calculate new size for display
        new_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        
        self.save()
        
        await ctx.send(f"🎉 Upgrade successful! Your inventory size is now **{new_size}**. Remaining coins: {user_conf.has_dinocoins}")

        # Achievements
        await self.check_achievement(user_conf, "first_upgrade", ctx)
        if user_conf.current_inventory_upgrade_level >= conf.maximum_upgrade_amount:
            await self.check_achievement(user_conf, "max_upgrade", ctx)

    @dcshop_buy.command(name="lure")
    async def buy_lure(self, ctx: commands.Context):
        """Buy a lure to spawn a dino later."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        # Check if already has lure
        if user_conf.has_lure:
            await ctx.send("You already have a lure! Use it with `dclure` before buying another.")
            return

        # Check Funds
        price = conf.price_lure
        if user_conf.has_dinocoins < price:
            await ctx.send(f"You need **{price}** DinoCoins to buy a lure. You have {user_conf.has_dinocoins}.")
            return
            
        # Process Purchase
        user_conf.has_dinocoins -= price
        user_conf.has_spent_dinocoins += price
        user_conf.has_lure = True
        
        self.save()
        
        await ctx.send(f"🥩 You bought a lure! Use it with `{ctx.prefix}dclure` to spawn a dino.")
        
        # Achievements
        await self.check_achievement(user_conf, "first_lure_purchase", ctx)
        
        await ctx.send(f"🥩 You bought a lure for **{price}** coins! Use `{ctx.prefix}dclure` to use it.")
