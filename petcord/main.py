"""
Main Petcord cog entry point.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional, Set

import discord
from discord.ui import View
from redbot.core import commands, Config
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path

from .abc import CompositeMetaClass
from .commands import UserCommands, AdminCommands
from .common.models import DB
from .tasks import DecayTask
from .views.persistent_views import StaleMainMenuView

log = logging.getLogger("red.petcord")


class Petcord(UserCommands, AdminCommands, commands.Cog, metaclass=CompositeMetaClass):
    """
    Virtual pet game where you raise adorable creatures!

    Find pets to adopt, care for them through their growth stages,
    and graduate them to your Home when they reach adulthood.
    Earn medals based on how well you raise your pets!
    """

    __version__ = "0.1.0"
    __author__ = ["Jayar/Vainne"]

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.db: DB = DB()
        self.data_path: Path = cog_data_path(self) / "data.json"
        self._save_lock: asyncio.Lock = asyncio.Lock()
        self._save_task: Optional[asyncio.Task] = None
        self._active_views: Set[View] = set()  # Track active views for cleanup
        self._load_failed: bool = False  # Track if database load failed
        self.decay_task: DecayTask = DecayTask(self)
        self.debug_log: list = []  # In-memory debug log for decay tracking

    async def cog_load(self) -> None:
        """Called when the cog is loaded."""
        # Register persistent fallback view so stale buttons after a
        # restart respond with "session expired" instead of being discarded.
        self._persistent_view = StaleMainMenuView()
        self.bot.add_view(self._persistent_view)
        asyncio.create_task(self._initialize())

    async def _initialize(self) -> None:
        """Initialize the cog after loading."""
        await self.bot.wait_until_red_ready()
        await self._load_data()
        self.decay_task.start()
        log.info(f"Petcord v{self.__version__} loaded successfully!")

    async def _load_data(self) -> None:
        """Load database from disk with backup protection."""
        self._load_failed = False  # Track if load failed
        
        if self.data_path.exists():
            # Create backup before attempting load
            backup_path = self.data_path.with_suffix('.json.backup')
            try:
                import shutil
                await asyncio.to_thread(shutil.copy2, self.data_path, backup_path)
                log.debug(f"Created backup at {backup_path}")
            except Exception as e:
                log.warning(f"Failed to create backup: {e}")
            
            try:
                self.db = await asyncio.to_thread(DB.from_file, self.data_path)
                log.debug(f"Loaded database from {self.data_path}")
            except Exception as e:
                log.error(f"Failed to load database: {e}")
                log.error("DATABASE LOAD FAILED - Saving is disabled until fixed!")
                log.error(f"Backup available at: {backup_path}")
                self._load_failed = True  # Prevent saving over corrupted data
                self.db = DB()
        else:
            log.debug("No existing database found, starting fresh")
            self.db = DB()

    async def cog_unload(self) -> None:
        """Called when the cog is unloaded."""
        # Stop the decay task
        self.decay_task.stop()
        
        # Stop the persistent fallback view
        if hasattr(self, '_persistent_view'):
            self._persistent_view.stop()
        
        # Stop all active views
        for view in list(self._active_views):
            view.stop()
            # Disable buttons on the message if possible
            if hasattr(view, 'message') and view.message:
                try:
                    for item in view.children:
                        item.disabled = True
                    await view.message.edit(view=view)
                except (discord.NotFound, discord.HTTPException):
                    pass
        self._active_views.clear()
        
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass
        
        # Final save (only if load succeeded)
        if not getattr(self, '_load_failed', False):
            await self.save()
        else:
            log.warning("Skipping final save - database load had failed")
        log.debug("Petcord cog unloaded")

    async def save(self) -> None:
        """Save database to disk with retry logic and rotating backups."""
        # Don't save if load failed - prevents overwriting backup
        if getattr(self, '_load_failed', False):
            log.warning("Save blocked - database load failed. Fix the issue and reload.")
            return
        
        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                async with self._save_lock:
                    # Create rotating backup before saving
                    await self._create_rotating_backup()
                    
                    await asyncio.to_thread(self.db.to_file, self.data_path)
                    log.debug("Database saved successfully")
                    return
            except Exception as e:
                if attempt < max_retries - 1:
                    log.warning(f"Save attempt {attempt + 1} failed: {e}, retrying...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    log.error(f"Failed to save database after {max_retries} attempts: {e}")
                    raise

    async def _create_rotating_backup(self) -> None:
        """Create a rotating backup, keeping up to 3 copies spaced ~8 hours apart."""
        import shutil
        from datetime import datetime
        
        if not self.data_path.exists():
            return
        
        backup_dir = self.data_path.parent / "backups"
        try:
            backup_dir.mkdir(exist_ok=True)
        except Exception as e:
            log.warning(f"Could not create backup directory: {e}")
            return
        
        # Check if we need a new backup (at least 8 hours since last)
        existing_backups = sorted(backup_dir.glob("data_*.json"), reverse=True)
        
        if existing_backups:
            # Get timestamp of most recent backup from filename
            try:
                latest = existing_backups[0]
                # Filename format: data_YYYYMMDD_HHMMSS.json
                timestamp_str = latest.stem.replace("data_", "")
                latest_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                hours_since = (datetime.now() - latest_time).total_seconds() / 3600
                
                if hours_since < 8:
                    # Too soon for another backup
                    return
            except Exception:
                pass  # If parsing fails, create a new backup anyway
        
        # Create new backup with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"data_{timestamp}.json"
        
        try:
            await asyncio.to_thread(shutil.copy2, self.data_path, backup_path)
            log.debug(f"Created backup: {backup_path.name}")
        except Exception as e:
            log.warning(f"Failed to create backup: {e}")
            return
        
        # Clean up old backups, keep only 3
        existing_backups = sorted(backup_dir.glob("data_*.json"), reverse=True)
        for old_backup in existing_backups[3:]:
            try:
                old_backup.unlink()
                log.debug(f"Removed old backup: {old_backup.name}")
            except Exception as e:
                log.warning(f"Failed to remove old backup {old_backup.name}: {e}")

    def get_available_backups(self) -> list:
        """Get list of available backup files."""
        backup_dir = self.data_path.parent / "backups"
        if not backup_dir.exists():
            return []
        return sorted(backup_dir.glob("data_*.json"), reverse=True)

    async def restore_from_backup(self, backup_index: int = 0) -> bool:
        """
        Restore database from a backup file.
        
        Args:
            backup_index: 0 = most recent, 1 = second most recent, etc.
        
        Returns:
            True if restore succeeded, False otherwise.
        """
        backups = self.get_available_backups()
        
        if not backups:
            log.error("No backups available to restore from")
            return False
        
        if backup_index >= len(backups):
            log.error(f"Backup index {backup_index} out of range (only {len(backups)} backups)")
            return False
        
        backup_path = backups[backup_index]
        
        try:
            self.db = await asyncio.to_thread(DB.from_file, backup_path)
            self._load_failed = False  # Clear the flag so saving works
            await self.save()  # Save immediately to restore the main file
            log.info(f"Successfully restored from backup: {backup_path.name}")
            return True
        except Exception as e:
            log.error(f"Failed to restore from backup: {e}")
            return False

    def schedule_save(self, delay: float = 1.0) -> None:
        """Schedule a save operation with debouncing."""
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()

        async def delayed_save():
            await asyncio.sleep(delay)
            await self.save()

        self._save_task = asyncio.create_task(delayed_save())

    def format_help_for_context(self, ctx: commands.Context) -> str:
        """Add version info to help text."""
        pre = super().format_help_for_context(ctx)
        return f"{pre}\n\nCog Version: {self.__version__}"

    async def red_delete_data_for_user(self, *, requester: str, user_id: int) -> None:
        """Delete user data per GDPR requirements."""
        deleted = False
        for guild_id, conf in self.db.configs.items():
            if user_id in conf.users:
                del conf.users[user_id]
                deleted = True
                log.info(f"Deleted data for user {user_id} in guild {guild_id}")
        
        if deleted:
            await self.save()

    # Debug command for testing Phase 1
    @commands.command(name="pcdebug")
    @commands.is_owner()
    async def petcord_debug(self, ctx: commands.Context) -> None:
        """Debug command to test cog functionality."""
        conf = self.db.get_conf(ctx.guild)
        user = conf.get_user(ctx.author)
        
        # Test data persistence
        user.total_interactions += 1
        await self.save()
        
        embed = discord.Embed(
            title="🐾 Petcord Debug",
            color=discord.Color.green()
        )
        embed.add_field(
            name="Cog Status",
            value=f"Version: {self.__version__}\nLoaded: ✅",
            inline=True
        )
        embed.add_field(
            name="Database Status",
            value=f"Guilds: {len(self.db.configs)}\nData path: `{self.data_path.name}`",
            inline=True
        )
        embed.add_field(
            name="Your Data",
            value=f"Interactions: {user.total_interactions}\nCurrent pet: {'Yes' if user.current_pet else 'No'}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    # Debug command for testing Phase 2 - Species Database
    @commands.command(name="pcspecies")
    @commands.is_owner()
    async def petcord_species(self, ctx: commands.Context, species_id: str = None) -> None:
        """Debug command to test species database."""
        from .database.species import (
            get_species, get_species_count, get_category_counts,
            get_random_species, SPECIES_DATABASE
        )
        from .database.appearance import generate_appearance, get_rarity_emoji
        
        if species_id:
            # Show specific species
            species = get_species(species_id)
            if not species:
                await ctx.send(f"❌ Species `{species_id}` not found.")
                return
            
            embed = discord.Embed(
                title=f"{species.emoji} {species.name}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Category", value=species.category.title(), inline=True)
            embed.add_field(name="Rarity", value=f"{get_rarity_emoji(species.rarity)} {species.rarity.replace('_', ' ').title()}", inline=True)
            embed.add_field(name="Care Difficulty", value=species.care_difficulty.title(), inline=True)
            embed.add_field(name="Activity", value=species.activity_level.replace('_', ' ').title(), inline=True)
            embed.add_field(name="Social Need", value=species.social_need.replace('_', ' ').title(), inline=True)
            embed.add_field(name="Lifespan", value=species.lifespan.title(), inline=True)
            embed.add_field(name="Coats", value=", ".join(species.possible_coats), inline=False)
            embed.add_field(name="Patterns", value=", ".join(species.possible_patterns), inline=False)
            embed.add_field(name="Temperament", value=species.temperament, inline=False)
            embed.add_field(name="Unique Interaction", value=f"{species.unique_interaction} ({species.unique_interaction_effect})", inline=False)
            
            await ctx.send(embed=embed)
        else:
            # Show database stats
            category_counts = get_category_counts()
            
            embed = discord.Embed(
                title="🐾 Species Database",
                description=f"Total species: **{get_species_count()}**",
                color=discord.Color.green()
            )
            
            for category, count in sorted(category_counts.items()):
                embed.add_field(name=category.replace('_', ' ').title(), value=str(count), inline=True)
            
            # Test random generation
            random_species = get_random_species()
            coat, pattern, rarity = generate_appearance(random_species)
            
            embed.add_field(
                name="🎲 Random Pet Generated",
                value=f"{random_species.emoji} **{random_species.name}**\nCoat: {coat}\nPattern: {pattern}\nRarity: {get_rarity_emoji(rarity)} {rarity.replace('_', ' ').title()}",
                inline=False
            )
            
            await ctx.send(embed=embed)
