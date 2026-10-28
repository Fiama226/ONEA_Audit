"""Entretiens de la mission (D14)."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.users.models import User

from ..models import (
    ROLES_INTERVENANTS,
    AffectationMission,
    Entretien,
    EtapeMission,
    Mission,
    StatutEntretien,
)
from .travaux import verrouiller_travaux

_CHAMPS = {
    "duree_minutes",
    "lieu",
    "autres_interlocuteurs",
    "themes",
    "compte_rendu",
    "note_synthese",
}
_MODIFIABLES = _CHAMPS | {"objet", "date_prevue", "etape", "auditeurs", "interlocuteurs"}
_M2M = {"auditeurs", "interlocuteurs"}


def _controler_etape(mission: Mission, etape: EtapeMission | None) -> None:
    if etape is None:
        return
    if etape.mission_id != mission.pk or etape.deleted_at is not None:
        message = "L'étape doit être une étape de la mission."
        raise refuser(message, etape=message)


def _controler_auditeurs(mission: Mission, auditeurs: Iterable[User]) -> list[User]:
    liste = list(auditeurs)
    equipe = set(
        AffectationMission.objects.filter(
            mission=mission, role_mission__in=ROLES_INTERVENANTS
        ).values_list("utilisateur_id", flat=True)
    )
    if any(u.pk not in equipe for u in liste):
        message = "Les auditeurs doivent faire partie de l'équipe de la mission."
        raise refuser(message, auditeurs=message)
    return liste


def _controler_duree(entretien: Entretien) -> None:
    duree = entretien.duree_minutes
    if duree is not None and not 1 <= duree <= 600:
        message = "La durée doit être comprise entre 1 et 600 minutes."
        raise refuser(message, duree_minutes=message)


@transaction.atomic
def creer_entretien(
    mission: Mission,
    *,
    objet: str,
    date_prevue: datetime,
    by: User,
    etape: EtapeMission | None = None,
    auditeurs: Iterable[User] = (),
    interlocuteurs: Iterable[User] = (),
    **champs: Any,
) -> Entretien:
    mission = verrouiller_travaux(mission)
    _controler_etape(mission, etape)
    equipe = _controler_auditeurs(mission, auditeurs)
    entretien = Entretien(mission=mission, objet=objet, date_prevue=date_prevue, etape=etape)
    appliquer(entretien, champs, _CHAMPS)
    _controler_duree(entretien)
    enregistrer(entretien, by=by, creation=True)
    entretien.auditeurs.set(equipe)
    entretien.interlocuteurs.set(list(interlocuteurs))
    return entretien


@transaction.atomic
def modifier_entretien(entretien: Entretien, *, by: User, **changes: Any) -> Entretien:
    mission = verrouiller_travaux(entretien.mission)
    entretien = relire(entretien)
    if entretien.statut == StatutEntretien.ANNULE:
        raise RegleMetierError("Un entretien annulé ne peut plus être modifié.")
    appliquer(entretien, changes, _MODIFIABLES, m2m=_M2M)
    if "etape" in changes:
        _controler_etape(mission, changes["etape"])
    auditeurs = (
        _controler_auditeurs(mission, changes["auditeurs"]) if "auditeurs" in changes else None
    )
    _controler_duree(entretien)
    enregistrer(entretien, by=by)
    if auditeurs is not None:
        entretien.auditeurs.set(auditeurs)
    if "interlocuteurs" in changes:
        entretien.interlocuteurs.set(list(changes["interlocuteurs"]))
    return entretien


@transaction.atomic
def supprimer_entretien(entretien: Entretien, *, by: User) -> None:
    verrouiller_travaux(entretien.mission)
    relire(entretien).soft_delete(by)


@transaction.atomic
def marquer_entretien_realise(entretien: Entretien, *, by: User) -> Entretien:
    verrouiller_travaux(entretien.mission)
    entretien = relire(entretien)
    if entretien.statut != StatutEntretien.PLANIFIE:
        raise RegleMetierError("Seul un entretien planifié peut être marqué comme réalisé.")
    if not entretien.compte_rendu.strip():
        message = "Saisissez le compte rendu avant de marquer l'entretien comme réalisé."
        raise refuser(message, compte_rendu=message)
    entretien.statut = StatutEntretien.REALISE
    entretien.realise_le = timezone.now()
    enregistrer(entretien, by=by)
    return entretien


@transaction.atomic
def annuler_entretien(entretien: Entretien, *, motif: str, by: User) -> Entretien:
    verrouiller_travaux(entretien.mission)
    entretien = relire(entretien)
    if not motif.strip():
        message = "Le motif est obligatoire."
        raise refuser(message, motif=message)
    if entretien.statut != StatutEntretien.PLANIFIE:
        raise RegleMetierError("Seul un entretien planifié peut être annulé.")
    entretien.statut = StatutEntretien.ANNULE
    entretien.motif_annulation = motif.strip()
    enregistrer(entretien, by=by)
    return entretien
