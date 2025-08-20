"""Core app configuration and startup checks (like libmagic availability)."""

import magic
from django.apps import AppConfig
from django.core.checks import register, Error

class CoreConfig(AppConfig):
    """AppConfig registering a system check for libmagic presence."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "CourseManagementApp.core"

    def ready(self):
        """Register a Django system check to ensure libmagic is operational."""
        @register()
        def libmagic_check(app_configs, **kwargs):
            try:
                magic.from_buffer(b"\x89PNG\r\n\x1a\n")
            except Exception as exc:
                return [Error(f"libmagic not available: {exc}", id="core.E001")]
            return []