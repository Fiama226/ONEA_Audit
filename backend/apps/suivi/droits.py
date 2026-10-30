"""Droits du suivi : section visibilité (R11).

- RAI : tout ; DG : lecture seule ; AUDITEUR et AUDITE : leurs missions (`missions_visibles`) ;
  ADMIN : rien.
- Le suivi n'est lisible que pour les missions dont le rapport est déjà diffusé.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db.models import QuerySet

from apps.core.exceptions import RegleMetierError
from apps.missions.acces import missions_visibles, role_dans_mission
from apps.missions.models import (
    ROLES_INTERVENANTS,
    AffectationMission,
    DeclarationIndependance,
    Mission,
    RoleMission,
    StatutMission,
)
from apps.users.models import Role, User

from .models import (
    STATUTS_CLOS,
    PreuveMiseEnOeuvre,
    StatutDemandeReport,
    StatutSuivi,
    SuiviAction,
)

STATUTS_MISSION_SUIVI: frozenset[str] = frozenset(
    {StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI, StatutMission.CLOTUREE}
)


def missions_suivi_visibles(user: User) -> QuerySet[Mission]:
    if user.role in (Role.RAI, Role.DG):
        base = Mission.objects.all()
    elif user.role in (Role.AUDITEUR, Role.AUDITE):
        base = missions_visibles(user)
    else:
        return Mission.objects.none()
    return base.filter(statut__in=STATUTS_MISSION_SUIVI)


def suivis_visibles(user: User) -> QuerySet[SuiviAction]:
    return SuiviAction.objects.filter(mission__in=missions_suivi_visibles(user).values("pk"))


# --- Section « actions » (T5) : droits des transitions, commentaires et responsable ----------
# Les droits d'une action se calculent ici et nulle part ailleurs (services, API, frontend).

CODES = (
    "DEMARRER",
    "DECLARER_REALISEE",
    "PROPOSER_ABANDON",
    "VERIFIER",
    "REJETER",
    "CLOTURER",
    "ACCEPTER_ABANDON",
    "ROUVRIR",
    "COMMENTER",
    "CHANGER_RESPONSABLE",
    "DEPOSER_PREUVE",
    "DEMANDER_REPORT",
)

STATUTS_MISSION_ACTIFS: frozenset[str] = frozenset(
    {StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI}
)

_RAI = "RAI"
_RESPONSABLE = "RESPONSABLE"  # responsable de l'action
_VERIFICATEUR = "VERIFICATEUR"  # intervenant de la mission à déclaration levée
_MEMBRE = "MEMBRE"  # audité affecté à la mission
_LANCABLES = (StatutSuivi.A_LANCER, StatutSuivi.EN_COURS)
_OUVERTS = tuple(s for s in StatutSuivi if s not in STATUTS_CLOS)
_TOUS = tuple(StatutSuivi)
_EXECUTANTS = frozenset({_RAI, _RESPONSABLE})
_VERIFIEURS = frozenset({_RAI, _VERIFICATEUR})

# code -> statut de l'action -> groupes autorisés (R2, R3, R4).
REGLES: dict[str, dict[str, frozenset[str]]] = {
    "DEMARRER": {StatutSuivi.A_LANCER: _EXECUTANTS},
    "DECLARER_REALISEE": dict.fromkeys(_LANCABLES, _EXECUTANTS),
    "PROPOSER_ABANDON": dict.fromkeys(_LANCABLES, _EXECUTANTS),
    "VERIFIER": {StatutSuivi.REALISEE: _VERIFIEURS},
    "REJETER": {
        StatutSuivi.REALISEE: _VERIFIEURS,
        StatutSuivi.VERIFIEE: frozenset({_RAI}),
        StatutSuivi.ABANDON_PROPOSE: frozenset({_RAI}),
    },
    "CLOTURER": {StatutSuivi.VERIFIEE: frozenset({_RAI})},
    "ACCEPTER_ABANDON": {StatutSuivi.ABANDON_PROPOSE: frozenset({_RAI})},
    "ROUVRIR": dict.fromkeys(STATUTS_CLOS, frozenset({_RAI})),
    "COMMENTER": dict.fromkeys(_TOUS, frozenset({_RAI, _RESPONSABLE, _VERIFICATEUR, _MEMBRE})),
    "CHANGER_RESPONSABLE": dict.fromkeys(_OUVERTS, frozenset({_RAI})),
    "DEPOSER_PREUVE": dict.fromkeys(_LANCABLES, _EXECUTANTS),
    "DEMANDER_REPORT": dict.fromkeys(_LANCABLES, _EXECUTANTS),
}

# Codes qui engagent la responsabilité de la déclaration (jamais `declaree_par`).
CODES_VERIFICATION: frozenset[str] = frozenset({"VERIFIER", "REJETER"})

MSG_AUTO_VERIFICATION = (
    "Vous avez déclaré cette action : sa vérification revient à une autre personne."
)


@dataclass(frozen=True)
class ContexteSuivi:
    """Rôles de l'utilisateur par mission, calculés une fois pour une liste d'actions."""

    user: User
    roles: Mapping[UUID, str] = field(default_factory=dict)
    levees: frozenset[UUID] = frozenset()
    statuts_mission: Mapping[UUID, str] = field(default_factory=dict)


def contexte_suivi(user: User, missions: Iterable[UUID]) -> ContexteSuivi:
    """Trois requêtes au plus, quel que soit le nombre de missions."""
    ids = set(missions)
    if not ids:
        return ContexteSuivi(user=user)
    statuts = dict(Mission.objects.filter(pk__in=ids).values_list("pk", "statut"))
    roles: dict[UUID, str] = {}
    levees: set[UUID] = set()
    if user.role in (Role.AUDITEUR, Role.AUDITE):
        affectations = AffectationMission.objects.filter(utilisateur=user, mission_id__in=ids)
        roles = dict(affectations.values_list("mission_id", "role_mission"))
        declarations = DeclarationIndependance.objects.filter(
            affectation__utilisateur=user,
            affectation__mission_id__in=ids,
            affectation__deleted_at__isnull=True,
        ).select_related("affectation")
        levees = {d.affectation.mission_id for d in declarations if d.levee}
    return ContexteSuivi(user=user, roles=roles, levees=frozenset(levees), statuts_mission=statuts)


def _groupes(suivi: SuiviAction, user: User, contexte: ContexteSuivi) -> set[str]:
    if user.role == Role.RAI:
        return {_RAI}
    groupes: set[str] = set()
    if user.role == Role.AUDITE and suivi.responsable_id == user.pk:
        groupes.add(_RESPONSABLE)
    role_mission = contexte.roles.get(suivi.mission_id)
    if user.role == Role.AUDITE and role_mission == RoleMission.AUDITE:
        groupes.add(_MEMBRE)
    if (
        user.role == Role.AUDITEUR
        and role_mission in ROLES_INTERVENANTS
        and suivi.mission_id in contexte.levees
    ):
        groupes.add(_VERIFICATEUR)
    return groupes


def _refus_declarant(suivi: SuiviAction, user: User, code: str) -> bool:
    if code not in CODES_VERIFICATION:
        return False
    return suivi.statut == StatutSuivi.REALISEE and suivi.declaree_par_id == user.pk


def _evaluer(suivi: SuiviAction, user: User, code: str, contexte: ContexteSuivi) -> str:
    """`OK`, `ROLE` (droit absent : 403), `ETAT` (opération impossible : 422) ou `DECLARANT`."""
    regles = REGLES[code]
    groupes = _groupes(suivi, user, contexte)
    if not groupes & frozenset().union(*regles.values()):
        return "ROLE"
    if contexte.statuts_mission.get(suivi.mission_id) not in STATUTS_MISSION_ACTIFS:
        return "ETAT"
    autorises = regles.get(suivi.statut)
    if autorises is None or not groupes & autorises:
        return "ETAT"
    if _refus_declarant(suivi, user, code):
        return "DECLARANT"
    return "OK"


def actions_possibles(suivi: SuiviAction, user: User, *, contexte: ContexteSuivi) -> list[str]:
    return [c for c in CODES if _evaluer(suivi, user, c, contexte) == "OK"]


def exiger_droit_action(user: User, suivi: SuiviAction, code: str) -> None:
    """403 seulement : l'API le contrôle AVANT le sérialiseur (400) ; l'état reste un 422 aval."""
    contexte = contexte_suivi(user, [suivi.mission_id])
    if _evaluer(suivi, user, code, contexte) == "ROLE":
        raise PermissionDenied("Vous n'avez pas le droit d'effectuer cette opération.")


def exiger_action(user: User, suivi: SuiviAction, code: str) -> None:
    """403 si l'utilisateur n'a pas ce droit ; 422 si l'état de l'action ne le permet pas."""
    contexte = contexte_suivi(user, [suivi.mission_id])
    verdict = _evaluer(suivi, user, code, contexte)
    if verdict == "ROLE":
        raise PermissionDenied("Vous n'avez pas le droit d'effectuer cette opération.")
    if verdict == "DECLARANT":
        raise RegleMetierError(MSG_AUTO_VERIFICATION)
    if verdict == "ETAT":
        libelle = StatutSuivi(suivi.statut).label
        raise RegleMetierError(f"Cette opération n'est pas possible pour une action « {libelle} ».")


# --- preuves et reports (T6) ---------------------------------------------------------------
MSG_DROIT_SUIVI = "Vous n'avez pas le droit d'effectuer cette opération sur cette action."
MSG_DROIT_DECISION = "Seul le RAI peut décider d'une demande de report."
MSG_DROIT_PREUVE = "Vous n'avez pas le droit de consulter cette preuve."


def peut_operer_pour_responsable(user: User, suivi: SuiviAction) -> bool:
    """Responsable courant de l'action, ou RAI (saisie pour son compte, R3)."""
    if user.role == Role.RAI:
        return True
    return user.role == Role.AUDITE and suivi.responsable_id == user.pk


