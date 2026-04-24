"""
Pet Wardrobe System

This module handles all wardrobe/clothing functionality for pets:
- Helper functions for equipping/unequipping items
- Compatibility checking (species restrictions)
- Display formatting for worn items
- Wardrobe UI views

Items are stored in user inventory and "equipped" is just a reference.
Multiple pets can wear the same item (it's cosmetic display only).
"""

from typing import TYPE_CHECKING, Optional, List, Tuple, Dict
import discord
from discord.ui import View, Button, Select
from discord import SelectOption

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, Pet, GuildSettings

from .petshop import SHOP_DATABASE
from .species import get_species
from ..common.constants import (
    WEAR_SLOTS,
    CATEGORY_TO_SLOT,
    SLOT_DISPLAY,
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_slot_for_item(item_id: str) -> Optional[str]:
    """Get the wear slot for an item based on its category.
    
    Args:
        item_id: The item ID from SHOP_DATABASE
        
    Returns:
        Slot name (e.g., "head", "body") or None if item isn't wearable
    """
    item = SHOP_DATABASE.get(item_id)
    if not item:
        return None
    
    category = item.get("category", "")
    return CATEGORY_TO_SLOT.get(category)


def can_pet_wear_item(pet: "Pet", item_id: str) -> Tuple[bool, str]:
    """Check if a pet can wear a specific item.
    
    Args:
        pet: The pet to check
        item_id: The item ID to check
        
    Returns:
        Tuple of (can_wear: bool, reason: str)
        If can_wear is False, reason explains why
    """
    item = SHOP_DATABASE.get(item_id)
    if not item:
        return False, "Item not found"
    
    # Check if item is wearable at all
    slot = get_slot_for_item(item_id)
    if not slot:
        return False, "This item cannot be worn"
    
    # Get species info
    species = get_species(pet.species_id)
    if not species:
        return False, "Unknown pet species"
    
    # Check category restriction (e.g., only dogs/cats can wear)
    cat_restricted = item.get("category_restricted", [])
    if cat_restricted and species.category not in cat_restricted:
        friendly_cats = ", ".join(cat.replace("_", " ").title() for cat in cat_restricted)
        return False, f"This item is only for: {friendly_cats}"
    
    # Check species restriction (e.g., only specific species)
    species_restricted = item.get("species_restricted", [])
    if species_restricted and pet.species_id not in species_restricted:
        return False, "This item doesn't fit your pet's species"
    
    return True, ""


def user_owns_item(user_data: "User", item_id: str) -> bool:
    """Check if user owns an item in their inventory."""
    return any(inv_item.item_id == item_id for inv_item in user_data.current_item_inventory)


def equip_item(pet: "Pet", user_data: "User", item_id: str) -> Tuple[bool, str]:
    """Equip an item to a pet.
    
    Args:
        pet: The pet to equip the item on
        user_data: The user's data (to verify ownership)
        item_id: The item to equip
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    # Verify user owns the item
    if not user_owns_item(user_data, item_id):
        return False, "You don't own this item"
    
    # Check if pet can wear the item
    can_wear, reason = can_pet_wear_item(pet, item_id)
    if not can_wear:
        return False, reason
    
    # Get the slot and equip
    slot = get_slot_for_item(item_id)
    if not slot:
        return False, "This item cannot be worn"
    
    # Get item name for message
    item = SHOP_DATABASE.get(item_id, {})
    item_name = item.get("name", item_id)
    
    # Check if replacing an existing item
    old_item_id = pet.equipped_items.get(slot)
    old_item_name = ""
    if old_item_id:
        old_item = SHOP_DATABASE.get(old_item_id, {})
        old_item_name = old_item.get("name", old_item_id)
    
    # Equip the item
    pet.equipped_items[slot] = item_id
    
    if old_item_name:
        return True, f"Replaced **{old_item_name}** with **{item_name}**"
    else:
        return True, f"Equipped **{item_name}**"


def unequip_slot(pet: "Pet", slot: str) -> Tuple[bool, str]:
    """Remove an item from a specific slot.
    
    Args:
        pet: The pet to unequip from
        slot: The slot to clear
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if slot not in WEAR_SLOTS:
        return False, "Invalid slot"
    
    if slot not in pet.equipped_items:
        return False, "Nothing equipped in that slot"
    
    item_id = pet.equipped_items.pop(slot)
    item = SHOP_DATABASE.get(item_id, {})
    item_name = item.get("name", item_id)
    
    return True, f"Removed **{item_name}**"


def unequip_all(pet: "Pet") -> Tuple[bool, str]:
    """Remove all equipped items from a pet.
    
    Args:
        pet: The pet to unequip from
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    if not pet.equipped_items:
        return False, "Pet isn't wearing anything"
    
    count = len(pet.equipped_items)
    pet.equipped_items.clear()
    
    return True, f"Removed {count} item{'s' if count != 1 else ''}"


def get_equipped_display(pet: "Pet", user_data: "User" = None) -> Optional[str]:
    """Get display text for all equipped items.
    
    If user_data is provided, validates ownership and auto-unequips
    items the user no longer owns.
    
    Args:
        pet: The pet to display equipment for
        user_data: Optional user data for ownership validation
        
    Returns:
        Formatted string of equipped items, or None if nothing equipped
    """
    if not pet.equipped_items:
        return None
    
    # Get slots in display order
    sorted_slots = sorted(
        pet.equipped_items.keys(),
        key=lambda s: SLOT_DISPLAY.get(s, {}).get("order", 99)
    )
    
    lines = []
    slots_to_remove = []
    
    for slot in sorted_slots:
        item_id = pet.equipped_items[slot]
        item = SHOP_DATABASE.get(item_id)
        
        if not item:
            # Item no longer exists in database
            slots_to_remove.append(slot)
            continue
        
        # If user_data provided, check ownership
        if user_data and not user_owns_item(user_data, item_id):
            slots_to_remove.append(slot)
            continue
        
        slot_info = SLOT_DISPLAY.get(slot, {"emoji": "•"})
        item_name = item.get("name", item_id)
        lines.append(f"{slot_info['emoji']} {item_name}")
    
    # Clean up invalid equipped items
    for slot in slots_to_remove:
        pet.equipped_items.pop(slot, None)
    
    if not lines:
        return None
    
    return "\n".join(lines)


def get_equipped_compact(pet: "Pet") -> str:
    """Get compact emoji-only display of equipped items.
    
    Args:
        pet: The pet to display equipment for
        
    Returns:
        String of emojis for equipped slots (e.g., "🎩👕📿")
    """
    if not pet.equipped_items:
        return ""
    
    # Get slots in display order
    sorted_slots = sorted(
        pet.equipped_items.keys(),
        key=lambda s: SLOT_DISPLAY.get(s, {}).get("order", 99)
    )
    
    emojis = []
    for slot in sorted_slots:
        slot_info = SLOT_DISPLAY.get(slot, {})
        if "emoji" in slot_info:
            emojis.append(slot_info["emoji"])
    
    return "".join(emojis)


def get_wearable_pets(user_data: "User", item_id: str) -> List["Pet"]:
    """Get all pets that can wear a specific item.
    
    Args:
        user_data: The user's data
        item_id: The item to check
        
    Returns:
        List of pets that can wear this item
    """
    pets = []
    
    # Check current pet
    if user_data.current_pet:
        can_wear, _ = can_pet_wear_item(user_data.current_pet, item_id)
        if can_wear:
            pets.append(user_data.current_pet)
    
    # Check home pets
    for pet in user_data.home_pets:
        can_wear, _ = can_pet_wear_item(pet, item_id)
        if can_wear:
            pets.append(pet)
    
    return pets


def get_available_items_for_slot(user_data: "User", pet: "Pet", slot: str) -> List[dict]:
    """Get all owned items that can fill a specific slot for a pet.
    
    Args:
        user_data: The user's data (for inventory)
        pet: The pet to check compatibility for
        slot: The slot to find items for
        
    Returns:
        List of item dicts with 'id' included, sorted by name
    """
    if slot not in WEAR_SLOTS:
        return []
    
    valid_categories = WEAR_SLOTS[slot]
    items = []
    
    for inv_item in user_data.current_item_inventory:
        item_data = SHOP_DATABASE.get(inv_item.item_id)
        if not item_data:
            continue
        
        # Check if item fits this slot
        if item_data.get("category") not in valid_categories:
            continue
        
        # Check if pet can wear it
        can_wear, _ = can_pet_wear_item(pet, inv_item.item_id)
        if not can_wear:
            continue
        
        items.append({
            "id": inv_item.item_id,
            **item_data
        })
    
    # Sort by name
    items.sort(key=lambda x: x.get("name", ""))
    
    return items


def get_all_pets(user_data: "User") -> List[Tuple["Pet", str]]:
    """Get all pets belonging to a user with labels.
    
    Args:
        user_data: The user's data
        
    Returns:
        List of (pet, label) tuples where label indicates if current/home
    """
    pets = []
    
    if user_data.current_pet:
        pets.append((user_data.current_pet, "current"))
    
    for pet in user_data.home_pets:
        pets.append((pet, "home"))
    
    return pets


# =============================================================================
# WARDROBE VIEWS
# =============================================================================

class WardrobeButton(Button):
    """Button to access the wardrobe from Home view."""
    
    def __init__(self, row: int = 1):
        super().__init__(
            label="Wardrobe",
            emoji="👗",
            style=discord.ButtonStyle.secondary,
            row=row,
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: View = self.view
        
        # Get all pets
        pets = get_all_pets(view.user_data)
        
        if not pets:
            await interaction.response.send_message(
                "❌ You don't have any pets to dress up!",
                ephemeral=True
            )
            return
        
        # Create pet selection view
        wardrobe_view = WardrobePetSelectView(
            cog=view.cog,
            author=view.author,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            parent_view=view,
        )
        
        embed = wardrobe_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=wardrobe_view)
        wardrobe_view.message = view.message


class WardrobePetSelectView(View):
    """View for selecting which pet to dress up."""
    
    def __init__(
        self,
        cog: "Petcord",
        author: discord.Member,
        user_data: "User",
        guild_settings: "GuildSettings",
        parent_view: View,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.author = author
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None
        
        # Build pet selection dropdown
        self._build_pet_select()
        
        # Add back button
        self.add_item(BackToHomeButton(parent_view))
    
    def _build_pet_select(self) -> None:
        """Build the pet selection dropdown."""
        pets = get_all_pets(self.user_data)
        
        if not pets:
            return
        
        options = []
        for i, (pet, location) in enumerate(pets):
            species = get_species(pet.species_id)
            species_name = species.name if species else "Unknown"
            
            # Build description
            if location == "current":
                desc = f"Currently raising • {pet.life_stage.title()}"
            else:
                medal_str = f" {self._medal_emoji(pet.medal)}" if pet.medal else ""
                desc = f"In Home{medal_str} • {pet.life_stage.title()}"
            
            # Show equipped count
            equipped_count = len(pet.equipped_items)
            if equipped_count > 0:
                desc += f" • {equipped_count} item{'s' if equipped_count != 1 else ''} worn"
            
            options.append(SelectOption(
                label=f"{pet.name} the {species_name}",
                description=desc[:100],  # Discord limit
                value=str(i),
                emoji="🐾" if location == "current" else "🏠",
            ))
        
        select = Select(
            placeholder="Select a pet to dress up...",
            options=options,
            row=0,
        )
        select.callback = self._on_pet_select
        self.add_item(select)
    
    def _medal_emoji(self, medal: str) -> str:
        """Get medal emoji."""
        return {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(medal, "")
    
    async def _on_pet_select(self, interaction: discord.Interaction) -> None:
        """Handle pet selection."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your wardrobe!", ephemeral=True)
            return
        
        pets = get_all_pets(self.user_data)
        # interaction.data is guaranteed by Discord when callback fires from Select
        data = interaction.data or {}
        selected_idx = int(data.get("values", ["0"])[0])
        
        if selected_idx >= len(pets):
            await interaction.response.send_message("Invalid selection.", ephemeral=True)
            return
        
        selected_pet, location = pets[selected_idx]
        
        # Open wardrobe for this pet
        wardrobe_view = WardrobeView(
            cog=self.cog,
            author=self.author,
            user_data=self.user_data,
            guild_settings=self.guild_settings,
            pet=selected_pet,
            pet_location=location,
            parent_view=self,
        )
        
        embed = wardrobe_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=wardrobe_view)
        wardrobe_view.message = self.message
    
    def build_embed(self) -> discord.Embed:
        """Build the pet selection embed."""
        embed = discord.Embed(
            title="👗 Wardrobe",
            description="Choose a pet to dress up!",
            color=discord.Color.purple(),
        )
        
        pets = get_all_pets(self.user_data)
        
        if not pets:
            embed.description = "You don't have any pets yet!"
        else:
            pet_list = []
            for pet, location in pets:
                species = get_species(pet.species_id)
                species_name = species.name if species else "Unknown"
                loc_emoji = "🐾" if location == "current" else "🏠"
                
                equipped = get_equipped_compact(pet)
                equipped_str = f" {equipped}" if equipped else ""
                
                pet_list.append(f"{loc_emoji} **{pet.name}** the {species_name}{equipped_str}")
            
            embed.add_field(
                name="Your Pets",
                value="\n".join(pet_list),
                inline=False
            )
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the author can interact."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "This isn't your wardrobe!", ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Disable view on timeout."""
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class WardrobeView(View):
    """Main wardrobe view for a specific pet."""
    
    def __init__(
        self,
        cog: "Petcord",
        author: discord.Member,
        user_data: "User",
        guild_settings: "GuildSettings",
        pet: "Pet",
        pet_location: str,
        parent_view: View,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.author = author
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.pet = pet
        self.pet_location = pet_location
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None
        
        # Build slot selection dropdown
        self._build_slot_select()
        
        # Add remove all button (only if something equipped)
        if pet.equipped_items:
            self.add_item(RemoveAllButton(row=1))
        
        # Add back button
        self.add_item(BackToPetSelectButton(parent_view, row=1))
    
    def _build_slot_select(self) -> None:
        """Build the slot selection dropdown."""
        options = []
        
        # Sort slots by display order
        sorted_slots = sorted(
            SLOT_DISPLAY.items(),
            key=lambda x: x[1].get("order", 99)
        )
        
        for slot, info in sorted_slots:
            # Check if slot has an item
            equipped_id = self.pet.equipped_items.get(slot)
            if equipped_id:
                item = SHOP_DATABASE.get(equipped_id, {})
                item_name = item.get("name", "Unknown")
                desc = f"Currently: {item_name}"
            else:
                desc = "Empty - click to equip"
            
            # Count available items for this slot
            available = get_available_items_for_slot(self.user_data, self.pet, slot)
            if available:
                desc += f" • {len(available)} available"
            
            options.append(SelectOption(
                label=f"{info['name']} Slot",
                description=desc[:100],
                value=slot,
                emoji=info["emoji"],
            ))
        
        select = Select(
            placeholder="Select a slot to change...",
            options=options,
            row=0,
        )
        select.callback = self._on_slot_select
        self.add_item(select)
    
    async def _on_slot_select(self, interaction: discord.Interaction) -> None:
        """Handle slot selection."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your wardrobe!", ephemeral=True)
            return
        
        # interaction.data is guaranteed by Discord when callback fires from Select
        data = interaction.data or {}
        slot = data.get("values", [""])[0]
        
        # Open slot item selection view
        slot_view = SlotItemSelectView(
            cog=self.cog,
            author=self.author,
            user_data=self.user_data,
            guild_settings=self.guild_settings,
            pet=self.pet,
            pet_location=self.pet_location,
            slot=slot,
            parent_view=self,
        )
        
        embed = slot_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=slot_view)
        slot_view.message = self.message
    
    def build_embed(self) -> discord.Embed:
        """Build the wardrobe embed."""
        species = get_species(self.pet.species_id)
        species_name = species.name if species else "Unknown"
        
        loc_str = "(currently raising)" if self.pet_location == "current" else "(in Home)"
        
        embed = discord.Embed(
            title=f"👗 {self.pet.name}'s Wardrobe",
            description=f"{species_name} {loc_str}",
            color=discord.Color.purple(),
        )
        
        # Show all slots with current equipment
        slot_lines = []
        sorted_slots = sorted(
            SLOT_DISPLAY.items(),
            key=lambda x: x[1].get("order", 99)
        )
        
        for slot, info in sorted_slots:
            equipped_id = self.pet.equipped_items.get(slot)
            if equipped_id:
                item = SHOP_DATABASE.get(equipped_id, {})
                item_name = item.get("name", "Unknown")
                slot_lines.append(f"{info['emoji']} **{info['name']}:** {item_name}")
            else:
                slot_lines.append(f"{info['emoji']} **{info['name']}:** *(empty)*")
        
        embed.add_field(
            name="Equipment Slots",
            value="\n".join(slot_lines),
            inline=False
        )
        
        # Show inventory count
        total_wearable = sum(
            1 for item in self.user_data.current_item_inventory
            if get_slot_for_item(item.item_id) is not None
        )
        embed.set_footer(text=f"You own {total_wearable} wearable item{'s' if total_wearable != 1 else ''}")
        
        return embed
    
    async def refresh(self, interaction: discord.Interaction) -> None:
        """Refresh the view after changes."""
        # Rebuild the view
        self.clear_items()
        self._build_slot_select()
        if self.pet.equipped_items:
            self.add_item(RemoveAllButton(row=1))
        self.add_item(BackToPetSelectButton(self.parent_view, row=1))
        
        embed = self.build_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the author can interact."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "This isn't your wardrobe!", ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Disable view on timeout."""
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


class SlotItemSelectView(View):
    """View for selecting an item for a specific slot."""
    
    def __init__(
        self,
        cog: "Petcord",
        author: discord.Member,
        user_data: "User",
        guild_settings: "GuildSettings",
        pet: "Pet",
        pet_location: str,
        slot: str,
        parent_view: WardrobeView,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.author = author
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.pet = pet
        self.pet_location = pet_location
        self.slot = slot
        self.parent_view = parent_view
        self.message: Optional[discord.Message] = None
        
        # Build item selection dropdown
        self._build_item_select()
        
        # Add remove button if slot has item
        if slot in pet.equipped_items:
            self.add_item(RemoveFromSlotButton(slot, row=1))
        
        # Add back button
        self.add_item(BackToWardrobeButton(parent_view, row=1))
    
    def _build_item_select(self) -> None:
        """Build the item selection dropdown."""
        available = get_available_items_for_slot(self.user_data, self.pet, self.slot)
        
        if not available:
            return  # No dropdown if no items
        
        current_equipped = self.pet.equipped_items.get(self.slot)
        
        options = []
        for item in available[:25]:  # Discord limit
            item_id = item["id"]
            item_name = item.get("name", item_id)
            rarity = item.get("rarity", "common").title()
            
            is_equipped = item_id == current_equipped
            desc = f"{rarity}"
            if is_equipped:
                desc += " • Currently equipped ✓"
            
            options.append(SelectOption(
                label=item_name[:100],
                description=desc[:100],
                value=item_id,
                emoji=item.get("emoji", "👕"),
                default=is_equipped,
            ))
        
        select = Select(
            placeholder="Select an item to equip...",
            options=options,
            row=0,
        )
        select.callback = self._on_item_select
        self.add_item(select)
    
    async def _on_item_select(self, interaction: discord.Interaction) -> None:
        """Handle item selection."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("This isn't your wardrobe!", ephemeral=True)
            return
        
        # interaction.data is guaranteed by Discord when callback fires from Select
        data = interaction.data or {}
        item_id = data.get("values", [""])[0]
        
        # Equip the item
        success, message = equip_item(self.pet, self.user_data, item_id)
        
        if success:
            self.cog.schedule_save()
            # Return to main wardrobe view
            await self.parent_view.refresh(interaction)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
    
    def build_embed(self) -> discord.Embed:
        """Build the slot item selection embed."""
        slot_info = SLOT_DISPLAY.get(self.slot, {"name": self.slot.title(), "emoji": "•"})
        
        embed = discord.Embed(
            title=f"{slot_info['emoji']} {slot_info['name']} Slot",
            description=f"Select an item for **{self.pet.name}**",
            color=discord.Color.purple(),
        )
        
        # Show current item
        current_id = self.pet.equipped_items.get(self.slot)
        if current_id:
            item = SHOP_DATABASE.get(current_id, {})
            item_name = item.get("name", "Unknown")
            embed.add_field(
                name="Currently Equipped",
                value=f"{item.get('emoji', '👕')} {item_name}",
                inline=False
            )
        else:
            embed.add_field(
                name="Currently Equipped",
                value="*Nothing*",
                inline=False
            )
        
        # Show available items
        available = get_available_items_for_slot(self.user_data, self.pet, self.slot)
        if available:
            item_list = []
            for item in available[:10]:  # Show first 10
                emoji = item.get("emoji", "•")
                name = item.get("name", item["id"])
                rarity = item.get("rarity", "common").title()
                is_current = item["id"] == current_id
                check = " ✓" if is_current else ""
                item_list.append(f"{emoji} {name} ({rarity}){check}")
            
            if len(available) > 10:
                item_list.append(f"*...and {len(available) - 10} more*")
            
            embed.add_field(
                name=f"Available Items ({len(available)})",
                value="\n".join(item_list),
                inline=False
            )
        else:
            embed.add_field(
                name="Available Items",
                value="*You don't own any items for this slot that this pet can wear.*",
                inline=False
            )
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the author can interact."""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message(
                "This isn't your wardrobe!", ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Disable view on timeout."""
        for item in self.children:
            item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# =============================================================================
# NAVIGATION BUTTONS
# =============================================================================

class BackToHomeButton(Button):
    """Button to return to Home view."""
    
    def __init__(self, home_view: View, row: int = 1):
        super().__init__(
            label="Back to Home",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            row=row,
        )
        self.home_view = home_view
    
    async def callback(self, interaction: discord.Interaction) -> None:
        # Return to the home view
        embed = self.home_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.home_view)


class BackToPetSelectButton(Button):
    """Button to return to pet selection."""
    
    def __init__(self, pet_select_view: View, row: int = 1):
        super().__init__(
            label="Back",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=row,
        )
        self.pet_select_view = pet_select_view
    
    async def callback(self, interaction: discord.Interaction) -> None:
        embed = self.pet_select_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.pet_select_view)


class BackToWardrobeButton(Button):
    """Button to return to main wardrobe view."""
    
    def __init__(self, wardrobe_view: WardrobeView, row: int = 1):
        super().__init__(
            label="Back",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=row,
        )
        self.wardrobe_view = wardrobe_view
    
    async def callback(self, interaction: discord.Interaction) -> None:
        # Rebuild wardrobe view in case equipment changed
        self.wardrobe_view.clear_items()
        self.wardrobe_view._build_slot_select()
        if self.wardrobe_view.pet.equipped_items:
            self.wardrobe_view.add_item(RemoveAllButton(row=1))
        self.wardrobe_view.add_item(BackToPetSelectButton(self.wardrobe_view.parent_view, row=1))
        
        embed = self.wardrobe_view.build_embed()
        await interaction.response.edit_message(embed=embed, view=self.wardrobe_view)


class RemoveAllButton(Button):
    """Button to remove all equipped items."""
    
    def __init__(self, row: int = 1):
        super().__init__(
            label="Remove All",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
            row=row,
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: WardrobeView = self.view
        
        if interaction.user.id != view.author.id:
            await interaction.response.send_message("This isn't your wardrobe!", ephemeral=True)
            return
        
        success, message = unequip_all(view.pet)
        
        if success:
            view.cog.schedule_save()
            await view.refresh(interaction)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)


class RemoveFromSlotButton(Button):
    """Button to remove item from current slot."""
    
    def __init__(self, slot: str, row: int = 1):
        super().__init__(
            label="Remove",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=row,
        )
        self.slot = slot
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: SlotItemSelectView = self.view
        
        if interaction.user.id != view.author.id:
            await interaction.response.send_message("This isn't your wardrobe!", ephemeral=True)
            return
        
        success, message = unequip_slot(view.pet, self.slot)
        
        if success:
            view.cog.schedule_save()
            # Return to main wardrobe view
            await view.parent_view.refresh(interaction)
        else:
            await interaction.response.send_message(f"❌ {message}", ephemeral=True)
