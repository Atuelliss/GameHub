import asyncio
import datetime
import logging
import discord
import random
import time
import typing as t
import math

from redbot.core.utils.chat_formatting import humanize_timedelta
from redbot.core import commands, bank
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from . import blackmarket
from . import carjack
from .common.models import DB, User, Gang, GuildSettings
from .common.helpers import update_pbonus as helper_update_pbonus, recalculate_p_bonus
from .dynamic_menu import DynamicMenu
from .commands.debugcommands import DatabaseCommands
from .commands.admin_commands import AdminCommands
#from blackmarket import all_items

log = logging.getLogger("red.crimetime")


class BlackmarketBuyView(discord.ui.View):
    """View with buttons to purchase blackmarket items."""
    
    def __init__(self, cog, ctx: commands.Context, items: list, user, guildsettings):
        super().__init__(timeout=180)  # 3 minute timeout
        self.cog = cog
        self.ctx = ctx
        self.author = ctx.author
        self.items = items
        self.user = user
        self.guildsettings = guildsettings
        self.message = None
        
        # Create buttons for each item
        for idx, item in enumerate(items):
            # Check if user already owns this item
            slot_name = blackmarket.get_slot_name_lower(item["wear"])
            owned_attr = f"owned_{slot_name}"
            worn_attr = f"worn_{slot_name}"
            owned_dict = getattr(user, owned_attr, {})
            worn_keyword = getattr(user, worn_attr, None)
            
            already_owned = item["keyword"] in owned_dict or worn_keyword == item["keyword"]
            
            # Row 0 for armor (first 3), Row 1 for weapon (4th)
            row = 0 if idx < 3 else 1
            
            button = discord.ui.Button(
                label=f"Buy #{idx + 1}",
                style=discord.ButtonStyle.secondary if already_owned else discord.ButtonStyle.primary,
                disabled=already_owned,
                row=row,
                custom_id=f"buy_{idx}"
            )
            button.callback = self.make_callback(idx, item)
            self.add_item(button)
        
        # Add close button on Row 1 (next to weapon button)
        close_button = discord.ui.Button(
            label="Close",
            style=discord.ButtonStyle.danger,
            row=1,
            custom_id="close"
        )
        close_button.callback = self.close_callback
        self.add_item(close_button)
    
    def make_callback(self, idx: int, item: dict):
        async def callback(interaction: discord.Interaction):
            # Check if it's the original author
            if interaction.user.id != self.author.id:
                await interaction.response.send_message("This isn't your menu!", ephemeral=True)
                return
            
            # Refresh user data
            user = self.guildsettings.get_user(self.author)
            keyword = item["keyword"]
            cost = item["cost"]
            slot_name = blackmarket.get_slot_name_lower(item["wear"])
            owned_attr = f"owned_{slot_name}"
            worn_attr = f"worn_{slot_name}"
            owned_dict = getattr(user, owned_attr, {})
            worn_keyword = getattr(user, worn_attr, None)
            
            # Check if user already owns or is wearing this item (race condition prevention)
            if keyword in owned_dict or worn_keyword == keyword:
                await interaction.response.send_message(
                    f"You already own **{item['name']}**!",
                    ephemeral=True
                )
                return
            
            # Check if user can afford it
            if user.balance < cost:
                await interaction.response.send_message(
                    f"You don't have enough cash! You need ${cost:,} but only have ${user.balance:,}.",
                    ephemeral=True
                )
                return
            
            # Purchase the item
            user.balance -= cost
            owned_dict[keyword] = 1
            setattr(user, owned_attr, owned_dict)
            self.cog.save()
            
            # Disable this button
            for child in self.children:
                if child.custom_id == f"buy_{idx}":
                    child.disabled = True
                    child.style = discord.ButtonStyle.secondary
                    break
            
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(
                f"✅ Purchased **{item['name']}** for ${cost:,}! Use `ctinv wear {keyword}` to equip it.",
                ephemeral=True
            )
        
        return callback
    
    async def close_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your menu!", ephemeral=True)
            return
        
        await interaction.response.edit_message(view=None)
        self.stop()
    
    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass


class CrimeTime(DatabaseCommands, AdminCommands, commands.Cog):
    """
    A crime mini-game cog for Red-DiscordBot.
    """
    __author__ = "Jayar(Vainne)"
    __version__ = "0.0.1"

    def __init__(self, bot: Red):
        super().__init__()
        self.bot: Red = bot
        self.db: DB = DB()
        self.target_limit = 5 # number of targets to track against

        # Cooldowns separated by target or not target.
        self.pvpcooldown = commands.CooldownMapping.from_cooldown(1, 60, commands.BucketType.user)
        self.pvecooldown = commands.CooldownMapping.from_cooldown(1, 30, commands.BucketType.user)
        # Cooldown for investment command, cash to gold/diamonds. 12hours.
        self.investcooldown = commands.CooldownMapping.from_cooldown(1, 43200, commands.BucketType.user)
        # Cooldown for Blitz command, once per hour players can join each other attacking things.
        self.blitzcooldown = commands.CooldownMapping.from_cooldown(1, 3600, commands.BucketType.user)
        # Future cooldown spot for Robberies.

        # States
        self._saving = False
        self._save_pending = False
        
        # Background task handle
        self.blackmarket_task: asyncio.Task | None = None

    def cog_unload(self):
        """Clean up when cog is unloaded."""
        if self.blackmarket_task:
            self.blackmarket_task.cancel()

    def format_help_for_context(self, ctx: commands.Context):
        helpcmd = super().format_help_for_context(ctx)
        txt = "Version: {}\nAuthor: {}".format(self.__version__, self.__author__)
        return f"{helpcmd}\n\n{txt}"

    async def red_delete_data_for_user(self, *args, **kwargs):
        return

    async def red_get_data_for_user(self, *args, **kwargs):
        return

    async def cog_load(self) -> None:
        asyncio.create_task(self.initialize())

    async def initialize(self) -> None:
        await self.bot.wait_until_red_ready()
        try:
            self.db = await asyncio.to_thread(DB.from_file, cog_data_path(self) / "db.json")
            log.info("Config loaded")
        except Exception as e:
            log.exception("Failed to load config, initializing empty DB", exc_info=e)
            self.db = DB()
        # Start the blackmarket cycling task
        self.blackmarket_task = asyncio.create_task(self.blackmarket_cycle_loop())
        log.debug("Blackmarket cycle task started")

    async def blackmarket_cycle_loop(self) -> None:
        """Background task that checks and rotates blackmarket every 60 seconds."""
        await self.bot.wait_until_red_ready()
        
        # Immediate check on startup (don't wait 60 seconds for first check)
        try:
            current_time = time.time()
            for guild_id, settings in self.db.configs.items():
                if self.should_cycle_blackmarket(current_time, settings.blackmarket_last_cycle):
                    self.rotate_blackmarket(settings)
                    settings.blackmarket_last_cycle = current_time
                    log.debug(f"Blackmarket rotated for guild {guild_id} (startup check)")
            self.save()
        except Exception as e:
            log.exception("Error in blackmarket startup check", exc_info=e)
        
        # Regular 60-second check loop
        while True:
            try:
                await asyncio.sleep(60)  # Check every 60 seconds
                current_time = time.time()
                
                for guild_id, settings in self.db.configs.items():
                    if self.should_cycle_blackmarket(current_time, settings.blackmarket_last_cycle):
                        self.rotate_blackmarket(settings)
                        settings.blackmarket_last_cycle = current_time
                        log.debug(f"Blackmarket rotated for guild {guild_id}")
                
                self.save()
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.exception("Error in blackmarket cycle loop", exc_info=e)

    def should_cycle_blackmarket(self, current_time: float, last_cycle: float) -> bool:
        """Check if blackmarket should cycle based on 30-minute intervals aligned to clock (:00 and :30)."""
        now = datetime.datetime.fromtimestamp(current_time)
        
        # Determine the current cycle boundary (either :00 or :30 of the current hour)
        if now.minute >= 30:
            current_boundary = now.replace(minute=30, second=0, microsecond=0)
        else:
            current_boundary = now.replace(minute=0, second=0, microsecond=0)
        
        current_boundary_ts = current_boundary.timestamp()
        
        # If never cycled, or if we've crossed into a new boundary since last cycle
        if last_cycle == 0 or last_cycle < current_boundary_ts:
            return True
        
        return False

    def rotate_blackmarket(self, settings: GuildSettings) -> None:
        """Rotate the blackmarket items - 3 random armor pieces + 1 weapon, excluding current items."""
        # Get current item keywords to exclude
        current_keywords = set()
        if settings.blackmarket_current_items:
            current_keywords = {item.get("keyword") for item in settings.blackmarket_current_items}
        
        # Select 3 random armor categories (from head, chest, legs, feet)
        selected_categories = random.sample(blackmarket.armor_categories, 3)
        
        # Pick 1 random item from each selected armor category, excluding current items
        new_items = []
        for cat in selected_categories:
            available = [item for item in cat if item["keyword"] not in current_keywords]
            # If all items in category are current (unlikely), fall back to any item
            if not available:
                available = cat
            new_items.append(random.choice(available))
        
        # Always add 1 random weapon, excluding current weapon
        available_weapons = [w for w in blackmarket.tier_1_weapon if w["keyword"] not in current_keywords]
        if not available_weapons:
            available_weapons = blackmarket.tier_1_weapon
        new_items.append(random.choice(available_weapons))
        
        settings.blackmarket_current_items = new_items

    def get_time_until_next_cycle(self, settings: GuildSettings) -> int:
        """Get seconds until next blackmarket cycle (aligned to :00 or :30)."""
        now = datetime.datetime.now()
        
        # Find the next boundary (:00 or :30)
        if now.minute >= 30:
            # Next boundary is :00 of the next hour
            next_boundary = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        else:
            # Next boundary is :30 of current hour
            next_boundary = now.replace(minute=30, second=0, microsecond=0)
        
        remaining = (next_boundary - now).total_seconds()
        return max(0, int(remaining))

    def save(self) -> None:
        self._save_pending = True
        
        async def _save():
            if self._saving:
                return
            try:
                self._saving = True
                self._save_pending = False
                await asyncio.to_thread(self.db.to_file, cog_data_path(self) / "db.json")
            except Exception as e:
                log.exception("Failed to save config", exc_info=e)
            finally:
                self._saving = False
                # Check if another save was requested while we were saving
                if self._save_pending:
                    asyncio.create_task(_save())

        asyncio.create_task(_save())

