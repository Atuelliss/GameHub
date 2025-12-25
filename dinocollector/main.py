import asyncio
import logging
import discord
import time
import random

from redbot.core import commands, bank
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from .abc import CompositeMetaClass
from .commands import Commands
from .common.models import DB
from .listeners import Listeners
from .tasks import TaskLoops
from .main_helper import MainHelper
from .databases.gameinfo import select_random_creature, type_events, all_modifiers
from .databases.creatures import creature_library
from .databases.achievements import achievement_library
from .views import SpawnView, SetupView

log = logging.getLogger("red.dinocollector")

async def is_admin_or_mod(ctx: commands.Context):
    if not ctx.guild:
        return False
    
    # Check permissions (Manage Server is the default admin perm for this cog)
    if ctx.author.guild_permissions.manage_guild:
        return True
        
    # Check role
    cog = ctx.bot.get_cog("DinoCollector")
    if cog:
        conf = cog.db.get_conf(ctx.guild)
        if conf.admin_role_id:
            role = ctx.guild.get_role(conf.admin_role_id)
            if role and role in ctx.author.roles:
                return True
    return False


class DinoCollector(
    Commands, Listeners, TaskLoops, commands.Cog, metaclass=CompositeMetaClass
):
    """Dino Collector Game. Random embeds of Dinos will appear in chat for users to collect in their Explorer Log."""

    __author__ = "Jayar(Vainne)"
    __version__ = "0.0.1"

    def __init__(self, bot: Red):
        super().__init__(bot)
        self.bot: Red = bot
        self.db: DB = DB()

        # States
        self._saving = False
        self._save_retry = False

    def format_help_for_context(self, ctx: commands.Context):
        helpcmd = super().format_help_for_context(ctx)
        txt = "Version: {}\nAuthor: {}".format(self.__version__, self.__author__)
        return f"{helpcmd}\n\n{txt}"

    async def red_delete_data_for_user(self, *args, **kwargs):
        return

    async def check_achievement(self, user_conf, achievement_id: str, messageable):
        """Check and award achievement if not already unlocked."""
        if achievement_id not in achievement_library:
            return

        # Check if already unlocked
        if any(a.get("id") == achievement_id for a in user_conf.achievement_log):
            return
            
        # Unlock
        ach_data = achievement_library[achievement_id]
        user_conf.achievement_log.append({"id": achievement_id, "timestamp": time.time()})
        
        # Reward
        reward = ach_data["reward"]
        user_conf.has_dinocoins += reward
        user_conf.total_dinocoins_earned += reward
        
        self.save()
        
        # Notify
        embed = discord.Embed(
            title="🏆 Achievement Unlocked!",
            description=f"**{ach_data['name']}**\n{ach_data['description']}\n\nReward: **{reward} DinoCoins**",
            color=discord.Color.gold()
        )
        
        try:
            if isinstance(messageable, discord.Interaction):
                if messageable.response.is_done():
                    await messageable.followup.send(embed=embed, ephemeral=True)
                else:
                    await messageable.response.send_message(embed=embed, ephemeral=True)
            elif isinstance(messageable, (discord.TextChannel, commands.Context)):
                await messageable.send(embed=embed)
            elif isinstance(messageable, discord.Message):
                await messageable.channel.send(embed=embed)
        except Exception as e:
            log.error(f"Failed to send achievement notification: {e}")

    async def sync_achievements(self, ctx: commands.Context, user: discord.Member):
        """Retroactively check for achievements."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(user)
        
        newly_unlocked = []
        
        # Helper to check if unlocked
        def is_unlocked(aid):
            return any(a.get("id") == aid for a in user_conf.achievement_log)
            
        # 1. First Catch
        if not is_unlocked("first_capture"):
            if user_conf.total_ever_claimed > 0:
                newly_unlocked.append("first_capture")
                
        # 2. Corrupted Hunter
        if not is_unlocked("first_corrupted"):
            # Check inventory
            has_corrupted = any(d.get("modifier", "").lower() == "corrupted" for d in user_conf.current_dino_inv)
            if has_corrupted:
                newly_unlocked.append("first_corrupted")
                
        # 3. Shiny Hunter
        if not is_unlocked("first_shiny"):
            has_shiny = any(d.get("modifier", "").lower() == "shiny" for d in user_conf.current_dino_inv)
            if has_shiny:
                newly_unlocked.append("first_shiny")
                
        # 4. Expansionist (First Upgrade)
        if not is_unlocked("first_upgrade"):
            if user_conf.current_inventory_upgrade_level > 0:
                newly_unlocked.append("first_upgrade")
                
        # 5. Prepared (First Lure Purchase)
        if not is_unlocked("first_lure_purchase"):
            if user_conf.has_lure or user_conf.last_lure_use > 0:
                newly_unlocked.append("first_lure_purchase")
                
        # 6. Trapper (First Lure Use)
        if not is_unlocked("first_lure_use"):
            if user_conf.last_lure_use > 0:
                newly_unlocked.append("first_lure_use")
                
        # 7. Researcher (First Log Check) - Cannot check retroactively
        
        # 8. Generous Soul (First Gift) - Cannot check retroactively
        
        # 9. Trader (First Trade)
        if not is_unlocked("first_trade"):
            if user_conf.total_ever_traded > 0:
                newly_unlocked.append("first_trade")
                
        # 10. Hoarder (Full Inventory)
        if not is_unlocked("full_inventory"):
            current_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
            if len(user_conf.current_dino_inv) >= current_size:
                newly_unlocked.append("full_inventory")
                
        # 11. Maxed Out (Max Upgrade)
        if not is_unlocked("max_upgrade"):
            if user_conf.current_inventory_upgrade_level >= conf.maximum_upgrade_amount:
                newly_unlocked.append("max_upgrade")
                
        # 12. Best Friends (First Buddy)
        if not is_unlocked("first_buddy"):
            if user_conf.buddy_dino:
                newly_unlocked.append("first_buddy")
                
        if newly_unlocked:
            total_reward = 0
            description = ""
            
            for aid in newly_unlocked:
                ach_data = achievement_library[aid]
                user_conf.achievement_log.append({"id": aid, "timestamp": time.time()})
                reward = ach_data["reward"]
                user_conf.has_dinocoins += reward
                user_conf.total_dinocoins_earned += reward
                total_reward += reward
                
                description += f"**{ach_data['name']}** (+{reward} coins)\n"
                
            self.save()
            
            embed = discord.Embed(
                title="🏆 Achievements Synced!",
                description=f"{user.mention}, you have retroactively unlocked the following achievements:\n\n{description}\n**Total Earned:** {total_reward} DinoCoins",
                color=discord.Color.gold()
            )
            await ctx.send(embed=embed)

    async def red_get_data_for_user(self, *args, **kwargs):
        return

    async def cog_load(self) -> None:
        asyncio.create_task(self.initialize())

    async def initialize(self) -> None:
        await self.bot.wait_until_red_ready()
        self.db = await asyncio.to_thread(DB.from_file, cog_data_path(self) / "dinocollectordb.json")
        log.info("Config loaded")

    async def cog_check(self, ctx: commands.Context) -> bool:
        if not ctx.guild:
            return False
            
        # Allow admins to bypass blacklist check
        if await is_admin_or_mod(ctx):
            return True
            
        conf = self.db.get_conf(ctx.guild)
        if ctx.author.id in conf.blacklisted_users:
            return False
            
        return True

    def save(self) -> None:
        if self._saving:
            self._save_retry = True
            return

        async def _save():
            try:
                self._saving = True
                while True:
                    self._save_retry = False
                    await asyncio.to_thread(self.db.to_file, cog_data_path(self) / "dinocollectordb.json")
                    if not self._save_retry:
                        break
            except Exception as e:
                log.exception("Failed to save config", exc_info=e)
            finally:
                self._saving = False

        asyncio.create_task(_save())

#-------- General Commands --------#

    @commands.command()
    @commands.admin_or_permissions(manage_guild=True)
    async def dcsetup(self, ctx: commands.Context):
        """Run the DinoCollector setup wizard."""
        await ctx.send(
            "The game is currently installed but disabled until you do a quick setup.\n"
            "Would you like to perform a **full** setup, or a **quick** setup? (Type `full` or `quick`)"
        )

        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        try:
            msg = await self.bot.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await ctx.send("Setup Cancelled, please run the command again if you wish to continue.")
            return

        content = msg.content.lower().strip()
        if content == "full":
            await self.do_full_setup(ctx)
        elif content == "quick":
            await self.do_quick_setup(ctx)
        else:
            await ctx.send("Setup Cancelled, please run the command again if you wish to continue.")

    async def do_full_setup(self, ctx: commands.Context):
        embed = discord.Embed(title="Full Setup", color=discord.Color.red())
        embed.description = "This feature is currently under construction. Please use the Quick Setup method for now. We apologize for the inconvenience."
        await ctx.send(embed=embed)

    async def do_quick_setup(self, ctx: commands.Context):
        conf = self.db.get_conf(ctx.guild)
        
        # Helper to handle mixed input (Button OR Message)
        async def wait_for_input_or_cancel(view, timeout=60):
            # Create tasks
            view_task = asyncio.create_task(view.wait())
            msg_task = asyncio.create_task(self.bot.wait_for(
                "message", 
                check=lambda m: m.author == ctx.author and m.channel == ctx.channel, 
                timeout=timeout
            ))
            
            done, pending = await asyncio.wait([view_task, msg_task], return_when=asyncio.FIRST_COMPLETED)
            
            # Cancel pending tasks
            for task in pending:
                task.cancel()
                
            if view_task in done:
                # Button clicked or timeout
                return "view", view.action
            else:
                # Message received
                try:
                    msg = msg_task.result()
                    return "message", msg
                except asyncio.TimeoutError:
                    return "timeout", None

        # Step 0: Initial Prompt
        embed = discord.Embed(title="Quick Setup", color=discord.Color.blue())
        embed.description = "First let's start with role permissions. Would you like to setup an Admin role?"
        
        view = SetupView(ctx)
        view.add_button("Yes", discord.ButtonStyle.green, "yes")
        view.add_button("No", discord.ButtonStyle.red, "no")
        
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        
        await view.wait()
        
        if view.action is None: # Timeout
            await ctx.send("Setup timed out.")
            return
            
        # Step 1: Admin Role
        if view.action == "yes":
            while True:
                embed.description = "Do you want to set an Admin role? You can change or remove this later using `[p]dcset`.\nPlease enter the role with the @ sign, or the Role ID number."
                view = SetupView(ctx)
                view.add_button("Cancel", discord.ButtonStyle.grey, "cancel")
                await msg.edit(embed=embed, view=view)
                view.message = msg
                
                result_type, result_data = await wait_for_input_or_cancel(view)
                
                if result_type == "view":
                    if result_data == "cancel":
                        embed.description = "Setup Cancelled. Please try again later."
                        await msg.edit(embed=embed, view=None)
                        return
                    else: # Timeout
                        await ctx.send("Setup timed out.")
                        return
                elif result_type == "message":
                    # Validate Role
                    role_input = result_data.content
                    role = None
                    
                    # Try ID
                    if role_input.isdigit():
                        role = ctx.guild.get_role(int(role_input))
                    # Try Mention
                    elif len(result_data.role_mentions) > 0:
                        role = result_data.role_mentions[0]
                    
                    if role:
                        conf.admin_role_id = role.id
                        self.save()
                        try:
                            await result_data.delete()
                        except:
                            pass
                        break
                    else:
                        # Invalid role
                        try:
                            await result_data.delete()
                        except:
                            pass
                        
                        # Ask to retry
                        embed.description = "Invalid role or ID. Would you like to try again?"
                        view = SetupView(ctx)
                        view.add_button("Yes", discord.ButtonStyle.green, "yes")
                        view.add_button("No", discord.ButtonStyle.red, "no")
                        await msg.edit(embed=embed, view=view)
                        view.message = msg
                        
                        await view.wait()
                        
                        if view.action == "no":
                            break # Skip to next step
                        elif view.action != "yes": # Cancel or Timeout
                            embed.description = "Setup Cancelled. Please try again later."
                            await msg.edit(embed=embed, view=None)
                            return
                        # If yes, loop continues
        
        # Step 2: Channel
        while True:
            embed.description = "What channel should the game start in? Either link it with # or input the channel id number. You can add more later."
            view = SetupView(ctx)
            view.add_button("Cancel", discord.ButtonStyle.grey, "cancel")
            await msg.edit(embed=embed, view=view)
            view.message = msg
            
            result_type, result_data = await wait_for_input_or_cancel(view)
            
            if result_type == "view":
                if result_data == "cancel":
                    embed.description = "Setup Cancelled. Please try again later."
                    await msg.edit(embed=embed, view=None)
                    return
                else:
                    await ctx.send("Setup timed out.")
                    return
            elif result_type == "message":
                # Validate Channel
                chan_input = result_data.content
                channel = None
                
                if chan_input.isdigit():
                    channel = ctx.guild.get_channel(int(chan_input))
                elif len(result_data.channel_mentions) > 0:
                    channel = result_data.channel_mentions[0]
                
                if channel and isinstance(channel, discord.TextChannel):
                    if channel.id not in conf.allowed_channels:
                        conf.allowed_channels.append(channel.id)
                        self.save()
                    try:
                        await result_data.delete()
                    except:
                        pass
                    break
                else:
                    try:
                        await result_data.delete()
                    except:
                        pass
                    await ctx.send("Invalid channel, please try again.", delete_after=3)
                    # Loop continues
        
        # Step 3: Spawn Method
        embed.description = "Do you want to use the Time spawn method(randomly checks every little bit) or the Message method(depends on user chat in the specific channel.)"
        view = SetupView(ctx)
        view.add_button("Time", discord.ButtonStyle.primary, "time")
        view.add_button("Message", discord.ButtonStyle.primary, "message")
        view.add_button("Cancel", discord.ButtonStyle.grey, "cancel")
        
        await msg.edit(embed=embed, view=view)
        view.message = msg
        
        await view.wait()
        
        if view.action == "cancel":
            embed.description = "Setup Cancelled. Please try again later."
            await msg.edit(embed=embed, view=None)
            return
        elif view.action in ["time", "message"]:
            conf.spawn_mode = view.action
            self.save()
        else:
            await ctx.send("Setup timed out.")
            return
            
        # Step 4: Currency Conversion
        embed.description = "Do you want to allow the Redbot Bank currency conversion? You can enable or disable this at any time later."
        view = SetupView(ctx)
        view.add_button("Yes", discord.ButtonStyle.green, "yes")
        view.add_button("No", discord.ButtonStyle.red, "no")
        view.add_button("Cancel", discord.ButtonStyle.grey, "cancel")
        
        await msg.edit(embed=embed, view=view)
        view.message = msg
        
        await view.wait()
        
        if view.action == "cancel":
            embed.description = "Setup Cancelled. Please try again later."
            await msg.edit(embed=embed, view=None)
            return
        elif view.action == "yes":
            conf.discord_conversion_enabled = True
            self.save()
            
            # Step 5: Conversion Rate
            embed.description = f"Do you want to set the Conversion Rate or use Default({conf.discord_conversion_rate})?"
            view = SetupView(ctx)
            view.add_button("Set", discord.ButtonStyle.primary, "set")
            view.add_button("Default", discord.ButtonStyle.secondary, "default")
            view.add_button("Cancel", discord.ButtonStyle.grey, "cancel")
            
            await msg.edit(embed=embed, view=view)
            view.message = msg
            
            await view.wait()
            
            if view.action == "cancel":
                embed.description = "Setup Cancelled. Please try again later."
                await msg.edit(embed=embed, view=None)
                return
            elif view.action == "set":
                currency_name = await bank.get_currency_name(ctx.guild)
                while True:
                    embed.description = f"The default is currently 100 DinoCoins to your {currency_name}. What would you like to change it to?"
                    view = SetupView(ctx)
                    view.add_button("Cancel", discord.ButtonStyle.grey, "cancel")
                    
                    await msg.edit(embed=embed, view=view)
                    view.message = msg
                    
                    result_type, result_data = await wait_for_input_or_cancel(view)
                    
                    if result_type == "view":
                        if result_data == "cancel":
                            embed.description = "Setup Cancelled. Please try again later."
                            await msg.edit(embed=embed, view=None)
                            return
                        else:
                            await ctx.send("Setup timed out.")
                            return
                    elif result_type == "message":
                        try:
                            new_rate = int(result_data.content)
                            if new_rate <= 0:
                                raise ValueError
                            
                            conf.discord_conversion_rate = new_rate
                            self.save()
                            try:
                                await result_data.delete()
                            except:
                                pass
                            
                            await ctx.send(f"The new Discord Conversion Rate is {new_rate} to 1 {currency_name}.", delete_after=5)
                            break
                        except ValueError:
                            try:
                                await result_data.delete()
                            except:
                                pass
                            await ctx.send("That is not a valid number. Please input a new amount.", delete_after=3)
                            
        elif view.action == "no":
            conf.discord_conversion_enabled = False
            self.save()
        else:
            await ctx.send("Setup timed out.")
            return
            
        # Step 6: Start Game
        embed.description = "Are you ready to Start the Game?(Spawning begins if you click yes.)"
        view = SetupView(ctx)
        view.add_button("Yes", discord.ButtonStyle.green, "yes")
        view.add_button("No", discord.ButtonStyle.red, "no")
        
        await msg.edit(embed=embed, view=view)
        view.message = msg
        
        await view.wait()
        
        if view.action == "yes":
            conf.game_is_enabled = True
            self.save()
            
            channels_str = ", ".join([f"<#{c}>" for c in conf.allowed_channels])
            await ctx.send(f"Thank you, the game has begun. Check {channels_str} shortly for a fresh spawn!")
            await msg.edit(view=None)
        elif view.action == "no":
            embed.description = "The game will not spawn dinos until you use the command `[p]dcset startgame`. You have completed setup."
            await msg.edit(embed=embed, view=None)
        else:
            await ctx.send("Setup timed out.")

    @commands.command()
    async def dccommands(self, ctx: commands.Context):
        """List all available DinoCollector commands."""
        embed = discord.Embed(title="DinoCollector Commands", color=discord.Color.green())
        
        # User Commands
        user_cmds = (
            "**dccommands** - List all available commands.\n"
            "**dcinv** - View your inventory.\n"
            "**dclog** - View your Explorer Log.\n"
            "**dcstats** - View your stats.\n"
            "**dcsell <item/all/rarity>** - Sell dinos.\n"
            "**dcbuddy set <id> / clear** - Manage your buddy dino.\n"
            "**dctrade <user> <id> [price]** - Trade dinos.\n"
            "**dclure** - Use a lure.\n"
            "**dcshop** - View the shop.\n"
            "**dcshop buy upgrade** - Buy inventory slots.\n"
            "**dcshop buy lure** - Buy a lure."
        )
        embed.add_field(name="**User Commands**", value=user_cmds, inline=False)
        
        # Admin Commands
        is_admin = await self.bot.is_admin(ctx.author)
        if is_admin:
            admin_cmds = (
                "**dcset adminrole <role>** - Set the admin role.\n"
                "**dcset spawn** - Force a test spawn.\n"
                "**dcset channel <add/remove/list>** - Manage spawn channels.\n"
                "**dcset mode <message/time>** - Set spawn mode.\n"
                "**dcset chance <0-100>** - Set spawn chance (message mode).\n"
                "**dcset interval <seconds>** - Set spawn interval (time mode).\n"
                "**dcset cooldown <seconds>** - Set spawn cooldown.\n"
                "**dcset shop <upgrade_price/lure_price/lure_cooldown>** - Shop settings.\n"
                "**dcset filter <add/remove/list>** - Manage disallowed names.\n"
                "**dcspawn <random/rarity/modifier>** - Force specific spawns."
            )
            embed.add_field(name="**Admin Commands**", value=admin_cmds, inline=False)
            
        await ctx.send(embed=embed)

#-------- Admin Commands --------#

    @commands.group(invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def dcset(self, ctx: commands.Context):
        """DinoCollector settings group."""
        embed = discord.Embed(title="DinoCollector Admin Settings", color=discord.Color.red())
        embed.description = f"Use `{ctx.prefix}dcset <command>` to configure the bot."
        
        # Game Control
        embed.add_field(
            name="🎮 Game Control",
            value=(
                "`startgame` - Start spawning\n"
                "`stopgame` - Stop spawning\n"
                "`spawn` - Force spawn a dino\n"
                "`mode <message/time>` - Set spawn mode\n"
                "`chance <0-100>` - Set spawn chance\n"
                "`interval <seconds>` - Set spawn interval\n"
                "`cooldown <seconds>` - Set spawn cooldown\n"
                "`cleanup` - Toggle message cleanup\n"
                "`display` - Toggle dino images"
            ),
            inline=False
        )
        
        # User Management
        embed.add_field(
            name="👥 User Management",
            value=(
                "`setuser <user> ...` - Modify user data\n"
                "`resetuser <user>` - Reset user progress\n"
                "`blacklist <add/remove/list>` - Manage blacklist\n"
                "`setcoin <user> <amount>` - Set user coins"
            ),
            inline=False
        )
        
        # Economy & Shop
        embed.add_field(
            name="💰 Economy & Shop",
            value=(
                "`displayshop` - View shop settings\n"
                "`conversion` - Toggle currency conversion\n"
                "`convertrate <rate>` - Set conversion rate\n"
                "`buddybonus` - Toggle buddy bonus\n"
                "`logprice <amount>` - Set log value"
            ),
            inline=False
        )
        
        # Configuration
        embed.add_field(
            name="⚙️ Configuration",
            value=(
                "`adminrole <role>` - Set admin role\n"
                "`channel <add/remove/list>` - Manage allowed channels\n"
                "`filter <add/remove/list>` - Manage disallowed names\n"
                "`event` - Toggle event mode\n"
                "`activeevent <type>` - Set active event"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @dcset.command(name="adminrole")
    async def dcset_adminrole(self, ctx: commands.Context, role: discord.Role = None):
        """Set the admin role for DinoCollector.
        
        Leave empty to clear the admin role.
        """
        conf = self.db.get_conf(ctx.guild)
        if role:
            conf.admin_role_id = role.id
            await ctx.send(f"Admin role set to {role.mention}. Users with this role can now use admin commands.")
        else:
            conf.admin_role_id = None
            await ctx.send("Admin role cleared. Only users with `Manage Server` permission can use admin commands.")
        self.save()

    @dcset.command(name="blacklist")
    async def dcset_blacklist(self, ctx: commands.Context, user: discord.Member = None):
        """Blacklist a user from using DinoCollector commands.
        
        If no user is provided, lists blacklisted users.
        """
        conf = self.db.get_conf(ctx.guild)
        
        if user is None:
            # List blacklisted users
            if not conf.blacklisted_users:
                await ctx.send("No users are blacklisted.")
                return
            
            names = []
            for uid in conf.blacklisted_users:
                member = ctx.guild.get_member(uid)
                if member:
                    names.append(member.display_name)
                else:
                    names.append(f"Unknown User ({uid})")
            
            await ctx.send(f"**Blacklisted Users:**\n{', '.join(names)}")
            return
            
        # Toggle blacklist
        if user.id in conf.blacklisted_users:
            conf.blacklisted_users.remove(user.id)
            self.save()
            await ctx.send(f"{user.display_name} has been removed from the blacklist.")
        else:
            conf.blacklisted_users.append(user.id)
            self.save()
            await ctx.send(f"{user.display_name} has been added to the blacklist.")

    @dcset.command(name="resetuser")
    async def dcset_resetuser(self, ctx: commands.Context, user: discord.User | int):
        """Reset a user's DinoCollector data to default.
        
        This will wipe their inventory, coins, stats, and everything else.
        This action cannot be undone.
        """
        from .views import ConfirmationView
        
        user_id = user if isinstance(user, int) else user.id
        user_name = str(user_id) if isinstance(user, int) else user.display_name
        
        conf = self.db.get_conf(ctx.guild)
        
        if user_id not in conf.users:
            await ctx.send(f"**{user_name}** has no data to reset.")
            return
            
        view = ConfirmationView(ctx.author)
        msg = await ctx.send(
            f"⚠️ **WARNING** ⚠️\nAre you sure you want to completely reset all DinoCollector data for **{user_name}**?\n"
            "This includes inventory, coins, stats, and upgrades. This cannot be undone.",
            view=view
        )
        view.message = msg
        
        await view.wait()
        
        if view.confirmed:
            if user_id in conf.users:
                del conf.users[user_id]
                self.save()
                await msg.edit(content=f"User data for **{user_name}** has been completely reset.", view=None)
            else:
                await msg.edit(content=f"User data for **{user_name}** was already gone.", view=None)
        else:
            await msg.edit(content="Reset cancelled.", view=None)

    @dcset.command(name="setuser")
    async def dcset_setuser(self, ctx: commands.Context, user: discord.Member | discord.User | int, action: str, subaction: str = None):
        """Manage user data.
        
        Usage:
        [p]dcset setuser <user> log full - Add all dinos to user's explorer log
        """
        user_id = user if isinstance(user, int) else user.id
        user_name = str(user_id) if isinstance(user, int) else user.display_name

        if action.lower() == "log" and subaction and subaction.lower() == "full":
            conf = self.db.get_conf(ctx.guild)
            
            if user_id not in conf.users:
                # Initialize user if they don't exist
                from .common.models import User
                conf.users[user_id] = User()
                
            user_conf = conf.users[user_id]
            
            added_count = 0
            current_log_names = {d["name"] for d in user_conf.explorer_log}
            
            for creature in creature_library.values():
                name = creature["name"]
                if name not in current_log_names:
                    user_conf.explorer_log.append({"name": name})
                    current_log_names.add(name)
                    added_count += 1
            
            if added_count > 0:
                user_conf.explorer_log.sort(key=lambda x: x["name"])
                self.save()
                await ctx.send(f"Added {added_count} dinos to **{user_name}**'s explorer log. It is now full.")
            else:
                await ctx.send(f"**{user_name}** already has a full explorer log.")
        else:
            await ctx.send("Invalid syntax. Usage: `[p]dcset setuser <user> log full`")

    @dcset.command(name="startgame")
    async def dcset_startgame(self, ctx: commands.Context):
        """Enable the DinoCollector game."""
        conf = self.db.get_conf(ctx.guild)
        if conf.game_is_enabled:
            await ctx.send("The game is already enabled.")
            return
        conf.game_is_enabled = True
        self.save()
        await ctx.send("DinoCollector has been enabled! Dinos will now spawn.")

    @dcset.command(name="stopgame")
    async def dcset_stopgame(self, ctx: commands.Context):
        """Disable the DinoCollector game."""
        conf = self.db.get_conf(ctx.guild)
        if not conf.game_is_enabled:
            await ctx.send("The game is already disabled.")
            return
        conf.game_is_enabled = False
        self.save()
        await ctx.send("DinoCollector has been disabled. No more dinos will spawn.")

    @dcset.command(name="event")
    async def dcset_event(self, ctx: commands.Context, status: str = None):
        """Toggle event mode on or off."""
        conf = self.db.get_conf(ctx.guild)
        
        if status is None:
            current = "On" if conf.event_mode_enabled else "Off"
            await ctx.send(f"Events are currently **{current}**.")
            return
            
        status = status.lower()
        
        if status == "on":
            if conf.event_mode_enabled:
                await ctx.send("Events are already enabled, you may turn them OFF or use the `activeevent` subcommand to select a new event.")
            else:
                conf.event_mode_enabled = True
                self.save()
                await ctx.send("Events have been turned on, please use the `activeevent` subcommand to select an event.")
                
        elif status == "off":
            if conf.event_mode_enabled:
                event_name = conf.event_active_type if conf.event_active_type else "Event mode"
                conf.event_mode_enabled = False
                conf.event_active_type = ""
                self.save()
                await ctx.send(f"{event_name} has been disabled.")
            else:
                conf.event_active_type = ""
                self.save()
                await ctx.send("Events are already disabled.")
        else:
            await ctx.send("Please specify 'on' or 'off'.")

    @dcset.command(name="conversion")
    async def dcset_conversion(self, ctx: commands.Context, status: str = None):
        """Toggle Discord currency conversion on or off."""
        conf = self.db.get_conf(ctx.guild)
        
        if status is None:
            current = "Enabled" if conf.discord_conversion_enabled else "Disabled"
            await ctx.send(f"Discord currency conversion is currently **{current}**.")
            return
            
        status = status.lower()
        if status == "on":
            if conf.discord_conversion_enabled:
                await ctx.send("Discord currency conversion is already enabled.")
            else:
                conf.discord_conversion_enabled = True
                self.save()
                await ctx.send("Discord currency conversion has been **Enabled**.")
        elif status == "off":
            if not conf.discord_conversion_enabled:
                await ctx.send("Discord currency conversion is already disabled.")
            else:
                conf.discord_conversion_enabled = False
                self.save()
                await ctx.send("Discord currency conversion has been **Disabled**.")
        else:
            await ctx.send("Please specify 'on' or 'off'.")

    @dcset.command(name="convertrate")
    async def dcset_convertrate(self, ctx: commands.Context, rate: int):
        """Set the DinoCoin to Discord Currency conversion rate.
        
        This sets how many DinoCoins are required to get 1 unit of server currency.
        """
        if rate < 1:
            await ctx.send("Conversion rate must be at least 1.")
            return
            
        conf = self.db.get_conf(ctx.guild)
        conf.discord_conversion_rate = rate
        self.save()
        
        currency_name = await bank.get_currency_name(ctx.guild)
        await ctx.send(f"Conversion rate set to **{rate}** DinoCoins = 1 {currency_name}.")

    @dcset.command(name="activeevent")
    async def dcset_activeevent(self, ctx: commands.Context, event_type: str = None):
        """Set the active event type."""
        if event_type is None:
            valid_list = ", ".join(sorted(type_events))
            await ctx.send(f"Please specify an event type.\nValid events: {valid_list}")
            return

        if event_type.lower() not in type_events:
            valid_list = ", ".join(sorted(type_events))
            await ctx.send(f"That is not a valid event.\nValid events: {valid_list}")
            return
            
        conf = self.db.get_conf(ctx.guild)
        conf.event_active_type = event_type.lower()
        
        if not conf.event_mode_enabled:
            conf.event_mode_enabled = True
            await ctx.send(f"Event mode enabled and active event set to **{event_type}**.")
        else:
            await ctx.send(f"Active event updated to **{event_type}**.")
            
        self.save()

    @dcset.command(name="cleanup")
    async def dcset_cleanup(self, ctx: commands.Context):
        """Toggle message cleanup.
        
        If enabled, spawn messages will be deleted when they expire or are completed.
        If disabled, they will remain but be disabled.
        """
        conf = self.db.get_conf(ctx.guild)
        conf.message_cleanup_enabled = not conf.message_cleanup_enabled
        self.save()
        
        status = "Enabled" if conf.message_cleanup_enabled else "Disabled"
        await ctx.send(f"Message cleanup has been **{status}**.")

    @dcset.command(name="display")
    async def dcset_display(self, ctx: commands.Context):
        """Display current DinoCollector settings."""
        conf = self.db.get_conf(ctx.guild)
        
        embed = discord.Embed(title="DinoCollector Settings", color=discord.Color.blue())
        
        # Helper for bools
        def status(b: bool):
            return "Enabled" if b else "Disabled"
            
        # Admin Role
        admin_role = "None"
        if conf.admin_role_id:
            role = ctx.guild.get_role(conf.admin_role_id)
            if role:
                admin_role = role.mention
            else:
                admin_role = f"Deleted Role ({conf.admin_role_id})"
        
        # Allowed Channels
        channels = "All Channels"
        if conf.allowed_channels:
            ch_list = []
            for cid in conf.allowed_channels:
                ch = ctx.guild.get_channel(cid)
                if ch:
                    ch_list.append(ch.mention)
                else:
                    ch_list.append(f"Unknown ({cid})")
            channels = ", ".join(ch_list)
            
        # Last Spawn
        last_spawn_str = "Never"
        if conf.last_spawn > 0:
            last_spawn_str = f"<t:{int(conf.last_spawn)}:R>"

        embed.add_field(name="Admin Role", value=admin_role, inline=True)
        embed.add_field(name="Game Status", value=status(conf.game_is_enabled), inline=True)
        embed.add_field(name="Message Cleanup", value=status(conf.message_cleanup_enabled), inline=True)
        
        conversion_status = status(conf.discord_conversion_enabled)
        if conf.discord_conversion_enabled:
            conversion_status += f" ({conf.discord_conversion_rate})"
        embed.add_field(name="Discord Conversion", value=conversion_status, inline=True)
        
        embed.add_field(name="Event Mode", value=status(conf.event_mode_enabled), inline=True)
        
        active_event = conf.event_active_type.title() if conf.event_mode_enabled and conf.event_active_type else "None"
        embed.add_field(name="Active Event", value=active_event, inline=True)
        
        embed.add_field(name="Dino Image Usage", value=status(conf.dino_image_usage), inline=True)
        embed.add_field(name="Spawn Mode", value=conf.spawn_mode.title(), inline=True)
        embed.add_field(name="Spawn Chance", value=f"{conf.spawn_chance}%", inline=True)
        embed.add_field(name="Spawn Fail Chance", value=f"{conf.spawn_fail_chance}%", inline=True)
        embed.add_field(name="Spawn Interval", value=f"{conf.spawn_interval}s", inline=True)
        embed.add_field(name="Spawn Cooldown", value=f"{conf.spawn_cooldown}s", inline=True)
        embed.add_field(name="Last Spawn", value=last_spawn_str, inline=True)
        embed.add_field(name="Allowed Channels", value=channels, inline=False)
        
        await ctx.send(embed=embed)

    @dcset.command(name="displayshop")
    async def dcset_displayshop(self, ctx: commands.Context):
        """Display current DinoCollector Shop settings."""
        conf = self.db.get_conf(ctx.guild)
        
        embed = discord.Embed(title="DinoCollector Shop Settings", color=discord.Color.gold())
        
        # Calculations
        max_inv = conf.base_inventory_size + (conf.maximum_upgrade_amount * conf.inventory_per_upgrade)
        
        # Helper for time formatting
        def format_time(seconds: int) -> str:
            if seconds == 0:
                return "0 seconds"
            
            m, s = divmod(seconds, 60)
            h, m = divmod(m, 60)
            d, h = divmod(h, 24)
            
            parts = []
            if d > 0:
                parts.append(f"{d} day{'s' if d != 1 else ''}")
            if h > 0:
                parts.append(f"{h} hour{'s' if h != 1 else ''}")
            if m > 0:
                parts.append(f"{m} minute{'s' if m != 1 else ''}")
            if s > 0:
                parts.append(f"{s} second{'s' if s != 1 else ''}")
            
            return " ".join(parts)

        lure_cd_str = format_time(conf.lure_cooldown)
        
        embed.add_field(name="Inventory Upgrade Cost", value=f"{conf.price_upgrade} Coins", inline=True)
        embed.add_field(name="Inventory Slots per Upgrade", value=f"{conf.inventory_per_upgrade}", inline=True)
        embed.add_field(name="Maximum Upgrade Times", value=f"{conf.maximum_upgrade_amount}", inline=True)
        embed.add_field(name="Total Max Inventory", value=f"{max_inv}", inline=True)
        embed.add_field(name="Lure Price", value=f"{conf.price_lure} Coins", inline=True)
        embed.add_field(name="Lure Cooldown", value=lure_cd_str, inline=True)
        embed.add_field(name="Buddy Bonus", value="Enabled" if conf.buddy_bonus_enabled else "Disabled", inline=True)
        embed.add_field(name="Explorer Log Value", value=f"{conf.explorer_log_value} Coins", inline=True)
        
        await ctx.send(embed=embed)

    @dcset.command(name="buddybonus")
    async def dcset_buddybonus(self, ctx: commands.Context, status: str = None):
        """Toggle buddy bonus on or off."""
        conf = self.db.get_conf(ctx.guild)
        
        if status is None:
            current = "Enabled" if conf.buddy_bonus_enabled else "Disabled"
            await ctx.send(f"Buddy bonus is currently **{current}**.")
            return
            
        status = status.lower()
        if status == "on":
            if conf.buddy_bonus_enabled:
                await ctx.send("Buddy bonus is already enabled.")
            else:
                conf.buddy_bonus_enabled = True
                self.save()
                await ctx.send("Buddy bonus has been **Enabled**.")
        elif status == "off":
            if not conf.buddy_bonus_enabled:
                await ctx.send("Buddy bonus is already disabled.")
            else:
                conf.buddy_bonus_enabled = False
                self.save()
                await ctx.send("Buddy bonus has been **Disabled**.")
        else:
            await ctx.send("Please specify 'on' or 'off'.")

    @dcset.command(name="logprice")
    async def dcset_logprice(self, ctx: commands.Context, amount: int):
        """Set the value of a completed Explorer Log."""
        if amount <= 0:
            await ctx.send("The value must be a positive integer.")
            return
            
        conf = self.db.get_conf(ctx.guild)
        conf.explorer_log_value = amount
        self.save()
        
        await ctx.send(f"Explorer Log value has been set to **{amount} DinoCoins**.")

    @dcset.command()
    async def spawn(self, ctx: commands.Context):
        """Spawn a random dino for testing purposes."""
        conf = self.db.get_conf(ctx.guild)
        result = select_random_creature(event_mode_enabled=conf.event_mode_enabled)
        if result:
            embed, creature_data = result
            # For test spawn, we can attach the view too if desired, or just show embed
            # Let's attach the view so they can test capturing
            view = SpawnView(self, creature_data)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
        else:
            await ctx.send("No creatures available.")

    @dcset.group(name="channel", invoke_without_command=True)
    async def dc_channel(self, ctx: commands.Context):
        """Manage allowed channels for DinoCollector."""
        await ctx.send_help(ctx.command)

    @dc_channel.command(name="add")
    async def dc_channel_add(self, ctx: commands.Context, channel: discord.TextChannel):
        """Add a channel to the allowed list."""
        self.add_allowed_channel(ctx.guild, channel.id)
        self.save()
        await ctx.send(f"{channel.mention} added to allowed channels.")

    @dc_channel.command(name="remove")
    async def dc_channel_remove(self, ctx: commands.Context, channel: discord.TextChannel):
        """Remove a channel from the allowed list."""
        self.remove_allowed_channel(ctx.guild, channel.id)
        self.save()
        await ctx.send(f"{channel.mention} removed from allowed channels.")

    @dc_channel.command(name="list")
    async def dc_channel_list(self, ctx: commands.Context):
        """List allowed channels."""
        allowed_ids = self.get_allowed_channels(ctx.guild)
        if not allowed_ids:
            await ctx.send("All channels are allowed for DinoCollector spawns.")
            return
        
        channels = []
        for channel_id in allowed_ids:
            ch = ctx.guild.get_channel(channel_id)
            if ch:
                channels.append(ch.mention)
            else:
                channels.append(f"Unknown channel ({channel_id})")
        
        channel_list = ", ".join(channels)
        await ctx.send(f"Allowed channels: {channel_list}")

    @dcset.group(name="filter", invoke_without_command=True)
    async def dc_filter(self, ctx: commands.Context):
        """Manage the disallowed names filter."""
        await ctx.send_help(ctx.command)

    @dc_filter.command(name="add")
    async def dc_filter_add(self, ctx: commands.Context, name: str):
        """Add a name to the disallowed list."""
        name = name.lower()
        self.set_disallowed_name(ctx.guild, name)
        self.save()
        await ctx.send(f"Added `{name}` to the disallowed list.")

    @dc_filter.command(name="remove")
    async def dc_filter_remove(self, ctx: commands.Context, name: str):
        """Remove a name from the disallowed list."""
        name = name.lower()
        self.remove_disallowed_name(ctx.guild, name)
        self.save()
        await ctx.send(f"Removed `{name}` from the disallowed list.")

    @dc_filter.command(name="list")
    async def dc_filter_list(self, ctx: commands.Context):
        """List disallowed names."""
        names = self.list_disallowed_names(ctx.guild)
        if not names:
            await ctx.send("No names are disallowed.")
            return
        
        # Chunking for long lists?
        msg = f"Disallowed names: {', '.join(names)}"
        if len(msg) > 2000:
            msg = msg[:1997] + "..."
        await ctx.send(msg)

    @commands.group(invoke_without_command=True)
    @commands.admin_or_permissions(manage_guild=True)
    async def dcspawn(self, ctx: commands.Context):
        """Admin spawn commands."""
        await ctx.send_help(ctx.command)

    @dcspawn.command(name="random")
    async def dcspawn_random(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Spawn a random dino.
        
        Optionally specify a channel to spawn in. If a channel is specified, the command message will be deleted.
        """
        conf = self.db.get_conf(ctx.guild)
        result = select_random_creature(
            event_mode_enabled=conf.event_mode_enabled,
            event_active_type=conf.event_active_type
        )
        if result:
            embed, creature_data = result
            view = SpawnView(self, creature_data)
            
            target_channel = channel or ctx.channel
            msg = await target_channel.send(embed=embed, view=view)
            view.message = msg
            
            if channel:
                try:
                    await ctx.message.delete()
                except (discord.Forbidden, discord.HTTPException):
                    pass
        else:
            await ctx.send("No creatures available.")

    @dcspawn.command(name="rarity")
    async def dcspawn_rarity(self, ctx: commands.Context, rarity: str):
        """Spawn a dino by rarity.
        
        Valid rarities: common, uncommon, semi_rare, rare, very_rare, super_rare, legendary, event
        """
        conf = self.db.get_conf(ctx.guild)
        result = select_random_creature(
            event_mode_enabled=conf.event_mode_enabled,
            event_active_type=conf.event_active_type,
            force_rarity=rarity.lower()
        )
        if result:
            embed, creature_data = result
            view = SpawnView(self, creature_data)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
        else:
            await ctx.send(f"Could not spawn creature with rarity '{rarity}'. Valid rarities: common, uncommon, semi_rare, rare, very_rare, super_rare, legendary, event.")

    @dcspawn.command(name="modifier")
    async def dcspawn_modifier(self, ctx: commands.Context, modifier: str):
        """Spawn a dino with a specific modifier."""
        conf = self.db.get_conf(ctx.guild)
        result = select_random_creature(
            event_mode_enabled=conf.event_mode_enabled,
            event_active_type=conf.event_active_type,
            force_modifier=modifier.lower()
        )
        if result:
            embed, creature_data = result
            view = SpawnView(self, creature_data)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
        else:
            await ctx.send(f"Could not spawn creature with modifier '{modifier}'. Valid modifiers: normal, muscular, young, sickly, withered, shiny, corrupted.")

    @dcspawn.command(name="full")
    async def dcspawn_full(self, ctx: commands.Context, modifier: str, creature_key: str, channel: discord.TextChannel = None):
        """Spawn a specific dino with a specific modifier.
        
        <modifier>: shiny, corrupted, normal, etc.
        <creature_key>: The key name of the creature (e.g. achatina, rex).
        [channel]: Optional channel to spawn in.
        """
        # Validate creature
        creature_key = creature_key.lower()
        if creature_key not in creature_library:
            await ctx.send(f"Creature `{creature_key}` not found.")
            return
            
        creature = creature_library[creature_key]
        
        # Validate modifier
        modifier = modifier.lower()
        if modifier not in all_modifiers:
             await ctx.send(f"Modifier `{modifier}` not found. Valid modifiers: {', '.join(all_modifiers.keys())}")
             return
             
        modifier_value = all_modifiers[modifier]
        
        # Calculate value
        min_val, max_val = creature["value"]
        base_value = random.randint(min_val, max_val)
        total_value = base_value + modifier_value
        if total_value < 1:
            total_value = 1
            
        # Prepare embed
        embed = discord.Embed(title=f"A {modifier} {creature['name']} has appeared!")
        if creature["image"]:
            embed.set_thumbnail(url=creature["image"])
        embed.add_field(name="DinoCoin Value", value=str(total_value), inline=True)
        
        creature_data = {
            "name": creature["name"],
            "modifier": modifier,
            "rarity": creature["rarity"],
            "value": total_value,
            "image": creature["image"]
        }
        
        view = SpawnView(self, creature_data)
        
        target_channel = channel or ctx.channel
        msg = await target_channel.send(embed=embed, view=view)
        view.message = msg
        
        if channel:
            try:
                await ctx.message.delete()
            except (discord.Forbidden, discord.HTTPException):
                pass

    @dcset.command()
    async def mode(self, ctx: commands.Context, mode: str):
        """Set the spawn mode: 'message' or 'time'."""
        mode = mode.lower()
        if mode not in ["message", "time"]:
            await ctx.send("Invalid mode. Please choose 'message' or 'time'.")
            return
        
        self.db.get_conf(ctx.guild).spawn_mode = mode
        self.save()
        await ctx.send(f"Spawn mode set to `{mode}`.")

    @dcset.command()
    async def chance(self, ctx: commands.Context, chance: int):
        """Set the spawn chance (0-100) for message mode."""
        if not 0 <= chance <= 100:
            await ctx.send("Chance must be between 0 and 100.")
            return
        
        self.db.get_conf(ctx.guild).spawn_chance = chance
        self.save()
        await ctx.send(f"Spawn chance set to {chance}%.")

    @dcset.command()
    async def interval(self, ctx: commands.Context, seconds: int):
        """Set the spawn interval in seconds for time mode."""
        if seconds < 60:
            await ctx.send("Interval must be at least 60 seconds.")
            return
        
        self.db.get_conf(ctx.guild).spawn_interval = seconds
        self.save()
        await ctx.send(f"Spawn interval set to {seconds} seconds.")

    @dcset.command()
    async def cooldown(self, ctx: commands.Context, seconds: int):
        """Set the cooldown in seconds for message mode spawns."""
        if seconds < 0:
            await ctx.send("Cooldown cannot be negative.")
            return
        
        self.db.get_conf(ctx.guild).spawn_cooldown = seconds
        self.save()
        await ctx.send(f"Message spawn cooldown set to {seconds} seconds.")

    @dcset.command(name="setcoin")
    async def dcset_setcoin(self, ctx: commands.Context, user: discord.Member, amount: str):
        """Modify a user's DinoCoin balance.
        
        Usage:
        [p]dcset setcoin <user> +500  (Add 500)
        [p]dcset setcoin <user> -500  (Remove 500)
        [p]dcset setcoin <user> 500   (Set to 500)
        """
        try:
            value = int(amount)
        except ValueError:
            await ctx.send("Invalid amount. Please enter a number (e.g. 500, +500, -500).")
            return

        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(user)
        
        if amount.startswith("+"):
            # Add
            if value < 0: # Should not happen if starts with + but int parsing handles it
                 await ctx.send("Invalid amount.")
                 return
            user_conf.has_dinocoins += value
            user_conf.total_dinocoins_earned += value
            action = "Added"
            
        elif amount.startswith("-"):
            # Subtract
            # value is negative here because int("-500") is -500
            user_conf.has_dinocoins += value # Adding negative is subtracting
            if user_conf.has_dinocoins < 0:
                user_conf.has_dinocoins = 0
            action = "Removed"
            # Do not change total_dinocoins_earned
            
        else:
            # Set (No sign)
            if value < 0:
                await ctx.send("Amount cannot be negative when setting balance.")
                return
            user_conf.has_dinocoins = value
            user_conf.total_dinocoins_earned += value
            action = "Set"
            
        self.save()
        
        await ctx.send(f"{action} **{abs(value)}** DinoCoins for {user.display_name}. New Balance: {user_conf.has_dinocoins}")

    @dcset.group(name="shop", invoke_without_command=True)
    async def dc_shop(self, ctx: commands.Context):
        """Manage shop settings."""
        await ctx.send_help(ctx.command)

    @dc_shop.command(name="upgrade_price")
    async def shop_upgrade_price(self, ctx: commands.Context, price: int):
        """Set the price for inventory upgrades."""
        if price < 0:
            await ctx.send("Price cannot be negative.")
            return
        self.db.get_conf(ctx.guild).price_upgrade = price
        self.save()
        await ctx.send(f"Inventory upgrade price set to {price} coins.")

    @dc_shop.command(name="lure_price")
    async def shop_lure_price(self, ctx: commands.Context, price: int):
        """Set the price for lures."""
        if price < 0:
            await ctx.send("Price cannot be negative.")
            return
        self.db.get_conf(ctx.guild).price_lure = price
        self.save()
        await ctx.send(f"Lure price set to {price} coins.")

    @dc_shop.command(name="lure_cooldown")
    async def shop_lure_cooldown(self, ctx: commands.Context, seconds: int):
        """Set the cooldown for lures in seconds."""
        if seconds < 0:
            await ctx.send("Cooldown cannot be negative.")
            return
        self.db.get_conf(ctx.guild).lure_cooldown = seconds
        self.save()
        await ctx.send(f"Lure cooldown set to {seconds} seconds.")
