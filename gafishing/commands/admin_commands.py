import asyncio
from datetime import datetime
from io import BytesIO
import json
from zoneinfo import ZoneInfo, available_timezones

import discord
from redbot.core import bank, commands

from ..abc import MixinMeta

async def is_admin(ctx: commands.Context) -> bool:
    """Check if user is a bot admin, bot owner, or has Manage Server permission.
    
    Returns True if the user:
    - Is the bot owner, OR
    - Is a Red-DiscordBot admin, OR
    - Has the Manage Server (manage_guild) Discord permission
    """
    # Check if bot owner first
    if await ctx.bot.is_owner(ctx.author):
        return True
    
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


class ConversionRateModal(discord.ui.Modal, title="⚙️ Set Conversion Rate"):
    """Modal for setting custom conversion rate."""
    
    rate_input = discord.ui.TextInput(
        label="Conversion Rate",
        placeholder="e.g., 10 (meaning 10 FP = 1 currency)",
        required=True,
        min_length=1,
        max_length=20,
        style=discord.TextStyle.short
    )
    
    def __init__(self, view: "FishSetupView", currency_name: str):
        super().__init__()
        self.view = view
        self.currency_name = currency_name
        self.rate_input.placeholder = f"e.g., 10 (meaning 10 FP = 1 {currency_name})"
    
    async def on_submit(self, interaction: discord.Interaction):
        """Handle modal submission."""
        try:
            rate = float(self.rate_input.value.strip())
            if rate <= 0:
                await interaction.response.send_message(
                    "⚠️ Invalid rate. Rate must be greater than 0.",
                    ephemeral=True
                )
                return
            
            # Save the rate
            self.view.conf.discord_currency_conversion_rate = rate
            self.view.cog.save()
            
            # Format rate display
            if rate >= 1:
                rate_text = f"{rate:g} FP = 1 {self.currency_name}"
            else:
                rate_text = f"1 FP = {1/rate:g} {self.currency_name}"
            
            await interaction.response.send_message(
                f"✅ Conversion rate set to **{rate_text}**",
                ephemeral=True
            )
            
            # Complete setup
            await self.view.message.edit(embed=await self.view.get_complete_embed(), view=None)
            self.view.stop()
            
        except ValueError:
            await interaction.response.send_message(
                "⚠️ Invalid number. Please enter a valid number (decimals allowed).",
                ephemeral=True
            )


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


