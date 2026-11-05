from django.apps import AppConfig


class GouvernanceConfig(AppConfig):
    name = "apps.gouvernance"
    label = "gouvernance"
    verbose_name = "Règles de gouvernance"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import RegleGouvernance

        register(RegleGouvernance)
