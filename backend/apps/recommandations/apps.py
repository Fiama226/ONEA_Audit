from django.apps import AppConfig


class RecommandationsConfig(AppConfig):
    name = "apps.recommandations"
    label = "recommandations"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import AcceptationRisque, Action, EngagementPlanActions

        for modele in (Action, AcceptationRisque, EngagementPlanActions):
            register(modele)

        from apps.missions.services.livrables import enregistrer_controles

        from .controles import CONTROLES_ETAPE

        for numero, controles in CONTROLES_ETAPE.items():
            enregistrer_controles(numero, controles)

        from .documents import enregistrer_types

        enregistrer_types()
