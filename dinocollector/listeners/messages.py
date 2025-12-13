import discord
import random
import time
from redbot.core import commands

from ..abc import MixinMeta
from ..databases.gameinfo import select_random_creature
from ..views import SpawnView


class MessageListeners(MixinMeta):
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        
        conf = self.db.get_conf(message.guild)
        if not conf.game_is_enabled:
            return
            
        if conf.allowed_channels and message.channel.id not in conf.allowed_channels:
            return

        # Message Spawn Logic
        if conf.spawn_mode == "message":
            # Check cooldown
            if time.time() - conf.last_spawn < conf.spawn_cooldown:
                return
            
            # Roll for spawn
            if random.randint(1, 100) <= conf.spawn_chance:
                result = select_random_creature(
                    event_mode_enabled=conf.event_mode_enabled,
                    event_active_type=conf.event_active_type
                )
                if result:
                    embed, creature_data = result
                    conf.last_spawn = time.time()
                    conf.last_spawn_channel_id = message.channel.id
                    self.save()
                    view = SpawnView(self, creature_data)
                    msg = await message.channel.send(embed=embed, view=view)
                    view.message = msg
