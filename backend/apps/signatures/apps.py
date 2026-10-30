from django.apps import AppConfig


class SignaturesConfig(AppConfig):
    name = "apps.signatures"
    label = "signatures"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import Confirmation, ParametreSignature

        register(Confirmation)
        register(ParametreSignature)
