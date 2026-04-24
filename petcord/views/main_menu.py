"""
Main menu view for Petcord cog.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button
from typing import TYPE_CHECKING, Optional

from ..common.utils import calculate_cooldown_remaining, format_cooldown, format_stat_bar
from ..common.constants import (
    COOLDOWN_FEED, COOLDOWN_PLAY, COOLDOWN_GROOM, 
    COOLDOWN_REST, COOLDOWN_TREAT, COOLDOWN_PET,
    OWNER_SLEEP_DURATION_HOURS
)
from ..database.species import get_species
from ..database.wardrobe import get_equipped_display

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings


class MainMenuView(View):
    """Main pet dashboard view."""
    
    def __init__(
        self, 
        cog: "Petcord", 
        user_data: "User", 
        guild_settings: "GuildSettings",
        author_id: int,
        timeout: float = 180
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.message: Optional[discord.Message] = None
        self._setup_buttons()
        
        # Register with cog for cleanup on reload
        self.cog._active_views.add(self)
    
    def _setup_buttons(self) -> None:
        """Add buttons based on user state."""
        # Check for pending death notification first
        if self.user_data.pending_death_notification:
            self.add_item(AcknowledgeDeathButton())
            self.add_item(MemorialButton(row=0))
            self.add_item(CloseButton(row=0))
            return
        
        if self.user_data.current_pet is None:
            # No pet state - check cooldown
            cooldown_remaining = calculate_cooldown_remaining(
                self.user_data.last_pet_declined,
                self.guild_settings.find_cooldown_minutes
            )
            
            # Row 0: Main action buttons
            find_button = FindPetButton(disabled=(cooldown_remaining > 0))
            self.add_item(find_button)
            
            # Home button (view mature pets)
            home_button = HomeButton()
            self.add_item(home_button)
            
            # Memorial button
            memorial_button = MemorialButton()
            self.add_item(memorial_button)
            
            # Stats button
            stats_button = StatsButton()
            self.add_item(stats_button)
            
            # Row 1: Utility buttons
            self.add_item(SpeciesGuideButton())
            self.add_item(LeaderboardButton())
            refresh_button = RefreshButton(row=2)
            self.add_item(refresh_button)
            
            # Show HELP button for new players (never owned a pet)
            if self.user_data.total_pets_owned == 0:
                self.add_item(HelpButton())
            
            close_button = CloseButton(row=2)
            self.add_item(close_button)
        else:
            pet = self.user_data.current_pet
            
            # Has pet state - show care action buttons
            # Row 0: Primary care actions
            self.add_item(FeedButton(pet=pet))
            self.add_item(PlayButton(pet=pet))
            self.add_item(GroomButton(pet=pet))
            self.add_item(RestButton(pet=pet))
            
            # Row 1: Secondary actions
            self.add_item(TreatButton(pet=pet))
            self.add_item(PetActionButton(pet=pet))
            self.add_item(OwnerSleepButton(pet=pet, guild_settings=self.guild_settings))
            
            # Row 2: Home, Memorial, Stats, and Graduate if ready
            self.add_item(HomeButton(row=2))
            self.add_item(MemorialButton(row=2))
            if pet.ready_to_graduate:
                self.add_item(GraduateButton(row=2))
            self.add_item(StatsButton(row=2))
            
            # Row 3: Utility buttons
            self.add_item(AbandonButton(row=3))
            self.add_item(RefreshButton(row=3))
            self.add_item(CloseButton(row=3))
    
    async def build_embed(self) -> discord.Embed:
        """Build the main menu embed."""
        # Check for pending death notification first
        if self.user_data.pending_death_notification:
            return self._build_death_notification_embed()
        elif self.user_data.current_pet is None:
            return self._build_no_pet_embed()
        else:
            return self._build_pet_embed()
    
    def _build_death_notification_embed(self) -> discord.Embed:
        """Build embed to notify user their pet has died."""
        pet_name = self.user_data.pending_death_pet_name
        cause = self.user_data.pending_death_cause
        age_days = self.user_data.pending_death_age_days
        bond = self.user_data.pending_death_bond
        
        if cause == "old_age":
            embed = discord.Embed(
                title="🕊️ A Peaceful Passing",
                description=(
                    f"Your beloved companion **{pet_name}** has passed away peacefully "
                    f"of old age after **{age_days} days**.\n\n"
                    f"They lived a full and happy life in your Home.\n"
                    f"Final Bond: 💕 {bond}\n\n"
                    f"They've been added to your Memorial, where you can write an epitaph "
                    f"to honor their memory."
                ),
                color=discord.Color.purple()
            )
        else:  # neglect
            embed = discord.Embed(
                title="💔 Tragic News...",
                description=(
                    f"Your pet **{pet_name}** has passed away from neglect "
                    f"after only **{age_days} days**.\n\n"
                    f"They've been added to the Memorial.\n"
                    f"Please take better care of your next companion."
                ),
                color=discord.Color.dark_grey()
            )
        
        embed.add_field(
            name="🐾 What Now?",
            value="Click **Acknowledge** below to continue, then find a new pet to care for.",
            inline=False
        )
        
        return embed
    
    def _build_no_pet_embed(self) -> discord.Embed:
        """Build embed for no pet state."""
        cooldown_remaining = calculate_cooldown_remaining(
            self.user_data.last_pet_declined,
            self.guild_settings.find_cooldown_minutes
        )
        
        embed = discord.Embed(
            title="🐾 Petcord - Welcome!",
            color=discord.Color.blue()
        )
        
        if cooldown_remaining > 0:
            # On cooldown
            embed.description = "You don't have a pet yet."
            embed.add_field(
                name="⏳ Cooldown Active",
                value=f"You recently passed on a pet.\nYou can search again in: **{format_cooldown(cooldown_remaining)}**",
                inline=False
            )
        else:
            embed.description = (
                "You don't have a pet yet.\n"
                "Click **🔍 Find a Pet** below to discover a new companion!"
            )
        
        # Show quick stats
        stats_text = []
        if self.user_data.total_pets_owned > 0:
            stats_text.append(f"🏠 Pets in Home: **{len(self.user_data.home_pets)}**/{self.user_data.effective_home_capacity}")
            stats_text.append(f"🎖️ Total Medals: **{self.user_data.total_medals}** (🥇{self.user_data.gold_medals} 🥈{self.user_data.silver_medals} 🥉{self.user_data.bronze_medals})")
            stats_text.append(f"📊 Pets Raised: **{self.user_data.total_pets_graduated}**")
        
        if stats_text:
            embed.add_field(
                name="📋 Your Stats",
                value="\n".join(stats_text),
                inline=False
            )
        else:
            embed.add_field(
                name="💡 Getting Started",
                value="Find and adopt your first pet to begin your journey as a virtual pet caretaker!",
                inline=False
            )
        
        embed.set_footer(text="Use the buttons below to navigate")
        
        return embed
    
    def _build_has_pet_embed_placeholder(self) -> discord.Embed:
        """Build embed displaying current pet status."""
        return self._build_pet_embed()
    
    def _build_pet_embed(self) -> discord.Embed:
        """Build embed for current pet with stats and info."""
        pet = self.user_data.current_pet
        species = get_species(pet.species_id)
        
        # Get species info or fallback
        species_name = species.name if species else pet.species_id.replace("_", " ").title()
        species_emoji = species.emoji if species else "🐾"
        
        # Rarity display
        rarity_display = self._format_rarity(pet.rarity)
        
        # Stage emoji
        stage_emoji = {
            "baby": "🍼",
            "juvenile": "🌱",
            "adult": "🌟",
            "senior": "👴"
        }.get(pet.life_stage, "")
        
        embed = discord.Embed(
            title=f'{species_emoji} {pet.name}',
            description=f"**{species_name}** • {pet.life_stage.title()} {stage_emoji} • Day {int(pet.age_days) + 1}\n"
                       f"{rarity_display} • {pet.coat_color.replace('_', ' ').title()} / {pet.pattern.replace('_', ' ').title()}",
            color=self._get_health_color(pet.health)
        )
        
        # Stats with bars (display as int for cleaner UI)
        stats_lines = [
            f"❤️ Health:     {format_stat_bar(pet.health)} {int(pet.health)}%",
            f"🍖 Hunger:     {format_stat_bar(pet.hunger)} {int(pet.hunger)}%{self._warning_icon(pet.hunger)}",
            f"😊 Happiness:  {format_stat_bar(pet.happiness)} {int(pet.happiness)}%{self._warning_icon(pet.happiness)}",
            f"✨ Clean:      {format_stat_bar(pet.cleanliness)} {int(pet.cleanliness)}%{self._warning_icon(pet.cleanliness)}",
            f"⚡ Energy:     {format_stat_bar(pet.energy)} {int(pet.energy)}%{self._warning_icon(pet.energy)}",
            f"💕 Bond:       {format_stat_bar(pet.bond)} {int(pet.bond)}",
        ]
        embed.add_field(
            name="📊 Stats",
            value="```\n" + "\n".join(stats_lines) + "\n```",
            inline=False
        )
        
        # Quick info
        info_parts = []
        if species:
            info_parts.append(f"🎯 {species.temperament}")
        if pet.ready_to_graduate:
            info_parts.append("🎓 **Ready to graduate to Home!**")
        
        if info_parts:
            embed.add_field(
                name="📋 Info",
                value="\n".join(info_parts),
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
        
        embed.set_footer(text="Use the buttons below to care for your pet")
        
        return embed
    
    def _format_rarity(self, rarity: str) -> str:
        """Format rarity as stars."""
        mapping = {
            "common": "⭐ Common",
            "uncommon": "⭐⭐ Uncommon",
            "rare": "⭐⭐⭐ Rare",
            "very_rare": "⭐⭐⭐⭐ Very Rare",
            "legendary": "⭐⭐⭐⭐⭐ Legendary",
            "mythical": "🌟 Mythical"
        }
        return mapping.get(rarity, "⭐ Common")
    
    def _warning_icon(self, value: int) -> str:
        """Return warning icon if stat is low."""
        if value < 20:
            return " 🔴"
        elif value < 40:
            return " ⚠️"
        return ""
    
    def _get_health_color(self, health: int) -> discord.Color:
        """Get embed color based on health."""
        if health < 20:
            return discord.Color.red()
        elif health < 50:
            return discord.Color.orange()
        else:
            return discord.Color.green()
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command author can use buttons."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This menu isn't for you! Use the `petcord` command to open your own.",
                ephemeral=True
            )
            return False
        return True
    
    async def on_timeout(self) -> None:
        """Disable buttons when view times out."""
        # Unregister from cog
        self.cog._active_views.discard(self)
        
        for item in self.children:
            if isinstance(item, (Button,)):
                item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass
    
    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()


class FindPetButton(Button):
    """Button to initiate pet finding."""
    def __init__(self, disabled: bool = False):
        super().__init__(
            label="Find a Pet",
            emoji="🔍",
            style=discord.ButtonStyle.primary,
            disabled=disabled,
            row=0,
            custom_id="petcord:find_pet"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        # Get the parent view to access cog and user data
        view: MainMenuView = self.view
        
        # Import here to avoid circular import
        from .find_pet import PetFoundView, generate_offered_pet
        from ..common.utils import calculate_cooldown_remaining, format_cooldown
        
        # Double-check cooldown (in case button state is stale)
        cooldown_remaining = calculate_cooldown_remaining(
            view.user_data.last_pet_declined,
            view.guild_settings.find_cooldown_minutes
        )
        
        if cooldown_remaining > 0:
            await interaction.response.send_message(
                f"⏳ You can search again in **{format_cooldown(cooldown_remaining)}**",
                ephemeral=True
            )
            return
        
        # Stop the current view
        view.stop()
        
        # Generate random pet offer
        offered_pet = await generate_offered_pet()
        
        # Create offer view
        pet_view = PetFoundView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            offered_pet=offered_pet,
            author_id=view.author_id
        )
        
        embed = pet_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=pet_view)
        pet_view.message = view.message


class ViewPetButton(Button):
    """Button to view current pet details."""
    def __init__(self):
        super().__init__(
            label="Details",
            emoji="📋",
            style=discord.ButtonStyle.secondary,
            row=1
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "📋 Detailed pet view coming soon!",
            ephemeral=True
        )


class CareActionButton(Button):
    """Base class for pet care action buttons."""
    
    # Subclasses should override these
    action_name: str = ""
    action_emoji: str = ""
    stat_changes: dict = {}
    cooldown_attr: str = ""
    cooldown_hours: float = 1.0
    user_stat_attr: str = ""  # e.g. "total_feedings"
    primary_stat: str = ""  # Main stat to check if maxed (empty = always allowed)
    maxed_message: str = ""  # Message when primary stat is maxed
    
    def __init__(self, pet=None, **kwargs):
        super().__init__(**kwargs)
        
        # Store the emoji for re-application after label change
        stored_emoji = self.emoji
        
        # Check cooldown and disable button if on cooldown
        if pet is not None and self.cooldown_attr:
            import time
            last_used = getattr(pet, self.cooldown_attr, 0.0)
            cooldown_seconds = self.cooldown_hours * 3600
            time_since = time.time() - last_used
            if time_since < cooldown_seconds:
                self.disabled = True
                # Replace label with remaining time
                remaining = int(cooldown_seconds - time_since)
                hours, remainder = divmod(remaining, 3600)
                minutes, _ = divmod(remainder, 60)
                if hours > 0:
                    self.label = f"{hours}h {minutes}m"
                else:
                    self.label = f"{minutes}m"
                # Ensure emoji is preserved
                self.emoji = stored_emoji
    
    async def callback(self, interaction: discord.Interaction) -> None:
        import time
        
        view: MainMenuView = self.view
        pet = view.user_data.current_pet
        
        if pet is None:
            await interaction.response.send_message(
                "❌ You don't have a pet!",
                ephemeral=True
            )
            return
        
        # Check if primary stat is already maxed (if applicable)
        if self.primary_stat:
            current_primary = getattr(pet, self.primary_stat, 0)
            if current_primary >= 100:
                # Still set cooldown and update button even when maxed
                setattr(pet, self.cooldown_attr, time.time())
                pet.last_interaction = time.time()
                view.cog.schedule_save()
                
                # Format cooldown for message
                cooldown_seconds = int(self.cooldown_hours * 3600)
                hours, remainder = divmod(cooldown_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if hours > 0 and minutes > 0:
                    cooldown_str = f"{hours}h {minutes}m"
                elif hours > 0:
                    cooldown_str = f"{hours}h"
                else:
                    cooldown_str = f"{minutes}m"
                
                await interaction.response.send_message(
                    f"{self.maxed_message or 'Your pet does not need that right now!'}\n\n⏳ Try again in: **{cooldown_str}**",
                    ephemeral=True
                )
                
                # Refresh main view embed AND rebuild view to update button states
                new_embed = await view.build_embed()
                new_embed.set_author(
                    name=interaction.user.display_name,
                    icon_url=interaction.user.display_avatar.url
                )
                
                # Rebuild buttons to reflect new cooldown states
                view.clear_items()
                view._setup_buttons()
                
                if view.message:
                    try:
                        await view.message.edit(embed=new_embed, view=view)
                    except (discord.NotFound, discord.HTTPException):
                        pass
                return
        
        # Check cooldown
        last_used = getattr(pet, self.cooldown_attr, 0.0)
        cooldown_seconds = self.cooldown_hours * 3600
        time_since = time.time() - last_used
        
        if time_since < cooldown_seconds:
            remaining = int(cooldown_seconds - time_since)
            hours, remainder = divmod(remaining, 3600)
            minutes, seconds = divmod(remainder, 60)
            
            if hours > 0:
                time_str = f"{hours}h {minutes}m"
            elif minutes > 0:
                time_str = f"{minutes}m {seconds}s"
            else:
                time_str = f"{seconds}s"
            
            await interaction.response.send_message(
                f"⏳ You can {self.action_name} again in **{time_str}**.",
                ephemeral=True
            )
            return
        
        # Apply stat changes
        changes_text = []
        for stat, change in self.stat_changes.items():
            current = getattr(pet, stat, 0)
            # Bond has no max, other stats cap at 100
            if stat == "bond":
                new_val = max(0, current + change)
            else:
                new_val = max(0, min(100, current + change))
            setattr(pet, stat, new_val)
            
            # Display as int for cleaner output
            if change > 0:
                arrow = "📈"
                changes_text.append(f"{arrow} {stat.title()}: {int(current)} → {int(new_val)} (+{change})")
            else:
                arrow = "📉"
                changes_text.append(f"{arrow} {stat.title()}: {int(current)} → {int(new_val)} ({change})")
        
        # Update cooldown and interaction time
        setattr(pet, self.cooldown_attr, time.time())
        pet.last_interaction = time.time()
        
        # Update user stats
        view.user_data.total_interactions += 1
        if self.user_stat_attr:
            current_count = getattr(view.user_data, self.user_stat_attr, 0)
            setattr(view.user_data, self.user_stat_attr, current_count + 1)
        
        # Track highest bond achieved
        if pet.bond > view.user_data.highest_bond_achieved:
            view.user_data.highest_bond_achieved = int(pet.bond)
        
        # Update daily tracking
        from ..commands.helper_functions import update_daily_tracking
        update_daily_tracking(view.user_data, pet, self.action_name)
        
        # Check for new achievements
        from ..database.achievements import check_and_award_achievements, build_achievement_unlock_embed
        new_achievements = await check_and_award_achievements(view.user_data)
        achievement_embed = build_achievement_unlock_embed(new_achievements)
        
        # Save
        view.cog.schedule_save()
        
        # Format cooldown for next use
        cooldown_seconds = int(self.cooldown_hours * 3600)
        hours, remainder = divmod(cooldown_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if hours > 0 and minutes > 0:
            cooldown_str = f"{hours}h {minutes}m"
        elif hours > 0:
            cooldown_str = f"{hours}h"
        else:
            cooldown_str = f"{minutes}m"
        
        # Show result
        embed = discord.Embed(
            title=f"{self.action_emoji} {self.action_name.title()}!",
            description="\n".join(changes_text) + f"\n\n⏳ {self.action_name.title()} again in: **{cooldown_str}**",
            color=discord.Color.green()
        )
        
        # Include achievement if earned
        if achievement_embed:
            await interaction.response.send_message(
                embeds=[embed, achievement_embed], 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # Refresh main view embed AND rebuild view to update button states
        new_embed = await view.build_embed()
        new_embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        # Rebuild buttons to reflect new cooldown states
        view.clear_items()
        view._setup_buttons()
        
        if view.message:
            try:
                await view.message.edit(embed=new_embed, view=view)
            except (discord.NotFound, discord.HTTPException):
                pass


class FeedButton(CareActionButton):
    """Button to feed the pet."""
    action_name = "feed"
    action_emoji = "🍖"
    stat_changes = {"hunger": 30, "happiness": 5}
    cooldown_attr = "last_fed"
    cooldown_hours = COOLDOWN_FEED
    user_stat_attr = "total_feedings"
    primary_stat = "hunger"
    maxed_message = "🍖 Your pet isn't hungry right now!"
    
    def __init__(self, pet=None):
        super().__init__(
            pet=pet,
            label="Feed",
            emoji="🍖",
            style=discord.ButtonStyle.primary,
            row=0,
            custom_id="petcord:feed"
        )


class PlayButton(CareActionButton):
    """Button to play with the pet."""
    action_name = "play"
    action_emoji = "🎾"
    stat_changes = {"happiness": 25, "energy": -15, "bond": 3}
    cooldown_attr = "last_played"
    cooldown_hours = COOLDOWN_PLAY
    user_stat_attr = "total_play_sessions"
    primary_stat = "happiness"
    maxed_message = "🎾 Your pet is already as happy as can be!"
    
    def __init__(self, pet=None):
        super().__init__(
            pet=pet,
            label="Play",
            emoji="🎾",
            style=discord.ButtonStyle.primary,
            row=0,
            custom_id="petcord:play"
        )


class GroomButton(CareActionButton):
    """Button to groom the pet."""
    action_name = "groom"
    action_emoji = "✨"
    stat_changes = {"cleanliness": 35, "happiness": 5}
    cooldown_attr = "last_groomed"
    cooldown_hours = COOLDOWN_GROOM
    user_stat_attr = "total_grooming_sessions"
    primary_stat = "cleanliness"
    maxed_message = "✨ Your pet is already squeaky clean!"
    
    def __init__(self, pet=None):
        super().__init__(
            pet=pet,
            label="Groom",
            emoji="✨",
            style=discord.ButtonStyle.primary,
            row=0,
            custom_id="petcord:groom"
        )


class RestButton(CareActionButton):
    """Button to let the pet rest."""
    action_name = "rest"
    action_emoji = "🛏️"
    stat_changes = {"energy": 40, "health": 10}
    cooldown_attr = "last_rested"
    cooldown_hours = COOLDOWN_REST
    user_stat_attr = "total_rest_sessions"
    primary_stat = "energy"
    maxed_message = "🛏️ Your pet is already well-rested and full of energy!"
    
    def __init__(self, pet=None):
        super().__init__(
            pet=pet,
            label="Rest",
            emoji="🛏️",
            style=discord.ButtonStyle.primary,
            row=0,
            custom_id="petcord:rest"
        )


class TreatButton(CareActionButton):
    """Button to give the pet a treat."""
    action_name = "treat"
    action_emoji = "🍬"
    stat_changes = {"happiness": 20, "bond": 5, "hunger": 5}
    cooldown_attr = "last_treated"
    cooldown_hours = COOLDOWN_TREAT
    user_stat_attr = "total_treats_given"
    
    def __init__(self, pet=None):
        super().__init__(
            pet=pet,
            label="Treat",
            emoji="🍬",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id="petcord:treat"
        )


class PetActionButton(CareActionButton):
    """Button to pet/cuddle the pet."""
    action_name = "pet"
    action_emoji = "🤗"
    stat_changes = {"happiness": 10, "bond": 2}
    cooldown_attr = "last_petted"
    cooldown_hours = COOLDOWN_PET
    user_stat_attr = "total_petting_sessions"
    
    def __init__(self, pet=None):
        super().__init__(
            pet=pet,
            label="Pet",
            emoji="🤗",
            style=discord.ButtonStyle.secondary,
            row=1,
            custom_id="petcord:pet_action"
        )


class OwnerSleepButton(Button):
    """Button to pause decay for 6 hours (once per calendar day)."""
    
    def __init__(self, pet=None, guild_settings=None):
        import time
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        # Determine if button should be disabled (already used today)
        disabled = False
        label = "Owner Sleep"
        
        if pet is not None and guild_settings is not None:
            try:
                # Get server timezone
                tz = ZoneInfo(guild_settings.discord_server_timezone)
                today = datetime.now(tz).strftime("%Y-%m-%d")
                
                # Check if already used today
                if pet.last_owner_sleep_date == today:
                    disabled = True
                    label = "Use Tomorrow"
            except Exception:
                pass  # If timezone fails, allow use
        
        # Check if currently active (show remaining time)
        if pet is not None and pet.decay_paused_until > 0:
            current_time = time.time()
            if current_time < pet.decay_paused_until:
                remaining_seconds = int(pet.decay_paused_until - current_time)
                hours, remainder = divmod(remaining_seconds, 3600)
                minutes, _ = divmod(remainder, 60)
                if hours > 0:
                    label = f"💤 {hours}h {minutes}m"
                else:
                    label = f"💤 {minutes}m"
                disabled = True
            else:
                # Sleep has expired - clear the stale timestamp
                # This ensures next day check works correctly
                pet.decay_paused_until = 0
        
        super().__init__(
            label=label,
            emoji="😴",
            style=discord.ButtonStyle.primary if not disabled else discord.ButtonStyle.secondary,
            disabled=disabled,
            row=1,
            custom_id="petcord:owner_sleep"
        )
        self.pet = pet
        self.guild_settings = guild_settings
    
    async def callback(self, interaction: discord.Interaction) -> None:
        import time
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        
        view: MainMenuView = self.view
        pet = view.user_data.current_pet
        
        if pet is None:
            await interaction.response.send_message(
                "❌ You don't have a pet!",
                ephemeral=True
            )
            return
        
        # Double-check calendar day (in case of race condition)
        try:
            tz = ZoneInfo(view.guild_settings.discord_server_timezone)
            today = datetime.now(tz).strftime("%Y-%m-%d")
            
            if pet.last_owner_sleep_date == today:
                await interaction.response.send_message(
                    "😴 You've already used **Owner Sleep** today!\n"
                    "You can use it again tomorrow.",
                    ephemeral=True
                )
                return
        except Exception as e:
            # Log timezone errors if debug mode is on
            if view.user_data.debug_mode:
                try:
                    from datetime import datetime as dt
                    view.cog.debug_log.append({
                        "timestamp": dt.now().isoformat(),
                        "event": "OWNER_SLEEP_TIMEZONE_ERROR",
                        "error": str(e),
                        "configured_tz": view.guild_settings.discord_server_timezone,
                    })
                except Exception:
                    pass
            pass  # Proceed if timezone check fails
        
        # Check if currently paused
        current_time = time.time()
        
        # Clear expired sleep timestamp if present
        if pet.decay_paused_until > 0 and current_time >= pet.decay_paused_until:
            pet.decay_paused_until = 0
        
        if pet.decay_paused_until > 0 and current_time < pet.decay_paused_until:
            remaining = int(pet.decay_paused_until - current_time)
            hours, remainder = divmod(remaining, 3600)
            minutes, _ = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
            
            await interaction.response.send_message(
                f"😴 **Owner Sleep** is already active!\n"
                f"Decay paused for: **{time_str}**",
                ephemeral=True
            )
            return
        
        # Calculate next available use timestamp (start of next calendar day in server timezone)
        try:
            tz = ZoneInfo(view.guild_settings.discord_server_timezone)
            now = datetime.now(tz)
            tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            next_use_timestamp = int(tomorrow_start.timestamp())
        except Exception:
            # Fallback to UTC if timezone fails
            from datetime import timezone as dt_timezone
            now = datetime.now(dt_timezone.utc)
            tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            next_use_timestamp = int(tomorrow_start.timestamp())
        
        # Show confirmation dialog
        confirm_view = OwnerSleepConfirmView(
            parent_view=view,
            next_use_timestamp=next_use_timestamp
        )
        await interaction.response.send_message(
            f"😴 **Owner Sleep Confirmation**\n\n"
            f"This feature can only be used **once per calendar day**.\n"
            f"Your next available use would be: <t:{next_use_timestamp}:F>\n\n"
            f"Are you sure you want to activate Owner Sleep now?",
            view=confirm_view,
            ephemeral=True
        )


class OwnerSleepConfirmView(View):
    """Confirmation view for Owner Sleep activation."""
    
    def __init__(self, parent_view: "MainMenuView", next_use_timestamp: int, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.parent_view = parent_view
        self.next_use_timestamp = next_use_timestamp
    
    @discord.ui.button(label="Activate", emoji="✅", style=discord.ButtonStyle.success)
    async def activate_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Activate Owner Sleep."""
        import time
        from datetime import datetime
        from zoneinfo import ZoneInfo
        
        pet = self.parent_view.user_data.current_pet
        if pet is None:
            await interaction.response.edit_message(
                content="❌ You don't have a pet!",
                view=None
            )
            return
        
        current_time = time.time()
        
        # Activate Owner Sleep
        pet.decay_paused_until = current_time + (OWNER_SLEEP_DURATION_HOURS * 3600)
        
        # Record today's date as last used
        try:
            tz = ZoneInfo(self.parent_view.guild_settings.discord_server_timezone)
            pet.last_owner_sleep_date = datetime.now(tz).strftime("%Y-%m-%d")
        except Exception:
            from datetime import timezone
            pet.last_owner_sleep_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Debug logging if enabled
        if self.parent_view.user_data.debug_mode:
            try:
                debug_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "user_id": interaction.user.id,
                    "pet_name": pet.name,
                    "event": "OWNER_SLEEP_ACTIVATED",
                    "owner_sleep_active": True,
                    "pause_duration_hours": OWNER_SLEEP_DURATION_HOURS,
                    "pause_expires_at": datetime.fromtimestamp(pet.decay_paused_until).isoformat(),
                    "current_stats": {
                        "hunger": round(pet.hunger, 1),
                        "happiness": round(pet.happiness, 1),
                        "cleanliness": round(pet.cleanliness, 1),
                        "energy": round(pet.energy, 1),
                    },
                    "message": f"Owner Sleep ACTIVATED - Decay paused for {OWNER_SLEEP_DURATION_HOURS} hours"
                }
                self.parent_view.cog.debug_log.append(debug_entry)
                if len(self.parent_view.cog.debug_log) > 1000:
                    self.parent_view.cog.debug_log.pop(0)
            except Exception:
                pass  # Don't break activation if logging fails
        
        # Save
        self.parent_view.cog.schedule_save()
        
        # Show success message
        await interaction.response.edit_message(
            content=(
                f"😴 **Owner Sleep activated!**\n\n"
                f"All stat decay is paused for **{OWNER_SLEEP_DURATION_HOURS} hours**.\n"
                f"Your pet will stay exactly as they are while you rest.\n\n"
                f"💤 Sweet dreams!"
            ),
            view=None
        )
        
        # Refresh the main menu to show updated button state
        self.parent_view.clear_items()
        self.parent_view._setup_buttons()
        embed = await self.parent_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        try:
            await self.parent_view.message.edit(embed=embed, view=self.parent_view)
        except Exception:
            pass
        
        self.stop()
    
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: Button) -> None:
        """Cancel Owner Sleep activation."""
        await interaction.response.edit_message(
            content="😴 Owner Sleep activation cancelled.",
            view=None
        )
        self.stop()
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        pass  # Message is ephemeral, no cleanup needed


