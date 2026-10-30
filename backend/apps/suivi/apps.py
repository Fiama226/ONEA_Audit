from django.apps import AppConfig


class SuiviConfig(AppConfig):
    name = "apps.suivi"
    label = "suivi"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import DemandeReport, EvenementSuivi, PreuveMiseEnOeuvre, Relance, SuiviAction

        for modele in (SuiviAction, EvenementSuivi, DemandeReport, PreuveMiseEnOeuvre, Relance):
            register(modele)
