"""
Home pet views for viewing and interacting with graduated pets.
"""

import time
import discord
from discord.ui import View, Button, Select
from typing import TYPE_CHECKING, Optional, List

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, Pet, GuildSettings

from ..database.species import get_species
from ..database.wardrobe import get_equipped_compact, get_equipped_display, WardrobeButton


def format_timestamp(timestamp: float) -> str:
    """Format a timestamp as a readable date."""
    from datetime import datetime
    if timestamp == 0:
        return "Unknown"
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%b %d, %Y")


class HomeListView(View):
    """View for home pet list."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        guild_settings: "GuildSettings" = None,
        author: discord.Member = None
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.guild_settings = guild_settings
        self.author = author
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Add pet select dropdown if there are pets
        if user_data.home_pets:
            self.add_item(PetSelect(user_data.home_pets))
        
        # Add shop, inventory, and wardrobe buttons (row 1)
        self.add_item(SupplyShopButton())
        self.add_item(InventoryButton())
        
        # Add wardrobe button (needs guild_settings and author for the views)
        if guild_settings and author:
            wardrobe_btn = WardrobeButton(row=1)
            self.add_item(wardrobe_btn)
        
        # Add navigation buttons (row 2)
        self.add_item(BackToMenuButton(row=2))
        self.add_item(CloseHomeButton(row=2))

    def build_embed(self) -> discord.Embed:
        """Build home list embed."""
        capacity = self.user_data.effective_home_capacity
        current = len(self.user_data.home_pets)
        
        embed = discord.Embed(
            title=f"🏠 Your Home - {current}/{capacity} Pets",
            color=discord.Color.blue()
        )
        
        if not self.user_data.home_pets:
            embed.description = (
                "Your home is empty! 🏚️\n\n"
                "Raise a pet to adulthood to add them here.\n"
                "Home pets no longer need daily care - they're living their best life!"
            )
            return embed
        
        embed.description = "Your graduated companions are living happily here!"
        
        for i, pet in enumerate(self.user_data.home_pets, 1):
            species = get_species(pet.species_id)
            species_name = species.name if species else pet.species_id.replace("_", " ").title()
            species_emoji = species.emoji if species else "🐾"
            
            # Medal display
            medal_display = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(pet.medal, "")
            
            # Immortal indicator
            immortal_display = " ✨" if pet.is_immortal else ""
            
            # Stage emoji
            stage_emoji = {"adult": "🌟", "senior": "👴"}.get(pet.life_stage, "")
            
            # Equipped items compact display
            equipped_str = get_equipped_compact(pet)
            equipped_display = f" {equipped_str}" if equipped_str else ""
            
            embed.add_field(
                name=f"{i}. {species_emoji} {pet.name} {medal_display}{immortal_display}{equipped_display}",
                value=(
                    f"**{species_name}** • {pet.life_stage.title()} {stage_emoji}\n"
                    f"💕 Bond: {pet.bond} • Day {int(pet.age_days)}"
                ),
                inline=True
            )
        
        embed.set_footer(text="Select a pet from the dropdown to view details")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your Home! Use the `petcord` command to view yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class PetSelect(Select):
    """Dropdown to select a home pet to view."""

    def __init__(self, pets: List["Pet"]):
        options = []
        for i, pet in enumerate(pets[:25]):  # Discord limit: 25 options
            species = get_species(pet.species_id)
            species_name = species.name if species else pet.species_id.replace("_", " ").title()
            medal = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(pet.medal, "")
            immortal = " ✨" if pet.is_immortal else ""
            
            options.append(
                discord.SelectOption(
                    label=f"{pet.name} {medal}{immortal}",
                    description=f"{species_name} - {pet.life_stage.title()} - Bond: {pet.bond}",
                    value=str(i),
                    emoji=species.emoji if species else "🐾"
                )
            )
        
        super().__init__(
            placeholder="Select a pet to view...",
            options=options,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomeListView = self.view
        pet_index = int(self.values[0])
        
        # Create individual pet view
        pet_view = HomePetView(
            cog=view.cog,
            user_data=view.user_data,
            pet_index=pet_index,
            author_id=view.author_id,
            guild_settings=view.guild_settings,
            author=view.author
        )
        
        embed = pet_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        # Stop the list view
        view.stop()
        
        await interaction.response.edit_message(embed=embed, view=pet_view)
        pet_view.message = view.message


class SupplyShopButton(Button):
    """Button to open the supply shop."""

    def __init__(self):
        super().__init__(
            label="Supply Shop",
            emoji="🛒",
            style=discord.ButtonStyle.primary,
            row=1,
            disabled=False
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomeListView = self.view
        
        # Stop the home list view
        view.stop()
        
        # Create supply shop view
        shop_view = SupplyShopView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            guild_settings=view.guild_settings,
            author=view.author
        )
        
        embed = shop_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=shop_view)
        shop_view.message = view.message


class SupplyShopView(View):
    """View for the supply shop."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        guild_settings: "GuildSettings" = None,
        author: discord.Member = None
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.guild_settings = guild_settings
        self.author = author
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Row 0: Category buttons (disabled for now)
        self.add_item(ClothingButton())
        self.add_item(TreatsButton())
        self.add_item(VitaminsButton())
        
        # Row 1: Navigation buttons
        self.add_item(BackToHomeButton())
        self.add_item(CloseShopButton())

    def build_embed(self) -> discord.Embed:
        """Build supply shop embed."""
        embed = discord.Embed(
            title="🛒 Supply Shop",
            description=(
                "Welcome to the Supply Shop!\n\n"
                "Browse our selection of items for your pets.\n\n"
                "💰 **Your Petcoin:** {petcoin:,}\n"
                "✨ **Your Legendarycoin:** {legendarycoin:,}"
            ).format(
                petcoin=self.user_data.current_petcoin,
                legendarycoin=self.user_data.legendarycoin
            ),
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="👕 Clothing",
            value="Outfits, hats, and accessories",
            inline=True
        )
        embed.add_field(
            name="🍖 Treats",
            value="Delicious snacks for your pets",
            inline=True
        )
        embed.add_field(
            name="💊 Vitamins",
            value="Health boosters and supplements",
            inline=True
        )
        
        embed.set_footer(text="Select a category to browse items")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your shop menu! Use the `petcord` command to open yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class ClothingButton(Button):
    """Button to browse clothing items."""

    def __init__(self):
        super().__init__(
            label="Clothing",
            emoji="👕",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=False
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SupplyShopView = self.view
        
        # Stop this view
        view.stop()
        
        # Get guild settings for active holiday and timezone
        conf = view.cog.db.get_conf(interaction.guild)
        
        # Import and create clothing shop view
        from .clothing_shop import ClothingShopView
        
        clothing_view = ClothingShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=conf,
            author_id=view.author_id,
            active_holiday=conf.active_holiday
        )
        
        embed = clothing_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=clothing_view)
        clothing_view.message = view.message