########## Information Commands ##########
    # Crimetime Info Message
    @commands.command()
    async def crimetime(self, ctx: commands.Context):
        """Sends an embedded message with information on the overall game."""
    
    # Check if the bot has permission to send embeds
        if not ctx.channel.permissions_for(ctx.me).embed_links:
            return await ctx.send("I need the 'Embed Links' permission to display this message properly.")
        try:
            prefix = ctx.clean_prefix
            info_embed = discord.Embed(
                title="What is CrimeTime?", 
                description="A criminal mini-game cog for Red-DiscordBot created by Jayar(aka-Vainne).", 
                color=0xffd700)
            info_embed.add_field(
                name="*What is the purpose of the game?*",
                value="Crimetime is a Discord game designed to allow Players to take on the role of a Criminal and attempt to gain as much wealth as possible through various means.\n \nThe game came about as a joke at first on the Vertyco Ark Servers but has since expanded in scope after interest from Players was shown. It is currently in development and is nowhere near complete yet.",
                inline=False)
            info_embed.add_field(
                name="*The current commands available for use in the game are:*",
                value=f"`{prefix}mug` - Command to mug NPCs and Players.\n`{prefix}mug consider <user>` - Compares your chances against another player.\n`{prefix}cttarget` - Displays your recent mugging targets.\n`{prefix}mugcheck` - Checks a User's Cash Balance and Ratio.\n`{prefix}mugclear` - Resets your stats for a fee.\n`{prefix}ctwealth` - Displays total wealth $ assets of a User.\n`{prefix}ctbm` - View and buy/sell items from the BlackMarket.\n`{prefix}ctgive` - Transfer assets to another Player.\n`{prefix}ctinv` - Checks and allows wear/remove of items in your inventory.\n`{prefix}ctinvest` - Convert Cash to Gold Bars or Gems.\n`{prefix}ctliquidate` - Convert Bars or Gems to Cash.\n`{prefix}ctgang` - Commands to create/join/manage Gangs.",
                inline=False)
            await ctx.send(embed=info_embed)
        except discord.HTTPException:
            await ctx.send("An error occurred while sending the message. Please try again later.")

