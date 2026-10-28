"""Propagation of an account's activation state to Keycloak (D2).

The platform deactivation is authoritative and already committed when this runs; Keycloak
is only brought in line. The network calls are made outside any transaction, then a short
locked transaction records the outcome. The state applied is always the `is_active`
re-read from the database, and `A_JOUR` is only written when it did not change meanwhile,
so concurrent deactivation / reactivation converge on the next pass.

Messages stored on the account are fixed French strings (no secret, no response body).
"""

import logging
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError

from . import keycloak_admin
from .keycloak_admin import (
    KeycloakAdminError,
    KeycloakIndisponible,
    KeycloakIntrouvable,
    KeycloakNonConfigure,
)
from .models import KeycloakSyncStatut, User

logger = logging.getLogger(__name__)

DEJA_SYNCHRONISE_KEYCLOAK = "L'état du compte est déjà synchronisé avec Keycloak."
NON_LIE_ANNUAIRE = "Ce compte n'est pas encore lié à l'annuaire : rien à synchroniser."
ERREUR_INATTENDUE = "Erreur inattendue lors de la synchronisation avec Keycloak."


def _appliquer(keycloak_id: UUID, enabled: bool) -> KeycloakAdminError | None:
    """Push `enabled` to Keycloak. Returns the failure instead of raising it."""
    try:
        admin = keycloak_admin.get_keycloak_admin()
        try:
            admin.set_enabled(keycloak_id, enabled)
            if not enabled:
                admin.logout(keycloak_id)
        except KeycloakIntrouvable:
            if enabled:
                raise
            # Deactivation of an account that no longer exists in Keycloak: nothing to do.
    except KeycloakAdminError as exc:
        return exc
    except Exception:  # noqa: BLE001 - this function must never raise (beat task, request)
        logger.exception("Unexpected failure while syncing Keycloak user %s", keycloak_id)
        return KeycloakAdminError(ERREUR_INATTENDUE)
    return None


def est_permanente(erreur: KeycloakAdminError) -> bool:
    """True when retrying cannot help (404, refused, ...): manual relaunch only."""
    return not isinstance(erreur, KeycloakIndisponible | KeycloakNonConfigure)


def synchroniser_avec_resultat(
    compte_id: int, *, by: User | None = None
) -> tuple[User, KeycloakAdminError | None]:
    """Like `synchroniser_keycloak`, also returning the Keycloak failure (if any)."""
    compte = User.objects.get(pk=compte_id)
    if compte.keycloak_id is None or compte.keycloak_sync_statut == KeycloakSyncStatut.A_JOUR:
        return compte, None
    cible = compte.is_active
    # Snapshot of the attempt counter-part: every sync write bumps `keycloak_sync_le`, so a
    # sync that overlapped with another one sees a different value under the lock and must
    # not claim A_JOUR (its Keycloak write may have been overtaken).
    lu_le = compte.keycloak_sync_le
    erreur = _appliquer(compte.keycloak_id, cible)
    with transaction.atomic(), actor_scope(by):
        frais = User.objects.select_for_update().get(pk=compte_id)
        inchange = frais.is_active == cible and frais.keycloak_sync_le == lu_le
        if erreur is None:
            frais.keycloak_sync_statut = (
                KeycloakSyncStatut.A_JOUR if inchange else KeycloakSyncStatut.EN_ATTENTE
            )
            frais.keycloak_sync_erreur = ""
        else:
            frais.keycloak_sync_statut = (
                KeycloakSyncStatut.ECHEC if inchange else KeycloakSyncStatut.EN_ATTENTE
            )
            frais.keycloak_sync_erreur = erreur.message
        frais.keycloak_sync_manuel = erreur is not None and inchange and est_permanente(erreur)
        frais.keycloak_sync_le = timezone.now()
        frais.keycloak_sync_tentatives += 1
        frais.save(
            update_fields=[
                "keycloak_sync_statut",
                "keycloak_sync_erreur",
                "keycloak_sync_le",
                "keycloak_sync_tentatives",
                "keycloak_sync_manuel",
            ]
        )
    if erreur is not None:
        logger.warning(
            "Keycloak sync of account %s failed (%s): %s", compte_id, type(erreur).__name__, erreur
        )
    return frais, erreur


def synchroniser_keycloak(compte_id: int, *, by: User | None = None) -> User:
    """Bring Keycloak in line with the account. Never raises (except on database errors)."""
    return synchroniser_avec_resultat(compte_id, by=by)[0]


def relancer_synchronisation(compte: User, *, by: User) -> User:
    with transaction.atomic(), actor_scope(by):
        frais = User.objects.select_for_update().get(pk=compte.pk)
        if frais.keycloak_id is None:
            raise RegleMetierError(NON_LIE_ANNUAIRE)
        if frais.keycloak_sync_statut == KeycloakSyncStatut.A_JOUR:
            raise RegleMetierError(DEJA_SYNCHRONISE_KEYCLOAK)
        frais.keycloak_sync_statut = KeycloakSyncStatut.EN_ATTENTE
        frais.keycloak_sync_erreur = ""
        frais.keycloak_sync_manuel = False
        frais.save(
            update_fields=["keycloak_sync_statut", "keycloak_sync_erreur", "keycloak_sync_manuel"]
        )
    return synchroniser_keycloak(frais.pk, by=by)
