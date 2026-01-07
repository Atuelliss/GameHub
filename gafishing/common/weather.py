"""
Weather system for Greenacres Fishing.
Weather is influenced by season and time of day.
"""

import random
from enum import Enum
from typing import TypedDict

import discord

from .models import DB


class WeatherType(Enum):
    """Weather types with their properties: (name, emoji, fish_modifier, description)"""
    CLEAR = ("Clear", "☀️", 1.0, "Clear skies and calm waters.")
    PARTLY_CLOUDY = ("Partly Cloudy", "⛅", 1.1, "Some clouds but nice fishing weather.")
    CLOUDY = ("Cloudy", "☁️", 1.15, "Overcast skies. Fish are more active.")
    LIGHT_RAIN = ("Light Rain", "🌦️", 1.2, "Light rain bringing insects to the surface.")
    RAIN = ("Rain", "🌧️", 1.25, "Steady rain. Fish are feeding actively!")
    HEAVY_RAIN = ("Heavy Rain", "⛈️", 0.8, "Stormy conditions. Fishing is challenging.")
    THUNDERSTORM = ("Thunderstorm", "🌩️", 0.5, "Dangerous storm! Not safe to fish.")
    FOG = ("Fog", "🌫️", 1.1, "Misty conditions. Fish feel secure.")
    SNOW = ("Snow", "🌨️", 0.7, "Cold and snowy. Fish are sluggish.")
    WINDY = ("Windy", "💨", 0.9, "Strong winds making casting difficult.")
    HEATWAVE = ("Heatwave", "🔥", 0.6, "Oppressive heat. Fish are deep and inactive.")
    
    @property
    def name_str(self) -> str:
        return self.value[0]
    
    @property
    def emoji(self) -> str:
        return self.value[1]
    
    @property
    def fish_modifier(self) -> float:
        """Multiplier for catch rates. >1 = better fishing, <1 = worse."""
        return self.value[2]
    
    @property
    def description(self) -> str:
        return self.value[3]


class Weather(TypedDict):
    """Type for current weather information."""
    type: str
    emoji: str
    description: str
    fish_modifier: float
    temperature: int  # In Fahrenheit
    wind_speed: int  # In mph


# Season-based weather weights: {WeatherType: weight}
# Higher weight = more likely to occur
SEASON_WEATHER_WEIGHTS: dict[str, dict[WeatherType, int]] = {
    "Spring": {
        WeatherType.CLEAR: 20,
        WeatherType.PARTLY_CLOUDY: 25,
        WeatherType.CLOUDY: 20,
        WeatherType.LIGHT_RAIN: 15,
        WeatherType.RAIN: 10,
        WeatherType.HEAVY_RAIN: 5,
        WeatherType.THUNDERSTORM: 3,
        WeatherType.FOG: 10,
        WeatherType.WINDY: 8,
    },
    "Summer": {
        WeatherType.CLEAR: 35,
        WeatherType.PARTLY_CLOUDY: 25,
        WeatherType.CLOUDY: 10,
        WeatherType.LIGHT_RAIN: 5,
        WeatherType.RAIN: 5,
        WeatherType.HEAVY_RAIN: 3,
        WeatherType.THUNDERSTORM: 5,
        WeatherType.HEATWAVE: 15,
        WeatherType.WINDY: 5,
    },
    "Fall": {
        WeatherType.CLEAR: 20,
        WeatherType.PARTLY_CLOUDY: 25,
        WeatherType.CLOUDY: 25,
        WeatherType.LIGHT_RAIN: 15,
        WeatherType.RAIN: 10,
        WeatherType.FOG: 15,
        WeatherType.WINDY: 10,
    },
    "Winter": {
        WeatherType.CLEAR: 15,
        WeatherType.PARTLY_CLOUDY: 15,
        WeatherType.CLOUDY: 30,
        WeatherType.SNOW: 25,
        WeatherType.FOG: 10,
        WeatherType.WINDY: 10,
    },
}

# Base temperature ranges by season (Fahrenheit)
SEASON_TEMP_RANGES: dict[str, tuple[int, int]] = {
    "Spring": (45, 70),
    "Summer": (65, 95),
    "Fall": (40, 65),
    "Winter": (20, 45),
}

# Time of day temperature modifiers
TIME_TEMP_MODIFIERS: dict[str, int] = {
    "Dawn": -5,
    "Morning": 0,
    "Afternoon": 10,
    "Evening": 5,
    "Dusk": 0,
    "Night": -10,
}


