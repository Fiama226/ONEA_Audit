from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    name = "apps.notifications"
    label = "notifications"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import Notification

        register(Notification)
