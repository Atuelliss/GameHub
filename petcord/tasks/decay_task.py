"""
Background task for stat decay and pet aging.
"""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..main import Petcord

from ..database.species import get_species
from ..common.constants import (
    BASE_HUNGER_DECAY,
    BASE_HAPPINESS_DECAY,
    BASE_CLEANLINESS_DECAY,
    BASE_ENERGY_DECAY,
    CRITICAL_THRESHOLD,
    DANGER_WARNING_THRESHOLD,
    DANGER_WARNING_COOLDOWN,
    STAT_TIER_NOTIFICATION_COOLDOWN,
    STAT_TIER_EXCELLENT,
    STAT_TIER_GOOD,
    STAT_TIER_FAIR,
    STAT_TIER_LOW,
    STAT_TIERS,
    STAT_TIER_MESSAGES,
    DECAY_MULTIPLIERS,
    COOLDOWN_REST,
    REST_DECAY_MAX_REDUCTION,
    LIFE_STAGE_DECAY_MULTIPLIERS,
)

log = logging.getLogger("red.petcord.decay")


class DecayTask:
    """Background task for stat decay and pet aging."""

    def __init__(self, cog: "Petcord") -> None:
        self.cog = cog
        self.task: asyncio.Task = None
        self.decay_interval: int = 300  # 5 minutes between decay checks
        self._last_decay_time: float = 0.0

    def _get_rest_decay_multiplier(self, pet, current_time: float) -> float:
        """
        Calculate decay multiplier based on rest cooldown status.
        
        Returns a value between 0.5 (50% reduction) and 1.0 (normal decay).
        The reduction is strongest right after resting and fades linearly
        until the rest cooldown expires.
        """
        if pet.last_rested <= 0:
            return 1.0  # Never rested, normal decay
        
        rest_cooldown_seconds = COOLDOWN_REST * 3600
        time_since_rest = current_time - pet.last_rested
        
        # If past the cooldown, normal decay
        if time_since_rest >= rest_cooldown_seconds:
            return 1.0
        
        # Calculate progress through rest period (0.0 = just rested, 1.0 = cooldown expired)
        rest_progress = time_since_rest / rest_cooldown_seconds
        
        # Decay multiplier: starts at (1 - MAX_REDUCTION), fades to 1.0
        # At rest_progress=0: multiplier = 0.5 (50% reduction)
        # At rest_progress=1: multiplier = 1.0 (no reduction)
        min_multiplier = 1.0 - REST_DECAY_MAX_REDUCTION
        return min_multiplier + (REST_DECAY_MAX_REDUCTION * rest_progress)

    def _log_decay_debug(self, user_id: int, pet, species, decay_hours: float, 
                         rest_multiplier: float, life_stage_multiplier: float,
                         pre_stats: dict, post_stats: dict, 
                         decays: dict, category_multipliers: dict) -> None:
        """Log detailed decay information to the cog's debug_log list."""
        from datetime import datetime
        
        try:
            # Calculate rest info
            rest_active = rest_multiplier < 1.0
            rest_reduction_pct = round((1.0 - rest_multiplier) * 100, 1) if rest_active else 0
            
            # Calculate time remaining on rest if active
            rest_time_remaining_min = 0
            if rest_active and pet.last_rested > 0:
                rest_cooldown_seconds = COOLDOWN_REST * 3600
                time_since_rest = time.time() - pet.last_rested
                rest_time_remaining_min = round((rest_cooldown_seconds - time_since_rest) / 60, 1)
            
            # Check Owner Sleep status (should be inactive if we're here, but include for completeness)
            owner_sleep_active = False
            owner_sleep_remaining_min = 0
            current_time = time.time()
            if pet.decay_paused_until > 0 and current_time < pet.decay_paused_until:
                owner_sleep_active = True
                owner_sleep_remaining_min = round((pet.decay_paused_until - current_time) / 60, 1)
            
            # Life stage info
            life_stage_active = life_stage_multiplier < 1.0
            life_stage_reduction_pct = round((1.0 - life_stage_multiplier) * 100, 1) if life_stage_active else 0
            
            entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "pet_name": pet.name,
                "species": species.name if species else "Unknown",
                "category": species.category if species else "Unknown",
                "life_stage": pet.life_stage,
                "decay_hours": round(decay_hours, 3),
                "owner_sleep_active": owner_sleep_active,
                "owner_sleep_remaining_min": owner_sleep_remaining_min,
                "rest_active": rest_active,
                "rest_multiplier": round(rest_multiplier, 3),
                "rest_reduction_pct": rest_reduction_pct,
                "rest_time_remaining_min": rest_time_remaining_min,
                "life_stage_active": life_stage_active,
                "life_stage_multiplier": round(life_stage_multiplier, 3),
                "life_stage_reduction_pct": life_stage_reduction_pct,
                "category_multipliers": {k: round(v, 2) for k, v in category_multipliers.items()},
                "stats_before": {k: round(v, 1) for k, v in pre_stats.items()},
                "stats_after": {k: round(v, 1) for k, v in post_stats.items()},
                "decay_amounts": {k: round(v, 2) for k, v in decays.items()},
            }
            
            self.cog.debug_log.append(entry)
            
            # Keep log from growing too large (max 1000 entries)
            if len(self.cog.debug_log) > 1000:
                self.cog.debug_log.pop(0)
                
        except Exception as e:
            # Silently fail - debug logging shouldn't break gameplay
            log.warning(f"Debug log error: {e}")

    def _log_owner_sleep_debug(self, user_id: int, pet, remaining_min: float) -> None:
        """Log Owner Sleep (decay pause) status to debug log."""
        from datetime import datetime
        
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "pet_name": pet.name,
                "owner_sleep_active": True,
                "decay_paused": True,
                "pause_remaining_min": round(remaining_min, 1),
                "message": f"Decay SKIPPED - Owner Sleep active for {round(remaining_min, 1)} more minutes"
            }
            
            self.cog.debug_log.append(entry)
            
            # Keep log from growing too large (max 1000 entries)
            if len(self.cog.debug_log) > 1000:
                self.cog.debug_log.pop(0)
                
        except Exception as e:
            log.warning(f"Debug log error (owner sleep): {e}")

    def _log_decay_skipped(self, user_id: int, pet, reason: str, value: float) -> None:
        """Log when decay is skipped for debug purposes."""
        from datetime import datetime
        
        try:
            messages = {
                "recent_interaction": f"Decay SKIPPED - Last interaction was {round(value, 1)} minutes ago (minimum 3 min required)",
            }
            
            entry = {
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "pet_name": pet.name,
                "decay_skipped": True,
                "skip_reason": reason,
                "message": messages.get(reason, f"Decay skipped: {reason}")
            }
            
            self.cog.debug_log.append(entry)
            
            # Keep log from growing too large (max 1000 entries)
            if len(self.cog.debug_log) > 1000:
                self.cog.debug_log.pop(0)
                
        except Exception as e:
            log.warning(f"Debug log error (skipped): {e}")

    def start(self) -> None:
        """Start the decay task."""
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self._decay_loop())
            log.debug("Decay task started")

    def stop(self) -> None:
        """Stop the decay task."""
        if self.task and not self.task.done():
            self.task.cancel()
            log.debug("Decay task stopped")

    async def _decay_loop(self) -> None:
        """Main decay loop - runs continuously."""
        await asyncio.sleep(10)  # Initial delay to let cog fully initialize
        
        while True:
            try:
                await self._process_all_guilds()
                self._last_decay_time = time.time()
            except asyncio.CancelledError:
                raise  # Re-raise to properly exit
            except Exception as e:
                log.error(f"Decay task error: {e}", exc_info=True)
            
            await asyncio.sleep(self.decay_interval)

    async def _process_all_guilds(self) -> None:
        """Process decay for all guilds with enabled game."""
        pets_processed = 0
        home_pets_processed = 0
        
        for guild in self.cog.bot.guilds:
            conf = self.cog.db.get_conf(guild)
            
            if not conf.game_is_enabled:
                continue
            
            # Process each user
            for user_id, user_data in conf.users.items():
                # Process current growing pet
                pet = user_data.current_pet
                if pet and not pet.is_in_home:
                    # Check for daily rollover first
                    await self._check_daily_rollover(user_data, conf)
                    
                    # Then apply decay
                    await self._decay_pet(guild.id, user_id, user_data, conf)
                    pets_processed += 1
                
                # Process home pets (aging and natural death)
                if user_data.home_pets:
                    await self._process_home_pets(guild.id, user_id, user_data, conf)
                    home_pets_processed += len(user_data.home_pets)
        
        if pets_processed > 0 or home_pets_processed > 0:
            log.debug(f"Decay processed: {pets_processed} active pets, {home_pets_processed} home pets")
            self.cog.schedule_save()

    async def _decay_pet(self, guild_id: int, user_id: int, user_data, settings) -> None:
        """Apply decay to a single pet based on time since last interaction."""
        pet = user_data.current_pet
        species = get_species(pet.species_id)
        
        if not species:
            log.warning(f"Unknown species {pet.species_id} for pet {pet.name}")
            return
        
        # Check if decay is paused (Owner Sleep active)
        current_time = time.time()
        if pet.decay_paused_until > 0 and current_time < pet.decay_paused_until:
            # Debug logging if enabled
            if user_data.debug_mode:
                remaining_min = (pet.decay_paused_until - current_time) / 60
                self._log_owner_sleep_debug(user_id, pet, remaining_min)
            return  # Skip all decay while paused
        
        # Get category-specific decay multipliers
        category_multipliers = DECAY_MULTIPLIERS.get(species.category, {})
        
        # Calculate time since last decay check (in hours)
        # IMPORTANT: If Owner Sleep just expired, use the sleep expiration time as reference
        # This prevents massive instant decay when sleep ends
        current_time = time.time()
        reference_time = pet.last_interaction
        
        if pet.decay_paused_until > 0 and pet.decay_paused_until <= current_time:
            # Owner Sleep just expired - set last_interaction to 1 second before sleep ended
            # This overrides any interactions during sleep and ensures clean decay resumption
            # without a massive decay dump from time accumulated before/during sleep
            pet.last_interaction = pet.decay_paused_until - 1
            reference_time = pet.last_interaction
            # Clear the expired sleep timestamp
            pet.decay_paused_until = 0
        
        hours_since_check = (current_time - reference_time) / 3600
        
        # Only decay if there's been some time since last check
        if hours_since_check < 0.05:  # ~3 minutes minimum
            # Log skip reason if debug enabled
            if user_data.debug_mode:
                self._log_decay_skipped(user_id, pet, "recent_interaction", hours_since_check * 60)
            return
        
        # Cap at 12 hours to prevent instant death after long absences
        # This means max decay per cycle is 12 hours worth
        decay_hours = min(hours_since_check, 12)
        
        # Apply rest decay reduction (50% max reduction right after rest, fading to 0%)
        rest_multiplier = self._get_rest_decay_multiplier(pet, current_time)
        
        # Apply life stage multiplier (juveniles decay slower than babies)
        life_stage_multiplier = LIFE_STAGE_DECAY_MULTIPLIERS.get(pet.life_stage, 1.0)
        
        # Store pre-decay values for debug logging
        pre_hunger = pet.hunger
        pre_happiness = pet.happiness
        pre_cleanliness = pet.cleanliness
        pre_energy = pet.energy
        
        # Calculate individual stat decays: base rate × category multiplier × hours × rest reduction × life stage
        hunger_decay = BASE_HUNGER_DECAY * category_multipliers.get("hunger", 1.0) * decay_hours * rest_multiplier * life_stage_multiplier
        happiness_decay = BASE_HAPPINESS_DECAY * category_multipliers.get("happiness", 1.0) * decay_hours * rest_multiplier * life_stage_multiplier
        cleanliness_decay = BASE_CLEANLINESS_DECAY * category_multipliers.get("cleanliness", 1.0) * decay_hours * rest_multiplier * life_stage_multiplier
        energy_decay = BASE_ENERGY_DECAY * category_multipliers.get("energy", 1.0) * decay_hours * rest_multiplier * life_stage_multiplier
        
        # Apply decays (minimum 0, keep as float for accuracy)
        pet.hunger = max(0.0, pet.hunger - hunger_decay)
        pet.happiness = max(0.0, pet.happiness - happiness_decay)
        pet.cleanliness = max(0.0, pet.cleanliness - cleanliness_decay)
        pet.energy = max(0.0, pet.energy - energy_decay)
        
        # Debug logging if user has debug_mode enabled
        if user_data.debug_mode:
            self._log_decay_debug(
                user_id=user_id,
                pet=pet,
                species=species,
                decay_hours=decay_hours,
                rest_multiplier=rest_multiplier,
                life_stage_multiplier=life_stage_multiplier,
                pre_stats={"hunger": pre_hunger, "happiness": pre_happiness, "cleanliness": pre_cleanliness, "energy": pre_energy},
                post_stats={"hunger": pet.hunger, "happiness": pet.happiness, "cleanliness": pet.cleanliness, "energy": pet.energy},
                decays={"hunger": hunger_decay, "happiness": happiness_decay, "cleanliness": cleanliness_decay, "energy": energy_decay},
                category_multipliers=category_multipliers
            )
        
        # Check for stat tier changes and send friendly notifications
        await self._check_stat_tier_changes(guild_id, user_id, user_data, pet, species, settings, current_time)
        
        # Check for danger warning (before critical damage, so user has time to react)
        await self._check_danger_warning(guild_id, user_id, user_data, pet, settings, current_time)
        
        # Health damage from critical stats
        health_damage = 0
        if pet.hunger < CRITICAL_THRESHOLD:
            health_damage += 2  # Starving is most dangerous
        if pet.happiness < CRITICAL_THRESHOLD:
            health_damage += 1
        if pet.cleanliness < CRITICAL_THRESHOLD:
            health_damage += 1
        if pet.energy < CRITICAL_THRESHOLD:
            health_damage += 1
        
        # Apply health damage
        if health_damage > 0:
            pet.health = max(0, pet.health - health_damage)
            log.debug(f"Pet {pet.name} took {health_damage} health damage from critical stats")
        
        # Check for death from neglect
        if settings.pet_death_enabled and pet.health <= 0:
            await self._handle_pet_death(guild_id, user_id, user_data, "neglect", settings)
            return
        
        # Update last interaction to prevent runaway decay
        # (We don't want the same time period to be counted multiple times)
        # We set it to current time, so next decay cycle starts fresh
        pet.last_interaction = current_time

    def _get_stat_tier(self, value: int) -> str:
        """Determine the tier name for a stat value."""
        if value >= STAT_TIER_EXCELLENT:
            return "excellent"
        elif value >= STAT_TIER_GOOD:
            return "good"
        elif value >= STAT_TIER_FAIR:
            return "fair"
        elif value >= STAT_TIER_LOW:
            return "low"
        else:
            return "critical"
    
    def _tier_dropped(self, old_tier: str, new_tier: str) -> bool:
        """Check if tier dropped (new tier is worse than old tier)."""
        tier_order = {"excellent": 4, "good": 3, "fair": 2, "low": 1, "critical": 0}
        return tier_order.get(new_tier, 0) < tier_order.get(old_tier, 0)

    async def _check_stat_tier_changes(
        self,
        guild_id: int,
        user_id: int,
        user_data,
        pet,
        species,
        settings,
        current_time: float
    ) -> None:
        """Check for stat tier changes and send friendly notifications."""
        # Skip if user has notifications disabled
        if not user_data.warning_notifications:
            return
        
        # Skip if no allowed channel set
        if not settings.allowed_channel_id:
            return
        
        # Check cooldown to prevent spam (30 minutes between tier notifications)
        if current_time - user_data.last_stat_tier_notification < STAT_TIER_NOTIFICATION_COOLDOWN:
            return
        
        # Check each stat for tier changes
        tier_changes = []
        
        # Hunger
        new_hunger_tier = self._get_stat_tier(pet.hunger)
        if self._tier_dropped(pet.last_hunger_tier, new_hunger_tier):
            tier_changes.append(("hunger", new_hunger_tier))
        pet.last_hunger_tier = new_hunger_tier
        
        # Happiness
        new_happiness_tier = self._get_stat_tier(pet.happiness)
        if self._tier_dropped(pet.last_happiness_tier, new_happiness_tier):
            tier_changes.append(("happiness", new_happiness_tier))
        pet.last_happiness_tier = new_happiness_tier
        
        # Cleanliness
        new_cleanliness_tier = self._get_stat_tier(pet.cleanliness)
        if self._tier_dropped(pet.last_cleanliness_tier, new_cleanliness_tier):
            tier_changes.append(("cleanliness", new_cleanliness_tier))
        pet.last_cleanliness_tier = new_cleanliness_tier
        
        # Energy
        new_energy_tier = self._get_stat_tier(pet.energy)
        if self._tier_dropped(pet.last_energy_tier, new_energy_tier):
            tier_changes.append(("energy", new_energy_tier))
        pet.last_energy_tier = new_energy_tier
        
        # If no tier changes, skip sending notification
        if not tier_changes:
            return
        
        # Build and send notification for the most important tier change
        # Priority: critical > low > fair > good (we pick the worst)
        tier_priority = {"critical": 0, "low": 1, "fair": 2, "good": 3}
        tier_changes.sort(key=lambda x: tier_priority.get(x[1], 99))
        
        stat_name, tier = tier_changes[0]
        
        try:
            guild = self.cog.bot.get_guild(guild_id)
            if not guild:
                return
            
            channel = guild.get_channel(settings.allowed_channel_id)
            if not channel:
                return
            
            # Get the message for this stat and tier
            messages = STAT_TIER_MESSAGES.get(stat_name, {})
            message = messages.get(tier, "")
            
            if not message:
                return
            
            # Format with pet info
            species_name = species.name if species else "pet"
            formatted_message = message.format(name=pet.name, species=species_name)
            
            # Send as a simple message (not embed, to feel more casual)
            await channel.send(f"<@{user_id}> {formatted_message}")
            
            # Update cooldown
            user_data.last_stat_tier_notification = current_time
            log.debug(f"Sent tier change notification for {pet.name}: {stat_name} -> {tier}")
            
        except Exception as e:
            log.debug(f"Failed to send tier change notification: {e}")

    async def _check_danger_warning(
        self, 
        guild_id: int, 
        user_id: int, 
        user_data, 
        pet, 
        settings, 
        current_time: float
    ) -> None:
        """Check if pet is in danger and send warning notification if enabled."""
        # Skip if user has notifications disabled
        if not user_data.warning_notifications:
            return
        
        # Skip if no allowed channel set
        if not settings.allowed_channel_id:
            return
        
        # Check cooldown to prevent spam (1 hour between warnings)
        if current_time - user_data.last_warning_sent < DANGER_WARNING_COOLDOWN:
            return
        
        # Check which stats are in danger zone (above critical but getting close)
        danger_stats = []
        if pet.hunger <= DANGER_WARNING_THRESHOLD:
            danger_stats.append(("🍖 Hunger", int(pet.hunger)))
        if pet.happiness <= DANGER_WARNING_THRESHOLD:
            danger_stats.append(("😊 Happiness", int(pet.happiness)))
        if pet.cleanliness <= DANGER_WARNING_THRESHOLD:
            danger_stats.append(("🧹 Cleanliness", int(pet.cleanliness)))
        if pet.energy <= DANGER_WARNING_THRESHOLD:
            danger_stats.append(("😴 Energy", int(pet.energy)))
        
        # Also warn if health is getting low
        if pet.health <= 50:
            danger_stats.append(("❤️ Health", int(pet.health)))
        
        # Only send warning if there are danger stats
        if not danger_stats:
            return
        
        try:
            guild = self.cog.bot.get_guild(guild_id)
            if not guild:
                return
            
            channel = guild.get_channel(settings.allowed_channel_id)
            if not channel:
                return
            
            # Get the server's command prefix
            try:
                prefixes = await self.cog.bot.get_valid_prefixes(guild)
                prefix = prefixes[0] if prefixes else "!"
            except Exception:
                prefix = "!"
            
            # Build warning message
            stat_lines = "\n".join([f"• {name}: **{value}**" for name, value in danger_stats])
            
            embed = discord.Embed(
                title="⚠️ Pet Danger Warning!",
                description=(
                    f"<@{user_id}>, your pet **{pet.name}** needs attention!\n\n"
                    f"The following stats are dangerously low:\n{stat_lines}\n\n"
                    f"If these stats drop further, your pet's health will decline. "
                    f"Use `{prefix}petcord` to care for your pet before it's too late!"
                ),
                color=discord.Color.orange()
            )
            embed.set_footer(text="Disable these warnings in Stats → Notifications")
            
            await channel.send(content=f"<@{user_id}>", embed=embed)
            
            # Update cooldown
            user_data.last_warning_sent = current_time
            log.debug(f"Sent danger warning for {pet.name} (user {user_id})")
            
        except Exception as e:
            log.debug(f"Failed to send danger warning: {e}")

    async def _handle_pet_death(self, guild_id: int, user_id: int, user_data, cause: str, settings) -> None:
        """Handle pet death from neglect."""
        from ..common.models import PetMemorial
        
        pet = user_data.current_pet
        current_time = time.time()
        
        log.info(f"Pet {pet.name} (user {user_id}) died from {cause}")
        
        # Create memorial entry
        memorial = PetMemorial(
            name=pet.name,
            species_id=pet.species_id,
            coat_color=pet.coat_color,
            pattern=pet.pattern,
            rarity=pet.rarity,
            adopted_timestamp=pet.adopted_timestamp,
            graduated_timestamp=0.0,  # Never graduated
            passed_timestamp=current_time,
            total_lifespan_days=int(pet.age_days),
            death_cause=cause,
            medal="",  # No medal for neglected pets
            medal_score=0.0,
            final_bond=int(pet.bond),
            reached_home=False,
            epitaph_allowed=False  # Can't write epitaph for neglected pets
        )
        
        # Update user data
        user_data.memorial.append(memorial)
        user_data.current_pet = None
        user_data.pets_lost_to_neglect += 1
        user_data.total_pets_passed += 1
        
        # Set pending notification for when user next opens petcord
        user_data.pending_death_notification = True
        user_data.pending_death_pet_name = pet.name
        user_data.pending_death_cause = cause
        user_data.pending_death_age_days = int(pet.age_days)
        user_data.pending_death_bond = int(pet.bond)
        
        # Try to notify the user via channel message
        await self._send_death_notification(
            guild_id=guild_id,
            user_id=user_id,
            pet_name=pet.name,
            death_cause=cause,
            age_days=int(pet.age_days),
            bond=pet.bond,
            medal=None,
            settings=settings,
            achievement_embed=None  # No achievements for neglect deaths
        )

    async def _check_daily_rollover(self, user_data, settings) -> None:
        """Check if a new day has started and roll over tracking."""
        from ..commands.helper_functions import (
            initialize_daily_tracking,
            calculate_daily_score
        )
        
        pet = user_data.current_pet
        if not pet:
            return
        
        # Initialize tracking if not set
        if not user_data.current_day_start:
            initialize_daily_tracking(user_data)
            return
        
        # Check if a full day has passed
        hours_per_day = settings.growth_day_length_hours
        seconds_per_day = hours_per_day * 3600
        current_time = time.time()
        
        if current_time - user_data.current_day_start >= seconds_per_day:
            # Day complete - finalize score
            final_score = calculate_daily_score(user_data, pet)
            log.debug(f"Day {pet.age_days} complete for {pet.name}, score: {final_score:.1f}")
            
            # Track needs met/failed for each stat at end of day
            # Threshold of 40 - above = met, below = failed
            NEED_THRESHOLD = 40
            
            if pet.hunger >= NEED_THRESHOLD:
                user_data.hunger_needs_met += 1
            else:
                user_data.hunger_needs_failed += 1
            
            if pet.happiness >= NEED_THRESHOLD:
                user_data.happiness_needs_met += 1
            else:
                user_data.happiness_needs_failed += 1
            
            if pet.cleanliness >= NEED_THRESHOLD:
                user_data.cleanliness_needs_met += 1
            else:
                user_data.cleanliness_needs_failed += 1
            
            if pet.energy >= NEED_THRESHOLD:
                user_data.energy_needs_met += 1
            else:
                user_data.energy_needs_failed += 1
            
            # Add to history
            if user_data.current_day_scores:
                user_data.care_history.append(user_data.current_day_scores)
                pet.growth_daily_scores.append(user_data.current_day_scores)
            
            # Update running average
            if pet.growth_daily_scores:
                all_scores = [s.final_score for s in pet.growth_daily_scores]
                pet.growth_average_score = sum(all_scores) / len(all_scores)
                pet.growth_total_days = len(all_scores)
            
            # Age the pet
            pet.age_days += 1
            
            # Check for life stage transition
            await self._check_life_stage(user_data, pet)
            
            # Start new day
            initialize_daily_tracking(user_data)

    async def _check_life_stage(self, user_data, pet) -> None:
        """Check if pet should transition to a new life stage."""
        from ..database.species import get_species
        from ..common.constants import STAGE_THRESHOLDS
        
        species = get_species(pet.species_id)
        if not species:
            return
        
        # Get thresholds for this species' lifespan
        thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
        
        # Determine new stage based on age
        new_stage = "baby"
        for stage in ["senior", "adult", "juvenile", "baby"]:
            if pet.age_days >= thresholds.get(stage, 0):
                new_stage = stage
                break
        
        # Check if stage changed
        if new_stage != pet.life_stage:
            old_stage = pet.life_stage
            pet.life_stage = new_stage
            log.info(f"Pet {pet.name} grew from {old_stage} to {new_stage}!")
            
            # Mark as ready to graduate when reaching adult
            if new_stage == "adult" and not pet.reached_adult_timestamp:
                pet.reached_adult_timestamp = time.time()
                pet.ready_to_graduate = True

    async def _process_home_pets(self, guild_id: int, user_id: int, user_data, settings) -> None:
        """Process aging and potential death for home pets."""
        from ..common.constants import STAGE_THRESHOLDS
        
        current_time = time.time()
        
        # Iterate in reverse so we can safely remove pets
        for i in range(len(user_data.home_pets) - 1, -1, -1):
            pet = user_data.home_pets[i]
            
            # Skip immortal pets - they never age or die
            if pet.is_immortal:
                continue
            
            # Slow decay for home pets (cosmetic only, never critical)
            # Home pets maintain happiness/cleanliness at reasonable levels
            pet.happiness = max(50, pet.happiness - 1)
            pet.cleanliness = max(40, pet.cleanliness - 1)
            
            # Age the pet slowly (based on decay interval)
            # Home pets age at the same rate as growing pets
            hours_since_check = self.decay_interval / 3600
            day_length_hours = settings.growth_day_length_hours
            pet.age_days += hours_since_check / day_length_hours
            
            # Get species info for lifespan
            species = get_species(pet.species_id)
            if not species:
                continue
            
            thresholds = STAGE_THRESHOLDS.get(species.lifespan, STAGE_THRESHOLDS["medium"])
            
            # Check for stage transition (adult -> senior)
            if pet.life_stage == "adult" and pet.age_days >= thresholds.get("senior", 21):
                pet.life_stage = "senior"
                log.info(f"Home pet {pet.name} became a senior!")
            
            # Check for natural death (50% beyond senior threshold)
            max_age = thresholds.get("max_age", thresholds.get("senior", 21) * 1.5)
            
            if pet.age_days >= max_age:
                await self._handle_natural_death(guild_id, user_id, user_data, pet, i, settings)

    async def _handle_natural_death(
        self, 
        guild_id: int, 
        user_id: int, 
        user_data, 
        pet, 
        index: int,
        settings
    ) -> None:
        """Handle natural death from old age for a home pet."""
        from ..common.models import PetMemorial
        
        current_time = time.time()
        
        log.info(f"Home pet {pet.name} (user {user_id}) passed away peacefully of old age")
        
        # Create memorial entry
        memorial = PetMemorial(
            name=pet.name,
            species_id=pet.species_id,
            coat_color=pet.coat_color,
            pattern=pet.pattern,
            rarity=pet.rarity,
            adopted_timestamp=pet.adopted_timestamp,
            graduated_timestamp=pet.graduated_timestamp,
            passed_timestamp=current_time,
            total_lifespan_days=int(pet.age_days),
            death_cause="old_age",
            medal=pet.medal,
            medal_score=pet.medal_score,
            final_bond=int(pet.bond),
            reached_home=True,
            epitaph_allowed=True  # Can write epitaph for pets that passed naturally
        )
        
        # Update user data
        user_data.memorial.append(memorial)
        user_data.home_pets.pop(index)
        user_data.pets_passed_naturally += 1
        user_data.total_pets_passed += 1
        user_data.longest_pet_lifespan = max(
            user_data.longest_pet_lifespan, 
            int(pet.age_days)
        )
        
        # Set pending notification for when user next opens petcord
        user_data.pending_death_notification = True
        user_data.pending_death_pet_name = pet.name
        user_data.pending_death_cause = "old_age"
        user_data.pending_death_age_days = int(pet.age_days)
        user_data.pending_death_bond = int(pet.bond)
        
        # Check for new achievements
        from ..database.achievements import check_and_award_achievements, build_achievement_unlock_embed
        new_achievements = await check_and_award_achievements(user_data)
        achievement_embed = build_achievement_unlock_embed(new_achievements)
        
        # Notify the user via channel message
        await self._send_death_notification(
            guild_id=guild_id,
            user_id=user_id,
            pet_name=pet.name,
            death_cause="old_age",
            age_days=int(pet.age_days),
            bond=pet.bond,
            medal=pet.medal,
            settings=settings,
            achievement_embed=achievement_embed
        )

    async def _send_death_notification(
        self,
        guild_id: int,
        user_id: int,
        pet_name: str,
        death_cause: str,
        age_days: int,
        bond: int,
        medal: str,
        settings,
        achievement_embed=None
    ) -> None:
        """Send a death notification to the allowed channel."""
        # Check if there's an allowed channel set
        if not settings.allowed_channel_id:
            return
        
        try:
            guild = self.cog.bot.get_guild(guild_id)
            if not guild:
                return
            
            channel = guild.get_channel(settings.allowed_channel_id)
            if not channel:
                return
            
            # Build the notification embed
            if death_cause == "old_age":
                medal_display = {"gold": "🥇", "silver": "🥈", "bronze": "🥉"}.get(medal, "")
                
                embed = discord.Embed(
                    title="🕊️ A Peaceful Passing",
                    description=(
                        f"<@{user_id}>'s beloved companion **{pet_name}** {medal_display} "
                        f"has passed away peacefully of old age after **{age_days} days**.\n\n"
                        f"They lived a full and happy life.\n"
                        f"Final Bond: 💕 {bond}\n\n"
                        f"They've been added to the Memorial, where an epitaph can be written "
                        f"to honor their memory."
                    ),
                    color=discord.Color.purple()
                )
            else:  # neglect
                embed = discord.Embed(
                    title="💔 Tragic News...",
                    description=(
                        f"<@{user_id}>'s pet **{pet_name}** has passed away from neglect "
                        f"after only **{age_days} days**.\n\n"
                        f"They've been added to the Memorial. Please take better care "
                        f"of your next companion."
                    ),
                    color=discord.Color.dark_grey()
                )
            
            # Send with any achievement embeds
            embeds = [embed]
            if achievement_embed:
                embeds.append(achievement_embed)
            
            await channel.send(embeds=embeds)
        except Exception as e:
            log.debug(f"Failed to send death notification: {e}")


# Need discord import for notifications
import discord
