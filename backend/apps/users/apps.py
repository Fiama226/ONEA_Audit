from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = "apps.users"
    label = "users"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from auditlog.registry import auditlog

        from .models import User

        # Never log credentials or login timestamps.
        auditlog.register(User, exclude_fields=["password", "last_login"])
