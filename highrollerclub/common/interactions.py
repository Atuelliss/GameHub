from __future__ import annotations

from typing import Any

import aiohttp
import discord


_RECOVERABLE_INTERACTION_ERRORS = (discord.NotFound, aiohttp.ClientOSError, OSError)


async def safe_defer(interaction: discord.Interaction, **kwargs: Any) -> bool:
    try:
        await interaction.response.defer(**kwargs)
        return True
    except discord.InteractionResponded:
        return True
    except _RECOVERABLE_INTERACTION_ERRORS:
        return False


async def safe_response_edit_message(interaction: discord.Interaction, **kwargs: Any) -> bool:
    try:
        await interaction.response.edit_message(**kwargs)
        return True
    except discord.InteractionResponded:
        pass
    except _RECOVERABLE_INTERACTION_ERRORS:
        pass

    if interaction.message is None:
        return False

    try:
        await interaction.message.edit(**kwargs)
        return True
    except (_RECOVERABLE_INTERACTION_ERRORS, discord.HTTPException):
        return False


async def safe_edit_original_response(interaction: discord.Interaction, **kwargs: Any) -> bool:
    try:
        await interaction.edit_original_response(**kwargs)
        return True
    except _RECOVERABLE_INTERACTION_ERRORS:
        pass

    if interaction.message is None:
        return False

    try:
        await interaction.message.edit(**kwargs)
        return True
    except (_RECOVERABLE_INTERACTION_ERRORS, discord.HTTPException):
        return False