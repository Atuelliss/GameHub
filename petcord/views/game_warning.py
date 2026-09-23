"""
First-run game warning for Petcord cog.

Shown the first time a player opens the main menu. The player must accept
that Petcord is a pet-raising minigame where pets can and will pass away
before they can play. Rejecting closes the warning without creating any
player data.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import GuildSettings


def build_game_warning_embed(member: discord.Member) -> discord.Embed:
    """Build the first-run warning embed."""
    embed = discord.Embed(
        title="⚠️ Before You Begin - Petcord",
        description=(
            "**Petcord is a pet-raising minigame.**\n\n"
            "You'll adopt a virtual pet and care for it over real days: feeding, "
            "playing, grooming, and letting it rest.\n\n"
            "💔 **Your pets can and most likely will pass away.**\n"
            "• Growing pets can die if they're neglected and their needs aren't met.\n"
            "• Pets in your Home grow old and eventually pass away naturally.\n\n"
            "You can make pets immortal in the Home by feeding them ambrosia.\n"
            "Lost pets are remembered in your Memorial.\n\n"
            "Do you accept and want to start playing?"
        ),
        color=discord.Color.orange(),
    )
    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
    embed.set_footer(text="You only need to accept this once.")
    return embed


class GameWarningView(View):
    """Accept / Reject view for the first-run game warning."""

    def __init__(
        self,
        cog: "Petcord",
        guild_settings: "GuildSettings",
        author_id: int,
        timeout: float = 120,
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild_settings = guild_settings
        self.author_id = author_id
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This isn't your Petcord window! Use the `petcord` command to open your own.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="Accept", emoji="✅", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: Button) -> None:
        from .main_menu import MainMenuView

        self.stop()

        # Create the player's data only now that they've accepted
        user_data = self.guild_settings.get_user(interaction.user)
        user_data.accepted_game_warning = True
        self.cog.schedule_save()

        # Continue straight into the normal main menu in the same message
        view = MainMenuView(
            cog=self.cog,
            user_data=user_data,
            guild_settings=self.guild_settings,
            author_id=self.author_id,
        )
        embed = await view.build_embed()
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = self.message

    @discord.ui.button(label="Reject", emoji="❌", style=discord.ButtonStyle.danger)
    async def reject_button(self, interaction: discord.Interaction, button: Button) -> None:
        # Close the warning; no player data is created or changed
        self.stop()
        try:
            await interaction.message.delete()
        except discord.HTTPException:
            await interaction.response.edit_message(
                content="Petcord closed.", embed=None, view=None
            )

    async def on_timeout(self) -> None:
        # Treat no answer like Reject - remove the warning
        if self.message:
            try:
                await self.message.delete()
            except discord.HTTPException:
                pass
