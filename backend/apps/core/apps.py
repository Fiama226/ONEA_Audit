from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.reseau import reseaux_de_confiance

        reseaux_de_confiance()  # échec franc au démarrage si TRUSTED_PROXY_CIDRS est invalide
