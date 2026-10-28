"""Gardes de gel des missions et de leurs objets (reprise du principe I1/T2 du lot 2).

Toutes les gardes lisent l'état EN BASE (jamais l'instance en mémoire) : la sauvegarde qui change
un statut passe, toute sauvegarde suivante est refusée. Elles sont appelées par `save()` des
modèles, par `MissionEnfantQuerySet` (update, bulk_update, bulk_create) et par les services.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from django.http import Http404

from .exceptions import EtapeCloseError, MissionFigeeError
from .models import EtapeMission, Mission, StatutEtape, StatutMission

if TYPE_CHECKING:
    from collections.abc import Iterable

STATUTS_FIGES: frozenset[str] = frozenset(
    {StatutMission.SUSPENDUE, StatutMission.ANNULEE, StatutMission.CLOTUREE}
)
STATUTS_ETAPE_CLOSE: frozenset[str] = frozenset(
    {StatutEtape.TERMINEE, StatutEtape.VALIDEE, StatutEtape.A_REVALIDER}
)

# Champs que la sauvegarde de `reprendre` peut toucher sur une mission SUSPENDUE.
CHAMPS_REPRISE: frozenset[str] = frozenset(
    {"statut", "statut_avant_suspension", "updated_by", "updated_at"}
)
# Champs gelés par la fin de l'étape I (D17). Les M2M `processus` et `entites` sont contrôlés
# par les services.
CHAMPS_D17: tuple[str, ...] = (
    "titre",
    "type",
    "evenement_declencheur",
    "evenement_precision",
    "periode_debut",
    "periode_fin",
    "objectifs",
    "perimetre",
    "exclusions",
    "clients",
    "livrables_attendus",
)


def _figee(statut: str, reference: str) -> MissionFigeeError:
    return MissionFigeeError(reference, StatutMission(statut).label)


def refuser_si_figee(mission_id: UUID | None) -> None:
    """Refuse si la mission, lue en base, est suspendue, annulée ou clôturée."""
    if mission_id is None:
        return
    ligne = Mission.all_objects.filter(pk=mission_id).values_list("statut", "reference").first()
    if ligne is not None and ligne[0] in STATUTS_FIGES:
        raise _figee(*ligne)


def verrouiller_mission(mission: Mission | UUID) -> Mission:
    """Verrouille la ligne de mission (transaction requise) ; refuse si elle est figée."""
    pk = mission.pk if isinstance(mission, Mission) else mission
    verrouillee = Mission.objects.select_for_update().filter(pk=pk).first()
    if verrouillee is None:
        raise Http404("Mission introuvable.")
    if verrouillee.statut in STATUTS_FIGES:
        raise _figee(verrouillee.statut, verrouillee.reference)
    return verrouillee


def exiger_etape_ouverte(mission_id: UUID, numero: int) -> None:
    """Refuse si l'étape `numero` de la mission est terminée, validée ou à revalider (en base)."""
    from .etapes import romain

    statut = (
        EtapeMission.all_objects.filter(mission_id=mission_id, numero=numero)
        .values_list("statut", flat=True)
        .first()
    )
    if statut in STATUTS_ETAPE_CLOSE:
        raise EtapeCloseError(romain(numero))


def exiger_etape_ouverte_par_id(etape_id: UUID) -> None:
    from .etapes import romain

    ligne = EtapeMission.all_objects.filter(pk=etape_id).values_list("statut", "numero").first()
    if ligne is not None and ligne[0] in STATUTS_ETAPE_CLOSE:
        raise EtapeCloseError(romain(ligne[1]))


def controler_ecriture(objet: Any) -> None:
    """Contrôle un objet de mission (en mémoire ou lu en base) : mission puis étape."""
    refuser_si_figee(objet.mission_id)
    objet.exiger_travaux_ouverts()


def controler_sauvegarde(objet: Any) -> None:
    """Garde de `save()` d'un objet de mission : état en base, puis état à écrire."""
    if not objet._state.adding:
        en_base = type(objet).all_objects.filter(pk=objet.pk).first()
        if en_base is not None:
            controler_ecriture(en_base)
    controler_ecriture(objet)


def controler_sauvegarde_mission(mission: Mission, update_fields: "Iterable[str] | None") -> None:
    """Garde de `Mission.save()` sur une ligne existante."""
    en_base = (
        Mission.all_objects.filter(pk=mission.pk).values("statut", "reference", *CHAMPS_D17).first()
    )
    if en_base is None:
        return
    if en_base["statut"] in STATUTS_FIGES:
        reprise = (
            en_base["statut"] == StatutMission.SUSPENDUE
            and update_fields is not None
            and set(update_fields) <= CHAMPS_REPRISE
        )
        if not reprise:
            raise _figee(en_base["statut"], en_base["reference"])
        return
    concernes = CHAMPS_D17 if update_fields is None else tuple(set(CHAMPS_D17) & set(update_fields))
    if any(getattr(mission, c) != en_base[c] for c in concernes):
        exiger_etape_ouverte(mission.pk, 1)
