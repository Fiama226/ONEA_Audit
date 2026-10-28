from django.apps import AppConfig


class ReferentielConfig(AppConfig):
    name = "apps.referentiel"
    label = "referentiel"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import CartographieVersion, Direction, ObjetAuditable, Processus, Risque

        register(Direction)
        register(Processus, m2m_fields={"directions"})
        register(ObjetAuditable)
        register(CartographieVersion)
        register(Risque)
