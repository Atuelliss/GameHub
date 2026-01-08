"""
Fishing view - Where the actual fishing happens.
"""

import asyncio
import discord
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..main import GreenacresFishing

from .base_views import BaseView, BackToMenuMixin
from ..commands.helper_functions import (
    get_game_calendar,
    get_game_time_of_day,
    FishingSession,
    FishingPhase,
    create_fishing_session,
    cast_line,
    check_for_bite,
    retrieve_line,
    fish_strikes,
    attempt_set_hook,
    get_fight_event,
    process_reel_attempt,
    land_the_fish,
    handle_line_snap,
    calculate_gear_luck_bonus,
)
from ..common.weather import get_weather_for_guild, get_weather_display
from ..databases.items import LURES_DATABASE


# Location data with emojis and thumbnails
FISHING_LOCATIONS = {
    "pond": {
        "name": "Pond",
        "emoji": "🏞️",
        "description": "A peaceful pond surrounded by lily pads and cattails.",
        "water_type": "freshwater",
        "thumbnail": "https://images.unsplash.com/photo-1516410529446-2c777cb7366d?w=300&q=80"
    },
    "lake": {
        "name": "Lake",
        "emoji": "🌊",
        "description": "A large lake with deep waters and plenty of fish.",
        "water_type": "freshwater",
        "thumbnail": "https://images.unsplash.com/photo-1501785888041-af3ef285b470?w=300&q=80"
    },
    "river": {
        "name": "River",
        "emoji": "🏔️",
        "description": "A flowing river with currents that attract many species.",
        "water_type": "freshwater",
        "thumbnail": "https://images.unsplash.com/photo-1468276311594-df7cb65d8df6?w=300&q=80"
    },
    "ocean": {
        "name": "Ocean",
        "emoji": "🌅",
        "description": "The vast ocean with saltwater species and big catches.",
        "water_type": "saltwater",
        "thumbnail": "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?w=300&q=80"
    }
}


