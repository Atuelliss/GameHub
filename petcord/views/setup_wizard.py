"""
Setup wizard view for Petcord cog.

A linear, 6-step wizard that walks an admin through initial configuration:
    Step 1 — Notification channel
    Step 2 — Default home capacity
    Step 3 — Pet death toggle
    Step 4 — Petcoin conversion toggle
    Step 5 — Petcoin conversion rate
    Step 6 — Enable the game
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

import discord
from discord.ui import Button, View

from ..common.constants import MAX_HOME_CAPACITY

if TYPE_CHECKING:
    from ..main import Petcord
    from ..common.models import GuildSettings


TOTAL_STEPS = 6

STEP_TITLES: Dict[int, str] = {
    1: "Notification Channel",
    2: "Default Home Capacity",
    3: "Pet Death",
    4: "Petcoin Conversion",
    5: "Conversion Rate",
    6: "Enable Game",
}

STEP_DESCRIPTIONS: Dict[int, str] = {
    1: (
        "Select the **notification channel** where Petcord will announce events "
        "such as pet deaths.\n\n"
        "This is optional — use **Skip** to leave it unset for now."
    ),
    2: (
        f"Set the **default home capacity** — how many pets each user can keep in "
        f"their Home at once.\n\n"
        f"Click **Set Capacity** to enter a number. (Max: {MAX_HOME_CAPACITY})"
    ),
    3: (
        "Should growing pets (baby/juvenile) be able to **die from neglect** "
        "if their stats drop too low?\n\n"
        "Home pets are not affected by this setting."
    ),
    4: (
        "Allow players to **convert Petcoin into Discord economy credits**?\n\n"
        "If enabled, players can exchange their Petcoin for the server's currency "
        "using the conversion rate set in the next step."
    ),
    5: (
        "Set the **conversion rate**: how many Petcoin are required to receive "
        "1 Discord economy credit.\n\n"
        "Example: a rate of 10 means 10 Petcoin → 1 credit.\n"
        "Click **Set Rate** to enter a value."
    ),
    6: (
        "Everything is configured! **Enable the game** to let players start "
        "adopting and caring for pets.\n\n"
        "You can toggle this at any time with `pcset enable` / `pcset disable`."
    ),
}


# ---------------------------------------------------------------------------
# Modal
# ---------------------------------------------------------------------------

class _ConversionRateModal(discord.ui.Modal, title="Set Conversion Rate"):
    rate: discord.ui.TextInput = discord.ui.TextInput(
        label="Petcoin per Discord Credit",
        placeholder="Enter a whole number (e.g. 10)",
        min_length=1,
        max_length=6,
        required=True,
    )

    def __init__(self, wizard: "PetcordSetupView", current_value: int) -> None:
        super().__init__()
        self.wizard = wizard
        self.rate.default = str(current_value)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            value = int(self.rate.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid whole number.", ephemeral=True
            )
            return

        if value < 1:
            await interaction.response.send_message(
                "❌ Conversion rate must be at least 1.", ephemeral=True
            )
            return

        self.wizard.conf.petcoin_conversion_rate = value
        self.wizard.cog.schedule_save()
        self.wizard.completed[5] = f"{value} Petcoin → 1 credit"
        await self.wizard._advance(interaction, from_modal=True)


class _HomeCapacityModal(discord.ui.Modal, title="Set Home Capacity"):
    capacity: discord.ui.TextInput = discord.ui.TextInput(
        label="Default Home Capacity",
        placeholder=f"Enter a number (1–{MAX_HOME_CAPACITY})",
        min_length=1,
        max_length=2,
        required=True,
    )

    def __init__(self, wizard: "PetcordSetupView", current_value: int) -> None:
        super().__init__()
        self.wizard = wizard
        self.capacity.default = str(current_value)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        try:
            value = int(self.capacity.value.strip())
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid whole number.", ephemeral=True
            )
            return

        if not 1 <= value <= MAX_HOME_CAPACITY:
            await interaction.response.send_message(
                f"❌ Capacity must be between 1 and {MAX_HOME_CAPACITY}.",
                ephemeral=True,
            )
            return

        self.wizard.conf.default_home_capacity = value
        self.wizard.cog.schedule_save()
        self.wizard.completed[2] = f"{value} pets"
        await self.wizard._advance(interaction, from_modal=True)


# ---------------------------------------------------------------------------
# Channel select
# ---------------------------------------------------------------------------

class _ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, wizard: "PetcordSetupView") -> None:
        super().__init__(
            placeholder="Select a text channel…",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
            row=0,
        )
        self.wizard = wizard

    async def callback(self, interaction: discord.Interaction) -> None:
        channel = self.values[0]
        self.wizard.conf.allowed_channel_id = channel.id
        self.wizard.cog.schedule_save()
        self.wizard.completed[1] = f"<#{channel.id}>"
        await self.wizard._advance(interaction)


# ---------------------------------------------------------------------------
# Main wizard view
# ---------------------------------------------------------------------------

class PetcordSetupView(View):
    """Linear 4-step setup wizard for first-time Petcord configuration."""

    def __init__(
        self,
        cog: "Petcord",
        conf: "GuildSettings",
        author_id: int,
    ) -> None:
        super().__init__(timeout=300)
        self.cog = cog
        self.conf = conf
        self.author_id = author_id
        self.current_step: int = 1
        self.completed: Dict[int, str] = {}
        self.message: Optional[discord.Message] = None
        self._build_current_step()

    # ------------------------------------------------------------------
    # Interaction guard
    # ------------------------------------------------------------------

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message(
                "This setup wizard is not yours to control.", ephemeral=True
            )
            return False
        return True

    # ------------------------------------------------------------------
    # Embed helpers
    # ------------------------------------------------------------------

    def _current_value_display(self, step: int) -> str:
        if step == 1:
            ch_id = self.conf.allowed_channel_id
            return f"<#{ch_id}>" if ch_id else "Not set"
        if step == 2:
            return f"{self.conf.default_home_capacity} pets"
        if step == 3:
            return "Enabled ⚠️" if self.conf.pet_death_enabled else "Disabled 🛡️"
        if step == 4:
            return "Enabled 💱" if self.conf.petcoin_conversion_enabled else "Disabled ❌"
        if step == 5:
            return f"{self.conf.petcoin_conversion_rate} Petcoin → 1 credit"
        if step == 6:
            return "Enabled ✅" if self.conf.game_is_enabled else "Disabled ❌"
        return "—"

    def _build_embed(self) -> discord.Embed:
        step = self.current_step
        embed = discord.Embed(
            title=f"🐾 Petcord Setup — Step {step} of {TOTAL_STEPS}",
            description=STEP_DESCRIPTIONS[step],
            color=discord.Color.blurple(),
        )
        embed.add_field(
            name=f"Current: {STEP_TITLES[step]}",
            value=self._current_value_display(step),
            inline=False,
        )
        if self.completed:
            lines = [
                f"✅ **{STEP_TITLES[s]}**: {self.completed[s]}"
                for s in sorted(self.completed)
            ]
            embed.add_field(name="Saved This Session", value="\n".join(lines), inline=False)
        embed.set_footer(text=f"Step {step} of {TOTAL_STEPS} • Changes save immediately")
        return embed

    def _build_summary_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🐾 Petcord Setup Complete!",
            description="All settings have been saved. Here's a summary:",
            color=discord.Color.green(),
        )
        for step in range(1, TOTAL_STEPS + 1):
            val = self.completed.get(step, self._current_value_display(step))
            embed.add_field(name=STEP_TITLES[step], value=val, inline=True)
        embed.set_footer(text="Use pcset commands to adjust any setting at any time.")
        return embed

    # ------------------------------------------------------------------
    # Step rendering
    # ------------------------------------------------------------------

    def _build_current_step(self) -> None:
        self.clear_items()
        step = self.current_step

        if step == 1:
            self.add_item(_ChannelSelect(self))
            self._add_skip_button()
        elif step == 2:
            self._add_capacity_button()
        elif step == 3:
            self._add_toggle_buttons(
                field="pet_death_enabled",
                step=3,
                enable_label="Enable Pet Death",
                disable_label="Disable Pet Death",
                enable_display="Enabled ⚠️",
                disable_display="Disabled 🛡️",
            )
        elif step == 4:
            self._add_toggle_buttons(
                field="petcoin_conversion_enabled",
                step=4,
                enable_label="Enable Conversion",
                disable_label="Disable Conversion",
                enable_display="Enabled 💱",
                disable_display="Disabled ❌",
            )
        elif step == 5:
            self._add_conversion_rate_button()
        elif step == 6:
            self._add_toggle_buttons(
                field="game_is_enabled",
                step=6,
                enable_label="Enable Game",
                disable_label="Disable Game",
                enable_display="Enabled ✅",
                disable_display="Disabled ❌",
            )

        if step > 1:
            self._add_back_button()

    def _add_skip_button(self) -> None:
        btn = Button(label="Skip", style=discord.ButtonStyle.secondary, row=1)

        async def cb(interaction: discord.Interaction) -> None:
            self.completed[1] = "Not set (skipped)"
            self.current_step += 1
            self._build_current_step()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)

        btn.callback = cb
        self.add_item(btn)

    def _add_capacity_button(self) -> None:
        btn = Button(
            label="Set Capacity",
            style=discord.ButtonStyle.primary,
            emoji="🏠",
            row=0,
        )

        async def cb(interaction: discord.Interaction) -> None:
            modal = _HomeCapacityModal(self, self.conf.default_home_capacity)
            await interaction.response.send_modal(modal)

        btn.callback = cb
        self.add_item(btn)

    def _add_toggle_buttons(
        self,
        field: str,
        step: int,
        enable_label: str,
        disable_label: str,
        enable_display: str,
        disable_display: str,
    ) -> None:
        enable_btn = Button(label=enable_label, style=discord.ButtonStyle.success, row=0)
        disable_btn = Button(label=disable_label, style=discord.ButtonStyle.danger, row=0)

        async def enable_cb(interaction: discord.Interaction) -> None:
            setattr(self.conf, field, True)
            self.cog.schedule_save()
            self.completed[step] = enable_display
            await self._advance(interaction)

        async def disable_cb(interaction: discord.Interaction) -> None:
            setattr(self.conf, field, False)
            self.cog.schedule_save()
            self.completed[step] = disable_display
            await self._advance(interaction)

        enable_btn.callback = enable_cb
        disable_btn.callback = disable_cb
        self.add_item(enable_btn)
        self.add_item(disable_btn)

    def _add_conversion_rate_button(self) -> None:
        btn = Button(
            label="Set Rate",
            style=discord.ButtonStyle.primary,
            emoji="💱",
            row=0,
        )

        async def cb(interaction: discord.Interaction) -> None:
            modal = _ConversionRateModal(self, self.conf.petcoin_conversion_rate)
            await interaction.response.send_modal(modal)

        btn.callback = cb
        self.add_item(btn)

    def _add_back_button(self) -> None:
        btn = Button(label="◀ Back", style=discord.ButtonStyle.secondary, row=1)

        async def cb(interaction: discord.Interaction) -> None:
            self.current_step -= 1
            self._build_current_step()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)

        btn.callback = cb
        self.add_item(btn)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    async def _advance(
        self,
        interaction: discord.Interaction,
        from_modal: bool = False,
    ) -> None:
        if self.current_step < TOTAL_STEPS:
            self.current_step += 1
            self._build_current_step()
            embed = self._build_embed()
            if from_modal:
                await interaction.response.defer()
                if self.message:
                    await self.message.edit(embed=embed, view=self)
            else:
                await interaction.response.edit_message(embed=embed, view=self)
        else:
            await self._finish(interaction, from_modal=from_modal)

    async def _finish(
        self,
        interaction: discord.Interaction,
        from_modal: bool = False,
    ) -> None:
        self.stop()
        embed = self._build_summary_embed()
        if from_modal:
            await interaction.response.defer()
            if self.message:
                await self.message.edit(embed=embed, view=None)
        else:
            await interaction.response.edit_message(embed=embed, view=None)

    # ------------------------------------------------------------------
    # Timeout
    # ------------------------------------------------------------------

    async def on_timeout(self) -> None:
        if self.message:
            try:
                embed = discord.Embed(
                    title="🐾 Petcord Setup — Timed Out",
                    description=(
                        "The setup wizard timed out after 5 minutes.\n"
                        "Any completed steps were already saved.\n"
                        "Run `petsetup` again to continue."
                    ),
                    color=discord.Color.red(),
                )
                await self.message.edit(embed=embed, view=None)
            except discord.HTTPException:
                pass