class TreatsButton(Button):
    """Button to browse treats."""

    def __init__(self):
        super().__init__(
            label="Treats",
            emoji="🍖",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=False
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SupplyShopView = self.view
        view.stop()
        
        from .treats_shop import TreatsShopView
        
        treats_view = TreatsShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            author=view.author
        )
        
        embed = treats_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=treats_view)
        treats_view.message = view.message


class VitaminsButton(Button):
    """Button to browse vitamins."""

    def __init__(self):
        super().__init__(
            label="Vitamins",
            emoji="💊",
            style=discord.ButtonStyle.primary,
            row=0,
            disabled=False
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SupplyShopView = self.view
        view.stop()

        from .vitamins_shop import VitaminsShopView

        vitamins_view = VitaminsShopView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id,
            author=view.author
        )

        embed = vitamins_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=vitamins_view)
        vitamins_view.message = view.message


class BackToHomeButton(Button):
    """Button to return to home view from shop."""

    def __init__(self):
        super().__init__(
            label="Back to Home",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SupplyShopView = self.view
        
        # Stop this view
        view.stop()
        
        # Create home list view
        home_view = HomeListView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id
        )
        
        embed = home_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=home_view)
        home_view.message = view.message


class CloseShopButton(Button):
    """Button to close the shop view."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: SupplyShopView = self.view
        view.stop()
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)


class InventoryButton(Button):
    """Button to view inventory."""

    def __init__(self):
        super().__init__(
            label="Inventory",
            emoji="🎒",
            style=discord.ButtonStyle.primary,
            row=1,
            disabled=False
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomeListView = self.view
        
        # Stop current view
        view.stop()
        
        # Create inventory view
        inventory_view = InventoryView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id
        )
        
        embed = inventory_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=inventory_view)
        inventory_view.message = view.message


class BackToMenuButton(Button):
    """Button to return to main menu."""

    def __init__(self, row: int = 2):
        super().__init__(
            label="Back to Menu",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=row
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        from .main_menu import MainMenuView
        
        view: HomeListView = self.view
        
        # Stop this view
        view.stop()
        
        # Create main menu view
        conf = view.cog.db.get_conf(interaction.guild)
        main_view = MainMenuView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=conf,
            author_id=view.author_id
        )
        
        embed = await main_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=main_view)
        main_view.message = view.message


class CloseHomeButton(Button):
    """Button to close the home view."""

    def __init__(self, row: int = 2):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=row
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomeListView = self.view
        view.stop()
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)


class HomePetView(View):
    """View for individual home pet with interaction options."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        pet_index: int,
        author_id: int,
        guild_settings: "GuildSettings" = None,
        author: discord.Member = None
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.pet_index = pet_index
        self.pet = user_data.home_pets[pet_index]
        self.author_id = author_id
        self.guild_settings = guild_settings
        self.author = author
        self.message: Optional[discord.Message] = None
        
        # Register with cog
        self.cog._active_views.add(self)
        
        # Add interaction buttons
        self.add_item(HomePetButton())
        self.add_item(HomeGroomButton())
        self.add_item(HomeTreatButton())
        self.add_item(BackToHomeButton())
        self.add_item(CloseHomePetButton())

    def build_embed(self) -> discord.Embed:
        """Build individual pet embed."""
        pet = self.pet
        species = get_species(pet.species_id)
        
        species_name = species.name if species else pet.species_id.replace("_", " ").title()
        species_emoji = species.emoji if species else "🐾"
        
        # Medal display
        medal_text = ""
        if pet.medal:
            medal_display = {"gold": "🥇 Gold", "silver": "🥈 Silver", "bronze": "🥉 Bronze"}.get(pet.medal, "")
            medal_text = f"\n🏅 Medal: {medal_display} ({pet.medal_score:.1f}%)"
        
        # Immortal display
        immortal_text = "\n✨ **Immortal** - This pet will never age" if pet.is_immortal else ""
        
        # Stage emoji
        stage_emoji = {"adult": "🌟", "senior": "👴"}.get(pet.life_stage, "")
        
        embed = discord.Embed(
            title=f"{species_emoji} {pet.name}" + (" ✨" if pet.is_immortal else ""),
            description=(
                f"**{species_name}** • {pet.life_stage.title()} {stage_emoji} • Day {int(pet.age_days)}\n"
                f"🏠 Living happily in your Home{medal_text}{immortal_text}"
            ),
            color=discord.Color.green()
        )
        
        # Current status (display as int for cleaner UI)
        embed.add_field(
            name="📊 Status",
            value=(
                f"😊 Happiness: {int(pet.happiness)}%\n"
                f"✨ Cleanliness: {int(pet.cleanliness)}%\n"
                f"💕 Bond: {int(pet.bond)}"
            ),
            inline=True
        )
        
        # Time info
        if pet.graduated_timestamp:
            days_in_home = int((time.time() - pet.graduated_timestamp) / 86400)
            embed.add_field(
                name="📅 Timeline",
                value=(
                    f"Graduated: {format_timestamp(pet.graduated_timestamp)}\n"
                    f"Days in Home: {days_in_home}\n"
                    f"Total Age: {int(pet.age_days)} days"
                ),
                inline=True
            )
        
        # Appearance
        embed.add_field(
            name="🎨 Appearance",
            value=(
                f"Coat: {pet.coat_color.replace('_', ' ').title()}\n"
                f"Pattern: {pet.pattern.replace('_', ' ').title()}\n"
                f"Rarity: {pet.rarity.replace('_', ' ').title()}"
            ),
            inline=False
        )
        
        # Wearing section (only show if pet has equipped items)
        wearing_text = get_equipped_display(pet, self.user_data)
        if wearing_text:
            embed.add_field(
                name="👗 Wearing",
                value=wearing_text,
                inline=False
            )
        
        embed.set_footer(text="Home pets don't need daily care - just visit for fun!")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your pet! Use the `petcord` command to view yours.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass

    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class HomePetButton(Button):
    """Button to pet a home companion."""

    def __init__(self):
        super().__init__(
            label="Pet",
            emoji="🤗",
            style=discord.ButtonStyle.primary,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomePetView = self.view
        pet = view.pet
        
        # No cooldowns for home pets!
        old_happiness = pet.happiness
        old_bond = pet.bond
        
        pet.happiness = min(100, pet.happiness + 10)
        pet.bond = min(100, pet.bond + 2)
        
        view.cog.schedule_save()
        
        # Update embed
        embed = view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
        
        # Send ephemeral feedback
        await interaction.followup.send(
            f"🤗 You petted **{pet.name}**!\n"
            f"😊 Happiness: {int(old_happiness)} → {int(pet.happiness)}\n"
            f"💕 Bond: {int(old_bond)} → {int(pet.bond)}",
            ephemeral=True
        )


class HomeGroomButton(Button):
    """Button to groom a home companion."""

    def __init__(self):
        super().__init__(
            label="Groom",
            emoji="✨",
            style=discord.ButtonStyle.primary,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomePetView = self.view
        pet = view.pet
        
        old_cleanliness = pet.cleanliness
        pet.cleanliness = min(100, pet.cleanliness + 25)
        
        view.cog.schedule_save()
        
        embed = view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
        
        await interaction.followup.send(
            f"✨ You groomed **{pet.name}**!\n"
            f"Cleanliness: {int(old_cleanliness)} → {int(pet.cleanliness)}",
            ephemeral=True
        )


class HomeTreatButton(Button):
    """Button to give a home companion a treat."""

    def __init__(self):
        super().__init__(
            label="Treat",
            emoji="🍬",
            style=discord.ButtonStyle.primary,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomePetView = self.view
        pet = view.pet
        
        old_happiness = pet.happiness
        old_bond = pet.bond
        
        pet.happiness = min(100, pet.happiness + 15)
        pet.bond = min(100, pet.bond + 3)
        
        view.cog.schedule_save()
        
        embed = view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
        
        await interaction.followup.send(
            f"🍬 You gave **{pet.name}** a treat!\n"
            f"😊 Happiness: {int(old_happiness)} → {int(pet.happiness)}\n"
            f"💕 Bond: {int(old_bond)} → {int(pet.bond)}",
            ephemeral=True
        )


class BackToHomeButton(Button):
    """Button to return to home list."""

    def __init__(self):
        super().__init__(
            label="Back to Home",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomePetView = self.view
        view.stop()
        
        # Create home list view
        home_view = HomeListView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            guild_settings=view.guild_settings,
            author=view.author or interaction.user
        )
        
        embed = home_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=home_view)
        home_view.message = view.message


class CloseHomePetButton(Button):
    """Button to close the pet view."""

    def __init__(self):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=1
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: HomePetView = self.view
        view.stop()
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)


# =============================================================================
# INVENTORY VIEW
# =============================================================================

# Inventory category mapping (same as clothing shop)
INVENTORY_CATEGORIES = {
    "All Items": None,  # Special case - shows all
    "Onesies": ["onesie"],
    "Hats": ["hat"],
    "Headbands": ["headband"],
    "Collars": ["collar"],
    "Eyewear": ["eyepatch", "glasses"],
    "Footwear": ["socks", "booties"],
    "Tail Accessories": ["tail"],
    "Earrings": ["earring"],
    "Capes & Costumes": ["cape", "costume"],
}

INVENTORY_CATEGORY_EMOJIS = {
    "All Items": "📦",
    "Onesies": "👕",
    "Hats": "🎩",
    "Headbands": "🐱",
    "Collars": "🔴",
    "Eyewear": "😎",
    "Footwear": "🧦",
    "Tail Accessories": "🎀",
    "Earrings": "💎",
    "Capes & Costumes": "🦸",
}


class InventoryView(View):
    """View for displaying user's item inventory."""
    
    ITEMS_PER_PAGE = 10
    
    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        author_id: int,
        category: str = "All Items",
        page: int = 0
    ) -> None:
        super().__init__(timeout=180)
        self.cog = cog
        self.user_data = user_data
        self.author_id = author_id
        self.category = category
        self.page = page
        self.message: Optional[discord.Message] = None
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Get items for display
        self.all_items = self._get_category_items()
        self.total_pages = max(1, (len(self.all_items) + self.ITEMS_PER_PAGE - 1) // self.ITEMS_PER_PAGE)
        
        # Setup buttons
        self._setup_buttons()
    
    def _get_owned_item_ids(self) -> set:
        """Get set of item IDs the user owns."""
        return {item.item_id for item in self.user_data.current_item_inventory}
    
    def _get_category_items(self) -> List[dict]:
        """Get all items in the current category with ownership status."""
        from ..database.petshop import SHOP_DATABASE
        
        owned_ids = self._get_owned_item_ids()
        db_categories = INVENTORY_CATEGORIES.get(self.category)
        
        items = []
        for item_id, item_data in SHOP_DATABASE.items():
            # Filter by category if not "All Items"
            if db_categories is not None:
                if item_data.get("category") not in db_categories:
                    continue
            
            items.append({
                "id": item_id,
                "owned": item_id in owned_ids,
                **item_data
            })
        
        # Sort: owned items first, then by rarity, then by name
        rarity_order = {"legendary": 0, "rare": 1, "uncommon": 2, "common": 3}
        items.sort(key=lambda x: (
            0 if x["owned"] else 1,  # Owned first
            rarity_order.get(x.get("rarity", "common"), 4),
            x.get("name", "")
        ))
        
        return items
    
    def _setup_buttons(self) -> None:
        """Add navigation and filter buttons."""
        # Row 0: Category select
        self.add_item(InventoryCategorySelect(self.category))
        
        # Row 1: Pagination
        self.add_item(InventoryPrevButton(disabled=(self.page == 0)))
        self.add_item(InventoryNextButton(disabled=(self.page >= self.total_pages - 1)))
        
        # Row 2: Shop buttons
        self.add_item(ShopTreatsButton(self.user_data))
        self.add_item(InventoryVitaminsButton())
        
        # Row 3: Back button
        self.add_item(BackToHomeFromInventoryButton())
    
    def build_embed(self) -> discord.Embed:
        """Build the inventory embed."""
        from ..database.petshop import SHOP_DATABASE, get_item_count
        
        owned_ids = self._get_owned_item_ids()
        total_items = get_item_count()
        owned_count = len(owned_ids)
        
        # Calculate category-specific counts
        if self.category == "All Items":
            cat_total = total_items
            cat_owned = owned_count
        else:
            db_categories = INVENTORY_CATEGORIES.get(self.category, [])
            cat_items = [iid for iid, data in SHOP_DATABASE.items() 
                        if data.get("category") in db_categories]
            cat_total = len(cat_items)
            cat_owned = len([iid for iid in cat_items if iid in owned_ids])
        
        emoji = INVENTORY_CATEGORY_EMOJIS.get(self.category, "📦")
        
        embed = discord.Embed(
            title=f"🎒 Your Inventory",
            description=(
                f"**Collection Progress:** {owned_count}/{total_items} items ({owned_count*100//total_items}%)\n\n"
                f"**{emoji} {self.category}:** {cat_owned}/{cat_total} owned"
            ),
            color=discord.Color.teal()
        )
        
        # Get items for current page
        start_idx = self.page * self.ITEMS_PER_PAGE
        end_idx = start_idx + self.ITEMS_PER_PAGE
        page_items = self.all_items[start_idx:end_idx]
        
        if not page_items:
            embed.add_field(
                name="No Items",
                value="No items in this category.",
                inline=False
            )
        else:
            # Build item list
            item_lines = []
            for item in page_items:
                item_emoji = item.get("emoji", "📦")
                name = item.get("name", item["id"])
                rarity = item.get("rarity", "common")
                value = item.get("value", 0)
                
                # Rarity indicator
                rarity_indicator = {
                    "common": "⭐",
                    "uncommon": "⭐⭐",
                    "rare": "⭐⭐⭐",
                    "legendary": "✨"
                }.get(rarity, "⭐")
                
                # Ownership indicator
                if item["owned"]:
                    status = "✅"
                else:
                    status = "❌"
                
                item_lines.append(f"{status} {item_emoji} **{name}** {rarity_indicator} ({value:,}💰)")
            
            embed.add_field(
                name=f"Items (Page {self.page + 1}/{self.total_pages})",
                value="\n".join(item_lines),
                inline=False
            )
        
        # Legend
        embed.set_footer(text="✅ = Owned | ❌ = Not Owned | ⭐ = Rarity | 💰 = Value")
        
        return embed
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your inventory! Use the `petcord` command to view yours.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        self.cog._active_views.discard(self)
        for item in self.children:
            if hasattr(item, 'disabled'):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
    
    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class InventoryCategorySelect(Select):
    """Dropdown to select inventory category."""
    
    def __init__(self, current_category: str):
        options = []
        for cat_name in INVENTORY_CATEGORIES.keys():
            emoji = INVENTORY_CATEGORY_EMOJIS.get(cat_name, "📦")
            options.append(discord.SelectOption(
                label=cat_name,
                emoji=emoji,
                default=(cat_name == current_category)
            ))
        
        super().__init__(
            placeholder="Select a category...",
            options=options,
            row=0
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryView = self.view
        selected = self.values[0]
        
        # Create new view with selected category
        view.stop()
        
        new_view = InventoryView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            category=selected,
            page=0
        )
        
        embed = new_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=new_view)
        new_view.message = view.message


