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
