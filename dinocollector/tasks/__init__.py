# Task loops can be defined here
import asyncio
import random
import time
import logging
import aiohttp
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
        self.spawn_watchdog.start()
        log.debug("Spawn loop started")

    async def cog_unload(self):
        self.spawn_loop.cancel()
        self.spawn_watchdog.cancel()
        await super().cog_unload()

    @tasks.loop(seconds=60)
    async def spawn_loop(self):
        for guild in self.bot.guilds:
            try:
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
                    # Drop allowed channels that no longer exist (deleted channels can't be removed via command)
                    dead_ids = [cid for cid in conf.allowed_channels if guild.get_channel(cid) is None]
                    if dead_ids:
                        conf.allowed_channels = [cid for cid in conf.allowed_channels if cid not in dead_ids]
                        self.save()
                        log.warning(f"Removed deleted allowed channels for {guild.name}: {dead_ids}")

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
                    # Pick random text channel the bot can actually post in
                    text_channels = [
                        c for c in guild.channels
                        if isinstance(c, discord.TextChannel) and c.permissions_for(guild.me).send_messages
                    ]
                    if text_channels:
                        target_channel = random.choice(text_channels)

                if not target_channel:
                    # Nothing to spawn in - wait a full interval before retrying instead of every tick
                    conf.last_spawn = time.time()
                    continue

                if target_channel:
                    result = select_random_creature(
                        event_mode_enabled=conf.event_mode_enabled,
                        event_active_type=conf.event_active_type
                    )
                    if result:
                        embed, creature_data = result
                        try:
                            view = SpawnView(self, creature_data)
                            msg = await target_channel.send(embed=embed, view=view)
                            view.message = msg
                            conf.last_spawn = time.time()
                            conf.last_spawn_channel_id = target_channel.id
                            self.save()
                        except discord.Forbidden:
                            # Back off a full interval so a broken guild doesn't retry every tick
                            conf.last_spawn = time.time()
                            log.warning(f"Missing permissions to send in {target_channel.name} ({guild.name})")
                        except discord.HTTPException as e:
                            conf.last_spawn = time.time()
                            log.warning(f"HTTP error sending spawn in {guild.name}: {e}")
                        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
                            conf.last_spawn = time.time()
                            log.warning(f"Network error sending spawn in {guild.name}: {e}")
            except Exception as e:
                log.exception(f"Unexpected error in spawn loop for guild {guild.name} ({guild.id})", exc_info=e)

    @spawn_loop.before_loop
    async def before_spawn_loop(self):
        await self.bot.wait_until_red_ready()
        await self._db_ready.wait()
        log.debug("Spawn loop: bot ready and DB loaded, starting iterations")

    @tasks.loop(hours=1)
    async def spawn_watchdog(self):
        if not self.spawn_loop.is_running():
            log.warning("Spawn watchdog: spawn_loop is not running! Restarting...")
            self.spawn_loop.restart()

    @spawn_watchdog.before_loop
    async def before_spawn_watchdog(self):
        await self.bot.wait_until_red_ready()
        await self._db_ready.wait()
