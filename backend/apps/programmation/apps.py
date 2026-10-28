from django.apps import AppConfig


class ProgrammationConfig(AppConfig):
    name = "apps.programmation"
    label = "programmation"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import LigneProgramme, ProgrammeAnnuel

        register(ProgrammeAnnuel)
        register(LigneProgramme, m2m_fields={"entites"})
