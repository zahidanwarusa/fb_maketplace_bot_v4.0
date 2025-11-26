"""
Components Package
Contains all the route blueprints for the Facebook Marketplace Automation application
"""

from .dashboard import dashboard_bp
from .profiles import profiles_bp
from .listings import listings_bp
from .media import media_bp
from .history import history_bp
from .deleted import deleted_bp
from .schedule import schedule_bp
from .bot import bot_bp

__all__ = [
    'dashboard_bp',
    'profiles_bp',
    'listings_bp',
    'media_bp',
    'history_bp',
    'deleted_bp',
    'schedule_bp',
    'bot_bp'
]
