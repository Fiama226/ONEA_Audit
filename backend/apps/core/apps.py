from typing import Any

from django.apps import AppConfig
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.models.signals import post_migrate


def installer_gardes_sql(using: str = DEFAULT_DB_ALIAS, **kwargs: Any) -> None:
    """Après chaque migration : déclencheurs de gel et droits du rôle applicatif (D6)."""
    from .gardes_sql import installer

    installer(connections[using])


class CoreConfig(AppConfig):
    name = "apps.core"
    label = "core"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.reseau import reseaux_de_confiance

        reseaux_de_confiance()  # échec franc au démarrage si TRUSTED_PROXY_CIDRS est invalide

        from apps.core.journalisation import connecter_signaux_celery

        connecter_signaux_celery()
        post_migrate.connect(installer_gardes_sql, sender=self, dispatch_uid="core.gardes_sql")

        from . import consultations  # noqa: F401  (enregistre le modèle Consultation)
        from .audit import register
        from .models import ParametrePlateforme

        register(ParametrePlateforme)
