"""
Inventory view - View and manage your fishing gear and catches.
"""

import discord
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView, BackToMenuMixin, MainMenuView
from ..databases.items import RODS_DATABASE, LURES_DATABASE, HATS_DATABASE, COATS_DATABASE, BOOTS_DATABASE

# Combined clothing lookup
CLOTHING_DATABASE = {**HATS_DATABASE, **COATS_DATABASE, **BOOTS_DATABASE}


class InventoryView(BackToMenuMixin, BaseView):
    """View for the player's inventory."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        category: str = "overview"
    ):
        super().__init__(cog=cog, author=author)
        self.category = category
    
    async def create_inventory_embed(self) -> discord.Embed:
        """Create the inventory embed based on current category."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        if self.category == "rods":
            return await self._create_rods_embed(user_data)
        elif self.category == "lures":
            return await self._create_lures_embed(user_data)
        elif self.category == "clothing":
            return await self._create_clothing_embed(user_data)
        elif self.category == "fish":
            return await self._create_fish_embed(user_data)
        else:
            return await self._create_overview_embed(user_data)
    
    async def _create_overview_embed(self, user_data) -> discord.Embed:
        """Create the main inventory overview embed."""
        embed = discord.Embed(
            title="🎒 Your Inventory",
            description="View your fishing gear and catches!",
            color=discord.Color.blue()
        )
        
        # Count items in each category
        rod_count = len(user_data.current_rod_inventory)
        lure_count = sum(item.get("quantity", 1) for item in user_data.current_lure_inventory)
        clothing_count = len(user_data.current_clothing_inventory)
        fish_count = len(user_data.current_fish_inventory)
        
        embed.add_field(
            name="� Gear & Catches",
            value=(
                f"🎣 Rods: **{rod_count}**\n"
                f"🪝 Lures/Bait: **{lure_count}**\n"
                f"👕 Clothing: **{clothing_count}**\n"
                f"🐟 Fish: **{fish_count}**"
            ),
            inline=True
        )
        
        embed.add_field(
            name="💰 Currency",
            value=(
                f"FishPoints: **{user_data.total_fishpoints:,}**\n"
                f"🏆 Tokens: **{user_data.current_fishmaster_tokens}**"
            ),
            inline=True
        )
        
        embed.set_footer(text="Select a category to view details!")
        
        return embed
    
    async def _create_rods_embed(self, user_data) -> discord.Embed:
        """Create the rods inventory embed."""
        embed = discord.Embed(
            title="🎣 Your Rods",
            color=discord.Color.blue()
        )
        
        if not user_data.current_rod_inventory:
            embed.description = "You don't have any rods! Visit the Bait Shop to buy one."
        else:
            rod_lines = []
            for idx, rod in enumerate(user_data.current_rod_inventory):
                rod_id = rod.get("rod_id")
                durability = rod.get("durability", 0)
                rod_info = RODS_DATABASE.get(rod_id, {})
                name = rod_info.get("name", rod_id)
                max_durability = rod_info.get("durability", 100)
                is_equipped = user_data.equipped_rod_index == idx
                equipped = " ✅ *Equipped*" if is_equipped else ""
                rod_lines.append(f"**{name}** - {durability}/{max_durability} durability{equipped}")
            
            embed.description = "\n".join(rod_lines)
        
        embed.set_footer(text="Use the buttons below to navigate.")
        return embed
    
    async def _create_lures_embed(self, user_data) -> discord.Embed:
        """Create the lures/bait inventory embed."""
        embed = discord.Embed(
            title="🪝 Your Lures & Bait",
            color=discord.Color.orange()
        )
        
        if not user_data.current_lure_inventory:
            embed.description = "You don't have any lures or bait! Visit the Bait Shop to stock up."
        else:
            from ..commands.helper_functions import ensure_lure_uses
            lure_lines = []
            for idx, lure in enumerate(user_data.current_lure_inventory):
                lure_id = lure.get("lure_id")
                
                # Ensure uses tracking
                ensure_lure_uses(lure)
                
                remaining_uses = lure.get("remaining_uses", 0)
                uses_per_item = lure.get("uses_per_item", 1)
                max_uses = lure.get("quantity", 0) * uses_per_item
                
                lure_info = LURES_DATABASE.get(lure_id, {})
                name = lure_info.get("name", lure_id)
                is_equipped = user_data.equipped_lure_index == idx
                equipped = " ✅ *Equipped*" if is_equipped else ""
                lure_lines.append(f"**{name}** ({remaining_uses}/{max_uses} uses){equipped}")
            
            embed.description = "\n".join(lure_lines)
        
        embed.set_footer(text="Lures are consumed when fishing.")
        return embed
    
    async def _create_clothing_embed(self, user_data) -> discord.Embed:
        """Create the clothing inventory embed."""
        embed = discord.Embed(
            title="👕 Your Clothing",
            color=discord.Color.purple()
        )
        
        if not user_data.current_clothing_inventory:
            embed.description = "You don't have any special clothing! Visit the Bait Shop to browse outfits."
        else:
            clothing_lines = []
            for idx, item in enumerate(user_data.current_clothing_inventory):
                item_id = item.get("clothing_id")
                item_info = CLOTHING_DATABASE.get(item_id, {})
                name = item_info.get("name", item_id)
                slot = item.get("slot", item_info.get("slot", "unknown"))
                # Check if this item is equipped based on its slot
                is_equipped = False
                if slot == "hat" and user_data.equipped_hat_index == idx:
                    is_equipped = True
                elif slot == "coat" and user_data.equipped_coat_index == idx:
                    is_equipped = True
                elif slot == "boots" and user_data.equipped_boots_index == idx:
                    is_equipped = True
                equipped = " ✅ *Equipped*" if is_equipped else ""
                clothing_lines.append(f"**{name}** ({slot}){equipped}")
            
            embed.description = "\n".join(clothing_lines)
        
        embed.set_footer(text="Clothing provides special bonuses while fishing!")
        return embed
    
    async def _create_fish_embed(self, user_data) -> discord.Embed:
        """Create the fish inventory embed."""
        embed = discord.Embed(
            title="🐟 Your Caught Fish",
            color=discord.Color.teal()
        )
        
        if not user_data.current_fish_inventory:
            embed.description = "You haven't caught any fish yet! Go fishing to fill your bucket."
        else:
            # Show individual fish with length and weight
            fish_lines = []
            for fish in user_data.current_fish_inventory:
                fish_id = fish.get("fish_id", "unknown")
                display_name = fish_id.replace("_", " ").title()
                
                # Get length and weight
                weight_oz = fish.get("weight_oz", 0)
                length_in = fish.get("length_inches", 0)
                
                # Format weight
                if weight_oz >= 16:
                    weight_display = f"{weight_oz / 16:.1f} lbs"
                else:
                    weight_display = f"{weight_oz:.1f} oz"
                
                # Format length
                length_display = f"{length_in:.1f}\""
                
                # Trophy indicator
                trophy = "🏆 " if fish.get("is_trophy", False) else ""
                
                fish_lines.append(f"{trophy}**{display_name}** • {length_display} • {weight_display}")
            
            # Limit display to avoid embed limits
            if len(fish_lines) > 15:
                embed.description = "\n".join(fish_lines[:15])
                embed.description += f"\n\n*...and {len(fish_lines) - 15} more fish*"
            else:
                embed.description = "\n".join(fish_lines) if fish_lines else "No fish in inventory."
            
            # Summary
            embed.add_field(
                name="📊 Summary",
                value=f"Total fish: **{len(user_data.current_fish_inventory)}**",
                inline=False
            )
        
        embed.set_footer(text="Sell your fish at the Bait Shop!")
        return embed
    
    async def _update_view(self, interaction: discord.Interaction, category: str):
        """Update the view to show a different category."""
        self.category = category
        embed = await self.create_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    # Row 0: Main category buttons
    @discord.ui.button(label="Overview", style=discord.ButtonStyle.primary, emoji="🎒", row=0)
    async def show_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show inventory overview."""
        await self._update_view(interaction, "overview")
    
    @discord.ui.button(label="Fish", style=discord.ButtonStyle.secondary, emoji="🐟", row=0)
    async def show_fish(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show caught fish."""
        await self._update_view(interaction, "fish")
    
    # Row 1: Equipment category buttons
    @discord.ui.button(label="Rods", style=discord.ButtonStyle.secondary, emoji="🎣", row=1)
    async def show_rods(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show rods inventory."""
        await self._update_view(interaction, "rods")
    
    @discord.ui.button(label="Lures", style=discord.ButtonStyle.secondary, emoji="🪝", row=1)
    async def show_lures(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show lures/bait inventory."""
        await self._update_view(interaction, "lures")
    
    @discord.ui.button(label="Clothing", style=discord.ButtonStyle.secondary, emoji="👕", row=1)
    async def show_clothing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show clothing inventory."""
        await self._update_view(interaction, "clothing")
    
    # Row 2: Override back button from mixin to use row 2
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=2)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to the main menu."""
        from .main_menu import create_main_menu_embed
        
        new_view = MainMenuView(cog=self.cog, author=self.author)
        embed = await create_main_menu_embed(self.cog, interaction.guild, self.author)
        await self.stop_and_update(interaction, new_view, embed)
