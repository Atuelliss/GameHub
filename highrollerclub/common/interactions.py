from __future__ import annotations

import functools
import logging
import weakref
from typing import Any

import aiohttp
import discord


log = logging.getLogger("red.highrollerclub.interactions")

_RECOVERABLE_INTERACTION_ERRORS = (discord.NotFound, aiohttp.ClientOSError, OSError)

# message id -> the view currently displayed on that message (weak, so finished views drop out)
_current_views: "weakref.WeakValueDictionary[int, discord.ui.View]" = weakref.WeakValueDictionary()


def claim_message(message: discord.Message | None, view: discord.ui.View | None) -> None:
    """Record `view` as the view now shown on `message`, so only it may edit the message on timeout."""
    if message is None:
        return
    if view is None:
        # Buttons were removed; no view owns the message any more.
        _current_views.pop(message.id, None)
        return
    view._hrc_message = message  # type: ignore[attr-defined]
    _current_views[message.id] = view


async def expire_view(view: discord.ui.View) -> None:
    """on_timeout helper: grey out the view's buttons on its message.

    Every screen reuses one message, so the message is only edited if this view is
    still the one displayed on it. A stale view left behind by a screen change must
    not overwrite the newer screen's buttons.
    """
    for item in view.children:
        if hasattr(item, "disabled"):
            item.disabled = True  # type: ignore[attr-defined]
    message = getattr(view, "_hrc_message", None)
    if message is None or _current_views.get(message.id) is not view:
        return
    try:
        await message.edit(view=view)
    except (*_RECOVERABLE_INTERACTION_ERRORS, discord.HTTPException):
        pass


async def finish_hand_on_timeout(view: discord.ui.View, finish) -> None:
    """on_timeout helper for games that hold the bet while a hand is in progress.

    `finish(interaction)` settles the hand (cash out, stand, draw...) so a player
    who walks away isn't left with a taken bet and no result. It reuses the last
    interaction (stored in `view._hrc_last_interaction` by the view's
    interaction_check): the view times out minutes after the last click, well
    inside Discord's 15-minute window for editing through that interaction.
    The finished hand is then shown with its buttons greyed out.
    """
    interaction = getattr(view, "_hrc_last_interaction", None)
    if interaction is None or getattr(view, "_hrc_busy", False):
        await expire_view(view)
        return
    view._hrc_busy = True  # type: ignore[attr-defined]
    try:
        await finish(interaction)
    except Exception:
        log.exception("Could not finish a timed-out hand in %s", type(view).__name__)
    finally:
        view._hrc_busy = False  # type: ignore[attr-defined]
    for item in view.children:
        if hasattr(item, "disabled"):
            item.disabled = True  # type: ignore[attr-defined]
    try:
        await interaction.edit_original_response(view=view)
    except (*_RECOVERABLE_INTERACTION_ERRORS, discord.HTTPException):
        await expire_view(view)


def one_at_a_time(func):
    """Decorator for view methods that move money or game state.

    Only one decorated call per view runs at a time. A fast double-click
    dispatches two callbacks before the screen changes; the second one is
    acknowledged and dropped instead of paying out or deducting again.
    The check-and-set happens before the first await, so it can't race.

    Decorate entry points only: a decorated method that calls another
    decorated method on the same view would be blocked by itself.
    """
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if getattr(self, "_hrc_busy", False):
            if args and isinstance(args[0], discord.Interaction):
                await safe_defer(args[0])
            return None
        self._hrc_busy = True
        try:
            return await func(self, *args, **kwargs)
        finally:
            self._hrc_busy = False
    return wrapper


def _claim_from_kwargs(interaction: discord.Interaction, kwargs: dict[str, Any]) -> None:
    if "view" in kwargs:
        claim_message(interaction.message, kwargs["view"])


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
        _claim_from_kwargs(interaction, kwargs)
        return True
    except discord.InteractionResponded:
        pass
    except _RECOVERABLE_INTERACTION_ERRORS:
        pass

    if interaction.message is None:
        return False

    try:
        await interaction.message.edit(**kwargs)
        _claim_from_kwargs(interaction, kwargs)
        return True
    except (_RECOVERABLE_INTERACTION_ERRORS, discord.HTTPException):
        return False


async def _prefix(interaction: discord.Interaction) -> str:
    """The server's command prefix, for messages that tell players what to run."""
    try:
        prefixes = await interaction.client.get_valid_prefixes(interaction.guild)  # type: ignore[attr-defined]
    except AttributeError:
        prefixes = []
    # Skip mention prefixes: they read badly inside a code span.
    return next((p for p in prefixes if not p.startswith("<@")), "[p]")


async def not_your_session(interaction: discord.Interaction, what: str = "game session") -> None:
    """Tell someone pressing another player's buttons how to open their own screen."""
    await interaction.response.send_message(
        f"This isn't your {what}. Run `{await _prefix(interaction)}highrollerclub` to start your own.",
        ephemeral=True,
    )


async def session_expired(view: discord.ui.View, interaction: discord.Interaction) -> bool:
    """True, after closing the screen, when its data is no longer the live data.

    Game screens keep the conf and user they opened with. A player wipe, a backup
    restore or a cog reload replaces those, and play on the old objects would never
    be saved. Call this before a new hand starts; a hand already under way is left
    to finish, so a bet that has been taken is always settled.
    """
    conf = getattr(view, "_conf", None)
    user = getattr(view, "_user", None)
    if conf is None or user is None:
        return False
    cog = interaction.client.get_cog("HighRollerClub")  # type: ignore[attr-defined]
    live_conf = getattr(cog, "db", None) and cog.db.configs.get(interaction.guild_id)  # type: ignore[union-attr]
    if live_conf is conf and conf.users.get(interaction.user.id) is user:
        return False

    view.stop()
    await expire_view(view)
    text = (
        "The club's data was wiped, restored or reloaded since you opened this screen. "
        f"Run `{await _prefix(interaction)}highrollerclub` to open a fresh one."
    )
    try:
        if interaction.response.is_done():
            await interaction.followup.send(text, ephemeral=True)
        else:
            await interaction.response.send_message(text, ephemeral=True)
    except (*_RECOVERABLE_INTERACTION_ERRORS, discord.HTTPException):
        pass
    return True


async def safe_edit_original_response(interaction: discord.Interaction, **kwargs: Any) -> bool:
    try:
        await interaction.edit_original_response(**kwargs)
        _claim_from_kwargs(interaction, kwargs)
        return True
    except _RECOVERABLE_INTERACTION_ERRORS:
        pass

    if interaction.message is None:
        return False

    try:
        await interaction.message.edit(**kwargs)
        _claim_from_kwargs(interaction, kwargs)
        return True
    except (_RECOVERABLE_INTERACTION_ERRORS, discord.HTTPException):
        return False