def exiger_operer_pour_responsable(user: User, suivi: SuiviAction) -> None:
    if not peut_operer_pour_responsable(user, suivi):
        raise PermissionDenied(MSG_DROIT_SUIVI)


def exiger_decideur_report(user: User) -> None:
    if user.role != Role.RAI:
        raise PermissionDenied(MSG_DROIT_DECISION)


def peut_telecharger_preuve(user: User, preuve: PreuveMiseEnOeuvre) -> bool:
    """RAI, auditeurs et audités affectés à la mission. DG et ADMIN : jamais (R8, R11)."""
    mission = preuve.mission
    if mission.statut not in STATUTS_MISSION_SUIVI:
        return False
    if user.role == Role.RAI:
        return True
    if user.role in (Role.AUDITEUR, Role.AUDITE):
        return role_dans_mission(user, mission) is not None
    return False


def exiger_telechargement_preuve(user: User, preuve: PreuveMiseEnOeuvre) -> None:
    if not peut_telecharger_preuve(user, preuve):
        raise PermissionDenied(MSG_DROIT_PREUVE)


# --- droits affichés par l'API pour les preuves et les demandes de report (T10) --------------
# Mêmes règles que les services de T6, sans requête par ligne : le contexte est celui de la page.
STATUTS_PREUVES_MODIFIABLES: frozenset[str] = frozenset(
    {StatutSuivi.A_LANCER, StatutSuivi.EN_COURS}
)


