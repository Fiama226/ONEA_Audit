"""Contrôles de livrables de l'étape VII (D13 du plan du lot 5)."""

from apps.missions.models import EtapeMission, StatutEtape
from apps.missions.services.livrables import Controle

from ..gardes import statuts_etapes
from ..models import LigneMARC, ObjectifAudit, RapportOrientation


def _vi_validee(etape: EtapeMission) -> str | None:
    if statuts_etapes(etape.mission_id, (6,)).get(6) == StatutEtape.VALIDEE:
        return None
    return "Le référentiel d'audit n'est pas validé (jalon VI)."


def _objectif_retenu(etape: EtapeMission) -> str | None:
    if ObjectifAudit.objects.filter(mission_id=etape.mission_id, retenu=True).exists():
        return None
    return "Aucun objectif d'audit n'est retenu."


def _decisions_de_test(etape: EtapeMission) -> str | None:
    decides = ObjectifAudit.objects.filter(mission_id=etape.mission_id).values("ligne_marc_id")
    sans_decision = (
        LigneMARC.objects.filter(mission_id=etape.mission_id, cle=True)
        .exclude(pk__in=decides)
        .count()
    )
    if sans_decision:
        return f"Contrôles clés sans décision de test : {sans_decision}."
    return None


def _rapprochement(etape: EtapeMission) -> str | None:
    renseigne = (
        RapportOrientation.objects.filter(mission_id=etape.mission_id)
        .exclude(couverture_ordre="")
        .exists()
    )
    return None if renseigne else "Le rapprochement avec l'ordre de mission n'est pas renseigné."


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    7: [_vi_validee, _objectif_retenu, _decisions_de_test, _rapprochement]
}