class InventoryPrevButton(Button):
    """Button to go to previous page."""
    
    def __init__(self, disabled: bool = False):
        super().__init__(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=1,
            disabled=disabled
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryView = self.view
        
        if view.page > 0:
            view.stop()
            
            new_view = InventoryView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                category=view.category,
                page=view.page - 1
            )
            
            embed = new_view.build_embed()
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.edit_message(embed=embed, view=new_view)
            new_view.message = view.message


class InventoryNextButton(Button):
    """Button to go to next page."""
    
    def __init__(self, disabled: bool = False):
        super().__init__(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            row=1,
            disabled=disabled
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryView = self.view
        
        if view.page < view.total_pages - 1:
            view.stop()
            
            new_view = InventoryView(
                cog=view.cog,
                user_data=view.user_data,
                author_id=view.author_id,
                category=view.category,
                page=view.page + 1
            )
            
            embed = new_view.build_embed()
            embed.set_author(
                name=interaction.user.display_name,
                icon_url=interaction.user.display_avatar.url
            )
            
            await interaction.response.edit_message(embed=embed, view=new_view)
            new_view.message = view.message


class ShopTreatsButton(Button):
    """Button to view and use owned treats."""
    
    def __init__(self, user_data: "User"):
        import time
        from ..common.constants import SHOP_TREAT_COOLDOWN_HOURS
        
        # Check cooldown
        current_time = time.time()
        on_cooldown = False
        label = "Shop Treats"
        
        if user_data.last_shoptreat_used > 0:
            cooldown_end = user_data.last_shoptreat_used + (SHOP_TREAT_COOLDOWN_HOURS * 3600)
            if current_time < cooldown_end:
                on_cooldown = True
                remaining = int(cooldown_end - current_time)
                hours, remainder = divmod(remaining, 3600)
                minutes, _ = divmod(remainder, 60)
                if hours > 0:
                    label = f"🍖 {hours}h {minutes}m"
                else:
                    label = f"🍖 {minutes}m"
        
        super().__init__(
            label=label,
            emoji="🍖" if not on_cooldown else None,
            style=discord.ButtonStyle.primary if not on_cooldown else discord.ButtonStyle.secondary,
            row=2,
            disabled=False
        )
        self.user_data = user_data
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryView = self.view
        view.stop()
        
        from .treats_shop import InventoryTreatsView
        
        treats_view = InventoryTreatsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.cog.db.get_conf(interaction.guild),
            author_id=view.author_id,
            author=interaction.user
        )
        
        embed = treats_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=treats_view)
        treats_view.message = view.message


class InventoryVitaminsButton(Button):
    """Button to view and use owned vitamins from inventory."""

    def __init__(self):
        super().__init__(
            label="Vitamins",
            emoji="💊",
            style=discord.ButtonStyle.primary,
            row=2,
            disabled=False
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryView = self.view
        view.stop()

        from .vitamins_shop import InventoryVitaminsView

        vitamins_view = InventoryVitaminsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.cog.db.get_conf(interaction.guild),
            author_id=view.author_id,
            author=interaction.user
        )

        embed = vitamins_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )

        await interaction.response.edit_message(embed=embed, view=vitamins_view)
        vitamins_view.message = view.message


class BackToHomeFromInventoryButton(Button):
    """Button to return to home view from inventory."""
    
    def __init__(self):
        super().__init__(
            label="Back to Home",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            row=3
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: InventoryView = self.view
        view.stop()
        
        # Create home list view
        home_view = HomeListView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id
        )
        
        embed = home_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=home_view)
        home_view.message = view.message