class HomeButton(Button):
    """Button to view Home (mature pets)."""
    def __init__(self, row: int = 0):
        super().__init__(
            label="Home",
            emoji="🏠",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="petcord:home"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .home_views import HomeListView
        
        view: MainMenuView = self.view
        
        # Stop the current view
        view.stop()
        
        # Create home list view
        home_view = HomeListView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id,
            guild_settings=view.guild_settings,
            author=interaction.user
        )
        
        embed = home_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=home_view)
        home_view.message = view.message


class StatsButton(Button):
    """Button to view statistics."""
    def __init__(self, row: int = 0):
        super().__init__(
            label="Stats",
            emoji="📊",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="petcord:stats"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .stat_views import StatsView
        
        view: MainMenuView = self.view
        
        # Stop current view
        view.stop()
        
        # Create stats view
        stats_view = StatsView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=view.author_id
        )
        
        embed = stats_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=stats_view)
        stats_view.message = view.message


class AbandonButton(Button):
    """Button to abandon the current pet."""
    def __init__(self, row: int = 2):
        super().__init__(
            label="Abandon",
            emoji="🚪",
            style=discord.ButtonStyle.danger,
            row=row,
            custom_id="petcord:abandon"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        pet = view.user_data.current_pet
        
        if pet is None:
            await interaction.response.send_message(
                "❌ You don't have a pet to abandon!",
                ephemeral=True
            )
            return
        
        # Show confirmation view
        confirm_view = AbandonConfirmView(view, pet)
        embed = discord.Embed(
            title="🚪 Abandon Pet?",
            description=(
                f"Are you sure you want to abandon **{pet.name}**?\n\n"
                f"⚠️ This action cannot be undone!\n"
                f"• Your pet will be gone forever\n"
                f"• This will be recorded in your stats\n"
                f"• You can find a new pet immediately (no cooldown)"
            ),
            color=discord.Color.orange()
        )
        
        await interaction.response.send_message(embed=embed, view=confirm_view, ephemeral=True)


class AbandonConfirmView(View):
    """Confirmation view for abandoning a pet."""
    
    def __init__(self, parent_view: "MainMenuView", pet):
        super().__init__(timeout=60)
        self.parent_view = parent_view
        self.pet = pet
    
    @discord.ui.button(label="Yes, Abandon", style=discord.ButtonStyle.danger, emoji="🚪")
    async def confirm_abandon(self, interaction: discord.Interaction, button: Button):
        import time
        
        pet = self.pet
        user_data = self.parent_view.user_data
        
        # Record the abandonment
        user_data.pets_abandoned += 1
        
        # Add to pet history
        from ..common.models import PetHistoryEntry
        history_entry = PetHistoryEntry(
            name=pet.name,
            species_id=pet.species_id,
            rarity=pet.rarity,
            released_timestamp=time.time(),
            age_at_release=int(pet.age_days),
            bond_at_release=int(pet.bond),
            reason="abandoned"
        )
        user_data.pet_history.append(history_entry)
        
        # Store pet info before clearing
        pet_name = pet.name
        species_id = pet.species_id
        
        # Clear the current pet
        user_data.current_pet = None
        
        # Clear any daily tracking
        user_data.current_day_scores = None
        user_data.care_history = []
        
        # Save changes
        self.parent_view.cog.schedule_save()
        
        # Stop this confirmation view
        self.stop()
        
        # Send confirmation to user
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="🚪 Pet Abandoned",
                description=f"**{pet_name}** has been abandoned.\n\nYou can now find a new pet.",
                color=discord.Color.dark_grey()
            ),
            view=None
        )
        
        # Post shame message to notification channel
        try:
            from ..database.abandon import get_random_abandon_message
            from ..database.species import get_species
            
            guild_settings = self.parent_view.guild_settings
            if guild_settings.allowed_channel_id:
                guild = interaction.guild
                if guild:
                    channel = guild.get_channel(guild_settings.allowed_channel_id)
                    if channel:
                        species = get_species(species_id)
                        species_name = species.name if species else species_id.replace("_", " ").title()
                        
                        shame_message = get_random_abandon_message(
                            user_mention=interaction.user.mention,
                            species_name=species_name,
                            pet_name=pet_name
                        )
                        await channel.send(shame_message)
        except Exception:
            pass  # Don't let shame message failure break the abandon flow
        
        # Refresh the main menu
        self.parent_view.clear_items()
        self.parent_view._setup_buttons()
        embed = await self.parent_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        if self.parent_view.message:
            try:
                await self.parent_view.message.edit(embed=embed, view=self.parent_view)
            except (discord.NotFound, discord.HTTPException):
                pass
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_abandon(self, interaction: discord.Interaction, button: Button):
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(
                title="❌ Cancelled",
                description="Your pet is safe!",
                color=discord.Color.green()
            ),
            view=None
        )


