from django.apps import AppConfig


class TestAppConfig(AppConfig):
    name = "tests.testapp"
    label = "testapp"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import Exemple

        register(Exemple)
