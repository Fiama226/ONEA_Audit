"""Engagement de chaque responsable sur ses actions (D8) : ajout seul, « à renouveler »."""

from collections.abc import Iterable
from typing import Any, Literal

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer
from apps.missions.acces import role_dans_mission
from apps.missions.models import Mission, RoleMission
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.services import confirmer, empreinte
from apps.users.models import Role, User

from ..models import Action, EngagementPlanActions
from ._fenetres import ouvrir_plan

type EtatEngagement = Literal["CONFIRME", "A_RENOUVELER", "NON_CONFIRME"]

MSG_DROIT = "Seul un audité affecté à la mission peut s'engager sur le plan d'actions."
MSG_AUCUNE = "Aucune action ne vous est attribuée."


def actions_du_responsable(mission: Mission, user: User) -> list[Action]:
    return list(Action.objects.filter(mission=mission, responsable=user).order_by("numero"))


def donnees_actions(actions: Iterable[Action]) -> dict[str, Any]:
    return {
        "actions": [
            {
                "reference": a.reference,
                "libelle": a.libelle,
                "echeance": a.echeance.isoformat() if a.echeance else None,
                "indicateur": a.indicateur,
            }
            for a in actions
        ]
    }


def empreinte_actions(actions: Iterable[Action]) -> str:
    return empreinte("", donnees_actions(actions))


def etat_depuis(
    actions: Iterable[Action], engagement: EngagementPlanActions | None
) -> EtatEngagement:
    if engagement is None:
        return "NON_CONFIRME"
    if engagement.empreinte_actions == empreinte_actions(actions):
        return "CONFIRME"
    return "A_RENOUVELER"


def dernier_engagement(mission: Mission, user: User) -> EngagementPlanActions | None:
    return (
        EngagementPlanActions.objects.filter(mission=mission, auteur=user)
        .order_by("-created_at", "-pk")
        .first()
    )


def texte_engagement(mission: Mission, user: User) -> str:
    """Texte exact confirmé par l'audité (à confirmer avec ONEA)."""
    n = Action.objects.filter(mission=mission, responsable=user).count()
    qui = user.nom_complet + (f", {user.fonction}" if user.fonction else "")
    return (
        f"Je soussigné(e) {qui}, m'engage à mettre en œuvre les {n} actions dont je suis "
        f"responsable dans le plan d'actions de la mission {mission.reference}, "
        f"selon les échéances indiquées."
    )


@transaction.atomic
def engager(mission: Mission, *, by: User, adresse_ip: str | None = None) -> EngagementPlanActions:
    mission = ouvrir_plan(mission)
    if by.role != Role.AUDITE or role_dans_mission(by, mission) != RoleMission.AUDITE:
        raise PermissionDenied(MSG_DROIT)
    actions = actions_du_responsable(mission, by)
    if not actions:
        raise RegleMetierError(MSG_AUCUNE)
    confirmation = confirmer(
        type_document=TypeDocumentSignable.ENGAGEMENT_PLAN_ACTIONS,
        objet=mission,
        texte=texte_engagement(mission, by),
        donnees=donnees_actions(actions),
        by=by,
        adresse_ip=adresse_ip,
    )
    engagement = EngagementPlanActions(
        mission=mission,
        auteur=by,
        confirmation=confirmation,
        empreinte_actions=empreinte_actions(actions),
    )
    enregistrer(engagement, by=by, creation=True)
    return engagement


def etat_engagement(mission: Mission, user: User) -> EtatEngagement:
    return etat_depuis(actions_du_responsable(mission, user), dernier_engagement(mission, user))
