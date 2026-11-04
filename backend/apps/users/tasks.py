import logging

from celery import shared_task

from .models import User

logger = logging.getLogger(__name__)


@shared_task(name="users.purger_codes")  # type: ignore[untyped-decorator]
def purger_codes() -> int:
    """Daily purge of the transient credentials: one-time codes expired for more than 24 h
    and import password files past their 24 h (never downloaded). Returns the rows deleted."""
    from .auth_services import purger_codes_expires
    from .provisioning import purger_fichiers_mots_de_passe

    return purger_codes_expires() + purger_fichiers_mots_de_passe()


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
