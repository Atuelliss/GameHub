from ..abc import MixinMeta
from ..views import ConfirmationView, TradeView, SpawnView, LeaderboardView, PaginationView, HelpView, StatsView
from ..databases.gameinfo import select_random_creature, buddy_bonuses
from ..databases.creatures import creature_library
from ..databases.constants import DEFAULT_DISALLOWED_NAMES
from redbot.core import commands, bank
import discord
import time
import math

class User(MixinMeta):
    
    @commands.command()
    async def dchelp(self, ctx: commands.Context):
        """View the DinoCollector help menu."""
        embed = discord.Embed(title="Welcome to DinoCollector!", color=discord.Color.green())
        embed.description = (
            "This is an Ark-themed collection game. Dinosaurs from ASE and ASA will both spawn in user-set channels with a Capture button. "
            "Click them fast, as they will flee or others may grab them."
        )
        
        view = HelpView(ctx, self)
        view.update_buttons("main")
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg

    @commands.command(aliases=["dclb"])
    async def dcleaderboard(self, ctx: commands.Context):
        """View the DinoCollector leaderboard."""
        conf = self.db.get_conf(ctx.guild)
        
        # Get all users who have claimed at least one dino
        users_data = []
        for user_id, user_model in conf.users.items():
            if user_model.total_ever_claimed > 0:
                users_data.append((user_id, user_model))
        
        if not users_data:
            await ctx.send("No one has claimed any dinos yet!")
            return
            
        # Sort by total_ever_claimed descending
        users_data.sort(key=lambda x: x[1].total_ever_claimed, reverse=True)
        
        # Pagination logic
        per_page = 5
        pages = []
        num_pages = math.ceil(len(users_data) / per_page)
        
        for page_num in range(num_pages):
            start = page_num * per_page
            end = start + per_page
            chunk = users_data[start:end]
            
            embed = discord.Embed(title="🏆 DinoCollector Leaderboard", color=discord.Color.gold())
            description = ""
            
            for i, (user_id, user_model) in enumerate(chunk, start=start + 1):
                member = ctx.guild.get_member(user_id)
                username = member.name if member else f"Unknown User ({user_id})"
                
                description += (
                    f"**{i}. {username}** - "
                    f"Claimed: {user_model.total_ever_claimed} | "
                    f"Coins: {user_model.has_dinocoins} | "
                    f"Earned: {user_model.total_dinocoins_earned}\n\n"
                )
            
            embed.description = description
            embed.set_footer(text=f"Page {page_num + 1}/{num_pages}")
            pages.append(embed)
            
        view = LeaderboardView(pages, ctx.author)
        msg = await ctx.send(embed=pages[0], view=view)
        view.message = msg

    @commands.group(name="dclog", aliases=["dcel"], invoke_without_command=True)
    async def dclog(self, ctx: commands.Context, *, target: str = None):
        """View your Explorer Log (Dino Book)."""
        if target:
            target = target.strip()
            if target.lower() != "self" and target.lower() != ctx.author.name.lower():
                await ctx.send("You can only look at your own log.")
                return

        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        # Get all available creatures sorted by name
        all_creatures = sorted(creature_library.values(), key=lambda x: x["name"])
        total_creatures = len(all_creatures)
        
        # Get user's caught species
        caught_names = {d["name"] for d in user_conf.explorer_log}
        caught_count = 0
        
        # Calculate caught count based on library matching
        for c in all_creatures:
            if c["name"] in caught_names:
                caught_count += 1
                
        # Pagination
        per_page = 15
        pages = []
        num_pages = math.ceil(total_creatures / per_page)
        
        for page_num in range(num_pages):
            start = page_num * per_page
            end = start + per_page
            chunk = all_creatures[start:end]
            
            embed = discord.Embed(title="📖 Explorer Log", color=discord.Color.gold())
            embed.description = f"**Progress:** {caught_count}/{total_creatures} Species Caught\n\n"
            
            page_lines = []
            for i, creature in enumerate(chunk, start=start + 1):
                name = creature["name"].strip()
                is_caught = name in caught_names
                
                # Check for event
                is_event = creature.get("version") == "event" or creature.get("rarity") == "event"
                
                if is_caught:
                    if is_event:
                        page_lines.append(f"{i}. **{name}** (Event)")
                    else:
                        page_lines.append(f"{i}. **{name}**")
                else:
                    if is_event:
                        page_lines.append(f"{i}. *Unknown Dino!* (Event)")
                    else:
                        page_lines.append(f"{i}. *Unknown Dino!*")
            
            embed.description += "\n".join(page_lines)
            embed.set_footer(text=f"Page {page_num + 1}/{num_pages}")
            pages.append(embed)
            
        if not pages:
            await ctx.send("The creature library is empty!")
            return
            
        # Achievements
        await self.check_achievement(user_conf, "first_log_check", ctx)

        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            view = PaginationView(pages, ctx.author)
            msg = await ctx.send(embed=pages[0], view=view)
            view.message = msg

    @dclog.command(name="sell")
    async def dclog_sell(self, ctx: commands.Context):
        """Sell your completed Explorer Log for a reward."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        # Get all non-event creatures
        required_creatures = []
        for creature in creature_library.values():
            is_event = creature.get("version") == "event" or creature.get("rarity") == "event"
            if not is_event:
                required_creatures.append(creature["name"])
        
        # Check if user has all required creatures
        caught_names = {d["name"] for d in user_conf.explorer_log}
        missing = [name for name in required_creatures if name not in caught_names]
        
        if missing:
            await ctx.send("You still have missing slots in your Explorer Log!!! Hunt for more first!")
            return
            
        reward = conf.explorer_log_value
        
        view = ConfirmationView(ctx.author)
        # Customize buttons
        view.children[0].label = "Yes"
        view.children[1].label = "No"
        
        msg = await ctx.send(
            f"Are you sure you wish to sell your Explorer Log for {reward} DinoCoins?",
            view=view
        )
        view.message = msg
        
        await view.wait()
        
        if view.confirmed:
            # Clear log
            user_conf.explorer_log = []
            
            # Re-add buddy dino to log if exists
            if user_conf.buddy_dino:
                buddy_name = user_conf.buddy_dino.get("name")
                if buddy_name:
                    user_conf.explorer_log.append({"name": buddy_name})

            # Add coins
            user_conf.has_dinocoins += reward
            user_conf.total_dinocoins_earned += reward
            # Increment sold count
            user_conf.explorer_logs_sold += 1
            
            self.save()
            
            await msg.edit(content=f"You sold your Explorer Log for {reward} DinoCoins!", view=None)
        else:
            await msg.edit(content="You have decided not to sell your Explorer Log right now!", view=None)

    @commands.command()
    async def dcinv(self, ctx: commands.Context, user: discord.Member = None):
        """View your DinoCollector inventory."""
        target_user = user or ctx.author
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(target_user)
        
        if not user_conf.current_dino_inv:
            await ctx.send(f"{target_user.display_name}'s inventory is empty!")
            return
            
        # Pagination logic
        per_page = 25
        pages = []
        num_pages = math.ceil(len(user_conf.current_dino_inv) / per_page)
        
        for page_num in range(num_pages):
            start = page_num * per_page
            end = start + per_page
            chunk = user_conf.current_dino_inv[start:end]
            
            embed = discord.Embed(title=f"{target_user.display_name}'s Inventory", color=discord.Color.blue())
            description = ""
            
            for i, dino in enumerate(chunk, start=start + 1):
                modifier = dino.get('modifier', 'Normal')
                name = dino.get('name', 'Unknown')
                value = dino.get('value', 0)
                rarity = dino.get('rarity', 'Common').title()
                
                line = f"**{i}.** {modifier} {name} ({rarity}) - {value} Coins\n"
                description += line
            
            embed.description = description
            
            current_inv_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
            embed.set_footer(text=f"Page {page_num + 1}/{num_pages} | Total Dinos: {len(user_conf.current_dino_inv)} | Capacity: {current_inv_size}")
            pages.append(embed)
            
        if len(pages) == 1:
            await ctx.send(embed=pages[0])
        else:
            view = PaginationView(pages, ctx.author)
            msg = await ctx.send(embed=pages[0], view=view)
            view.message = msg

    @commands.command()
    async def dcsell(self, ctx: commands.Context, selection: str):
        """Sell dinos from your inventory.
        
        You can sell a specific dino by number, or bulk sell by rarity/all.
        
        Examples:
        `[p]dcsell 1` - Sell dino #1
        `[p]dcsell all` - Sell EVERYTHING
        `[p]dcsell common` - Sell all Common dinos
        `[p]dcsell rare` - Sell all Rare dinos
        """
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        if not user_conf.current_dino_inv:
            await ctx.send("Your inventory is empty!")
            return

        # Determine what to sell
        to_sell_indices = []
        selection = selection.lower()
        skipped_special = False
        
        if selection == "all":
            # Filter out shiny and event dinos
            for i, dino in enumerate(user_conf.current_dino_inv):
                is_shiny = dino.get("modifier", "").lower() == "shiny"
                is_event = dino.get("rarity", "").lower() == "event" or dino.get("version", "").lower() == "event"
                
                if is_shiny or is_event:
                    skipped_special = True
                else:
                    to_sell_indices.append(i)
                    
        elif selection.isdigit():
            idx = int(selection) - 1
            if 0 <= idx < len(user_conf.current_dino_inv):
                to_sell_indices = [idx]
            else:
                await ctx.send(f"Invalid number. Please choose between 1 and {len(user_conf.current_dino_inv)}.")
                return
        else:
            # Try to match rarity
            # Valid rarities: common, uncommon, semi_rare, rare, very_rare, super_rare, legendary, event
            # Allow partial matching e.g. "semi" for "semi_rare" if unambiguous? Let's stick to exact or simple mapping.
            rarity_map = {
                "common": "common",
                "uncommon": "uncommon",
                "semi": "semi_rare",
                "semi_rare": "semi_rare",
                "rare": "rare",
                "very": "very_rare",
                "very_rare": "very_rare",
                "super": "super_rare",
                "super_rare": "super_rare",
                "legendary": "legendary",
                "event": "event"
            }
            
            target_rarity = rarity_map.get(selection)
            if target_rarity:
                for i, dino in enumerate(user_conf.current_dino_inv):
                    if dino.get("rarity") == target_rarity:
                        # Check for shiny/event exclusion even in rarity selection (unless they specifically asked for 'event')
                        is_shiny = dino.get("modifier", "").lower() == "shiny"
                        # If they asked for 'event', don't skip events. But still skip shinies? 
                        # The request said "if there is a shiny or event dino within the inventory it would be excluded"
                        # I'll assume if they explicitly type "dcsell event", they WANT to sell events.
                        # But if they type "dcsell rare" and there is a shiny rare, skip it.
                        
                        should_skip = False
                        if is_shiny:
                            should_skip = True
                        
                        if target_rarity != "event":
                             is_event = dino.get("version", "").lower() == "event"
                             if is_event:
                                 should_skip = True
                        
                        if should_skip:
                            skipped_special = True
                        else:
                            to_sell_indices.append(i)
            else:
                await ctx.send("Invalid selection. Use a number, 'all', or a rarity (common, rare, etc).")
                return

        if not to_sell_indices:
            if skipped_special:
                await ctx.send("No dinos matched your selection (Shiny and Event dinos are protected from bulk selling).")
            else:
                await ctx.send("No dinos matched your selection.")
            return

        # Calculate totals
        total_value = 0
        dinos_to_remove = []
        
        # We need to be careful about indices shifting if we pop them one by one.
        # Better to collect the objects first.
        for i in to_sell_indices:
            dino = user_conf.current_dino_inv[i]
            total_value += dino.get("value", 0)
            dinos_to_remove.append(dino)

        count = len(dinos_to_remove)
        
        # Get buddy bonus percent
        bonus_percent = 0
        if conf.buddy_bonus_enabled and user_conf.buddy_dino:
            rarity = user_conf.buddy_dino_rarity.lower()
            bonus_percent = buddy_bonuses.get(rarity, 0)

        # Generate list of items for confirmation
        item_list = ""
        for dino in dinos_to_remove:
            modifier = dino.get('modifier', 'Normal')
            name = dino.get('name', 'Unknown')
            val = dino.get('value', 0)
            line = f"- {modifier} {name} ({val} coins)\n"
            
            if bonus_percent > 0:
                bonus = math.ceil(val * (bonus_percent / 100))
                if bonus == 0:
                    line += "  (Dino value too low to gain a buddy bonus.)\n"

            if len(item_list) + len(line) > 1500:
                item_list += f"... and {count - dinos_to_remove.index(dino)} more."
                break
            item_list += line

        # Confirmation
        description = f"Are you sure you want to sell **{count}** dino(s) for **{total_value}** DinoCoins?"
        if bonus_percent == 0:
             description += "\n(Active Buddy Bonus: 0%)"
        
        description += f"\n\n{item_list}"

        embed = discord.Embed(
            title="Confirm Sale",
            description=description,
            color=discord.Color.orange()
        )
        
        view = ConfirmationView(ctx.author)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        
        await view.wait()
        
        if view.confirmed:
            # Process Sale
            # Remove items. Since objects are references, we can remove them from the list.
            # But removing from list while iterating is tricky.
            # Rebuild the list excluding the sold ones.
            
            # Create a new list for inventory
            new_inv = []
            # We can't just use "if dino not in dinos_to_remove" because of duplicates.
            # We need to remove specific instances.
            
            # Let's use a set of indices to keep
            indices_to_sell = set(to_sell_indices)
            for i, dino in enumerate(user_conf.current_dino_inv):
                if i not in indices_to_sell:
                    new_inv.append(dino)
            
            # Calculate Bonus
            bonus_amount = 0
            bonus_percent = 0
            
            if conf.buddy_bonus_enabled and user_conf.buddy_dino:
                rarity = user_conf.buddy_dino_rarity.lower()
                bonus_percent = buddy_bonuses.get(rarity, 0)
                if bonus_percent > 0:
                    bonus_amount = math.ceil(total_value * (bonus_percent / 100))
            
            final_total = total_value + bonus_amount

            user_conf.current_dino_inv = new_inv
            user_conf.has_dinocoins += final_total
            user_conf.total_dinocoins_earned += final_total
            user_conf.total_ever_sold += count
            user_conf.buddy_bonus_total_gained += bonus_amount
            
            self.save()
            
            embed.title = "Sale Complete"
            if bonus_amount > 0:
                embed.description = (
                    f"Sold **{count}** dino(s).\n"
                    f"Base Value: {total_value}\n"
                    f"Buddy Bonus ({bonus_percent}%): +{bonus_amount}\n"
                    f"**Total Received: {final_total} DinoCoins**\n"
                    f"New Balance: {user_conf.has_dinocoins}"
                )
            else:
                low_value_note = "(Dino value was too low to grant a bonus.)\n" if bonus_percent > 0 else ""
                embed.description = (
                    f"Sold **{count}** dino(s).\n"
                    f"Base Value: {total_value}\n"
                    f"Buddy Bonus ({bonus_percent}%): +0\n"
                    f"{low_value_note}"
                    f"**Total Received: {total_value} DinoCoins**\n"
                    f"New Balance: {user_conf.has_dinocoins}"
                )
            
            if skipped_special:
                embed.description += "\n\n**Note:** Your shiny and event dinos were not sold. Please sell those individually if you wish to do so."

            embed.color = discord.Color.green()
            await msg.edit(embed=embed, view=None)
            
        else:
            # Cancelled
            embed.title = "Sale Cancelled"
            embed.description = "No dinos were sold."
            embed.color = discord.Color.red()
            await msg.edit(embed=embed, view=None)

    @commands.group(invoke_without_command=True)
    async def dcbuddy(self, ctx: commands.Context):
        """Manage your buddy dino."""
        await ctx.send_help(ctx.command)

    @dcbuddy.command(name="set")
    async def dcbuddy_set(self, ctx: commands.Context, dino_id: int):
        """Set a dino from your inventory as your buddy."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        # Check if user already has a buddy
        if user_conf.buddy_dino:
            await ctx.send(f"You already have a buddy! Use `{ctx.clean_prefix}dcbuddy clear` to remove it first.")
            return

        # Validate index
        idx = dino_id - 1
        if idx < 0 or idx >= len(user_conf.current_dino_inv):
            await ctx.send(f"Invalid dino ID. Please choose between 1 and {len(user_conf.current_dino_inv)}.")
            return

        # Get the dino
        dino = user_conf.current_dino_inv[idx]
        
        # Move to buddy
        user_conf.buddy_dino = dino
        user_conf.buddy_dino_rarity = dino.get("rarity", "Common")
        
        # Remove from inventory
        user_conf.current_dino_inv.pop(idx)
        
        self.save()
        
        modifier = dino.get("modifier", "Normal")
        name = dino.get("name", "Unknown")
        await ctx.send(f"You have set a **{modifier} {name}** as your buddy!")

        # Achievements
        await self.check_achievement(user_conf, "first_buddy", ctx)

    @dcbuddy.command(name="clear")
    async def dcbuddy_clear(self, ctx: commands.Context):
        """Return your buddy dino to your inventory."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        if not user_conf.buddy_dino:
            await ctx.send("You don't have a buddy set!")
            return
            
        # Check inventory capacity
        current_inv_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        if len(user_conf.current_dino_inv) >= current_inv_size:
            await ctx.send("You must sell at least one dino first.")
            return
            
        # Move back to inventory
        user_conf.current_dino_inv.append(user_conf.buddy_dino)
        
        # Clear buddy
        user_conf.buddy_dino = {}
        user_conf.buddy_dino_rarity = ""
        user_conf.buddy_name = ""
        
        self.save()
        
        await ctx.send("Your buddy has been returned to your inventory.")

    @dcbuddy.command(name="name")
    async def dcbuddy_name(self, ctx: commands.Context, *, name: str):
        """Rename your buddy dino."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        if not user_conf.buddy_dino:
            await ctx.send("You don't have a buddy set!")
            return
            
        # Check disallowed names
        if any(bad_word in name.lower() for bad_word in conf.disallowed_names):
            await ctx.send("You cannot use that name.")
            return
            
        # Set nickname
        user_conf.buddy_name = name
        self.save()
        
        await ctx.send(f"Your buddy has been renamed to **{name}**!")

    @dcbuddy.command(name="info")
    async def dcbuddy_info(self, ctx: commands.Context):
        """View details about your current buddy."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        if not user_conf.buddy_dino:
            await ctx.send(f"You don't have a buddy set! Use `{ctx.clean_prefix}dcbuddy set <id>` to set one.")
            return
            
        buddy = user_conf.buddy_dino
        rarity = buddy.get("rarity", "common")
        bonus = buddy_bonuses.get(rarity, 0)
        
        embed = discord.Embed(title="🦕 Buddy Information", color=discord.Color.green())
        
        spacer = "\u2002\u2002\u2002"
        details = f"**Rarity:** {rarity.title().replace('_', ' ')}{spacer}**Value:** {buddy.get('value', 0)} DinoCoins{spacer}**Buddy Bonus:** {bonus}%"
        
        # Determine display name
        nickname = user_conf.buddy_name
        species_name = f"{buddy.get('modifier', '').title()} {buddy.get('name', 'Unknown')}"
        
        if nickname:
            display_text = f"**Name - {nickname}**\n**Dino - {species_name}**\n\n{details}"
        else:
            display_text = f"**{species_name}**\n\n{details}"
        
        embed.add_field(name="Buddy Details", value=display_text, inline=False)
        
        embed.add_field(name="Total Bonus Earned", value=f"{user_conf.buddy_bonus_total_gained} DinoCoins", inline=False)
        
        if buddy.get("image"):
            embed.set_thumbnail(url=buddy.get("image"))
            
        await ctx.send(embed=embed)
    @commands.command()
    async def dclure(self, ctx: commands.Context):
        """Use a lure to spawn a dino in the current channel."""
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)

        # Check if user has a lure
        if not user_conf.has_lure:
            await ctx.send(f"You don't have a lure! Buy one from the shop: `{ctx.prefix}dcshop buy lure`")
            return

        # Check Channel Permissions
        if conf.allowed_channels and ctx.channel.id not in conf.allowed_channels:
            await ctx.send("You cannot use a lure in this channel!")
            return

        # Check Cooldown
        now = time.time()
        if now - user_conf.last_lure_use < conf.lure_cooldown:
            remaining = int(conf.lure_cooldown - (now - user_conf.last_lure_use))
            minutes = remaining // 60
            seconds = remaining % 60
            await ctx.send(f"You must wait **{minutes}m {seconds}s** before using another lure.")
            return

        # Consume Lure and Set Cooldown
        user_conf.has_lure = False
        user_conf.last_lure_use = now
        self.save()

        # Trigger Spawn
        await ctx.send(f"🥩 You placed a lure... something is approaching!")
        
        # Achievements
        await self.check_achievement(user_conf, "first_lure_use", ctx)

        result = select_random_creature(
            event_mode_enabled=conf.event_mode_enabled,
            event_active_type=conf.event_active_type
        )
        if result:
            embed, creature_data = result
            view = SpawnView(self, creature_data)
            msg = await ctx.send(embed=embed, view=view)
            view.message = msg
        else:
            # Refund Lure if something breaks
            user_conf.has_lure = True
            user_conf.last_lure_use = 0 # Reset cooldown
            self.save()
            await ctx.send("The lure failed to attract anything. (Lure returned)")

    @commands.command()
    async def dctrade(self, ctx: commands.Context, user: discord.Member, my_dino_id: int, trade_type: str, value: int = 0):
        """Trade a dino with another user.
        
        Usage:
        [p]dctrade <user> <your_dino_id> free
        [p]dctrade <user> <your_dino_id> coin <amount>
        [p]dctrade <user> <your_dino_id> dino <their_dino_id>
        """
        if user.id == ctx.author.id:
            await ctx.send("You cannot trade with yourself.")
            return
        if user.bot:
            await ctx.send("You cannot trade with bots.")
            return

        trade_type = trade_type.lower()
        if trade_type not in ["free", "coin", "dino"]:
            await ctx.send("Invalid trade type. Use `free`, `coin`, or `dino`.")
            return

        if trade_type in ["coin", "dino"] and value <= 0:
            await ctx.send(f"You must specify a valid {'amount' if trade_type == 'coin' else 'dino ID'} greater than 0.")
            return

        conf = self.db.get_conf(ctx.guild)
        sender_conf = conf.get_user(ctx.author)
        recipient_conf = conf.get_user(user)

        # Validate Sender has Dino
        if not sender_conf.current_dino_inv:
            await ctx.send("You have no dinos to trade.")
            return
        
        s_idx = my_dino_id - 1
        if not (0 <= s_idx < len(sender_conf.current_dino_inv)):
            await ctx.send(f"Invalid dino ID for you. Please choose between 1 and {len(sender_conf.current_dino_inv)}.")
            return
            
        dino_to_give = sender_conf.current_dino_inv[s_idx]
        dino_to_receive = None
        price = 0

        # Validate Trade Type Specifics
        recipient_inv_size = conf.base_inventory_size + (recipient_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        
        if trade_type == "free":
            # Recipient needs space
            if len(recipient_conf.current_dino_inv) >= recipient_inv_size:
                await ctx.send(f"{user.display_name}'s inventory is full!")
                return
                
        elif trade_type == "coin":
            price = value
            # Recipient needs space
            if len(recipient_conf.current_dino_inv) >= recipient_inv_size:
                await ctx.send(f"{user.display_name}'s inventory is full!")
                return
            # Recipient needs coins
            if recipient_conf.has_dinocoins < price:
                await ctx.send(f"{user.display_name} does not have enough DinoCoins ({price}).")
                return

        elif trade_type == "dino":
            # Recipient needs to have the dino
            if not recipient_conf.current_dino_inv:
                await ctx.send(f"{user.display_name} has no dinos to trade.")
                return
            
            r_idx = value - 1
            if not (0 <= r_idx < len(recipient_conf.current_dino_inv)):
                await ctx.send(f"Invalid dino ID for {user.display_name}. Please choose between 1 and {len(recipient_conf.current_dino_inv)}.")
                return
            
            dino_to_receive = recipient_conf.current_dino_inv[r_idx]

        # Send Trade Request
        embed = discord.Embed(title="Trade Request", color=discord.Color.gold())
        embed.description = f"{ctx.author.mention} wants to trade with {user.mention}."
        
        embed.add_field(name=f"{ctx.author.display_name} Offers", value=f"{dino_to_give['modifier']} {dino_to_give['name']} ({dino_to_give['rarity']})", inline=False)
        
        if trade_type == "free":
            embed.add_field(name="Requesting", value="Nothing (Free)", inline=False)
        elif trade_type == "coin":
            embed.add_field(name="Requesting", value=f"{price} DinoCoins", inline=False)
        elif trade_type == "dino":
            assert dino_to_receive is not None  # for type checker
            embed.add_field(name=f"{user.display_name} Offers", value=f"{dino_to_receive['modifier']} {dino_to_receive['name']} ({dino_to_receive['rarity']})", inline=False)

        embed.set_footer(text="Recipient must accept within 2 minutes.")

        view = TradeView(ctx.author, user)
        msg = await ctx.send(content=user.mention, embed=embed, view=view)
        view.message = msg
        
        await view.wait()
        
        if view.confirmed:
            # Re-validate EVERYTHING
            if dino_to_give not in sender_conf.current_dino_inv:
                await ctx.send(f"Trade failed: {ctx.author.display_name} no longer has the dino they offered!")
                return

            if trade_type == "free" or trade_type == "coin":
                recipient_inv_size = conf.base_inventory_size + (recipient_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
                if len(recipient_conf.current_dino_inv) >= recipient_inv_size:
                    await ctx.send(f"Trade failed: {user.display_name}'s inventory is full!")
                    return
            
            if trade_type == "coin":
                if recipient_conf.has_dinocoins < price:
                    await ctx.send(f"Trade failed: {user.display_name} does not have enough coins!")
                    return
            
            if trade_type == "dino":
                if dino_to_receive not in recipient_conf.current_dino_inv:
                    await ctx.send(f"Trade failed: {user.display_name} no longer has the requested dino!")
                    return

            # Execute Trade
            sender_conf.current_dino_inv.remove(dino_to_give)
            recipient_conf.current_dino_inv.append(dino_to_give)
            
            # Achievements
            if trade_type == "free":
                await self.check_achievement(sender_conf, "first_gift", ctx)
            else:
                await self.check_achievement(sender_conf, "first_trade", ctx)
            
            if trade_type == "dino":
                recipient_conf.current_dino_inv.remove(dino_to_receive)
                sender_conf.current_dino_inv.append(dino_to_receive)
                
                # Update Log for Sender (since they received a dino)
                assert dino_to_receive is not None  # for type checker
                already_in_log_s = any(d.get("name") == dino_to_receive["name"] for d in sender_conf.explorer_log)
                if not already_in_log_s:
                    sender_conf.explorer_log.append({"name": dino_to_receive["name"]})
                    sender_conf.explorer_log.sort(key=lambda x: x["name"])

            # Transfer Funds
            if trade_type == "coin":
                recipient_conf.has_dinocoins -= price
                recipient_conf.has_spent_dinocoins += price
                sender_conf.has_dinocoins += price
                sender_conf.total_dinocoins_earned += price
            
            # Update Stats
            sender_conf.total_ever_traded += 1
            recipient_conf.total_ever_traded += 1
            
            # Update Log for Recipient
            already_in_log = any(d.get("name") == dino_to_give["name"] for d in recipient_conf.explorer_log)
            if not already_in_log:
                recipient_conf.explorer_log.append({"name": dino_to_give["name"]})
                recipient_conf.explorer_log.sort(key=lambda x: x["name"])

            self.save()
            
            embed.title = "Trade Successful"
            embed.color = discord.Color.green()
            embed.clear_fields()
            
            desc = f"{ctx.author.mention} traded **{dino_to_give['name']}** to {user.mention}"
            if trade_type == "free":
                desc += " for free."
            elif trade_type == "coin":
                desc += f" for **{price}** coins."
            elif trade_type == "dino":
                assert dino_to_receive is not None  # for type checker
                desc += f" for **{dino_to_receive['name']}**."
            
            embed.description = desc
            await msg.edit(embed=embed, view=None)
            
        else:
            embed.title = "Trade Cancelled"
            embed.color = discord.Color.red()
            await msg.edit(embed=embed, view=None)

    @commands.command(aliases=["dcstat"])
    async def dcstats(self, ctx: commands.Context, user: discord.Member = None):
        """View DinoCollector statistics."""
        if not user:
            user = ctx.author
            
        # Sync achievements before showing stats
        await self.sync_achievements(ctx, user)
            
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(user)
        
        embed = discord.Embed(title=f"DinoCollector Stats: {user.display_name}", color=discord.Color.blue())
        embed.set_thumbnail(url=user.display_avatar.url)
        
        # Economy
        embed.add_field(name="💰 DinoCoins", value=f"{user_conf.has_dinocoins}", inline=True)
        embed.add_field(name="📈 Total Earned", value=f"{user_conf.total_dinocoins_earned}", inline=True)
        
        # Inventory
        current_inv_size = conf.base_inventory_size + (user_conf.current_inventory_upgrade_level * conf.inventory_per_upgrade)
        embed.add_field(name="🎒 Inventory", value=f"{len(user_conf.current_dino_inv)}/{current_inv_size}", inline=True)
        
        # Stats
        embed.add_field(name="🦖 Total Caught", value=f"{user_conf.total_ever_claimed}", inline=True)
        embed.add_field(name="💨 Escaped", value=f"{user_conf.total_escaped}", inline=True)
        embed.add_field(name="🤝 Total Traded", value=f"{user_conf.total_ever_traded}", inline=True)
        
        # First Catch
        first_dino = user_conf.first_dino_ever_caught or "None"
        first_time_str = "N/A"
        if user_conf.first_dino_caught_timestamp:
            try:
                ts = float(user_conf.first_dino_caught_timestamp)
                first_time_str = f"<t:{int(ts)}:D>"
            except ValueError:
                pass
                
        embed.add_field(name="🥇 First Catch", value=f"{first_dino}\n{first_time_str}", inline=True)
        
        # Buddy Dino
        if user_conf.buddy_dino:
            b_mod = user_conf.buddy_dino.get("modifier", "Normal")
            b_name = user_conf.buddy_dino.get("name", "Unknown")
            b_rarity = user_conf.buddy_dino.get("rarity", "Common").title()
            buddy_str = f"{b_mod} {b_name}\n({b_rarity})"
        else:
            buddy_str = "None"
            
        embed.add_field(name="🦕 Buddy", value=buddy_str, inline=True)

        # Explorer Logs Sold
        embed.add_field(name="📚 Logs Sold", value=f"{user_conf.explorer_logs_sold}", inline=True)

        # Lure Status
        has_lure = "Yes" if user_conf.has_lure else "No"
        
        now = time.time()
        if now - user_conf.last_lure_use < conf.lure_cooldown:
            remaining = int(conf.lure_cooldown - (now - user_conf.last_lure_use))
            minutes = remaining // 60
            seconds = remaining % 60
            lure_status = f"Cooldown: {minutes}m {seconds}s"
        else:
            lure_status = "Ready to use"
            
        embed.add_field(name="🥩 Lure", value=f"Owned: {has_lure}\nStatus: {lure_status}", inline=True)
        
        view = StatsView(ctx, user, self, embed)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.command()
    async def dcconvert(self, ctx: commands.Context, amount: str):
        """Convert DinoCoins to server currency.
        
        Usage:
        [p]dcconvert 500
        [p]dcconvert all
        """
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        if not conf.discord_conversion_enabled:
            await ctx.send("Currency conversion is disabled on this server.")
            return
            
        rate = conf.discord_conversion_rate
        
        if amount.lower() == "all":
            # Calculate max possible conversion
            if user_conf.has_dinocoins < rate:
                currency_name = await bank.get_currency_name(ctx.guild)
                await ctx.send(f"You need at least {rate} DinoCoins to convert (Rate: {rate} DC = 1 {currency_name}).")
                return
                
            # Calculate max whole number of currency
            max_currency = user_conf.has_dinocoins // rate
            amount_int = max_currency * rate
        else:
            try:
                amount_int = int(amount)
            except ValueError:
                await ctx.send("Please enter a valid number or 'all'.")
                return
                
            if amount_int <= 0:
                await ctx.send("Please enter a positive amount.")
                return
            
        if amount_int < rate:
            currency_name = await bank.get_currency_name(ctx.guild)
            await ctx.send(f"You need at least {rate} DinoCoins to convert (Rate: {rate} DC = 1 {currency_name}).")
            return
            
        if user_conf.has_dinocoins < amount_int:
            await ctx.send(f"You don't have enough DinoCoins! You have {user_conf.has_dinocoins}.")
            return
            
        # Calculate exact conversion
        currency_to_receive = amount_int // rate
        dinocoins_to_deduct = currency_to_receive * rate
        
        currency_name = await bank.get_currency_name(ctx.guild)
        
        msg_text = ""
        if dinocoins_to_deduct != amount_int:
            msg_text = (
                f"You have input a number outside the conversion ratio.\n"
                f"Would you like to convert **{dinocoins_to_deduct}** DinoCoins into **{currency_to_receive} {currency_name}**?"
            )
        else:
            msg_text = (
                f"Are you sure you wish to convert **{dinocoins_to_deduct}** DinoCoins into **{currency_to_receive} {currency_name}**?"
            )
            
        view = ConfirmationView(ctx.author, timeout=180)
        msg = await ctx.send(msg_text, view=view)
        view.message = msg
        
        await view.wait()
        
        try:
            await msg.edit(view=None)
        except discord.NotFound:
            pass
        
        if view.confirmed:
            # Re-check balance just in case
            if user_conf.has_dinocoins < dinocoins_to_deduct:
                await ctx.send("Transaction failed: Insufficient funds (balance changed).")
                return
                
            user_conf.has_dinocoins -= dinocoins_to_deduct
            user_conf.has_spent_dinocoins += dinocoins_to_deduct
            user_conf.total_converted_dinocoin += dinocoins_to_deduct
            self.save()
            
            try:
                await bank.deposit_credits(ctx.author, currency_to_receive)
                await ctx.send(f"Successfully converted **{dinocoins_to_deduct}** DinoCoins into **{currency_to_receive} {currency_name}**!")
            except Exception as e:
                # Refund if bank fails
                user_conf.has_dinocoins += dinocoins_to_deduct
                user_conf.has_spent_dinocoins -= dinocoins_to_deduct
                user_conf.total_converted_dinocoin -= dinocoins_to_deduct
                self.save()
                await ctx.send(f"Transaction failed during bank deposit: {e}")
        else:
            await ctx.send("Conversion cancelled.")

    @commands.command()
    async def dcinvest(self, ctx: commands.Context, amount: int):
        """Convert server currency to DinoCoins.
        
        Usage:
        [p]dcinvest 500
        """
        conf = self.db.get_conf(ctx.guild)
        user_conf = conf.get_user(ctx.author)
        
        if not conf.discord_conversion_enabled:
            await ctx.send("Discord Currency Conversion is disabled.")
            return
            
        if amount <= 0:
            await ctx.send("Please enter a positive amount.")
            return
            
        rate = conf.discord_conversion_rate
        currency_name = await bank.get_currency_name(ctx.guild)
        
        try:
            user_balance = await bank.get_balance(ctx.author)
        except Exception as e:
            await ctx.send(f"Could not retrieve your balance: {e}")
            return
            
        if user_balance < amount:
            await ctx.send(f"You don't have enough {currency_name}! You have {user_balance}.")
            return
            
        # Calculate conversion: 1 discord currency = rate DinoCoins
        dinocoins_to_receive = amount * rate
        
        msg_text = (
            f"Are you sure you wish to invest **{amount} {currency_name}** for **{dinocoins_to_receive}** DinoCoins?"
        )
            
        view = ConfirmationView(ctx.author, timeout=180)
        msg = await ctx.send(msg_text, view=view)
        view.message = msg
        
        await view.wait()
        
        if view.confirmed:
            # Re-check balance just in case
            try:
                current_balance = await bank.get_balance(ctx.author)
            except Exception as e:
                await msg.edit(content=f"Transaction failed: Could not verify balance: {e}", view=None)
                return
                
            if current_balance < amount:
                await msg.edit(content="Transaction failed: Insufficient funds (balance changed).", view=None)
                return
                
            try:
                await bank.withdraw_credits(ctx.author, amount)
                user_conf.has_dinocoins += dinocoins_to_receive
                user_conf.total_dinocoins_earned += dinocoins_to_receive
                self.save()
                await msg.edit(content=f"Successfully invested **{amount} {currency_name}** for **{dinocoins_to_receive}** DinoCoins!", view=None)
            except Exception as e:
                await msg.edit(content=f"Transaction failed during bank withdrawal: {e}", view=None)
        else:
            await msg.edit(content="Investment cancelled.", view=None)
