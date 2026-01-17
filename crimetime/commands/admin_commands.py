"""
CrimeTime Admin Commands

Admin-only commands for configuring user data and initiating events.
"""
import discord
from redbot.core import commands


async def is_admin_or_owner(ctx: commands.Context) -> bool:
    """Check if user can use admin commands.
    
    Returns True if the user:
    - Is the bot owner, OR
    - Has manage_guild permission, OR
    - Is a Red-DiscordBot admin
    """
    if not ctx.guild:
        return False
    
    # Bot owner check
    if await ctx.bot.is_owner(ctx.author):
        return True
    
    # Red-DiscordBot admin check
    if await ctx.bot.is_admin(ctx.author):
        return True
    
    # manage_guild permission check
    return ctx.author.guild_permissions.manage_guild


class AdminCommands:
    """Mixin class for CrimeTime admin commands."""

    # This group allows the Administrator to SET the users stats to specified amounts.
    @commands.group()
    @commands.check(is_admin_or_owner)
    async def ctset(self, ctx: commands.Context):
        """Configure CrimeTime User Data"""

    @ctset.command(name="view")  # View a Users info.
    async def view_player(self, ctx: commands.Context, target: discord.Member):
        """Checks the total info of a User."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_exp = target_user.player_exp
        target_level = target_user.player_level
        await ctx.send(f"-=-=-=-=-=-=-=-=-=-=-\n**{target.display_name}**\n-=-=-=-=-=-=-=-=-=-=-\nLevel - {target_level}\nExp    - {target_exp}")

    @ctset.command(name="balance")  # Set a User's Cash Balance to a specific number.
    async def set_player_balance(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's Cash Balance to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative balance!")
            return
        target_user.balance = amount
        await ctx.send(f"**{target.display_name}**'s Balance have been set to {amount}.")
        self.save()

    @ctset.command(name="bars")  # Set a User's Gold Bar Count to a specific number.
    async def set_player_bars(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's Gold Bar count to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative balance!")
            return
        target_user.gold_bars = amount
        await ctx.send(f"**{target.display_name}**'s Gold Bars have been set to {amount}.")
        self.save()
    
    @ctset.command(name="gems")  # Set a User's Gem Count to a specific number.
    async def set_player_gems(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's Gems count to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative balance!")
            return
        target_user.gems_owned = amount
        await ctx.send(f"**{target.display_name}**'s Gem count has been set to {amount}.")
        self.save()
    
    @ctset.command(name="pwin")  # Set a User's PvP wins.
    async def set_player_pwin(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's PvP Wins to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative amount!")
            return
        target_user.p_wins = amount
        await ctx.send(f"**{target.display_name}**'s PvP Mug Wins have been set to {amount}.")
        self.save()
    
    @ctset.command(name="ploss")  # Set a User's PvP losses.
    async def set_player_ploss(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's PvP Losses to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative amount!")
            return
        target_user.p_losses = amount
        await ctx.send(f"**{target.display_name}**'s PvP Mug Losses have been set to {amount}.")
        self.save()

    @ctset.command(name="rwin")  # Set a User's Rob wins.
    async def set_player_rwin(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's Robbery Wins to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative amount!")
            return
        target_user.r_wins = amount
        await ctx.send(f"**{target.display_name}**'s Robbery wins have been set to {amount}.")
        self.save()
    
    @ctset.command(name="rloss")  # Set a User's Rob losses.
    async def set_player_rloss(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's Robbery loss to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative amount!")
            return
        target_user.r_losses = amount
        await ctx.send(f"**{target.display_name}**'s Robbery losses have been set to {amount}.")
        self.save()

    @ctset.command(name="hwin")  # Set a User's Heist wins.
    async def set_player_hwin(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's Heist Wins to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative amount!")
            return
        target_user.h_wins = amount
        await ctx.send(f"**{target.display_name}**'s Heist wins have been set to {amount}.")
        self.save()
    
    @ctset.command(name="hloss")  # Set a User's Heist losses.
    async def set_player_hloss(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Set a User's Heist loss to specified amount."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        if amount < 0:
            await ctx.send("You cannot set a negative amount!")
            return
        target_user.h_losses = amount
        await ctx.send(f"**{target.display_name}**'s Heist losses have been set to {amount}.")
        self.save()

    @ctset.command(name="goldvalue")
    async def set_gold_value(self, ctx: commands.Context, amount: int):
        """Set the global gold bar value in the economy."""
        if amount <= 0:
            await ctx.send("You cannot set a negative or zero value for gold bars!")
            return
        self.db.bar_value = amount
        await ctx.send(f"Global Gold bar value has been set to ${amount}.")
        self.save()
    
    @ctset.command(name="gemvalue")
    async def set_gem_value(self, ctx: commands.Context, amount: int):
        """Set the global gem value in the economy."""
        if amount <= 0:
            await ctx.send("You cannot set a negative or zero value for gems!")
            return
        self.db.gem_value = amount
        await ctx.send(f"Global Gem value has been set to ${amount}.")
        self.save()

    @ctset.command(name="conversionvalue")
    async def set_conversion_value(self, ctx: commands.Context, amount: int):
        """Set the value gems are worth when converting to the Discord Currency."""
        if amount <= 0:
            await ctx.send("You cannot set a negative or zero value.")
            return
        self.db.gem_conversion_value = amount
        await ctx.send(f"Gem value to discord Currency has been set to {amount}.")
        self.save()

    @ctset.command(name="conversion")
    async def enable_bank_conversion(self, ctx: commands.Context, toggle: str):
        """Enable or disable bank conversion.
        
        Use "on" to enable or "off" to disable.
        """
        # Validate input
        toggle = toggle.lower()
        if toggle not in ["on", "off"]:
            await ctx.send("Invalid option. Please use 'on' or 'off'.")
            return
        
        # Set the value
        self.db.bank_conversion_enabled = (toggle == "on")
        
        # Save and inform
        await ctx.send(f"Bank conversion has been {'enabled' if toggle == 'on' else 'disabled'}.")
        self.save()

    # Admin-Initiated Events
    @commands.group(invoke_without_command=True)
    @commands.check(is_admin_or_owner)
    async def ctevent(self, ctx: commands.Context):
        """Ability for Admins to initiate a group event."""
        p = ctx.clean_prefix
        await ctx.send(f"Please specify a valid subcommand, e.g.:\n"
                       f"`{p}ctevent list`\n"
                       f"`{p}ctevent run <event number>`")

    @ctevent.command(name="list")
    async def list_event(self, ctx: commands.Context):
        # Check if the bot has permission to send embeds
        if not ctx.channel.permissions_for(ctx.me).embed_links:
            return await ctx.send("I need the 'Embed Links' permission to display this message properly.")
        try:
            info_embed = discord.Embed(
                title="CrimeTime Events!!", 
                description="An Admin-initiated Event List.", 
                color=0x00FF)
            info_embed.add_field(
                name="Events:",
                value="1  -  A heavily-crowded walkway. (Max $300)\n2  -  A broken ATM Machine. (Max $500)\n3  -  A blocked Armored Car. (Max $2000)\n \n* More will be added over time.",
                inline=False)
            await ctx.send(embed=info_embed)
        except discord.HTTPException:
            await ctx.send("An error occurred while sending the message. Please try again later.")
