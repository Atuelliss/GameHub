import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

import discord
from redbot.core import bank, commands

from ..abc import MixinMeta

async def is_admin(ctx: commands.Context) -> bool:
    """Check if user is a bot admin or has Manage Server permission.
    
    Returns True if the user:
    - Is a Red-DiscordBot admin, OR
    - Has the Manage Server (manage_guild) Discord permission
    """
    if not ctx.guild:
        return False
    
    # Check Discord permissions
    if ctx.author.guild_permissions.manage_guild:
        return True
    
    # Check Red-DiscordBot admin status
    return await ctx.bot.is_admin(ctx.author)

# Continent configuration with emojis
TIMEZONE_CONTINENTS = {
    "Africa": "🌍",
    "North America": "🌎",
    "South America": "🌎",
    "Antarctica": "🧊",
    "Asia": "🌏",
    "Atlantic": "🌊",
    "Australia": "🦘",
    "Europe": "🏰",
    "Indian": "🌊",
    "Pacific": "🏝️",
    "Other": "🌐",
}

# South American timezone identifiers (cities/regions in South America)
SOUTH_AMERICA_TIMEZONES = {
    "America/Araguaina", "America/Argentina/Buenos_Aires", "America/Argentina/Catamarca",
    "America/Argentina/ComodRivadavia", "America/Argentina/Cordoba", "America/Argentina/Jujuy",
    "America/Argentina/La_Rioja", "America/Argentina/Mendoza", "America/Argentina/Rio_Gallegos",
    "America/Argentina/Salta", "America/Argentina/San_Juan", "America/Argentina/San_Luis",
    "America/Argentina/Tucuman", "America/Argentina/Ushuaia", "America/Asuncion",
    "America/Bahia", "America/Belem", "America/Boa_Vista", "America/Bogota",
    "America/Buenos_Aires", "America/Campo_Grande", "America/Caracas", "America/Cayenne",
    "America/Cuiaba", "America/Eirunepe", "America/Fortaleza", "America/Guayaquil",
    "America/Guyana", "America/La_Paz", "America/Lima", "America/Maceio", "America/Manaus",
    "America/Montevideo", "America/Noronha", "America/Paramaribo", "America/Porto_Acre",
    "America/Porto_Velho", "America/Punta_Arenas", "America/Recife", "America/Rio_Branco",
    "America/Santarem", "America/Santiago", "America/Sao_Paulo",
}