def _weighted_random_choice(weights: dict[WeatherType, int]) -> WeatherType:
    """Select a random weather type based on weights."""
    total = sum(weights.values())
    r = random.randint(1, total)
    cumulative = 0
    for weather_type, weight in weights.items():
        cumulative += weight
        if r <= cumulative:
            return weather_type
    # Fallback (should never reach)
    return WeatherType.CLEAR


def get_weather(season: str, time_of_day: str, seed: int | None = None) -> Weather:
    """
    Generate weather based on season and time of day.
    
    Args:
        season: Current season name (Spring, Summer, Fall, Winter)
        time_of_day: Current time of day name (Dawn, Morning, etc.)
        seed: Optional seed for reproducible weather (e.g., based on game day)
    
    Returns:
        Weather dict with all weather information
    """
    if seed is not None:
        random.seed(seed)
    
    # Get weather weights for the season
    weights = SEASON_WEATHER_WEIGHTS.get(season, SEASON_WEATHER_WEIGHTS["Spring"])
    weather_type = _weighted_random_choice(weights)
    
    # Calculate temperature
    temp_range = SEASON_TEMP_RANGES.get(season, (50, 75))
    base_temp = random.randint(temp_range[0], temp_range[1])
    time_modifier = TIME_TEMP_MODIFIERS.get(time_of_day, 0)
    temperature = base_temp + time_modifier
    
    # Adjust temperature for certain weather conditions
    if weather_type == WeatherType.HEATWAVE:
        temperature = max(temperature, 90) + random.randint(5, 15)
    elif weather_type == WeatherType.SNOW:
        temperature = min(temperature, 32)
    elif weather_type in (WeatherType.RAIN, WeatherType.HEAVY_RAIN, WeatherType.THUNDERSTORM):
        temperature -= random.randint(3, 8)
    
    # Generate wind speed
    if weather_type == WeatherType.WINDY:
        wind_speed = random.randint(20, 40)
    elif weather_type in (WeatherType.THUNDERSTORM, WeatherType.HEAVY_RAIN):
        wind_speed = random.randint(15, 30)
    elif weather_type == WeatherType.CLEAR:
        wind_speed = random.randint(0, 10)
    else:
        wind_speed = random.randint(5, 15)
    
    # Reset random seed if we set one
    if seed is not None:
        random.seed()
    
    return Weather(
        type=weather_type.name_str,
        emoji=weather_type.emoji,
        description=weather_type.description,
        fish_modifier=weather_type.fish_modifier,
        temperature=temperature,
        wind_speed=wind_speed,
    )


def get_weather_for_guild(
    db: DB, 
    guild: discord.Guild | int,
    season: str,
    time_of_day: str,
    game_day: int
) -> Weather:
    """
    Get weather for a guild, using game day as seed for consistency.
    
    Weather changes every game hour (24 weather periods per day).
    This ensures weather is consistent for all players during the same hour.
    
    Args:
        db: Database instance
        guild: Guild or guild ID
        season: Current season name
        time_of_day: Current time of day name
        game_day: Total game days elapsed (used for seed)
    
    Returns:
        Weather dict
    """
    # Create a seed based on guild, game day, and current hour
    from ..commands.helper_functions import get_game_time_of_day
    time_info = get_game_time_of_day(db, guild)
    hour = time_info['hour']
    
    gid = guild if isinstance(guild, int) else guild.id
    seed = hash((gid, game_day, hour)) % (2**31)
    
    return get_weather(season, time_of_day, seed=seed)


def get_weather_display(weather: Weather) -> str:
    """
    Get a formatted string showing current weather.
    
    Example: "☀️ Clear - 72°F, Wind: 5 mph"
    """
    return (
        f"{weather['emoji']} {weather['type']} - "
        f"{weather['temperature']}°F, Wind: {weather['wind_speed']} mph"
    )


def get_weather_fishing_message(weather: Weather) -> str:
    """Get a message about how the weather affects fishing."""
    modifier = weather['fish_modifier']
    
    if modifier >= 1.2:
        return "🎣 **Excellent** fishing conditions!"
    elif modifier >= 1.1:
        return "🎣 **Good** fishing conditions."
    elif modifier >= 1.0:
        return "🎣 **Normal** fishing conditions."
    elif modifier >= 0.8:
        return "🎣 **Fair** fishing conditions."
    elif modifier >= 0.6:
        return "🎣 **Poor** fishing conditions."
    else:
        return "⚠️ **Dangerous** conditions - fishing not recommended!"
