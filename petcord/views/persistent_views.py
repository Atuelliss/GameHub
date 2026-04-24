"""
Persistent fallback views for handling stale button interactions after bot restart/cog reload.

When the bot restarts, any active Petcord menus still visible in Discord will have buttons
that no longer map to an in-memory View. Without this fallback, clicking those buttons
produces a "View interaction referencing unknown view" warning and the interaction is silently
discarded. This module registers a persistent View (timeout=None) with matching custom_ids
so stale clicks get a friendly "session expired" response instead.
"""

from __future__ import annotations

import discord
from discord.ui import View, Button


# All custom_ids used by MainMenuView buttons in main_menu.py
MAIN_MENU_BUTTON_IDS = [
    "petcord:feed",
    "petcord:play",
    "petcord:groom",
    "petcord:rest",
    "petcord:treat",
    "petcord:pet_action",
    "petcord:owner_sleep",
    "petcord:find_pet",
    "petcord:home",
    "petcord:stats",
    "petcord:abandon",
    "petcord:memorial",
    "petcord:refresh",
    "petcord:close",
    "petcord:ack_death",
    "petcord:species_guide",
    "petcord:leaderboard",
    "petcord:graduate",
    "petcord:help",
]


class StaleMainMenuView(View):
    """Persistent view that catches stale button clicks from MainMenuView after a restart.

    Active MainMenuView instances are tracked by (message_id, custom_id) and take priority.
    This view (registered with no message_id) only fires when no active view matches,
    i.e. the original view was lost to a restart or cog reload.
    """

    def __init__(self):
        super().__init__(timeout=None)
        for i, cid in enumerate(MAIN_MENU_BUTTON_IDS):
            button = Button(
                custom_id=cid,
                label="\u200b",
                style=discord.ButtonStyle.secondary,
                row=i // 5,
            )
            button.callback = self._handle_stale
            self.add_item(button)

    async def _handle_stale(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            "\u23f3 This session has expired. Use the `petcord` command to open a new menu.",
            ephemeral=True,
        )
        # Remove stale buttons from the old message so the user doesn't click again
        try:
            await interaction.message.edit(view=None)
        except (discord.NotFound, discord.HTTPException):
            pass