class FishSetupView(discord.ui.View):
    """Interactive setup view with embed-based steps."""
    
    def __init__(self, cog, ctx: commands.Context, conf):
        super().__init__(timeout=300.0)
        self.cog = cog
        self.ctx = ctx
        self.conf = conf
        self.message = None
        self.current_step = "welcome"
        self.awaiting_timezone = False
        self.awaiting_rate = False
        
        self._setup_welcome_buttons()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("This isn't your setup session!", ephemeral=True)
            return False
        return True
    
    def _setup_welcome_buttons(self):
        """Setup buttons for welcome screen."""
        self.clear_items()
        
        start_btn = discord.ui.Button(
            label="Start Setup",
            emoji="🎣",
            style=discord.ButtonStyle.success,
            row=0
        )
        start_btn.callback = self._start_setup
        self.add_item(start_btn)
        
        cancel_btn = discord.ui.Button(
            label="Cancel",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )
        cancel_btn.callback = self._cancel_setup
        self.add_item(cancel_btn)
    
    def _setup_timezone_buttons(self):
        """Setup buttons for timezone step."""
        self.clear_items()
        
        help_btn = discord.ui.Button(
            label="View Timezones",
            emoji="🌍",
            style=discord.ButtonStyle.primary,
            row=0
        )
        help_btn.callback = self._show_timezone_help
        self.add_item(help_btn)
        
        skip_btn = discord.ui.Button(
            label="Skip",
            emoji="⏭️",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        skip_btn.callback = self._skip_timezone
        self.add_item(skip_btn)
    
    def _setup_hemisphere_buttons(self):
        """Setup buttons for hemisphere selection."""
        self.clear_items()
        
        north_btn = discord.ui.Button(
            label="Northern Hemisphere",
            emoji="🧭",
            style=discord.ButtonStyle.primary,
            row=0
        )
        north_btn.callback = self._select_hemisphere_north
        self.add_item(north_btn)
        
        south_btn = discord.ui.Button(
            label="Southern Hemisphere",
            emoji="🧭",
            style=discord.ButtonStyle.primary,
            row=0
        )
        south_btn.callback = self._select_hemisphere_south
        self.add_item(south_btn)
        
        skip_btn = discord.ui.Button(
            label="Skip",
            emoji="⏭️",
            style=discord.ButtonStyle.secondary,
            row=1
        )
        skip_btn.callback = self._skip_hemisphere
        self.add_item(skip_btn)
    
    def _setup_game_enable_buttons(self):
        """Setup buttons for enabling the game."""
        self.clear_items()
        
        enable_btn = discord.ui.Button(
            label="Enable Game",
            emoji="🟢",
            style=discord.ButtonStyle.success,
            row=0
        )
        enable_btn.callback = self._enable_game
        self.add_item(enable_btn)
        
        disable_btn = discord.ui.Button(
            label="Keep Disabled",
            emoji="🔴",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        disable_btn.callback = self._disable_game
        self.add_item(disable_btn)
    
    def _setup_conversion_buttons(self):
        """Setup buttons for currency conversion."""
        self.clear_items()
        
        enable_btn = discord.ui.Button(
            label="Enable Conversion",
            emoji="💱",
            style=discord.ButtonStyle.success,
            row=0
        )
        enable_btn.callback = self._enable_conversion
        self.add_item(enable_btn)
        
        disable_btn = discord.ui.Button(
            label="Disable Conversion",
            emoji="🚫",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        disable_btn.callback = self._disable_conversion
        self.add_item(disable_btn)
    
    def _setup_rate_buttons(self):
        """Setup buttons for conversion rate."""
        self.clear_items()
        
        custom_btn = discord.ui.Button(
            label="Set Custom Rate",
            emoji="⚙️",
            style=discord.ButtonStyle.primary,
            row=0
        )
        custom_btn.callback = self._set_custom_rate
        self.add_item(custom_btn)
        
        default_btn = discord.ui.Button(
            label="Keep Default",
            emoji="✅",
            style=discord.ButtonStyle.success,
            row=0
        )
        default_btn.callback = self._keep_default_rate
        self.add_item(default_btn)
    
    # Embed generators
    def get_welcome_embed(self) -> discord.Embed:
        """Generate welcome embed."""
        embed = discord.Embed(
            title="🎣 Greenacres Fishing Setup",
            description=(
                "Welcome to the setup wizard for Greenacres Fishing!\n\n"
                "This will guide you through:\n"
                "• Setting your server's timezone\n"
                "• Choosing your hemisphere\n"
                "• Enabling the game\n"
                "• Configuring currency conversion\n\n"
                "Click **Start Setup** to begin!"
            ),
            color=discord.Color.blue()
        )
        return embed
    
    def get_timezone_embed(self) -> discord.Embed:
        """Generate timezone selection embed."""
        embed = discord.Embed(
            title="🌍 Step 1/5: Select Timezone",
            description=(
                f"**Current timezone:** `{self.conf.timezone}`\n\n"
                "Please type your server's timezone in chat.\n"
                "Examples: `America/New_York`, `Europe/London`, `UTC`\n\n"
                "• Click **View Timezones** to browse available timezones\n"
                "• Click **Skip** to keep the current setting\n\n"
                "⏰ **Waiting for your timezone input...**"
            ),
            color=discord.Color.blue()
        )
        return embed
    
    def get_hemisphere_embed(self) -> discord.Embed:
        """Generate hemisphere selection embed."""
        embed = discord.Embed(
            title="🧭 Step 2/5: Select Hemisphere",
            description=(
                f"**Current hemisphere:** `{self.conf.hemisphere.title()}ern`\n\n"
                "This affects season calculation for fish availability.\n\n"
                "Select your hemisphere:"
            ),
            color=discord.Color.blue()
        )
        return embed
    
    def get_game_time_embed(self) -> discord.Embed:
        """Generate game time preview embed."""
        from .helper_functions import get_game_calendar, get_game_time_of_day
        
        calendar = get_game_calendar(self.cog.db, self.ctx.guild)
        time_of_day = get_game_time_of_day(self.cog.db, self.ctx.guild)
        tz = ZoneInfo(self.conf.timezone)
        real_now = datetime.now(tz)
        
        embed = discord.Embed(
            title="📅 Step 3/5: Game Time Preview",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🎮 Game Time",
            value=f"{time_of_day['emoji']} **{time_of_day['name']}** ({time_of_day['hour']:02d}:{time_of_day['minute']:02d})",
            inline=False
        )
        
        embed.add_field(
            name="📅 Game Calendar",
            value=f"Day **{calendar['day_of_season']}** of **{calendar['season']}**, Year **{calendar['year']}**",
            inline=False
        )
        
        embed.add_field(
            name="🌍 Real World",
            value=(
                f"{real_now.strftime('%B %d, %Y at %I:%M %p %Z')}\n"
                f"Hemisphere: {self.conf.hemisphere.title()}ern"
            ),
            inline=False
        )
        
        embed.set_footer(text="You can adjust time settings later with fishset gametime")
        return embed
    
    def get_game_enable_embed(self) -> discord.Embed:
        """Generate game enable embed."""
        status = "🟢 Enabled" if self.conf.is_game_enabled else "🔴 Disabled"
        
        embed = discord.Embed(
            title="🎮 Step 4/5: Enable the Game",
            description=(
                f"**Current status:** {status}\n\n"
                "Would you like to enable Greenacres Fishing for your server?"
            ),
            color=discord.Color.blue()
        )
        return embed
    
    async def get_conversion_embed(self) -> discord.Embed:
        """Generate currency conversion embed."""
        currency_name = await bank.get_currency_name(self.ctx.guild)
        status = "🟢 Enabled" if self.conf.discord_currency_conversion_enabled else "🔴 Disabled"
        
        embed = discord.Embed(
            title="💱 Step 5/5: Currency Conversion",
            description=(
                f"**Current status:** {status}\n\n"
                f"This feature allows players to convert FishPoints ↔ {currency_name}.\n\n"
                "Would you like to enable currency conversion?"
            ),
            color=discord.Color.blue()
        )
        return embed
    
    async def get_rate_embed(self) -> discord.Embed:
        """Generate conversion rate embed."""
        currency_name = await bank.get_currency_name(self.ctx.guild)
        rate = self.conf.discord_currency_conversion_rate
        
        # Format rate display based on value
        if rate >= 1:
            rate_text = f"{rate:g} FP = 1 {currency_name}"
        else:
            rate_text = f"1 FP = {1/rate:g} {currency_name}"
        
        embed = discord.Embed(
            title="⚙️ Set Conversion Rate",
            description=(
                f"**Current rate:** {rate_text}\n\n"
                f"The default rate is 1 FP = 1 {currency_name}.\n\n"
                "Would you like to set a custom rate?\n\n"
                "**Examples:**\n"
                f"• `100` = 100 FP per 1 {currency_name}\n"
                f"• `0.5` = 1 FP per 2 {currency_name}\n"
                f"• `0.1` = 1 FP per 10 {currency_name}\n"
                f"• `0.04` = 1 FP per 25 {currency_name}\n"
                f"• `0.02` = 1 FP per 50 {currency_name}"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Click 'Set Custom Rate' to enter your rate")
        return embed
    
    async def get_complete_embed(self) -> discord.Embed:
        """Generate setup complete embed."""
        currency_name = await bank.get_currency_name(self.ctx.guild)
        
        embed = discord.Embed(
            title="🎣 Setup Complete!",
            color=discord.Color.green()
        )
        
        # Format rate display based on value
        rate = self.conf.discord_currency_conversion_rate
        if rate >= 1:
            rate_text = f"{rate:g} FP = 1 {currency_name}"
        else:
            rate_text = f"1 FP = {1/rate:g} {currency_name}"
        
        embed.add_field(
            name="Configuration Summary",
            value=(
                f"• Game: {'🟢 Enabled' if self.conf.is_game_enabled else '🔴 Disabled'}\n"
                f"• Timezone: `{self.conf.timezone}`\n"
                f"• Hemisphere: `{self.conf.hemisphere.title()}ern`\n"
                f"• Currency Conversion: {'🟢 Enabled' if self.conf.discord_currency_conversion_enabled else '🔴 Disabled'}\n"
                f"• Conversion Rate: {rate_text}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="What's Next?",
            value="Players can now use the `fish` command to start playing!",
            inline=False
        )
        
        return embed
    
    # Button callbacks
    async def _start_setup(self, interaction: discord.Interaction):
        """Start the setup process."""
        self.current_step = "timezone"
        self.awaiting_timezone = True
        self._setup_timezone_buttons()
        await interaction.response.edit_message(embed=self.get_timezone_embed(), view=self)
        
        # Start listening for timezone input
        asyncio.create_task(self._listen_for_timezone())
    
    async def _cancel_setup(self, interaction: discord.Interaction):
        """Cancel setup."""
        embed = discord.Embed(
            title="❌ Setup Cancelled",
            description="You can run `fishsetup` again anytime to configure the game.",
            color=discord.Color.red()
        )
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)
    
    async def _show_timezone_help(self, interaction: discord.Interaction):
        """Show timezone browser."""
        view = TimezoneRegionView(author=self.ctx.author)
        await interaction.response.send_message(embed=view._get_continent_embed(), view=view, ephemeral=True)
    
    async def _skip_timezone(self, interaction: discord.Interaction):
        """Skip timezone step."""
        self.awaiting_timezone = False
        await self._proceed_to_hemisphere(interaction)
    
    async def _listen_for_timezone(self):
        """Listen for timezone input in chat."""
        def check(m: discord.Message) -> bool:
            return m.author.id == self.ctx.author.id and m.channel.id == self.ctx.channel.id
        
        while self.awaiting_timezone and not self.is_finished():
            try:
                msg = await self.cog.bot.wait_for("message", check=check, timeout=120.0)
                timezone_input = msg.content.strip()
                
                # Case-insensitive check
                matching_tz = None
                for tz in available_timezones():
                    if tz.lower() == timezone_input.lower():
                        matching_tz = tz
                        break
                
                if matching_tz:
                    self.conf.timezone = matching_tz
                    self.cog.save()
                    self.awaiting_timezone = False
                    
                    # Send confirmation and proceed
                    await self.ctx.send(f"✅ Timezone set to **{matching_tz}**")
                    self._setup_hemisphere_buttons()
                    await self.message.edit(embed=self.get_hemisphere_embed(), view=self)
                    break
                else:
                    # Ask them to try again
                    await self.ctx.send(
                        f"❌ `{timezone_input}` is not a recognized timezone.\n"
                        "Please try again or click **View Timezones** to browse available options."
                    )
            except asyncio.TimeoutError:
                if self.awaiting_timezone:
                    self.awaiting_timezone = False
                    embed = discord.Embed(
                        title="⏰ Setup Timed Out",
                        description="Run `fishsetup` again to continue.",
                        color=discord.Color.red()
                    )
                    await self.message.edit(embed=embed, view=None)
                    self.stop()
                break
    
    async def _proceed_to_hemisphere(self, interaction: discord.Interaction):
        """Move to hemisphere step."""
        self.current_step = "hemisphere"
        self._setup_hemisphere_buttons()
        await interaction.response.edit_message(embed=self.get_hemisphere_embed(), view=self)
    
    async def _select_hemisphere_north(self, interaction: discord.Interaction):
        """Select northern hemisphere."""
        self.conf.hemisphere = "north"
        self.cog.save()
        await self._proceed_to_game_time(interaction)
    
    async def _select_hemisphere_south(self, interaction: discord.Interaction):
        """Select southern hemisphere."""
        self.conf.hemisphere = "south"
        self.cog.save()
        await self._proceed_to_game_time(interaction)
    
    async def _skip_hemisphere(self, interaction: discord.Interaction):
        """Skip hemisphere step."""
        await self._proceed_to_game_time(interaction)
    
    async def _proceed_to_game_time(self, interaction: discord.Interaction):
        """Show game time preview."""
        self.current_step = "game_time"
        self._setup_game_enable_buttons()
        await interaction.response.edit_message(embed=self.get_game_time_embed(), view=self)
    
    async def _enable_game(self, interaction: discord.Interaction):
        """Enable the game."""
        self.conf.is_game_enabled = True
        self.cog.save()
        await self._proceed_to_conversion(interaction)
    
    async def _disable_game(self, interaction: discord.Interaction):
        """Keep game disabled."""
        self.conf.is_game_enabled = False
        self.cog.save()
        await self._proceed_to_conversion(interaction)
    
    async def _proceed_to_conversion(self, interaction: discord.Interaction):
        """Move to conversion step."""
        self.current_step = "conversion"
        self._setup_conversion_buttons()
        await interaction.response.edit_message(embed=await self.get_conversion_embed(), view=self)
    
    async def _enable_conversion(self, interaction: discord.Interaction):
        """Enable currency conversion."""
        self.conf.discord_currency_conversion_enabled = True
        self.cog.save()
        await self._proceed_to_rate(interaction)
    
    async def _disable_conversion(self, interaction: discord.Interaction):
        """Disable currency conversion."""
        self.conf.discord_currency_conversion_enabled = False
        self.cog.save()
        await self._complete_setup(interaction)
    
    async def _proceed_to_rate(self, interaction: discord.Interaction):
        """Move to rate step."""
        self.current_step = "rate"
        self._setup_rate_buttons()
        await interaction.response.edit_message(embed=await self.get_rate_embed(), view=self)
    
    async def _set_custom_rate(self, interaction: discord.Interaction):
        """Set custom conversion rate."""
        currency_name = await bank.get_currency_name(self.ctx.guild)
        modal = ConversionRateModal(self, currency_name)
        await interaction.response.send_modal(modal)
    
    async def _keep_default_rate(self, interaction: discord.Interaction):
        """Keep default conversion rate."""
        self.awaiting_rate = False  # Cancel any listening task
        await self._complete_setup(interaction)
    
    async def _complete_setup(self, interaction: discord.Interaction):
        """Complete the setup."""
        self.current_step = "complete"
        await interaction.response.edit_message(embed=await self.get_complete_embed(), view=None)
        self.stop()


class Admin(MixinMeta):
    @commands.command(name="fishsetup")
    @commands.admin_or_permissions(administrator=True)
    @commands.guild_only()
    @commands.check(is_admin)
    async def fishsetup(self, ctx: commands.Context):
        """Walk through the initial setup for Greenacres Fishing."""
        conf = self.db.get_conf(ctx.guild)
        
        # Create the setup view
        setup_view = FishSetupView(cog=self, ctx=ctx, conf=conf)
        embed = setup_view.get_welcome_embed()
        message = await ctx.send(embed=embed, view=setup_view)
        setup_view.message = message

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
        # Format rate display based on value
        rate = conf.discord_currency_conversion_rate
        if rate >= 1:
            rate_text = f"{rate:g} FP = 1 {currency_name}"
        else:
            rate_text = f"1 FP = {1/rate:g} {currency_name}"
        
        embed.add_field(
            name="Currency Conversion System",
            value=f"{currency_status}\n💱 Rate: {rate_text}",
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
        
        # Format rate display based on value
        rate = conf.discord_currency_conversion_rate
        if rate >= 1:
            rate_text = f"{rate:g} FP = 1 {currency_name}"
        else:
            rate_text = f"1 FP = {1/rate:g} {currency_name}"
        
        await ctx.send(
            f"💱 Currency conversion is now {status}\n"
            f"Rate: **{rate_text}**"
        )

    @fishset.command(name="setrate")
    @commands.check(is_admin)
    async def set_conversion_rate(self, ctx: commands.Context, rate: float):
        """Set the FishPoints to Discord currency conversion rate.
        
        Examples:
        - `fishset setrate 100` = 100 FP per 1 currency
        - `fishset setrate 0.5` = 1 FP per 2 currency
        - `fishset setrate 0.1` = 1 FP per 10 currency
        """
        if rate <= 0:
            await ctx.send("❌ Rate must be a positive number.")
            return
        
        conf = self.db.get_conf(ctx.guild)
        old_rate = conf.discord_currency_conversion_rate
        conf.discord_currency_conversion_rate = rate
        self.save()
        
        currency_name = await bank.get_currency_name(ctx.guild)
        
        # Format new rate display
        if rate >= 1:
            new_rate_text = f"{rate:g} FP = 1 {currency_name}"
        else:
            new_rate_text = f"1 FP = {1/rate:g} {currency_name}"
        
        # Format old rate display
        if old_rate >= 1:
            old_rate_text = f"{old_rate:g} FP = 1 {currency_name}"
        else:
            old_rate_text = f"1 FP = {1/old_rate:g} {currency_name}"
        
        await ctx.send(f"✅ Conversion rate updated: **{new_rate_text}** (was {old_rate_text})")

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
    
    @fishset.command(name="debug")
    @commands.is_owner()
    async def set_debug(self, ctx: commands.Context, user: discord.Member):
        """Toggle debug mode for a user.
        
        When enabled:
        - Shows detailed catch info (ephemeral message to user)
        - Logs all catches to debug log in memory
        - Use for testing token rewards and catch mechanics
        
        Examples:
            [p]fishset debug @User - Toggle debug mode
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        user_data.debug_mode = not user_data.debug_mode
        self.save()
        
        status = "enabled" if user_data.debug_mode else "disabled"
        await ctx.send(
            f"✅ Debug mode **{status}** for {user.mention}\n"
            f"{'Debug info will be shown after each catch and logged to memory.' if user_data.debug_mode else 'Debug mode turned off.'}"
        )
    
    @fishset.command(name="spawnfish")
    @commands.is_owner()
    async def spawn_fish(self, ctx: commands.Context, user: discord.Member, fish_id: str, weight: str = "random", length: str = "random"):
        """Queue a specific fish for a user's next catch (testing).
        
        Parameters:
        - user: The user who will catch this fish
        - fish_id: ID of the fish (e.g., largemouth_bass, red_snapper)
        - weight: "max", "random", or specific oz value (e.g., "200")
        - length: "max", "random", or specific inches value (e.g., "25.5")
        
        Examples:
            [p]fishset spawnfish @User largemouth_bass max max
            [p]fishset spawnfish @User red_snapper max random
            [p]fishset spawnfish @User bluegill 50 8.5
        """
        from ..databases.fish import FISH_DATABASE
        
        # Validate fish ID
        if fish_id not in FISH_DATABASE:
            available = ", ".join(sorted(FISH_DATABASE.keys())[:10])
            await ctx.send(
                f"❌ Unknown fish ID: `{fish_id}`\n"
                f"Available fish IDs: {available}... (use `!fish` command to see all)"
            )
            return
        
        fish_data = FISH_DATABASE[fish_id]
        fish_name = fish_data.get("name", fish_id)
        
        # Validate weight parameter
        if weight not in ["max", "random"]:
            try:
                weight_val = float(weight)
                if weight_val <= 0:
                    await ctx.send("❌ Weight must be positive.")
                    return
            except ValueError:
                await ctx.send('❌ Weight must be "max", "random", or a number.')
                return
        
        # Validate length parameter
        if length not in ["max", "random"]:
            try:
                length_val = float(length)
                if length_val <= 0:
                    await ctx.send("❌ Length must be positive.")
                    return
            except ValueError:
                await ctx.send('❌ Length must be "max", "random", or a number.')
                return
        
        # Queue the spawn
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        user_data.pending_spawn = {
            "fish_id": fish_id,
            "weight": weight,
            "length": length
        }
        self.save()
        
        # Build confirmation message
        max_weight = fish_data.get("max_weight_oz", 0)
        max_length = fish_data.get("max_length_inches", 0)
        
        weight_display = f"max ({max_weight} oz / {max_weight/16:.2f} lbs)" if weight == "max" else (weight if weight == "random" else f"{weight} oz")
        length_display = f"max ({max_length} inches)" if length == "max" else (length if length == "random" else f"{length} inches")
        
        await ctx.send(
            f"✅ Queued **{fish_name}** for {user.mention}'s next catch\n"
            f"Weight: {weight_display}\n"
            f"Length: {length_display}"
        )
    
    @fishset.command(name="debugdownload")
    @commands.is_owner()
    async def debug_download(self, ctx: commands.Context):
        """Download the fishing debug log.
        
        The log contains detailed information about all catches 
        made while debug mode was enabled for users.
        Note: Log is stored in memory and will be cleared on cog reload.
        """
        if not self.debug_log:
            await ctx.send("❌ No debug log entries. Debug mode must be enabled for at least one user who has caught fish.")
            return
        
        try:
            # Create BytesIO buffer with formatted JSON
            buffer = BytesIO()
            formatted_json = json.dumps(self.debug_log, indent=2)
            buffer.write(formatted_json.encode('utf-8'))
            buffer.seek(0)  # Reset to beginning for reading
            
            await ctx.send(
                f"📊 Fishing debug log ({len(self.debug_log):,} entries):", 
                file=discord.File(buffer, filename="fishing_debug_export.json")
            )
        except Exception as e:
            await ctx.send(f"❌ Error creating debug log: {e}")
    
    @fishset.command(name="debugclear")
    @commands.is_owner()
    async def debug_clear(self, ctx: commands.Context):
        """Clear the fishing debug log.
        
        This permanently removes all debug log entries from memory.
        """
        if not self.debug_log:
            await ctx.send("❌ No debug log entries to clear.")
            return
        
        entry_count = len(self.debug_log)
        self.debug_log.clear()
        await ctx.send(f"✅ Debug log cleared ({entry_count:,} entries removed).")

    @fishset.command(name="listfish")
    async def list_fish(self, ctx: commands.Context, water_type: str = None):
        """Display a paginated list of all fish in the database.
        
        Parameters:
        - water_type: Optional filter - "freshwater", "saltwater", or "both"
        
        If no filter is provided, all fish are shown sorted by water type then alphabetically.
        
        Examples:
            [p]fishset listfish - Show all fish
            [p]fishset listfish freshwater - Show only freshwater fish
            [p]fishset listfish saltwater - Show only saltwater fish
        """
        from ..databases.fish import FISH_DATABASE
        
        # Validate water_type input
        valid_types = ["freshwater", "saltwater", "both", None]
        if water_type and water_type.lower() not in ["freshwater", "saltwater", "both"]:
            await ctx.send("❌ Invalid water type. Use `freshwater`, `saltwater`, `both`, or leave empty for all fish.")
            return
        
        water_filter = water_type.lower() if water_type else None
        
        # Build fish list dynamically from database
        fish_list = []
        for fish_id, fish_data in FISH_DATABASE.items():
            fish_water = fish_data.get("water_type", "unknown")
            
            # Apply filter
            if water_filter and water_filter != "both":
                if fish_water != water_filter:
                    continue
            
            fish_list.append({
                "id": fish_id,
                "name": fish_data.get("name", fish_id),
                "water_type": fish_water,
                "rarity": fish_data.get("rarity", "common"),
                "locations": fish_data.get("locations", []),
                "max_weight_oz": fish_data.get("max_weight_oz", 0),
                "max_length_inches": fish_data.get("max_length_inches", 0),
                "base_fishpoints": fish_data.get("base_fishpoints", 0),
            })
        
        if not fish_list:
            await ctx.send("❌ No fish found matching that filter.")
            return
        
        # Sort by water type, then alphabetically by name
        fish_list.sort(key=lambda f: (f["water_type"], f["name"].lower()))
        
        # Create and send the view
        view = FishListView(cog=self, author=ctx.author, fish_list=fish_list, water_filter=water_filter)
        embed = view.create_embed()
        message = await ctx.send(embed=embed, view=view)
        view.message = message


class FishListView(discord.ui.View):
    """Paginated view for displaying fish list."""
    
    FISH_PER_PAGE = 10
    
    def __init__(self, cog, author: discord.Member, fish_list: list, water_filter: str = None):
        super().__init__(timeout=300.0)  # 5 minute timeout
        self.cog = cog
        self.author = author
        self.fish_list = fish_list
        self.water_filter = water_filter
        self.page = 0
        self.total_pages = (len(fish_list) + self.FISH_PER_PAGE - 1) // self.FISH_PER_PAGE
        self.message = None
        
        self._update_buttons()
    
    def _update_buttons(self):
        """Update button states based on current page."""
        self.prev_button.disabled = (self.page == 0)
        self.next_button.disabled = (self.page >= self.total_pages - 1)
        self.page_indicator.label = f"Page {self.page + 1}/{self.total_pages}"
    
    def create_embed(self) -> discord.Embed:
        """Create the embed for the current page."""
        # Calculate slice for current page
        start_idx = self.page * self.FISH_PER_PAGE
        end_idx = start_idx + self.FISH_PER_PAGE
        page_fish = self.fish_list[start_idx:end_idx]
        
        # Build title
        if self.water_filter:
            title = f"Fish Database - {self.water_filter.title()}"
        else:
            title = "Fish Database - All Fish"
        
        embed = discord.Embed(
            title=title,
            description=f"{len(self.fish_list)} fish total",
            color=discord.Color.blue()
        )
        
        # Build fish list - one line per fish, no emojis
        fish_lines = []
        for fish in page_fish:
            # Format weight
            max_oz = fish["max_weight_oz"]
            if max_oz >= 16:
                weight_str = f"{max_oz/16:.1f}lbs"
            else:
                weight_str = f"{max_oz:.1f}oz"
            
            # Water type abbreviation
            water = "SW" if fish["water_type"] == "saltwater" else "FW"
            
            # Rarity abbreviation
            rarity_abbrev = {
                "common": "C",
                "uncommon": "U", 
                "rare": "R",
                "epic": "E",
                "legendary": "L"
            }
            rarity = rarity_abbrev.get(fish["rarity"], "C")
            
            fish_lines.append(
                f"`{fish['id']}` - {fish['name']} [{water}/{rarity}] {weight_str}, {fish['max_length_inches']:.1f}in"
            )
        
        embed.add_field(
            name="Fish",
            value="\n".join(fish_lines) if fish_lines else "No fish on this page.",
            inline=False
        )
        
        embed.set_footer(text=f"Page {self.page + 1}/{self.total_pages} | FW=Freshwater, SW=Saltwater | C/U/R/E/L=Rarity")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the command author to interact."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This menu isn't for you!", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        """Handle timeout - disable all buttons."""
        self.stop()
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
            except discord.HTTPException:
                pass
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.secondary, row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to previous page."""
        self.page = max(0, self.page - 1)
        self._update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Page 1/1", style=discord.ButtonStyle.secondary, disabled=True, row=0)
    async def page_indicator(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Page indicator (non-interactive)."""
        pass
    
    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Go to next page."""
        self.page = min(self.total_pages - 1, self.page + 1)
        self._update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, row=0)
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the view."""
        self.stop()
        await interaction.response.edit_message(view=None)