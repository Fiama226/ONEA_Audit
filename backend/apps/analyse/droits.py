"""Droits sur les travaux d'analyse : seule source, consommée par les vues et le frontend.

Au plus trois requêtes : rôle / déclaration (1), statuts des étapes III, V, VI, VII (1).
"""

from dataclasses import dataclass

from apps.missions.gardes import STATUTS_FIGES
from apps.missions.models import (
    ROLES_INTERVENANTS,
    AffectationMission,
    DeclarationIndependance,
    Mission,
    RoleMission,
    StatutEtape,
)
from apps.users.models import Role, User

from .gardes import ACTIFS, statuts_etapes


@dataclass(frozen=True)
class DroitsAnalyse:
    voir_travaux: bool = False
    contribuer_iii: bool = False
    contribuer_v: bool = False
    donner_avis: bool = False
    voir_referentiel: bool = False
    contribuer_vii: bool = False


_AVIS_OUVERT = frozenset({StatutEtape.EN_COURS, StatutEtape.TERMINEE, StatutEtape.RENVOYEE})


def _contribution(user: User, mission: Mission) -> tuple[bool, bool, bool]:
    """(voir_travaux, peut_contribuer, audite_affecte) ; équivalent à `acces.peut_contribuer`."""
    if user.role == Role.RAI:
        return True, True, False
    if user.role == Role.AUDITEUR:
        declaration = (
            DeclarationIndependance.objects.filter(
                affectation__mission=mission,
                affectation__utilisateur=user,
                affectation__role_mission__in=ROLES_INTERVENANTS,
                affectation__deleted_at__isnull=True,
            )
            .select_related("affectation")
            .first()
        )
        return declaration is not None, declaration is not None and declaration.levee, False
    if user.role == Role.AUDITE:
        audite = AffectationMission.objects.filter(
            mission=mission, utilisateur=user, role_mission=RoleMission.AUDITE
        ).exists()
        return False, False, audite
    return False, False, False


def droits_analyse(user: User, mission: Mission) -> DroitsAnalyse:
    voir_travaux, contribue, audite = _contribution(user, mission)
    if not (voir_travaux or audite):
        return DroitsAnalyse()
    statuts = statuts_etapes(mission.pk, (3, 5, 6, 7))
    vi = statuts.get(6, StatutEtape.A_FAIRE)
    libre = mission.statut not in STATUTS_FIGES
    modifie = contribue and libre
    return DroitsAnalyse(
        voir_travaux=voir_travaux,
        contribuer_iii=modifie and statuts.get(3) in ACTIFS,
        contribuer_v=modifie and (statuts.get(5) in ACTIFS or vi in ACTIFS),
        donner_avis=audite and libre and vi in _AVIS_OUVERT,
        voir_referentiel=voir_travaux or (audite and vi != StatutEtape.A_FAIRE),
        contribuer_vii=modifie and statuts.get(7) in ACTIFS and vi == StatutEtape.VALIDEE,
    )