class LocationSelectView(BackToMenuMixin, BaseView):
    """View for selecting a fishing location."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member
    ):
        super().__init__(cog=cog, author=author)
    
    async def create_location_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the location selection embed."""
        conf = self.cog.db.get_conf(guild)
        user_data = conf.get_user(self.author)
        
        # Get game time and weather
        calendar = get_game_calendar(self.cog.db, guild)
        time_of_day = get_game_time_of_day(self.cog.db, guild)
        weather = get_weather_for_guild(
            self.cog.db, 
            guild, 
            calendar['season'], 
            time_of_day['name'],
            calendar['total_game_days']
        )
        
        embed = discord.Embed(
            title="🎣 Choose Your Fishing Spot",
            description=(
                f"Where would you like to fish today?\n\n"
                f"**Current Weather:** {get_weather_display(weather)}\n"
                f"*{weather['description']}*"
            ),
            color=discord.Color.blue()
        )
        
        # Add location descriptions
        locations_text = ""
        for loc_id, loc_data in FISHING_LOCATIONS.items():
            locations_text += f"{loc_data['emoji']} **{loc_data['name']}** - {loc_data['description']}\n"
        
        embed.add_field(
            name="📍 Available Locations",
            value=locations_text,
            inline=False
        )
        
        embed.set_footer(text="Select a location to start fishing!")
        
        return embed
    
    async def _go_to_location(self, interaction: discord.Interaction, location: str):
        """Navigate to the selected fishing location."""
        new_view = FishingView(cog=self.cog, author=self.author, location=location)
        embed = await new_view.create_fishing_embed(interaction.guild)
        await self.stop_and_update(interaction, new_view, embed)
    
    # Row 0: Location buttons
    @discord.ui.button(label="Pond", style=discord.ButtonStyle.primary, emoji="🏞️", row=0)
    async def select_pond(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Select the pond location."""
        await self._go_to_location(interaction, "pond")
    
    @discord.ui.button(label="Lake", style=discord.ButtonStyle.primary, emoji="🌊", row=0)
    async def select_lake(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Select the lake location."""
        await self._go_to_location(interaction, "lake")
    
    @discord.ui.button(label="River", style=discord.ButtonStyle.primary, emoji="🏔️", row=0)
    async def select_river(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Select the river location."""
        await self._go_to_location(interaction, "river")
    
    @discord.ui.button(label="Ocean", style=discord.ButtonStyle.primary, emoji="🌅", row=0)
    async def select_ocean(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Select the ocean location."""
        await self._go_to_location(interaction, "ocean")
    
    # Row 1: Go Back button is added by BackToMenuMixin


class FishingView(BackToMenuMixin, BaseView):
    """View for the fishing session at a specific location."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        location: str = "pond"
    ):
        super().__init__(cog=cog, author=author)
        self.location = location
        self.location_data = FISHING_LOCATIONS.get(location, FISHING_LOCATIONS["pond"])
    
    async def create_fishing_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the fishing session embed."""
        conf = self.cog.db.get_conf(guild)
        user_data = conf.get_user(self.author)
        
        # Get game time and weather
        calendar = get_game_calendar(self.cog.db, guild)
        time_of_day = get_game_time_of_day(self.cog.db, guild)
        weather = get_weather_for_guild(
            self.cog.db, 
            guild, 
            calendar['season'], 
            time_of_day['name'],
            calendar['total_game_days']
        )
        
        embed = discord.Embed(
            title=f"{self.location_data['emoji']} {self.location_data['name']}",
            description=(
                f"*{self.location_data['description']}*\n\n"
                f"**Weather:** {get_weather_display(weather)}\n"
                f"*{weather['description']}*"
            ),
            color=discord.Color.green()
        )
        
        # Add location thumbnail
        embed.set_thumbnail(url=self.location_data['thumbnail'])
        
        embed.add_field(
            name="🎒 Your Gear",
            value=(
                f"🎣 Rods: **{len(user_data.current_rod_inventory)}**\n"
                f"🪝 Lures: **{len(user_data.current_lure_inventory)}**"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🐟 Your Catch",
            value=f"Fish in bucket: **{len(user_data.current_fish_inventory)}**",
            inline=True
        )
        
        embed.add_field(
            name="💧 Water Type",
            value=f"**{self.location_data['water_type'].title()}**",
            inline=True
        )
        
        embed.set_footer(text="Cast your line and see what you catch!")
        
        return embed
    
    @discord.ui.button(label="Cast Line", style=discord.ButtonStyle.success, emoji="🎣", row=0)
    async def cast_line_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cast the fishing line and start fishing."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        # Check if player has equipped rod and lure
        equipped_rod = user_data.get_equipped_rod()
        equipped_lure = user_data.get_equipped_lure()
        
        if not equipped_rod:
            await interaction.response.send_message(
                "❌ You need to equip a rod first! Use Change Gear.",
                ephemeral=True
            )
            return
        
        if not equipped_lure or equipped_lure.get("quantity", 0) <= 0:
            await interaction.response.send_message(
                "❌ You need bait! Visit the Bait Shop to buy some.",
                ephemeral=True
            )
            return
        
        # Check rod durability
        if equipped_rod.get("durability", 0) <= 0:
            await interaction.response.send_message(
                "❌ Your rod is broken! Buy a new one at the Bait Shop.",
                ephemeral=True
            )
            return
        
        # Check if rod is compatible with this water type
        from ..databases.items import RODS_DATABASE
        rod_id = equipped_rod.get("rod_id", "")
        rod_info = RODS_DATABASE.get(rod_id, {})
        rod_water_type = rod_info.get("water_type", "both")
        location_water_type = self.location_data.get("water_type", "freshwater")
        location_name = self.location_data.get("name", "this location")
        
        # Check compatibility
        rod_compatible = False
        if rod_water_type == "both":
            rod_compatible = True
        elif rod_water_type == "freshwater" and location_water_type == "freshwater":
            rod_compatible = True
        elif rod_water_type == "saltwater" and location_water_type == "saltwater":
            rod_compatible = True
        elif rod_water_type == "river_only" and self.location == "river":
            rod_compatible = True
        elif rod_water_type == "ocean_only" and self.location == "ocean":
            rod_compatible = True
        
        if not rod_compatible:
            rod_name = rod_info.get("name", "Your rod")
            await interaction.response.send_message(
                f"❌ **{rod_name}** isn't suited for {location_name}!\n"
                f"This rod is designed for: **{rod_water_type.replace('_', ' ').title()}**\n"
                f"Use **Change Gear** to equip a different rod.",
                ephemeral=True
            )
            return
        
        # Calculate luck bonus from equipped gear (hat, coat, boots)
        luck_bonus = calculate_gear_luck_bonus(user_data)
        
        # Increment fishing attempts counter
        user_data.total_fishing_attempts += 1
        self.cog.save()
        
        # Start active fishing!
        new_view = ActiveFishingView(
            cog=self.cog,
            author=self.author,
            location=self.location,
            location_data=self.location_data,
            luck_bonus=luck_bonus
        )
        embed = await new_view.create_fishing_embed(interaction.guild)
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Change Gear", style=discord.ButtonStyle.secondary, emoji="🔧", row=0)
    async def change_gear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Change equipped gear."""
        new_view = ChangeGearView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_gear_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    # Override BackToMenuMixin to go back to location select instead
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=4)
    async def back_to_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to location selection."""
        new_view = LocationSelectView(cog=self.cog, author=self.author)
        embed = await new_view.create_location_embed(interaction.guild)
        await self.stop_and_update(interaction, new_view, embed)


class ChangeGearView(BaseView):
    """View for changing equipped gear."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        location: str = "pond"
    ):
        super().__init__(cog=cog, author=author)
        self.location = location
    
    async def create_gear_embed(self) -> discord.Embed:
        """Create the gear selection embed."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        from ..databases.items import RODS_DATABASE, LURES_DATABASE
        
        embed = discord.Embed(
            title="🔧 Change Gear",
            description="Select a gear category to swap your equipped items.",
            color=discord.Color.orange()
        )
        
        # Show currently equipped rod
        equipped_rod = user_data.get_equipped_rod()
        if equipped_rod:
            rod_info = RODS_DATABASE.get(equipped_rod.get("rod_id", ""), {})
            rod_name = rod_info.get("name", "Unknown Rod")
            rod_durability = equipped_rod.get("durability", 0)
            rod_max = rod_info.get("durability", 100)
            embed.add_field(
                name="🎣 Equipped Rod",
                value=f"**{rod_name}**\nDurability: {rod_durability}/{rod_max}",
                inline=True
            )
        else:
            embed.add_field(
                name="🎣 Equipped Rod",
                value="*None equipped*",
                inline=True
            )
        
        # Show currently equipped lure
        equipped_lure = user_data.get_equipped_lure()
        if equipped_lure:
            from ..commands.helper_functions import ensure_lure_uses
            ensure_lure_uses(equipped_lure)
            
            lure_info = LURES_DATABASE.get(equipped_lure.get("lure_id", ""), {})
            lure_name = lure_info.get("name", "Unknown Lure")
            remaining_uses = equipped_lure.get("remaining_uses", 0)
            uses_per_item = equipped_lure.get("uses_per_item", 1)
            max_uses = equipped_lure.get("quantity", 0) * uses_per_item
            embed.add_field(
                name="🪝 Equipped Lure",
                value=f"**{lure_name}**\n{remaining_uses}/{max_uses} uses",
                inline=True
            )
        else:
            embed.add_field(
                name="🪝 Equipped Lure",
                value="*None equipped*",
                inline=True
            )
        
        embed.set_footer(text="Choose a category below to change your gear.")
        
        return embed
    
    @discord.ui.button(label="Change Rod", style=discord.ButtonStyle.primary, emoji="🎣", row=0)
    async def change_rod(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Change equipped rod."""
        new_view = SelectRodView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_rod_select_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Change Lure", style=discord.ButtonStyle.primary, emoji="🪝", row=0)
    async def change_lure(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Change equipped lure."""
        new_view = SelectLureView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_lure_select_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def back_to_fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to fishing view."""
        new_view = FishingView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_fishing_embed(interaction.guild)
        await self.stop_and_update(interaction, new_view, embed)


class SelectRodView(BaseView):
    """View for selecting a rod to equip."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        location: str = "pond"
    ):
        super().__init__(cog=cog, author=author)
        self.location = location
        self._add_rod_select()
    
    def _add_rod_select(self):
        """Add the rod selection dropdown."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        from ..databases.items import RODS_DATABASE
        
        options = []
        for idx, rod in enumerate(user_data.current_rod_inventory):
            rod_id = rod.get("rod_id", "")
            rod_info = RODS_DATABASE.get(rod_id, {})
            rod_name = rod_info.get("name", "Unknown Rod")
            durability = rod.get("durability", 0)
            max_dur = rod_info.get("durability", 100)
            
            is_equipped = user_data.equipped_rod_index == idx
            label = f"{rod_name} ({durability}/{max_dur})"
            if is_equipped:
                label = f"✓ {label}"
            
            options.append(discord.SelectOption(
                label=label[:100],
                value=str(idx),
                description=f"Power: {rod_info.get('power', 'N/A')} | Action: {rod_info.get('action', 'N/A')}",
                default=is_equipped
            ))
        
        if options:
            select = discord.ui.Select(
                placeholder="Select a rod to equip...",
                options=options,
                row=0
            )
            select.callback = self.rod_selected
            self.add_item(select)
    
    async def create_rod_select_embed(self) -> discord.Embed:
        """Create the rod selection embed."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        embed = discord.Embed(
            title="🎣 Select Rod",
            description="Choose a rod from your inventory to equip.",
            color=discord.Color.blue()
        )
        
        if not user_data.current_rod_inventory:
            embed.description = "You don't have any rods! Visit the Bait Shop to buy one."
        
        return embed
    
    async def rod_selected(self, interaction: discord.Interaction):
        """Handle rod selection."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        selected_idx = int(interaction.data["values"][0])
        user_data.equip_rod(selected_idx)
        self.cog.save()
        
        # Go back to gear view
        new_view = ChangeGearView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_gear_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def back_to_gear(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to gear selection."""
        new_view = ChangeGearView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_gear_embed()
        await self.stop_and_update(interaction, new_view, embed)


class SelectLureView(BaseView):
    """View for selecting a lure to equip."""
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        location: str = "pond"
    ):
        super().__init__(cog=cog, author=author)
        self.location = location
        self._add_lure_select()
    
    def _add_lure_select(self):
        """Add the lure selection dropdown."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        from ..databases.items import LURES_DATABASE
        from ..commands.helper_functions import ensure_lure_uses
        
        options = []
        for idx, lure in enumerate(user_data.current_lure_inventory):
            lure_id = lure.get("lure_id", "")
            lure_info = LURES_DATABASE.get(lure_id, {})
            lure_name = lure_info.get("name", "Unknown Lure")
            
            # Ensure uses tracking
            ensure_lure_uses(lure)
            remaining_uses = lure.get("remaining_uses", 0)
            uses_per_item = lure.get("uses_per_item", 1)
            max_uses = lure.get("quantity", 0) * uses_per_item
            
            is_equipped = user_data.equipped_lure_index == idx
            label = f"{lure_name} ({remaining_uses}/{max_uses})"
            if is_equipped:
                label = f"✓ {label}"
            
            water_type = lure_info.get("water_type", "universal")
            options.append(discord.SelectOption(
                label=label[:100],
                value=str(idx),
                description=f"Water: {water_type.title()} | Type: {lure_info.get('type', 'N/A')}",
                default=is_equipped
            ))
        
        if options:
            select = discord.ui.Select(
                placeholder="Select a lure to equip...",
                options=options,
                row=0
            )
            select.callback = self.lure_selected
            self.add_item(select)
    
    async def create_lure_select_embed(self) -> discord.Embed:
        """Create the lure selection embed."""
        conf = self.cog.db.get_conf(self.author.guild)
        user_data = conf.get_user(self.author)
        
        embed = discord.Embed(
            title="🪝 Select Lure",
            description="Choose a lure from your inventory to equip.",
            color=discord.Color.blue()
        )
        
        if not user_data.current_lure_inventory:
            embed.description = "You don't have any lures! Visit the Bait Shop to buy some."
        
        return embed
    
    async def lure_selected(self, interaction: discord.Interaction):
        """Handle lure selection."""
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        selected_idx = int(interaction.data["values"][0])
        user_data.equip_lure(selected_idx)
        self.cog.save()
        
        # Go back to gear view
        new_view = ChangeGearView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_gear_embed()
        await self.stop_and_update(interaction, new_view, embed)
    
    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary, emoji="◀️", row=1)
    async def back_to_gear_lure(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Return to gear selection from lure view."""
        new_view = ChangeGearView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_gear_embed()
        await self.stop_and_update(interaction, new_view, embed)


# =============================================================================
# ACTIVE FISHING VIEW - Dynamic fishing gameplay
# =============================================================================

class ActiveFishingView(BaseView):
    """
    Dynamic fishing view that handles the actual fishing gameplay.
    Buttons change based on the current fishing phase.
    """
    
    def __init__(
        self, 
        cog: "GreenacresFishing",
        author: discord.Member,
        location: str = "pond",
        location_data: dict = None,
        luck_bonus: int = 0
    ):
        super().__init__(cog=cog, author=author, timeout=120.0)  # 2 min timeout for fishing
        self.location = location
        self.location_data = location_data or FISHING_LOCATIONS.get(location, FISHING_LOCATIONS["pond"])
        self.luck_bonus = luck_bonus  # Store for session resets
        
        # Create fishing session with luck bonus
        self.session = create_fishing_session(
            location=location,
            water_type=self.location_data.get("water_type", "freshwater"),
            luck_bonus=luck_bonus
        )
        
        # Timing control
        self._waiting_for_bite = False
        self._waiting_for_strike = False
        
        # Click spam prevention - only one action at a time
        self._processing = False
        
        # Track last user interaction to prevent auto-updates from keeping view alive forever
        self._last_user_interaction: float = time.time()
        self._user_timeout_seconds: float = 120.0  # 2 minutes of no user clicks = timeout
        
        # Task tracking for proper cancellation
        self._bite_task: Optional[asyncio.Task] = None
        self._hook_task: Optional[asyncio.Task] = None
        self._fight_task: Optional[asyncio.Task] = None
        self._tension_task: Optional[asyncio.Task] = None
        
        # Initialize buttons
        self._update_buttons()
    
    async def _check_processing(self, interaction: discord.Interaction) -> bool:
        """
        Check if we're already processing an action.
        Returns True if we should block this interaction.
        """
        if self._processing:
            # Already processing, ignore this click
            try:
                await interaction.response.defer()
            except:
                pass
            return True
        return False
    
    def _cancel_all_tasks(self):
        """Cancel all running async tasks to prevent them from continuing after view closes."""
        tasks_to_cancel = [
            self._bite_task,
            self._hook_task,
            self._fight_task,
            self._tension_task
        ]
        
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()
        
        # Clear references
        self._bite_task = None
        self._hook_task = None
        self._fight_task = None
        self._tension_task = None
    
    def _should_timeout_from_inactivity(self) -> bool:
        """Check if user has been inactive for too long."""
        return (time.time() - self._last_user_interaction) > self._user_timeout_seconds
    
    def _update_user_interaction(self):
        """Update timestamp when user clicks a button."""
        self._last_user_interaction = time.time()
    
    async def _disable_buttons_and_stop(self):
        """Disable all buttons, update the message, then stop the view."""
        # Disable all buttons
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        
        # Update the message to show disabled buttons
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass
        
        # Now stop the view
        self.stop()
    
    async def create_fishing_embed(self, guild: discord.Guild) -> discord.Embed:
        """Create the active fishing embed."""
        from ..commands.helper_functions import ensure_lure_uses
        
        conf = self.cog.db.get_conf(guild)
        user_data = conf.get_user(self.author)
        
        # Get equipped lure info
        equipped_lure = user_data.get_equipped_lure()
        if equipped_lure:
            ensure_lure_uses(equipped_lure)
            lure_id = equipped_lure.get("lure_id", "")
            lure_info = LURES_DATABASE.get(lure_id, {})
            lure_name = lure_info.get("name", "Unknown Bait")
            remaining_uses = equipped_lure.get("remaining_uses", 0)
            uses_per_item = equipped_lure.get("uses_per_item", 1)
            max_uses = equipped_lure.get("quantity", 0) * uses_per_item
            lure_display = f"{remaining_uses}/{max_uses}"
        else:
            lure_name = "None"
            lure_display = "0/0"
        
        # Build embed
        embed = discord.Embed(
            title=f"🎣 Fishing at {self.location_data['name']}",
            color=discord.Color.blue()
        )
        
        embed.set_thumbnail(url=self.location_data.get("thumbnail", ""))
        
        # Status section - show recent messages
        if self.session.status_messages:
            status_text = "\n".join(self.session.status_messages[-3:])
        else:
            status_text = "*Ready to cast your line...*"
        
        embed.description = status_text
        
        # Stats field
        stats_text = (
            f"📏 Line Distance: **{self.session.line_distance} ft**\n"
            f"🪝 Bait: **{lure_name}** ({lure_display} uses)\n"
            f"✅ Successful: **{self.session.successful_interactions}**\n"
            f"❌ Mistakes: **{self.session.botched_attempts}/{self.session.max_botched}**"
        )
        embed.add_field(name="📊 Status", value=stats_text, inline=True)
        
        # Phase indicator
        phase_names = {
            FishingPhase.IDLE: "🔵 Ready",
            FishingPhase.CASTING: "🟡 Casting...",
            FishingPhase.WAITING: "🟡 Waiting for bite...",
            FishingPhase.RETRIEVING: "🟡 Retrieving...",
            FishingPhase.FISH_FOLLOWING: "🟠 Something following!",
            FishingPhase.FISH_STRIKE: "🔴 FISH ON! Set the hook!",
            FishingPhase.FIGHTING: "🔴 Fighting fish!",
            FishingPhase.TENSION_HIGH: "⚠️ HIGH TENSION - Don't reel!",
            FishingPhase.LANDED: "🟢 Fish Landed!",
            FishingPhase.ESCAPED: "⚫ Fish Escaped...",
        }
        phase_display = phase_names.get(self.session.phase, "Unknown")
        embed.add_field(name="🎯 Phase", value=phase_display, inline=True)
        
        return embed
    
    def _update_buttons(self):
        """Update visible buttons based on current phase."""
        # Clear all items first
        self.clear_items()
        
        phase = self.session.phase
        
        if phase == FishingPhase.IDLE:
            # Show Cast Line button
            cast_btn = discord.ui.Button(
                label="Cast Line",
                style=discord.ButtonStyle.success,
                emoji="🎣",
                row=0
            )
            cast_btn.callback = self._on_cast_line
            self.add_item(cast_btn)
            
        elif phase in (FishingPhase.WAITING, FishingPhase.RETRIEVING):
            # Show Retrieve button
            retrieve_btn = discord.ui.Button(
                label="Retrieve",
                style=discord.ButtonStyle.primary,
                emoji="🔄",
                row=0
            )
            retrieve_btn.callback = self._on_retrieve
            self.add_item(retrieve_btn)
            
        elif phase == FishingPhase.FISH_FOLLOWING:
            # Show Retrieve button (fish might strike)
            retrieve_btn = discord.ui.Button(
                label="Retrieve",
                style=discord.ButtonStyle.primary,
                emoji="🔄",
                row=0
            )
            retrieve_btn.callback = self._on_retrieve_with_fish
            self.add_item(retrieve_btn)
            
        elif phase == FishingPhase.FISH_STRIKE:
            # Show Set Hook button (urgent!)
            hook_btn = discord.ui.Button(
                label="SET HOOK!",
                style=discord.ButtonStyle.danger,
                emoji="🪝",
                row=0
            )
            hook_btn.callback = self._on_set_hook
            self.add_item(hook_btn)
            
        elif phase == FishingPhase.FIGHTING:
            # Show Reel In button
            reel_btn = discord.ui.Button(
                label="Reel In",
                style=discord.ButtonStyle.success,
                emoji="🎣",
                row=0
            )
            reel_btn.callback = self._on_reel_in
            self.add_item(reel_btn)
            
        elif phase == FishingPhase.TENSION_HIGH:
            # Show Reel In button - player can make a mistake!
            # The label warns them but they can still click it
            reel_btn = discord.ui.Button(
                label="Reel In",
                style=discord.ButtonStyle.danger,  # Red to indicate danger
                emoji="⚠️",
                row=0
            )
            reel_btn.callback = self._on_reel_during_tension
            self.add_item(reel_btn)
            
        elif phase in (FishingPhase.LANDED, FishingPhase.ESCAPED):
            # Show Continue button
            continue_btn = discord.ui.Button(
                label="Continue Fishing",
                style=discord.ButtonStyle.success,
                emoji="🎣",
                row=0
            )
            continue_btn.callback = self._on_continue
            self.add_item(continue_btn)
        
        # Always show Stop Fishing button (except when landed/escaped)
        if phase not in (FishingPhase.LANDED, FishingPhase.ESCAPED):
            stop_btn = discord.ui.Button(
                label="Stop Fishing",
                style=discord.ButtonStyle.danger,
                emoji="🛑",
                row=1
            )
            stop_btn.callback = self._on_stop_fishing
            self.add_item(stop_btn)
        else:
            # Show Back to Location button
            back_btn = discord.ui.Button(
                label="Back to Location",
                style=discord.ButtonStyle.secondary,
                emoji="◀️",
                row=1
            )
            back_btn.callback = self._on_back_to_location
            self.add_item(back_btn)
    
    async def _refresh_view(self, interaction: discord.Interaction):
        """Refresh the embed and buttons."""
        self._update_buttons()
        embed = await self.create_fishing_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _on_cast_line(self, interaction: discord.Interaction):
        """Handle Cast Line button."""
        # Prevent click spam
        if await self._check_processing(interaction):
            return
        self._processing = True
        
        # Track user interaction
        self._update_user_interaction()
        
        try:
            # Check bait before casting
            conf = self.cog.db.get_conf(interaction.guild)
            user_data = conf.get_user(self.author)
            
            equipped_lure = user_data.get_equipped_lure()
            if not equipped_lure or equipped_lure.get("quantity", 0) <= 0:
                # No bait! Unequip and send back to location
                user_data.equipped_lure_index = None
                self.cog.save()
                
                await interaction.response.send_message(
                    "❌ You're out of bait! Visit the Bait Shop to buy more.",
                    ephemeral=True
                )
                
                # Return to location view
                self.stop()
                new_view = FishingView(cog=self.cog, author=self.author, location=self.location)
                embed = await new_view.create_fishing_embed(interaction.guild)
                new_view.message = self.message
                await self.message.edit(embed=embed, view=new_view)
                return
            
            # Increment fishing attempts counter
            user_data.total_fishing_attempts += 1
            self.cog.save()
            
            # Cast the line
            cast_line(self.session)
            
            # Update view
            self._update_buttons()
            embed = await self.create_fishing_embed(interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Start waiting for bite (10 second delay)
            # Cancel any existing bite task first
            if self._bite_task and not self._bite_task.done():
                self._bite_task.cancel()
            
            self._waiting_for_bite = True
            self._bite_task = asyncio.create_task(self._wait_for_bite(interaction))
        finally:
            self._processing = False
    
    async def _wait_for_bite(self, interaction: discord.Interaction):
        """Wait for a fish to show interest."""
        await asyncio.sleep(10)  # 10 second wait
        
        # Check if view is still active
        if not self.is_active():
            return
        
        if not self._waiting_for_bite or self.session.phase != FishingPhase.WAITING:
            return
        
        self._waiting_for_bite = False
        
        # Get game conditions
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        calendar = get_game_calendar(self.cog.db, interaction.guild)
        time_of_day = get_game_time_of_day(self.cog.db, interaction.guild)
        weather = get_weather_for_guild(
            self.cog.db,
            interaction.guild,
            calendar['season'],
            time_of_day['name'],
            calendar['total_game_days']
        )
        
        equipped_lure = user_data.get_equipped_lure()
        bait_id = equipped_lure.get("lure_id", "") if equipped_lure else ""
        
        # Check for bite
        interested, msg = check_for_bite(
            self.session,
            calendar['season'],
            weather['type'].value if hasattr(weather['type'], 'value') else str(weather['type']),
            bait_id
        )
        
        # Check again if view is still active before editing
        if not self.is_active():
            return
        
        # Update display
        self._update_buttons()
        embed = await self.create_fishing_embed(interaction.guild)
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            return
        except discord.HTTPException:
            return
        
        # If nothing biting, automatically wait and check again
        if not interested and self.session.phase == FishingPhase.WAITING and self.is_active():
            # Cancel any existing bite task before starting a new one
            if self._bite_task and not self._bite_task.done():
                self._bite_task.cancel()
            
            self._waiting_for_bite = True
            self._bite_task = asyncio.create_task(self._wait_for_bite(interaction))
    
    async def _on_retrieve(self, interaction: discord.Interaction):
        """Handle Retrieve button (no fish following)."""
        # Prevent click spam
        if await self._check_processing(interaction):
            return
        self._processing = True
        
        # Track user interaction
        self._update_user_interaction()
        
        try:
            retrieve_line(self.session)
            
            if self.session.line_distance <= 0:
                # Line fully retrieved, back to idle
                self.session.phase = FishingPhase.IDLE
            
            self._update_buttons()
            embed = await self.create_fishing_embed(interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)
            
            # If still waiting phase, restart the timer
            if self.session.phase in (FishingPhase.WAITING, FishingPhase.RETRIEVING):
                self.session.phase = FishingPhase.WAITING
                
                # Cancel any existing bite task before starting a new one
                if self._bite_task and not self._bite_task.done():
                    self._bite_task.cancel()
                
                self._waiting_for_bite = True
                self._bite_task = asyncio.create_task(self._wait_for_bite(interaction))
        finally:
            self._processing = False
    
    async def _on_retrieve_with_fish(self, interaction: discord.Interaction):
        """Handle Retrieve button when fish is following."""
        # Prevent click spam
        if await self._check_processing(interaction):
            return
        self._processing = True
        
        # Track user interaction
        self._update_user_interaction()
        
        try:
            retrieve_line(self.session)
            
            # Get game conditions for fish strike
            conf = self.cog.db.get_conf(interaction.guild)
            user_data = conf.get_user(self.author)
            calendar = get_game_calendar(self.cog.db, interaction.guild)
            time_of_day = get_game_time_of_day(self.cog.db, interaction.guild)
            weather = get_weather_for_guild(
                self.cog.db,
                interaction.guild,
                calendar['season'],
                time_of_day['name'],
                calendar['total_game_days']
            )
            
            equipped_lure = user_data.get_equipped_lure()
            bait_id = equipped_lure.get("lure_id", "") if equipped_lure else ""
            
            # Check if fish strikes (50/50)
            fish_id, fish_data, msg = fish_strikes(
                self.session,
                calendar['season'],
                weather['type'].value if hasattr(weather['type'], 'value') else str(weather['type']),
                bait_id
            )
            
            self._update_buttons()
            embed = await self.create_fishing_embed(interaction.guild)
            await interaction.response.edit_message(embed=embed, view=self)
            
            # If fish struck, start the hook timeout
            if fish_id and self.is_active():
                # Cancel any existing hook task before starting a new one
                if self._hook_task and not self._hook_task.done():
                    self._hook_task.cancel()
                
                self._waiting_for_strike = True
                self._hook_task = asyncio.create_task(self._wait_for_hook_set(interaction))
            elif self.session.phase == FishingPhase.WAITING and self.is_active():
                # Fish swam away - restart waiting for bite
                # Cancel any existing bite task before starting a new one
                if self._bite_task and not self._bite_task.done():
                    self._bite_task.cancel()
                
                self._waiting_for_bite = True
                self._bite_task = asyncio.create_task(self._wait_for_bite(interaction))
        finally:
            self._processing = False
    
    async def _wait_for_hook_set(self, interaction: discord.Interaction):
        """Wait for player to set hook (5 second timeout)."""
        await asyncio.sleep(5)
        
        # Check if view is still active
        if not self.is_active():
            return
        
        if not self._waiting_for_strike or self.session.phase != FishingPhase.FISH_STRIKE:
            return
        
        self._waiting_for_strike = False
        
        # Player didn't set hook in time!
        self.session.phase = FishingPhase.WAITING
        self.session.fish_id = None
        self.session.fish_data = None
        self.session.timeout_seconds = 3.0
        self.session.add_message("*Too slow! The fish spits out the hook and swims away.*")
        
        # Check again before editing
        if not self.is_active():
            return
        
        self._update_buttons()
        embed = await self.create_fishing_embed(interaction.guild)
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass
        except discord.HTTPException:
            pass
    
    async def _on_set_hook(self, interaction: discord.Interaction):
        """Handle Set Hook button."""
        # Prevent click spam
        if await self._check_processing(interaction):
            return
        self._processing = True
        
        # Track user interaction
        self._update_user_interaction()
        
        try:
            self._waiting_for_strike = False
            
            # Cancel hook timeout task if it's running
            if self._hook_task and not self._hook_task.done():
                self._hook_task.cancel()
                self._hook_task = None
            
            success, msg = attempt_set_hook(self.session)
            
            self._update_buttons()
            embed = await self.create_fishing_embed(interaction.guild)
            
            message_updated = False
            try:
                await interaction.response.edit_message(embed=embed, view=self)
                message_updated = True
            except (discord.NotFound, discord.HTTPException):
                # Interaction failed, try direct message edit
                try:
                    await self.message.edit(embed=embed, view=self)
                    message_updated = True
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # Only start fight sequence if message was updated successfully and hook was set
            if success and message_updated:
                # Cancel any existing fight task before starting a new one
                if self._fight_task and not self._fight_task.done():
                    self._fight_task.cancel()
                
                # Start the fight!
                self._fight_task = asyncio.create_task(self._start_fight_sequence(interaction))
        finally:
            self._processing = False
    
    async def _start_fight_sequence(self, interaction: discord.Interaction):
        """Start the fish fighting sequence."""
        await asyncio.sleep(2)  # Brief pause
        
        # Check if view is still active
        if not self.is_active():
            self.session.add_message("DEBUG: Fight stopped - view not active")
            return
        
        # Check if user has been inactive too long
        if self._should_timeout_from_inactivity():
            self.session.add_message("*You've been idle too long. The fish escapes!*")
            self.session.phase = FishingPhase.ESCAPED
            self._cancel_all_tasks()
            await self._disable_buttons_and_stop()
            return
        
        if self.session.phase not in (FishingPhase.FIGHTING, FishingPhase.TENSION_HIGH):
            return
        
        # Check if fish is very close - stop auto-events and let player finish reeling
        # Only stop when fish is at 0 feet (about to be landed)
        if self.session.line_distance <= 0:
            # Fish is landed - no more auto-events
            return
        
        # Wait for any user interactions to complete before updating
        max_wait = 10  # Maximum 1 second wait
        wait_count = 0
        while self._processing and wait_count < max_wait:
            await asyncio.sleep(0.1)
            wait_count += 1
        
        if not self.is_active():
            return
        
        # Get next fight event
        phase, msg, should_reel = get_fight_event(self.session)
        
        # Check again before editing
        if not self.is_active():
            return
        
        self._update_buttons()
        embed = await self.create_fishing_embed(interaction.guild)
        try:
            await self.message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.HTTPException):
            return
        
        # If tension high, wait for timeout then process
        if phase == FishingPhase.TENSION_HIGH and self.is_active():
            # Cancel any existing tension task before starting a new one
            if self._tension_task and not self._tension_task.done():
                self._tension_task.cancel()
            
            self._tension_task = asyncio.create_task(self._wait_for_tension_release(interaction))
        elif phase == FishingPhase.FIGHTING and self.is_active():
            # Continue the fight sequence - just create new task, don't cancel current one
            self._fight_task = asyncio.create_task(self._start_fight_sequence(interaction))
    
    async def _wait_for_tension_release(self, interaction: discord.Interaction):
        """Wait during high tension phase."""
        await asyncio.sleep(3)  # 3 second wait
        
        # Check if view is still active
        if not self.is_active():
            return
        
        # Check if user has been inactive too long
        if self._should_timeout_from_inactivity():
            self.session.add_message("*You've been idle too long. The fish escapes!*")
            self.session.phase = FishingPhase.ESCAPED
            self._cancel_all_tasks()
            await self._disable_buttons_and_stop()
            return
        
        if self.session.phase != FishingPhase.TENSION_HIGH:
            return
        
        # Wait for any user interactions to complete before updating
        max_wait = 10  # Maximum 1 second wait
        wait_count = 0
        while self._processing and wait_count < max_wait:
            await asyncio.sleep(0.1)
            wait_count += 1
        
        if not self.is_active():
            return
        
        # Player waited correctly
        success, msg, landed = process_reel_attempt(self.session, did_reel=False)
        
        # Check again before editing
        if not self.is_active():
            return
        
        self._update_buttons()
        embed = await self.create_fishing_embed(interaction.guild)
        try:
            await self.message.edit(embed=embed, view=self)
        except (discord.NotFound, discord.HTTPException):
            return
        
        if self.session.phase == FishingPhase.FIGHTING and self.is_active():
            # Continue fight - just create new task, don't cancel current one
            self._fight_task = asyncio.create_task(self._start_fight_sequence(interaction))
    
    async def _on_reel_during_tension(self, interaction: discord.Interaction):
        """Handle Reel In button during high tension - this is a MISTAKE!"""
        # Prevent click spam
        if await self._check_processing(interaction):
            return
        self._processing = True
        
        # Track user interaction
        self._update_user_interaction()
        
        try:
            # Cancel tension task if player clicked during it
            if self._tension_task and not self._tension_task.done():
                self._tension_task.cancel()
                self._tension_task = None
            
            conf = self.cog.db.get_conf(interaction.guild)
            user_data = conf.get_user(self.author)
            
            # Player made a mistake - reeling during high tension!
            success, msg, landed = process_reel_attempt(self.session, did_reel=True)
            
            if self.session.phase == FishingPhase.ESCAPED:
                # Line snapped from the mistake
                snap_msg, rod_broke = handle_line_snap(self.session, user_data)
                self.cog.save()
                
                # If rod broke, disable all buttons and stop fishing
                if rod_broke:
                    self._disable_all_buttons()
            
            self._update_buttons()
            embed = await self.create_fishing_embed(interaction.guild)
            
            message_updated = False
            try:
                await interaction.response.edit_message(embed=embed, view=self)
                message_updated = True
            except (discord.NotFound, discord.HTTPException):
                # Interaction failed, try direct message edit
                try:
                    await self.message.edit(embed=embed, view=self)
                    message_updated = True
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # If still fighting (just got a warning), continue sequence - only if message updated
            if message_updated and self.session.phase in (FishingPhase.FIGHTING, FishingPhase.TENSION_HIGH) and self.is_active():
                # Cancel old fight task and start new one
                if self._fight_task and not self._fight_task.done():
                    self._fight_task.cancel()
                
                self._fight_task = asyncio.create_task(self._start_fight_sequence(interaction))
        finally:
            self._processing = False
    
    async def _on_reel_in(self, interaction: discord.Interaction):
        """Handle Reel In button during fight."""
        # Prevent click spam
        if await self._check_processing(interaction):
            return
        self._processing = True
        
        # Track user interaction
        self._update_user_interaction()
        
        try:
            conf = self.cog.db.get_conf(interaction.guild)
            user_data = conf.get_user(self.author)
            
            success, msg, landed = process_reel_attempt(self.session, did_reel=True)
            
            if landed:
                # Fish is landed!
                land_msg, is_record, earned_token = land_the_fish(self.session, user_data)
                self.cog.save()
            elif self.session.phase == FishingPhase.ESCAPED:
                # Line snapped
                snap_msg, rod_broke = handle_line_snap(self.session, user_data)
                self.cog.save()
                
                # If rod broke, disable all buttons and stop fishing
                if rod_broke:
                    self._disable_all_buttons()
            
            self._update_buttons()
            embed = await self.create_fishing_embed(interaction.guild)
            
            message_updated = False
            try:
                await interaction.response.edit_message(embed=embed, view=self)
                message_updated = True
            except (discord.NotFound, discord.HTTPException):
                # Interaction failed, try direct message edit
                try:
                    await self.message.edit(embed=embed, view=self)
                    message_updated = True
                except (discord.NotFound, discord.HTTPException):
                    pass
            
            # If still fighting, continue sequence - only if message updated
            if message_updated and self.session.phase in (FishingPhase.FIGHTING, FishingPhase.TENSION_HIGH) and self.is_active():
                # Cancel old fight task and start new one
                if self._fight_task and not self._fight_task.done():
                    self._fight_task.cancel()
                
                self._fight_task = asyncio.create_task(self._start_fight_sequence(interaction))
        finally:
            self._processing = False
    
    async def _on_continue(self, interaction: discord.Interaction):
        """Handle Continue Fishing button."""
        # Check if player still has bait
        conf = self.cog.db.get_conf(interaction.guild)
        user_data = conf.get_user(self.author)
        
        equipped_lure = user_data.get_equipped_lure()
        if not equipped_lure or equipped_lure.get("quantity", 0) <= 0:
            # No bait! Unequip and send back to location
            user_data.equipped_lure_index = None
            self.cog.save()
            
            await interaction.response.send_message(
                "❌ You're out of bait! Visit the Bait Shop to buy more.",
                ephemeral=True
            )
            
            # Return to location view
            self.stop()
            new_view = FishingView(cog=self.cog, author=self.author, location=self.location)
            embed = await new_view.create_fishing_embed(interaction.guild)
            new_view.message = self.message
            await self.message.edit(embed=embed, view=new_view)
            return
        
        # Reset session for new cast (keep same luck bonus)
        self.session = create_fishing_session(
            location=self.location,
            water_type=self.location_data.get("water_type", "freshwater"),
            luck_bonus=self.luck_bonus
        )
        
        self._update_buttons()
        embed = await self.create_fishing_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _on_stop_fishing(self, interaction: discord.Interaction):
        """Handle Stop Fishing button - return to location."""
        self._waiting_for_bite = False
        self._waiting_for_strike = False
        
        # Cancel all running tasks to prevent them from trying to update after view closes
        self._cancel_all_tasks()
        
        self.stop()
        new_view = FishingView(cog=self.cog, author=self.author, location=self.location)
        embed = await new_view.create_fishing_embed(interaction.guild)
        new_view.message = self.message
        await interaction.response.edit_message(embed=embed, view=new_view)
    
    async def _on_back_to_location(self, interaction: discord.Interaction):
        """Return to the fishing location view."""
        await self._on_stop_fishing(interaction)
    
    async def on_timeout(self):
        """Handle view timeout."""
        self._waiting_for_bite = False
        self._waiting_for_strike = False
        
        # Cancel all running tasks to prevent them from trying to update after timeout
        self._cancel_all_tasks()
        
        # Disable buttons and update message
        await self._disable_buttons_and_stop()
        
        await super().on_timeout()