class TimezoneRegionView(discord.ui.View):
    """View for selecting a timezone region, then browsing timezones within it."""
    
    def __init__(self, author: discord.Member):
        super().__init__(timeout=180.0)
        self.author = author
        self.message: discord.Message = None
        self.current_region: str = None
        self.current_page = 0
        self.per_page = 15
        self.region_timezones: list[str] = []
        
        # Build the continent selection buttons
        self._build_continent_buttons()
    
    def _build_continent_buttons(self):
        """Build the initial continent selection buttons."""
        self.clear_items()
        
        for continent, emoji in TIMEZONE_CONTINENTS.items():
            button = discord.ui.Button(
                label=continent,
                emoji=emoji,
                style=discord.ButtonStyle.primary,
                custom_id=f"continent_{continent}"
            )
            button.callback = self._make_continent_callback(continent)
            self.add_item(button)
        
        # Add close button
        close_btn = discord.ui.Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id="close"
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
    
    def _make_continent_callback(self, continent: str):
        async def callback(interaction: discord.Interaction):
            await self._show_region_timezones(interaction, continent)
        return callback
    
    async def _close_callback(self, interaction: discord.Interaction):
        self.stop()
        await interaction.response.edit_message(
            content="Timezone list closed. Please enter your timezone now.",
            embed=None,
            view=None
        )
    
    def _get_timezones_for_region(self, region: str) -> list[str]:
        """Get all timezones for a specific region/continent."""
        all_tz = sorted(available_timezones())
        
        if region == "Other":
            # Timezones that don't start with a continent prefix (like UTC, GMT, etc.)
            return [tz for tz in all_tz if "/" not in tz or tz.startswith("Etc/")]
        elif region == "South America":
            # Return only South American timezones
            return [tz for tz in all_tz if tz in SOUTH_AMERICA_TIMEZONES]
        elif region == "North America":
            # Return America/* timezones that are NOT in South America
            return [tz for tz in all_tz if tz.startswith("America/") and tz not in SOUTH_AMERICA_TIMEZONES]
        else:
            return [tz for tz in all_tz if tz.startswith(f"{region}/")]
    
    async def _show_region_timezones(self, interaction: discord.Interaction, region: str):
        """Show timezones for the selected region."""
        self.current_region = region
        self.current_page = 0
        self.region_timezones = self._get_timezones_for_region(region)
        
        self._build_pagination_buttons()
        await interaction.response.edit_message(embed=self._get_region_embed(), view=self)
    
    def _build_pagination_buttons(self):
        """Build pagination buttons for browsing timezones in a region."""
        self.clear_items()
        
        # Back to continents button
        back_btn = discord.ui.Button(
            label="← Back to Regions",
            style=discord.ButtonStyle.secondary,
            custom_id="back"
        )
        back_btn.callback = self._back_to_continents
        self.add_item(back_btn)
        
        # Previous page (always enabled for wrap-around)
        prev_btn = discord.ui.Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            custom_id="prev"
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)
        
        # Next page (always enabled for wrap-around)
        next_btn = discord.ui.Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            custom_id="next"
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)
        
        # Close button
        close_btn = discord.ui.Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id="close"
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
    
    async def _back_to_continents(self, interaction: discord.Interaction):
        """Go back to continent selection."""
        self.current_region = None
        self._build_continent_buttons()
        await interaction.response.edit_message(embed=self._get_continent_embed(), view=self)
    
    async def _prev_page(self, interaction: discord.Interaction):
        """Go to previous page (wraps to last page if on first)."""
        total_pages = (len(self.region_timezones) + self.per_page - 1) // self.per_page
        if self.current_page > 0:
            self.current_page -= 1
        else:
            # Wrap to last page
            self.current_page = total_pages - 1
        self._build_pagination_buttons()
        await interaction.response.edit_message(embed=self._get_region_embed(), view=self)
    
    async def _next_page(self, interaction: discord.Interaction):
        """Go to next page (wraps to first page if on last)."""
        total_pages = (len(self.region_timezones) + self.per_page - 1) // self.per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
        else:
            # Wrap to first page
            self.current_page = 0
        self._build_pagination_buttons()
        await interaction.response.edit_message(embed=self._get_region_embed(), view=self)
    
    def _get_continent_embed(self) -> discord.Embed:
        """Get the embed for continent selection."""
        embed = discord.Embed(
            title="🌍 Select a Region",
            description="Click a button below to browse timezones in that region.",
            color=discord.Color.blue()
        )
        
        # Show counts for each region
        region_info = []
        for continent, emoji in TIMEZONE_CONTINENTS.items():
            count = len(self._get_timezones_for_region(continent))
            region_info.append(f"{emoji} **{continent}**: {count} timezones")
        
        embed.add_field(name="Available Regions", value="\n".join(region_info), inline=False)
        embed.set_footer(text="Select a region to see its timezones")
        return embed
    
    def _get_region_embed(self) -> discord.Embed:
        """Get the embed for a specific region's timezones."""
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.region_timezones[start:end]
        total_pages = (len(self.region_timezones) + self.per_page - 1) // self.per_page
        
        emoji = TIMEZONE_CONTINENTS.get(self.current_region, "🌐")
        embed = discord.Embed(
            title=f"{emoji} {self.current_region} Timezones",
            description="\n".join(f"`{tz}`" for tz in page_items),
            color=discord.Color.blue()
        )
        embed.set_footer(
            text=f"Page {self.current_page + 1}/{total_pages} • {len(self.region_timezones)} timezones in {self.current_region}"
        )
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your setup session!", ephemeral=True)
            return False
        return True


