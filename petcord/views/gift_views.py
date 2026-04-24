"""
Pet gift/transfer views for Petcord cog.
"""

from __future__ import annotations

import time
import discord
from discord.ui import View, Button
from typing import TYPE_CHECKING, Optional

from ..database.species import get_species
from ..database.appearance import get_rarity_emoji

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings, Pet


# 24 hours in seconds - minimum time before a received pet can be re-gifted
PET_TRANSFER_LOCKOUT_SECONDS = 24 * 60 * 60


class PetGiftView(View):
    """View for accepting or declining a pet gift."""
    
    def __init__(
        self, 
        cog: "Petcord", 
        sender: discord.Member,
        sender_data: "User",
        recipient: discord.Member,
        recipient_data: "User",
        guild_settings: "GuildSettings",
        pet: "Pet",
        pet_index: int,  # Index in sender's home_pets list
        timeout: float = 300  # 5 minutes to respond
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.sender = sender
        self.sender_data = sender_data
        self.recipient = recipient
        self.recipient_data = recipient_data
        self.guild_settings = guild_settings
        self.pet = pet
        self.pet_index = pet_index
        self.message: Optional[discord.Message] = None
        self.responded = False
        
        # Register with cog for cleanup on reload
        self.cog._active_views.add(self)
    
    def build_embed(self) -> discord.Embed:
        """Build the gift offer embed."""
        species = get_species(self.pet.species_id)
        species_name = species.name if species else self.pet.species_id.replace("_", " ").title()
        species_emoji = species.emoji if species else "🐾"
        
        # Rarity display
        rarity_display = {
            "common": "⭐ Common",
            "uncommon": "⭐⭐ Uncommon",
            "rare": "⭐⭐⭐ Rare",
            "very_rare": "⭐⭐⭐⭐ Very Rare",
            "legendary": "⭐⭐⭐⭐⭐ Legendary",
            "mythical": "🌟 Mythical"
        }
        
        embed = discord.Embed(
            title="🎁 You've Been Offered a Pet!",
            description=f"**{self.sender.display_name}** wants to gift you a pet from their Home!",
            color=discord.Color.purple()
        )
        
        # Pet info
        embed.add_field(
            name=f"{species_emoji} {self.pet.name}",
            value=f"**Species:** {species_name}\n"
                  f"**Rarity:** {rarity_display.get(self.pet.rarity, self.pet.rarity.title())}\n"
                  f"**Coat:** {self.pet.coat_color.replace('_', ' ').title()}\n"
                  f"**Pattern:** {self.pet.pattern.replace('_', ' ').title()}",
            inline=True
        )
        
        # Stats info
        embed.add_field(
            name="📊 Stats",
            value=f"**Age:** {int(self.pet.age_days)} days\n"
                  f"**Life Stage:** {self.pet.life_stage.title()}\n"
                  f"**Bond:** {self.pet.bond}",
            inline=True
        )
        
        # Special attributes
        special_attrs = []
        if self.pet.is_immortal:
            special_attrs.append("✨ Immortal")
        if self.pet.medal:
            medal_emoji = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(self.pet.medal, "🏅")
            special_attrs.append(f"{medal_emoji} {self.pet.medal.title()} Medal")
        
        if special_attrs:
            embed.add_field(
                name="🌟 Special",
                value="\n".join(special_attrs),
                inline=True
            )
        
        # Recipient's home capacity
        current_home = len(self.recipient_data.home_pets)
        max_capacity = self.recipient_data.effective_home_capacity
        embed.add_field(
            name="🏠 Your Home",
            value=f"**{current_home}/{max_capacity}** pets",
            inline=True
        )
        
        embed.add_field(
            name="─" * 20,
            value="Would you like to accept this pet into your Home?",
            inline=False
        )
        
        embed.set_footer(text="This offer expires in 5 minutes • You can only decline or accept once")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the recipient can use buttons."""
        if interaction.user.id != self.recipient.id:
            await interaction.response.send_message(
                "This gift offer is for someone else!",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        # Remove from active views
        self.cog._active_views.discard(self)
        
        if self.message:
            timeout_embed = discord.Embed(
                title="⏰ Gift Offer Expired",
                description=f"The gift offer from **{self.sender.display_name}** has expired.\n"
                           f"**{self.pet.name}** remains in their Home.",
                color=discord.Color.grey()
            )
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(embed=timeout_embed, view=self)
            except discord.HTTPException:
                pass
    
    @discord.ui.button(label="Accept Gift", style=discord.ButtonStyle.success, emoji="🎁")
    async def accept_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Accept the pet gift."""
        if self.responded:
            return
        self.responded = True
        
        # Double-check home capacity (in case it changed)
        if len(self.recipient_data.home_pets) >= self.recipient_data.effective_home_capacity:
            error_embed = discord.Embed(
                title="❌ Home is Full!",
                description="You don't have room in your Home for another pet.\n"
                           "Graduate more pets to unlock additional capacity!",
                color=discord.Color.red()
            )
            self.stop()
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=error_embed, view=self)
            self.cog._active_views.discard(self)
            return
        
        # Verify the pet is still in the sender's home at the expected index
        if self.pet_index >= len(self.sender_data.home_pets):
            error_embed = discord.Embed(
                title="❌ Pet No Longer Available",
                description="This pet is no longer in the sender's Home.",
                color=discord.Color.red()
            )
            self.stop()
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=error_embed, view=self)
            self.cog._active_views.discard(self)
            return
        
        # Additional verification - check by name in case list order changed
        sender_pet = None
        actual_index = -1
        for i, p in enumerate(self.sender_data.home_pets):
            if p.name == self.pet.name and p.species_id == self.pet.species_id:
                sender_pet = p
                actual_index = i
                break
        
        if sender_pet is None:
            error_embed = discord.Embed(
                title="❌ Pet No Longer Available",
                description=f"**{self.pet.name}** is no longer in {self.sender.display_name}'s Home.",
                color=discord.Color.red()
            )
            self.stop()
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(embed=error_embed, view=self)
            self.cog._active_views.discard(self)
            return
        
        # Remove pet from sender's home
        transferred_pet = self.sender_data.home_pets.pop(actual_index)
        
        # Track original owner if this is the first transfer
        if transferred_pet.original_owner_id is None:
            transferred_pet.original_owner_id = self.sender.id
        
        # Add sender to previous owners list
        if self.sender.id not in transferred_pet.previous_owners:
            transferred_pet.previous_owners.append(self.sender.id)
        
        # Update transfer timestamp (for 24h re-gift lockout)
        transferred_pet.last_transferred_timestamp = time.time()
        
        # Add pet to recipient's home
        self.recipient_data.home_pets.append(transferred_pet)
        
        # Update statistics
        self.sender_data.pets_gifted += 1
        self.sender_data.last_gift_sent_timestamp = time.time()
        self.recipient_data.pets_received += 1
        
        # Save changes
        self.cog.schedule_save()
        
        # Build success embed
        success_embed = discord.Embed(
            title="🎁 Gift Accepted!",
            description=f"**{transferred_pet.name}** has moved to **{self.recipient.display_name}**'s Home!",
            color=discord.Color.green()
        )
        
        success_embed.add_field(
            name="📤 From",
            value=f"{self.sender.mention}\n"
                  f"Pets gifted: {self.sender_data.pets_gifted}",
            inline=True
        )
        
        success_embed.add_field(
            name="📥 To",
            value=f"{self.recipient.mention}\n"
                  f"Pets received: {self.recipient_data.pets_received}",
            inline=True
        )
        
        if transferred_pet.is_immortal:
            success_embed.add_field(
                name="✨ Note",
                value=f"**{transferred_pet.name}** is immortal and will stay that way!",
                inline=False
            )
        
        success_embed.set_footer(text="The pet retains its medal but the medal doesn't transfer to your stats")
        
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=success_embed, view=self)
        self.cog._active_views.discard(self)
    
    @discord.ui.button(label="Decline", style=discord.ButtonStyle.secondary, emoji="❌")
    async def decline_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Decline the pet gift."""
        if self.responded:
            return
        self.responded = True
        
        decline_embed = discord.Embed(
            title="❌ Gift Declined",
            description=f"You declined the gift of **{self.pet.name}**.\n"
                       f"The pet remains in **{self.sender.display_name}**'s Home.",
            color=discord.Color.grey()
        )
        
        self.stop()
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(embed=decline_embed, view=self)
        self.cog._active_views.discard(self)
