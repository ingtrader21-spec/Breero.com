"""Compatibility facade for structured application settings.

New validation belongs in ``app.settings`` modules. Existing imports from
``app.config`` remain stable.
"""

from app.settings import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
