import logging

from celery import shared_task

from .models import User

logger = logging.getLogger(__name__)


@shared_task(name="users.purger_codes")  # type: ignore[untyped-decorator]
def purger_codes() -> int:
    """Daily purge of the transient credentials: one-time codes expired for more than 24 h,
    import password files past their 24 h (never downloaded) and queued temporary passwords
    past their hour (worker down). Returns the rows deleted."""
    from .auth_services import purger_codes_expires
    from .envois import purger_envois_expires
    from .provisioning import purger_fichiers_mots_de_passe

    return purger_codes_expires() + purger_fichiers_mots_de_passe() + purger_envois_expires()


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
    from .auth_services import (
        emettre_otp,
        envoi_courriel_actif,
        logger_securite,
        quota_codes_reinitialisation,
        reinitialisation_bloquee,
    )
    from .courriels import envoyer_code
    from .models import ObjetOtp

    if compte_id is None:
        return False
    compte = User.objects.filter(pk=compte_id, is_active=True).first()
    if compte is None or not compte.email or not envoi_courriel_actif():
        return False
    if reinitialisation_bloquee(compte):
        # AUTH-02: too many wrong codes in 24 h. The reset by an administrator remains.
        logger_securite.warning(
            "Code de réinitialisation non émis, compte bloqué (codes faux) : compte=%s",
            compte.pk,
        )
        return False
    if not quota_codes_reinitialisation(compte.pk):
        logger.warning("Quota des codes de réinitialisation atteint : compte=%s", compte.pk)
        return False
    code = emettre_otp(compte, ObjetOtp.RESET)
    if not envoyer_code(compte, code, ObjetOtp.RESET):
        logger.warning("Code de réinitialisation non envoyé : compte=%s", compte.pk)
        return False
    return True


@shared_task(name="users.envoyer_code_connexion")  # type: ignore[untyped-decorator]
def envoyer_code_connexion(compte_id: int) -> bool:
    """Issue and email the LOGIN code of a login waiting for its second step (AUTH-01).

    Queued by the login view once the password is right: the code is issued here, in the
    worker (the only container that reaches the SMTP relay), never carried by the broker.
    Nothing is issued for an account that no longer qualifies (login code turned off,
    disabled, locked, no address).
    """
    from .auth_services import (
        compte_utilisable,
        emettre_otp,
        envoi_courriel_actif,
        logger_securite,
        quota_codes_connexion,
    )
    from .courriels import envoyer_code
    from .models import ObjetOtp

    compte = User.objects.filter(pk=compte_id, is_active=True, otp_connexion_actif=True).first()
    if compte is None or not compte.email or not envoi_courriel_actif():
        return False
    if compte_utilisable(compte) is not None:
        return False
    if not quota_codes_connexion(compte.pk):
        # N6: the password holder cannot flood the owner's mailbox (the last code mailed
        # stays valid).
        logger_securite.warning(
            "Code de connexion non émis, plafond par compte atteint : compte=%s", compte.pk
        )
        return False
    code = emettre_otp(compte, ObjetOtp.LOGIN)
    if not envoyer_code(compte, code, ObjetOtp.LOGIN):
        logger.warning("Code de connexion non envoyé : compte=%s", compte.pk)
        return False
    return True


@shared_task(name="users.envoyer_code_activation_otp")  # type: ignore[untyped-decorator]
def envoyer_code_activation_otp(compte_id: int) -> bool:
    """Issue and email the ACTIVATION code the owner asked for in "Mon compte".

    Same rules as the login code (issued in the worker, per-account cap); nothing is
    issued once the option is on.
    """
    from .auth_services import (
        emettre_otp,
        envoi_courriel_actif,
        logger_securite,
        quota_codes_connexion,
    )
    from .courriels import envoyer_code
    from .models import ObjetOtp

    compte = User.objects.filter(pk=compte_id, is_active=True, otp_connexion_actif=False).first()
    if compte is None or not compte.email or not envoi_courriel_actif():
        return False
    if not quota_codes_connexion(compte.pk):
        logger_securite.warning(
            "Code d'activation non émis, plafond par compte atteint : compte=%s", compte.pk
        )
        return False
    code = emettre_otp(compte, ObjetOtp.ACTIVATION)
    if not envoyer_code(compte, code, ObjetOtp.ACTIVATION):
        logger.warning("Code d'activation non envoyé : compte=%s", compte.pk)
        return False
    return True


@shared_task(name="users.envoyer_mot_de_passe_temporaire")  # type: ignore[untyped-decorator]
def envoyer_mot_de_passe_temporaire(envoi_id: str, compte_id: int | None = None) -> bool:
    """Email a temporary password queued by `envois.mettre_en_file_mot_de_passe` (AUTH-01).

    The arguments are the id of the encrypted, short-lived row and the account id (for the
    error log if the row is gone): the password itself never travels through the broker.
    The row is read once and deleted.
    """
    from .envois import envoyer_mot_de_passe_en_attente

    return envoyer_mot_de_passe_en_attente(envoi_id, compte_id)
