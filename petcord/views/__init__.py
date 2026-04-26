"""Views package for Petcord cog."""

from .main_menu import MainMenuView, FindPetButton, HomeButton, StatsButton, RefreshButton, CloseButton
from .find_pet import PetFoundView, generate_offered_pet
from .modals import PetNamingModal
from .graduation import GraduationView
from .home_views import HomeListView, HomePetView
from .memorial import MemorialView, MemorialDetailView
from .stat_views import StatsView
from .achievements import AchievementsView
from .species_guide import SpeciesGuideView
from .leaderboard import LeaderboardView
from .howto_views import HowToView
from .gift_views import PetGiftView
from .setup_wizard import PetcordSetupView
