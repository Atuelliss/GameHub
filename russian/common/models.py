import json
import discord
from pathlib import Path
from . import Base


class User(Base):
    # Russian Roulette stats
    player_wins: int = 0
    player_deaths: int = 0
    player_chickens: int = 0
    player_total_challenges: int = 0
    player_total_rejections: int = 0
    player_total_games_played: int = 0
    
    # Financial tracking
    total_amount_won: int = 0
    total_amount_lost: int = 0
    
    def update_game_stat(self, outcome: str, amount: int = 0) -> None:
        """
        Update Russian Roulette stats based on game outcome
        
        Parameters:
        - outcome: The result of the game ("win", "death", "chicken", "challenge", "rejection")
        - amount: The amount of credits won (positive) or lost (negative)
        """
        # Only increment games_played for actual gameplay outcomes
        if outcome in ["win", "death", "chicken"]:
            self.player_total_games_played += 1
    
        # Update outcome stats
        if outcome == "win":
            self.player_wins += 1
            self.total_amount_won += amount
        elif outcome == "death":
            self.player_deaths += 1
            self.total_amount_lost += amount
        elif outcome == "chicken":
            self.player_chickens += 1
            self.total_amount_lost += amount
        elif outcome == "challenge":
            self.player_total_challenges += 1
            # Remove the financial tracking here - no loss if challenge isn't accepted
        elif outcome == "rejection":
            self.player_total_rejections += 1


class GuildSettings(Base):
    users: dict[int, User] = {}
    
    # Russian Roulette settings
    min_bet: int = 100
    max_bet: int = 3000

    # Game can only be ran in specific channels if this is set.
    # Empty list means all channels are allowed
    allowed_channels: list[int] = []

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure users dict is initialized
        if not self.users:
            self.users = {}

    def get_user(self, user: discord.User | int) -> User:
        uid = user if isinstance(user, int) else user.id
        return self.users.setdefault(uid, User())
        
    def get_game_leaderboard(self) -> dict[int, dict]:
        """Get Russian Roulette leaderboard data for all users in the guild"""
        leaderboard = {}
        for uid, user in self.users.items():
            leaderboard[uid] = {
                "wins": user.player_wins,
                "deaths": user.player_deaths,
                "chickens": user.player_chickens,
                "challenges": user.player_total_challenges,
                "rejections": user.player_total_rejections,
                "games_played": user.player_total_games_played,
                "total_won": user.total_amount_won,
                "total_lost": user.total_amount_lost
            }
        return leaderboard
        
    def is_channel_allowed(self, channel_id: int) -> bool:
        """Check if a channel is allowed for Russian Roulette commands
        
        If allowed_channels list is empty, all channels are allowed
        """
        return not self.allowed_channels or channel_id in self.allowed_channels


class DB(Base):
    configs: dict[int, GuildSettings] = {}

    def get_conf(self, guild: discord.Guild | int) -> GuildSettings:
        gid = guild if isinstance(guild, int) else guild.id
        return self.configs.setdefault(gid, GuildSettings())
        
    @classmethod
    def from_file(cls, path: Path) -> "DB":
        """Load database from file"""
        if not path.exists():
            raise FileNotFoundError(f"Database file not found at {path}")
        
        with open(path, "r") as f:
            data = json.load(f)
        
        return cls.model_validate(data)
    
    def to_file(self, path: Path) -> None:
        """Save database to file"""
        # Ensure directory exists
        path.parent.mkdir(parents=True, exist_ok=True)
    
        with open(path, "w") as f:
            json.dump(self.model_dump(), f, indent=4)  # Changed from self.dict() to self.model_dump()
    
    # Helper methods for Russian Roulette
    def get_min_bet(self, guild_id: int) -> int:
        """Get minimum bet for a guild"""
        return self.get_conf(guild_id).min_bet
    
    def set_min_bet(self, guild_id: int, amount: int) -> None:
        self.get_conf(guild_id).min_bet = amount
    
    def get_max_bet(self, guild_id: int) -> int:
        return self.get_conf(guild_id).max_bet
    
    def set_max_bet(self, guild_id: int, amount: int) -> None:
        self.get_conf(guild_id).max_bet = amount
    
    def get_leaderboard(self, guild_id: int) -> dict:
        return self.get_conf(guild_id).get_game_leaderboard()
    
    def update_leaderboard(self, guild_id: int, player_id: int, outcome: str, amount: int = 0) -> None:
        user = self.get_conf(guild_id).get_user(player_id)
        user.update_game_stat(outcome, amount)
