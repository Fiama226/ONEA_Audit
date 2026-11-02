"""Droits sur les travaux d'analyse : seule source, consommée par les vues et le frontend.

Construits sur `missions.acces` (rôle, déclaration d'indépendance levée, `peut_contribuer`).
Au plus trois requêtes : rôle (1), déclaration levée d'un intervenant (1), statuts des étapes
III, V, VI, VII (1). Le gel de mission est lu sur l'instance `mission` fournie par l'appelant
(la vue vient de la charger), alors que les gardes d'écriture le relisent en base.
"""

from dataclasses import dataclass

from apps.core.memoire import memoise
from apps.missions.acces import declaration_levee, peut_contribuer, role_dans_mission
from apps.missions.gardes import STATUTS_FIGES
from apps.missions.models import ROLES_INTERVENANTS, Mission, RoleMission, StatutEtape
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


def _profil(user: User, mission: Mission) -> tuple[bool, bool, bool]:
    """(voir_travaux, peut_contribuer, audite_affecte)."""
    if user.role == Role.RAI:
        return True, peut_contribuer(user, mission), False
    if user.role not in (Role.AUDITEUR, Role.AUDITE):
        return False, False, False
    role = role_dans_mission(user, mission)
    if user.role == Role.AUDITEUR and role in ROLES_INTERVENANTS:
        # Même règle que `peut_contribuer`, sans relire le rôle.
        return True, declaration_levee(user, mission), False
    return False, False, user.role == Role.AUDITE and role == RoleMission.AUDITE


def droits_analyse(user: User, mission: Mission) -> DroitsAnalyse:
    """Mémorisé dans un bloc `memo_lecture()` (lecture seule), sinon recalculé."""
    return memoise(("droits_analyse", user.pk, mission.pk), lambda: _calculer(user, mission))


def _calculer(user: User, mission: Mission) -> DroitsAnalyse:
    voir_travaux, contribue, audite = _profil(user, mission)
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
