import discord
from redbot.core import commands
from datetime import datetime

from ..abc import MixinMeta
from .helper_functions import welcome_to_fishing, is_channel_allowed
from ..views import MainMenuView, WelcomeView, create_main_menu_embed, FishInfoView
from ..databases.items import RODS_DATABASE, LURES_DATABASE, HATS_DATABASE, COATS_DATABASE, BOOTS_DATABASE


class User(MixinMeta):
    """User commands for Greenacres Fishing."""
    
    @commands.command(name="fish")
    @commands.guild_only()
    async def fish_command(self, ctx: commands.Context):
        """
        Start your fishing adventure!
        
        Opens the main fishing menu where you can:
        - Go Fishing to catch fish
        - Visit the Bait Shop to buy gear
        - View the Leaderboards
        """
        conf = self.db.get_conf(ctx.guild)
        
        # Check if the game is enabled
        if not conf.is_game_enabled:
            await ctx.send("Greenacres Fishing is currently disabled. Please try again later.")
            return
        
        # Check if channel is allowed (admins bypass this check)
        if not await is_channel_allowed(self.db, ctx.guild, ctx.channel.id, ctx.author, self.bot):
            return  # Silently ignore commands in non-allowed channels
        
        user_data = conf.get_user(ctx.author)
        
        # Check if this is a first-time player
        if not user_data.first_join:
            # Show welcome screen for new players
            embed = await welcome_to_fishing(
                interaction=None,
                db=self.db,
                guild=ctx.guild,
                user=ctx.author
            )
            view = WelcomeView(cog=self, author=ctx.author)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
        else:
            # Show main menu for returning players
            embed = await create_main_menu_embed(self, ctx.guild, ctx.author, ctx.prefix)
            view = MainMenuView(cog=self, author=ctx.author)
            message = await ctx.send(embed=embed, view=view)
            view.message = message

    @commands.command(name="fishinfo")
    @commands.guild_only()
    async def fish_info(self, ctx: commands.Context, target: discord.Member = None):
        """
        View fishing statistics for yourself or another player.
        
        If no target is specified, shows your own stats.
        """
        # Default to author if no target specified
        if target is None:
            target = ctx.author
        
        # Don't allow bots to be targeted
        if target.bot:
            await ctx.send("❌ Bots don't go fishing!")
            return
        
        conf = self.db.get_conf(ctx.guild)
        
        # Check if channel is allowed (admins bypass this check)
        if not await is_channel_allowed(self.db, ctx.guild, ctx.channel.id, ctx.author, self.bot):
            return  # Silently ignore commands in non-allowed channels
        
        # Check if target has any data
        if target.id not in conf.users:
            if target == ctx.author:
                await ctx.send("❌ You haven't started fishing yet! Use the `fish` command to begin.")
            else:
                await ctx.send(f"❌ **{target.display_name}** hasn't started fishing yet.")
            return
        
        user_data = conf.get_user(target)
        
        # Format first cast timestamp
        if user_data.first_cast_timestamp:
            try:
                # Try to parse as Unix timestamp (could be stored as string or int)
                ts = float(user_data.first_cast_timestamp)
                first_cast = datetime.fromtimestamp(ts).strftime("%b %d, %Y at %I:%M %p")
            except (ValueError, TypeError):
                # If it's already a formatted string, use as-is
                first_cast = user_data.first_cast_timestamp
        else:
            first_cast = "Never"
        
        # Format last scavenge timestamp
        if user_data.last_scavenge_timestamp > 0:
            last_scavenge = datetime.fromtimestamp(user_data.last_scavenge_timestamp).strftime("%Y-%m-%d %H:%M")
        else:
            last_scavenge = "Never"
        
        # Get equipped item names
        def get_rod_name(user_data) -> str:
            rod = user_data.get_equipped_rod()
            if rod:
                rod_id = rod.get("rod_id")
                return RODS_DATABASE.get(rod_id, {}).get("name", rod_id)
            return "None"
        
        def get_lure_name(user_data) -> str:
            lure = user_data.get_equipped_lure()
            if lure:
                lure_id = lure.get("lure_id")
                qty = lure.get("quantity", 0)
                name = LURES_DATABASE.get(lure_id, {}).get("name", lure_id)
                return f"{name} (x{qty})"
            return "None"
        
        def get_clothing_name(user_data, slot: str, database: dict) -> str:
            if slot == "hat":
                idx = user_data.equipped_hat_index
            elif slot == "coat":
                idx = user_data.equipped_coat_index
            elif slot == "boots":
                idx = user_data.equipped_boots_index
            else:
                return "None"
            
            if idx is not None and idx < len(user_data.current_clothing_inventory):
                item = user_data.current_clothing_inventory[idx]
                item_id = item.get("clothing_id")
                return database.get(item_id, {}).get("name", item_id)
            return "None"
        
        # Build embed
        embed = discord.Embed(
            title=f"🎣 Fishing Profile: {target.display_name}",
            color=discord.Color.blue()
        )
        
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        
        # Stats field
        embed.add_field(
            name="📊 Statistics",
            value=(
                f"🎣 First Cast: **{first_cast}**\n"
                f"🐟 Total Fish Caught: **{user_data.total_fish_ever_caught:,}**\n"
                f"🎯 Total Attempts: **{user_data.total_fishing_attempts:,}**\n"
                f"🏪 Total Fish Sold: **{user_data.total_fish_sold:,}**"
            ),
            inline=False
        )
        
        # Currency field
        embed.add_field(
            name="💰 Currency",
            value=(
                f"FishPoints: **{user_data.total_fishpoints:,}**\n"
                f"Most FP Ever: **{user_data.most_fishpoints_ever:,}**\n"
                f"🏆 Tokens: **{user_data.current_fishmaster_tokens}**\n"
                f"Most Tokens Ever: **{user_data.most_fishmaster_tokens_ever}**"
            ),
            inline=True
        )
        
        # Equipped gear field
        embed.add_field(
            name="🎒 Equipped Gear",
            value=(
                f"🎣 Rod: **{get_rod_name(user_data)}**\n"
                f"🪝 Lure: **{get_lure_name(user_data)}**\n"
                f"🎩 Hat: **{get_clothing_name(user_data, 'hat', HATS_DATABASE)}**\n"
                f"🧥 Coat: **{get_clothing_name(user_data, 'coat', COATS_DATABASE)}**\n"
                f"👢 Boots: **{get_clothing_name(user_data, 'boots', BOOTS_DATABASE)}**"
            ),
            inline=True
        )
        
        # Last scavenge
        embed.set_footer(text=f"🗑️ Last Scavenge: {last_scavenge}")
        
        # Always create the view (for Help/Close buttons)
        view = FishInfoView(cog=self, author=ctx.author, target=target, embed=embed, prefix=ctx.prefix)
        message = await ctx.send(embed=embed, view=view)
        view.message = message
