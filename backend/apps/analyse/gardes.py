"""Gardes de gel par étape des objets d'analyse (D4 du plan du lot 5).

Comme celles du lot 3, elles lisent l'état EN BASE.
"""

from collections.abc import Iterable
from uuid import UUID

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.gardes import STATUTS_ETAPE_CLOSE, exiger_etape_ouverte
from apps.missions.models import EtapeMission, StatutEtape

from .models import TypeQuestionnaire

ACTIFS: frozenset[str] = frozenset({StatutEtape.EN_COURS, StatutEtape.RENVOYEE})
MSG_VI_NON_VALIDEE = (
    "Le référentiel d'audit doit être validé (jalon VI) avant de sélectionner "
    "les objectifs d'audit."
)


def statuts_etapes(mission_id: UUID, numeros: Iterable[int]) -> dict[int, str]:
    """Statuts (lus en base, une requête) des étapes demandées."""
    return dict(
        EtapeMission.all_objects.filter(
            mission_id=mission_id, numero__in=list(numeros), deleted_at__isnull=True
        ).values_list("numero", "statut")
    )


def exiger_fenetre_marc(mission_id: UUID) -> None:
    """Gel de la MARC, du QCI et des forces/faiblesses : VI close, ou V close et VI inactive."""
    statuts = statuts_etapes(mission_id, (5, 6))
    vi = statuts.get(6)
    if vi in STATUTS_ETAPE_CLOSE:
        raise EtapeCloseError("VI")
    if statuts.get(5) in STATUTS_ETAPE_CLOSE and vi not in ACTIFS:
        raise EtapeCloseError("V")


def exiger_gel_questionnaire(mission_id: UUID, type_: str) -> None:
    if type_ == TypeQuestionnaire.PRISE_CONNAISSANCE:
        exiger_etape_ouverte(mission_id, 3)
    else:
        exiger_fenetre_marc(mission_id)


def exiger_avis_ouvert(mission_id: UUID) -> None:
    """Gel des avis des audités : VI validée ou à revalider."""
    if statuts_etapes(mission_id, (6,)).get(6) in (StatutEtape.VALIDEE, StatutEtape.A_REVALIDER):
        raise EtapeCloseError("VI")


def exiger_actives(mission_id: UUID, *, une_de: Iterable[int], message: str) -> None:
    """422 `RegleMetierError(message)` si aucune des étapes n'est EN_COURS ou RENVOYEE."""
    statuts = statuts_etapes(mission_id, une_de)
    if not any(s in ACTIFS for s in statuts.values()):
        raise RegleMetierError(message)


def exiger_vi_validee(mission_id: UUID) -> None:
    if statuts_etapes(mission_id, (6,)).get(6) != StatutEtape.VALIDEE:
        raise RegleMetierError(MSG_VI_NON_VALIDEE)