class MemorialButton(Button):
    """Button to view pet memorial."""
    def __init__(self, row: int = 0):
        super().__init__(
            label="Memorial",
            emoji="🪦",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="petcord:memorial"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        from .memorial import MemorialView
        
        view: MainMenuView = self.view
        
        # Stop the current view
        view.stop()
        
        # Create memorial view
        memorial_view = MemorialView(
            cog=view.cog,
            user_data=view.user_data,
            author_id=view.author_id
        )
        
        embed = memorial_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=memorial_view)
        memorial_view.message = view.message


class RefreshButton(Button):
    """Button to refresh the main menu embed."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="petcord:refresh"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        
        # Rebuild buttons to reflect current state (pet status, cooldowns, etc.)
        view.clear_items()
        view._setup_buttons()
        
        # Rebuild and update the embed with fresh data
        embed = await view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=view)


class CloseButton(Button):
    """Button to close the main menu."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Close",
            emoji="✖️",
            style=discord.ButtonStyle.danger,
            row=row,
            custom_id="petcord:close"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        
        # Stop the view and delete the message
        view.stop()
        
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            # If we can't delete, just disable buttons
            for item in view.children:
                item.disabled = True
            await interaction.response.edit_message(view=view)


class AcknowledgeDeathButton(Button):
    """Button to acknowledge pet death notification and continue."""
    def __init__(self, row: int = 0):
        super().__init__(
            label="Acknowledge",
            emoji="🕊️",
            style=discord.ButtonStyle.primary,
            row=row,
            custom_id="petcord:ack_death"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        
        # Clear the pending notification
        view.user_data.pending_death_notification = False
        view.user_data.pending_death_pet_name = ""
        view.user_data.pending_death_cause = ""
        view.user_data.pending_death_age_days = 0
        view.user_data.pending_death_bond = 0
        view.cog.schedule_save()
        
        # Rebuild buttons and embed for normal state
        view.clear_items()
        view._setup_buttons()
        embed = await view.build_embed()
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        
        await interaction.response.edit_message(embed=embed, view=view)


class SpeciesGuideButton(Button):
    """Button to open the species guide."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Species",
            emoji="📖",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="petcord:species_guide"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        
        # Import here to avoid circular import
        from .species_guide import SpeciesGuideView
        
        # Stop current view
        view.stop()
        
        # Create species guide view
        species_view = SpeciesGuideView(
            cog=view.cog,
            author_id=interaction.user.id
        )
        
        embed = await species_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=species_view)
        species_view.message = view.message


class LeaderboardButton(Button):
    """Button to view the server leaderboard."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Leaderboard",
            emoji="🏆",
            style=discord.ButtonStyle.secondary,
            row=row,
            custom_id="petcord:leaderboard"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        
        # Import here to avoid circular import
        from .leaderboard import LeaderboardView
        
        # Stop current view
        view.stop()
        
        # Create leaderboard view
        lb_view = LeaderboardView(
            cog=view.cog,
            guild_id=interaction.guild_id,
            author_id=interaction.user.id
        )
        
        embed = await lb_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=lb_view)
        lb_view.message = view.message


