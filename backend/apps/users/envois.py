"""Authentication emails leave from the Celery worker only (AUTH-01).

In production only `worker` reaches the SMTP relay (network `mail-out`, secret
`email_password`); `web` has no route out, on purpose: giving the internet-facing container
an egress would widen what a compromise of it can reach. So the web process never sends an
authentication email itself, it queues a task, and **no secret ever travels through the
broker**:

- login code: the task receives the account id and issues the code itself (like the
  forgotten-password code, `tasks.envoyer_code_reinitialisation`);
- temporary password (welcome, reset by an administrator or a delegate): the clear password
  is stored encrypted (Fernet, key derived from `SECRET_KEY`) in an `EnvoiMotDePasse` row
  that lives one hour at most; the task receives the row id only, reads the row once, deletes
  it, and sends the email if that password is still the account's current one.

The web side cannot know whether the email will actually be delivered: "queued" is what it
reports. A temporary password is therefore shown to the operator (once) only when nothing was
queued: sending switched off by the caller or not configured, no address on the account, or
the broker unreachable. If the worker then fails to send, it logs an error and the operator
gives a new temporary password (reset with display).
"""

import base64
import logging
from datetime import timedelta
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .auth_services import envoi_courriel_actif, logger_securite
from .courriels import envoyer_bienvenue, envoyer_mot_de_passe_reinitialise
from .models import EnvoiMotDePasse, NatureEnvoi, User

logger = logging.getLogger(__name__)

# Long enough for a busy worker, short enough that a forgotten row is worth little.
DUREE_ENVOI_EN_ATTENTE = timedelta(hours=1)
_SEL = "apps.users.envois.EnvoiMotDePasse"


def _fernet() -> Fernet:
    """Key derived from SECRET_KEY: a database dump alone never reveals a password."""
    cle = salted_hmac(_SEL, "envoi-mot-de-passe", algorithm="sha256").digest()
    return Fernet(base64.urlsafe_b64encode(cle))


def mettre_en_file_mot_de_passe(user: User, mot_de_passe: str, nature: NatureEnvoi) -> bool:
    """Queue the email carrying this temporary password. True = queued (never shown then).

    Call it after the commit that set the password. False when sending is not configured,
    the account has no address, or the broker cannot be reached (no row is left behind).
    """
    from .tasks import envoyer_mot_de_passe_temporaire

    if not user.email or not envoi_courriel_actif():
        return False
    envoi = EnvoiMotDePasse.objects.create(
        user=user,
        nature=nature,
        contenu=_fernet().encrypt(mot_de_passe.encode("utf-8")),
        expire_le=timezone.now() + DUREE_ENVOI_EN_ATTENTE,
    )
    try:
        envoyer_mot_de_passe_temporaire.delay(str(envoi.pk))
    except Exception as exc:  # noqa: BLE001 - broker down: the password is shown instead
        EnvoiMotDePasse.objects.filter(pk=envoi.pk).delete()
        logger_securite.warning(
            "Courriel de mot de passe temporaire non mis en file : compte=%s (%s)",
            user.pk,
            type(exc).__name__,
        )
        return False
    return True


def envoyer_mot_de_passe_en_attente(envoi_id: str) -> bool:
    """Worker side: read the row once (deleted at once), then send. True = sent."""
    try:
        cle = UUID(str(envoi_id))
    except ValueError:
        return False
    with transaction.atomic():
        envoi = EnvoiMotDePasse.objects.select_for_update().filter(pk=cle).first()
        if envoi is None:
            return False
        envoi.delete()
    user = User.objects.filter(pk=envoi.user_id, is_active=True).first()
    if envoi.expire_le <= timezone.now() or user is None:
        logger_securite.warning(
            "Courriel de mot de passe temporaire abandonné (expiré ou compte inactif) : compte=%s",
            envoi.user_id,
        )
        return False
    try:
        mot_de_passe = _fernet().decrypt(bytes(envoi.contenu)).decode("utf-8")
    except InvalidToken:  # SECRET_KEY changed meanwhile
        logger_securite.warning("Mot de passe en attente illisible : compte=%s", envoi.user_id)
        return False
    if not user.check_password(mot_de_passe):
        # Replaced (new reset) or already changed by its owner: never mail a stale password.
        logger_securite.info(
            "Courriel de mot de passe temporaire inutile (mot de passe déjà remplacé) : compte=%s",
            user.pk,
        )
        return False
    envoyer = (
        envoyer_bienvenue
        if envoi.nature == NatureEnvoi.BIENVENUE
        else (envoyer_mot_de_passe_reinitialise)
    )
    if not envoyer(user, mot_de_passe):
        logger_securite.error(
            "Courriel de mot de passe temporaire NON envoyé : compte=%s nature=%s. "
            "Réinitialisez le mot de passe avec affichage.",
            user.pk,
            envoi.nature,
        )
        return False
    return True


def purger_envois_expires() -> int:
    """Delete the rows past their expiry (a worker down for an hour). Returns the count."""
    supprimes, _ = EnvoiMotDePasse.objects.filter(expire_le__lte=timezone.now()).delete()
    return supprimes