#Cttarget command, displays most recent targets of Mug
    @commands.command()
    async def cttarget(self, ctx: commands.Context):
        '''Prints out a brief list of the user's most recent target list.'''
        member = ctx.author
        guild = ctx.guild
        guildsettings = self.db.get_conf(guild)
        user = guildsettings.get_user(member)

        # Convert user IDs to display names with IDs
        recent_target_ids = user.recent_targets
        recent_targets = []

        for uid in recent_target_ids:
            target = guild.get_member(uid)
            if target:
                recent_targets.append(f"{target.display_name} ({uid})")
            else:
                recent_targets.append(f"Unknown User ({uid})")

        target_list = "\n".join(recent_targets) if recent_targets else "no one recently"
        await ctx.send(f"-=-=-=-=-=-=-=-=-=-=-=-=-=-\n*You have recently attacked:*\n-=-=-=-=-=-=-=-=-=-=-=-=-=-\n{target_list}\n-=-=-=-=-=-=-=-=-=-=-=-=-=-\nTry attacking others NOT on this list to continue.")

    # Check balance and stats specifically attributed to the Mug command.
    async def update_pbonus(self, ctx: commands.Context, member: discord.Member) -> None:
        """Recalculate and update a user's P-bonus based on their win/loss ratio."""
        await helper_update_pbonus(self, ctx, member)

    # Check balance and stats specifically attributed to the Mug command.
    @commands.command()
    async def ctstat(self, ctx: commands.Context, member: discord.Member = None):
        """Displays Player's wealth, gear, and stats."""
        member  = member or ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        cash = user.balance
        bars = user.gold_bars        
        gems = user.gems_owned
        total_wealth = cash + (bars * self.db.bar_value) + (gems * self.db.gem_value)
        
        # Helper to get worn item name from keyword
        def get_worn_name(keyword):
            if not keyword:
                return "None"
            item = blackmarket.get_item_by_keyword(keyword)
            return item["name"] if item else keyword
        
        # Get worn gear names (or "None" if empty)
        head_item = get_worn_name(user.worn_head)
        chest_item = get_worn_name(user.worn_chest)
        legs_item = get_worn_name(user.worn_legs)
        feet_item = get_worn_name(user.worn_feet)
        weapon_item = get_worn_name(user.worn_weapon)
        consumable_item = get_worn_name(user.worn_consumable)
        
        p_wins = user.p_wins
        p_loss = user.p_losses
        p_ratio = user.p_ratio
        p_bonus = user.p_bonus
        atk_bonus = user.player_atk_bonus
        def_bonus = user.player_def_bonus
        balance = user.balance
        r_wins = user.r_wins
        r_loss = user.r_losses
        r_ratio = user.r_ratio_str
        h_wins = user.h_wins
        h_loss = user.h_losses
        h_ratio = user.h_ratio_str
        
        inner_width = 46
        border = "═" * inner_width
        
        # Truncate long item names to fit the box
        def truncate(text, max_len=28):
            return text[:max_len] if len(text) > max_len else text
        
        # Wrap equipped items in brackets for ini syntax highlighting (makes them blue)
        def format_gear(name):
            if name == "None":
                return "None"
            return f"[{truncate(name)}]"
        
        lines = [
            "```ini",
            "╔" + border + "╗",
            "║" + "PLAYER STATS".center(inner_width) + "║",
            "║" + f"~ {member.display_name} ~".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " Player Information".ljust(inner_width) + "║",
            "║" + f"   Level : {user.player_level:<6} Exp : {user.player_exp}".ljust(inner_width) + "║",
            "║" + f"   To Next Level : {user.tnl_exp}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " Wealth".ljust(inner_width) + "║",
            "║" + f"   Cash      :          {f'${balance:,}':>14}".ljust(inner_width) + "║",
            "║" + f"   Gold Bars : {bars:>3}  →   {f'${self.db.bar_value*bars:,}':>14}".ljust(inner_width) + "║",
            "║" + f"   Gems      : {gems:>3}  →   {f'${self.db.gem_value*gems:,}':>14}".ljust(inner_width) + "║",
            "║" + f"   Total     :          {f'${total_wealth:,}':>14}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " Equipped Gear".ljust(inner_width) + "║",
            "║" + f"   Head       : {format_gear(head_item)}".ljust(inner_width) + "║",
            "║" + f"   Chest      : {format_gear(chest_item)}".ljust(inner_width) + "║",
            "║" + f"   Legs       : {format_gear(legs_item)}".ljust(inner_width) + "║",
            "║" + f"   Feet       : {format_gear(feet_item)}".ljust(inner_width) + "║",
            "║" + f"   Weapon     : {format_gear(weapon_item)}".ljust(inner_width) + "║",
            "║" + f"   Consumable : {format_gear(consumable_item)}".ljust(inner_width) + "║",
            "║" + f"   Atk Bonus : +{atk_bonus:.2f}  Def Bonus : +{def_bonus:.2f}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " Combat Stats".ljust(inner_width) + "║",
            "║" + f"   PvP     : {p_wins:>4}W / {p_loss}L   Ratio: {p_ratio:.2f}".ljust(inner_width) + "║",
            "║" + f"   Robbery : {r_wins:>4}W / {r_loss}L   Ratio: {r_ratio}".ljust(inner_width) + "║",
            "║" + f"   Heist   : {h_wins:>4}W / {h_loss}L   Ratio: {h_ratio}".ljust(inner_width) + "║",
            "║" + f"   P-Bonus : {p_bonus:+.2f}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))


    # Check total wealth of all currencies.
    @commands.command()
    async def ctwealth(self, ctx: commands.Context, member: discord.Member = None):
        """Checks the total assets of a User."""
        member = member or ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        cash = user.balance
        gold = user.gold_bars
        gold_value = self.db.bar_value
        gems = user.gems_owned
        gem_value = self.db.gem_value
        gold_total = gold * gold_value
        gem_total = gems * gem_value
        total_value = cash + gold_total + gem_total
        
        inner_width = 44
        border = "═" * inner_width
        
        lines = [
            "```",
            "╔" + border + "╗",
            "║" + "WEALTH REPORT".center(inner_width) + "║",
            "║" + f"~ {member.display_name} ~".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + f"  Cash      :            ${cash:>12,}".ljust(inner_width) + "║",
            "║" + f"  Gold Bars : {gold:>3}  →     ${gold_total:>12,}".ljust(inner_width) + "║",
            "║" + f"  Gems      : {gems:>3}  →     ${gem_total:>12,}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + f"  TOTAL WEALTH :         ${total_value:>12,}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))

    # Check balance and stats specifically attributed to the Mug command.
    @commands.command()
    async def mugcheck(self, ctx: commands.Context, member: discord.Member = None):
        """Checks the Balance, Wins/Losses, and Ratio of a User."""
        member  = member or ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        await self.update_pbonus(ctx, member)
        user = guildsettings.get_user(member)        
        p_wins = user.p_wins
        p_loss = user.p_losses
        p_ratio = user.p_ratio
        p_bonus = user.p_bonus
        balance = user.balance
        atk_bonus = user.player_atk_bonus
        def_bonus = user.player_def_bonus
        
        inner_width = 46
        border = "═" * inner_width
        
        lines = [
            "```ini",
            "╔" + border + "╗",
            "║" + "MUG CHECK".center(inner_width) + "║",
            "║" + f"~ {member.display_name} ~".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " Balance".ljust(inner_width) + "║",
            "║" + f"   Cash : {f'${balance:,}':>18}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " PvP Stats".ljust(inner_width) + "║",
            "║" + f"   Wins   : {p_wins:>4}".ljust(inner_width) + "║",
            "║" + f"   Losses : {p_loss:>4}".ljust(inner_width) + "║",
            "║" + f"   Ratio  : {p_ratio:.2f}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " Bonuses".ljust(inner_width) + "║",
            "║" + f"   P-Bonus   : {p_bonus:+.2f}".ljust(inner_width) + "║",
            "║" + f"   Atk Bonus : {atk_bonus:+.2f}".ljust(inner_width) + "║",
            "║" + f"   Def Bonus : {def_bonus:+.2f}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))

########## Economic/Asset Commands ##########
    # CtInvest function
    # Convert Cash to Gold or Gemstones
    @commands.group(invoke_without_command=True)
    async def ctinvest(self, ctx: commands.Context):
        """Ability for players to convert currency forms."""
        p = ctx.clean_prefix
        await ctx.send(f"Please specify a valid subcommand, e.g.:\n"
                       f"`{p}ctinvest bars <amount>`\n"
                       f"`{p}ctinvest gems <amount>`")

    @ctinvest.command(name="bars")
    async def invest_bars(self, ctx: commands.Context, amount: int = None):
        """Allows a Player to convert cash to Gold Bars."""
        member = ctx.author
        investbucket = self.investcooldown.get_bucket(ctx.message)
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)  
        if user is None:
            await ctx.send("User data not found. Please try again later.")
            return
        if amount is None:
            await ctx.send("You must specify the amount of gold bars to invest in.")
            return
        if amount <= 0:
            await ctx.send("Please enter a valid number of gold bars to invest in.")
            return

        gold_value = self.db.bar_value
        cash_needed = amount * gold_value

        secondsleft = investbucket.update_rate_limit()
        if user.balance < cash_needed:
            await ctx.send(f"You do not have the ${cash_needed} needed for that transaction.")
            return
        if secondsleft:
            wait_time = humanize_timedelta(seconds=int(secondsleft))
            await ctx.send(f"You must wait {wait_time} before investing again.")
            return
        else:
            user.balance -= cash_needed
            user.gold_bars += amount
            self.save()
            if amount == 1:
                await ctx.send(f"You invested ${cash_needed} into {amount} gold bar!\nYour investment is safe from mugging for now!")
            else:
                await ctx.send(f"You invested ${cash_needed} into {amount} gold bars!\nYour investment is safe from mugging for now!")

    @ctinvest.command(name="gems")
    async def invest_gems(self, ctx: commands.Context, amount: int = None):
        """Allows a Player to convert cash to gems."""
        member = ctx.author
        investbucket = self.investcooldown.get_bucket(ctx.message)
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        if user is None:
            await ctx.send("User data not found. Please try again later.")
            return
        if amount is None:
            await ctx.send("You must specify the amount of gems to invest in.")
            return
        if amount <= 0:
            await ctx.send("Please enter a valid number of gems to invest in.")
            return

        gem_value = self.db.gem_value
        cash_needed = amount * gem_value

        secondsleft = investbucket.update_rate_limit()
        if user.balance < cash_needed:
            await ctx.send(f"You do not have the ${cash_needed} for that transaction.")
            return
        if secondsleft:
            wait_time = humanize_timedelta(seconds=int(secondsleft))
            await ctx.send(f"You must wait {wait_time} before investing again.")
            return        
        else:
            user.balance -= cash_needed
            user.gems_owned += amount
            self.save()
            if amount == 1:
                await ctx.send(f"You invested ${cash_needed} into {amount} gem!\nYour investment is safe from mugging for now!")
            else:
                await ctx.send(f"You invested ${cash_needed} into {amount} gems!\nYour investment is safe from mugging for now!")

    @ctinvest.command(name="b2g")
    async def bars_to_gems(self, ctx: commands.Context, amount: int = None):
        """Allows a Player to convert Gold Bars to Gems."""
        member = ctx.author
        investbucket = self.investcooldown.get_bucket(ctx.message)
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)  
        if user is None:
            await ctx.send("User data not found. Please try again later.")
            return
        if amount is None:
            await ctx.send("You must specify the amount of gold bars to invest in.")
            return
        if amount <= 0:
            await ctx.send("Please enter a valid number of gold bars to invest in.")
            return
        if amount % 2 != 0:
            await ctx.send("You must input an even number of gold bars. (2 bars = 1 gem)")
            return
        if user.gold_bars < amount:
            await ctx.send("You do not have enough gold bars for that transaction.")
            return
        gems_to_add = amount // 2
        user.gold_bars -= amount
        user.gems_owned += gems_to_add
        self.save()
        await ctx.send(f"You successfully converted {amount} gold bars into {gems_to_add} gems!")
     
    # Liquidation commands, turns gems/bars into cash.
    @commands.group(invoke_without_command=True, aliases=["ctld"])
    async def ctliquidate(self, ctx: commands.Context):
        """Ability for players to convert currency forms."""
        p = ctx.clean_prefix
        await ctx.send(f"Please specify a valid subcommand, e.g.:\n"
                       f"`{p}ctliquidate bars <amount>`\n"
                       f"`{p}ctliquidate gems <amount>`")

    @ctliquidate.command(name="bars")
    async def liquidate_bars(self, ctx: commands.Context, amount: int = None):
        """Allows a Player to convert Gold Bars to Cash."""
        member = ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        if user is None:
            await ctx.send("User data not found. Please try again later.")
            return
        if amount is None:
            await ctx.send("You must specify the amount of gold bars to convert.")
            return
        if amount <= 0:
            await ctx.send("Please enter a valid number of gold bars to convert.")
            return

        gold_value = self.db.bar_value
        cash_payout = amount * gold_value

        if user.gold_bars < amount:
            await ctx.send("You do not have enough gold bars for that transaction.")
            return
        else:
            user.balance += cash_payout
            user.gold_bars -= amount
            self.save()
            if amount == 1:
                await ctx.send(f"You converted {amount} bar into ${cash_payout}!")
            else:
                await ctx.send(f"You converted {amount} bars into ${cash_payout}!")

    @ctliquidate.command(name="gems")
    async def liquidate_gems(self, ctx: commands.Context, amount: int = None):
        """Allows a Player to convert gems to cash."""
        member = ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        if user is None:
            await ctx.send("User data not found. Please try again later.")
            return
        if amount is None:
            await ctx.send("You must specify the amount of gems to liquidate.")
            return
        if amount <= 0:
            await ctx.send("Please enter a valid number of gems to liquidate.")
            return       

        gem_value = self.db.gem_value
        cash_payout = amount * gem_value

        if user.gems_owned < amount:
            await ctx.send("You do not have enough gems for that transaction.")
            return
        else:
            user.balance += cash_payout
            user.gems_owned -= amount
            self.save()
            if amount == 1:
                await ctx.send(f"You converted {amount} gem into ${cash_payout}!")
            else:
                await ctx.send(f"You converted {amount} gems into ${cash_payout}!")
    
    # Ability for Players to give currency to others.
    # NOTE: give_gems is intentionally omitted - gems cannot be transferred between players by design.
    @commands.group(invoke_without_command=True)
    async def ctgive(self, ctx: commands.Context):
        """Ability for players to transfer currency forms."""
        p = ctx.clean_prefix
        await ctx.send(f"Please specify a valid subcommand, e.g., `{p}ctgive cash @user amount`.")

    #Give another player Cash.
    @ctgive.command(name="cash")
    async def give_cash(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Allows a Player to give a form of Currency to another user."""
        
        # Ensure target is not None and not the giver
        if target == ctx.author:
            await ctx.send("You cannot do this alone; you must target another user.")
            return
        
        # Prevent giving to bots
        if target.bot:
            await ctx.send("You cannot give currency to bots!")
            return

        # Get user data
        guildsettings = self.db.get_conf(ctx.guild)
        giver = guildsettings.get_user(ctx.author)
        target_user = guildsettings.get_user(target)

        # Validate amount
        if amount <= 0:
            await ctx.send("You must send a positive amount.")
            return

        # Ensure giver has enough balance
        if giver.balance < amount:
            await ctx.send("You do not have that much to give!!")
            return

        # Transfer currency
        giver.balance -= amount
        target_user.balance += amount
        self.save()
        await ctx.send(f"You gave {target.mention} ${amount}.")

    #Give another player Gold Bars
    @ctgive.command(name="bars")
    async def give_gold_bars(self, ctx: commands.Context, target: discord.Member, amount: int):
        """Allows a Player to give a form of Currency to another user."""
        
        # Ensure target is not None and not the giver
        if target == ctx.author:
            await ctx.send("You cannot do this alone; you must target another user.")
            return
        
        # Prevent giving to bots
        if target.bot:
            await ctx.send("You cannot give currency to bots!")
            return

        # Get user data
        guildsettings = self.db.get_conf(ctx.guild)
        giver = guildsettings.get_user(ctx.author)
        target_user = guildsettings.get_user(target)

        # Validate amount
        if amount <= 0:
            await ctx.send("You must send a positive amount.")
            return

        # Ensure giver has enough balance
        if giver.gold_bars < amount:
            await ctx.send("You do not have that much to give!!")
            return

        # Transfer currency
        giver.gold_bars -= amount
        target_user.gold_bars += amount
        self.save()
        if amount == 1:
            await ctx.send(f"You gave {target.mention} {amount} gold bar.")
        else:
            await ctx.send(f"You gave {target.mention} {amount} gold bars.")

    # Players can convert Gems into Discord Currency
    @commands.command()
    async def ctconvert(self, ctx: commands.Context, amount: str = None):
        """Convert gems to Discord currency (if enabled)."""
        member = ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)

        # Ensure conversion is enabled
        if not self.db.bank_conversion_enabled:
            await ctx.send("Conversion is currently disabled. You cannot exchange gems at this time.")
            return
        
        # Ensure user inputs an amount
        if amount is None:
            await ctx.send(f"How many gems would you like to convert? Use `{ctx.clean_prefix}ctconvert #`")
            return
        
        # Check if amount is valid integer
        try:
            amount = int(amount)
        except ValueError:
            await ctx.send("Please provide a whole number of gems to convert.")
            return
        
        # Check if amount is positive
        if amount <= 0:
            await ctx.send("You must convert a positive number of gems.")
            return

        # Check if user has enough gems
        if user.gems_owned < amount:
            await ctx.send(f"You only have {user.gems_owned} gems. You cannot convert {amount}.")
            return
        
        # Convert the gems and deposit into Redbot Bank
        currency_to_deposit = (amount * self.db.gem_conversion_value)
        user.gems_owned -= amount
        await bank.deposit_credits(ctx.author, currency_to_deposit)
        currency_name = await bank.get_currency_name(ctx.guild)
        await ctx.send(f"You converted {amount} gems into {currency_to_deposit} {currency_name}.")
        self.save()

########## Actual Gameplay Commands ##########
    # Actually run the MUG command.
    @commands.group(invoke_without_command=True)
    async def mug(self, ctx: commands.Context, target: discord.Member = None):
        """This command can be used for both PvE and PvP mugging."""
        guildsettings = self.db.get_conf(ctx.guild)
        if not guildsettings.is_mug_enabled:
            await ctx.send("Mugging is currently disabled in this server.")
            return

        if target is not None and target == ctx.author: # Targetting yourself does nothing.
            await ctx.send("You reach into your pockets and grab your wallet, what now?")
            return
        if target is not None and target.bot: # No targeting Bots!
            await ctx.send("You cannot target the Bots!")
            return
        
        pvpbucket = self.pvpcooldown.get_bucket(ctx.message) # Cooldown for Mug pve
        pvebucket = self.pvecooldown.get_bucket(ctx.message) # Cooldown for Mug pvp
        author    = ctx.author
        #Rating = Easy
        stranger1 = ["a smart-mouthed boy", "a grouchy old man", "an elderly woman", "a sweet foreign couple",  "a lady-of-the-night", 
                    "a random stranger", "a stuffy-looking banker", "a creepy little girl", "a sad-faced clown", "a Dwarf in a penguin costume", 
                    "a sleep-deprived college Student", "a scruffy Puppy with a wallet in it's mouth", "a hyper Ballerina", 
                    "a boy dressed as a Stormtrooper", "a girl dressed as Princess Leia", "a baby in a stroller", "a group of drunk frat boys", 
                    "a poor girl doing the morning walk of shame", "another mugger who's bad at their job", "a man in a transparent banana costume",
                    "an angry jawa holding an oddly-thrusting mechanism", "two Furries fighting over an 'Uwu'",
                    "a dude in drag posting a thirst-trap on tiktok", "a mighty keyboard-warrior with cheetoh dust on his face", "a goat-hearder",
                    "Stormtrooper TK-421 who's firing at you and missing every shot", "an escaped mental patient oblivious to their surroundings",
                    "a Mogwai doused in water", "a tiny fairy trying to eat an oversized grape"]
        #Rating = Medium
        stranger2 = ["a man in a business suit", "a doped-out gang-banger", "an off-duty policeman", "a local politician", 
                     "a scrawny meth-head missing most of his teeth", "Chuck Schumer's personal assistant", "the Villainess Heiress", 
                     "an Elvis Presley impersonator shaking his hips to a song", "E.T. trying to hitchike home", "some juggling seals balancing on beach balls",
                     "an elderly woman just trying to cross the street", "a ten-year old little punk", "a meth-gator from the Florida swamps", 
                     "a Canadian Goose with squinty eyes", "Kano from Mortal Kombat, down on his luck", "a Jordanian terrorist searching for the Zohan",
                     "a clothed Carcharodontosaurus, wiping his runny nose with a kleenex", "Bart Simpson coming out of a firework stand"]
        #Rating = Hard
        stranger3 = ["Elon Musk leaving a DOGE meeting", "Bill Clinton, walking with his zipper down", "Vladamir Putin, humming 'Putin on the ritz'", "Bigfoot!!", "Steve Job's Corpse", 
                     "Roseanne Barr running from a BET awards show", "Borat!!", "a shirtless Florida-man", "Megatron", "John Wick's dog", "Bill Murray in a tracksuit with a cigar", 
                     "Joe Rogan", "Michelle Obama eating an ice-cream cone", "Will Smith's right-hand", "Macho-Man Randy Savage, 'Oooooh yeeeah'", "Greta Thunberg chasing cow farts", 
                     "Bill Murray in a zombie costume staring into the distance", "Mrs. Doubtfire awkwardly running to help someone", "90-year old Hulk Hogan in his iconic red/yellow wrestling gear",
                     "Forest Gump screaming, 'How are you run-nang so fast'"]
        rating_easy    = 0.2
        rating_medium  = 0.5
        rating_hard    = 0.7
        difficulty_choice = random.choice([stranger1, stranger2, stranger3])
        mugger_user = guildsettings.get_user(ctx.author)
        pve_attack = random.uniform(0, 1) 
        pvp_attack = random.uniform(0, 1) + mugger_user.p_bonus + mugger_user.player_atk_bonus

        if target is None:
            secondsleft = pvebucket.update_rate_limit()
            if secondsleft:
                wait_time = humanize_timedelta(seconds=int(secondsleft))
                return await ctx.send(f"You must wait {wait_time} before you can reuse this command.")
            # If we are here, no timer and user can mug an npc.
            if difficulty_choice == stranger1:
                strangerchoice = random.choice(difficulty_choice)
                if pve_attack > rating_easy:
                    reward = random.randint(1, 35)
                    mugger_user.balance += reward
                    mugger_user.pve_win += 1                             
                    await ctx.send(f"**{author.display_name}** successfully mugged *{strangerchoice}* and made off with ${reward}!")
#Temp                    mugger_user.player_exp += 1 # +1 to Player Experience
                else:
                    mugger_user.pve_loss += 1
                    await ctx.send(f"**{author.display_name}** looked around for someone to mug but found no one nearby...")
            elif difficulty_choice == stranger2:
                strangerchoice = random.choice(difficulty_choice)
                if pve_attack > rating_medium:
                    reward = random.randint(36, 65)
                    mugger_user.balance += reward
                    mugger_user.pve_win += 1                    
                    await ctx.send(f"**{author.display_name}** successfully mugged *{strangerchoice}* and made off with ${reward}!")
#Temp                    mugger_user.player_exp += 2 # +2 to Player Experience
                else:
                    mugger_user.pve_loss += 1                    
                    await ctx.send(f"**{author.display_name}** looked around for someone to mug but found no one nearby...")
            elif difficulty_choice == stranger3:
                strangerchoice = random.choice(difficulty_choice)
                if pve_attack > rating_hard:
                    reward = random.randint(66, 95)
                    mugger_user.balance += reward
                    mugger_user.pve_win += 1                    
                    await ctx.send(f"**{author.display_name}** successfully mugged *{strangerchoice}* and made off with ${reward}!")
#Temp                    mugger_user.player_exp += 3 # +3 to Player Experience
                else:
                    mugger_user.pve_loss += 1                    
                    await ctx.send(f"**{author.display_name}** looked around for someone to mug but found no one nearby...")
        else:
            # If we here, user targeted a player and now we check allowed status.
            target_user = guildsettings.get_user(target)
            if mugger_user.balance < 50:
                await ctx.send(f"You have less than $50 and cannot mug other Players yet!.")
                return
            if target_user.balance < 50:
                await ctx.send(f"The target has less than $50 and isn't worth mugging.")
                return
            # PvP Mugging, Attacking another User who is not under the minimum amount.
            pvp_defend = random.uniform(0, 1) + target_user.p_bonus + target_user.player_def_bonus

            # Track pvp targets and make sure new target is allowed, this prevents attacking the same person over and over.
            # Check if the target is valid and enforce unique targets
            # Get the list of recent targets from the user's data
            recent_targets = mugger_user.recent_targets

            if target.id in recent_targets:
                await ctx.send(f"You have already mugged {target.display_name} recently. Mug other players to clear your target list!")
                return
            
            # Check the pvp timer.    
            secondsleft = pvpbucket.update_rate_limit() # Add pvp timer to user.
            if secondsleft:
                wait_time = humanize_timedelta(seconds=int(secondsleft))
                return await ctx.send(f"You must wait {wait_time} until you can target another Player!")
            # Add the new target to the list
            recent_targets.append(target.id)
            # Keep only the last 5
            if len(recent_targets) > 5:
                recent_targets.pop(0)
            # Save back to the user
            mugger_user.recent_targets = recent_targets
            # Run the actual contested check.
            if pvp_attack > pvp_defend:
                mug_amount = min(round(target_user.balance * 0.07), 1000)
#Temp                mugger_user.player_exp += 5 # +5 to Player Experience
                mugger_user.balance += mug_amount
                target_user.balance -= mug_amount
                await ctx.send(f"You attack {target} with everything you've got!\nYou have overwhelmed them this time and made off with ${mug_amount}!\nYou WON!!")
                #+1 pwin to attacker, +1 ploss to target
                mugger_user.p_wins += 1
                target_user.p_losses += 1
                # Update p_bonus for both players
                recalculate_p_bonus(mugger_user)
                recalculate_p_bonus(target_user)
            elif pvp_attack < pvp_defend:
                await ctx.send(f"You attack {target} and find them well prepared!\nYou have failed this time!")
                #+1 ploss to attacker, +1 pwin to target
                mugger_user.p_losses += 1
                target_user.p_wins += 1
                # Update p_bonus for both players
                recalculate_p_bonus(mugger_user)
                recalculate_p_bonus(target_user)
            elif pvp_attack == pvp_defend:
                await ctx.send(f"You attack {target} and find that you are equally matched!\nYou flee before you suffer any losses.")
                #Make no changes from here for the pvp aspect.
        self.save()

# Ability for players to clear their win/loss ratios.
    @commands.command()
    async def mugclear(self, ctx: commands.Context, target: discord.Member = None):
        """Reset a User's PvP Wins and Losses to 0 for an incrimental cost."""
        # Cost to clear ratio for the first time
        first_free = 0
        base_cost = 500
        # Default to author if no target is provided
        target = target or ctx.author

        # Prevent using on others
        if target != ctx.author:
            await ctx.send("You cannot use this on others.")
            return

        # Get guild settings and user data
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)

        # Calculate cost based on how many times the user has reset
        cost = first_free if target_user.mugclear_count == 0 else base_cost * target_user.mugclear_count

        # Check if player can afford to reset
        if target_user.balance < cost:
            await ctx.send("You cannot afford to reset your ratio at this time.")
            return  # Stop execution if they can't afford it

        # Ask for confirmation
        await ctx.send(f"This will completely reset all of your Win/Loss stats for ${cost}. This can NOT be reverted.\nType 'yes' to confirm.")

        try:
            msg = await ctx.bot.wait_for("message", timeout=30, check=lambda m: m.author == ctx.author and m.channel == ctx.channel)
            if msg.content.lower() != "yes":
                await ctx.send("Action canceled. PvP stats were not reset.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Confirmation timed out. PvP stats were not reset.")
            return

        # Reset user's stats
        target_user.p_wins = 0
        target_user.p_losses = 0        
        target_user.mugclear_count += 1  # Corrected increment
        target_user.balance -= cost #Removes the cost of the clear from the users balance.

        await ctx.send("Your PvP Wins/Losses have been reset to 0.")
        self.save()

    @mug.command(name="consider")
    async def mug_consider(self, ctx: commands.Context, target: discord.Member):
        """Compare your combat stats against another player to see your odds."""
        if target == ctx.author:
            await ctx.send("You can't consider mugging yourself!")
            return
        if target.bot:
            await ctx.send("You cannot consider mugging a Bot!")
            return

        guildsettings = self.db.get_conf(ctx.guild)
        attacker = guildsettings.get_user(ctx.author)
        defender = guildsettings.get_user(target)

        # Calculate total bonuses
        atk_total = attacker.p_bonus + attacker.player_atk_bonus
        def_total = defender.p_bonus + defender.player_def_bonus

        # Calculate win probability using the difference
        # Both sides roll uniform(0,1), so we calculate P(X + atk_total > Y + def_total)
        c = def_total - atk_total  # defender's advantage
        if c >= 1:
            win_chance = 0.0
        elif c <= -1:
            win_chance = 1.0
        elif c >= 0:
            win_chance = ((1 - c) ** 2) / 2
        else:  # -1 < c < 0
            win_chance = 1 - ((1 + c) ** 2) / 2

        win_pct = win_chance * 100

        # Build the display
        inner_width = 44
        lines = [
            "╔" + "═" * inner_width + "╗",
            "║" + f"Consider: {target.display_name}".center(inner_width) + "║",
            "╠" + "═" * inner_width + "╣",
            "║" + f"YOUR STATS".center(inner_width) + "║",
            "║" + f"  P-Bonus: {attacker.p_bonus:+.2f}".ljust(inner_width) + "║",
            "║" + f"  Atk-Bonus: +{attacker.player_atk_bonus:.2f}".ljust(inner_width) + "║",
            "║" + f"  Total Attack: {atk_total:+.2f}".ljust(inner_width) + "║",
            "╠" + "═" * inner_width + "╣",
            "║" + f"THEIR STATS".center(inner_width) + "║",
            "║" + f"  P-Bonus: {defender.p_bonus:+.2f}".ljust(inner_width) + "║",
            "║" + f"  Def-Bonus: +{defender.player_def_bonus:.2f}".ljust(inner_width) + "║",
            "║" + f"  Total Defense: {def_total:+.2f}".ljust(inner_width) + "║",
            "╠" + "═" * inner_width + "╣",
            "║" + f"Win Chance: {win_pct:.1f}%".center(inner_width) + "║",
            "╚" + "═" * inner_width + "╝",
        ]
        await ctx.send("```" + "\n".join(lines) + "```")

