"""
Inventory view - View and manage your fishing gear and catches.
"""

import discord
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView, MainMenuView
from ..databases.items import RODS_DATABASE, LURES_DATABASE, HATS_DATABASE, COATS_DATABASE, BOOTS_DATABASE

# Combined clothing lookup
CLOTHING_DATABASE = {**HATS_DATABASE, **COATS_DATABASE, **BOOTS_DATABASE}


class InventoryView(BaseView):
    """View for the player's inventory."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        category: str = "overview"
    ):
        super().__init__(cog=cog, author=author)
        self.category = category
        
        # Initialize the view with all buttons
        if self.category == "clothing":
            self._add_clothing_selects()
        self._add_category_buttons()
        self._add_back_button()
    
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
            # Organize by slot
            hats = []
            coats = []
            boots = []
            
            for idx, item in enumerate(user_data.current_clothing_inventory):
                item_id = item.get("clothing_id")
                item_info = CLOTHING_DATABASE.get(item_id, {})
                name = item_info.get("name", item_id)
                slot = item.get("slot", item_info.get("slot", "unknown"))
                luck = item_info.get("luck_bonus", 0)
                
                # Check if this item is equipped based on its slot
                is_equipped = False
                if slot == "hat" and user_data.equipped_hat_index == idx:
                    is_equipped = True
                elif slot == "coat" and user_data.equipped_coat_index == idx:
                    is_equipped = True
                elif slot == "boots" and user_data.equipped_boots_index == idx:
                    is_equipped = True
                
                equipped = " ✅" if is_equipped else ""
                item_line = f"**{name}**{equipped} (+{luck} luck)"
                
                if slot == "hat":
                    hats.append(item_line)
                elif slot == "coat":
                    coats.append(item_line)
                elif slot == "boots":
                    boots.append(item_line)
            
            # Build description
            desc_parts = []
            if hats:
                desc_parts.append("**🎩 Hats**\n" + "\n".join(hats))
            if coats:
                desc_parts.append("**🧥 Coats**\n" + "\n".join(coats))
            if boots:
                desc_parts.append("**👢 Boots**\n" + "\n".join(boots))
            
            embed.description = "\n\n".join(desc_parts) if desc_parts else "No clothing items."
            
            # Show total luck bonus
            hat = user_data.get_equipped_clothing("hat")
            coat = user_data.get_equipped_clothing("coat")
            boots_item = user_data.get_equipped_clothing("boots")
            
            total_luck = 0
            if hat:
                hat_info = CLOTHING_DATABASE.get(hat.get("clothing_id", ""), {})
                total_luck += hat_info.get("luck_bonus", 0)
            if coat:
                coat_info = CLOTHING_DATABASE.get(coat.get("clothing_id", ""), {})
                total_luck += coat_info.get("luck_bonus", 0)
            if boots_item:
                boots_info = CLOTHING_DATABASE.get(boots_item.get("clothing_id", ""), {})
                total_luck += boots_info.get("luck_bonus", 0)
            
            embed.add_field(
                name="🍀 Total Luck Bonus",
                value=f"**+{total_luck}** luck from equipped gear",
                inline=False
            )
        
        embed.set_footer(text="Use the dropdowns below to equip/unequip clothing items!")
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
    
    def _add_clothing_selects(self):
        """Add dropdown selects for each clothing slot."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        # Group items by slot
        hats = []
        coats = []
        boots = []
        
        for idx, item in enumerate(user_data.current_clothing_inventory):
            item_id = item.get("clothing_id")
            item_info = CLOTHING_DATABASE.get(item_id, {})
            slot = item.get("slot", item_info.get("slot", "unknown"))
            
            if slot == "hat":
                hats.append((idx, item, item_info))
            elif slot == "coat":
                coats.append((idx, item, item_info))
            elif slot == "boots":
                boots.append((idx, item, item_info))
        
        # Add hat selector
        if hats:
            hat_options = [discord.SelectOption(
                label="None (Unequip)",
                value="none",
                emoji="❌",
                default=(user_data.equipped_hat_index is None)
            )]
            
            for idx, item, item_info in hats:
                name = item_info.get("name", "Unknown Hat")
                luck = item_info.get("luck_bonus", 0)
                is_equipped = user_data.equipped_hat_index == idx
                
                hat_options.append(discord.SelectOption(
                    label=name[:100],
                    value=str(idx),
                    description=f"+{luck} luck",
                    emoji="✅" if is_equipped else "🎩",
                    default=is_equipped
                ))
            
            hat_select = discord.ui.Select(
                placeholder="Select Hat...",
                options=hat_options,
                row=0
            )
            hat_select.callback = self.hat_selected
            self.add_item(hat_select)
        
        # Add coat selector
        if coats:
            coat_options = [discord.SelectOption(
                label="None (Unequip)",
                value="none",
                emoji="❌",
                default=(user_data.equipped_coat_index is None)
            )]
            
            for idx, item, item_info in coats:
                name = item_info.get("name", "Unknown Coat")
                luck = item_info.get("luck_bonus", 0)
                is_equipped = user_data.equipped_coat_index == idx
                
                coat_options.append(discord.SelectOption(
                    label=name[:100],
                    value=str(idx),
                    description=f"+{luck} luck",
                    emoji="✅" if is_equipped else "🧥",
                    default=is_equipped
                ))
            
            coat_select = discord.ui.Select(
                placeholder="Select Coat...",
                options=coat_options,
                row=1
            )
            coat_select.callback = self.coat_selected
            self.add_item(coat_select)
        
        # Add boots selector
        if boots:
            boots_options = [discord.SelectOption(
                label="None (Unequip)",
                value="none",
                emoji="❌",
                default=(user_data.equipped_boots_index is None)
            )]
            
            for idx, item, item_info in boots:
                name = item_info.get("name", "Unknown Boots")
                luck = item_info.get("luck_bonus", 0)
                is_equipped = user_data.equipped_boots_index == idx
                
                boots_options.append(discord.SelectOption(
                    label=name[:100],
                    value=str(idx),
                    description=f"+{luck} luck",
                    emoji="✅" if is_equipped else "👢",
                    default=is_equipped
                ))
            
            boots_select = discord.ui.Select(
                placeholder="Select Boots...",
                options=boots_options,
                row=2
            )
            boots_select.callback = self.boots_selected
            self.add_item(boots_select)
    
    async def hat_selected(self, interaction: discord.Interaction):
        """Handle hat selection."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        selected_value = interaction.data["values"][0]
        
        if selected_value == "none":
            user_data.unequip_clothing("hat")
        else:
            idx = int(selected_value)
            user_data.equip_clothing(idx)
        
        self.cog.save()
        
        # Refresh view
        self.clear_items()
        self._add_clothing_selects()
        self._add_category_buttons()
        self._add_back_button()
        
        embed = await self.create_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def coat_selected(self, interaction: discord.Interaction):
        """Handle coat selection."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        selected_value = interaction.data["values"][0]
        
        if selected_value == "none":
            user_data.unequip_clothing("coat")
        else:
            idx = int(selected_value)
            user_data.equip_clothing(idx)
        
        self.cog.save()
        
        # Refresh view
        self.clear_items()
        self._add_clothing_selects()
        self._add_category_buttons()
        self._add_back_button()
        
        embed = await self.create_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def boots_selected(self, interaction: discord.Interaction):
        """Handle boots selection."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        selected_value = interaction.data["values"][0]
        
        if selected_value == "none":
            user_data.unequip_clothing("boots")
        else:
            idx = int(selected_value)
            user_data.equip_clothing(idx)
        
        self.cog.save()
        
        # Refresh view
        self.clear_items()
        self._add_clothing_selects()
        self._add_category_buttons()
        self._add_back_button()
        
        embed = await self.create_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    def _add_category_buttons(self):
        """Add the category navigation buttons."""
        # Determine which row to start on based on whether we're showing clothing
        start_row = 3 if self.category == "clothing" else 0
        
        # Main category buttons
        overview_btn = discord.ui.Button(label="Overview", style=discord.ButtonStyle.primary, emoji="🎒", row=start_row)
        overview_btn.callback = self.show_overview
        self.add_item(overview_btn)
        
        fish_btn = discord.ui.Button(label="Fish", style=discord.ButtonStyle.secondary, emoji="🐟", row=start_row)
        fish_btn.callback = self.show_fish
        self.add_item(fish_btn)
        
        # Equipment category buttons
        rods_btn = discord.ui.Button(label="Rods", style=discord.ButtonStyle.secondary, emoji="🎣", row=start_row + 1)
        rods_btn.callback = self.show_rods
        self.add_item(rods_btn)
        
        lures_btn = discord.ui.Button(label="Lures", style=discord.ButtonStyle.secondary, emoji="🪝", row=start_row + 1)
        lures_btn.callback = self.show_lures
        self.add_item(lures_btn)
        
        clothing_btn = discord.ui.Button(label="Clothing", style=discord.ButtonStyle.secondary, emoji="👕", row=start_row + 1)
        clothing_btn.callback = self.show_clothing
        self.add_item(clothing_btn)
    
    def _add_back_button(self):
        """Add the back button."""
        # Back button goes below the equipment buttons
        start_row = 3 if self.category == "clothing" else 0
        back_row = start_row + 2  # Two rows after the start (below equipment buttons)
        back_btn = discord.ui.Button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=back_row)
        back_btn.callback = self.back_to_menu
        self.add_item(back_btn)
    
    async def _update_view(self, interaction: discord.Interaction, category: str):
        """Update the view to show a different category."""
        self.category = category
        
        # Rebuild view with proper buttons/selects
        self.clear_items()
        if category == "clothing":
            self._add_clothing_selects()
        self._add_category_buttons()
        self._add_back_button()
        
        embed = await self.create_inventory_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_overview(self, interaction: discord.Interaction, button: discord.ui.Button = None):
        """Show inventory overview."""
        await self._update_view(interaction, "overview")
    
    async def show_fish(self, interaction: discord.Interaction, button: discord.ui.Button = None):
        """Show caught fish."""
        await self._update_view(interaction, "fish")
    
    async def show_rods(self, interaction: discord.Interaction, button: discord.ui.Button = None):
        """Show rods inventory."""
        await self._update_view(interaction, "rods")
    
    async def show_lures(self, interaction: discord.Interaction, button: discord.ui.Button = None):
        """Show lures/bait inventory."""
        await self._update_view(interaction, "lures")
    
    async def show_clothing(self, interaction: discord.Interaction, button: discord.ui.Button = None):
        """Show clothing inventory."""
        await self._update_view(interaction, "clothing")
    
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button = None):
        """Return to the main menu."""
        from .main_menu import create_main_menu_embed
        
        new_view = MainMenuView(cog=self.cog, author=self.author)
        embed = await create_main_menu_embed(self.cog, interaction.guild, self.author)
        await self.stop_and_update(interaction, new_view, embed)
