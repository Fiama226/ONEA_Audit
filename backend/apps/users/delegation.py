"""Effective account-management rights: the ADMIN role, or rights delegated by an admin.

Rules (spec "Hypothèses", plan Task 6), enforced here for the API permissions *and* for
the services (which commands also call):

- an ADMIN may do every action (the per-action rules such as "not on one's own account" or
  "not the last admin" stay in the services);
- a non-ADMIN actor only has the rights of his ``DelegationGestionComptes``, and none while
  his account is disabled;
- a non-ADMIN actor never acts on a *protected* account: an ADMIN, another manager (an
  account holding a delegated right: no lateral move to rights one was not given) or his
  own account;
- only an ADMIN reads or changes a delegation, and only an ADMIN assigns the ADMIN role.

Everything is read from the database on every call (role, active flag, delegation): a
revocation, a deactivation or a role change takes effect on the very next request. Nothing
is cached.
"""

from typing import Any, Literal

from django.core.exceptions import PermissionDenied

from .models import Role, User

Action = Literal["creer", "reinitialiser", "roles", "desactiver"]
ACTIONS: tuple[Action, ...] = ("creer", "reinitialiser", "roles", "desactiver")

_CHAMPS = tuple(f"delegation_comptes__{action}" for action in ACTIONS)

DROIT_REFUSE = "Vous n'avez pas le droit d'effectuer cette action sur ce compte."
ADMIN_SEULEMENT = "Seul un administrateur peut gérer les délégations."
ATTRIBUTION_ADMIN = "Seul un administrateur peut attribuer le rôle Administrateur."


def _aucun() -> dict[str, bool]:
    return dict.fromkeys(ACTIONS, False)


def _etat(acteur: Any) -> tuple[bool, dict[str, bool]]:
    """``(est_admin, droits)`` of the actor, read fresh from the database."""
    if not isinstance(acteur, User) or acteur.pk is None:
        return False, _aucun()
    ligne = User.objects.filter(pk=acteur.pk).values("role", "is_active", *_CHAMPS).first()
    if ligne is None:
        return False, _aucun()
    if ligne["role"] == Role.ADMIN:
        # An inactive admin cannot authenticate; the demo system actor is one (commands).
        return True, dict.fromkeys(ACTIONS, True)
    if not ligne["is_active"]:
        return False, _aucun()
    return False, {action: bool(ligne[f"delegation_comptes__{action}"]) for action in ACTIONS}


def _cible_protegee(acteur: User, cible: User) -> bool:
    """For a non-ADMIN actor: own account, an ADMIN, or another manager."""
    if cible.pk is None or cible.pk == acteur.pk:
        return True
    ligne = User.objects.filter(pk=cible.pk).values("role", *_CHAMPS).first()
    if ligne is None:
        return True
    return ligne["role"] == Role.ADMIN or any(ligne[champ] for champ in _CHAMPS)


def droits_effectifs(acteur: Any) -> dict[str, bool]:
    """The four rights the actor holds (all of them for an ADMIN), whatever the target."""
    return _etat(acteur)[1]


def est_administrateur(acteur: Any) -> bool:
    return _etat(acteur)[0]


def etat_sur(acteur: Any, cible: User) -> tuple[bool, dict[str, bool]]:
    """``(est_admin, droits)`` of the actor on this target (two queries at most)."""
    admin, droits = _etat(acteur)
    if admin or not any(droits.values()):
        return admin, droits
    if _cible_protegee(acteur, cible):
        return False, _aucun()
    return False, droits


def droits_sur(acteur: Any, cible: User) -> dict[str, bool]:
    """The four rights the actor holds on this target."""
    return etat_sur(acteur, cible)[1]


def _verifier_action(action: str) -> None:
    if action not in ACTIONS:
        raise ValueError(f"Unknown account action: {action!r}")


def peut(acteur: Any, action: Action, cible: User | None = None) -> bool:
    """True when ``acteur`` may perform ``action`` (on ``cible`` when given)."""
    _verifier_action(action)
    if cible is None:
        return droits_effectifs(acteur)[action]
    return droits_sur(acteur, cible)[action]


def exiger(acteur: Any, action: Action, cible: User | None = None) -> None:
    """Service-side guard: raise ``PermissionDenied`` (HTTP 403) unless ``peut``."""
    if not peut(acteur, action, cible):
        raise PermissionDenied(DROIT_REFUSE)


def exiger_administrateur(acteur: Any, message: str = ADMIN_SEULEMENT) -> None:
    if not est_administrateur(acteur):
        raise PermissionDenied(message)


def exiger_attribution_role(acteur: Any, role: str) -> None:
    """Only an ADMIN gives the ADMIN role (at creation or by a role change)."""
    if role == Role.ADMIN:
        exiger_administrateur(acteur, ATTRIBUTION_ADMIN)
