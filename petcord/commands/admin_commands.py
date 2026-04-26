"""
Admin commands for Petcord cog.
"""

from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo, available_timezones

import discord
from discord.ui import Button, View
from redbot.core import bank, commands
from redbot.core.commands import Context
from redbot.core.utils.views import SimpleMenu
from typing import TYPE_CHECKING, Optional

from ..abc import MixinMeta
from ..views.setup_wizard import PetcordSetupView

if TYPE_CHECKING:
    pass


# =============================================================================
# TIMEZONE CONFIGURATION
# =============================================================================

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


# =============================================================================
# UI VIEWS
# =============================================================================

class TimezoneRegionView(View):
    """View for selecting a timezone region, then browsing timezones within it."""
    
    def __init__(self, author: discord.Member):
        super().__init__(timeout=180.0)
        self.author = author
        self.message: Optional[discord.Message] = None
        self.current_region: Optional[str] = None
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
            content="Timezone browser closed. Use the command with a timezone name to set it.",
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
            await interaction.response.send_message("This isn't your timezone browser!", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(
                    content="Timezone browser timed out.",
                    embed=None,
                    view=None
                )
            except discord.NotFound:
                pass


class ClearAllTimersConfirmView(View):
    """Confirmation view for clearing all timers."""
    
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.confirmed = False
        self.message: Optional[discord.Message] = None
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "Only the command author can use these buttons.",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm_button(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_button(self, interaction: discord.Interaction, button: Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
    
    async def on_timeout(self):
        self.confirmed = False
        if self.message:
            try:
                await self.message.edit(
                    embed=discord.Embed(
                        title="⏱️ Timed Out",
                        description="Confirmation timed out. No timers were cleared.",
                        color=discord.Color.grey()
                    ),
                    view=None
                )
            except discord.NotFound:
                pass


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


class AdminCommands(MixinMeta):
    """Admin commands for Petcord configuration."""

    @commands.command(name="petsetup")
    @commands.check(is_admin)
    @commands.guild_only()
    async def petsetup(self, ctx: Context) -> None:
        """Interactive setup wizard for Petcord.

        Walks you through the four core settings:
        1. Notification channel
        2. Default home capacity
        3. Pet death toggle
        4. Enable the game

        Each step saves immediately. You can re-run this command at any time
        to review or change settings. Use `pcset` commands for finer control.
        """
        conf = self.db.get_conf(ctx.guild)
        view = PetcordSetupView(cog=self, conf=conf, author_id=ctx.author.id)
        embed = view._build_embed()
        view.message = await ctx.send(embed=embed, view=view)

    @commands.group(name="pcset", invoke_without_command=True)
    @commands.check(is_admin)
    @commands.guild_only()
    async def pcset(self, ctx: Context) -> None:
        """Petcord admin settings and commands."""
        prefix = ctx.clean_prefix
        cmds = sorted(ctx.command.commands, key=lambda c: c.name)
        cmds_per_page = 10
        total_pages = max(1, -(-len(cmds) // cmds_per_page))
        pages = []
        for i in range(0, max(1, len(cmds)), cmds_per_page):
            chunk = cmds[i:i + cmds_per_page]
            page_num = i // cmds_per_page + 1
            embed = discord.Embed(
                title="⚙️ Petcord Admin Commands",
                description=f"Use `{prefix}pcset <command>` to run a command.",
                color=discord.Color.blue(),
            )
            embed.set_footer(text=f"Page {page_num}/{total_pages}")
            for cmd in chunk:
                brief = cmd.brief or (cmd.help.splitlines()[0] if cmd.help else "No description.")
                aliases = f" | aliases: {', '.join(cmd.aliases)}" if cmd.aliases else ""
                embed.add_field(
                    name=f"`{prefix}pcset {cmd.name}`{aliases}",
                    value=brief,
                    inline=False,
                )
            pages.append(embed)
        await SimpleMenu(pages, disable_after_timeout=True).start(ctx)
    
    @pcset.command(name="enable")
    async def pcset_enable(self, ctx: Context) -> None:
        """Enable Petcord in this server."""
        conf = self.db.get_conf(ctx.guild)
        
        if conf.game_is_enabled:
            await ctx.send("🎮 Petcord is already enabled in this server.")
            return
        
        conf.game_is_enabled = True
        self.schedule_save()
        await ctx.send("✅ Petcord is now **enabled** in this server!")
    
    @pcset.command(name="disable")
    async def pcset_disable(self, ctx: Context) -> None:
        """Disable Petcord in this server."""
        conf = self.db.get_conf(ctx.guild)
        
        if not conf.game_is_enabled:
            await ctx.send("🎮 Petcord is already disabled in this server.")
            return
        
        conf.game_is_enabled = False
        self.schedule_save()
        await ctx.send("❌ Petcord is now **disabled** in this server.")
    
    @pcset.command(name="cleartimer", aliases=["clearcd", "resetcooldown"])
    async def pcset_cleartimer(self, ctx: Context, user: discord.Member) -> None:
        """Clear the pet finding cooldown for a user.
        
        This removes the cooldown that occurs when a user passes on a pet.
        
        **Arguments:**
        - `<user>` - The user to clear the cooldown for.
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        if user_data.last_pet_declined <= 0:
            await ctx.send(f"⏱️ **{user.display_name}** doesn't have an active cooldown.")
            return
        
        user_data.last_pet_declined = 0
        self.schedule_save()
        
        await ctx.send(f"✅ Cleared the pet finding cooldown for **{user.display_name}**.")
    
    @pcset.command(name="clearalltimers")
    async def pcset_clearalltimers(self, ctx: Context) -> None:
        """Clear ALL cooldowns for ALL users in this server.
        
        This resets:
        - Pet finding cooldowns (from declining pets)
        - All care action cooldowns (feed, play, groom, rest, treat, pet)
        
        This does NOT affect:
        - Pet age or growth progress
        - Pet stats (hunger, happiness, etc.)
        - Graduation status
        
        **Requires confirmation before executing.**
        """
        conf = self.db.get_conf(ctx.guild)
        
        if not conf.users:
            await ctx.send("❌ No users have Petcord data in this server.")
            return
        
        # Create confirmation view
        view = ClearAllTimersConfirmView(ctx.author.id)
        
        embed = discord.Embed(
            title="⚠️ Clear All Timers - Confirmation Required",
            description=(
                "This will reset **ALL** cooldowns for **ALL** users:\n\n"
                "**Will be cleared:**\n"
                "• Pet finding cooldowns\n"
                "• Feed, Play, Groom, Rest, Treat, Pet cooldowns\n\n"
                "**Will NOT be affected:**\n"
                "• Pet age/growth progress\n"
                "• Pet stats (hunger, happiness, etc.)\n"
                "• Graduation status\n\n"
                f"**Users affected:** {len(conf.users)}"
            ),
            color=discord.Color.orange()
        )
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message
        
        # Wait for response
        await view.wait()
        
        if not view.confirmed:
            await message.edit(
                embed=discord.Embed(
                    title="❌ Cancelled",
                    description="No timers were cleared.",
                    color=discord.Color.red()
                ),
                view=None
            )
            return
        
        # Clear all timers
        users_cleared = 0
        pets_cleared = 0
        
        for user_id, user_data in conf.users.items():
            # Clear pet finding cooldown
            user_data.last_pet_declined = 0
            users_cleared += 1
            
            # Clear current pet's action cooldowns
            if user_data.current_pet:
                pet = user_data.current_pet
                pet.last_fed = 0
                pet.last_played = 0
                pet.last_groomed = 0
                pet.last_rested = 0
                pet.last_treated = 0
                pet.last_petted = 0
                pets_cleared += 1
            
            # Clear home pets' action cooldowns too
            for home_pet in user_data.home_pets:
                home_pet.last_fed = 0
                home_pet.last_played = 0
                home_pet.last_groomed = 0
                home_pet.last_rested = 0
                home_pet.last_treated = 0
                home_pet.last_petted = 0
                pets_cleared += 1
        
        self.schedule_save()
        
        await message.edit(
            embed=discord.Embed(
                title="✅ All Timers Cleared",
                description=(
                    f"Successfully reset all cooldowns!\n\n"
                    f"• **Users affected:** {users_cleared}\n"
                    f"• **Pets affected:** {pets_cleared}"
                ),
                color=discord.Color.green()
            ),
            view=None
        )
    
    @pcset.command(name="clearsleep", aliases=["resetsleep"])
    async def pcset_clearsleep(self, ctx: Context, target: Optional[str] = None) -> None:
        """Clear the Owner Sleep daily usage restriction.
        
        This removes the "Use Tomorrow" restriction, allowing users to
        activate Owner Sleep again today. Does NOT cancel any currently
        active sleep pause - those continue until their timer expires.
        
        **Arguments:**
        - No argument: Clears for yourself (the command author)
        - `all`: Clears for ALL users in the server
        - `<user>`: Clears for a specific user (mention or ID)
        
        **Examples:**
        - `[p]pcset clearsleep` - Clear your own restriction
        - `[p]pcset clearsleep all` - Clear for everyone
        - `[p]pcset clearsleep @User` - Clear for a specific user
        """
        conf = self.db.get_conf(ctx.guild)
        
        # No argument = self
        if target is None:
            user_data = conf.get_user(ctx.author)
            if user_data.current_pet is None:
                await ctx.send("🐾 You don't have a pet.")
                return
            
            old_date = user_data.current_pet.last_owner_sleep_date
            if not old_date:
                await ctx.send("😴 You don't have an Owner Sleep restriction to clear.")
                return
            
            user_data.current_pet.last_owner_sleep_date = ""
            self.schedule_save()
            await ctx.send(
                f"✅ Cleared your Owner Sleep restriction.\n"
                f"You can now use Owner Sleep again today."
            )
            return
        
        # "all" argument = all users
        if target.lower() == "all":
            users_cleared = 0
            for user_id, user_data in conf.users.items():
                if user_data.current_pet and user_data.current_pet.last_owner_sleep_date:
                    user_data.current_pet.last_owner_sleep_date = ""
                    users_cleared += 1
                # Also clear for home pets (they have the field too)
                for home_pet in user_data.home_pets:
                    if home_pet.last_owner_sleep_date:
                        home_pet.last_owner_sleep_date = ""
            
            self.schedule_save()
            await ctx.send(
                f"✅ Cleared Owner Sleep restriction for **{users_cleared}** users.\n"
                f"They can now use Owner Sleep again today."
            )
            return
        
        # Try to parse as a user mention or ID
        user: Optional[discord.Member] = None
        
        # Check if it's a mention
        if target.startswith("<@") and target.endswith(">"):
            user_id_str = target.strip("<@!>")
            try:
                user_id = int(user_id_str)
                user = ctx.guild.get_member(user_id)
            except ValueError:
                pass
        else:
            # Try as a raw user ID
            try:
                user_id = int(target)
                user = ctx.guild.get_member(user_id)
            except ValueError:
                # Try as a username
                user = discord.utils.find(
                    lambda m: m.name.lower() == target.lower() or 
                              m.display_name.lower() == target.lower(),
                    ctx.guild.members
                )
        
        if user is None:
            await ctx.send(f"❌ Could not find user: `{target}`")
            return
        
        user_data = conf.get_user(user)
        if user_data.current_pet is None:
            await ctx.send(f"🐾 **{user.display_name}** doesn't have a pet.")
            return
        
        old_date = user_data.current_pet.last_owner_sleep_date
        if not old_date:
            await ctx.send(f"😴 **{user.display_name}** doesn't have an Owner Sleep restriction to clear.")
            return
        
        user_data.current_pet.last_owner_sleep_date = ""
        self.schedule_save()
        await ctx.send(
            f"✅ Cleared Owner Sleep restriction for **{user.display_name}**.\n"
            f"They can now use Owner Sleep again today."
        )
    
    @pcset.command(name="maxout")
    async def pcset_maxout(self, ctx: Context, user: discord.Member) -> None:
        """Set a user's current pet stats to 100%.
        
        This restores all pet stats (hunger, health, happiness, 
        cleanliness, energy) to their maximum values.
        
        **Arguments:**
        - `<user>` - The user whose pet should be maxed out.
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        if user_data.current_pet is None:
            await ctx.send(f"🐾 **{user.display_name}** doesn't have a current pet.")
            return
        
        pet = user_data.current_pet
        pet.hunger = 100
        pet.health = 100
        pet.happiness = 100
        pet.cleanliness = 100
        pet.energy = 100
        self.schedule_save()
        
        await ctx.send(
            f"✅ **{pet.name}**'s stats have been maxed out!\n"
            f"🍖 Hunger: 100% | ❤️ Health: 100% | 😊 Happiness: 100% | ✨ Clean: 100% | ⚡ Energy: 100%"
        )
    
    @pcset.command(name="heal")
    async def pcset_heal(self, ctx: Context, target: str, amount: Optional[str] = None) -> None:
        """Heal pet health for yourself, a user, or all users.
        
        **Usage:**
        - `[p]pcset heal self` - Max your pet's health to 100
        - `[p]pcset heal all full` - Max all users' pets health to 100
        - `[p]pcset heal all <amount>` - Add health points to all pets
        - `[p]pcset heal <user> <amount>` - Add health points to a user's pet
        - `[p]pcset heal <user> full` - Max a user's pet health to 100
        
        **Examples:**
        - `[p]pcset heal self` - Restore your pet to full health
        - `[p]pcset heal all 10` - Give all pets +10 health
        - `[p]pcset heal all full` - Max everyone's pet health
        - `[p]pcset heal @User 25` - Give a user's pet +25 health
        """
        conf = self.db.get_conf(ctx.guild)
        
        # Handle "self" - max out author's pet
        if target.lower() == "self":
            user_data = conf.get_user(ctx.author)
            if user_data.current_pet is None:
                await ctx.send("🐾 You don't have a pet being raised.")
                return
            
            pet = user_data.current_pet
            old_health = pet.health
            pet.health = 100
            self.schedule_save()
            
            await ctx.send(
                f"❤️ **{pet.name}**'s health restored to full!\n"
                f"Health: {old_health:.0f}% → 100%"
            )
            return
        
        # Handle "all" - heal all users' pets
        if target.lower() == "all":
            if amount is None:
                await ctx.send("❌ Please specify an amount or `full`.\nExample: `[p]pcset heal all 10` or `[p]pcset heal all full`")
                return
            
            pets_healed = 0
            
            if amount.lower() == "full":
                # Max out all pets
                for user_id, user_data in conf.users.items():
                    if user_data.current_pet:
                        user_data.current_pet.health = 100
                        pets_healed += 1
                
                self.schedule_save()
                await ctx.send(f"❤️ Maxed health to 100% for **{pets_healed}** pets!")
            else:
                # Add specific amount
                try:
                    heal_amount = int(amount)
                except ValueError:
                    await ctx.send("❌ Amount must be a number or `full`.")
                    return
                
                if heal_amount <= 0:
                    await ctx.send("❌ Amount must be positive.")
                    return
                
                for user_id, user_data in conf.users.items():
                    if user_data.current_pet:
                        user_data.current_pet.health = min(100, user_data.current_pet.health + heal_amount)
                        pets_healed += 1
                
                self.schedule_save()
                await ctx.send(f"❤️ Added **+{heal_amount}** health to **{pets_healed}** pets! (capped at 100)")
            return
        
        # Handle <user> <amount> - heal specific user's pet
        if amount is None:
            await ctx.send("❌ Please specify an amount or `full`.\nExample: `[p]pcset heal @User 10` or `[p]pcset heal @User full`")
            return
        
        # Try to parse user
        user: Optional[discord.Member] = None
        
        if target.startswith("<@") and target.endswith(">"):
            user_id_str = target.strip("<@!>")
            try:
                user_id = int(user_id_str)
                user = ctx.guild.get_member(user_id)
            except ValueError:
                pass
        else:
            try:
                user_id = int(target)
                user = ctx.guild.get_member(user_id)
            except ValueError:
                user = discord.utils.find(
                    lambda m: m.name.lower() == target.lower() or 
                              m.display_name.lower() == target.lower(),
                    ctx.guild.members
                )
        
        if user is None:
            await ctx.send(f"❌ Could not find user: `{target}`")
            return
        
        user_data = conf.get_user(user)
        if user_data.current_pet is None:
            await ctx.send(f"🐾 **{user.display_name}** doesn't have a pet being raised.")
            return
        
        pet = user_data.current_pet
        old_health = pet.health
        
        if amount.lower() == "full":
            pet.health = 100
            self.schedule_save()
            await ctx.send(
                f"❤️ **{pet.name}**'s health restored to full!\n"
                f"Health: {old_health:.0f}% → 100%"
            )
        else:
            try:
                heal_amount = int(amount)
            except ValueError:
                await ctx.send("❌ Amount must be a number or `full`.")
                return
            
            if heal_amount <= 0:
                await ctx.send("❌ Amount must be positive.")
                return
            
            pet.health = min(100, pet.health + heal_amount)
            self.schedule_save()
            await ctx.send(
                f"❤️ Healed **{pet.name}** for **+{heal_amount}** health!\n"
                f"Health: {old_health:.0f}% → {pet.health:.0f}%"
            )
    
    @pcset.command(name="setstat")
    async def pcset_setstat(
        self, 
        ctx: Context, 
        user: discord.Member, 
        stat: str, 
        value: int
    ) -> None:
        """Set a specific stat for a user's current pet.
        
        Useful for testing notifications and decay. Setting stats low
        will trigger tier change notifications if the user has them enabled.
        
        **Arguments:**
        - `<user>` - The user whose pet to modify.
        - `<stat>` - The stat to set: hunger, happiness, cleanliness, energy, health, or bond.
        - `<value>` - The value to set (0-100, or 0-200 for bond).
        
        **Examples:**
        - `[p]pcset setstat @User hunger 50` - Set hunger to 50%
        - `[p]pcset setstat @User energy 25` - Set energy to 25% (will trigger low warning)
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        if user_data.current_pet is None:
            await ctx.send(f"🐾 **{user.display_name}** doesn't have a current pet.")
            return
        
        pet = user_data.current_pet
        stat = stat.lower()
        
        # Validate stat name
        valid_stats = ["hunger", "happiness", "cleanliness", "energy", "health", "bond"]
        if stat not in valid_stats:
            await ctx.send(f"❌ Invalid stat. Choose from: {', '.join(valid_stats)}")
            return
        
        # Validate value range
        max_value = 200 if stat == "bond" else 100
        if not 0 <= value <= max_value:
            await ctx.send(f"❌ Value must be between 0 and {max_value}.")
            return
        
        # Set the stat
        old_value = getattr(pet, stat)
        setattr(pet, stat, value)
        self.schedule_save()
        
        # Emoji mapping
        emoji_map = {
            "hunger": "🍖",
            "happiness": "😊", 
            "cleanliness": "✨",
            "energy": "⚡",
            "health": "❤️",
            "bond": "💕"
        }
        emoji = emoji_map.get(stat, "📊")
        
        await ctx.send(
            f"✅ Set **{pet.name}**'s {emoji} {stat.title()} from **{old_value}** → **{value}**\n"
            f"💡 Run `{ctx.clean_prefix}petcord` or wait for decay cycle to trigger notifications."
        )
    
    @pcset.command(name="setstats")
    async def pcset_setstats(
        self, 
        ctx: Context, 
        user: discord.Member, 
        value: int
    ) -> None:
        """Set ALL stats for a user's current pet to the same value.
        
        Quick way to test notifications by setting all stats low at once.
        
        **Arguments:**
        - `<user>` - The user whose pet to modify.
        - `<value>` - The value to set all stats to (0-100).
        
        **Examples:**
        - `[p]pcset setstats @User 50` - Set all stats to 50%
        - `[p]pcset setstats @User 35` - Set all stats to 35% (fair tier)
        - `[p]pcset setstats @User 15` - Set all stats to 15% (critical!)
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        if user_data.current_pet is None:
            await ctx.send(f"🐾 **{user.display_name}** doesn't have a current pet.")
            return
        
        if not 0 <= value <= 100:
            await ctx.send("❌ Value must be between 0 and 100.")
            return
        
        pet = user_data.current_pet
        pet.hunger = value
        pet.happiness = value
        pet.cleanliness = value
        pet.energy = value
        pet.health = value
        self.schedule_save()
        
        await ctx.send(
            f"✅ Set **{pet.name}**'s stats to **{value}%**!\n"
            f"🍖 Hunger: {value}% | ❤️ Health: {value}% | 😊 Happiness: {value}% | "
            f"✨ Clean: {value}% | ⚡ Energy: {value}%\n"
            f"💡 Run `{ctx.clean_prefix}petcord` or wait for decay cycle to trigger notifications."
        )
    
    @pcset.command(name="triggerdecay", aliases=["decay"])
    async def pcset_triggerdecay(self, ctx: Context) -> None:
        """Manually trigger a decay cycle for testing.
        
        This runs the decay task immediately, which will:
        - Apply stat decay to all pets
        - Check for tier changes and send notifications
        - Check for danger warnings
        - Age pets if a day has passed
        """
        await ctx.send("⏳ Triggering decay cycle...")
        
        try:
            await self.decay_task._process_all_guilds()
            await ctx.send("✅ Decay cycle complete! Check for notifications in the allowed channel.")
        except Exception as e:
            await ctx.send(f"❌ Error during decay: {e}")

    @pcset.command(name="clearpet", aliases=["removepet", "deletepet"])
    async def pcset_clearpet(self, ctx: Context, user: discord.Member) -> None:
        """Remove a user's current pet without penalty.
        
        This removes the pet completely without recording it as a death
        or affecting the user's stats negatively. Useful for testing or
        resolving issues.
        
        **Arguments:**
        - `<user>` - The user whose pet should be removed.
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        if user_data.current_pet is None:
            await ctx.send(f"🐾 **{user.display_name}** doesn't have a current pet.")
            return
        
        pet_name = user_data.current_pet.name
        species_id = user_data.current_pet.species_id
        
        # Simply remove the pet without any negative consequences
        user_data.current_pet = None
        self.schedule_save()
        
        await ctx.send(
            f"✅ Removed **{pet_name}** ({species_id.replace('_', ' ').title()}) "
            f"from **{user.display_name}** without penalty."
        )
    
    @pcset.command(name="cooldown")
    async def pcset_cooldown(self, ctx: Context, minutes: int) -> None:
        """Set the cooldown duration for passing on pets.
        
        **Arguments:**
        - `<minutes>` - Cooldown duration in minutes (1-1440).
        """
        if not 1 <= minutes <= 1440:
            await ctx.send("❌ Cooldown must be between 1 and 1440 minutes (24 hours).")
            return
        
        conf = self.db.get_conf(ctx.guild)
        conf.find_cooldown_minutes = minutes
        self.schedule_save()
        
        await ctx.send(f"✅ Pet finding cooldown set to **{minutes} minutes**.")
    
    @pcset.command(name="display", aliases=["settings", "showsettings"])
    async def pcset_display(self, ctx: Context) -> None:
        """View current Petcord settings for this server."""
        conf = self.db.get_conf(ctx.guild)
        
        embed = discord.Embed(
            title="⚙️ Petcord Settings",
            color=discord.Color.blue()
        )
        
        # Game status
        status = "✅ Enabled" if conf.game_is_enabled else "❌ Disabled"
        embed.add_field(name="Game Status", value=status, inline=True)
        
        # Cooldown
        embed.add_field(
            name="Find Cooldown", 
            value=f"{conf.find_cooldown_minutes} minutes", 
            inline=True
        )
        
        # Notification channel
        if conf.allowed_channel_id:
            channel_display = f"<#{conf.allowed_channel_id}>"
        else:
            channel_display = "Not set"
        embed.add_field(name="Notification Channel", value=channel_display, inline=True)
        
        # Death settings
        death_status = "⚠️ Enabled" if conf.pet_death_enabled else "🛡️ Disabled"
        embed.add_field(name="Pet Death", value=death_status, inline=True)
        
        # Home capacity
        embed.add_field(
            name="Default Home Capacity",
            value=f"{conf.default_home_capacity} pets",
            inline=True
        )
        
        # Medal thresholds
        embed.add_field(
            name="Medal Thresholds",
            value=f"🥇 Gold: {conf.medal_gold_threshold}%\n"
                  f"🥈 Silver: {conf.medal_silver_threshold}%\n"
                  f"🥉 Bronze: {conf.medal_bronze_threshold}%",
            inline=True
        )
        
        # Growth settings
        embed.add_field(
            name="Growth Day Length",
            value=f"{conf.growth_day_length_hours} hours",
            inline=True
        )
        
        # User count
        user_count = len(conf.users)
        embed.add_field(name="Registered Users", value=str(user_count), inline=True)
        
        # Gift cooldown
        embed.add_field(
            name="Gift Cooldown",
            value=f"{conf.gift_cooldown_hours} hours",
            inline=True
        )
        
        # Timezone
        try:
            tz = ZoneInfo(conf.discord_server_timezone)
            now_in_tz = datetime.now(tz)
            tz_display = f"`{conf.discord_server_timezone}`\n{now_in_tz.strftime('%I:%M %p')}"
        except Exception:
            tz_display = f"`{conf.discord_server_timezone}` (invalid)"
        embed.add_field(
            name="Server Timezone",
            value=tz_display,
            inline=True
        )
        
        # Petcoin conversion
        currency_name = await bank.get_currency_name(ctx.guild)
        conversion_status = "💱 Enabled" if conf.petcoin_conversion_enabled else "❌ Disabled"
        embed.add_field(name="Petcoin Conversion", value=conversion_status, inline=True)
        embed.add_field(
            name="Conversion Rate",
            value=f"{conf.petcoin_conversion_rate} Petcoin → 1 {currency_name}",
            inline=True,
        )

        # Blacklisted names count
        embed.add_field(
            name="Blocked Names",
            value=str(len(conf.disallowed_names)),
            inline=True
        )
        
        # Server-wide pet statistics
        total_graduated = sum(u.total_pets_graduated for u in conf.users.values())
        total_neglect_deaths = sum(u.pets_lost_to_neglect for u in conf.users.values())
        embed.add_field(
            name="Server Pet Stats",
            value=f"🎓 Graduated: {total_graduated}\n"
                  f"💀 Neglect Deaths: {total_neglect_deaths}",
            inline=True
        )
        
        await ctx.send(embed=embed)

    @pcset.command(name="settransfer", aliases=["giftcooldown", "transfercooldown"])
    async def pcset_settransfer(self, ctx: Context, hours: int) -> None:
        """Set the cooldown for gifting pets to other users.
        
        This determines how long a user must wait between sending
        pet gifts. Does not affect receiving gifts.
        
        **Arguments:**
        - `<hours>` - Cooldown duration in hours (1-168, max 1 week).
        
        **Note:** There is also a fixed 24-hour lockout on re-gifting
        a pet that was just received, which cannot be changed.
        """
        if not 1 <= hours <= 168:
            await ctx.send("❌ Cooldown must be between 1 and 168 hours (1 week).")
            return
        
        conf = self.db.get_conf(ctx.guild)
        conf.gift_cooldown_hours = hours
        self.schedule_save()
        
        await ctx.send(f"✅ Pet gift cooldown set to **{hours} hours**.")

    @pcset.command(name="listplayers", aliases=["players", "userlist", "listusers"])
    async def pcset_listplayers(self, ctx: Context) -> None:
        """List all players in this server with their pet statistics.
        
        Shows each player's:
        - Total pets owned
        - Pets graduated to Home
        - Pets lost to neglect
        - Pets passed naturally (old age)
        - Current pet (if any)
        """
        conf = self.db.get_conf(ctx.guild)
        
        if not conf.users:
            await ctx.send("🐾 No players have joined Petcord in this server yet.")
            return
        
        # Build player list
        player_lines = []
        
        for user_id, user_data in conf.users.items():
            # Try to get the member
            member = ctx.guild.get_member(int(user_id))
            if member:
                name = member.display_name
            else:
                name = f"Unknown ({user_id})"
            
            # Get stats
            graduated = user_data.total_pets_graduated
            neglect_deaths = user_data.pets_lost_to_neglect
            natural_deaths = user_data.pets_passed_naturally
            total_owned = user_data.total_pets_owned
            home_count = len(user_data.home_pets)
            
            # Current pet indicator
            if user_data.current_pet:
                current = f"🐾 {user_data.current_pet.name}"
            else:
                current = "—"
            
            # Format line with stats
            stats = f"🎓 {graduated} | 💔 {neglect_deaths} | 🕊️ {natural_deaths}"
            player_lines.append({
                "name": name,
                "total_owned": total_owned,
                "stats": stats,
                "home_count": home_count,
                "current": current,
            })
        
        # Sort by total pets owned (descending)
        player_lines.sort(key=lambda x: x["total_owned"], reverse=True)
        
        # Send paginated view
        view = ListPlayersView(
            cog=self,
            ctx=ctx,
            player_lines=player_lines,
        )
        embed = view.build_embed()
        view.message = await ctx.send(embed=embed, view=view)

    @pcset.command(name="deleteuser", aliases=["remove", "wipe"])
    async def pcset_deleteuser(self, ctx: Context, user: discord.Member) -> None:
        """Delete a user's Petcord data completely.
        
        ⚠️ **WARNING:** This permanently deletes ALL of the user's data including:
        - Current pet
        - All pets in Home
        - All memorial entries
        - All achievements
        - All statistics and history
        
        This action cannot be undone!
        
        **Arguments:**
        - `<user>` - The user whose data should be deleted.
        """
        from discord.ui import View, Button
        
        conf = self.db.get_conf(ctx.guild)
        user_id = user.id
        
        # Check if user exists in the database
        if user_id not in conf.users:
            await ctx.send(f"🐾 **{user.display_name}** doesn't have any Petcord data to delete.")
            return
        
        user_data = conf.users[user_id]
        
        # Gather stats for confirmation message
        pets_owned = user_data.total_pets_owned
        home_pets = len(user_data.home_pets)
        memorial_count = len(user_data.memorial)
        achievements = len(user_data.achievements)
        current_pet = user_data.current_pet.name if user_data.current_pet else "None"
        
        # Build confirmation embed
        embed = discord.Embed(
            title="⚠️ Confirm User Data Deletion",
            description=(
                f"You are about to **permanently delete** all Petcord data for **{user.display_name}**.\n\n"
                f"**This will delete:**\n"
                f"• 🐾 Current Pet: {current_pet}\n"
                f"• 🏠 Home Pets: {home_pets}\n"
                f"• 🪦 Memorial Entries: {memorial_count}\n"
                f"• 🏆 Achievements: {achievements}\n"
                f"• 📊 Total Pets Owned: {pets_owned}\n"
                f"• All statistics and history\n\n"
                f"**This action cannot be undone!**"
            ),
            color=discord.Color.red()
        )
        
        # Create confirmation view
        class DeleteConfirmView(View):
            def __init__(self, cog, ctx, user, user_id, conf):
                super().__init__(timeout=30)
                self.cog = cog
                self.ctx = ctx
                self.user = user
                self.user_id = user_id
                self.conf = conf
                self.responded = False
            
            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.ctx.author.id:
                    await interaction.response.send_message(
                        "Only the command author can confirm this action.",
                        ephemeral=True
                    )
                    return False
                return True
            
            @discord.ui.button(label="Yes, Delete", style=discord.ButtonStyle.danger, emoji="🗑️")
            async def confirm_button(self, interaction: discord.Interaction, button: Button):
                if self.responded:
                    return
                self.responded = True
                
                # Delete the user data
                del self.conf.users[self.user_id]
                self.cog.schedule_save()
                
                # Update embed
                success_embed = discord.Embed(
                    title="✅ User Data Deleted",
                    description=f"All Petcord data for **{self.user.display_name}** has been permanently deleted.",
                    color=discord.Color.green()
                )
                
                self.stop()
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=success_embed, view=self)
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
            async def cancel_button(self, interaction: discord.Interaction, button: Button):
                if self.responded:
                    return
                self.responded = True
                
                cancel_embed = discord.Embed(
                    title="❌ Deletion Cancelled",
                    description=f"No data was deleted for **{self.user.display_name}**.",
                    color=discord.Color.grey()
                )
                
                self.stop()
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=cancel_embed, view=self)
            
            async def on_timeout(self):
                timeout_embed = discord.Embed(
                    title="⏰ Confirmation Timed Out",
                    description=f"No data was deleted for **{self.user.display_name}**.",
                    color=discord.Color.grey()
                )
                for item in self.children:
                    item.disabled = True
                try:
                    await self.message.edit(embed=timeout_embed, view=self)
                except:
                    pass
        
        view = DeleteConfirmView(self, ctx, user, user_id, conf)
        view.message = await ctx.send(embed=embed, view=view)

    @pcset.command(name="deleteall", aliases=["wipeall", "resetall"])
    async def pcset_deleteall(self, ctx: Context) -> None:
        """Delete ALL Petcord user data for this server.
        
        ⚠️ **EXTREME WARNING:** This permanently deletes ALL player data including:
        - All users' current pets
        - All users' Home pets
        - All memorial entries
        - All achievements
        - All statistics and history
        
        This affects EVERY player in this server and cannot be undone!
        """
        from discord.ui import View, Button
        
        conf = self.db.get_conf(ctx.guild)
        
        # Check if there are any users
        if not conf.users:
            await ctx.send("🐾 There are no Petcord users in this server to delete.")
            return
        
        # Gather total stats
        total_users = len(conf.users)
        total_pets_owned = sum(u.total_pets_owned for u in conf.users.values())
        total_home_pets = sum(len(u.home_pets) for u in conf.users.values())
        total_memorials = sum(len(u.memorial) for u in conf.users.values())
        total_achievements = sum(len(u.achievements) for u in conf.users.values())
        active_pets = sum(1 for u in conf.users.values() if u.current_pet)
        
        # Build confirmation embed
        embed = discord.Embed(
            title="🚨 CONFIRM COMPLETE DATA WIPE 🚨",
            description=(
                f"**This will delete ALL users in the database, are you SURE?**\n\n"
                f"**This will permanently delete:**\n"
                f"• 👥 Total Users: **{total_users}**\n"
                f"• 🐾 Active Pets: **{active_pets}**\n"
                f"• 🏠 Home Pets: **{total_home_pets}**\n"
                f"• 🪦 Memorial Entries: **{total_memorials}**\n"
                f"• 🏆 Achievements: **{total_achievements}**\n"
                f"• 📊 Total Pets Ever Owned: **{total_pets_owned}**\n\n"
                f"⚠️ **THIS ACTION CANNOT BE UNDONE!** ⚠️"
            ),
            color=discord.Color.dark_red()
        )
        
        # Create confirmation view
        class DeleteAllConfirmView(View):
            def __init__(self, cog, ctx, conf, total_users):
                super().__init__(timeout=30)
                self.cog = cog
                self.ctx = ctx
                self.conf = conf
                self.total_users = total_users
                self.responded = False
            
            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.ctx.author.id:
                    await interaction.response.send_message(
                        "Only the command author can confirm this action.",
                        ephemeral=True
                    )
                    return False
                return True
            
            @discord.ui.button(label="Yes, DELETE ALL", style=discord.ButtonStyle.danger, emoji="🗑️")
            async def confirm_button(self, interaction: discord.Interaction, button: Button):
                if self.responded:
                    return
                self.responded = True
                
                # Delete all user data
                deleted_count = len(self.conf.users)
                self.conf.users.clear()
                self.cog.schedule_save()
                
                # Update embed
                success_embed = discord.Embed(
                    title="✅ All User Data Deleted",
                    description=f"All Petcord data for **{deleted_count} users** has been permanently deleted.",
                    color=discord.Color.green()
                )
                
                self.stop()
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=success_embed, view=self)
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
            async def cancel_button(self, interaction: discord.Interaction, button: Button):
                if self.responded:
                    return
                self.responded = True
                
                cancel_embed = discord.Embed(
                    title="❌ Deletion Cancelled",
                    description="No data was deleted. All user data is safe.",
                    color=discord.Color.grey()
                )
                
                self.stop()
                for item in self.children:
                    item.disabled = True
                await interaction.response.edit_message(embed=cancel_embed, view=self)
            
            async def on_timeout(self):
                timeout_embed = discord.Embed(
                    title="⏰ Confirmation Timed Out",
                    description="No data was deleted. All user data is safe.",
                    color=discord.Color.grey()
                )
                for item in self.children:
                    item.disabled = True
                try:
                    await self.message.edit(embed=timeout_embed, view=self)
                except:
                    pass
        
        view = DeleteAllConfirmView(self, ctx, conf, total_users)
        view.message = await ctx.send(embed=embed, view=view)

    @pcset.command(name="graduate")
    async def pcset_graduate(self, ctx: Context, user: discord.Member) -> None:
        """Instantly graduate a user's pet to their Home.
        
        This ages the pet to adult and sends them to Home with a medal
        based on their current growth average score.
        
        Useful for testing or helping users who encounter issues.
        """
        import time
        from ..common.constants import GOLD_THRESHOLD, SILVER_THRESHOLD, BRONZE_THRESHOLD
        
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        pet = user_data.current_pet
        
        if not pet:
            await ctx.send(f"❌ **{user.display_name}** doesn't have a current pet to graduate.")
            return
        
        # Calculate medal based on current growth average
        avg_score = pet.growth_average_score
        
        # If no daily scores yet, calculate a quick estimate from current stats
        if avg_score == 0 and not pet.growth_daily_scores:
            # Estimate based on current stats
            avg_score = (pet.hunger + pet.happiness + pet.cleanliness + pet.energy) / 4
        
        # Determine medal
        if avg_score >= GOLD_THRESHOLD:
            pet.medal = "gold"
            bond_bonus = 20
            user_data.gold_medals += 1
            medal_display = "🥇 Gold"
        elif avg_score >= SILVER_THRESHOLD:
            pet.medal = "silver"
            bond_bonus = 10
            user_data.silver_medals += 1
            medal_display = "🥈 Silver"
        elif avg_score >= BRONZE_THRESHOLD:
            pet.medal = "bronze"
            bond_bonus = 5
            user_data.bronze_medals += 1
            medal_display = "🥉 Bronze"
        else:
            pet.medal = ""
            bond_bonus = 0
            medal_display = "No Medal"
        
        # Update pet for graduation
        pet.life_stage = "adult"
        pet.medal_score = avg_score
        pet.bond = min(100, pet.bond + bond_bonus)
        pet.is_in_home = True
        pet.ready_to_graduate = False
        pet.reached_adult_timestamp = time.time()
        pet.graduated_timestamp = time.time()
        
        # Move to home
        user_data.home_pets.append(pet)
        user_data.current_pet = None
        user_data.total_pets_graduated += 1
        
        # Award legendarycoin every 5 graduations
        legendarycoin_earned = 0
        if user_data.total_pets_graduated % 5 == 0:
            legendarycoin_earned = 1
            user_data.legendarycoin += 1
            user_data.most_legendarycoin_earned += 1
        
        if pet.medal:
            user_data.total_medals += 1
        
        # Update medal streak
        if pet.medal == "gold":
            user_data.current_medal_streak += 1
            user_data.best_medal_streak = max(
                user_data.best_medal_streak,
                user_data.current_medal_streak
            )
        else:
            user_data.current_medal_streak = 0
        
        # Update lifetime tracking
        if pet.bond > user_data.highest_bond_achieved:
            user_data.highest_bond_achieved = int(pet.bond)
        
        self.schedule_save()
        
        # Build legendarycoin text for display
        legendarycoin_text = ""
        if legendarycoin_earned > 0:
            legendarycoin_text = f"\n✨ Legendarycoin Earned: +{legendarycoin_earned}"
        
        embed = discord.Embed(
            title="🎓 Pet Graduated by Admin",
            description=(
                f"**{pet.name}** has been graduated to **{user.display_name}**'s Home!\n\n"
                f"🏅 Medal: {medal_display} ({avg_score:.1f}%)\n"
                f"💕 Bond Bonus: +{bond_bonus}\n"
                f"📊 Final Bond: {pet.bond}{legendarycoin_text}"
            ),
            color=discord.Color.gold()
        )
        embed.set_footer(text=f"Graduated by {ctx.author}")
        
        await ctx.send(embed=embed)

    @pcset.command(name="channel")
    async def pcset_channel(self, ctx: Context, channel: discord.TextChannel = None) -> None:
        """Set the notification channel for Petcord events.
        
        This channel will receive notifications for:
        - Pet deaths (both from neglect and old age)
        
        Use without a channel argument to clear the setting.
        """
        conf = self.db.get_conf(ctx.guild)
        
        if channel is None:
            conf.allowed_channel_id = None
            self.schedule_save()
            await ctx.send("✅ Notification channel cleared. Death notifications will not be sent.")
            return
        
        conf.allowed_channel_id = channel.id
        self.schedule_save()
        
        await ctx.send(f"✅ Notification channel set to {channel.mention}.\n"
                       f"Pet death notifications will be sent there.")

    @pcset.command(name="death")
    async def pcset_death(self, ctx: Context, enabled: bool) -> None:
        """Enable or disable pet death from neglect during growth.
        
        When enabled, growing pets (baby/juvenile) can die if their
        stats drop too low from neglect. Home pets are not affected.
        
        **Arguments:**
        - `<enabled>` - True to enable, False to disable.
        """
        conf = self.db.get_conf(ctx.guild)
        conf.pet_death_enabled = enabled
        self.schedule_save()
        
        if enabled:
            await ctx.send("⚠️ Pet death from neglect is now **enabled**.\n"
                          "Growing pets can die if their stats drop too low.")
        else:
            await ctx.send("🛡️ Pet death from neglect is now **disabled**.\n"
                          "Pets will not die from neglect (they can still pass from old age in Home).")

    @pcset.command(name="immortal", aliases=["eternal", "protect"])
    async def pcset_immortal(self, ctx: Context, user: discord.Member, pet_name: str, immortal: bool) -> None:
        """Make a specific pet immortal (or mortal again).
        
        Immortal pets will never age or die from old age. They stay
        in their current life stage forever.
        
        This only works on pets that are in the user's Home (graduated pets).
        
        **Arguments:**
        - `<user>` - The user who owns the pet.
        - `<pet_name>` - The name of the pet (use quotes if it has spaces).
        - `<immortal>` - True to make immortal, False to make mortal again.
        
        **Examples:**
        - `[p]pcset immortal @user "Whiskers" true`
        - `[p]pcset immortal @user Fluffy false`
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        # Search for the pet in home_pets (case-insensitive)
        pet_name_lower = pet_name.lower()
        matching_pet = None
        
        for pet in user_data.home_pets:
            if pet.name.lower() == pet_name_lower:
                matching_pet = pet
                break
        
        if matching_pet is None:
            # List their home pets for convenience
            if user_data.home_pets:
                pet_names = ", ".join(f"`{p.name}`" for p in user_data.home_pets)
                await ctx.send(
                    f"❌ Could not find a pet named `{pet_name}` in **{user.display_name}**'s Home.\n"
                    f"**Their Home pets:** {pet_names}"
                )
            else:
                await ctx.send(
                    f"❌ **{user.display_name}** has no pets in their Home yet.\n"
                    "Pets must graduate to Home (reach adult stage) before they can be made immortal."
                )
            return
        
        # Update immortal status
        matching_pet.is_immortal = immortal
        self.schedule_save()
        
        if immortal:
            await ctx.send(
                f"✨ **{matching_pet.name}** is now **immortal**!\n"
                f"This pet will never age or pass away from old age."
            )
        else:
            await ctx.send(
                f"⏳ **{matching_pet.name}** is now **mortal** again.\n"
                f"This pet will age normally and may eventually pass from old age."
            )

    @pcset.command(name="medals")
    async def pcset_medals(self, ctx: Context, gold: float, silver: float, bronze: float) -> None:
        """Set the medal score thresholds.
        
        These thresholds determine what medal a pet earns at graduation
        based on their average daily care score.
        
        **Arguments:**
        - `<gold>` - Minimum score for Gold medal (e.g., 90)
        - `<silver>` - Minimum score for Silver medal (e.g., 75)
        - `<bronze>` - Minimum score for Bronze medal (e.g., 55)
        
        Note: Thresholds must satisfy bronze < silver < gold ≤ 100
        """
        # Validate thresholds
        if not (0 <= bronze < silver < gold <= 100):
            await ctx.send("❌ Invalid thresholds. Must satisfy: 0 ≤ bronze < silver < gold ≤ 100")
            return
        
        conf = self.db.get_conf(ctx.guild)
        conf.medal_gold_threshold = gold
        conf.medal_silver_threshold = silver
        conf.medal_bronze_threshold = bronze
        self.schedule_save()
        
        await ctx.send(
            f"✅ Medal thresholds updated:\n"
            f"🥇 Gold: **{gold}%**\n"
            f"🥈 Silver: **{silver}%**\n"
            f"🥉 Bronze: **{bronze}%**"
        )

    @pcset.group(name="blacklist", aliases=["blocklist"])
    async def pcset_blacklist(self, ctx: Context) -> None:
        """Manage the pet name blacklist.
        
        Blacklisted words cannot be used in pet names.
        """
        if ctx.invoked_subcommand is None:
            prefix = ctx.clean_prefix
            cmds = sorted(ctx.command.commands, key=lambda c: c.name)
            embed = discord.Embed(
                title="⛔ Petcord Blacklist Commands",
                description=f"Use `{prefix}pcset blacklist <command>` to manage blocked pet names.",
                color=discord.Color.red(),
            )
            for cmd in cmds:
                brief = cmd.brief or (cmd.help.splitlines()[0] if cmd.help else "No description.")
                aliases = f" | aliases: {', '.join(cmd.aliases)}" if cmd.aliases else ""
                embed.add_field(
                    name=f"`{prefix}pcset blacklist {cmd.name}`{aliases}",
                    value=brief,
                    inline=False,
                )
            await ctx.send(embed=embed)

    @pcset_blacklist.command(name="add")
    async def blacklist_add(self, ctx: Context, *, word: str) -> None:
        """Add a word to the name blacklist.
        
        **Arguments:**
        - `<word>` - The word to block from pet names.
        """
        conf = self.db.get_conf(ctx.guild)
        word_lower = word.lower().strip()
        
        if not word_lower:
            await ctx.send("❌ Please provide a word to add.")
            return
        
        if word_lower in conf.disallowed_names:
            await ctx.send(f"⚠️ **{word}** is already in the blacklist.")
            return
        
        conf.disallowed_names.append(word_lower)
        self.schedule_save()
        
        await ctx.send(f"✅ Added **{word}** to the name blacklist.")

    @pcset_blacklist.command(name="remove")
    async def blacklist_remove(self, ctx: Context, *, word: str) -> None:
        """Remove a word from the name blacklist.
        
        **Arguments:**
        - `<word>` - The word to remove.
        """
        conf = self.db.get_conf(ctx.guild)
        word_lower = word.lower().strip()
        
        if word_lower not in conf.disallowed_names:
            await ctx.send(f"⚠️ **{word}** is not in the blacklist.")
            return
        
        conf.disallowed_names.remove(word_lower)
        self.schedule_save()
        
        await ctx.send(f"✅ Removed **{word}** from the name blacklist.")

    @pcset_blacklist.command(name="list")
    async def blacklist_list(self, ctx: Context) -> None:
        """Show all blacklisted words."""
        conf = self.db.get_conf(ctx.guild)
        
        if not conf.disallowed_names:
            await ctx.send("📝 The name blacklist is empty.")
            return
        
        # Sort alphabetically
        sorted_words = sorted(conf.disallowed_names)
        
        embed = discord.Embed(
            title="🚫 Name Blacklist",
            description=f"**{len(sorted_words)}** words blocked from pet names:",
            color=discord.Color.red()
        )
        
        # Display in columns
        words_display = ", ".join(f"`{w}`" for w in sorted_words[:50])
        if len(sorted_words) > 50:
            words_display += f"\n*...and {len(sorted_words) - 50} more*"
        
        embed.add_field(name="Blocked Words", value=words_display, inline=False)
        
        await ctx.send(embed=embed)

    # =========================================================================
    # Backup & Restore Commands
    # =========================================================================
    
    @pcset.group(name="backup")
    @commands.is_owner()
    async def pcset_backup(self, ctx: Context) -> None:
        """Database backup management (Bot Owner only)."""
        if ctx.invoked_subcommand is None:
            prefix = ctx.clean_prefix
            cmds = sorted(ctx.command.commands, key=lambda c: c.name)
            embed = discord.Embed(
                title="🗃️ Petcord Backup Commands",
                description=f"Use `{prefix}pcset backup <command>` to manage backups.",
                color=discord.Color.orange(),
            )
            for cmd in cmds:
                brief = cmd.brief or (cmd.help.splitlines()[0] if cmd.help else "No description.")
                aliases = f" | aliases: {', '.join(cmd.aliases)}" if cmd.aliases else ""
                embed.add_field(
                    name=f"`{prefix}pcset backup {cmd.name}`{aliases}",
                    value=brief,
                    inline=False,
                )
            await ctx.send(embed=embed)
    
    @pcset_backup.command(name="list")
    async def backup_list(self, ctx: Context) -> None:
        """List available database backups."""
        from datetime import datetime
        
        backups = self.get_available_backups()
        
        if not backups:
            await ctx.send("📂 No backups available. Backups are created automatically every 8 hours when data changes.")
            return
        
        embed = discord.Embed(
            title="💾 Available Backups",
            description=f"Use `{ctx.clean_prefix}pcset backup restore <number>` to restore a backup.",
            color=discord.Color.blue()
        )
        
        backup_lines = []
        for i, backup in enumerate(backups):
            try:
                # Parse timestamp from filename: data_YYYYMMDD_HHMMSS.json
                timestamp_str = backup.stem.replace("data_", "")
                backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                time_display = backup_time.strftime("%b %d, %Y at %I:%M %p")
                
                # File size
                size_kb = backup.stat().st_size / 1024
                
                backup_lines.append(f"**{i + 1}.** {time_display} ({size_kb:.1f} KB)")
            except Exception:
                backup_lines.append(f"**{i + 1}.** {backup.name}")
        
        embed.add_field(
            name="Backups (newest first)",
            value="\n".join(backup_lines) or "None",
            inline=False
        )
        
        embed.set_footer(text="Backups are rotated automatically, keeping the 3 most recent")
        
        await ctx.send(embed=embed)
    
    @pcset_backup.command(name="restore")
    async def backup_restore(self, ctx: Context, backup_number: int = 1) -> None:
        """Restore the database from a backup.
        
        **Arguments:**
        - `[backup_number]` - Which backup to restore (1 = most recent). Default: 1
        
        ⚠️ **Warning:** This will overwrite all current data!
        """
        backups = self.get_available_backups()
        
        if not backups:
            await ctx.send("❌ No backups available to restore.")
            return
        
        if backup_number < 1 or backup_number > len(backups):
            await ctx.send(f"❌ Invalid backup number. Choose between 1 and {len(backups)}.")
            return
        
        # Confirm action
        backup_path = backups[backup_number - 1]
        
        await ctx.send(
            f"⚠️ **Are you sure you want to restore from backup?**\n"
            f"Backup: `{backup_path.name}`\n\n"
            f"This will **overwrite all current data**. Type `yes` to confirm."
        )
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            msg = await self.bot.wait_for("message", check=check, timeout=30)
            if msg.content.lower() != "yes":
                await ctx.send("❌ Restore cancelled.")
                return
        except Exception:
            await ctx.send("❌ Restore cancelled (timed out).")
            return
        
        # Perform restore
        success = await self.restore_from_backup(backup_number - 1)
        
        if success:
            await ctx.send(f"✅ Successfully restored from backup `{backup_path.name}`!")
        else:
            await ctx.send("❌ Failed to restore from backup. Check logs for details.")
    
    @pcset_backup.command(name="create")
    async def backup_create(self, ctx: Context) -> None:
        """Force create a backup now (ignores 8-hour cooldown)."""
        import shutil
        from datetime import datetime
        
        if not self.data_path.exists():
            await ctx.send("❌ No data file exists to backup.")
            return
        
        backup_dir = self.data_path.parent / "backups"
        backup_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"data_{timestamp}.json"
        
        try:
            shutil.copy2(self.data_path, backup_path)
            
            # Clean up old backups, keep only 3
            existing_backups = sorted(backup_dir.glob("data_*.json"), reverse=True)
            for old_backup in existing_backups[3:]:
                old_backup.unlink()
            
            size_kb = backup_path.stat().st_size / 1024
            await ctx.send(f"✅ Created backup: `{backup_path.name}` ({size_kb:.1f} KB)")
        except Exception as e:
            await ctx.send(f"❌ Failed to create backup: {e}")
    
    @pcset.command(name="generate", aliases=["offer", "gift"])
    async def pcset_generate(
        self, 
        ctx: Context, 
        user: discord.Member, 
        species_id: str, 
        coat: Optional[str] = None, 
        pattern: Optional[str] = None
    ) -> None:
        """Offer a specific pet to a user.
        
        This generates a pet offer for the target user with the exact
        species, coat color, and pattern you specify. The user can then
        choose to adopt or pass on the pet.
        
        **Arguments:**
        - `<user>` - The user to offer the pet to.
        - `<species_id>` - The species ID (e.g., "scottish_fold", "golden_retriever").
        - `[coat]` - Optional coat color (e.g., "Gray", "Piebald", "Albino").
        - `[pattern]` - Optional pattern (e.g., "Tabby", "Solid", "Spotted").
        
        **Special Coats:**
        Rare: Albino, Melanistic, Leucistic, Piebald
        Mythical: Rainbow, Galaxy, Crystal, Shadow
        
        **Examples:**
        - `[p]pcset generate @user scottish_fold`
        - `[p]pcset generate @user scottish_fold Gray Tabby`
        - `[p]pcset generate @user golden_retriever Piebald`
        """
        from ..database.species import get_species, SPECIES_DATABASE
        from ..database.appearance import (
            RARE_COATS, MYTHICAL_COATS, generate_appearance,
            is_special_coat, is_mythical_coat
        )
        from ..views.find_pet import PetFoundView
        
        conf = self.db.get_conf(ctx.guild)
        
        # Normalize species_id (convert spaces to underscores, lowercase)
        species_id_normalized = species_id.lower().replace(" ", "_").replace("-", "_")
        
        # Try to find the species
        species = get_species(species_id_normalized)
        
        if species is None:
            # Try fuzzy matching
            matching = [
                sid for sid in SPECIES_DATABASE.keys() 
                if species_id_normalized in sid or sid in species_id_normalized
            ]
            
            if matching:
                suggestions = ", ".join(f"`{s}`" for s in matching[:5])
                await ctx.send(
                    f"❌ Species `{species_id}` not found.\n"
                    f"**Did you mean:** {suggestions}"
                )
            else:
                # Show some example species
                examples = list(SPECIES_DATABASE.keys())[:10]
                await ctx.send(
                    f"❌ Species `{species_id}` not found.\n"
                    f"**Example species IDs:** {', '.join(f'`{e}`' for e in examples)}"
                )
            return
        
        # Determine coat and pattern
        if coat is None and pattern is None:
            # Generate random appearance
            final_coat, final_pattern, final_rarity = generate_appearance(species)
        else:
            # User specified at least one - validate and use
            all_valid_coats = species.possible_coats + RARE_COATS + MYTHICAL_COATS
            
            if coat:
                # Case-insensitive match
                coat_match = next(
                    (c for c in all_valid_coats if c.lower() == coat.lower()), 
                    None
                )
                if coat_match is None:
                    valid_coats = ", ".join(f"`{c}`" for c in species.possible_coats[:8])
                    special = ", ".join(f"`{c}`" for c in RARE_COATS + MYTHICAL_COATS)
                    await ctx.send(
                        f"❌ Invalid coat `{coat}` for {species.name}.\n"
                        f"**Valid coats:** {valid_coats}\n"
                        f"**Special coats:** {special}"
                    )
                    return
                final_coat = coat_match
            else:
                # Random coat from species pool
                import random
                final_coat = random.choice(species.possible_coats) if species.possible_coats else "Standard"
            
            if pattern:
                # Case-insensitive match
                pattern_match = next(
                    (p for p in species.possible_patterns if p.lower() == pattern.lower()),
                    None
                )
                if pattern_match is None:
                    valid_patterns = ", ".join(f"`{p}`" for p in species.possible_patterns)
                    await ctx.send(
                        f"❌ Invalid pattern `{pattern}` for {species.name}.\n"
                        f"**Valid patterns:** {valid_patterns}"
                    )
                    return
                final_pattern = pattern_match
            else:
                # Random pattern from species pool
                import random
                final_pattern = random.choice(species.possible_patterns) if species.possible_patterns else "Solid"
            
            # Determine rarity based on coat
            if is_mythical_coat(final_coat):
                final_rarity = "mythical"
            elif is_special_coat(final_coat):
                # Upgrade rarity by one tier
                rarity_order = ["common", "uncommon", "rare", "very_rare", "legendary", "mythical"]
                try:
                    idx = rarity_order.index(species.rarity)
                    final_rarity = rarity_order[min(idx + 1, len(rarity_order) - 2)]
                except ValueError:
                    final_rarity = species.rarity
            else:
                final_rarity = species.rarity
        
        # Get user data
        user_data = conf.get_user(user)
        
        # Check if user already has a pet
        if user_data.current_pet is not None:
            await ctx.send(
                f"⚠️ **{user.display_name}** already has a pet named "
                f"**{user_data.current_pet.name}**.\n"
                f"Use `{ctx.clean_prefix}pcset clearpet {user.mention}` first to remove their current pet."
            )
            return
        
        # Create the offered pet dict
        offered_pet = {
            "species": species,
            "coat": final_coat,
            "pattern": final_pattern,
            "rarity": final_rarity
        }
        
        # Create the view for the TARGET user
        view = PetFoundView(
            cog=self,
            user_data=user_data,
            guild_settings=conf,
            offered_pet=offered_pet,
            author_id=user.id  # Important: set to target user so only they can adopt
        )
        
        # Build and send the embed
        embed = view.build_embed()
        embed.set_footer(text=f"🎁 Gift from {ctx.author.display_name} | Only {user.display_name} can adopt")
        
        view.message = await ctx.send(
            content=f"🎁 {user.mention}, a pet has been offered to you!",
            embed=embed,
            view=view
        )
    
    @pcset.command(name="species", aliases=["listspecies", "specieslist"])
    async def pcset_species(self, ctx: Context, category: Optional[str] = None) -> None:
        """List available species IDs for the generate command.
        
        **Arguments:**
        - `[category]` - Optional category filter (dogs, cats, small_mammals, 
          reptiles, birds, aquatic, exotic).
        
        **Examples:**
        - `[p]pcset species` - List all categories with species count
        - `[p]pcset species cats` - List all cat species
        """
        from ..database.species import (
            SPECIES_DATABASE, get_all_categories, 
            get_species_by_category, get_all_species
        )
        
        if category is None:
            # Show category overview
            categories = get_all_categories()
            
            embed = discord.Embed(
                title="🐾 Species Categories",
                description=f"Use `{ctx.clean_prefix}pcset species <category>` to see species in a category.",
                color=discord.Color.blue()
            )
            
            for cat in sorted(categories):
                species_list = get_species_by_category(cat)
                # Show count and a few examples
                examples = [s.name for s in species_list[:3]]
                embed.add_field(
                    name=f"{cat.replace('_', ' ').title()} ({len(species_list)})",
                    value=", ".join(examples) + ("..." if len(species_list) > 3 else ""),
                    inline=True
                )
            
            embed.set_footer(text=f"Total: {len(SPECIES_DATABASE)} species")
            await ctx.send(embed=embed)
        else:
            # Show species in category
            category_normalized = category.lower().replace(" ", "_")
            species_list = get_species_by_category(category_normalized)
            
            if not species_list:
                categories = get_all_categories()
                await ctx.send(
                    f"❌ Category `{category}` not found.\n"
                    f"**Valid categories:** {', '.join(f'`{c}`' for c in sorted(categories))}"
                )
                return
            
            # Build species list by rarity
            by_rarity = {}
            for sp in species_list:
                if sp.rarity not in by_rarity:
                    by_rarity[sp.rarity] = []
                by_rarity[sp.rarity].append(sp)
            
            embed = discord.Embed(
                title=f"🐾 {category_normalized.replace('_', ' ').title()} Species",
                color=discord.Color.blue()
            )
            
            rarity_order = ["common", "uncommon", "rare", "very_rare", "legendary", "mythical"]
            for rarity in rarity_order:
                if rarity in by_rarity:
                    species_text = "\n".join(
                        f"{s.emoji} `{s.id}` - {s.name}" 
                        for s in by_rarity[rarity]
                    )
                    embed.add_field(
                        name=f"{rarity.replace('_', ' ').title()} ({len(by_rarity[rarity])})",
                        value=species_text[:1024] if len(species_text) > 1024 else species_text,
                        inline=False
                    )
            
            await ctx.send(embed=embed)

    @pcset.command(name="tease")
    async def pcset_tease(self, ctx: Context, user: discord.Member) -> None:
        """Send a fake abandon message to tease a user (just for fun!).
        
        This posts a random abandon-style message about the user's current pet
        but does NOT actually abandon the pet or affect any stats.
        
        **Arguments:**
        - `<user>` - The user to tease.
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.users.get(user.id)
        
        if not user_data or not user_data.current_pet:
            await ctx.send(f"❌ {user.display_name} doesn't have a pet to tease about!")
            return
        
        pet = user_data.current_pet
        
        # Get species name
        from ..database.species import get_species
        species = get_species(pet.species_id)
        species_name = species.name if species else pet.species_id.replace("_", " ").title()
        
        # Get random tease message
        from ..database.abandon import get_random_abandon_message
        tease_message = get_random_abandon_message(
            user_mention=user.mention,
            species_name=species_name,
            pet_name=pet.name
        )
        
        # Add disclaimer
        full_message = f"{tease_message}\n\n*— This is just a joke! {pet.name} is safe and sound.* 😉"
        
        await ctx.send(full_message)

    @pcset.command(name="timezone", aliases=["tz"])
    async def pcset_timezone(self, ctx: Context, timezone: Optional[str] = None) -> None:
        """Set or view the server's timezone for time-based features.
        
        The timezone is used for accurate daily resets and time-based events.
        
        Use standard IANA timezone names like:
        - `America/New_York`
        - `America/Los_Angeles`
        - `America/Chicago`
        - `Europe/London`
        - `Asia/Tokyo`
        - `UTC`
        
        Full list: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        
        **Examples:**
        - `[p]pcset timezone` - Show current timezone
        - `[p]pcset timezone America/New_York`
        - `[p]pcset timezone Europe/London`
        - `[p]pcset timezone browse` - Browse available timezones
        """
        conf = self.db.get_conf(ctx.guild)
        
        # If no timezone provided, show current setting
        if timezone is None:
            try:
                tz = ZoneInfo(conf.discord_server_timezone)
                now = datetime.now(tz)
                await ctx.send(
                    f"🕐 **Server Timezone:** `{conf.discord_server_timezone}`\n"
                    f"📅 **Current Time:** {now.strftime('%Y-%m-%d %I:%M %p %Z')}\n\n"
                    f"Use `{ctx.clean_prefix}pcset timezone <timezone>` to change.\n"
                    f"Use `{ctx.clean_prefix}pcset timezone browse` to browse available timezones."
                )
            except Exception:
                await ctx.send(
                    f"⚠️ **Server Timezone:** `{conf.discord_server_timezone}` (invalid)\n\n"
                    f"Please set a valid timezone with `{ctx.clean_prefix}pcset timezone <timezone>`"
                )
            return
        
        # If "browse" requested, show the interactive browser
        if timezone.lower() == "browse":
            view = TimezoneRegionView(ctx.author)
            embed = view._get_continent_embed()
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
            return
        
        # Case-insensitive timezone lookup
        # Find the correctly-cased version from available_timezones()
        timezone_lower = timezone.lower()
        matched_timezone = None
        for tz in available_timezones():
            if tz.lower() == timezone_lower:
                matched_timezone = tz
                break
        
        # Validate the timezone
        if matched_timezone is None:
            # Try to find close matches for better UX
            matches = [tz for tz in available_timezones() if timezone_lower in tz.lower()][:10]
            if matches:
                match_list = "\n".join(f"• `{m}`" for m in sorted(matches))
                await ctx.send(
                    f"❌ Invalid timezone `{timezone}`. Did you mean one of these?\n{match_list}\n\n"
                    f"Or use `{ctx.clean_prefix}pcset timezone browse` to browse all timezones."
                )
            else:
                await ctx.send(
                    f"❌ Invalid timezone `{timezone}`.\n\n"
                    f"Use a valid IANA timezone name.\n"
                    f"Examples: `America/New_York`, `Europe/London`, `Asia/Tokyo`, `UTC`\n\n"
                    f"Or use `{ctx.clean_prefix}pcset timezone browse` to browse all timezones."
                )
            return
        
        # Set the timezone (using the correctly-cased version)
        conf.discord_server_timezone = matched_timezone
        self.schedule_save()
        
        # Show current time in that timezone as confirmation
        now = datetime.now(ZoneInfo(matched_timezone))
        await ctx.send(
            f"✅ Server timezone set to **{matched_timezone}**\n"
            f"📅 Current time: {now.strftime('%Y-%m-%d %I:%M %p %Z')}"
        )

    @pcset.command(name="debug")
    @commands.is_owner()
    async def pcset_debug(self, ctx: Context, user: discord.Member) -> None:
        """Toggle debug mode for a user's pet decay tracking.
        
        When enabled:
        - Logs detailed decay information to in-memory debug log
        - Tracks rest decay reduction, stat changes, and timing
        - Use `[p]pcset debugdl` to download the log file
        
        **Arguments:**
        - `<user>` - The user to toggle debug mode for.
        
        **Examples:**
        - `[p]pcset debug @User` - Toggle debug mode
        """
        conf = self.db.get_conf(ctx.guild)
        user_data = conf.get_user(user)
        
        user_data.debug_mode = not user_data.debug_mode
        self.schedule_save()
        
        # Add confirmation entry to debug log
        if user_data.debug_mode:
            from datetime import datetime
            self.debug_log.append({
                "timestamp": datetime.now().isoformat(),
                "user_id": user.id,
                "message": f"Debug mode ENABLED for user {user.id}",
                "debug_mode_toggle": True
            })
        
        status = "enabled" if user_data.debug_mode else "disabled"
        await ctx.send(
            f"✅ Debug mode **{status}** for {user.mention}\n"
            f"{f'Decay info will be logged. Use `{ctx.clean_prefix}pcset debugdl` to download the log.' if user_data.debug_mode else 'Debug mode turned off.'}"
        )

    @pcset.command(name="debugdl", aliases=["debugdownload"])
    @commands.is_owner()
    async def pcset_debugdl(self, ctx: Context) -> None:
        """Download the Petcord debug log.
        
        The log contains detailed information about decay calculations
        for users with debug mode enabled.
        
        Note: Log is stored in memory and will be cleared on cog reload.
        """
        if not self.debug_log:
            await ctx.send(f"❌ No debug log entries. Enable debug mode for a user with `{ctx.clean_prefix}pcset debug @User` first.")
            return
        
        try:
            # Create BytesIO buffer with formatted JSON
            buffer = BytesIO()
            formatted_json = json.dumps(self.debug_log, indent=2)
            buffer.write(formatted_json.encode('utf-8'))
            buffer.seek(0)  # Reset to beginning for reading
            
            await ctx.send(
                f"📊 Petcord debug log ({len(self.debug_log):,} entries):", 
                file=discord.File(buffer, filename="petcord_debug_export.json")
            )
        except Exception as e:
            await ctx.send(f"❌ Error creating debug log: {e}")

    @pcset.command(name="debugclear")
    @commands.is_owner()
    async def pcset_debugclear(self, ctx: Context) -> None:
        """Clear the Petcord debug log.
        
        This permanently removes all debug log entries from memory.
        """
        if not self.debug_log:
            await ctx.send("❌ No debug log entries to clear.")
            return
        
        entry_count = len(self.debug_log)
        self.debug_log.clear()
        await ctx.send(f"✅ Debug log cleared ({entry_count:,} entries removed).")

    @pcset.command(name="setpcoin", aliases=["setpetcoin", "givepcoin"])
    async def pcset_setpcoin(self, ctx: Context, target: str, amount: str) -> None:
        """Set or modify Petcoin balance for a user or all users.
        
        Use `all` to affect every user who has played Petcord.
        Use `+` or `-` prefix on amount to add/subtract instead of setting.
        
        When adding (+), the amount is also added to most_petcoin_earned.
        When setting without +/-, if the new balance exceeds most_petcoin_earned, it updates.
        When subtracting (-), most_petcoin_earned is not affected.
        
        **Arguments:**
        - `<target>` - Either `all` or a @user mention.
        - `<amount>` - Number to set, or +/- number to add/subtract.
        
        **Examples:**
        - `[p]pcset setpcoin all 100` - Set everyone to 100 Petcoins
        - `[p]pcset setpcoin all +50` - Give everyone 50 Petcoins
        - `[p]pcset setpcoin @User 500` - Set user to 500 Petcoins
        - `[p]pcset setpcoin @User +100` - Give user 100 Petcoins
        - `[p]pcset setpcoin @User -50` - Remove 50 Petcoins from user
        """
        conf = self.db.get_conf(ctx.guild)
        
        # Parse amount and operation
        amount_str = amount.strip()
        if amount_str.startswith("+"):
            operation = "add"
            try:
                value = int(amount_str[1:])
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number like `+100` or `-50` or `100`.")
                return
        elif amount_str.startswith("-"):
            operation = "subtract"
            try:
                value = int(amount_str[1:])
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number like `+100` or `-50` or `100`.")
                return
        else:
            operation = "set"
            try:
                value = int(amount_str)
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number like `+100` or `-50` or `100`.")
                return
        
        if value < 0:
            await ctx.send("❌ Amount must be a positive number (use `-` prefix to subtract).")
            return
        
        # Handle "all" target
        if target.lower() == "all":
            if not conf.users:
                await ctx.send("❌ No users have played Petcord in this server yet.")
                return
            
            affected = 0
            zeroed = 0
            
            for user_id, user_data in conf.users.items():
                old_balance = user_data.current_petcoin
                
                if operation == "add":
                    user_data.current_petcoin += value
                    user_data.most_petcoin_earned += value
                elif operation == "subtract":
                    new_balance = old_balance - value
                    if new_balance < 0:
                        user_data.current_petcoin = 0
                        zeroed += 1
                    else:
                        user_data.current_petcoin = new_balance
                else:  # set
                    user_data.current_petcoin = value
                    if value > user_data.most_petcoin_earned:
                        user_data.most_petcoin_earned = value
                
                affected += 1
            
            self.schedule_save()
            
            op_text = {
                "add": f"Added **+{value:,}** Petcoins to",
                "subtract": f"Removed **-{value:,}** Petcoins from",
                "set": f"Set Petcoins to **{value:,}** for"
            }[operation]
            
            msg = f"✅ {op_text} **{affected:,}** users."
            if zeroed > 0:
                msg += f"\n⚠️ {zeroed:,} user(s) were set to 0 (insufficient balance)."
            
            await ctx.send(msg)
            return
        
        # Handle specific user target
        try:
            # Try to convert to member
            converter = commands.MemberConverter()
            user = await converter.convert(ctx, target)
        except commands.MemberNotFound:
            await ctx.send(f"❌ Could not find user `{target}`. Use `all` or mention a user.")
            return
        
        user_data = conf.get_user(user)
        old_balance = user_data.current_petcoin
        zeroed = False
        
        if operation == "add":
            user_data.current_petcoin += value
            user_data.most_petcoin_earned += value
            new_balance = user_data.current_petcoin
        elif operation == "subtract":
            new_balance = old_balance - value
            if new_balance < 0:
                user_data.current_petcoin = 0
                new_balance = 0
                zeroed = True
            else:
                user_data.current_petcoin = new_balance
        else:  # set
            user_data.current_petcoin = value
            new_balance = value
            if value > user_data.most_petcoin_earned:
                user_data.most_petcoin_earned = value
        
        self.schedule_save()
        
        op_text = {
            "add": f"Added **+{value:,}**",
            "subtract": f"Removed **-{value:,}**",
            "set": f"Set to **{value:,}**"
        }[operation]
        
        msg = f"✅ {op_text} Petcoins for {user.mention}\n💰 Balance: {old_balance:,} → {new_balance:,}"
        if zeroed:
            msg += "\n⚠️ Balance was set to 0 (insufficient funds)."
        
        await ctx.send(msg)

    @pcset.command(name="setlcoin", aliases=["setlegendarycoin", "givelcoin"])
    async def pcset_setlcoin(self, ctx: Context, target: str, amount: str) -> None:
        """Set or modify Legendary Coin balance for a user or all users.
        
        Use `all` to affect every user who has played Petcord.
        Use `+` or `-` prefix on amount to add/subtract instead of setting.
        
        When adding (+), the amount is also added to most_legendarycoin_earned.
        When setting without +/-, if the new balance exceeds most_legendarycoin_earned, it updates.
        When subtracting (-), most_legendarycoin_earned is not affected.
        
        **Arguments:**
        - `<target>` - Either `all` or a @user mention.
        - `<amount>` - Number to set, or +/- number to add/subtract.
        
        **Examples:**
        - `[p]pcset setlcoin all 5` - Set everyone to 5 Legendary Coins
        - `[p]pcset setlcoin all +1` - Give everyone 1 Legendary Coin
        - `[p]pcset setlcoin @User 10` - Set user to 10 Legendary Coins
        - `[p]pcset setlcoin @User +2` - Give user 2 Legendary Coins
        - `[p]pcset setlcoin @User -1` - Remove 1 Legendary Coin from user
        """
        conf = self.db.get_conf(ctx.guild)
        
        # Parse amount and operation
        amount_str = amount.strip()
        if amount_str.startswith("+"):
            operation = "add"
            try:
                value = int(amount_str[1:])
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number like `+1` or `-1` or `5`.")
                return
        elif amount_str.startswith("-"):
            operation = "subtract"
            try:
                value = int(amount_str[1:])
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number like `+1` or `-1` or `5`.")
                return
        else:
            operation = "set"
            try:
                value = int(amount_str)
            except ValueError:
                await ctx.send("❌ Invalid amount. Use a number like `+1` or `-1` or `5`.")
                return
        
        if value < 0:
            await ctx.send("❌ Amount must be a positive number (use `-` prefix to subtract).")
            return
        
        # Handle "all" target
        if target.lower() == "all":
            if not conf.users:
                await ctx.send("❌ No users have played Petcord in this server yet.")
                return
            
            affected = 0
            zeroed = 0
            
            for user_id, user_data in conf.users.items():
                old_balance = user_data.legendarycoin
                
                if operation == "add":
                    user_data.legendarycoin += value
                    user_data.most_legendarycoin_earned += value
                elif operation == "subtract":
                    new_balance = old_balance - value
                    if new_balance < 0:
                        user_data.legendarycoin = 0
                        zeroed += 1
                    else:
                        user_data.legendarycoin = new_balance
                else:  # set
                    user_data.legendarycoin = value
                    if value > user_data.most_legendarycoin_earned:
                        user_data.most_legendarycoin_earned = value
                
                affected += 1
            
            self.schedule_save()
            
            op_text = {
                "add": f"Added **+{value:,}** Legendary Coins to",
                "subtract": f"Removed **-{value:,}** Legendary Coins from",
                "set": f"Set Legendary Coins to **{value:,}** for"
            }[operation]
            
            msg = f"✅ {op_text} **{affected:,}** users."
            if zeroed > 0:
                msg += f"\n⚠️ {zeroed:,} user(s) were set to 0 (insufficient balance)."
            
            await ctx.send(msg)
            return
        
        # Handle specific user target
        try:
            # Try to convert to member
            converter = commands.MemberConverter()
            user = await converter.convert(ctx, target)
        except commands.MemberNotFound:
            await ctx.send(f"❌ Could not find user `{target}`. Use `all` or mention a user.")
            return
        
        user_data = conf.get_user(user)
        old_balance = user_data.legendarycoin
        zeroed = False
        
        if operation == "add":
            user_data.legendarycoin += value
            user_data.most_legendarycoin_earned += value
            new_balance = user_data.legendarycoin
        elif operation == "subtract":
            new_balance = old_balance - value
            if new_balance < 0:
                user_data.legendarycoin = 0
                new_balance = 0
                zeroed = True
            else:
                user_data.legendarycoin = new_balance
        else:  # set
            user_data.legendarycoin = value
            new_balance = value
            if value > user_data.most_legendarycoin_earned:
                user_data.most_legendarycoin_earned = value
        
        self.schedule_save()
        
        op_text = {
            "add": f"Added **+{value:,}**",
            "subtract": f"Removed **-{value:,}**",
            "set": f"Set to **{value:,}**"
        }[operation]
        
        msg = f"✅ {op_text} Legendary Coins for {user.mention}\n✨ Balance: {old_balance:,} → {new_balance:,}"
        if zeroed:
            msg += "\n⚠️ Balance was set to 0 (insufficient funds)."
        
        await ctx.send(msg)

    @pcset.command(name="currentstage", aliases=["activepets", "raising"])
    async def pcset_currentstage(self, ctx: Context) -> None:
        """View all users currently raising pets, sorted by progress.
        
        Users are sorted by:
        1. Life stage (Adult > Juvenile > Baby)
        2. Day number within stage (higher = more progress)
        3. Alphabetical by username (tiebreaker)
        
        Only shows users with an active pet that hasn't been graduated.
        """
        conf = self.db.get_conf(ctx.guild)
        
        # Collect all users with active pets (current_pet that's not in home)
        active_raisers = []
        
        for user_id, user_data in conf.users.items():
            if user_data.current_pet is None:
                continue
            
            pet = user_data.current_pet
            # Skip pets that are already in home (graduated)
            if pet.is_in_home:
                continue
            
            # Try to get the member to get display name
            member = ctx.guild.get_member(user_id)
            if member is None:
                # User left server, skip
                continue
            
            active_raisers.append({
                "user_id": user_id,
                "display_name": member.display_name,
                "username": member.name.lower(),  # For alphabetical sorting
                "pet": pet,
            })
        
        if not active_raisers:
            await ctx.send("📊 No users are currently raising pets in this server.")
            return
        
        # Sort by: stage (adult > juvenile > baby), then day (desc), then username (asc)
        stage_priority = {"adult": 0, "juvenile": 1, "baby": 2, "senior": -1}
        
        active_raisers.sort(
            key=lambda x: (
                stage_priority.get(x["pet"].life_stage, 3),  # Stage priority
                -int(x["pet"].age_days),  # Days descending (negative for reverse)
                x["username"],  # Username ascending
            )
        )
        
        # Send paginated view
        view = CurrentStageView(
            cog=self,
            ctx=ctx,
            active_raisers=active_raisers,
        )
        embed = view.build_embed()
        view.message = await ctx.send(embed=embed, view=view)


# =============================================================================
# CURRENT STAGE PAGINATION VIEW
# =============================================================================

USERS_PER_PAGE = 10  # 2 lines per user, so 10 users = 20 lines


class CurrentStageView(View):
    """Paginated view for displaying users currently raising pets."""
    
    def __init__(
        self,
        cog: "MixinMeta",
        ctx: Context,
        active_raisers: list,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.active_raisers = active_raisers
        self.current_page = 0
        self.message: Optional[discord.Message] = None
        
        # Calculate total pages
        import math
        self.total_pages = max(1, math.ceil(len(active_raisers) / USERS_PER_PAGE))
        
        self._setup_buttons()
    
    def _setup_buttons(self) -> None:
        """Set up pagination buttons."""
        self.clear_items()
        
        # Previous page button
        prev_btn = Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            disabled=self.total_pages <= 1,
            row=0
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)
        
        # Close button
        close_btn = Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )
        close_btn.callback = self._close
        self.add_item(close_btn)
        
        # Next page button
        next_btn = Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            disabled=self.total_pages <= 1,
            row=0
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)
    
    async def _prev_page(self, interaction: discord.Interaction) -> None:
        """Go to previous page (wraps around)."""
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = self.total_pages - 1
        
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    async def _next_page(self, interaction: discord.Interaction) -> None:
        """Go to next page (wraps around)."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        else:
            self.current_page = 0
        
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    async def _close(self, interaction: discord.Interaction) -> None:
        """Close the view."""
        self.stop()
        await interaction.response.edit_message(view=None)
    
    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page."""
        from ..database.species import get_species
        
        # Page info
        if self.total_pages > 1:
            title = f"📊 Active Pet Raisers (Page {self.current_page + 1}/{self.total_pages})"
        else:
            title = "📊 Active Pet Raisers"
        
        embed = discord.Embed(
            title=title,
            color=discord.Color.green()
        )
        
        # Get users for current page
        start_idx = self.current_page * USERS_PER_PAGE
        end_idx = start_idx + USERS_PER_PAGE
        page_users = self.active_raisers[start_idx:end_idx]
        
        # Build lines
        lines = []
        for entry in page_users:
            pet = entry["pet"]
            display_name = entry["display_name"]
            user_id = entry["user_id"]
            
            # Get species info
            species = get_species(pet.species_id)
            if species:
                pet_type = species.name
            else:
                pet_type = pet.species_id.replace("_", " ").title()
            
            # Stage display
            stage_display = pet.life_stage.capitalize()
            
            # Day display (add 1 to match main menu - "currently on day X")
            day = int(pet.age_days) + 1
            
            # Format: Two lines per user
            lines.append(f"**{display_name}** ({user_id})")
            lines.append(f"  └ {pet_type} · {stage_display} · Day {day}")
        
        embed.description = "\n".join(lines) if lines else "No active pet raisers."
        
        # Footer with total count
        total = len(self.active_raisers)
        embed.set_footer(text=f"Total: {total} active raiser{'s' if total != 1 else ''}")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only admins can interact."""
        # Allow the original command author
        if interaction.user.id == self.ctx.author.id:
            return True
        
        # Also allow other admins
        if await self.ctx.bot.is_admin(interaction.user):
            return True
        
        await interaction.response.send_message(
            "Only admins can use this view.",
            ephemeral=True
        )
        return False
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


# =============================================================================
# LIST PLAYERS PAGINATION VIEW
# =============================================================================

PLAYERS_PER_PAGE = 8  # 2 lines per player, keeps under 1024 char limit


class ListPlayersView(View):
    """Paginated view for displaying all Petcord players."""
    
    def __init__(
        self,
        cog: "MixinMeta",
        ctx: Context,
        player_lines: list,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.ctx = ctx
        self.player_lines = player_lines
        self.current_page = 0
        self.message: Optional[discord.Message] = None
        
        # Calculate total pages
        import math
        self.total_pages = max(1, math.ceil(len(player_lines) / PLAYERS_PER_PAGE))
        
        self._setup_buttons()
    
    def _setup_buttons(self) -> None:
        """Set up pagination buttons."""
        self.clear_items()
        
        # Previous page button
        prev_btn = Button(
            label="◀",
            style=discord.ButtonStyle.secondary,
            disabled=self.total_pages <= 1,
            row=0
        )
        prev_btn.callback = self._prev_page
        self.add_item(prev_btn)
        
        # Close button
        close_btn = Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )
        close_btn.callback = self._close
        self.add_item(close_btn)
        
        # Next page button
        next_btn = Button(
            label="▶",
            style=discord.ButtonStyle.secondary,
            disabled=self.total_pages <= 1,
            row=0
        )
        next_btn.callback = self._next_page
        self.add_item(next_btn)
    
    async def _prev_page(self, interaction: discord.Interaction) -> None:
        """Go to previous page (wraps around)."""
        if self.current_page > 0:
            self.current_page -= 1
        else:
            self.current_page = self.total_pages - 1
        
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    async def _next_page(self, interaction: discord.Interaction) -> None:
        """Go to next page (wraps around)."""
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        else:
            self.current_page = 0
        
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
    
    async def _close(self, interaction: discord.Interaction) -> None:
        """Close the view."""
        self.stop()
        await interaction.response.edit_message(view=None)
    
    def build_embed(self) -> discord.Embed:
        """Build the embed for the current page."""
        # Page info
        if self.total_pages > 1:
            title = f"🐾 Petcord Players (Page {self.current_page + 1}/{self.total_pages})"
        else:
            title = "🐾 Petcord Players"
        
        embed = discord.Embed(
            title=title,
            description="**Legend:** 🎓 Graduated | 💔 Lost to Neglect | 🕊️ Passed Naturally",
            color=discord.Color.blue()
        )
        
        # Get players for current page
        start_idx = self.current_page * PLAYERS_PER_PAGE
        end_idx = start_idx + PLAYERS_PER_PAGE
        page_players = self.player_lines[start_idx:end_idx]
        
        # Build lines
        lines = []
        for entry in page_players:
            name = entry["name"]
            total = entry["total_owned"]
            stats = entry["stats"]
            home = entry["home_count"]
            current = entry["current"]
            
            lines.append(f"**{name}** — Owned: {total} | 🏠 {home}")
            lines.append(f"  └ {stats} | Now: {current}")
        
        embed.add_field(
            name="Players",
            value="\n".join(lines) if lines else "No players",
            inline=False
        )
        
        # Footer with total count
        total = len(self.player_lines)
        embed.set_footer(text=f"Total: {total} player{'s' if total != 1 else ''}")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only admins can interact."""
        # Allow the original command author
        if interaction.user.id == self.ctx.author.id:
            return True
        
        # Also allow other admins
        if await self.ctx.bot.is_admin(interaction.user):
            return True
        
        await interaction.response.send_message(
            "Only admins can use this view.",
            ephemeral=True
        )
        return False
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
