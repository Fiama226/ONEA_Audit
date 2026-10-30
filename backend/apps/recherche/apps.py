from django.apps import AppConfig


class RechercheConfig(AppConfig):
    name = "apps.recherche"
    label = "recherche"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from . import signaux

        signaux.connecter()