class GraduateButton(Button):
    """Button to open graduation ceremony for adult pets."""
    def __init__(self, row: int = 2):
        super().__init__(
            label="Graduate!",
            emoji="🎓",
            style=discord.ButtonStyle.success,
            row=row,
            custom_id="petcord:graduate"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        pet = view.user_data.current_pet
        
        if not pet or not pet.ready_to_graduate:
            await interaction.response.send_message(
                "Your pet isn't ready to graduate yet!",
                ephemeral=True
            )
            return
        
        # Import here to avoid circular import
        from .graduation import GraduationView
        
        # Stop the current view
        view.stop()
        
        # Create graduation view
        grad_view = GraduationView(
            cog=view.cog,
            user_data=view.user_data,
            guild_settings=view.guild_settings,
            author_id=interaction.user.id
        )
        
        embed = grad_view.build_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=grad_view)
        grad_view.message = view.message


class HelpButton(Button):
    """Button to open How-To help for new players."""
    def __init__(self, row: int = 1):
        super().__init__(
            label="Help",
            emoji="❓",
            style=discord.ButtonStyle.primary,
            row=row,
            custom_id="petcord:help"
        )
    
    async def callback(self, interaction: discord.Interaction) -> None:
        view: MainMenuView = self.view
        
        # Import here to avoid circular import
        from .howto_views import HowToView
        
        # Stop current view
        view.stop()
        
        # Create How-To view without return capability (new players start fresh)
        howto_view = HowToView(
            cog=view.cog,
            author_id=interaction.user.id,
            guild_settings=view.guild_settings,
            return_view=None,
            return_embed=None
        )
        
        embed = howto_view.get_main_help_embed()
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.edit_message(embed=embed, view=howto_view)
        howto_view.message = view.message
