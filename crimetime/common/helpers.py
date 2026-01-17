import discord
from redbot.core import commands


def recalculate_p_bonus(user) -> None:
    """Recalculate a user's p_bonus based on their current p_ratio.
    
    This is a synchronous helper for use after PvP outcomes.
    Call this after modifying p_wins or p_losses.
    """
    p_ratio = user.p_ratio
    # Winning tiers (ratio >= 1 means wins >= losses)
    if p_ratio >= 5:           # 5:1 or better
        user.p_bonus = 0.25
    elif p_ratio >= 3:         # 3:1 to 5:1
        user.p_bonus = 0.15
    elif p_ratio >= 2:         # 2:1 to 3:1
        user.p_bonus = 0.1
    elif p_ratio >= 1:         # 1:1 to 2:1 (even or winning)
        user.p_bonus = 0.05
    # Losing tiers (ratio < 1 means losses > wins, using reciprocals)
    elif p_ratio >= 0.5:       # 1:2 losing
        user.p_bonus = -0.05
    elif p_ratio >= 0.33:      # 1:3 losing
        user.p_bonus = -0.1
    elif p_ratio >= 0.2:       # 1:5 losing
        user.p_bonus = -0.15
    elif p_ratio > 0:          # Worse than 1:5 but has wins
        user.p_bonus = -0.2
    else:                      # 0 wins (winless)
        user.p_bonus = -0.25


async def update_pbonus(cog, ctx: commands.Context, member: discord.Member) -> None:
    """Recalculate and update a user's P-bonus based on their win/loss ratio.
    
    This is the async version for use in commands like mugcheck and pbupdate.
    It looks up the user and saves after updating.
    """
    guildsettings = cog.db.get_conf(ctx.guild)
    user = guildsettings.get_user(member)
    recalculate_p_bonus(user)
    cog.save()
    