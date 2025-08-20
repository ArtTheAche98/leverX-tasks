"""Learning app configuration (registers signal handlers)."""

from django.apps import AppConfig

class LearningConfig(AppConfig):
    """AppConfig for the learning domain (lectures, homework, submissions, grades)."""
    default_auto_field = "django.db.models.BigAutoField"
    name = "CourseManagementApp.learning"

    def ready(self):
        """Import signal handlers to connect Django model signals."""
        from CourseManagementApp.learning import signals