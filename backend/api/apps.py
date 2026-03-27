from django.apps import AppConfig
import sys

class ApiConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api"

    def ready(self):
        # Already migrated. Disabling to avoid deadlock on startup.
        pass
