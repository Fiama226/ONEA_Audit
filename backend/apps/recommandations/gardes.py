"""Gardes de gel du plan d'actions (D8 du plan du lot 7).

Elles comparent la ligne EN BASE à l'instance écrite, et sont appelées par `save()` des modèles
et par leurs QuerySets (`update`, `bulk_update`, `bulk_create`).
"""

from collections.abc import Collection
from typing import Any

from apps.core.exceptions import RegleMetierError
from apps.missions.gardes import exiger_etape_ouverte, refuser_si_figee
from apps.missions.models import Mission, StatutMission

from .exceptions import MSG_ACCEPTATION_IMMUABLE, MSG_AUTRE_MISSION, MSG_STATUT_SUIVI
from .models import Action

ETAPE_PLAN_ACTIONS = 16

CHAMPS_NEUTRES: frozenset[str] = frozenset({"updated_at", "updated_by"})
CHAMPS_SUIVI: frozenset[str] = frozenset({"statut"})
CHAMPS_CONTENU: frozenset[str] = (
    frozenset(f.name for f in Action._meta.concrete_fields) - CHAMPS_SUIVI - CHAMPS_NEUTRES
)
STATUTS_SUIVI: frozenset[str] = frozenset({StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI})


def champs_modifies(
    avant: Any,
    apres: Any,
    *,
    forces: Collection[str] = (),
    touches: Collection[str] | None = None,
) -> set[str]:
    """Champs (hors horodatage) qui diffèrent ; `forces` : écrits par expression (donc modifiés)."""
    modeles = type(avant)._meta.concrete_fields
    resultat: set[str] = set()
    for champ in modeles:
        if champ.name in CHAMPS_NEUTRES:
            continue
        if touches is not None and champ.name not in touches and champ.attname not in touches:
            continue
        if champ.name in forces or getattr(avant, champ.attname) != getattr(apres, champ.attname):
            resultat.add(champ.name)
    return resultat


def _statut_mission(mission_id: Any) -> str | None:
    statut: str | None = (
        Mission.all_objects.filter(pk=mission_id).values_list("statut", flat=True).first()
    )
    return statut


def controler_action(
    avant: Action | None,
    apres: Action,
    *,
    forces: Collection[str] = (),
    touches: Collection[str] | None = None,
) -> None:
    """Gel D8 : contenu modifiable tant que XVI n'est pas close ; `statut` pendant le suivi."""
    refuser_si_figee(apres.mission_id)
    if avant is None:
        exiger_etape_ouverte(apres.mission_id, ETAPE_PLAN_ACTIONS)
        _exiger_meme_mission(apres)
        return
    refuser_si_figee(avant.mission_id)
    modifies = champs_modifies(avant, apres, forces=forces, touches=touches)
    if modifies & CHAMPS_CONTENU:
        exiger_etape_ouverte(avant.mission_id, ETAPE_PLAN_ACTIONS)
        exiger_etape_ouverte(apres.mission_id, ETAPE_PLAN_ACTIONS)
    if modifies & CHAMPS_SUIVI and _statut_mission(avant.mission_id) not in STATUTS_SUIVI:
        raise RegleMetierError(MSG_STATUT_SUIVI)


def _exiger_meme_mission(action: Action) -> None:
    from apps.constats.models import Recommandation

    mission_id = (
        Recommandation.all_objects.filter(pk=action.recommandation_id)
        .values_list("mission_id", flat=True)
        .first()
    )
    if mission_id is not None and mission_id != action.mission_id:
        raise RegleMetierError(MSG_AUTRE_MISSION)


def controler_acceptation(
    avant: Any,
    apres: Any,
    *,
    forces: Collection[str] = (),
    touches: Collection[str] | None = None,
) -> None:
    """Acceptation : immuable, sauf suppression logique, qui exige XVI ouverte."""
    refuser_si_figee(apres.mission_id)
    if avant is None:
        exiger_etape_ouverte(apres.mission_id, ETAPE_PLAN_ACTIONS)
        return
    modifies = champs_modifies(avant, apres, forces=forces, touches=touches)
    if not modifies:
        return
    if modifies - {"deleted_at"} or avant.deleted_at is not None or apres.deleted_at is None:
        raise RegleMetierError(MSG_ACCEPTATION_IMMUABLE)
    exiger_etape_ouverte(avant.mission_id, ETAPE_PLAN_ACTIONS)
