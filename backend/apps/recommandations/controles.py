"""Contrôles de livrables de l'étape XVI (D15 du plan du lot 7)."""

from django.db.models import Q

from apps.constats.models import Recommandation, StatutConstat
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from .models import AcceptationRisque, Action

MSG_XV = "Terminez l'étape XV avant de finaliser le plan d'actions."


def _xv_close(etape: EtapeMission) -> str | None:
    statut = (
        EtapeMission.objects.filter(mission_id=etape.mission_id, numero=15)
        .values_list("statut", flat=True)
        .first()
    )
    return None if statut in STATUTS_ETAPE_CLOSE else MSG_XV


def _recommandations_couvertes(etape: EtapeMission) -> list[str]:
    avec_action = set(
        Action.objects.filter(mission_id=etape.mission_id).values_list(
            "recommandation_id", flat=True
        )
    )
    acceptees = set(
        AcceptationRisque.objects.filter(mission_id=etape.mission_id).values_list(
            "recommandation_id", flat=True
        )
    )
    recos = (
        Recommandation.objects.filter(
            mission_id=etape.mission_id, constat__statut=StatutConstat.VALIDE
        )
        .exclude(pk__in=avec_action | acceptees)
        .select_related("constat")
        .order_by("constat__numero", "ordre")
    )
    return [
        f"La recommandation {r.constat.reference}-{r.ordre} n'a ni action ni acceptation du risque."
        for r in recos
    ]


def _actions_completes(etape: EtapeMission) -> list[str]:
    incompletes = (
        Action.objects.filter(mission_id=etape.mission_id)
        .filter(
            Q(responsable__isnull=True) | Q(echeance__isnull=True) | Q(indicateur__regex=r"^\s*$")
        )
        .order_by("numero")
        .values_list("reference", flat=True)
    )
    return [
        f"L'action {reference} n'a pas de responsable, d'échéance ou d'indicateur."
        for reference in incompletes
    ]


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    16: [_xv_close, _recommandations_couvertes, _actions_completes]
}
