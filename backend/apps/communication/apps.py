from django.apps import AppConfig


class CommunicationConfig(AppConfig):
    name = "apps.communication"
    label = "communication"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import (
            DestinataireDiffusion,
            Diffusion,
            EvenementRapport,
            Rapport,
            RapportProvisoire,
            ReponseRapport,
        )

        for modele in (
            Rapport,
            RapportProvisoire,
            ReponseRapport,
            EvenementRapport,
            DestinataireDiffusion,
            Diffusion,
        ):
            register(modele)
