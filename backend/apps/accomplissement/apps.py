from django.apps import AppConfig


class AccomplissementConfig(AppConfig):
    name = "apps.accomplissement"
    label = "accomplissement"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import (
            EvenementFiche,
            FicheDeTest,
            InstantaneProgramme,
            PieceJustificative,
            ProgrammeDeTravail,
            TestPrevu,
        )

        for modele in (
            ProgrammeDeTravail,
            TestPrevu,
            FicheDeTest,
            EvenementFiche,
            PieceJustificative,
            InstantaneProgramme,
        ):
            register(modele)
