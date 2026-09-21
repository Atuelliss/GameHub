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
    @commands.group(invoke_without_command=True)
    @commands.check(is_admin_or_owner)
    async def ctset(self, ctx: commands.Context):
        """Configure CrimeTime settings and user data."""
        p = ctx.clean_prefix
        embed = discord.Embed(
            title="CrimeTime Admin Settings",
            description=f"Use `{p}ctset <command>` to configure settings.",
            color=discord.Color.gold()
        )
        
        # Server Overview
        embed.add_field(
            name="Server Overview",
            value=f"`{p}ctset display` - View server stats and settings",
            inline=False
        )
        
        # Game Modes
        embed.add_field(
            name="Game Modes",
            value=(
                f"`{p}ctset setmode <mode> <on/off>`\n"
                f"Modes: `mug`, `carjacking`, `robbery`, `heist`, `events`"
            ),
            inline=False
        )
        
        # Player Data Management
        embed.add_field(
            name="Player Data",
            value=(
                f"`{p}ctset view <user>` - View player info\n"
                f"`{p}ctset balance <user> <amt>` - Set cash balance\n"
                f"`{p}ctset bars <user> <amt>` - Set gold bars\n"
                f"`{p}ctset gems <user> <amt>` - Set gems"
            ),
            inline=False
        )
        
        # Player Stats
        embed.add_field(
            name="Player Stats",
            value=(
                f"`{p}ctset pwin/ploss <user> <amt>` - PvP mug wins/losses\n"
                f"`{p}ctset rwin/rloss <user> <amt>` - Robbery wins/losses\n"
                f"`{p}ctset hwin/hloss <user> <amt>` - Heist wins/losses"
            ),
            inline=False
        )
        
        # Economy Values
        embed.add_field(
            name="Economy Values",
            value=(
                f"`{p}ctset goldvalue <amt>` - Set gold bar cash value\n"
                f"`{p}ctset gemvalue <amt>` - Set gem cash value"
            ),
            inline=False
        )
        
        # Discord Currency Conversion
        embed.add_field(
            name="Discord Currency Conversion",
            value=(
                f"`{p}ctset conversion <on/off>` - Toggle gem conversion\n"
                f"`{p}ctset conversionvalue <amt>` - Set gem to currency rate"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @ctset.command(name="display")
    async def display_settings(self, ctx: commands.Context):
        """Display current server statistics and settings."""
        guildsettings = self.db.get_conf(ctx.guild)
        
        # Calculate player statistics
        total_users = len(guildsettings.users)
        total_cash = sum(u.balance for u in guildsettings.users.values())
        total_bars = sum(u.gold_bars for u in guildsettings.users.values())
        total_gems = sum(u.gems_owned for u in guildsettings.users.values())
        
        # Gang statistics
        total_gangs = len(guildsettings.gangs)
        total_gang_members = sum(gang.member_count for gang in guildsettings.gangs.values())
        
        # Helper for on/off display
        def status(enabled: bool) -> str:
            return "ON" if enabled else "OFF"
        
        embed = discord.Embed(
            title=f"CrimeTime Server Overview",
            description=f"Statistics and settings for **{ctx.guild.name}**",
            color=discord.Color.gold()
        )
        
        # Economy Statistics
        embed.add_field(
            name="Economy Statistics",
            value=(
                f"Total Players: **{total_users:,}**\n"
                f"Total Cash: **${total_cash:,}**\n"
                f"Total Gold Bars: **{total_bars:,}**\n"
                f"Total Gems: **{total_gems:,}**"
            ),
            inline=False
        )
        
        # Gang Statistics
        embed.add_field(
            name="Gang Statistics",
            value=(
                f"Total Gangs: **{total_gangs:,}**\n"
                f"Total Gang Members: **{total_gang_members:,}**"
            ),
            inline=False
        )
        
        # Game Modules Status
        embed.add_field(
            name="Game Modules",
            value=(
                f"Mugging: **{status(guildsettings.is_mug_enabled)}**\n"
                f"Carjacking: **{status(guildsettings.is_carjacking_enabled)}**\n"
                f"Robbery: **{status(guildsettings.is_robbery_enabled)}**\n"
                f"Heist: **{status(guildsettings.is_heist_enabled)}**\n"
                f"Events: **{status(guildsettings.is_pop_up_enabled)}**"
            ),
            inline=True
        )
        
        # Bank Settings
        embed.add_field(
            name="Bank Settings",
            value=(
                f"Bank Enabled: **{status(guildsettings.is_bank_enabled)}**\n"
                f"Interest Rate: **{guildsettings.bank_interest_rate:.2%}**\n"
                f"Max Withdraw: **${guildsettings.bank_max_withdraw:,}**"
            ),
            inline=True
        )
        
        # Economy Values
        embed.add_field(
            name="Economy Values",
            value=(
                f"Gold Bar Value: **${guildsettings.bar_value:,}**\n"
                f"Gem Value: **${guildsettings.gem_value:,}**\n"
                f"Conversion: **{status(guildsettings.is_conversion_enabled)}**\n"
                f"Conversion Rate: **{guildsettings.gem_conversion_value:,}**"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @ctset.command(name="setmode")
    async def set_game_mode(self, ctx: commands.Context, mode: str, toggle: str):
        """Enable or disable game modes.
        
        Modes: mug, carjacking, robbery, heist, events
        Toggle: on/off, enable/disable, enabled/disabled
        
        Example: [p]ctset setmode mug on
        """
        guildsettings = self.db.get_conf(ctx.guild)
        
        # Normalize inputs
        mode = mode.lower()
        toggle = toggle.lower()
        
        # Map mode names to settings attributes
        mode_map = {
            "mug": ("is_mug_enabled", "Mugging"),
            "carjacking": ("is_carjacking_enabled", "Carjacking"),
            "robbery": ("is_robbery_enabled", "Robbery"),
            "heist": ("is_heist_enabled", "Heist"),
            "events": ("is_pop_up_enabled", "Events"),
        }
        
        # Validate mode
        if mode not in mode_map:
            valid_modes = ", ".join(f"`{m}`" for m in mode_map.keys())
            await ctx.send(f"Invalid mode. Valid modes are: {valid_modes}")
            return
        
        # Parse toggle value
        on_values = ["on", "enable", "enabled"]
        off_values = ["off", "disable", "disabled"]
        
        if toggle in on_values:
            enabled = True
        elif toggle in off_values:
            enabled = False
        else:
            await ctx.send("Invalid toggle. Use `on`/`off`, `enable`/`disable`, or `enabled`/`disabled`.")
            return
        
        # Apply the setting
        attr_name, display_name = mode_map[mode]
        setattr(guildsettings, attr_name, enabled)
        self.save()
        
        status = "enabled" if enabled else "disabled"
        await ctx.send(f"**{display_name}** has been **{status}**.")

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
        """Set the gold bar value for this server's economy."""
        if amount <= 0:
            await ctx.send("You cannot set a negative or zero value for gold bars!")
            return
        guildsettings = self.db.get_conf(ctx.guild)
        guildsettings.bar_value = amount
        await ctx.send(f"Gold bar value has been set to ${amount}.")
        self.save()
    
    @ctset.command(name="gemvalue")
    async def set_gem_value(self, ctx: commands.Context, amount: int):
        """Set the gem value for this server's economy."""
        if amount <= 0:
            await ctx.send("You cannot set a negative or zero value for gems!")
            return
        guildsettings = self.db.get_conf(ctx.guild)
        guildsettings.gem_value = amount
        await ctx.send(f"Gem value has been set to ${amount}.")
        self.save()

    @ctset.command(name="conversionvalue")
    async def set_conversion_value(self, ctx: commands.Context, amount: int):
        """Set the value gems are worth when converting to the Discord Currency."""
        if amount <= 0:
            await ctx.send("You cannot set a negative or zero value.")
            return
        guildsettings = self.db.get_conf(ctx.guild)
        guildsettings.gem_conversion_value = amount
        await ctx.send(f"Gem value to Discord Currency has been set to {amount}.")
        self.save()

    @ctset.command(name="conversion")
    async def enable_bank_conversion(self, ctx: commands.Context, toggle: str):
        """Enable or disable bank conversion for this server.
        
        Use "on" to enable or "off" to disable.
        """
        # Validate input
        toggle = toggle.lower()
        if toggle not in ["on", "off"]:
            await ctx.send("Invalid option. Please use 'on' or 'off'.")
            return
        
        # Set the value
        guildsettings = self.db.get_conf(ctx.guild)
        guildsettings.is_conversion_enabled = (toggle == "on")
        
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
