"""Programme de travail par objectif d'audit retenu (étape VIII, D3, D5)."""

from typing import Any

from django.db import transaction

from apps.analyse.models import ObjectifAudit
from apps.analyse.services.objectifs import objectifs_retenus
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import Mission
from apps.users.models import User

from ..droits import ETAPE_CONTENU
from ..models import ProgrammeDeTravail
from ._fenetres_programme import Droit, exiger_droit, exiger_fenetre, verrouiller

CHAMPS_PROGRAMME = {"techniques", "criteres_preuve", "commentaire"}
MSG_TESTS_ACTIFS = "Supprimez d'abord les tests de ce programme."


def _ouvrir(mission: Mission, by: User) -> Mission:
    verrouillee = verrouiller(mission)
    exiger_droit(by, verrouillee, Droit.CONTENU)
    exiger_fenetre(verrouillee.pk, ETAPE_CONTENU)
    return verrouillee


def _objectif_de_la_mission(mission: Mission, objectif: ObjectifAudit) -> ObjectifAudit:
    appartient = ObjectifAudit.objects.filter(pk=objectif.pk, mission=mission).exists()
    if not appartient:
        message = "Cet objectif n'appartient pas à la mission."
        raise refuser(message, objectif=message)
    verrouille = objectifs_retenus(mission).select_for_update(no_key=True).filter(pk=objectif.pk)
    retenu = verrouille.first()
    if retenu is None:
        message = "Cet objectif n'est pas retenu pour la mission."
        raise refuser(message, objectif=message)
    return retenu


@transaction.atomic
def creer_programme(
    mission: Mission, *, objectif: ObjectifAudit, by: User, **champs: Any
) -> ProgrammeDeTravail:
    mission = _ouvrir(mission, by)
    cible = _objectif_de_la_mission(mission, objectif)
    if ProgrammeDeTravail.objects.filter(mission=mission, objectif=cible).exists():
        message = "Cet objectif a déjà un programme de travail."
        raise refuser(message, objectif=message)
    programme = ProgrammeDeTravail(mission=mission, objectif=cible)
    appliquer(programme, champs, CHAMPS_PROGRAMME)
    enregistrer(programme, by=by, creation=True)
    return programme


@transaction.atomic
def modifier_programme(
    programme: ProgrammeDeTravail, *, by: User, **changes: Any
) -> ProgrammeDeTravail:
    _ouvrir(programme.mission, by)
    programme = relire(programme)
    appliquer(programme, changes, CHAMPS_PROGRAMME)
    enregistrer(programme, by=by)
    return programme


@transaction.atomic
def supprimer_programme(programme: ProgrammeDeTravail, *, by: User) -> None:
    _ouvrir(programme.mission, by)
    programme = relire(programme)
    if programme.tests.exists():
        raise refuser(MSG_TESTS_ACTIFS)
    programme.soft_delete(by)
