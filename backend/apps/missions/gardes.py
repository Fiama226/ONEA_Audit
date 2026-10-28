"""Gardes de gel des missions et de leurs objets (reprise du principe I1/T2 du lot 2).

Toutes les gardes lisent l'état EN BASE (jamais l'instance en mémoire) : la sauvegarde qui change
un statut passe, toute sauvegarde suivante est refusée. Elles sont appelées par `save()` des
modèles, par les QuerySets (update, bulk_update, bulk_create), par les récepteurs `m2m_changed`
et par les services.
"""

from collections.abc import Callable, Iterable
from typing import Any
from uuid import UUID

from django.db.models.expressions import Combinable
from django.http import Http404

from .exceptions import EtapeCloseError, MissionFigeeError
from .models import EtapeMission, Mission, StatutEtape, StatutMission

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
# Une mission SUSPENDUE peut aussi être annulée (motif d'annulation).
CHAMPS_ANNULATION: frozenset[str] = CHAMPS_REPRISE | {"motif_annulation"}
# Champs gelés par la fin de l'étape I (D17). Les M2M `processus` et `entites` sont gardés par
# les récepteurs `m2m_changed` (voir `apps.py`).
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
_CHAMPS_LUS = ("pk", "statut", "reference", "statut_avant_suspension", *CHAMPS_D17)


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
        EtapeMission.all_objects.filter(
            mission_id=mission_id, numero=numero, deleted_at__isnull=True
        )
        .values_list("statut", flat=True)
        .first()
    )
    if statut in STATUTS_ETAPE_CLOSE:
        raise EtapeCloseError(romain(numero))


def exiger_etape_ouverte_par_id(etape_id: UUID) -> None:
    from .etapes import romain

    ligne = (
        EtapeMission.all_objects.filter(pk=etape_id, deleted_at__isnull=True)
        .values_list("statut", "numero")
        .first()
    )
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


def _controler_gel(en_base: dict[str, Any], apres: Callable[[str], Any], touches: set[str]) -> None:
    """Refuse l'écriture sur une mission figée, sauf reprise ou annulation depuis SUSPENDUE."""
    if en_base["statut"] not in STATUTS_FIGES:
        return
    suspendue = en_base["statut"] == StatutMission.SUSPENDUE
    reprise = (
        suspendue
        and touches <= CHAMPS_REPRISE
        and "statut" in touches
        and apres("statut") == en_base["statut_avant_suspension"]
        and "statut_avant_suspension" in touches
        and apres("statut_avant_suspension") == ""
    )
    annulation = (
        suspendue
        and touches <= CHAMPS_ANNULATION
        and "statut" in touches
        and apres("statut") == StatutMission.ANNULEE
    )
    if not (reprise or annulation):
        raise _figee(en_base["statut"], en_base["reference"])


def _d17_change(en_base: dict[str, Any], apres: Callable[[str], Any], touches: set[str]) -> bool:
    for champ in CHAMPS_D17:
        if champ in touches:
            valeur = apres(champ)
            if isinstance(valeur, Combinable) or valeur != en_base[champ]:
                return True
    return False


def controler_lignes_mission(
    lignes: Iterable[dict[str, Any]],
    apres: Callable[[dict[str, Any], str], Any],
    touches: set[str],
) -> None:
    """Garde commune à `Mission.save`, `update` et `bulk_update`.

    `lignes` : valeurs en base (`_CHAMPS_LUS`) ; `apres(ligne, champ)` : valeur écrite ;
    `touches` : champs écrits. Une requête par vérification d'étape I, et seulement si un champ
    D17 change.
    """
    etape_i_a_verifier: set[UUID] = set()
    for ligne in lignes:

        def valeur(champ: str, ligne: dict[str, Any] = ligne) -> Any:
            return apres(ligne, champ)

        _controler_gel(ligne, valeur, touches)
        if ligne["statut"] not in STATUTS_FIGES and _d17_change(ligne, valeur, touches):
            etape_i_a_verifier.add(ligne["pk"])
    for pk in etape_i_a_verifier:
        exiger_etape_ouverte(pk, 1)


def controler_sauvegarde_mission(mission: Mission, update_fields: Iterable[str] | None) -> None:
    """Garde de `Mission.save()` sur une ligne existante."""
    en_base = Mission.all_objects.filter(pk=mission.pk).values(*_CHAMPS_LUS).first()
    if en_base is None:
        return
    touches = (
        {f.name for f in Mission._meta.concrete_fields}
        if update_fields is None
        else set(update_fields)
    )
    controler_lignes_mission([en_base], lambda _l, champ: getattr(mission, champ), touches)


def controler_m2m_mission(mission: Mission, *, d17: bool) -> None:
    """Garde des M2M de la mission : mission non figée ; `d17` : étape I ouverte."""
    refuser_si_figee(mission.pk)
    if d17:
        exiger_etape_ouverte(mission.pk, 1)
