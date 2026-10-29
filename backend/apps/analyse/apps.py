from django.apps import AppConfig


class AnalyseConfig(AppConfig):
    name = "apps.analyse"
    label = "analyse"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register
        from apps.missions.services.livrables import enregistrer_controles

        from . import recepteurs  # noqa: F401
        from .controles import etape_iii, etape_v_vi, etape_vii
        from .documents import enregistrer_types
        from .models import (
            AvisAudite,
            DescriptionProcessus,
            ForceFaiblesse,
            GrilleSeparation,
            LigneMARC,
            ObjectifAudit,
            Questionnaire,
            QuestionQuestionnaire,
            RapportOrientation,
        )

        for modele in (
            Questionnaire,
            QuestionQuestionnaire,
            DescriptionProcessus,
            GrilleSeparation,
            LigneMARC,
            ForceFaiblesse,
            AvisAudite,
            ObjectifAudit,
            RapportOrientation,
        ):
            register(modele)

        for module in (etape_iii, etape_v_vi, etape_vii):
            for numero, controles in module.CONTROLES_ETAPE.items():
                if controles:
                    enregistrer_controles(numero, controles)

        enregistrer_types()
