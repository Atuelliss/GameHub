from ..abc import MixinMeta
import discord    

class Admin(MixinMeta):
    def __init__(self, bot):
        self.bot = bot
        super().__init__(bot)
        
    #-------------------------
    # Setup Disallowed Names
    def set_disallowed_name(self, guild: discord.Guild | int, name: str) -> None:
        conf = self.get_conf(guild)
        if name not in conf.disallowed_names:
            conf.disallowed_names.append(name)   

    # List disallowed names
    def list_disallowed_names(self, guild: discord.Guild | int) -> list[str]:
        return self.get_conf(guild).disallowed_names

    # Remove a name from disallowed list
    def remove_disallowed_name(self, guild: discord.Guild | int, name: str) -> None:
        conf = self.get_conf(guild)
        if name in conf.disallowed_names:
            conf.disallowed_names.remove(name)

    #-------------------------
    # Setup Allowable Channels
    def get_allowed_channels(self, guild: discord.Guild | int) -> list[int]:
        return self.get_conf(guild).allowed_channels

    def set_allowed_channels(self, guild: discord.Guild | int, channels: list[int]) -> None:
        self.get_conf(guild).allowed_channels = channels

    def add_allowed_channel(self, guild: discord.Guild | int, channel_id: int) -> None:
        conf = self.get_conf(guild)
        if channel_id not in conf.allowed_channels:
            conf.allowed_channels.append(channel_id)

    def remove_allowed_channel(self, guild: discord.Guild | int, channel_id: int) -> None:
        conf = self.get_conf(guild)
        if channel_id in conf.allowed_channels:
            conf.allowed_channels.remove(channel_id)

    def get_conf(self, guild):
        return self.db.get_conf(guild)
    #-------------------------