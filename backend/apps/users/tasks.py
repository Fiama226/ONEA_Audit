import logging
from datetime import timedelta

from celery import shared_task
from django.db.models import F
from django.utils import timezone

from .keycloak_admin import KeycloakIndisponible, KeycloakNonConfigure
from .keycloak_sync import synchroniser_avec_resultat
from .models import KeycloakSyncStatut, User

logger = logging.getLogger(__name__)

BACKOFF_BASE = timedelta(minutes=15)
BACKOFF_MAX_EXPONENT = 6  # caps the delay at 15 min * 64 = 16 h


@shared_task(name="users.synchroniser_comptes_keycloak")  # type: ignore[untyped-decorator]
def synchroniser_comptes_keycloak(limit: int = 50) -> int:
    """Retry the pending / failed Keycloak syncs, oldest attempt first.

    Permanent failures (404, refused: `keycloak_sync_manuel`) are left to a manual relaunch,
    and transient ones are retried with an exponential backoff on `tentatives`, so that an
    unrecoverable account does not write an audit row every 15 minutes. Stops at the first
    `KeycloakIndisponible` (or missing configuration): the other accounts would fail the same
    way. Returns the number of accounts processed.
    """
    now = timezone.now()
    candidats = (
        User.objects.filter(
            keycloak_id__isnull=False,
            keycloak_sync_manuel=False,
            keycloak_sync_statut__in=(KeycloakSyncStatut.EN_ATTENTE, KeycloakSyncStatut.ECHEC),
        )
        .order_by(F("keycloak_sync_le").asc(nulls_first=True), "pk")
        .values_list("pk", "keycloak_sync_le", "keycloak_sync_tentatives")
    )
    ids: list[int] = []
    for pk, derniere, tentatives in candidats.iterator():
        delai = BACKOFF_BASE * 2 ** min(tentatives, BACKOFF_MAX_EXPONENT)
        if derniere is not None and derniere > now - delai:
            continue
        ids.append(pk)
        if len(ids) >= limit:
            break
    traites = 0
    for compte_id in ids:
        try:
            _, erreur = synchroniser_avec_resultat(compte_id, by=None)
        except User.DoesNotExist:
            continue
        traites += 1
        if isinstance(erreur, KeycloakIndisponible | KeycloakNonConfigure):
            logger.warning("Keycloak sync batch interrupted after %s account(s)", traites)
            break
    return traites


@shared_task(name="users.purger_codes")  # type: ignore[untyped-decorator]
def purger_codes() -> int:
    """Daily purge of one-time codes expired for more than 24 h."""
    from .auth_services import purger_codes_expires

    return purger_codes_expires()


@shared_task(name="users.purger_sessions")  # type: ignore[untyped-decorator]
def purger_sessions() -> None:
    """Daily removal of expired sessions (database backend; Django's clearsessions)."""
    from django.core.management import call_command

    call_command("clearsessions")


@shared_task(name="users.envoyer_code_reinitialisation")  # type: ignore[untyped-decorator]
def envoyer_code_reinitialisation(compte_id: int | None) -> bool:
    """Issue and email a RESET code, for an active account only. Never tells the caller.

    Queued by every "forgotten password" request, known account or not (``None``), so that
    the answer costs the same work whatever the identifier: only the worker does the hash
    and the SMTP exchange. The code is issued here, never carried by the broker.
    """
    from .auth_services import emettre_otp, envoi_courriel_actif, quota_codes_reinitialisation
    from .courriels import envoyer_code
    from .models import ObjetOtp

    if compte_id is None:
        return False
    compte = User.objects.filter(pk=compte_id, is_active=True).first()
    if compte is None or not compte.email or not envoi_courriel_actif():
        return False
    if not quota_codes_reinitialisation(compte.pk):
        logger.warning("Quota des codes de réinitialisation atteint : compte=%s", compte.pk)
        return False
    code = emettre_otp(compte, ObjetOtp.RESET)
    if not envoyer_code(compte, code, ObjetOtp.RESET):
        logger.warning("Code de réinitialisation non envoyé : compte=%s", compte.pk)
        return False
    return True