class ClearUserConfirmView(discord.ui.View):
    """Confirmation view for clearing user data."""
    
    def __init__(self, cog, author: discord.Member, target: discord.Member):
        super().__init__(timeout=30.0)
        self.cog = cog
        self.author = author
        self.target = target
        self.message = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your confirmation!", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Disable buttons on timeout."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            embed = discord.Embed(
                title="⏰ Timed Out",
                description="User data clear cancelled due to timeout.",
                color=discord.Color.grey()
            )
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm clearing the user's data."""
        conf = self.cog.db.get_conf(interaction.guild)
        
        if self.target.id in conf.users:
            del conf.users[self.target.id]
            self.cog.save()
            
            embed = discord.Embed(
                title="✅ User Data Cleared",
                description=f"All data for **{self.target.display_name}** has been deleted.\nThey can now start fresh!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Error",
                description=f"**{self.target.display_name}** no longer has any data to clear.",
                color=discord.Color.red()
            )
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the clear operation."""
        embed = discord.Embed(
            title="❌ Cancelled",
            description="User data clear cancelled.",
            color=discord.Color.grey()
        )
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


class WipeUsersConfirmModal(discord.ui.Modal, title="⚠️ FINAL CONFIRMATION"):
    """Modal for final confirmation of wiping all users."""
    
    confirmation_input = discord.ui.TextInput(
        label="Type CONFIRM to proceed",
        placeholder="CONFIRM",
        required=True,
        min_length=7,
        max_length=7,
        style=discord.TextStyle.short
    )
    
    def __init__(self, view: "WipeUsersConfirmView"):
        super().__init__()
        self.view = view
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        if self.confirmation_input.value != "CONFIRM":
            await interaction.response.send_message(
                "❌ Confirmation text did not match. Wipe cancelled.",
                ephemeral=True
            )
            return
        
        # Proceed with wipe
        conf = self.view.cog.db.get_conf(interaction.guild)
        user_count = len(conf.users)
        
        # Wipe all users
        conf.users.clear()
        self.view.cog.save()
        
        # Update embed
        embed = discord.Embed(
            title="✅ All Users Wiped",
            description=(
                f"**{user_count}** user(s) have been permanently deleted from the database.\n\n"
                f"**Current user count:** 0\n\n"
                f"All players will start fresh when they next use the game."
            ),
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Wiped by {interaction.user.display_name}")
        
        # Disable all buttons
        for item in self.view.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self.view)
        self.view.stop()


class WipeUsersConfirmView(discord.ui.View):
    """Confirmation view for wiping all users."""
    
    def __init__(self, cog, author: discord.Member, user_count: int):
        super().__init__(timeout=60.0)
        self.cog = cog
        self.author = author
        self.user_count = user_count
        self.message = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your confirmation!", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Disable buttons on timeout."""
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        if self.message:
            embed = discord.Embed(
                title="⏰ Timed Out",
                description="User wipe cancelled due to timeout.",
                color=discord.Color.grey()
            )
            try:
                await self.message.edit(embed=embed, view=self)
            except discord.HTTPException:
                pass
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="⚠️")
    async def confirm_wipe(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show final confirmation modal."""
        modal = WipeUsersConfirmModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Deny", style=discord.ButtonStyle.secondary, emoji="❌")
    async def deny_wipe(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the wipe operation."""
        embed = discord.Embed(
            title="❌ Cancelled",
            description="User wipe cancelled. No data was deleted.",
            color=discord.Color.grey()
        )
        
        for item in self.children:
            item.disabled = True
        
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


class Admin(MixinMeta):
    @commands.command(name="fishsetup")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def fishsetup(self, ctx: commands.Context):
        """Walk through the initial setup for Greenacres Fishing."""
        conf = self.db.get_conf(ctx.guild)
        
        def check(m: discord.Message) -> bool:
            return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id
        
        # Step 1: Timezone
        await ctx.send(
            "🎣 **Greenacres Fishing Setup**\n\n"
            "**Step 1/3: Timezone**\n"
            f"Current timezone: `{conf.timezone}`\n\n"
            "Please enter your server's timezone (e.g., `America/New_York`, `Europe/London`, `UTC`).\n"
            "Type `help` to see all available timezones, or `skip` to keep the current setting."
        )
        
        # Timezone input loop (allows help to be shown and then continue)
        timezone_set = False
        while not timezone_set:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=120.0)
                user_input = msg.content.strip().lower()
                
                if user_input == "help":
                    # Show region-based timezone browser
                    view = TimezoneRegionView(author=ctx.author)
                    help_msg = await ctx.send(embed=view._get_continent_embed(), view=view)
                    view.message = help_msg
                    await view.wait()
                    await ctx.send("Now enter your timezone choice:")
                    continue  # Loop back to wait for timezone input
                
                elif user_input == "skip":
                    await ctx.send(f"⏭️ Skipped. Timezone remains `{conf.timezone}`.")
                    timezone_set = True
                
                else:
                    timezone = msg.content.strip()  # Use original case for timezone
                    if timezone in available_timezones():
                        conf.timezone = timezone
                        self.save()
                        await ctx.send(f"✅ Timezone set to **{timezone}**")
                        timezone_set = True
                    else:
                        # Try to find similar timezones
                        matches = [tz for tz in available_timezones() if timezone.lower() in tz.lower()][:5]
                        if matches:
                            # Build numbered list for selection
                            match_list = "\n".join(f"`{i+1}` - `{m}`" for i, m in enumerate(sorted(matches)))
                            await ctx.send(
                                f"⚠️ `{timezone}` is not a valid timezone. Did you mean one of these?\n\n"
                                f"{match_list}\n\n"
                                "Reply with the **number** of your choice, or type `utc` to use UTC."
                            )
                            
                            try:
                                tz_msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                                tz_response = tz_msg.content.strip().lower()
                                
                                if tz_response == "utc":
                                    conf.timezone = "UTC"
                                    self.save()
                                    await ctx.send("✅ Timezone set to **UTC**")
                                elif tz_response.isdigit():
                                    choice = int(tz_response)
                                    sorted_matches = sorted(matches)
                                    if 1 <= choice <= len(sorted_matches):
                                        selected_tz = sorted_matches[choice - 1]
                                        conf.timezone = selected_tz
                                        self.save()
                                        await ctx.send(f"✅ Timezone set to **{selected_tz}**")
                                    else:
                                        await ctx.send(f"⚠️ Invalid choice. Keeping `{conf.timezone}`.")
                                else:
                                    await ctx.send(f"⚠️ Invalid response. Keeping `{conf.timezone}`.")
                            except asyncio.TimeoutError:
                                await ctx.send(f"⏰ Timed out. Keeping `{conf.timezone}`.")
                        else:
                            # No matches found, offer UTC
                            await ctx.send(
                                f"⚠️ `{timezone}` is not a valid timezone and no similar matches found.\n"
                                "Would you like to use `UTC`? Reply with `yes` or `no`."
                            )
                            
                            try:
                                utc_msg = await self.bot.wait_for("message", check=check, timeout=60.0)
                                if utc_msg.content.strip().lower() in ("yes", "y"):
                                    conf.timezone = "UTC"
                                    self.save()
                                    await ctx.send("✅ Timezone set to **UTC**")
                                else:
                                    await ctx.send(f"⏭️ Keeping `{conf.timezone}`.")
                            except asyncio.TimeoutError:
                                await ctx.send(f"⏰ Timed out. Keeping `{conf.timezone}`.")
                        timezone_set = True
                        
            except asyncio.TimeoutError:
                await ctx.send("⏰ Setup timed out. Run `fishsetup` again to continue.")
                return
        
        # Step 2: Hemisphere
        await ctx.send(
            "**Step 2/3: Hemisphere**\n"
            f"Current hemisphere: `{conf.hemisphere}`\n\n"
            "This affects season calculation. Enter `north` or `south`.\n"
            "Or type `skip` to keep the current setting."
        )
        
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
            if msg.content.lower() != "skip":
                hemisphere = msg.content.strip().lower()
                if hemisphere in ("north", "south"):
                    conf.hemisphere = hemisphere
                    self.save()
                    await ctx.send(f"✅ Hemisphere set to **{hemisphere.title()}ern Hemisphere**")
                else:
                    await ctx.send(f"⚠️ Invalid hemisphere. Keeping `{conf.hemisphere}`.")
            else:
                await ctx.send(f"⏭️ Skipped. Hemisphere remains `{conf.hemisphere}`.")
        except asyncio.TimeoutError:
            await ctx.send("⏰ Setup timed out. Run `fishsetup` again to continue.")
            return
        
        # Step 3: Show game time info
        from .helper_functions import get_game_calendar, get_game_time_of_day
        
        calendar = get_game_calendar(self.db, ctx.guild)
        time_of_day = get_game_time_of_day(self.db, ctx.guild)
        tz = ZoneInfo(conf.timezone)
        real_now = datetime.now(tz)
        
        await ctx.send(
            "**Step 3/3: Game Time Preview**\n\n"
            f"**🎮 Game Time**\n"
            f"{time_of_day['emoji']} **{time_of_day['name']}** ({time_of_day['hour']:02d}:{time_of_day['minute']:02d})\n\n"
            f"**📅 Game Calendar**\n"
            f"Day **{calendar['day_of_season']}** of **{calendar['season']}**, Year **{calendar['year']}**\n\n"
            f"**🌍 Real World**\n"
            f"{real_now.strftime('%B %d, %Y at %I:%M %p %Z')}\n"
            f"Hemisphere: {conf.hemisphere.title()}ern\n\n"
            "You can adjust time settings later with `fishset gametime`."
        )
        
        # Final step: Enable the game
        status = "🟢 Enabled" if conf.is_game_enabled else "🔴 Disabled"
        await ctx.send(
            "**Enable the Game?**\n"
            f"Current status: {status}\n\n"
            "Would you like to enable Greenacres Fishing?\n"
            "Reply with `yes`, `on`, or `enable` to enable.\n"
            "Reply with `no`, `off`, or `disable` to keep it disabled."
        )
        
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
            response = msg.content.strip().lower()
            
            if response in ("yes", "on", "enable"):
                conf.is_game_enabled = True
                self.save()
                await ctx.send("✅ **Greenacres Fishing is now ENABLED!**")
            elif response in ("no", "off", "disable"):
                conf.is_game_enabled = False
                self.save()
                await ctx.send("🔴 **Greenacres Fishing remains DISABLED.**")
            else:
                await ctx.send(f"⚠️ Unrecognized response. Game status unchanged ({status}).")
        except asyncio.TimeoutError:
            await ctx.send("⏰ Setup timed out. Game status unchanged. Run `fishsetup` again to continue.")
            return
        
        # Currency Conversion Setup
        currency_name = await bank.get_currency_name(ctx.guild)
        conv_status = "🟢 Enabled" if conf.discord_currency_conversion_enabled else "🔴 Disabled"
        await ctx.send(
            "**💱 Discord Currency Conversion**\n"
            f"Current status: {conv_status}\n\n"
            f"This feature allows players to convert FishPoints ↔ {currency_name}.\n\n"
            "Would you like to enable currency conversion?\n"
            "Reply with `yes` to enable, or `no` to disable."
        )
        
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
            response = msg.content.strip().lower()
            
            if response in ("yes", "y"):
                conf.discord_currency_conversion_enabled = True
                self.save()
                await ctx.send(f"✅ Currency conversion **enabled**!")
                
                # Ask about conversion rate
                await ctx.send(
                    "**Set Conversion Rate?**\n"
                    f"Current rate: **{conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}**\n\n"
                    f"The default rate is 100 FP = 1 {currency_name}.\n"
                    "Would you like to set a custom rate?\n"
                    "Reply with `yes` to set a custom rate, or `no` to keep the default."
                )
                
                try:
                    msg = await self.bot.wait_for("message", check=check, timeout=120.0)
                    rate_response = msg.content.strip().lower()
                    
                    if rate_response in ("yes", "y"):
                        await ctx.send(
                            "Enter the conversion rate (FishPoints per 1 Discord currency).\n"
                            "For example, enter `100` for 100 FP = 1 Discord currency.\n"
                            "Enter `50` for 50 FP = 1 Discord currency."
                        )
                        
                        try:
                            msg = await self.bot.wait_for("message", check=check, timeout=120.0)
                            try:
                                rate = int(msg.content.strip())
                                if rate <= 0:
                                    await ctx.send(f"⚠️ Invalid rate. Keeping default of **{conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}**.")
                                else:
                                    conf.discord_currency_conversion_rate = rate
                                    self.save()
                                    await ctx.send(f"✅ Conversion rate set to **{rate:,} FP = 1 {currency_name}**")
                            except ValueError:
                                await ctx.send(f"⚠️ Invalid number. Keeping default of **{conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}**.")
                        except asyncio.TimeoutError:
                            await ctx.send(f"⏰ Timed out. Keeping default of **{conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}**.")
                    else:
                        await ctx.send(
                            f"✅ Keeping default rate of **{conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}**.\n"
                            "You can change this anytime with `fishset setrate <amount>`."
                        )
                except asyncio.TimeoutError:
                    await ctx.send(
                        f"⏰ Timed out. Keeping default rate of **{conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}**.\n"
                        "You can change this anytime with `fishset setrate <amount>`."
                    )
                    
            elif response in ("no", "n"):
                conf.discord_currency_conversion_enabled = False
                self.save()
                await ctx.send(
                    "🔴 Currency conversion **disabled**.\n"
                    "You can enable it anytime with `fishset conversion on`."
                )
            else:
                await ctx.send(f"⚠️ Unrecognized response. Currency conversion status unchanged ({conv_status}).")
        except asyncio.TimeoutError:
            await ctx.send("⏰ Timed out. Currency conversion status unchanged.")
        
        # Final setup complete message
        await ctx.send(
            "🎣 **Setup Complete!**\n\n"
            f"• Game: {'🟢 Enabled' if conf.is_game_enabled else '🔴 Disabled'}\n"
            f"• Timezone: `{conf.timezone}`\n"
            f"• Hemisphere: `{conf.hemisphere.title()}ern`\n"
            f"• Currency Conversion: {'🟢 Enabled' if conf.discord_currency_conversion_enabled else '🔴 Disabled'}\n"
            f"• Conversion Rate: {conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}\n\n"
            "Players can now use the `fish` command to start playing!"
        )

    @commands.group(name="fishset", aliases=["fset"])
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def fishset(self, ctx: commands.Context):
        """Admin settings for Greenacres Fishing."""
        pass

    @fishset.command(name="timezone", aliases=["tz"])
    async def set_timezone(self, ctx: commands.Context, timezone: str = None):
        """Set or view the server's timezone for time-based features.
        
        Use standard timezone names like:
        - America/New_York
        - America/Los_Angeles  
        - Europe/London
        - Asia/Tokyo
        - UTC
        
        Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        """
        conf = self.db.get_conf(ctx.guild)
        
        # If no timezone provided, show current setting
        if timezone is None:
            tz = ZoneInfo(conf.timezone)
            now = datetime.now(tz)
            await ctx.send(
                f"🕐 Server timezone: **{conf.timezone}**\n"
                f"Current time: {now.strftime('%Y-%m-%d %I:%M %p %Z')}"
            )
            return
        
        # Validate the timezone
        if timezone not in available_timezones():
            # Try to find close matches for better UX
            matches = [tz for tz in available_timezones() if timezone.lower() in tz.lower()][:10]
            if matches:
                match_list = "\n".join(f"• `{m}`" for m in sorted(matches))
                await ctx.send(f"❌ Invalid timezone. Did you mean one of these?\n{match_list}")
            else:
                await ctx.send(
                    "❌ Invalid timezone. Use a valid IANA timezone name.\n"
                    "Examples: `America/New_York`, `Europe/London`, `Asia/Tokyo`, `UTC`"
                )
            return

        conf.timezone = timezone
        self.save()

        # Show current time in that timezone as confirmation
        now = datetime.now(ZoneInfo(timezone))
        await ctx.send(
            f"✅ Server timezone set to **{timezone}**\n"
            f"Current time: {now.strftime('%Y-%m-%d %I:%M %p %Z')}"
        )

    @fishset.command(name="hemisphere", aliases=["hemi"])
    async def set_hemisphere(self, ctx: commands.Context, hemisphere: str = None):
        """Set or view the server's hemisphere for season calculation.
        
        Valid options: north, south
        
        This affects which season is active:
        - Northern: Winter in Dec-Feb, Summer in Jun-Aug
        - Southern: Summer in Dec-Feb, Winter in Jun-Aug
        """
        conf = self.db.get_conf(ctx.guild)
        
        if hemisphere is None:
            await ctx.send(
                f"🌍 Server hemisphere: **{conf.hemisphere.title()}ern Hemisphere**\n"
                f"Use `{ctx.clean_prefix}fishset hemisphere north` or `south` to change."
            )
            return
        
        hemisphere = hemisphere.lower()
        if hemisphere not in ("north", "south"):
            await ctx.send("❌ Invalid hemisphere. Use `north` or `south`.")
            return
        
        conf.hemisphere = hemisphere
        self.save()
        
        await ctx.send(f"✅ Server hemisphere set to **{hemisphere.title()}ern Hemisphere**")

    @fishset.command(name="gametime", aliases=["gt"])
    async def show_game_time(self, ctx: commands.Context):
        """Show the current game time, day, season, and year."""
        from .helper_functions import get_game_calendar, get_game_time_of_day
        
        conf = self.db.get_conf(ctx.guild)
        calendar = get_game_calendar(self.db, ctx.guild)
        time_of_day = get_game_time_of_day(self.db, ctx.guild)
        
        # Get real-world time for comparison
        tz = ZoneInfo(conf.timezone)
        real_now = datetime.now(tz)
        
        embed_desc = (
            f"**🎮 Game Time**\n"
            f"{time_of_day['emoji']} **{time_of_day['name']}** ({time_of_day['hour']:02d}:{time_of_day['minute']:02d})\n\n"
            f"**📅 Game Calendar**\n"
            f"Day **{calendar['day_of_season']}** of **{calendar['season']}**, Year **{calendar['year']}**\n"
            f"(Total game days: {calendar['total_game_days']})\n\n"
            f"**🌍 Real World**\n"
            f"{real_now.strftime('%B %d, %Y at %I:%M %p %Z')}\n"
            f"Hemisphere: {conf.hemisphere.title()}ern"
        )
        
        await ctx.send(embed_desc)

    @fishset.command(name="clearuser")
    @commands.check(is_admin)
    async def clear_user(self, ctx: commands.Context, target: discord.Member):
        """Remove a user from the database, letting them start fresh.
        
        This will delete ALL of the user's data including:
        - Fish inventory
        - Bait and equipment
        - Currency and tokens
        - Statistics and records
        """
        conf = self.db.get_conf(ctx.guild)
        
        if target.id not in conf.users:
            await ctx.send(f"❌ **{target.display_name}** has no data to clear.")
            return
        
        # Create confirmation embed and view
        embed = discord.Embed(
            title="⚠️ Clear User Data",
            description=(
                f"This will permanently delete **ALL** data for **{target.display_name}**.\n\n"
                f"**This includes:**\n"
                f"• Fish inventory\n"
                f"• Bait and equipment\n"
                f"• Currency and tokens\n"
                f"• Statistics and records\n\n"
                f"**This action cannot be undone.**"
            ),
            color=discord.Color.red()
        )
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        view = ClearUserConfirmView(cog=self, author=ctx.author, target=target)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @fishset.command(name="wipeusers")
    @commands.check(is_admin)
    async def wipe_users(self, ctx: commands.Context):
        """⚠️ DANGER: Wipe ALL users from the database.
        
        This is an extreme measure that will permanently delete ALL user data
        for EVERY player in the server. This cannot be undone.
        
        Only use this if you need to completely reset the game.
        """
        conf = self.db.get_conf(ctx.guild)
        user_count = len(conf.users)
        
        if user_count == 0:
            await ctx.send("ℹ️ There are no users in the database to wipe.")
            return
        
        # Create warning embed
        embed = discord.Embed(
            title="🚨 EXTREME MEASURE - WIPE ALL USERS 🚨",
            description=(
                f"**⚠️ THIS WILL PERMANENTLY DELETE ALL USER DATA ⚠️**\n\n"
                f"**Current users in database:** {user_count}\n\n"
                f"**This will erase:**\n"
                f"• All fish inventories\n"
                f"• All bait and equipment\n"
                f"• All currency and tokens\n"
                f"• All statistics and records\n"
                f"• Everything for every player\n\n"
                f"**⛔ THIS ACTION CANNOT BE UNDONE ⛔**\n\n"
                f"Press **Confirm** to proceed with a final verification step.\n"
                f"Press **Deny** to cancel this operation."
            ),
            color=discord.Color.dark_red()
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name} | Use with extreme caution")
        
        view = WipeUsersConfirmView(cog=self, author=ctx.author, user_count=user_count)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @fishset.command(name="startgame")
    @commands.check(is_admin)
    async def start_game(self, ctx: commands.Context):
        """Enable the fishing game for this server."""
        conf = self.db.get_conf(ctx.guild)
        
        if conf.is_game_enabled:
            await ctx.send("🟢 The fishing game is already enabled!")
            return
        
        conf.is_game_enabled = True
        self.save()
        await ctx.send("✅ **Greenacres Fishing is now ENABLED!**\n🎣 Players can now use the `fish` command to start playing.")

    @fishset.command(name="stopgame")
    @commands.check(is_admin)
    async def stop_game(self, ctx: commands.Context):
        """Disable the fishing game for this server."""
        conf = self.db.get_conf(ctx.guild)
        
        if not conf.is_game_enabled:
            await ctx.send("🔴 The fishing game is already disabled!")
            return
        
        conf.is_game_enabled = False
        self.save()
        await ctx.send("🔴 **Greenacres Fishing is now DISABLED.**\n⚠️ Players will not be able to use the `fish` command until the game is re-enabled.")

    @fishset.command(name="display")
    @commands.check(is_admin)
    async def display_settings(self, ctx: commands.Context):
        """Display server game statistics and settings."""
        conf = self.db.get_conf(ctx.guild)
        
        # Get Discord currency name
        currency_name = await bank.get_currency_name(ctx.guild)
        
        # Game state
        game_status = "🟢 Enabled" if conf.is_game_enabled else "🔴 Disabled"
        
        # Currency conversion
        currency_status = "🟢 Enabled" if conf.discord_currency_conversion_enabled else "🔴 Disabled"
        
        # Total fisherfolk (users who have played)
        total_fisherfolk = len(conf.users)
        
        # Total fish caught by all users ever
        total_fish_caught = sum(user.total_fish_ever_caught for user in conf.users.values())
        
        embed = discord.Embed(
            title="🎣 Greenacres Fishing - Server Stats",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="Game State",
            value=game_status,
            inline=False
        )
        embed.add_field(
            name="Currency Conversion System",
            value=f"{currency_status}\n💱 Rate: {conf.discord_currency_conversion_rate:,} FP:1 {currency_name}",
            inline=False
        )
        embed.add_field(
            name="Total Fisherfolk",
            value=f"🧑‍🌾 {total_fisherfolk:,} players",
            inline=True
        )
        embed.add_field(
            name="Total Fish Caught",
            value=f"🐟 {total_fish_caught:,} fish",
            inline=True
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)

    @fishset.command(name="conversion")
    @commands.check(is_admin)
    async def set_conversion_toggle(self, ctx: commands.Context, state: str = None):
        """Toggle or set the Discord currency conversion feature.
        
        Arguments:
        - `on` or `enabled` - Enable currency conversion
        - `off` or `disabled` - Disable currency conversion
        - No argument - Toggle the current state
        
        Example: `fishset conversion on`
        """
        conf = self.db.get_conf(ctx.guild)
        
        if state is None:
            # Toggle current state
            conf.discord_currency_conversion_enabled = not conf.discord_currency_conversion_enabled
        else:
            state_lower = state.lower()
            if state_lower in ("on", "enabled"):
                conf.discord_currency_conversion_enabled = True
            elif state_lower in ("off", "disabled"):
                conf.discord_currency_conversion_enabled = False
            else:
                await ctx.send("❌ Invalid argument. Use `on`, `enabled`, `off`, `disabled`, or no argument to toggle.")
                return
        
        self.save()
        
        status = "✅ **Enabled**" if conf.discord_currency_conversion_enabled else "❌ **Disabled**"
        currency_name = await bank.get_currency_name(ctx.guild)
        await ctx.send(
            f"💱 Currency conversion is now {status}\n"
            f"Rate: **{conf.discord_currency_conversion_rate:,} FP = 1 {currency_name}**"
        )

    @fishset.command(name="setrate")
    @commands.check(is_admin)
    async def set_conversion_rate(self, ctx: commands.Context, rate: int):
        """Set the FishPoints to Discord currency conversion rate.
        
        Example: `fishset setrate 100` means 100 FP = 1 Discord currency.
        """
        if rate <= 0:
            await ctx.send("❌ Rate must be a positive number.")
            return
        
        conf = self.db.get_conf(ctx.guild)
        old_rate = conf.discord_currency_conversion_rate
        conf.discord_currency_conversion_rate = rate
        self.save()
        
        currency_name = await bank.get_currency_name(ctx.guild)
        await ctx.send(f"✅ Conversion rate updated: **{rate:,} FP = 1 {currency_name}** (was {old_rate:,})")

    @fishset.group(name="channel", invoke_without_command=True)
    @commands.check(is_admin)
    async def fish_channel(self, ctx: commands.Context):
        """Manage allowed channels for Greenacres Fishing.
        
        Use subcommands: add, remove, list
        If no channels are set, the game can be played in any channel.
        """
        await ctx.send_help(ctx.command)

    @fish_channel.command(name="add")
    @commands.check(is_admin)
    async def fish_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        """Add a channel to the allowed list.
        
        Once any channel is added, commands will only work in allowed channels.
        """
        conf = self.db.get_conf(ctx.guild)
        if channel.id in conf.allowed_channels:
            await ctx.send(f"❌ {channel.mention} is already in the allowed channels list.")
            return
        
        conf.allowed_channels.append(channel.id)
        self.save()
        await ctx.send(f"✅ {channel.mention} added to allowed channels.")

    @fish_channel.command(name="remove")
    @commands.check(is_admin)
    async def fish_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """Remove a channel from the allowed list.
        
        If all channels are removed, the game can be played anywhere again.
        """
        conf = self.db.get_conf(ctx.guild)
        if channel.id not in conf.allowed_channels:
            await ctx.send(f"❌ {channel.mention} is not in the allowed channels list.")
            return
        
        conf.allowed_channels.remove(channel.id)
        self.save()
        
        if not conf.allowed_channels:
            await ctx.send(f"✅ {channel.mention} removed. No channels are restricted - the game can be played anywhere.")
        else:
            await ctx.send(f"✅ {channel.mention} removed from allowed channels.")

    @fish_channel.command(name="list")
    @commands.check(is_admin)
    async def fish_channel_list(self, ctx: commands.Context):
        """List all allowed channels for Greenacres Fishing."""
        conf = self.db.get_conf(ctx.guild)
        
        if not conf.allowed_channels:
            await ctx.send("📢 No channel restrictions set - Greenacres Fishing can be played in any channel.")
            return
        
        channels = []
        invalid_ids = []
        for channel_id in conf.allowed_channels:
            ch = ctx.guild.get_channel(channel_id)
            if ch:
                channels.append(ch.mention)
            else:
                invalid_ids.append(str(channel_id))
        
        embed = discord.Embed(
            title="🎣 Allowed Fishing Channels",
            color=discord.Color.blue()
        )
        
        if channels:
            embed.add_field(
                name="Active Channels",
                value="\n".join(channels),
                inline=False
            )
        
        if invalid_ids:
            embed.add_field(
                name="⚠️ Invalid Channel IDs",
                value="\n".join(invalid_ids) + "\n*These channels no longer exist and should be removed.*",
                inline=False
            )
        
        embed.set_footer(text=f"Total: {len(conf.allowed_channels)} channel(s)")
        await ctx.send(embed=embed)
    @fishset.command(name="fpset")
    @commands.check(is_admin)
    async def set_fishpoints(self, ctx: commands.Context, target: discord.Member, amount: str):
        """Set a user's FishPoints.
        
        **Usage:**
        • `[p]fishset fpset @user 100` - Set FishPoints to exactly 100
        • `[p]fishset fpset @user +50` - Add 50 FishPoints
        • `[p]fishset fpset @user -25` - Subtract 25 FishPoints
        
        **Notes:**
        - Setting to an exact amount updates "most ever" if the new amount is higher
        - Adding (+) updates both current and "most ever" if new total is higher
        - Subtracting (-) only reduces current FishPoints, never affects "most ever"
        - Current FishPoints cannot go below 0
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(target)
        
        old_fp = user_data.total_fishpoints
        old_most = user_data.most_fishpoints_ever
        
        # Parse the amount
        if amount.startswith('+'):
            # Add to current amount
            try:
                add_amount = int(amount[1:])
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number after the `+` sign.")
                return
            
            user_data.total_fishpoints += add_amount
            
            # Update most_fishpoints_ever if new total is higher
            if user_data.total_fishpoints > user_data.most_fishpoints_ever:
                user_data.most_fishpoints_ever = user_data.total_fishpoints
            
            self.save()
            
            await ctx.send(
                f"✅ Added **{add_amount:,}** FishPoints to {target.mention}\n"
                f"Current: **{old_fp:,}** → **{user_data.total_fishpoints:,}**\n"
                f"Most Ever: **{old_most:,}** → **{user_data.most_fishpoints_ever:,}**"
            )
            
        elif amount.startswith('-'):
            # Subtract from current amount
            try:
                sub_amount = int(amount[1:])
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number after the `-` sign.")
                return
            
            user_data.total_fishpoints = max(0, user_data.total_fishpoints - sub_amount)
            # most_fishpoints_ever stays unchanged
            
            self.save()
            
            await ctx.send(
                f"✅ Subtracted **{sub_amount:,}** FishPoints from {target.mention}\n"
                f"Current: **{old_fp:,}** → **{user_data.total_fishpoints:,}**\n"
                f"Most Ever: **{user_data.most_fishpoints_ever:,}** (unchanged)"
            )
            
        else:
            # Set to exact amount
            try:
                new_amount = int(amount)
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number, `+number`, or `-number`.")
                return
            
            if new_amount < 0:
                await ctx.send("❌ FishPoints cannot be negative. Use `0` for zero or `-number` to subtract.")
                return
            
            user_data.total_fishpoints = new_amount
            
            # Update most_fishpoints_ever if new amount is higher
            if new_amount > user_data.most_fishpoints_ever:
                user_data.most_fishpoints_ever = new_amount
            
            self.save()
            
            most_changed = " (updated)" if new_amount > old_most else " (unchanged)"
            
            await ctx.send(
                f"✅ Set {target.mention}'s FishPoints to **{new_amount:,}**\n"
                f"Previous: **{old_fp:,}**\n"
                f"Most Ever: **{user_data.most_fishpoints_ever:,}**{most_changed}"
            )
