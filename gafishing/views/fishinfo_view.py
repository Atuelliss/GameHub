"""
FishInfo View - View for displaying user fishing profile with currency conversion options.
"""

import discord
from typing import TYPE_CHECKING, Optional
from redbot.core import bank

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView
from ..databases.fish import FISH_DATABASE


class FishInfoView(BaseView):
    """View for fishinfo command with optional currency conversion buttons."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        target: discord.Member,
        embed: discord.Embed,
        prefix: str = "!"
    ):
        super().__init__(cog=cog, author=author)
        self.target = target
        self.original_embed = embed
        self.prefix = prefix
        
        # Check if conversion is enabled and target is self
        conf = self.cog.db.get_conf(author.guild)
        conversion_enabled = conf.discord_currency_conversion_enabled and target.id == author.id
        
        # Add Help button (Row 0)
        help_btn = discord.ui.Button(
            label="Help",
            emoji="❓",
            style=discord.ButtonStyle.primary,
            row=0
        )
        help_btn.callback = self._help_callback
        self.add_item(help_btn)
        
        # Add close button (Row 0)
        close_btn = discord.ui.Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
        
        # Only show conversion buttons if targeting yourself and conversion is enabled
        if conversion_enabled:
            # Add conversion buttons dynamically (Row 1 to not interfere with Help/Close)
            self._add_conversion_buttons()
    
    async def _help_callback(self, interaction: discord.Interaction):
        """Open the help menu."""
        help_view = FishInfoHelpView(
            cog=self.cog,
            author=self.author,
            parent_view=self,
            original_embed=self.original_embed,
            prefix=self.prefix
        )
        embed = help_view.get_main_help_embed()
        await interaction.response.edit_message(embed=embed, view=help_view)
    
    def _add_conversion_buttons(self):
        """Add the currency conversion buttons (Row 1)."""
        # Convert FP button
        fp_btn = discord.ui.Button(
            label="Convert FP",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            row=1
        )
        fp_btn.callback = self._convert_fp_callback
        self.add_item(fp_btn)
        
        # Convert Discord Currency button (label set dynamically)
        currency_btn = discord.ui.Button(
            label="Convert Currency",  # Will be updated with actual currency name
            emoji="💰",
            style=discord.ButtonStyle.primary,
            row=1,
            custom_id="convert_currency"
        )
        currency_btn.callback = self._convert_currency_callback
        self.add_item(currency_btn)
    
    async def _close_callback(self, interaction: discord.Interaction):
        """Close the view."""
        self.stop()
        await interaction.response.edit_message(view=None)
    
    async def _convert_fp_callback(self, interaction: discord.Interaction):
        """Handle converting FishPoints to Discord currency."""
        conf = self.cog.db.get_conf(interaction.guild)
        currency_name = await bank.get_currency_name(interaction.guild)
        
        modal = ConvertFPModal(
            cog=self.cog,
            author=self.author,
            target=self.target,
            original_embed=self.original_embed,
            parent_view=self,
            currency_name=currency_name,
            conversion_rate=conf.discord_currency_conversion_rate
        )
        await interaction.response.send_modal(modal)
    
    async def _convert_currency_callback(self, interaction: discord.Interaction):
        """Handle converting Discord currency to FishPoints."""
        conf = self.cog.db.get_conf(interaction.guild)
        currency_name = await bank.get_currency_name(interaction.guild)
        
        modal = ConvertCurrencyModal(
            cog=self.cog,
            author=self.author,
            target=self.target,
            original_embed=self.original_embed,
            parent_view=self,
            currency_name=currency_name,
            conversion_rate=conf.discord_currency_conversion_rate
        )
        await interaction.response.send_modal(modal)


class ConvertFPModal(discord.ui.Modal):
    """Modal for converting FishPoints to Discord currency."""
    
    def __init__(
        self,
        cog: "GreenacresFishing",
        author: discord.Member,
        target: discord.Member,
        original_embed: discord.Embed,
        parent_view: FishInfoView,
        currency_name: str,
        conversion_rate: int
    ):
        super().__init__(title=f"Convert FP → {currency_name}")
        self.cog = cog
        self.author = author
        self.target = target
        self.original_embed = original_embed
        self.parent_view = parent_view
        self.currency_name = currency_name
        self.conversion_rate = conversion_rate
        
        # Create TextInput with dynamic placeholder
        self.amount_input = discord.ui.TextInput(
            label="Amount of FishPoints to convert",
            placeholder=f"Rate: {conversion_rate} FP = 1 {currency_name}",
            min_length=1,
            max_length=10
        )
        self.add_item(self.amount_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
            if amount < 1:
                raise ValueError("Amount must be at least 1")
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid positive number.",
                ephemeral=True
            )
            return
        
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        # Check if user has enough FP
        if user_data.total_fishpoints < amount:
            await interaction.response.send_message(
                f"❌ You don't have enough FishPoints! You have **{user_data.total_fishpoints:,}** FP.",
                ephemeral=True
            )
            return
        
        # Check if amount is less than conversion rate
        if amount < self.conversion_rate:
            await interaction.response.send_message(
                f"❌ You need at least **{self.conversion_rate:,}** FP to convert (Rate: {self.conversion_rate} FP = 1 {self.currency_name}).",
                ephemeral=True
            )
            return
        
        # Calculate conversion
        currency_to_receive = amount // self.conversion_rate
        fp_to_deduct = currency_to_receive * self.conversion_rate
        
        # Check if amount doesn't divide evenly
        if fp_to_deduct != amount:
            # Show confirmation view
            confirm_view = ConvertConfirmView(
                cog=self.cog,
                author=self.author,
                target=self.target,
                original_embed=self.original_embed,
                parent_view=self.parent_view,
                conversion_type="fp_to_currency",
                amount_to_deduct=fp_to_deduct,
                amount_to_receive=currency_to_receive,
                currency_name=self.currency_name,
                conversion_rate=self.conversion_rate
            )
            
            await interaction.response.send_message(
                f"⚠️ You can only convert **{fp_to_deduct:,}** FP (not {amount:,}).\n"
                f"This will give you **{currency_to_receive:,}** {self.currency_name}.\n\n"
                f"Do you wish to continue?",
                view=confirm_view,
                ephemeral=True
            )
        else:
            # Exact amount - process directly
            await self._process_fp_conversion(interaction, user_data, fp_to_deduct, currency_to_receive)
    
    async def _process_fp_conversion(
        self, 
        interaction: discord.Interaction, 
        user_data, 
        fp_to_deduct: int, 
        currency_to_receive: int
    ):
        """Process the FP to currency conversion."""
        # Deduct FP
        user_data.total_fishpoints -= fp_to_deduct
        self.cog.save()
        
        try:
            # Add Discord currency
            await bank.deposit_credits(self.author, currency_to_receive)
            
            # Acknowledge the modal
            await interaction.response.defer()
            
            # Send success message to channel (not ephemeral)
            await interaction.channel.send(
                f"💱 {self.author.mention} converted **{fp_to_deduct:,}** FishPoints into **{currency_to_receive:,}** {self.currency_name}!"
            )
        except Exception as e:
            # Rollback if bank fails
            user_data.total_fishpoints += fp_to_deduct
            self.cog.save()
            
            await interaction.response.send_message(
                f"❌ Transaction failed: {e}",
                ephemeral=True
            )


class ConvertCurrencyModal(discord.ui.Modal):
    """Modal for converting Discord currency to FishPoints."""
    
    def __init__(
        self,
        cog: "GreenacresFishing",
        author: discord.Member,
        target: discord.Member,
        original_embed: discord.Embed,
        parent_view: FishInfoView,
        currency_name: str,
        conversion_rate: int
    ):
        super().__init__(title=f"Convert {currency_name} → FP")
        self.cog = cog
        self.author = author
        self.target = target
        self.original_embed = original_embed
        self.parent_view = parent_view
        self.currency_name = currency_name
        self.conversion_rate = conversion_rate
        
        # Create TextInput with dynamic label and placeholder
        self.amount_input = discord.ui.TextInput(
            label=f"Amount of {currency_name} to convert",
            placeholder=f"Rate: 1 {currency_name} = {conversion_rate} FP",
            min_length=1,
            max_length=10
        )
        self.add_item(self.amount_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            amount = int(self.amount_input.value)
            if amount < 1:
                raise ValueError("Amount must be at least 1")
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid positive number.",
                ephemeral=True
            )
            return
        
        # Check if user has enough Discord currency
        try:
            user_balance = await bank.get_balance(self.author)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Could not retrieve your balance: {e}",
                ephemeral=True
            )
            return
        
        if user_balance < amount:
            await interaction.response.send_message(
                f"❌ You don't have enough {self.currency_name}! You have **{user_balance:,}**.",
                ephemeral=True
            )
            return
        
        # Calculate conversion: 1 Discord currency = conversion_rate FP
        fp_to_receive = amount * self.conversion_rate
        
        # Show confirmation
        confirm_view = ConvertConfirmView(
            cog=self.cog,
            author=self.author,
            target=self.target,
            original_embed=self.original_embed,
            parent_view=self.parent_view,
            conversion_type="currency_to_fp",
            amount_to_deduct=amount,
            amount_to_receive=fp_to_receive,
            currency_name=self.currency_name,
            conversion_rate=self.conversion_rate
        )
        
        await interaction.response.send_message(
            f"💱 Convert **{amount:,}** {self.currency_name} into **{fp_to_receive:,}** FishPoints?\n\n"
            f"(Rate: 1 {self.currency_name} = {self.conversion_rate} FP)",
            view=confirm_view,
            ephemeral=True
        )


class ConvertConfirmView(discord.ui.View):
    """View for confirming currency conversion."""
    
    def __init__(
        self,
        cog: "GreenacresFishing",
        author: discord.Member,
        target: discord.Member,
        original_embed: discord.Embed,
        parent_view: FishInfoView,
        conversion_type: str,  # "fp_to_currency" or "currency_to_fp"
        amount_to_deduct: int,
        amount_to_receive: int,
        currency_name: str,
        conversion_rate: int
    ):
        super().__init__(timeout=60.0)
        self.cog = cog
        self.author = author
        self.target = target
        self.original_embed = original_embed
        self.parent_view = parent_view
        self.conversion_type = conversion_type
        self.amount_to_deduct = amount_to_deduct
        self.amount_to_receive = amount_to_receive
        self.currency_name = currency_name
        self.conversion_rate = conversion_rate
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original author can interact."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "This isn't your conversion!",
                ephemeral=True
            )
            return False
        return True
    
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the conversion."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        if self.conversion_type == "fp_to_currency":
            # Re-check FP balance
            if user_data.total_fishpoints < self.amount_to_deduct:
                await interaction.response.edit_message(
                    content="❌ Transaction failed: Insufficient FishPoints (balance changed).",
                    view=None
                )
                return
            
            # Deduct FP
            user_data.total_fishpoints -= self.amount_to_deduct
            self.cog.save()
            
            try:
                # Add Discord currency
                await bank.deposit_credits(self.author, self.amount_to_receive)
                
                # Edit the ephemeral confirmation message
                await interaction.response.edit_message(
                    content="✅ Conversion complete!",
                    view=None
                )
                
                # Send success message to channel (not ephemeral)
                await interaction.channel.send(
                    f"💱 {self.author.mention} converted **{self.amount_to_deduct:,}** FishPoints into **{self.amount_to_receive:,}** {self.currency_name}!"
                )
            except Exception as e:
                # Rollback if bank fails
                user_data.total_fishpoints += self.amount_to_deduct
                self.cog.save()
                
                await interaction.response.edit_message(
                    content=f"❌ Transaction failed: {e}",
                    view=None
                )
        
        elif self.conversion_type == "currency_to_fp":
            # Re-check Discord currency balance
            try:
                current_balance = await bank.get_balance(self.author)
            except Exception as e:
                await interaction.response.edit_message(
                    content=f"❌ Transaction failed: Could not verify balance: {e}",
                    view=None
                )
                return
            
            if current_balance < self.amount_to_deduct:
                await interaction.response.edit_message(
                    content=f"❌ Transaction failed: Insufficient {self.currency_name} (balance changed).",
                    view=None
                )
                return
            
            try:
                # Withdraw Discord currency
                await bank.withdraw_credits(self.author, self.amount_to_deduct)
                
                # Add FP
                user_data.total_fishpoints += self.amount_to_receive
                
                # Update most FP ever if needed
                if user_data.total_fishpoints > user_data.most_fishpoints_ever:
                    user_data.most_fishpoints_ever = user_data.total_fishpoints
                
                self.cog.save()
                
                # Edit the ephemeral confirmation message
                await interaction.response.edit_message(
                    content="✅ Conversion complete!",
                    view=None
                )
                
                # Send success message to channel (not ephemeral)
                await interaction.channel.send(
                    f"💱 {self.author.mention} converted **{self.amount_to_deduct:,}** {self.currency_name} into **{self.amount_to_receive:,}** FishPoints!"
                )
            except Exception as e:
                await interaction.response.edit_message(
                    content=f"❌ Transaction failed: {e}",
                    view=None
                )
        
        self.stop()
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the conversion."""
        await interaction.response.edit_message(
            content="Conversion cancelled.",
            view=None
        )
        self.stop()
    
    async def on_timeout(self):
        """Handle timeout."""
        # View will just expire, ephemeral message will remain
        pass


