# Task loops can be defined here
import asyncio
import random
import time
import logging
import discord
from discord.ext import tasks

from ..abc import CompositeMetaClass
from ..databases.gameinfo import select_random_creature
from ..views import SpawnView

log = logging.getLogger("red.dinocollector.tasks")

class TaskLoops(metaclass=CompositeMetaClass):
    """
    Subclass all task loops in this directory so you can import this single task loop class in your cog's class constructor.

    See `commands` directory for the same pattern.
    """
    
    def __init__(self, bot):
        super().__init__()
        self.spawn_loop.start()
        log.debug("Spawn loop started")

    async def cog_unload(self):
        self.spawn_loop.cancel()
        await super().cog_unload()

    @tasks.loop(seconds=60)
    async def spawn_loop(self):
        await self.bot.wait_until_red_ready()
        for guild in self.bot.guilds:
            conf = self.db.get_conf(guild)
            
            # log.info(f"Checking spawn for {guild.name}: Enabled={conf.game_is_enabled}, Mode={conf.spawn_mode}, Last={conf.last_spawn}, Interval={conf.spawn_interval}")

            if not conf.game_is_enabled or conf.spawn_mode != "time":
                continue
                
            if time.time() - conf.last_spawn < conf.spawn_interval:
                continue
            
            # RNG Check
            if random.randint(1, 100) > conf.spawn_chance:
                # log.debug(f"Spawn RNG skipped for {guild.name}")
                continue

            log.debug(f"Attempting spawn for {guild.name}")
            
            # Time to spawn!
            # Select a channel
            target_channel = None
            if conf.allowed_channels:
                # Pick random from allowed
                valid_channels = [guild.get_channel(cid) for cid in conf.allowed_channels]
                valid_channels = [c for c in valid_channels if c and isinstance(c, discord.TextChannel)]
                
                if valid_channels:
                    # If multiple channels, avoid the last one
                    if len(valid_channels) > 1 and conf.last_spawn_channel_id:
                        candidates = [c for c in valid_channels if c.id != conf.last_spawn_channel_id]
                        # Fallback if filtering removed everything (shouldn't happen if len > 1)
                        if not candidates:
                            candidates = valid_channels
                        target_channel = random.choice(candidates)
                    else:
                        target_channel = random.choice(valid_channels)
                else:
                    log.warning(f"No valid channels found for {guild.name} despite allowed_channels being set! IDs: {conf.allowed_channels}")
            else:
                # Pick random text channel
                text_channels = [c for c in guild.channels if isinstance(c, discord.TextChannel)]
                if text_channels:
                    target_channel = random.choice(text_channels)
            
            if target_channel:
                result = select_random_creature(
                    event_mode_enabled=conf.event_mode_enabled,
                    event_active_type=conf.event_active_type
                )
                if result:
                    embed, creature_data = result
                    conf.last_spawn = time.time()
                    conf.last_spawn_channel_id = target_channel.id
                    self.save()
                    try:
                        view = SpawnView(self, creature_data)
                        msg = await target_channel.send(embed=embed, view=view)
                        view.message = msg
                    except discord.Forbidden:
                        pass # Can't send in this channel
