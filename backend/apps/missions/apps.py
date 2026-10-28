from django.apps import AppConfig


class MissionsConfig(AppConfig):
    name = "apps.missions"
    label = "missions"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from .models import (
            AffectationMission,
            DeclarationIndependance,
            Entretien,
            EtapeMission,
            EvenementEtape,
            Mission,
            Reunion,
            RisqueMission,
        )

        register(Mission, m2m_fields={"processus", "entites"})
        register(AffectationMission)
        register(DeclarationIndependance)
        register(EtapeMission)
        register(EvenementEtape)
        register(Reunion, m2m_fields={"participants"})
        register(Entretien, m2m_fields={"auditeurs", "interlocuteurs"})
        register(RisqueMission)
