"""Actions correctives (D8 du plan du lot 7) : écritures sous verrou mission, étapes, entité."""

import datetime
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max

from apps.constats.models import Constat, Recommandation, StatutConstat
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.acces import role_dans_mission
from apps.missions.models import RoleMission
from apps.missions.services import aujourd_hui
from apps.users.models import Role, User

from .. import droits
from ..managers import prochain_numero_action
from ..models import AcceptationRisque, Action
from ._fenetres import ouvrir_plan

CHAMPS = {"libelle", "responsable", "echeance", "indicateur", "moyens", "ordre"}
MSG_NON_VALIDE = "Cette recommandation porte sur un constat non validé."
MSG_RESPONSABLE = "Le responsable doit être un audité affecté à la mission."
MSG_ECHEANCE = "L'échéance doit être postérieure ou égale à aujourd'hui."
MSG_LIBELLE = "La mesure corrective est obligatoire."
MSG_ACCEPTEE = (
    "Cette recommandation fait l'objet d'une acceptation du risque : "
    "retirez-la avant d'ajouter une action."
)
MSG_DROIT = "Vous ne pouvez pas modifier le plan d'actions de cette entité."


def _exiger_droit_proposition(by: User, constat: Constat, mission: Any) -> None:
    contexte = droits.contexte_plan(mission, by)
    if not droits.peut_proposer(contexte, constat.entite_id):
        raise PermissionDenied(MSG_DROIT)


def _verifier_responsable(responsable: User | None, mission: Any) -> None:
    if responsable is None:
        return
    if (
        responsable.role != Role.AUDITE
        or role_dans_mission(responsable, mission) != RoleMission.AUDITE
    ):
        raise refuser(MSG_RESPONSABLE, responsable=MSG_RESPONSABLE)


def _verifier_echeance(echeance: datetime.date | None) -> None:
    if echeance is not None and echeance < aujourd_hui():
        raise refuser(MSG_ECHEANCE, echeance=MSG_ECHEANCE)


def _verifier_champs(
    champs: dict[str, Any], mission: Any, *, echeance_actuelle: Any = None
) -> None:
    inconnus = set(champs) - CHAMPS
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    if "responsable" in champs:
        _verifier_responsable(champs["responsable"], mission)
    if "echeance" in champs and champs["echeance"] != echeance_actuelle:
        _verifier_echeance(champs["echeance"])


@transaction.atomic
def creer_action(
    recommandation: Recommandation, *, libelle: str, by: User, **champs: Any
) -> Action:
    mission = ouvrir_plan(recommandation.mission)
    recommandation = relire(recommandation)
    constat = recommandation.constat
    _exiger_droit_proposition(by, constat, mission)
    if constat.statut != StatutConstat.VALIDE:
        raise RegleMetierError(MSG_NON_VALIDE)
    if AcceptationRisque.objects.filter(recommandation=recommandation).exists():
        raise RegleMetierError(MSG_ACCEPTEE)
    libelle = libelle.strip()
    if not libelle:
        raise refuser(MSG_LIBELLE, libelle=MSG_LIBELLE)
    _verifier_champs(champs, mission)
    if "ordre" not in champs:
        dernier = Action.objects.filter(recommandation=recommandation).aggregate(m=Max("ordre"))
        champs["ordre"] = (dernier["m"] or 0) + 1
    numero = prochain_numero_action(mission.pk)
    action = Action(
        mission=mission,
        recommandation=recommandation,
        numero=numero,
        reference=f"A-{numero:02d}",
        libelle=libelle,
        proposee_par=by,
    )
    appliquer(action, champs, CHAMPS)
    enregistrer(action, by=by, creation=True)
    return action


@transaction.atomic
def modifier_action(action: Action, *, by: User, **changes: Any) -> Action:
    mission = ouvrir_plan(action.mission)
    action = relire(action)
    _exiger_droit_action(action, by, mission)
    if "libelle" in changes:
        changes["libelle"] = changes["libelle"].strip()
        if not changes["libelle"]:
            raise refuser(MSG_LIBELLE, libelle=MSG_LIBELLE)
    _verifier_champs(changes, mission, echeance_actuelle=action.echeance)
    appliquer(action, changes, CHAMPS)
    enregistrer(action, by=by)
    return action


@transaction.atomic
def supprimer_action(action: Action, *, by: User) -> None:
    mission = ouvrir_plan(action.mission)
    action = relire(action)
    _exiger_droit_action(action, by, mission)
    action.soft_delete(by)


def _exiger_droit_action(action: Action, by: User, mission: Any) -> None:
    contexte = droits.contexte_plan(mission, by)
    if not droits.actions_action(action, by, contexte=contexte):
        raise PermissionDenied(MSG_DROIT)
