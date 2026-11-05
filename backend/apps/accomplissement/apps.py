from django.apps import AppConfig


class AccomplissementConfig(AppConfig):
    name = "apps.accomplissement"
    label = "accomplissement"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register
        from apps.missions.services.livrables import enregistrer_controles

        from . import recepteurs  # noqa: F401
        from .controles import programme as controles_programme
        from .models import (
            AccordResultats,
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
            AccordResultats,
        ):
            register(modele)

        from .controles import fiches as controles_fiches

        for module in (controles_programme, controles_fiches):
            for numero, controles in module.CONTROLES_ETAPE.items():
                enregistrer_controles(numero, controles)

        from apps.missions.services.derogations import enregistrer_controle_audite

        from .services.accords import ETAPE_RESULTATS, controle_accord_resultats

        enregistrer_controle_audite(
            ETAPE_RESULTATS, "evidence_agreement", controle_accord_resultats
        )

        from .documents import enregistrer_types

        enregistrer_types()
