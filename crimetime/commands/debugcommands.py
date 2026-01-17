"""
CrimeTime Database Commands

Admin-only commands for importing/exporting guild data between bot instances.
"""
import json
from io import BytesIO
from datetime import datetime

import discord
from redbot.core import commands

from ..common.models import GuildSettings, User, Gang


async def is_admin_or_owner(ctx: commands.Context) -> bool:
    """Check if user can use database commands.
    
    Returns True if the user:
    - Is the bot owner, OR
    - Is the Discord server owner
    """
    if not ctx.guild:
        return False
    
    # Bot owner check
    if await ctx.bot.is_owner(ctx.author):
        return True
    
    # Server owner check
    if ctx.author.id == ctx.guild.owner_id:
        return True
    
    return False


class DatabaseCommands:
    """Mixin class for CrimeTime database commands."""

    @commands.group(name="ctdatabase", aliases=["ctdb"], invoke_without_command=True)
    @commands.check(is_admin_or_owner)
    async def ctdatabase(self, ctx: commands.Context):
        """Database commands for importing/exporting CrimeTime data.
        
        These commands allow you to backup and restore guild data,
        which is useful for migrating between bot instances.
        """
        p = ctx.clean_prefix
        await ctx.send(
            f"**CrimeTime Database Commands:**\n"
            f"`{p}ctdatabase download` - Download this guild's data as a JSON file\n"
            f"`{p}ctdatabase upload` - Upload and restore data from a JSON file\n"
            f"`{p}ctdatabase info` - Show current data statistics"
        )

    @ctdatabase.command(name="download")
    @commands.check(is_admin_or_owner)
    async def database_download(self, ctx: commands.Context):
        """Download this guild's CrimeTime data as a JSON file.
        
        Creates an in-memory JSON file containing:
        - All user data (balances, stats, inventory, equipped items)
        - All gang data (members, earnings, creation dates)
        - Guild settings (feature toggles, blackmarket state)
        
        This file can be uploaded to another bot instance using `ctdatabase upload`.
        Note: User IDs are preserved, so users must exist on both servers.
        """
        guildsettings = self.db.get_conf(ctx.guild)
        
        # Build export data
        export_data = {
            "meta": {
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat(),
                "guild_id": ctx.guild.id,
                "guild_name": ctx.guild.name,
                "user_count": len(guildsettings.users),
                "gang_count": len(guildsettings.gangs),
            },
            "guild_settings": guildsettings.model_dump()
        }
        
        try:
            # Create in-memory buffer
            buffer = BytesIO()
            formatted_json = json.dumps(export_data, indent=2, default=str)
            buffer.write(formatted_json.encode('utf-8'))
            buffer.seek(0)
            
            # Generate filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"crimetime_backup_{ctx.guild.id}_{timestamp}.json"
            
            await ctx.send(
                f"📦 **CrimeTime Data Export**\n"
                f"• Users: {len(guildsettings.users):,}\n"
                f"• Gangs: {len(guildsettings.gangs):,}\n"
                f"• Guild: {ctx.guild.name}",
                file=discord.File(buffer, filename=filename)
            )
        except Exception as e:
            await ctx.send(f"❌ Error creating export: {e}")

    @ctdatabase.command(name="upload")
    @commands.check(is_admin_or_owner)
    async def database_upload(self, ctx: commands.Context):
        """Upload and restore CrimeTime data from a JSON file.
        
        Attach a JSON file exported with `ctdatabase download` to your message,
        or reply to a message that has the file attached.
        
        **Warning:** This will REPLACE all existing data for this guild!
        
        The import will:
        - Restore all user balances, stats, and inventory
        - Restore all gang data and memberships
        - Restore guild settings (feature toggles, blackmarket state)
        """
        # Find the attachment
        attachment = None
        
        # Check current message for attachment
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
        # Check replied message for attachment
        elif ctx.message.reference and ctx.message.reference.resolved:
            ref_msg = ctx.message.reference.resolved
            if hasattr(ref_msg, 'attachments') and ref_msg.attachments:
                attachment = ref_msg.attachments[0]
        
        if not attachment:
            await ctx.send(
                "❌ No file found. Please attach a JSON file to your message, "
                "or reply to a message that has the backup file attached."
            )
            return
        
        # Validate file type
        if not attachment.filename.endswith('.json'):
            await ctx.send("❌ Invalid file type. Please provide a `.json` file.")
            return
        
        # Confirmation prompt
        await ctx.send(
            f"⚠️ **Warning: This will REPLACE all CrimeTime data for this guild!**\n\n"
            f"File: `{attachment.filename}`\n"
            f"Size: {attachment.size:,} bytes\n\n"
            f"Type `confirm` within 30 seconds to proceed."
        )
        
        try:
            msg = await ctx.bot.wait_for(
                "message",
                timeout=30,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel
            )
            if msg.content.lower() != "confirm":
                await ctx.send("❌ Import cancelled.")
                return
        except Exception:
            await ctx.send("❌ Import timed out.")
            return
        
        # Download and parse the file
        try:
            file_content = await attachment.read()
            data = json.loads(file_content.decode('utf-8'))
        except json.JSONDecodeError as e:
            await ctx.send(f"❌ Invalid JSON file: {e}")
            return
        except Exception as e:
            await ctx.send(f"❌ Error reading file: {e}")
            return
        
        # Validate structure
        if "guild_settings" not in data:
            await ctx.send("❌ Invalid backup file: missing `guild_settings` key.")
            return
        
        # Extract meta info
        meta = data.get("meta", {})
        original_guild = meta.get("guild_name", "Unknown")
        original_users = meta.get("user_count", "?")
        original_gangs = meta.get("gang_count", "?")
        
        try:
            # Reconstruct the GuildSettings from the data
            gs_data = data["guild_settings"]
            
            # Reconstruct User objects
            users_dict = {}
            for uid_str, user_data in gs_data.get("users", {}).items():
                uid = int(uid_str)
                users_dict[uid] = User(**user_data)
            
            # Reconstruct Gang objects
            gangs_dict = {}
            for gang_id, gang_data in gs_data.get("gangs", {}).items():
                gangs_dict[gang_id] = Gang(**gang_data)
            
            # Create new GuildSettings with reconstructed data
            new_settings = GuildSettings(
                users=users_dict,
                gangs=gangs_dict,
                is_mug_enabled=gs_data.get("is_mug_enabled", True),
                is_carjacking_enabled=gs_data.get("is_carjacking_enabled", False),
                is_robbery_enabled=gs_data.get("is_robbery_enabled", False),
                is_heist_enabled=gs_data.get("is_heist_enabled", False),
                is_pop_up_enabled=gs_data.get("is_pop_up_enabled", False),
                is_bank_enabled=gs_data.get("is_bank_enabled", True),
                bank_interest_rate=gs_data.get("bank_interest_rate", 0.05),
                bank_max_withdraw=gs_data.get("bank_max_withdraw", 1000000),
                is_conversion_enabled=gs_data.get("is_conversion_enabled", False),
                blackmarket_last_cycle=gs_data.get("blackmarket_last_cycle", 0),
                blackmarket_current_items=gs_data.get("blackmarket_current_items", []),
            )
            
            # Replace the guild's settings
            self.db.configs[ctx.guild.id] = new_settings
            self.save()
            
            await ctx.send(
                f"✅ **Import Successful!**\n\n"
                f"**Source:** {original_guild}\n"
                f"**Imported:**\n"
                f"• Users: {len(users_dict):,}\n"
                f"• Gangs: {len(gangs_dict):,}\n\n"
                f"All CrimeTime data has been restored."
            )
            
        except Exception as e:
            await ctx.send(f"❌ Error importing data: {e}")

    @ctdatabase.command(name="info")
    @commands.check(is_admin_or_owner)
    async def database_info(self, ctx: commands.Context):
        """Show current CrimeTime data statistics for this guild."""
        guildsettings = self.db.get_conf(ctx.guild)
        
        # Calculate statistics
        total_users = len(guildsettings.users)
        total_gangs = len(guildsettings.gangs)
        
        # Calculate total wealth
        total_cash = sum(u.balance for u in guildsettings.users.values())
        total_bars = sum(u.gold_bars for u in guildsettings.users.values())
        total_gems = sum(u.gems_owned for u in guildsettings.users.values())
        
        # Count users with activity
        active_users = sum(
            1 for u in guildsettings.users.values() 
            if u.balance > 0 or u.p_wins > 0 or u.pve_win > 0
        )
        
        # Feature toggles
        features = []
        if guildsettings.is_mug_enabled:
            features.append("Mug")
        if guildsettings.is_carjacking_enabled:
            features.append("Carjack")
        if guildsettings.is_robbery_enabled:
            features.append("Robbery")
        if guildsettings.is_heist_enabled:
            features.append("Heist")
        if guildsettings.is_pop_up_enabled:
            features.append("Pop-ups")
        
        inner_width = 44
        border = "═" * inner_width
        
        lines = [
            "```",
            "╔" + border + "╗",
            "║" + "CRIMETIME DATA INFO".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + f" Total Users    : {total_users:,}".ljust(inner_width) + "║",
            "║" + f" Active Users   : {active_users:,}".ljust(inner_width) + "║",
            "║" + f" Total Gangs    : {total_gangs:,}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " ECONOMY".center(inner_width) + "║",
            "║" + f" Total Cash     : ${total_cash:,}".ljust(inner_width) + "║",
            "║" + f" Total Gold Bars: {total_bars:,}".ljust(inner_width) + "║",
            "║" + f" Total Gems     : {total_gems:,}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + f" Features: {', '.join(features) or 'None'}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))

    @ctdatabase.error
    async def ctdatabase_error(self, ctx: commands.Context, error):
        """Handle permission errors for ctdatabase commands."""
        if isinstance(error, commands.CheckFailure):
            await ctx.send("❌ You don't have permission to use this command. "
                          "Only bot owners, server owners, and Red admins can use database commands.")
        else:
            raise error