class FishInfoHelpView(BaseView):
    """Help view for fishinfo command with multiple information pages."""
    
    def __init__(
        self,
        cog: "GreenacresFishing",
        author: discord.Member,
        parent_view: FishInfoView,
        original_embed: discord.Embed,
        prefix: str = "!"
    ):
        super().__init__(cog=cog, author=author)
        self.parent_view = parent_view
        self.original_embed = original_embed
        self.prefix = prefix
        self.current_page = "main"
        self.fish_list_page = 0  # For pagination
        
        # Build fish list once
        self._build_fish_lists()
        
        # Set up main menu buttons
        self._setup_main_buttons()
    
    def _build_fish_lists(self):
        """Build categorized fish lists for display."""
        self.freshwater_fish = []
        self.saltwater_fish = []
        self.hybrid_fish = []
        
        for fish_id, fish_data in sorted(FISH_DATABASE.items(), key=lambda x: x[1]["name"]):
            fish_name = fish_data["name"]
            water_type = fish_data["water_type"]
            
            if water_type == "freshwater":
                self.freshwater_fish.append(fish_name)
            elif water_type == "saltwater":
                self.saltwater_fish.append(fish_name)
            elif water_type == "both":
                self.hybrid_fish.append(fish_name)
        
        # Calculate total pages needed (15 fish per page)
        self.fish_per_page = 15
        all_fish = self.freshwater_fish + self.hybrid_fish + self.saltwater_fish
        self.total_fish_pages = max(1, (len(all_fish) + self.fish_per_page - 1) // self.fish_per_page)
    
    def get_main_help_embed(self) -> discord.Embed:
        """Generate the main help menu embed."""
        embed = discord.Embed(
            title="🎣 Greenacres Fishing Info",
            description=(
                "This game is a simulated real-time fishing system with reactive fish-fighting and dynamic leaderboards.\n"
                "• It stores and tracks the real-world timezone/hemisphere of the Server (once set by the Server Owner)\n"
                "• It uses that to track the current season for in-game situations (some fish are less active in off seasons)\n"
                "• It has a day/night cycle (2 in-game days to 1 real-day) and an active weather environment that changes each hour that can impact fish activity"
            ),
            color=discord.Color.blue()
        )
        embed.set_footer(text="Select a topic to learn more")
        return embed
    
    def get_getting_started_embed(self) -> discord.Embed:
        """Generate the Getting Started embed."""
        embed = discord.Embed(
            title="🎯 Getting Started with Fishing",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="Choosing a Location",
            value=(
                f"Use `{self.prefix}fish` to see all available fishing locations. Each location has different fish "
                "and water types (freshwater/saltwater) and might require specific gear."
            ),
            inline=False
        )
        
        embed.add_field(
            name="Casting Your Line",
            value=(
                "Once at a location, select your bait/lure and click \"Cast Line\" to begin fishing!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="The Interactive Fishing Process",
            value=(
                "• Wait for a fish to bite (you'll get a notification)\n"
                "• Click \"Reel In\" when prompted (or if nothing is happening/fish wanders off)\n"
                "• Watch the tension meter - keep it in the safe zone (Avoid RED)!\n"
                "• Click \"Reel\" to pull the fish in but don't spam the button. They fight harder the closer they get\n"
                "• Successfully land the fish to add it to your catch!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Different baits attract different fish\n"
                "• Weather and season affect what fish appear\n"
                "• Better rods help land bigger fish!\n"
                "• Notice - Rods can be damaged by mistakes during fish-fighting. Be careful or you may have to replace them"
            ),
            inline=False
        )
        
        return embed
    
    def get_bait_shop_embed(self) -> discord.Embed:
        """Generate the Bait Shop Info embed."""
        embed = discord.Embed(
            title="🏪 Bait Shop Information",
            description="The Bait Shop is your one-stop shop for all your fishing needs!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Purchasing Items",
            value=(
                "• Browse available bait, lures, and fishing gear in the shop\n"
                "• Use your FishPoints (FP) to buy items\n"
                "• Better equipment helps you catch bigger and rarer fish"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Selling Your Catch",
            value=(
                "• Navigate to the \"Sell Fish\" section\n"
                "• Select individual fish or sell in bulk\n"
                "• Earn FishPoints based on:\n"
                "  - Fish species and rarity\n"
                "  - Weight and length of the catch\n"
                "  - Current market conditions"
            ),
            inline=False
        )
        
        embed.add_field(
            name="FishMaster Outfit",
            value=(
                "• The ultimate fishing gear set available only in the Bait Shop\n"
                "• Purchased with FP but requires a FishMaster Token to unlock\n"
                "• Provides the best bonuses in the game"
            ),
            inline=False
        )
        
        return embed
    
    def get_fishpoints_tokens_embed(self) -> discord.Embed:
        """Generate the FishPoints/Tokens info embed."""
        embed = discord.Embed(
            title="💰 FishPoints & FishMaster Tokens",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="FishPoints (FP)",
            value=(
                "• Earned by selling fish at the Bait Shop\n"
                "• Used to purchase bait, lures, and fishing equipment\n"
                "• Can be converted to Discord server currency (if enabled by server owner)\n"
                "• Larger/rarer fish = more FishPoints!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Discord Currency Conversion",
            value=(
                "• Convert FishPoints → Server Currency\n"
                "• Convert Server Currency → FishPoints\n"
                "• Conversion rate set by server owner\n"
                "• Access via your fishinfo profile"
            ),
            inline=False
        )
        
        embed.add_field(
            name="FishMaster Tokens 🏆",
            value=(
                "• Prestigious tokens earned by breaking records!\n"
                "• Awarded when you catch:\n"
                "  - The HEAVIEST specimen of a fish species\n"
                "  - The LONGEST specimen of a fish species\n"
                "• Required to purchase the FishMaster Outfit\n"
                "• The FishMaster Outfit is the best gear in the game!\n"
                "• Tokens cannot be traded or converted"
            ),
            inline=False
        )
        
        return embed
    
    def get_search_garbage_embed(self) -> discord.Embed:
        """Generate the Search Garbage info embed."""
        embed = discord.Embed(
            title="🗑️ Searching Garbage for Supplies",
            description="Sometimes fortune favors the resourceful! Search through garbage to find free fishing supplies.",
            color=discord.Color.greyple()
        )
        
        embed.add_field(
            name="How It Works",
            value=(
                "• Find random bait, lures, or other useful items\n"
                "• There's a cooldown between searches\n"
                "• Not all searches are successful - sometimes you find nothing!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="What You Might Find",
            value=(
                "• Basic bait (worms, breadballs)\n"
                "• Damaged lures (still usable!)\n"
                "• Occasionally rare items\n"
                "• Junk (trash items with no value)"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Search regularly to build up a free bait stockpile\n"
                "• Great for beginners who are low on FishPoints\n"
                "• Don't rely solely on garbage - buy quality gear for better results!"
            ),
            inline=False
        )
        
        return embed
    
    def get_fish_list_embed(self, page: int = 0) -> discord.Embed:
        """Generate the Fish List embed with pagination."""
        # Combine all fish into one list for pagination
        all_fish = []
        
        # Add freshwater fish with their type
        for fish in self.freshwater_fish:
            all_fish.append((fish, "Freshwater 🌊"))
        
        # Add hybrid fish
        for fish in self.hybrid_fish:
            all_fish.append((fish, "Freshwater/Saltwater 🌊🌊"))
        
        # Add saltwater fish
        for fish in self.saltwater_fish:
            all_fish.append((fish, "Saltwater 🌊"))
        
        # Calculate page boundaries
        start_idx = page * self.fish_per_page
        end_idx = min(start_idx + self.fish_per_page, len(all_fish))
        page_fish = all_fish[start_idx:end_idx]
        
        embed = discord.Embed(
            title="🐟 Complete Fish Database",
            description=f"Page {page + 1} of {self.total_fish_pages}",
            color=discord.Color.teal()
        )
        
        # Group by water type for display
        current_type = None
        fish_list = []
        
        for fish_name, water_type in page_fish:
            if water_type != current_type:
                if fish_list:
                    # Add previous group
                    embed.add_field(
                        name=f"**{current_type}**",
                        value="\n".join(fish_list),
                        inline=False
                    )
                    fish_list = []
                current_type = water_type
            fish_list.append(f"• {fish_name}")
        
        # Add last group
        if fish_list:
            embed.add_field(
                name=f"**{current_type}**",
                value="\n".join(fish_list),
                inline=False
            )
        
        # Add totals at the bottom
        total_count = len(FISH_DATABASE)
        embed.set_footer(
            text=f"Total Species: {total_count} ({len(self.freshwater_fish)} Freshwater, "
                 f"{len(self.hybrid_fish)} Hybrid, {len(self.saltwater_fish)} Saltwater)"
        )
        
        return embed
    
    def _setup_main_buttons(self):
        """Set up buttons for main help menu."""
        self.clear_items()
        
        # Row 0
        getting_started_btn = discord.ui.Button(
            label="Getting Started",
            emoji="🎯",
            style=discord.ButtonStyle.primary,
            row=0
        )
        getting_started_btn.callback = self._getting_started_callback
        self.add_item(getting_started_btn)
        
        bait_shop_btn = discord.ui.Button(
            label="Bait Shop Info",
            emoji="🏪",
            style=discord.ButtonStyle.primary,
            row=0
        )
        bait_shop_btn.callback = self._bait_shop_callback
        self.add_item(bait_shop_btn)
        
        # Row 1
        fishpoints_btn = discord.ui.Button(
            label="FishPoints/Tokens",
            emoji="💰",
            style=discord.ButtonStyle.primary,
            row=1
        )
        fishpoints_btn.callback = self._fishpoints_callback
        self.add_item(fishpoints_btn)
        
        garbage_btn = discord.ui.Button(
            label="Search Garbage?",
            emoji="🗑️",
            style=discord.ButtonStyle.primary,
            row=1
        )
        garbage_btn.callback = self._garbage_callback
        self.add_item(garbage_btn)
        
        # Row 2
        fish_list_btn = discord.ui.Button(
            label="Fish List",
            emoji="🐟",
            style=discord.ButtonStyle.primary,
            row=2
        )
        fish_list_btn.callback = self._fish_list_callback
        self.add_item(fish_list_btn)
        
        # Row 3 - Navigation
        back_btn = discord.ui.Button(
            label="Back",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=3
        )
        back_btn.callback = self._back_to_fishinfo_callback
        self.add_item(back_btn)
        
        close_btn = discord.ui.Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=3
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
    
    def _setup_sub_buttons(self, include_pagination: bool = False):
        """Set up buttons for sub-pages."""
        self.clear_items()
        
        if include_pagination:
            # Add pagination buttons
            prev_btn = discord.ui.Button(
                label="Previous",
                emoji="◀️",
                style=discord.ButtonStyle.primary,
                row=0,
                disabled=(self.fish_list_page == 0)
            )
            prev_btn.callback = self._fish_list_prev_callback
            self.add_item(prev_btn)
            
            next_btn = discord.ui.Button(
                label="Next",
                emoji="▶️",
                style=discord.ButtonStyle.primary,
                row=0,
                disabled=(self.fish_list_page >= self.total_fish_pages - 1)
            )
            next_btn.callback = self._fish_list_next_callback
            self.add_item(next_btn)
            
            # Back and close on row 1
            back_row = 1
        else:
            # Back and close on row 0
            back_row = 0
        
        back_btn = discord.ui.Button(
            label="Back",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=back_row
        )
        back_btn.callback = self._back_to_help_main_callback
        self.add_item(back_btn)
        
        close_btn = discord.ui.Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=back_row
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
    
    # Button callbacks
    async def _getting_started_callback(self, interaction: discord.Interaction):
        """Show Getting Started page."""
        self.current_page = "getting_started"
        embed = self.get_getting_started_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _bait_shop_callback(self, interaction: discord.Interaction):
        """Show Bait Shop Info page."""
        self.current_page = "bait_shop"
        embed = self.get_bait_shop_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _fishpoints_callback(self, interaction: discord.Interaction):
        """Show FishPoints/Tokens page."""
        self.current_page = "fishpoints"
        embed = self.get_fishpoints_tokens_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _garbage_callback(self, interaction: discord.Interaction):
        """Show Search Garbage page."""
        self.current_page = "garbage"
        embed = self.get_search_garbage_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _fish_list_callback(self, interaction: discord.Interaction):
        """Show Fish List page."""
        self.current_page = "fish_list"
        self.fish_list_page = 0
        embed = self.get_fish_list_embed(self.fish_list_page)
        self._setup_sub_buttons(include_pagination=True)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _fish_list_prev_callback(self, interaction: discord.Interaction):
        """Go to previous page of fish list."""
        if self.fish_list_page > 0:
            self.fish_list_page -= 1
            embed = self.get_fish_list_embed(self.fish_list_page)
            self._setup_sub_buttons(include_pagination=True)
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def _fish_list_next_callback(self, interaction: discord.Interaction):
        """Go to next page of fish list."""
        if self.fish_list_page < self.total_fish_pages - 1:
            self.fish_list_page += 1
            embed = self.get_fish_list_embed(self.fish_list_page)
            self._setup_sub_buttons(include_pagination=True)
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def _back_to_help_main_callback(self, interaction: discord.Interaction):
        """Go back to main help menu."""
        self.current_page = "main"
        self.fish_list_page = 0
        embed = self.get_main_help_embed()
        self._setup_main_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _back_to_fishinfo_callback(self, interaction: discord.Interaction):
        """Go back to original fishinfo embed."""
        await interaction.response.edit_message(embed=self.original_embed, view=self.parent_view)
        self.stop()
    
    async def _close_callback(self, interaction: discord.Interaction):
        """Close the view."""
        self.stop()
        await interaction.response.edit_message(view=None)