############### Gang System Commands ###############
    @commands.group(name="ctgang", invoke_without_command=True)
    async def ctgang(self, ctx: commands.Context):
        """Gang system commands for creating and managing criminal organizations."""
        p = ctx.clean_prefix
        await ctx.send(
            f"**Gang System Commands:**\n"
            f"`{p}ctgang create <name>` - Create a new gang ($5,000)\n"
            f"`{p}ctgang invite <@player>` - Invite a player to your gang\n"
            f"`{p}ctgang remove <@player>` - Remove a player from your gang\n"
            f"`{p}ctgang leave` - Leave your current gang\n"
            f"`{p}ctgang disband` - Disband your gang (leader only)\n"
            f"`{p}ctgang info` - View your gang's information\n"
            f"`{p}ctgang list` - List all gangs in the server\n"
            f"`{p}ctgang transfer <@player>` - Transfer leadership"
        )

    @ctgang.command(name="create")
    async def gang_create(self, ctx: commands.Context, *, name: str = None):
        """Create a new gang for $5,000."""
        if name is None:
            await ctx.send("You must provide a name for your gang. Usage: `ctgang create <name>`")
            return

        # Validate gang name
        if len(name) < 3 or len(name) > 25:
            await ctx.send("Gang name must be between 3 and 25 characters.")
            return

        if not all(c.isalnum() or c.isspace() for c in name):
            await ctx.send("Gang name can only contain letters, numbers, and spaces.")
            return

        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)

        # Check if user is already in a gang
        if user.gang_id:
            existing_gang = guildsettings.get_gang(user.gang_id)
            if existing_gang:
                await ctx.send(f"You are already in a gang: **{existing_gang.name}**. Leave or disband it first.")
                return

        # Check if gang name already exists
        if guildsettings.get_gang_by_name(name):
            await ctx.send("A gang with that name already exists. Choose a different name.")
            return

        # Check if user has enough money
        gang_cost = 5000
        if user.balance < gang_cost:
            await ctx.send(f"You need ${gang_cost} to create a gang. You only have ${user.balance}.")
            return

        # Confirm creation
        await ctx.send(f"Creating gang **{name}** will cost you ${gang_cost}. Type 'yes' to confirm.")

        try:
            msg = await ctx.bot.wait_for(
                "message",
                timeout=30,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel
            )
            if msg.content.lower() != "yes":
                await ctx.send("Gang creation cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Gang creation timed out.")
            return

        # Create the gang
        user.balance -= gang_cost
        gang = guildsettings.create_gang(name, ctx.author.id)
        user.gang_id = gang.gang_id

        await ctx.send(f"🎉 Congratulations! You have created the gang **{name}**!\nUse `ctgang invite @player` to add members (max 4).")
        self.save()

    @ctgang.command(name="invite")
    async def gang_invite(self, ctx: commands.Context, target: discord.Member = None):
        """Invite a player to your gang (leader only)."""
        if target is None:
            await ctx.send("You must specify a player to invite. Usage: `ctgang invite @player`")
            return

        if target == ctx.author:
            await ctx.send("You cannot invite yourself!")
            return

        if target.bot:
            await ctx.send("You cannot invite bots to your gang!")
            return

        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)
        target_user = guildsettings.get_user(target)

        # Check if user is in a gang and is the leader
        if not user.gang_id:
            await ctx.send("You are not in a gang. Create one first with `ctgang create <name>`.")
            return

        gang = guildsettings.get_gang(user.gang_id)
        if not gang:
            user.gang_id = None
            await ctx.send("Your gang data was not found. Please create a new gang.")
            self.save()
            return

        if gang.leader_id != ctx.author.id:
            await ctx.send("Only the gang leader can invite new members.")
            return

        if gang.is_full:
            await ctx.send("Your gang is full (max 5 members including leader).")
            return

        # Check if target is already in a gang
        if target_user.gang_id:
            await ctx.send(f"{target.display_name} is already in a gang.")
            return

        # Send invite and wait for response
        await ctx.send(
            f"{target.mention}, you have been invited to join **{gang.name}**!\n"
            f"Type 'accept' within 60 seconds to join."
        )

        try:
            msg = await ctx.bot.wait_for(
                "message",
                timeout=60,
                check=lambda m: m.author == target and m.channel == ctx.channel
            )
            if msg.content.lower() != "accept":
                await ctx.send(f"{target.display_name} declined the invitation.")
                return
        except asyncio.TimeoutError:
            await ctx.send(f"Invitation to {target.display_name} expired.")
            return

        # Add member to gang
        gang.add_member(target.id)
        target_user.gang_id = gang.gang_id

        await ctx.send(f"🎉 {target.display_name} has joined **{gang.name}**! ({gang.member_count}/5 members)")
        self.save()

    @ctgang.command(name="remove")
    async def gang_remove(self, ctx: commands.Context, target: discord.Member = None):
        """Remove a player from your gang (leader only)."""
        if target is None:
            await ctx.send("You must specify a player to remove. Usage: `ctgang remove @player`")
            return

        if target == ctx.author:
            await ctx.send("You cannot remove yourself! Use `ctgang disband` or `ctgang transfer` instead.")
            return

        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)
        target_user = guildsettings.get_user(target)

        # Check if user is in a gang and is the leader
        if not user.gang_id:
            await ctx.send("You are not in a gang.")
            return

        gang = guildsettings.get_gang(user.gang_id)
        if not gang:
            user.gang_id = None
            await ctx.send("Your gang data was not found.")
            self.save()
            return

        if gang.leader_id != ctx.author.id:
            await ctx.send("Only the gang leader can remove members.")
            return

        # Check if target is in the gang
        if target.id not in gang.members:
            await ctx.send(f"{target.display_name} is not in your gang.")
            return

        # Remove the member
        gang.remove_member(target.id)
        target_user.gang_id = None

        await ctx.send(f"{target.display_name} has been removed from **{gang.name}**. ({gang.member_count}/5 members)")
        self.save()

    @ctgang.command(name="leave")
    async def gang_leave(self, ctx: commands.Context):
        """Leave your current gang (members only, leader must transfer or disband)."""
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)

        if not user.gang_id:
            await ctx.send("You are not in a gang.")
            return

        gang = guildsettings.get_gang(user.gang_id)
        if not gang:
            user.gang_id = None
            await ctx.send("Your gang data was not found. You have been removed from it.")
            self.save()
            return

        if gang.leader_id == ctx.author.id:
            await ctx.send(
                "You are the gang leader and cannot leave.\n"
                "Use `ctgang transfer @player` to transfer leadership, or `ctgang disband` to disband the gang."
            )
            return

        # Remove member from gang
        gang.remove_member(ctx.author.id)
        user.gang_id = None

        await ctx.send(f"You have left **{gang.name}**.")
        self.save()

    @ctgang.command(name="disband")
    async def gang_disband(self, ctx: commands.Context):
        """Disband your gang (leader only). This action is irreversible."""
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)

        if not user.gang_id:
            await ctx.send("You are not in a gang.")
            return

        gang = guildsettings.get_gang(user.gang_id)
        if not gang:
            user.gang_id = None
            await ctx.send("Your gang data was not found.")
            self.save()
            return

        if gang.leader_id != ctx.author.id:
            await ctx.send("Only the gang leader can disband the gang.")
            return

        gang_name = gang.name

        # Confirm disbanding
        await ctx.send(
            f"⚠️ Are you sure you want to disband **{gang_name}**?\n"
            f"This will remove all {gang.member_count} members and cannot be undone.\n"
            f"Type 'disband' to confirm."
        )

        try:
            msg = await ctx.bot.wait_for(
                "message",
                timeout=30,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel
            )
            if msg.content.lower() != "disband":
                await ctx.send("Gang disbanding cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Gang disbanding timed out.")
            return

        # Clear gang_id for all members
        for member_id in gang.members:
            member_user = guildsettings.get_user(member_id)
            member_user.gang_id = None

        # Clear leader's gang_id
        user.gang_id = None

        # Delete the gang
        guildsettings.delete_gang(gang.gang_id)

        await ctx.send(f"💀 **{gang_name}** has been disbanded.")
        self.save()

    @ctgang.command(name="info")
    async def gang_info(self, ctx: commands.Context):
        """View information about your gang."""
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)

        if not user.gang_id:
            await ctx.send("You are not in a gang. Create one with `ctgang create <name>`.")
            return

        gang = guildsettings.get_gang(user.gang_id)
        if not gang:
            user.gang_id = None
            await ctx.send("Your gang data was not found.")
            self.save()
            return

        # Get leader info
        leader = ctx.guild.get_member(gang.leader_id)
        leader_name = leader.display_name if leader else f"Unknown ({gang.leader_id})"

        # Get member info
        member_names = []
        for member_id in gang.members:
            member = ctx.guild.get_member(member_id)
            if member:
                member_names.append(member.display_name)
            else:
                member_names.append(f"Unknown ({member_id})")

        members_str = ", ".join(member_names) if member_names else "None"

        # Calculate gang age
        gang_age_seconds = time.time() - gang.created_at
        gang_age_days = int(gang_age_seconds // 86400)

        inner_width = 44
        border = "═" * inner_width
        
        lines = [
            "```",
            "╔" + border + "╗",
            "║" + f"GANG: {gang.name}".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + f" Leader  : {leader_name}".ljust(inner_width) + "║",
            "║" + f" Members : {members_str}".ljust(inner_width) + "║",
            "║" + f" Size    : {gang.member_count}/5".ljust(inner_width) + "║",
            "║" + f" Age     : {gang_age_days} days".ljust(inner_width) + "║",
            "║" + f" Earnings: ${gang.total_earnings}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))

    @ctgang.command(name="list")
    async def gang_list(self, ctx: commands.Context):
        """List all gangs in the server."""
        guildsettings = self.db.get_conf(ctx.guild)

        if not guildsettings.gangs:
            await ctx.send("There are no gangs in this server yet. Be the first to create one with `ctgang create <name>`!")
            return

        gang_lines = ["**🏴 Gangs in this Server:**\n"]
        for gang in guildsettings.gangs.values():
            leader = ctx.guild.get_member(gang.leader_id)
            leader_name = leader.display_name if leader else "Unknown"
            gang_lines.append(f"• **{gang.name}** - Led by {leader_name} ({gang.member_count}/5 members)")

        await ctx.send("\n".join(gang_lines))

    @ctgang.command(name="transfer")
    async def gang_transfer(self, ctx: commands.Context, target: discord.Member = None):
        """Transfer gang leadership to another member (leader only)."""
        if target is None:
            await ctx.send("You must specify a player to transfer leadership to. Usage: `ctgang transfer @player`")
            return

        if target == ctx.author:
            await ctx.send("You are already the leader!")
            return

        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)

        if not user.gang_id:
            await ctx.send("You are not in a gang.")
            return

        gang = guildsettings.get_gang(user.gang_id)
        if not gang:
            user.gang_id = None
            await ctx.send("Your gang data was not found.")
            self.save()
            return

        if gang.leader_id != ctx.author.id:
            await ctx.send("Only the gang leader can transfer leadership.")
            return

        # Check if target is in the gang
        if target.id not in gang.members:
            await ctx.send(f"{target.display_name} is not in your gang. They must be a member first.")
            return

        # Confirm transfer
        await ctx.send(
            f"⚠️ Are you sure you want to transfer leadership of **{gang.name}** to {target.display_name}?\n"
            f"You will become a regular member. Type 'transfer' to confirm."
        )

        try:
            msg = await ctx.bot.wait_for(
                "message",
                timeout=30,
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel
            )
            if msg.content.lower() != "transfer":
                await ctx.send("Leadership transfer cancelled.")
                return
        except asyncio.TimeoutError:
            await ctx.send("Leadership transfer timed out.")
            return

        # Perform the transfer
        if target.id in gang.members:
            gang.members.remove(target.id)  # Remove new leader from members
        gang.members.append(ctx.author.id)  # Add old leader to members
        gang.leader_id = target.id  # Set new leader

        await ctx.send(f"👑 {target.display_name} is now the leader of **{gang.name}**!")
        self.save()
############### End of Gang System Commands ###############

    # Carjacking Command Group
    @commands.group(name="ctcarjack", aliases=["ctcj"], invoke_without_command=True)
    async def ctcarjack(self, ctx: commands.Context):
        """Used to perform Carjacking or view Information."""
        p = ctx.clean_prefix
        await ctx.send(f"**Please specify a valid subcommand, e.g.:**\n"
                       f"`{p}ctcj list` - *Lists all possible cars in the game.*\n"
                       f"`{p}ctcj inv`  - *Displays your Collector's Garage(max 3).*\n"
                       f"`{p}ctcj hunt` - *Search for potential cars to steal.*")
    
    # Displays all cars in the game
    @ctcarjack.command(name="list")
    async def list_all_cars(self, ctx: commands.Context):
        """Lists all cars in the game categorized by rarity."""
        embed = discord.Embed(title="Carjack: Available Cars", color=discord.Color.orange())

        categories = [
            ("Rarest", carjack.rarest_cars, True),
            ("Semi-Rare", carjack.semi_rare_cars, True),
            ("Common", carjack.common_cars, False),
            ("Junk", carjack.junk_cars, False),
        ]

        for title, car_list, show_max in categories:
            if not car_list:
                continue

            lines = []
            for car in car_list:
                max_display = "∞" if car["max"] == float("inf") else car["max"]
                if show_max:
                    line = f"{car['year']} {car['make']} {car['model']} (Max: {max_display}) - Value: ${car['value']:,}"
                else:
                    line = f"{car['year']} {car['make']} {car['model']} - Value: ${car['value']:,}"
                lines.append(line)

            embed.add_field(name=title, value="\n".join(lines), inline=False)

        await ctx.send(embed=embed)

    @ctcarjack.command(name="inv")
    async def carjack_inv(self, ctx: commands.Context):
        """Display your stolen car collection."""
        await ctx.send("🚧 This feature is coming soon!")

    @ctcarjack.command(name="hunt")
    async def carjack_hunt(self, ctx: commands.Context):
        """Search for cars to steal."""
        await ctx.send("🚧 This feature is coming soon!")


############### BlackMarket Commands ###############
    @commands.group(invoke_without_command=True)
    async def ctbm(self, ctx: commands.Context):
        """Blackmarket code."""
        p = ctx.clean_prefix
        await ctx.send(f"Please specify a valid subcommand, e.g.:\n"
                       f"`{p}ctbm listall` - (Admin only) Will list all items that exist.\n"
                       f"`{p}ctbm display` - (Admin only) Shows cycle timing info.\n"
                       f"`{p}ctbm list` - Will list the current available items to buy.\n"
                       f"`{p}ctbm buy (#)` - Will purchase the item if you don't already own it.\n"
                       f"`{p}ctbm sell (slot) (item)` - Sells the item for a little less than it's worth."
                       )
    #Shows a list of ALL items that have been created in blackmarket.py, whether actively in the market or not.
    @ctbm.command(name="listall")
    @commands.admin_or_permissions(manage_guild=True)
    async def display_allitems_list(self, ctx: commands.Context):
        """Print all currently created Tier 1 gear grouped by category on separate lines."""

        categories = {
            "Head Gear": blackmarket.tier_1_head,
            "Chest Gear": blackmarket.tier_1_chest,
            "Leg Gear": blackmarket.tier_1_legs,
            "Foot Gear": blackmarket.tier_1_feet,
            "Weapons": blackmarket.tier_1_weapon,
        }

        lines = ["**__Current Gear Listing:__**\n"]

        for category, items in categories.items():
            line = f"__**{category}:**__ " + ", ".join(
                f"{item['name']} (${item['cost']})" for item in items
            )
            lines.append(line)
        await ctx.send("\n".join(lines))

    #Admin command to display blackmarket cycle timing info for debugging.
    @ctbm.command(name="display")
    @commands.admin_or_permissions(manage_guild=True)
    async def display_cycle_info(self, ctx: commands.Context):
        """Display blackmarket cycle timing information for debugging."""
        guildsettings = self.db.get_conf(ctx.guild)
        
        last_cycle = guildsettings.blackmarket_last_cycle
        now = datetime.datetime.now()
        
        # Format last cycle time
        if last_cycle == 0:
            last_cycle_str = "Never (not yet cycled)"
        else:
            last_dt = datetime.datetime.fromtimestamp(last_cycle)
            last_cycle_str = last_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate next cycle boundary
        if now.minute >= 30:
            next_boundary = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        else:
            next_boundary = now.replace(minute=30, second=0, microsecond=0)
        
        next_cycle_str = next_boundary.strftime("%Y-%m-%d %H:%M:%S")
        current_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        time_remaining = self.get_time_until_next_cycle(guildsettings)
        minutes = time_remaining // 60
        seconds = time_remaining % 60
        
        inner_width = 44
        lines = [
            "```",
            "╔" + "═" * inner_width + "╗",
            "║" + "BLACKMARKET CYCLE DEBUG".center(inner_width) + "║",
            "╠" + "═" * inner_width + "╣",
            "║" + f" Current Time:".ljust(inner_width) + "║",
            "║" + f"   {current_time_str}".ljust(inner_width) + "║",
            "║" + f" Last Cycle:".ljust(inner_width) + "║",
            "║" + f"   {last_cycle_str}".ljust(inner_width) + "║",
            "║" + f" Next Cycle:".ljust(inner_width) + "║",
            "║" + f"   {next_cycle_str}".ljust(inner_width) + "║",
            "╠" + "═" * inner_width + "╣",
            "║" + f" Time Until Cycle: {minutes:02d}m {seconds:02d}s".ljust(inner_width) + "║",
            "╚" + "═" * inner_width + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))

    #Shows a list of all items currently available for purchase in the market's cycle.
    @ctbm.command(name="list")
    async def display_current_items_list(self, ctx: commands.Context):
        """Print all items available to purchase this cycle."""
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)
        
        # Initialize blackmarket if empty
        if not guildsettings.blackmarket_current_items:
            self.rotate_blackmarket(guildsettings)
            guildsettings.blackmarket_last_cycle = time.time()
            self.save()
        
        items = guildsettings.blackmarket_current_items
        time_remaining = self.get_time_until_next_cycle(guildsettings)
        minutes = time_remaining // 60
        seconds = time_remaining % 60
        
        # Inner width (characters between the two ║ borders)
        inner_width = 44
        
        # Build the display
        lines = [
            "```",
            "╔" + "═" * inner_width + "╗",
            "║" + "BLACK MARKET".center(inner_width) + "║",
            "║" + f"Refreshes in: {minutes:02d}m {seconds:02d}s".center(inner_width) + "║",
            "╠" + "═" * inner_width + "╣",
        ]
        
        for idx, item in enumerate(items, 1):
            slot_name = blackmarket.get_slot_name(item["wear"])
            name = item["name"]
            cost = item["cost"]
            # Truncate name if too long to fit in the box
            max_name_len = 24
            display_name = name[:max_name_len] if len(name) > max_name_len else name
            # Build the item line and pad to inner_width
            item_text = f" {idx}. {display_name:<{max_name_len}} ${cost:>5} "
            lines.append("║" + item_text.ljust(inner_width) + "║")
            # Build the bonus line and pad to inner_width
            bonus_text = f"    [{slot_name}] +{item['factor']:.2f} bonus"
            lines.append("║" + bonus_text.ljust(inner_width) + "║")
        
        lines.extend([
            "╠" + "═" * inner_width + "╣",
            "║" + " Click a button below to purchase".ljust(inner_width) + "║",
            "╚" + "═" * inner_width + "╝",
            "```"
        ])
        
        # Create the view with buy buttons
        view = BlackmarketBuyView(self, ctx, items, user, guildsettings)
        message = await ctx.send("\n".join(lines), view=view)
        view.message = message

    @ctbm.command(name="buy")
    async def buy_blackmarket_item(self, ctx: commands.Context, item_number: int = None):
        """Purchase an item from the blackmarket."""
        if item_number is None:
            await ctx.send("You must specify an item number. Usage: `ctbm buy <1-4>`")
            return
        
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)
        
        # Initialize blackmarket if empty
        if not guildsettings.blackmarket_current_items:
            self.rotate_blackmarket(guildsettings)
            guildsettings.blackmarket_last_cycle = time.time()
            self.save()
        
        items = guildsettings.blackmarket_current_items
        
        # Validate item number
        if item_number < 1 or item_number > len(items):
            await ctx.send(f"Invalid item number. Please choose 1-{len(items)}.")
            return
        
        item = items[item_number - 1]
        keyword = item["keyword"]
        cost = item["cost"]
        wear_slot = item["wear"]
        slot_name = blackmarket.get_slot_name_lower(wear_slot)
        
        # Check if user already owns or is wearing this item
        owned_attr = f"owned_{slot_name}"
        worn_attr = f"worn_{slot_name}"
        owned_dict = getattr(user, owned_attr, {})
        worn_keyword = getattr(user, worn_attr, None)
        
        if keyword in owned_dict or worn_keyword == keyword:
            await ctx.send(f"You already own **{item['name']}**!")
            return
        
        # Check if user can afford it
        if user.balance < cost:
            await ctx.send(f"You don't have enough cash! You need ${cost} but only have ${user.balance}.")
            return
        
        # Purchase the item
        user.balance -= cost
        owned_dict[keyword] = 1
        setattr(user, owned_attr, owned_dict)
        
        await ctx.send(
            f"🛒 You purchased **{item['name']}** for ${cost}!\n"
            f"It has been added to your inventory. Use `ctinv wear {keyword}` to equip it."
        )
        self.save()

    @ctbm.command(name="sell")
    async def sell_inventory_item(self, ctx: commands.Context, slot: str = None, keyword: str = None):
        """Sell an item from your inventory for 50-70% of its value."""
        if slot is None or keyword is None:
            await ctx.send(
                "You must specify a slot and item keyword.\n"
                "Usage: `ctbm sell <slot> <keyword>`\n"
                "Slots: weapon, head, chest, legs, feet\n"
                "Example: `ctbm sell weapon knuckles`"
            )
            return
        
        slot = slot.lower()
        keyword = keyword.lower()
        
        valid_slots = ["weapon", "head", "chest", "legs", "feet"]
        if slot not in valid_slots:
            await ctx.send(f"Invalid slot. Valid slots: {', '.join(valid_slots)}")
            return
        
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)
        
        # Check if item is in inventory (not worn)
        owned_attr = f"owned_{slot}"
        owned_dict = getattr(user, owned_attr, {})
        
        if keyword not in owned_dict:
            await ctx.send(f"You don't have **{keyword}** in your {slot} inventory. Check `ctinv owned`.")
            return
        
        # Find the item to get its value
        item = blackmarket.get_item_by_keyword(keyword)
        if not item:
            await ctx.send("Item data not found. Please contact an admin.")
            return
        
        # Calculate sell price (50-70% of cost)
        sell_percentage = random.uniform(0.50, 0.70)
        sell_price = int(item["cost"] * sell_percentage)
        
        # Remove from inventory and add cash
        del owned_dict[keyword]
        setattr(user, owned_attr, owned_dict)
        user.balance += sell_price
        
        await ctx.send(
            f"💰 You sold **{item['name']}** for ${sell_price}!\n"
            f"(Original value: ${item['cost']})"
        )
        self.save()

