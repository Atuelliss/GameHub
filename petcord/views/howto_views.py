"""
How-To / Help view for Petcord cog.
Provides a walkthrough of all game mechanics.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings

from ..common.constants import (
    GOLD_THRESHOLD, SILVER_THRESHOLD, BRONZE_THRESHOLD,
    STAGE_THRESHOLDS,
    COOLDOWN_FEED, COOLDOWN_PLAY, COOLDOWN_GROOM,
    COOLDOWN_REST, COOLDOWN_TREAT, COOLDOWN_PET,
    REST_DECAY_MAX_REDUCTION,
    ACTION_EFFECTS,
)


def _format_cooldown(hours: float) -> str:
    """Format cooldown hours into a readable string."""
    if hours >= 1:
        whole_hours = int(hours)
        remaining_minutes = int(round((hours - whole_hours) * 60))
        if remaining_minutes > 0:
            return f"{whole_hours}h {remaining_minutes}m"
        else:
            return f"{whole_hours}h"
    else:
        minutes = int(round(hours * 60))
        return f"{minutes}m"


class HowToView(View):
    """Main How-To help view with multiple information pages."""
    
    def __init__(
        self,
        cog: "Petcord",
        author_id: int,
        guild_settings: "GuildSettings",
        return_view: Optional[View] = None,
        return_embed: Optional[discord.Embed] = None,
        timeout: float = 300
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.author_id = author_id
        self.guild_settings = guild_settings
        self.return_view = return_view  # View to return to when pressing Back
        self.return_embed = return_embed  # Embed to show when returning
        self.message: Optional[discord.Message] = None
        self.current_page = "main"
        
        # Register with cog for cleanup
        self.cog._active_views.add(self)
        
        # Set up main menu buttons
        self._setup_main_buttons()
    
    def _setup_main_buttons(self) -> None:
        """Set up buttons for main help menu."""
        self.clear_items()
        
        # Row 0: Core mechanics
        finding_btn = Button(
            label="Finding Pets",
            emoji="🔍",
            style=discord.ButtonStyle.primary,
            row=0
        )
        finding_btn.callback = self._finding_pets_callback
        self.add_item(finding_btn)
        
        caring_btn = Button(
            label="Pet Care",
            emoji="💕",
            style=discord.ButtonStyle.primary,
            row=0
        )
        caring_btn.callback = self._pet_care_callback
        self.add_item(caring_btn)
        
        growth_btn = Button(
            label="Growth & Stages",
            emoji="🌱",
            style=discord.ButtonStyle.primary,
            row=0
        )
        growth_btn.callback = self._growth_callback
        self.add_item(growth_btn)
        
        # Row 1: More mechanics
        medals_btn = Button(
            label="Medals & Scoring",
            emoji="🏅",
            style=discord.ButtonStyle.primary,
            row=1
        )
        medals_btn.callback = self._medals_callback
        self.add_item(medals_btn)
        
        home_btn = Button(
            label="Pet Home",
            emoji="🏠",
            style=discord.ButtonStyle.primary,
            row=1
        )
        home_btn.callback = self._home_callback
        self.add_item(home_btn)
        
        memorial_btn = Button(
            label="Memorial",
            emoji="🪦",
            style=discord.ButtonStyle.primary,
            row=1
        )
        memorial_btn.callback = self._memorial_callback
        self.add_item(memorial_btn)
        
        # Row 2: Additional info
        achievements_btn = Button(
            label="Achievements",
            emoji="🏆",
            style=discord.ButtonStyle.primary,
            row=2
        )
        achievements_btn.callback = self._achievements_callback
        self.add_item(achievements_btn)
        
        stats_btn = Button(
            label="Stats & Tips",
            emoji="📊",
            style=discord.ButtonStyle.primary,
            row=2
        )
        stats_btn.callback = self._stats_tips_callback
        self.add_item(stats_btn)
        
        # Row 3: Navigation
        if self.return_view is not None:
            back_btn = Button(
                label="Back",
                emoji="◀️",
                style=discord.ButtonStyle.secondary,
                row=3
            )
            back_btn.callback = self._back_callback
            self.add_item(back_btn)
        
        close_btn = Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=3
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
    
    def _setup_sub_buttons(self) -> None:
        """Set up buttons for sub-pages (back to main help)."""
        self.clear_items()
        
        back_btn = Button(
            label="Back to Help Menu",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            row=0
        )
        back_btn.callback = self._back_to_main_help_callback
        self.add_item(back_btn)
        
        close_btn = Button(
            label="Close",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            row=0
        )
        close_btn.callback = self._close_callback
        self.add_item(close_btn)
    
    # ==========================================================================
    # EMBED BUILDERS
    # ==========================================================================
    
    def get_main_help_embed(self) -> discord.Embed:
        """Generate the main help menu embed."""
        embed = discord.Embed(
            title="🐾 Petcord - How To Play",
            description=(
                "Welcome to Petcord! Raise virtual pets, care for them through "
                "their life stages, and earn medals for excellent care!\n\n"
                "**Select a topic below to learn more:**"
            ),
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="🔍 Finding Pets",
            value="How to discover and adopt new companions",
            inline=True
        )
        embed.add_field(
            name="💕 Pet Care",
            value="Feeding, playing, and keeping your pet healthy",
            inline=True
        )
        embed.add_field(
            name="🌱 Growth & Stages",
            value="How pets age and progress through life",
            inline=True
        )
        embed.add_field(
            name="🏅 Medals & Scoring",
            value="Earning Gold, Silver, and Bronze medals",
            inline=True
        )
        embed.add_field(
            name="🏠 Pet Home",
            value="Where graduated pets live happily",
            inline=True
        )
        embed.add_field(
            name="🪦 Memorial",
            value="Remembering pets who have passed",
            inline=True
        )
        embed.add_field(
            name="🏆 Achievements",
            value="Unlock badges for your accomplishments",
            inline=True
        )
        embed.add_field(
            name="📊 Stats & Tips",
            value="Understanding stats and pro tips",
            inline=True
        )
        
        embed.set_footer(text="Choose a topic to learn more!")
        return embed
    
    def get_finding_pets_embed(self) -> discord.Embed:
        """Generate the Finding Pets help embed."""
        embed = discord.Embed(
            title="🔍 Finding & Adopting Pets",
            color=discord.Color.green()
        )
        
        embed.add_field(
            name="How to Find a Pet",
            value=(
                "1. Use the `petcord` command to open the main menu\n"
                "2. Click **🔍 Find a Pet** to search for a companion\n"
                "3. A random pet will be offered to you!\n"
                "4. View its species, rarity, coat, and pattern"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Adopting or Passing",
            value=(
                "• Click **✅ Adopt** to take the pet home - you'll name it!\n"
                "• Click **❌ Pass** to decline - starts a cooldown before searching again\n"
                "• Click **◀️ Back** to return to the menu without any penalty"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🌟 Rarity Tiers",
            value=(
                "• ⭐ **Common** - Most frequently found\n"
                "• ⭐⭐ **Uncommon** - Somewhat rare\n"
                "• ⭐⭐⭐ **Rare** - Special finds\n"
                "• ⭐⭐⭐⭐ **Very Rare** - Hard to find\n"
                "• ⭐⭐⭐⭐⭐ **Legendary** - Extremely rare\n"
                "• 🌟 **Mythical** - Nearly impossible to find!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="✨ Special Coats",
            value=(
                "Some pets have rare coat variants that increase rarity:\n"
                "• **Rare Coats:** Albino, Melanistic, Leucistic, Piebald\n"
                "• **Mythical Coats:** Rainbow, Galaxy, Crystal, Shadow"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📖 Species Guide",
            value="Use the **Species** button to browse all 100 available species!",
            inline=False
        )
        
        return embed
    
    def get_pet_care_embed(self) -> discord.Embed:
        """Generate the Pet Care help embed."""
        embed = discord.Embed(
            title="💕 Caring For Your Pet",
            color=discord.Color.pink()
        )
        
        # Get action effects from constants
        feed_effects = ACTION_EFFECTS.get("feed", {})
        play_effects = ACTION_EFFECTS.get("play", {})
        groom_effects = ACTION_EFFECTS.get("groom", {})
        rest_effects = ACTION_EFFECTS.get("rest", {})
        treat_effects = ACTION_EFFECTS.get("treat", {})
        pet_effects = ACTION_EFFECTS.get("pet", {})
        
        # Calculate rest decay reduction percentage
        rest_decay_pct = int(REST_DECAY_MAX_REDUCTION * 100)
        
        embed.add_field(
            name=f"🍖 Feeding ({_format_cooldown(COOLDOWN_FEED)} cooldown)",
            value=f"Restores **Hunger** (+{feed_effects.get('hunger', 30)}) and adds a bit of Happiness (+{feed_effects.get('happiness', 5)})",
            inline=True
        )
        embed.add_field(
            name=f"🎾 Playing ({_format_cooldown(COOLDOWN_PLAY)} cooldown)",
            value=f"Boosts **Happiness** (+{play_effects.get('happiness', 25)}), uses Energy ({play_effects.get('energy', -15)}), builds **Bond** (+{play_effects.get('bond', 3)})",
            inline=True
        )
        embed.add_field(
            name=f"✨ Grooming ({_format_cooldown(COOLDOWN_GROOM)} cooldown)",
            value=f"Restores **Cleanliness** (+{groom_effects.get('cleanliness', 35)}) and adds Happiness (+{groom_effects.get('happiness', 5)})",
            inline=True
        )
        embed.add_field(
            name=f"💤 Resting ({_format_cooldown(COOLDOWN_REST)} cooldown)",
            value=(
                f"Restores **Energy** (+{rest_effects.get('energy', 40)}) and heals Health (+{rest_effects.get('health', 5)})\n"
                f"🌙 *Bonus:* Slows stat decay by up to {rest_decay_pct}% while resting!"
            ),
            inline=True
        )
        embed.add_field(
            name=f"🍬 Treats ({_format_cooldown(COOLDOWN_TREAT)} cooldown)",
            value=f"Big Happiness boost (+{treat_effects.get('happiness', 20)}) and **Bond** bonus (+{treat_effects.get('bond', 5)})",
            inline=True
        )
        embed.add_field(
            name=f"🤗 Petting ({_format_cooldown(COOLDOWN_PET)} cooldown)",
            value=f"Light Happiness (+{pet_effects.get('happiness', 10)}) and steady Bond growth (+{pet_effects.get('bond', 2)})",
            inline=True
        )
        
        embed.add_field(
            name="⚠️ Stat Decay",
            value=(
                "Stats naturally decrease over time:\n"
                "• **Hunger** decays fastest - feed regularly!\n"
                "• **Energy** depletes, especially after playing\n"
                "• **Cleanliness** and **Happiness** decline gradually\n"
                "• Different species decay at different rates\n"
                f"• 💡 **Resting** slows ALL decay by up to {rest_decay_pct}%!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔴 Critical Stats Warning",
            value=(
                "When any stat drops below **20%**, your pet takes **Health damage**!\n"
                "Multiple critical stats = more damage. Keep all stats above 40% to be safe.\n\n"
                "💡 **Tip:** Enable notifications in Stats → 🔔 Notifications to get @mentioned\n"
                "when your pet's stats drop dangerously low!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💤 Owner Sleep",
            value=(
                "Need a break? Use the **Owner Sleep** button to pause all stat decay for **6 hours**!\n"
                "• Can be used **once per calendar day**\n"
                "• Stats stay exactly where they are while you rest\n"
                "• Perfect for overnight breaks"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🍖 Shop Treats (Supply Shop)",
            value=(
                "Buy special treats from the Supply Shop to boost specific stats!\n"
                "• Available in **3 tiers**: Low (+5), Medium (+10), High (+20)\n"
                "• **All treats also give +5 Bond!**\n"
                "• Use treats from Home → Inventory → Shop Treats\n"
                "• **6-hour cooldown** between uses (separate from main Treat button)\n"
                "• Max 5 of each treat type"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💀 Pet Death (if enabled)",
            value=(
                "If the server has death enabled and your pet's Health reaches 0, "
                "they will pass away from neglect. Take good care of them!"
            ),
            inline=False
        )
        
        return embed
    
    def get_growth_embed(self) -> discord.Embed:
        """Generate the Growth & Stages help embed."""
        embed = discord.Embed(
            title="🌱 Growth & Life Stages",
            color=discord.Color.teal()
        )
        
        embed.add_field(
            name="Life Stages",
            value=(
                "🍼 **Baby** - Newly adopted, needs lots of care\n"
                "🌱 **Juvenile** - Growing up, still tracked for medals\n"
                "🌟 **Adult** - Fully grown, ready to graduate!\n"
                "👴 **Senior** - Living peacefully in the Home"
            ),
            inline=False
        )
        
        # Build lifespan info from constants
        embed.add_field(
            name="📅 Growth Timeline",
            value=(
                "Different species have different lifespans:\n"
                f"• **Short:** Adult at day 5, lives ~35 days\n"
                f"• **Medium:** Adult at day 10, lives ~70 days\n"
                f"• **Long:** Adult at day 21, lives ~141 days\n"
                f"• **Extended:** Adult at day 30, lives ~210 days"
            ),
            inline=False
        )
        
        embed.add_field(
            name="⏰ Pet Days",
            value=(
                f"One 'pet day' = **{self.guild_settings.growth_day_length_hours}** real hours.\n"
                "Your pet ages and daily scores are calculated based on this cycle."
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎓 Graduation",
            value=(
                "When your pet reaches **Adult** stage:\n"
                "• A **🎓 Graduate!** button appears\n"
                "• You can choose to graduate them to your Home\n"
                "• Their care score determines their medal\n"
                "• You can then adopt a new pet!"
            ),
            inline=False
        )

        embed.add_field(
            name="🍯 Immortality (Golden Ambrosia)",
            value=(
                "Graduated Home pets will eventually pass away from old age — "
                "but you can prevent that with the **Golden Ambrosia**!\n\n"
                "• Purchase **🍯 Golden Ambrosia** from the **Treats Shop** (2,500 coins — Legendary)\n"
                "• Go to **Inventory → Shop Treats** and use it\n"
                "• Choose which Home pet to grant Immortality to\n"
                "• Confirm — your pet will **never die of old age**!\n\n"
                "✨ *Immortal pets still age through Senior stage, but their lifespan becomes endless. "
                "Only one Ambrosia is needed per pet.*"
            ),
            inline=False
        )

        return embed
    
    def get_medals_embed(self) -> discord.Embed:
        """Generate the Medals & Scoring help embed."""
        embed = discord.Embed(
            title="🏅 Medals & Care Scoring",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Daily Care Score",
            value=(
                "Each day, your care is scored based on:\n"
                "• 🍖 **Feeding** (30%) - Did you feed regularly?\n"
                "• 😊 **Happiness** (25%) - Is your pet happy?\n"
                "• ✨ **Cleanliness** (20%) - Did you groom?\n"
                "• ⚡ **Energy** (15%) - Did your pet get rest?\n"
                "• 🎁 **Bonus** (10%) - Extra treats and petting"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Daily Ratings",
            value=(
                "• ⭐⭐⭐⭐⭐ **Perfect** - 95%+ score\n"
                "• ⭐⭐⭐⭐ **Excellent** - 80%+ score\n"
                "• ⭐⭐⭐ **Good** - 60%+ score\n"
                "• ⭐⭐ **Fair** - 40%+ score\n"
                "• ⭐ **Poor** - 20%+ score\n"
                "• 💀 **Critical** - Below 20%"
            ),
            inline=True
        )
        
        embed.add_field(
            name="Medal Thresholds",
            value=(
                f"🥇 **Gold Medal** - {GOLD_THRESHOLD}%+ average\n"
                f"🥈 **Silver Medal** - {SILVER_THRESHOLD}%+ average\n"
                f"🥉 **Bronze Medal** - {BRONZE_THRESHOLD}%+ average\n"
                "❌ **No Medal** - Below bronze threshold"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🔥 Medal Streaks",
            value=(
                "Earn consecutive **Gold medals** to build a streak!\n"
                "Your streak resets if you earn Silver, Bronze, or no medal.\n"
                "Build long streaks for special achievements!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips for Gold",
            value=(
                "• Feed **at least twice** per day\n"
                "• Play and groom daily\n"
                "• Give treats and pet for bonus points\n"
                "• Don't let any stat go critical!"
            ),
            inline=False
        )
        
        return embed
    
    def get_home_embed(self) -> discord.Embed:
        """Generate the Pet Home help embed."""
        embed = discord.Embed(
            title="🏠 The Pet Home",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="What is the Home?",
            value=(
                "The Home is where your **graduated pets** live!\n"
                "Once a pet reaches adulthood and you choose to graduate them, "
                "they move to your Home and live happily."
            ),
            inline=False
        )
        
        embed.add_field(
            name="Home Benefits",
            value=(
                "• Pets in the Home **don't need daily care**\n"
                "• They maintain stable stats automatically\n"
                "• You can visit and interact with them anytime\n"
                "• Each pet displays their medal achievement"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Home Capacity",
            value=(
                f"Your Home can hold up to **{self.guild_settings.default_home_capacity}** pets.\n"
                "When it's full, you'll need to wait for pets to pass naturally "
                "before adding more."
            ),
            inline=False
        )
        
        embed.add_field(
            name="Life in the Home",
            value=(
                "• Pets continue to age slowly in the Home\n"
                "• **Adults** may eventually become **Seniors**\n"
                "• Seniors will eventually pass away peacefully of old age\n"
                "• Lifespan varies: Short-lived pets last ~1 month, longest ~6 months"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Interacting with Home Pets",
            value=(
                "Click on a pet in your Home to:\n"
                "• View their full stats and history\n"
                "• See their medal and growth story\n"
                "• Enjoy their company!"
            ),
            inline=False
        )
        
        return embed
    
    def get_memorial_embed(self) -> discord.Embed:
        """Generate the Memorial help embed."""
        embed = discord.Embed(
            title="🪦 The Pet Memorial",
            color=discord.Color.dark_grey()
        )
        
        embed.add_field(
            name="What is the Memorial?",
            value=(
                "The Memorial is a place to remember all your pets who have passed.\n"
                "Every pet's memory is preserved here forever."
            ),
            inline=False
        )
        
        embed.add_field(
            name="🕊️ Peaceful Passings",
            value=(
                "Pets who lived a full life and passed of **old age** in the Home:\n"
                "• Shown with a 🕊️ dove symbol\n"
                "• Display their earned medal\n"
                "• You can write a custom **epitaph** for them"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💔 Lost to Neglect",
            value=(
                "If death is enabled and a pet passes from neglect:\n"
                "• Shown with a 💔 broken heart symbol\n"
                "• No medal is awarded\n"
                "• Epitaphs are not allowed\n"
                "• A reminder to care better for future pets"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Writing Epitaphs",
            value=(
                "For peacefully passed pets, you can write a short epitaph:\n"
                "• Select the pet from the memorial list\n"
                "• Click the **Write Epitaph** button\n"
                "• Enter your heartfelt message\n"
                "• The epitaph will display on their memorial"
            ),
            inline=False
        )
        
        return embed
    
    def get_achievements_embed(self) -> discord.Embed:
        """Generate the Achievements help embed."""
        from ..database.achievements import get_total_achievement_count, get_category_display_order
        
        total = get_total_achievement_count()
        
        embed = discord.Embed(
            title="🏆 Achievements",
            description=f"There are **{total} achievements** to unlock across 5 categories!",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🐣 Adoption Achievements",
            value=(
                "Earned by adopting pets:\n"
                "• First Friend (1 pet)\n"
                "• Growing Family (5 pets)\n"
                "• Pet Collector, Dedicated Caretaker, Pet Whisperer..."
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏅 Medal Achievements",
            value=(
                "Earned by collecting medals:\n"
                "• First Gold/Silver/Bronze\n"
                "• Gold Collector (5 golds)\n"
                "• Medal streaks (3, 5, 10 consecutive golds)..."
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏠 Home Achievements",
            value=(
                "Related to your Pet Home:\n"
                "• Homeowner (first graduation)\n"
                "• Full House (5 pets in Home)\n"
                "• Gentle Goodbye (peaceful passing)..."
            ),
            inline=False
        )
        
        embed.add_field(
            name="💕 Care Achievements",
            value=(
                "Earned through caring actions:\n"
                "• Caring Heart (100 needs met)\n"
                "• Feeding Frenzy (50 feedings)\n"
                "• Play Time, Clean Freak, Treat Master..."
            ),
            inline=False
        )
        
        embed.add_field(
            name="✨ Special Achievements",
            value=(
                "Unique accomplishments:\n"
                "• Best Friends Forever (100 bond)\n"
                "• Long Life (30+ day pet)\n"
                "• Some achievements are **hidden** until unlocked!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="Viewing Your Achievements",
            value="Check the **Stats** page and click **Achievements** to see your progress!",
            inline=False
        )
        
        return embed
    
    def get_stats_tips_embed(self) -> discord.Embed:
        """Generate the Stats & Tips help embed."""
        embed = discord.Embed(
            title="📊 Stats & Pro Tips",
            color=discord.Color.orange()
        )
        
        embed.add_field(
            name="Understanding Pet Stats",
            value=(
                "❤️ **Health** - Overall wellbeing (damaged by critical stats)\n"
                "🍖 **Hunger** - Keep fed to avoid starvation\n"
                "😊 **Happiness** - Play and treats boost this\n"
                "✨ **Cleanliness** - Groom regularly\n"
                "⚡ **Energy** - Let your pet rest\n"
                "💕 **Bond** - Builds with play, treats, and petting"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📈 Stat Bars",
            value=(
                "• Stats range from **0% to 100%**\n"
                "• ⚠️ Warning when below 40%\n"
                "• 🔴 Critical when below 20%\n"
                "• Critical stats damage Health!"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎯 Pro Tips for Success",
            value=(
                "**1.** Check on your pet every few hours\n"
                "**2.** Feed twice daily minimum for gold scores\n"
                "**3.** Play + Groom daily for consistent care\n"
                "**4.** Use treats for big happiness/bond boosts\n"
                "**5.** Pet frequently - low cooldown, steady bond gain"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏆 Leaderboard",
            value=(
                "Compete with others on the server leaderboard!\n"
                "Rankings are based on total medals earned.\n"
                "Access via the **Leaderboard** button on the main menu."
            ),
            inline=False
        )
        
        embed.add_field(
            name="📖 Species Guide",
            value=(
                "Different species have different traits:\n"
                "• **Activity Level** affects energy needs\n"
                "• **Social Need** affects happiness decay\n"
                "• **Care Difficulty** varies by species\n"
                "• **Lifespan** determines growth speed"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔔 Danger Warning Notifications",
            value=(
                "Get @mentioned when your pet is in danger!\n"
                "• Warns when any stat drops to **30 or below**\n"
                "• Also warns if Health drops to **50 or below**\n"
                "• Gives you time to act before critical damage\n"
                "• Toggle in **Stats → Notifications** button\n"
                "• 🔔 Green = Enabled, 🔕 Red = Disabled"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🛒 Supply Shop Features",
            value=(
                "**Clothing:** Dress up your pets (Home → Shop → Clothing)\n"
                "**Shop Treats:** Buy stat-boosting treats (Home → Shop → Treats)\n"
                "**Inventory:** View & use owned items (Home → Inventory)"
            ),
            inline=False
        )
        
        return embed
    
    # ==========================================================================
    # CALLBACKS
    # ==========================================================================
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original user can interact."""
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This help menu isn't for you! Use the `petcord` command to open your own.",
                ephemeral=True
            )
            return False
        return True
    
    async def _finding_pets_callback(self, interaction: discord.Interaction):
        """Show Finding Pets page."""
        self.current_page = "finding"
        embed = self.get_finding_pets_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _pet_care_callback(self, interaction: discord.Interaction):
        """Show Pet Care page."""
        self.current_page = "care"
        embed = self.get_pet_care_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _growth_callback(self, interaction: discord.Interaction):
        """Show Growth & Stages page."""
        self.current_page = "growth"
        embed = self.get_growth_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _medals_callback(self, interaction: discord.Interaction):
        """Show Medals & Scoring page."""
        self.current_page = "medals"
        embed = self.get_medals_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _home_callback(self, interaction: discord.Interaction):
        """Show Pet Home page."""
        self.current_page = "home"
        embed = self.get_home_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _memorial_callback(self, interaction: discord.Interaction):
        """Show Memorial page."""
        self.current_page = "memorial"
        embed = self.get_memorial_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _achievements_callback(self, interaction: discord.Interaction):
        """Show Achievements page."""
        self.current_page = "achievements"
        embed = self.get_achievements_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _stats_tips_callback(self, interaction: discord.Interaction):
        """Show Stats & Tips page."""
        self.current_page = "stats"
        embed = self.get_stats_tips_embed()
        self._setup_sub_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _back_to_main_help_callback(self, interaction: discord.Interaction):
        """Go back to main help menu."""
        self.current_page = "main"
        embed = self.get_main_help_embed()
        self._setup_main_buttons()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _back_callback(self, interaction: discord.Interaction):
        """Go back to the original view."""
        if self.return_view and self.return_embed:
            await interaction.response.edit_message(embed=self.return_embed, view=self.return_view)
            self.stop()
        else:
            # Just close if no return view
            await self._close_callback(interaction)
    
    async def _close_callback(self, interaction: discord.Interaction):
        """Close the view."""
        self.stop()
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(view=self)
    
    async def on_timeout(self) -> None:
        """Handle view timeout."""
        self.cog._active_views.discard(self)
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass
    
    def stop(self) -> None:
        """Stop the view and unregister from cog."""
        self.cog._active_views.discard(self)
        super().stop()
