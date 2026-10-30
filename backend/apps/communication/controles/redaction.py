"""Contrôles de livrables des étapes XVII et XVIII (D15 du plan du lot 7)."""

from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import EtapeMission
from apps.missions.services.livrables import Controle

from ..models import Rapport, StatutRapport

MSG_XVI = "Terminez l'étape XVI avant de terminer la rédaction du rapport."
MSG_SECTIONS = "Rédigez la synthèse, l'appréciation globale et la conclusion du rapport."
MSG_SOUMETTRE = "Soumettez le rapport depuis l'écran du rapport."

_SOUMIS = (StatutRapport.SOUMIS, StatutRapport.VALIDE, StatutRapport.DIFFUSE)


def _rapport_actif(mission_id: object) -> Rapport | None:
    return (
        Rapport.objects.filter(mission_id=mission_id)
        .exclude(statut=StatutRapport.REMPLACE)
        .order_by("numero_version")
        .last()
    )


def _xvi_close(etape: EtapeMission) -> str | None:
    statut = (
        EtapeMission.objects.filter(mission_id=etape.mission_id, numero=16)
        .values_list("statut", flat=True)
        .first()
    )
    return None if statut in STATUTS_ETAPE_CLOSE else MSG_XVI


def _sections_redigees(etape: EtapeMission) -> str | None:
    rapport = _rapport_actif(etape.mission_id)
    complet = (
        rapport is not None
        and rapport.synthese.strip()
        and rapport.appreciation_globale
        and rapport.conclusion.strip()
    )
    return None if complet else MSG_SECTIONS


def _rapport_soumis(etape: EtapeMission) -> str | None:
    rapport = _rapport_actif(etape.mission_id)
    return None if rapport is not None and rapport.statut in _SOUMIS else MSG_SOUMETTRE


CONTROLES_ETAPE: dict[int, list[Controle]] = {
    17: [_xvi_close, _sections_redigees],
    18: [_rapport_soumis],
}