def actions_preuve(preuve: PreuveMiseEnOeuvre, user: User, *, contexte: ContexteSuivi) -> list[str]:
    """`MODIFIER` et `RETIRER` (exécutant, action ouverte, mission non figée), `TELECHARGER`."""
    codes: list[str] = []
    mission_statut = contexte.statuts_mission.get(preuve.mission_id)
    if (
        peut_operer_pour_responsable(user, preuve.suivi)
        and mission_statut in STATUTS_MISSION_ACTIFS
        and preuve.suivi.statut in STATUTS_PREUVES_MODIFIABLES
    ):
        codes += ["MODIFIER", "RETIRER"]
    lisible = mission_statut in STATUTS_MISSION_SUIVI and (
        user.role == Role.RAI
        or (user.role in (Role.AUDITEUR, Role.AUDITE) and preuve.mission_id in contexte.roles)
    )
    if lisible:
        codes.append("TELECHARGER")
    return codes


def actions_demande(demande: Any, user: User, *, contexte: ContexteSuivi) -> list[str]:
    """`ACCEPTER` (action encore reportable) et `REFUSER` : RAI, demande en attente."""
    if user.role != Role.RAI or demande.statut != StatutDemandeReport.EN_ATTENTE:
        return []
    if contexte.statuts_mission.get(demande.mission_id) not in STATUTS_MISSION_ACTIFS:
        return []
    codes = ["REFUSER"]
    if demande.suivi.statut in STATUTS_PREUVES_MODIFIABLES:
        codes.insert(0, "ACCEPTER")
    return codes
