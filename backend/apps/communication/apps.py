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

        from .controles.provisoire import CONTROLES_ETAPE as CONTROLES_PROVISOIRE
        from .controles.redaction import CONTROLES_ETAPE

        for numero, controles in (*CONTROLES_PROVISOIRE.items(), *CONTROLES_ETAPE.items()):
            enregistrer_controles(numero, controles)

        from apps.missions.services.etapes import ActionEtape, reserver_actions

        from . import recepteurs
        from .documents import enregistrer_types

        enregistrer_types()
        # XVIII : terminer, valider et renvoyer se font depuis l'écran du rapport (D9).
        reserver_actions(18, ActionEtape.TERMINER, ActionEtape.VALIDER, ActionEtape.RENVOYER)
        recepteurs.connecter()
