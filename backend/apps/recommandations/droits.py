"""Droits du plan d'actions (D8, D13 du plan du lot 7) : seule source pour vues et frontend.

Construits sur `missions.acces`. `contexte_plan` calcule une fois (rôle, entités de l'audité,
fenêtre) ; `actions_action` et `actions_recommandation` sont ensuite presque purs.
"""

from dataclasses import dataclass, field
from uuid import UUID

from django.db.models import Q, QuerySet

from apps.missions.acces import declaration_levee, role_dans_mission
from apps.missions.models import ROLES_INTERVENANTS, EtapeMission, Mission, RoleMission
from apps.missions.services.travaux import STATUTS_TRAVAUX
from apps.referentiel.models import Direction
from apps.users.models import Role, User

from .models import AcceptationRisque, Action
from .services._fenetres import ETAPE_CLOTURE, fenetre_ouverte
from .services.statuts import INCONNU, _Inconnu

MODIFIER = "MODIFIER"
SUPPRIMER = "SUPPRIMER"
AJOUTER_ACTION = "AJOUTER_ACTION"
ACCEPTER_RISQUE = "ACCEPTER_RISQUE"
RETIRER_ACCEPTATION = "RETIRER_ACCEPTATION"


@dataclass(frozen=True)
class ContextePlan:
    contribue: bool = False
    rai: bool = False
    audite: bool = False
    fenetre: bool = False
    entites: frozenset[str] = field(default_factory=frozenset)


def contexte_plan(mission: Mission, user: User) -> ContextePlan:
    statuts = dict(
        EtapeMission.objects.filter(mission=mission, numero__in=(ETAPE_CLOTURE, 16)).values_list(
            "numero", "statut"
        )
    )
    fenetre = mission.statut in STATUTS_TRAVAUX and fenetre_ouverte(
        statuts.get(ETAPE_CLOTURE), statuts.get(16)
    )
    role = role_dans_mission(user, mission)
    audite = user.role == Role.AUDITE and role == RoleMission.AUDITE
    entites: frozenset[str] = frozenset()
    if audite and user.direction_code:
        entites = frozenset(
            str(pk)
            for pk in Direction.objects.filter(code=user.direction_code).values_list(
                "pk", flat=True
            )
        )
    return ContextePlan(
        # équivalent à peut_contribuer, sans relire le rôle dans la mission (requêtes bornées)
        contribue=user.role == Role.RAI
        or (role in ROLES_INTERVENANTS and declaration_levee(user, mission)),
        rai=user.role == Role.RAI,
        audite=audite,
        fenetre=fenetre,
        entites=entites,
    )


def peut_proposer(contexte: ContextePlan, entite_id: UUID | str | None) -> bool:
    """Équipe habilitée, ou audité responsable de l'entité du constat."""
    if contexte.contribue:
        return True
    return contexte.audite and entite_id is not None and str(entite_id) in contexte.entites


def peut_ecrire_action(action: Action, user: User, *, contexte: ContextePlan) -> bool:
    """Droit d'écriture sur l'action, indépendamment de la fenêtre (le gel répond 422)."""
    if contexte.contribue:
        return True
    if contexte.audite and user.pk in (action.proposee_par_id, action.responsable_id):
        return peut_proposer(contexte, action.recommandation.constat.entite_id)
    return False


def actions_action(action: Action, user: User, *, contexte: ContextePlan) -> list[str]:
    if not contexte.fenetre or not peut_ecrire_action(action, user, contexte=contexte):
        return []
    return [MODIFIER, SUPPRIMER]


def actions_recommandation(
    reco: object,
    user: User,
    *,
    contexte: ContextePlan,
    nb_actions: int | None = None,
    acceptation: AcceptationRisque | None | _Inconnu = INCONNU,
) -> list[str]:
    from apps.constats.models import Recommandation, StatutConstat

    if not contexte.fenetre or not isinstance(reco, Recommandation):
        return []
    constat = reco.constat
    if constat.statut != StatutConstat.VALIDE:
        return []
    if acceptation is INCONNU:
        acceptation = AcceptationRisque.objects.filter(recommandation=reco).first()
    if nb_actions is None:
        nb_actions = Action.objects.filter(recommandation=reco).count()
    resultat: list[str] = []
    if acceptation is not None and not isinstance(acceptation, _Inconnu):
        if contexte.rai or (contexte.audite and acceptation.auteur_id == user.pk):
            resultat.append(RETIRER_ACCEPTATION)
        return resultat
    if peut_proposer(contexte, constat.entite_id):
        resultat.append(AJOUTER_ACTION)
    if nb_actions == 0 and contexte.audite and peut_proposer(contexte, constat.entite_id):
        resultat.append(ACCEPTER_RISQUE)
    return resultat


def actions_visibles(user: User, mission: Mission) -> QuerySet[Action]:
    """RAI et intervenants : tout ; audité affecté : son entité ou ses actions ; sinon rien."""
    base = Action.objects.filter(mission=mission)
    if user.role == Role.RAI:
        return base
    role = role_dans_mission(user, mission)
    if user.role == Role.AUDITEUR and role in ROLES_INTERVENANTS:
        return base
    if user.role == Role.AUDITE and role == RoleMission.AUDITE:
        critere = Q(responsable=user)
        if user.direction_code:
            critere |= Q(recommandation__constat__entite__code=user.direction_code)
        return base.filter(critere)
    return Action.objects.none()


def peut_engager(user: User, mission: Mission) -> bool:
    contexte = contexte_plan(mission, user)
    if not (contexte.audite and contexte.fenetre):
        return False
    return Action.objects.filter(mission=mission, responsable=user).exists()
