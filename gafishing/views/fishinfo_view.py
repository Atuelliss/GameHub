"""
FishInfo View - View for displaying user fishing profile with currency conversion options.
"""

import discord
from typing import TYPE_CHECKING, Optional
from redbot.core import bank

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView


class FishInfoView(BaseView):
    """View for fishinfo command with optional currency conversion buttons."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        target: discord.Member,
        embed: discord.Embed
    ):
        super().__init__(cog=cog, author=author)
        self.target = target
        self.original_embed = embed
        
        # Check if conversion is enabled and target is self
        conf = self.cog.db.get_conf(author.guild)
        
        # Only show conversion buttons if targeting yourself and conversion is enabled
        if conf.discord_currency_conversion_enabled and target.id == author.id:
            # Add conversion buttons dynamically
            self._add_conversion_buttons()
        
        # Add close button
        close_btn = discord.ui.Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=1
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
    
    def _add_conversion_buttons(self):
        """Add the currency conversion buttons."""
        # Convert FP button
        fp_btn = discord.ui.Button(
            label="Convert FP",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            row=0
        )
        fp_btn.callback = self._convert_fp_callback
        self.add_item(fp_btn)
        
        # Convert Discord Currency button (label set dynamically)
        currency_btn = discord.ui.Button(
            label="Convert Currency",  # Will be updated with actual currency name
            emoji="💰",
            style=discord.ButtonStyle.primary,
            row=0,
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
