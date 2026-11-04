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


INSTRUCTION_OPERATEUR = "Réinitialisez le mot de passe avec affichage."


def _perte(raison: str, compte_id: int | None, envoi_id: object) -> None:
    """A temporary password that will never reach its owner (N3): an ERROR the operator
    acts on. The account id and the row id only, never the password."""
    logger_securite.error(
        "Mot de passe temporaire perdu (%s) : compte=%s envoi=%s. %s",
        raison,
        compte_id if compte_id is not None else "inconnu",
        envoi_id,
        INSTRUCTION_OPERATEUR,
    )


def _dans_une_transaction() -> bool:
    """True inside an atomic block of the caller (a test case's own block does not count,
    like Django's check of durable blocks)."""
    connexion = transaction.get_connection()
    return any(not getattr(bloc, "_from_testcase", False) for bloc in connexion.atomic_blocks)


def _deposer(envoi_id: str, compte_id: int) -> bool:
    """Put the task on the broker; on failure drop the row. True = queued."""
    from .tasks import envoyer_mot_de_passe_temporaire

    try:
        envoyer_mot_de_passe_temporaire.delay(envoi_id, compte_id)
    except Exception as exc:  # noqa: BLE001 - broker down
        EnvoiMotDePasse.objects.filter(pk=envoi_id).delete()
        logger_securite.warning(
            "Courriel de mot de passe temporaire non mis en file : compte=%s (%s)",
            compte_id,
            type(exc).__name__,
        )
        return False
    return True


def _deposer_apres_validation(envoi_id: str, compte_id: int) -> None:
    """Run at the commit of the caller's transaction: the caller was already told
    "queued", so a broker failure now loses the password (logged as such)."""
    if not _deposer(envoi_id, compte_id):
        _perte("file indisponible", compte_id, envoi_id)


def mettre_en_file_mot_de_passe(user: User, mot_de_passe: str, nature: NatureEnvoi) -> bool:
    """Queue the email carrying this temporary password. True = queued (never shown then).

    False when sending is not configured, the account has no address, or the broker cannot
    be reached (no row is left behind): the caller shows the password once. Inside a
    transaction of the caller, the task is queued only at its commit, so that the worker
    never looks for a row not committed yet (N3); True is then answered at once.
    """
    if not user.email or not envoi_courriel_actif():
        return False
    envoi = EnvoiMotDePasse.objects.create(
        user=user,
        nature=nature,
        contenu=_fernet().encrypt(mot_de_passe.encode("utf-8")),
        expire_le=timezone.now() + DUREE_ENVOI_EN_ATTENTE,
    )
    envoi_id, compte_id = str(envoi.pk), user.pk
    if _dans_une_transaction():
        transaction.on_commit(lambda: _deposer_apres_validation(envoi_id, compte_id))
        return True
    return _deposer(envoi_id, compte_id)


def envoyer_mot_de_passe_en_attente(envoi_id: str, compte_id: int | None = None) -> bool:
    """Worker side: read the row once (deleted at once), then send. True = sent.

    Every way the password can be lost logs an ERROR with the operator's instruction (N3):
    row gone (purged, already read), expired, account disabled, row unreadable after a
    SECRET_KEY change, send failure. A password already replaced is not a loss (info).
    """
    try:
        cle = UUID(str(envoi_id))
    except ValueError:
        _perte("identifiant invalide", compte_id, envoi_id)
        return False
    with transaction.atomic():
        envoi = EnvoiMotDePasse.objects.select_for_update().filter(pk=cle).first()
        if envoi is None:
            _perte("en attente introuvable", compte_id, envoi_id)
            return False
        envoi.delete()
    if envoi.expire_le <= timezone.now():
        _perte("expiré avant l'envoi", envoi.user_id, envoi_id)
        return False
    user = User.objects.filter(pk=envoi.user_id, is_active=True).first()
    if user is None:
        _perte("compte désactivé", envoi.user_id, envoi_id)
        return False
    try:
        mot_de_passe = _fernet().decrypt(bytes(envoi.contenu)).decode("utf-8")
    except InvalidToken:  # SECRET_KEY changed meanwhile
        _perte("illisible après un changement de SECRET_KEY", envoi.user_id, envoi_id)
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
        else envoyer_mot_de_passe_reinitialise
    )
    if not envoyer(user, mot_de_passe):
        _perte(f"envoi SMTP en échec, nature={envoi.nature}", user.pk, envoi_id)
        return False
    return True


def purger_envois_expires() -> int:
    """Delete the rows past their expiry (a worker down for an hour). Returns the count."""
    supprimes, _ = EnvoiMotDePasse.objects.filter(expire_le__lte=timezone.now()).delete()
    return supprimes
