"""Réunions d'ouverture, de lancement et de clôture (D13)."""

from collections.abc import Iterable
from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.users.models import User

from ..models import Mission, Reunion, TypeReunion
from ..notifications import notifier_reunion
from .travaux import verrouiller_travaux

_CHAMPS = {"lieu", "ordre_du_jour", "participants_externes", "decisions", "compte_rendu"}
_MODIFIABLES = _CHAMPS | {"date", "participants"}


@transaction.atomic
def creer_reunion(
    mission: Mission,
    *,
    type: str,  # noqa: A002
    date: datetime,
    by: User,
    participants: Iterable[User] = (),
    **champs: Any,
) -> Reunion:
    mission = verrouiller_travaux(mission)
    if type not in TypeReunion.values:
        raise refuser("Type de réunion inconnu.", type="Type de réunion inconnu.")
    if Reunion.objects.filter(mission=mission, type=type).exists():
        message = "Cette réunion existe déjà pour la mission."
        raise refuser(message, type=message)
    reunion = Reunion(mission=mission, type=type, date=date)
    appliquer(reunion, champs, _CHAMPS)
    enregistrer(reunion, by=by, creation=True)
    reunion.participants.set(list(participants))
    notifier_reunion(reunion, reunion.participants.all(), by=by)
    return reunion


@transaction.atomic
def modifier_reunion(reunion: Reunion, *, by: User, **changes: Any) -> Reunion:
    verrouiller_travaux(reunion.mission)
    reunion = relire(reunion)
    appliquer(reunion, changes, _MODIFIABLES, m2m={"participants"})
    enregistrer(reunion, by=by)
    if "participants" in changes:
        reunion.participants.set(list(changes["participants"]))
        notifier_reunion(reunion, reunion.participants.all(), by=by)
    return reunion


@transaction.atomic
def supprimer_reunion(reunion: Reunion, *, by: User) -> None:
    verrouiller_travaux(reunion.mission)
    relire(reunion).soft_delete(by)


@transaction.atomic
def marquer_reunion_tenue(reunion: Reunion, *, by: User) -> Reunion:
    verrouiller_travaux(reunion.mission)
    reunion = relire(reunion)
    if reunion.tenue_le is not None:
        raise RegleMetierError("Cette réunion est déjà marquée comme tenue.")
    if not reunion.compte_rendu.strip():
        message = "Saisissez le compte rendu avant de marquer la réunion comme tenue."
        raise refuser(message, compte_rendu=message)
    maintenant = timezone.now()
    if reunion.date > maintenant:
        message = "Une réunion à venir ne peut pas être marquée comme tenue."
        raise refuser(message, date=message)
    reunion.tenue_le = maintenant
    enregistrer(reunion, by=by)
    return reunion
