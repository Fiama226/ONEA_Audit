from django.apps import AppConfig


class ConstatsConfig(AppConfig):
    name = "apps.constats"
    label = "constats"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from django.db.models.signals import m2m_changed

        from apps.core.audit import register

        from . import gardes
        from .models import (
            CauseConstat,
            Constat,
            EvenementConstat,
            Recommandation,
            ReponseAudite,
        )

        register(Constat, m2m_fields={"fiches"})
        for modele in (CauseConstat, Recommandation, ReponseAudite, EvenementConstat):
            register(modele)

        from apps.missions.services.livrables import enregistrer_controles

        from .controles import CONTROLES_ETAPE

        for numero, controles in CONTROLES_ETAPE.items():
            enregistrer_controles(numero, controles)

        from apps.missions.services.derogations import enregistrer_controle_audite

        from .controles import controle_positions_audite

        enregistrer_controle_audite(14, "findings_agreed", controle_positions_audite)

        from .documents import enregistrer_types

        enregistrer_types()

        m2m_changed.connect(gardes.garder_fiches, sender=Constat.fiches.through, weak=False)
