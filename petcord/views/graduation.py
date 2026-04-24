"""
Graduation ceremony view for when pets reach adulthood.
"""

import time
import discord
from discord.ui import View, Button
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import User, GuildSettings

from ..common.constants import GOLD_THRESHOLD, SILVER_THRESHOLD, BRONZE_THRESHOLD


class GraduationView(View):
    """View for pet graduation ceremony."""

    def __init__(
        self,
        cog: "Petcord",
        user_data: "User",
        guild_settings: "GuildSettings",
        author_id: int = None
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.user_data = user_data
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.message = None
        
        # Add buttons
        self.add_item(SendToHomeButton())
        self.add_item(KeepGrowingButton())

    def _calculate_medal(self) -> tuple[str, str, str]:
        """
        Calculate medal based on growth average score.
        
        Returns:
            (medal_display, medal_key, medal_emoji) tuple
        """
        pet = self.user_data.current_pet
        avg_score = pet.growth_average_score
        
        if avg_score >= GOLD_THRESHOLD:
            return ("🥇 GOLD", "gold", "🥇")
        elif avg_score >= SILVER_THRESHOLD:
            return ("🥈 SILVER", "silver", "🥈")
        elif avg_score >= BRONZE_THRESHOLD:
            return ("🥉 BRONZE", "bronze", "🥉")
        else:
            return ("No Medal", "", "❌")

    def build_embed(self) -> discord.Embed:
        """Build graduation celebration embed."""
        pet = self.user_data.current_pet
        
        if not pet:
            return discord.Embed(
                title="❌ Error",
                description="No pet found!",
                color=discord.Color.red()
            )
        
        medal_display, medal_key, medal_emoji = self._calculate_medal()
        avg_score = pet.growth_average_score
        
        embed = discord.Embed(
            title="🎉 CONGRATULATIONS! 🎉",
            description=f"**{pet.name}** has grown into an Adult!",
            color=discord.Color.gold()
        )
        
        # Medal field
        embed.add_field(
            name="🏅 Medal Earned",
            value=(
                f"{medal_display}\n"
                f"Final Score: **{avg_score:.1f}%**\n"
                f"Growth Days: {pet.growth_total_days}"
            ),
            inline=False
        )
        
        # Care summary
        scores = pet.growth_daily_scores
        perfect = len([s for s in scores if s.rating == "perfect"])
        excellent = len([s for s in scores if s.rating == "excellent"])
        good = len([s for s in scores if s.rating == "good"])
        fair = len([s for s in scores if s.rating in ("fair", "poor", "critical")])
        
        embed.add_field(
            name="📊 Care Summary",
            value=(
                f"⭐ Perfect Days: **{perfect}**\n"
                f"✨ Excellent Days: **{excellent}**\n"
                f"👍 Good Days: **{good}**\n"
                f"😐 Other Days: **{fair}**\n"
                f"💕 Final Bond: **{pet.bond}**"
            ),
            inline=True
        )
        
        # Medal thresholds info
        embed.add_field(
            name="🎯 Medal Thresholds",
            value=(
                f"🥇 Gold: {GOLD_THRESHOLD}%+\n"
                f"🥈 Silver: {SILVER_THRESHOLD}%+\n"
                f"🥉 Bronze: {BRONZE_THRESHOLD}%+"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🏠 Ready for Home!",
            value=(
                f"**{pet.name}** is ready to move to your Home!\n\n"
                "• Pets in Home no longer need daily care\n"
                "• You can visit and interact with them anytime\n"
                "• They may eventually pass away of old age\n"
                "• You'll be able to adopt a new pet!"
            ),
            inline=False
        )
        
        embed.set_footer(text="Choose an option below")
        
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Only allow the original user to interact."""
        if self.author_id and interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your graduation ceremony! Use your own menu.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self) -> None:
        """Handle view timeout."""
        if self.message:
            try:
                for item in self.children:
                    item.disabled = True
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


class SendToHomeButton(Button):
    """Button to graduate pet to Home."""

    def __init__(self):
        super().__init__(
            label="Send to Home",
            emoji="🏠",
            style=discord.ButtonStyle.success,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: GraduationView = self.view
        user_data = view.user_data
        pet = user_data.current_pet
        
        if not pet:
            await interaction.response.send_message(
                "❌ Something went wrong - no pet found!",
                ephemeral=True
            )
            return
        
        # Check if home is full
        if len(user_data.home_pets) >= user_data.effective_home_capacity:
            await interaction.response.send_message(
                f"❌ Your Home is full! ({len(user_data.home_pets)}/{user_data.effective_home_capacity})\n\n"
                "You can keep growing your pet, or wait for a Home pet to pass.\n"
                "💡 **Tip:** Graduate more pets to unlock more Home capacity!",
                ephemeral=True
            )
            return
        
        # Calculate and set medal
        avg_score = pet.growth_average_score
        if avg_score >= GOLD_THRESHOLD:
            pet.medal = "gold"
            bond_bonus = 20
            user_data.gold_medals += 1
        elif avg_score >= SILVER_THRESHOLD:
            pet.medal = "silver"
            bond_bonus = 10
            user_data.silver_medals += 1
        elif avg_score >= BRONZE_THRESHOLD:
            pet.medal = "bronze"
            bond_bonus = 5
            user_data.bronze_medals += 1
        else:
            pet.medal = ""
            bond_bonus = 0
        
        # Apply graduation bonuses
        pet.medal_score = avg_score
        pet.bond = min(100, pet.bond + bond_bonus)
        pet.is_in_home = True
        pet.ready_to_graduate = False
        pet.graduated_timestamp = time.time()
        
        # Move pet to home
        user_data.home_pets.append(pet)
        user_data.current_pet = None
        user_data.total_pets_graduated += 1
        
        # Award legendarycoin every 5 graduations
        legendarycoin_earned = 0
        if user_data.total_pets_graduated % 5 == 0:
            legendarycoin_earned = 1
            user_data.legendarycoin += 1
            user_data.most_legendarycoin_earned += 1
        
        if pet.medal:
            user_data.total_medals += 1
        
        # Update medal streak (gold medals only)
        if pet.medal == "gold":
            user_data.current_medal_streak += 1
            user_data.best_medal_streak = max(
                user_data.best_medal_streak,
                user_data.current_medal_streak
            )
        else:
            user_data.current_medal_streak = 0
        
        # Award petcoins based on medal and lifespan
        from ..commands.helper_functions import award_graduation_petcoins
        petcoins_earned = award_graduation_petcoins(user_data, pet, pet.medal)
        
        # Update lifetime tracking
        if pet.bond > user_data.highest_bond_achieved:
            user_data.highest_bond_achieved = int(pet.bond)
        
        # Check for new achievements
        from ..database.achievements import check_and_award_achievements, build_achievement_unlock_embed
        new_achievements = await check_and_award_achievements(user_data)
        achievement_embed = build_achievement_unlock_embed(new_achievements)
        
        # Save
        view.cog.schedule_save()
        
        # Medal display
        medal_display = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(pet.medal, "")
        
        # Build petcoin display
        if petcoins_earned > 0:
            petcoin_text = f"💰 Petcoins Earned: +{petcoins_earned}\n"
        else:
            petcoin_text = ""
        
        # Build legendarycoin display
        if legendarycoin_earned > 0:
            legendarycoin_text = f"✨ Legendarycoin Earned: +{legendarycoin_earned} (Every 5 graduations!)\n"
        else:
            legendarycoin_text = ""
        
        embed = discord.Embed(
            title="🏠 Welcome Home!",
            description=(
                f"**{pet.name}** is now living in your Home! {medal_display}\n\n"
                f"💕 Bond Bonus: +{bond_bonus}\n"
                f"🏅 Total Medals: {user_data.total_medals}\n"
                f"{petcoin_text}"
                f"{legendarycoin_text}\n"
                f"Use the `petcord` command to adopt a new pet or visit your Home!"
            ),
            color=discord.Color.green()
        )
        
        # Send both embeds if achievements earned
        if achievement_embed:
            await interaction.response.edit_message(embeds=[embed, achievement_embed], view=None)
        else:
            await interaction.response.edit_message(embed=embed, view=None)
        view.stop()


class KeepGrowingButton(Button):
    """Button to skip graduation and keep pet growing."""

    def __init__(self):
        super().__init__(
            label="Keep Growing",
            emoji="🌱",
            style=discord.ButtonStyle.secondary,
            row=0
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        view: GraduationView = self.view
        pet = view.user_data.current_pet
        
        if not pet:
            await interaction.response.send_message(
                "❌ Something went wrong - no pet found!",
                ephemeral=True
            )
            return
        
        # Save without clearing ready_to_graduate — the Graduate button
        # must remain available on the main menu so they can come back to it.
        view.cog.schedule_save()
        
        embed = discord.Embed(
            title="🌱 Continuing to Grow",
            description=(
                f"**{pet.name}** will continue growing with you!\n\n"
                f"They can still graduate to Home anytime from the main menu.\n"
                f"Note: Your daily care score will keep updating."
            ),
            color=discord.Color.blue()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        view.stop()
