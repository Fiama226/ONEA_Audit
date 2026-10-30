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

        from apps.missions.services.livrables import enregistrer_controles

        from .controles.redaction import CONTROLES_ETAPE

        for numero, controles in CONTROLES_ETAPE.items():
            enregistrer_controles(numero, controles)