############### Player Equipment Commands ###############
    #Player Inventory command group.
    @commands.group(invoke_without_command=True)
    async def ctinv(self, ctx: commands.Context):
        """All commands for player interactions with gear."""
        p = ctx.clean_prefix
        await ctx.send(f"Please specify a valid subcommand, e.g.:\n"
                       f"`{p}ctinv all` - Will list a full display of your items.\n"
                       f"`{p}ctinv worn` - Will list what you are currently wearing.\n"
                       f"`{p}ctinv owned` - Items in your carried inventory.\n"
                       f"`{p}ctinv wear (item)` - Wear an item you own.\n"
                       f"`{p}ctinv remove (item)` - Remove a worn item."
                       )
    #Displays currently worn items, but not what else they own.
    @ctinv.command(name="worn")
    async def display_user_worn_items(self, ctx: commands.Context):
        '''Prints out a list of all the currently worn gear.'''
        member = ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        
        def format_worn(keyword):
            if not keyword:
                return "Empty"
            item = blackmarket.get_item_by_keyword(keyword)
            if item:
                return f"{item['name']} (+{item['factor']:.2f})"
            return keyword
        
        inner_width = 44
        border = "═" * inner_width
        
        lines = [
            "```",
            "╔" + border + "╗",
            "║" + f"{member.display_name}'s Worn Equipment".center(inner_width) + "║",
            "║" + f"Atk: +{user.player_atk_bonus:.2f} / Def: +{user.player_def_bonus:.2f}".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + f" [Weapon]     : {format_worn(user.worn_weapon)}".ljust(inner_width) + "║",
            "║" + f" [Head]       : {format_worn(user.worn_head)}".ljust(inner_width) + "║",
            "║" + f" [Chest]      : {format_worn(user.worn_chest)}".ljust(inner_width) + "║",
            "║" + f" [Legs]       : {format_worn(user.worn_legs)}".ljust(inner_width) + "║",
            "║" + f" [Feet]       : {format_worn(user.worn_feet)}".ljust(inner_width) + "║",
            "║" + f" [Consumable] : {format_worn(user.worn_consumable)}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))

    #Displays only a list of the items owned by the player, but not worn.
    @ctinv.command(name="owned")
    async def display_user_owned_items(self, ctx: commands.Context):
        '''Prints out a list of items in the player's inventory.'''
        member = ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        
        def format_owned(owned_dict, max_len=28):
            if not owned_dict:
                return "Empty"
            result = ", ".join(owned_dict.keys())
            if len(result) > max_len:
                return result[:max_len-3] + "..."
            return result
        
        inner_width = 44
        border = "═" * inner_width
        
        lines = [
            "```",
            "╔" + border + "╗",
            "║" + f"{member.display_name}'s Inventory".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + f" [Weapon]     : {format_owned(user.owned_weapon)}".ljust(inner_width) + "║",
            "║" + f" [Head]       : {format_owned(user.owned_head)}".ljust(inner_width) + "║",
            "║" + f" [Chest]      : {format_owned(user.owned_chest)}".ljust(inner_width) + "║",
            "║" + f" [Legs]       : {format_owned(user.owned_legs)}".ljust(inner_width) + "║",
            "║" + f" [Feet]       : {format_owned(user.owned_feet)}".ljust(inner_width) + "║",
            "║" + f" [Consumable] : {format_owned(user.owned_consumable)}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))
    #Displays all worn and owned items in one screen.
    @ctinv.command(name="all")
    async def display_all_user_items(self, ctx: commands.Context):
        '''Prints out a list of all the currently owned and worn gear.'''
        member = ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(member)
        
        # Format worn items nicely
        def format_worn(keyword):
            if not keyword:
                return "Empty"
            item = blackmarket.get_item_by_keyword(keyword)
            if item:
                return f"{item['name']} (+{item['factor']:.2f})"
            return keyword
        
        # Format owned items nicely
        def format_owned(owned_dict, max_len=28):
            if not owned_dict:
                return "Empty"
            result = ", ".join(owned_dict.keys())
            if len(result) > max_len:
                return result[:max_len-3] + "..."
            return result
        
        inner_width = 44
        border = "═" * inner_width
        
        lines = [
            "```",
            "╔" + border + "╗",
            "║" + f"{member.display_name}'s Gear".center(inner_width) + "║",
            "║" + f"Atk: +{user.player_atk_bonus:.2f} / Def: +{user.player_def_bonus:.2f}".center(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " [Worn Equipment]".ljust(inner_width) + "║",
            "║" + f"  Weapon    : {format_worn(user.worn_weapon)}".ljust(inner_width) + "║",
            "║" + f"  Head      : {format_worn(user.worn_head)}".ljust(inner_width) + "║",
            "║" + f"  Chest     : {format_worn(user.worn_chest)}".ljust(inner_width) + "║",
            "║" + f"  Legs      : {format_worn(user.worn_legs)}".ljust(inner_width) + "║",
            "║" + f"  Feet      : {format_worn(user.worn_feet)}".ljust(inner_width) + "║",
            "╠" + border + "╣",
            "║" + " [Inventory]".ljust(inner_width) + "║",
            "║" + f"  Weapon    : {format_owned(user.owned_weapon)}".ljust(inner_width) + "║",
            "║" + f"  Head      : {format_owned(user.owned_head)}".ljust(inner_width) + "║",
            "║" + f"  Chest     : {format_owned(user.owned_chest)}".ljust(inner_width) + "║",
            "║" + f"  Legs      : {format_owned(user.owned_legs)}".ljust(inner_width) + "║",
            "║" + f"  Feet      : {format_owned(user.owned_feet)}".ljust(inner_width) + "║",
            "╚" + border + "╝",
            "```"
        ]
        await ctx.send("\n".join(lines))

    #Command to wear an item into a specific worn_slot.
    @ctinv.command(name="wear")
    async def wear_user_owned_item(self, ctx: commands.Context, keyword: str = None):
        '''Equips an item owned by the User.'''
        if keyword is None:
            await ctx.send(
                "You must specify an item keyword to wear.\n"
                "Usage: `ctinv wear <keyword>`\n"
                "Example: `ctinv wear bandana`\n"
                "Use `ctinv owned` to see your inventory."
            )
            return
        
        keyword = keyword.lower()
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)
        
        # Find the item to determine its slot
        item = blackmarket.get_item_by_keyword(keyword)
        if not item:
            await ctx.send(f"Unknown item: **{keyword}**. Check `ctinv owned` for your items.")
            return
        
        slot_name = blackmarket.get_slot_name_lower(item["wear"])
        owned_attr = f"owned_{slot_name}"
        worn_attr = f"worn_{slot_name}"
        
        # Check if user owns this item
        owned_dict = getattr(user, owned_attr, {})
        if keyword not in owned_dict:
            await ctx.send(f"You don't own **{item['name']}**. Check `ctinv owned`.")
            return
        
        # Check if something is already worn in that slot
        currently_worn = getattr(user, worn_attr, None)
        
        if currently_worn:
            # Swap: move currently worn item back to inventory
            owned_dict[currently_worn] = 1
            old_item = blackmarket.get_item_by_keyword(currently_worn)
            old_name = old_item["name"] if old_item else currently_worn
            swap_msg = f"\nYou unequipped **{old_name}** and put it in your inventory."
        else:
            swap_msg = ""
        
        # Remove from inventory and equip
        del owned_dict[keyword]
        setattr(user, owned_attr, owned_dict)
        setattr(user, worn_attr, keyword)
        
        await ctx.send(
            f"✅ You equipped **{item['name']}** in your {slot_name.capitalize()} slot!"
            f"{swap_msg}\n"
            f"Bonus: +{item['factor']:.2f} {'Attack' if slot_name == 'weapon' else 'Defense'}"
        )
        self.save()

    #Command to take an item out of a specific slot and put it into regular inventory.
    @ctinv.command(name="remove")
    async def remove_user_worn_item(self, ctx: commands.Context, slot: str = None):
        '''Removes a currently worn piece of gear.'''
        if slot is None:
            await ctx.send(
                "You must specify a slot to remove from.\n"
                "Usage: `ctinv remove <slot>`\n"
                "Slots: weapon, head, chest, legs, feet\n"
                "Example: `ctinv remove head`"
            )
            return
        
        slot = slot.lower()
        valid_slots = ["weapon", "head", "chest", "legs", "feet"]
        
        if slot not in valid_slots:
            await ctx.send(f"Invalid slot. Valid slots: {', '.join(valid_slots)}")
            return
        
        guildsettings = self.db.get_conf(ctx.guild)
        user = guildsettings.get_user(ctx.author)
        
        worn_attr = f"worn_{slot}"
        owned_attr = f"owned_{slot}"
        
        currently_worn = getattr(user, worn_attr, None)
        
        if not currently_worn:
            await ctx.send(f"You don't have anything equipped in your {slot.capitalize()} slot.")
            return
        
        # Find the item for display
        item = blackmarket.get_item_by_keyword(currently_worn)
        item_name = item["name"] if item else currently_worn
        
        # Move to inventory
        owned_dict = getattr(user, owned_attr, {})
        owned_dict[currently_worn] = 1
        setattr(user, owned_attr, owned_dict)
        setattr(user, worn_attr, None)
        
        await ctx.send(f"✅ You removed **{item_name}** and placed it in your inventory.")
        self.save()
############### End of Equipment Commands ###############

##########  Admin Commands  ##########
    # Manually update a users P-Bonus
    @commands.command()
    @commands.admin_or_permissions(manage_guild=True)  # Only Admins can use this command
    async def pbupdate(self, ctx: commands.Context, member: discord.Member = None):
        """Checks the Balance, Wins/Losses, and Ratio of a User."""
        member  = member or ctx.author
        guildsettings = self.db.get_conf(ctx.guild)
        await self.update_pbonus(ctx, member)
        await ctx.send(f"{member.display_name}'s PvP bonus has been updated to {guildsettings.get_user(member).p_bonus}")

    # This group allows the Administrator to CLEAR amounts, not set them.
    @commands.group()
    @commands.admin_or_permissions(manage_guild=True)  # Only Admins can use this command    
    async def ctclear(self, ctx: commands.Context):
        """Configure CrimeTime User Data"""

    @ctclear.command() # Clears a User's total data file.
    async def all(self, ctx: commands.Context, target: discord.Member):
        '''Reset a User's total Stat pool to 0.'''
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_user.balance = 0
        target_user.gold_bars = 0
        target_user.gems_owned = 0
        target_user.p_wins = 0
        target_user.p_losses = 0
        target_user.r_wins = 0
        target_user.r_losses = 0
        target_user.h_wins = 0
        target_user.h_losses = 0
        target_user.pop_up_wins = 0
        target_user.pop_up_losses = 0
        await ctx.send(f"**{target.display_name}**'s complete record has been reset to 0.")
        self.save()

    @ctclear.command(name="balance") # Clears a User's cash balance
    async def clear_balance(self, ctx: commands.Context, target: discord.Member):
        """Reset a User's Cash Balance to 0."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_user.balance = 0
        await ctx.send(f"**{target.display_name}**'s Balance has been reset to 0.")
        self.save()

    @ctclear.command(name="bars") # Clears a User's Gold-Bar balance
    async def clear_bars(self, ctx: commands.Context, target: discord.Member):
        """Reset a User's Gold Bar Count to 0."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_user.gold_bars = 0
        await ctx.send(f"**{target.display_name}**'s Gold Bar count has been reset to 0.")
        self.save()
    
    @ctclear.command(name="gems") # Clears a User's Gem count balance
    async def clear_gems(self, ctx: commands.Context, target: discord.Member):
        """Reset a User's Gem count to 0."""
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_user.gems_owned = 0
        await ctx.send(f"**{target.display_name}**'s Gem count has been reset to 0.")
        self.save()
 
    @ctclear.command(name="pstats") # Clears a User's PvP wins and losses.
    async def clear_pstats(self, ctx: commands.Context, target: discord.Member):
        '''Reset a User's PvP Wins and Losses to 0.'''
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_user.p_wins = 0
        target_user.p_losses = 0
        await ctx.send(f"**{target.display_name}**'s PvP Wins/Losses have been reset to 0.")
        self.save()
    
    @ctclear.command(name="rstats") # Clear's a Users Rob wins and losses.
    async def clear_rstats(self, ctx: commands.Context, target: discord.Member):
        '''Reset a User's Robbery Wins and Losses to 0.'''
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_user.r_wins = 0
        target_user.r_losses = 0
        await ctx.send(f"**{target.display_name}**'s Robbery Wins/Losses have been reset to 0.")
        self.save()
    
    @ctclear.command(name="hstats") # Clear's a Users Heist wins and losses.
    async def clear_hstats(self, ctx: commands.Context, target: discord.Member):
        '''Reset a User's Heist Wins and Losses to 0.'''
        guildsettings = self.db.get_conf(ctx.guild)
        target_user = guildsettings.get_user(target)
        target_user.h_wins = 0
        target_user.h_losses = 0
        await ctx.send(f"**{target.display_name}**'s Heist Wins/Losses have been reset to 0.")
        self.save()

########## Leaderboard Section, be careful ##########
    # Start of Leaderboard Commands
    @commands.command()  # Leaderboard Commands for Mugging
    async def muglb(self, ctx: commands.Context, stat: t.Literal["balance", "wins", "ratio"]):
        """Displays leaderboard for Player Mugging stats."""
        guildsettings = self.db.get_conf(ctx.guild)
        users: dict[int, User] = guildsettings.users

        if stat == "balance":
            sorted_users = sorted(users.items(), key=lambda x: x[1].balance, reverse=True)
            sorted_users = [i for i in sorted_users if i[1].balance]
        elif stat == "wins":
            sorted_users = sorted(users.items(), key=lambda x: x[1].p_wins, reverse=True)
            sorted_users = [i for i in sorted_users if i[1].p_wins]
        else:  # Ratio
            sorted_users = sorted(users.items(), key=lambda x: x[1].p_ratio, reverse=True)
            sorted_users = [i for i in sorted_users if i[1].p_ratio]
        
        # ⛔ Prevent IndexError if list is empty
        if not sorted_users:
            await ctx.send("No users found with any data for that stat.")
            return

        embeds = []
        pages = math.ceil(len(sorted_users) / 15)
        start = 0
        stop = 15

        for index in range(pages):
            stop = min(stop, len(sorted_users))
            txt = ""
            for position in range(start, stop):
                user_id, user_obj = sorted_users[position]

                if stat == "balance":
                    value = user_obj.balance
                elif stat == "wins":
                    value = user_obj.p_wins
                else:
                    value = user_obj.p_ratio

                member = ctx.guild.get_member(user_id)
                if member:
                    username = f"{member.display_name} ({user_id})"
                else:
                    username = f"Unknown User ({user_id})"

                txt += f"{position + 1}. `{value}` : {username}\n"

            title = f"{stat.capitalize()} Leaderboard!"
            embed = discord.Embed(description=txt, title=title)
            embed.set_footer(text=f"Page {index + 1}/{pages}")
            embeds.append(embed)
            start += 15
            stop += 15

        await DynamicMenu(ctx, embeds).refresh()
