from collections.abc import Iterable

from django.apps import AppConfig


class AnalyseConfig(AppConfig):
    name = "apps.analyse"
    label = "analyse"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self) -> None:
        from apps.core.audit import register

        from . import recepteurs  # noqa: F401
        from .controles import etape_iii, etape_v_vi, etape_vii
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
                _enregistrer_controles(numero, controles)


def _enregistrer_controles(numero: int, controles: Iterable[object]) -> None:
    """Fusionne des contrôles dans le registre du lot 3 (idempotent).

    À remplacer par `missions.services.livrables.enregistrer_controles` (T2) à la fusion :
    cette tâche n'édite pas `apps.missions`.
    """
    from apps.missions.services.livrables import CONTROLES

    existants = CONTROLES.setdefault(numero, [])
    for controle in controles:
        if controle not in existants:
            existants.append(controle)  # type: ignore[arg-type]
