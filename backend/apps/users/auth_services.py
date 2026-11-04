"""In-app authentication: password login with lockout, one-time codes, temporary passwords."""

import logging
import secrets
import string
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from redis.exceptions import RedisError

from apps.core.exceptions import RegleMetierError

from .models import CodeOtp, ObjetOtp, User

# Security log: failed logins and locks. Never a password, never the typed identifier
# (users often type their password in the identifier field); the account id only.
logger_securite = logging.getLogger("onea.securite")

OTP_VALIDITE = timedelta(minutes=10)
OTP_ESSAIS_MAX = 5
OTP_PURGE_APRES = timedelta(hours=24)
MOT_DE_PASSE_TEMPORAIRE_LONGUEUR = 16
ECHECS_AVANT_VERROUILLAGE = 5
DUREE_VERROUILLAGE = timedelta(minutes=15)
# At most this many RESET codes per account per window (each code allows 5 guesses).
CODES_REINITIALISATION_MAX = 10
CODES_REINITIALISATION_FENETRE = timedelta(hours=24)
# Session key of a login waiting for its OTP step: the account id.
CLE_OTP_COMPTE = "onea_otp_compte"

MEME_MOT_DE_PASSE = "Le nouveau mot de passe doit être différent de l'actuel."
ENVOI_COURRIEL_NON_CONFIGURE = "Envoi de courriels non configuré"
COMPTE_SANS_COURRIEL = "Aucune adresse de courriel n'est enregistrée sur votre compte."


class OtpImpossible(RegleMetierError):
    """The login code cannot be turned on: no email could reach the account."""

    status_http = 409


class Etape(StrEnum):
    """What the client must do after a successful password check."""

    OK = "OK"
    OTP = "OTP"
    CHANGER_MOT_DE_PASSE = "CHANGER_MOT_DE_PASSE"


@dataclass(frozen=True)
class Resultat:
    """Outcome of `authentifier`. `etape is None` means refused (the reason is never exposed)."""

    user: User | None = None
    etape: Etape | None = None


_REFUS = Resultat()


def trouver_compte(identifiant: str) -> User | None:
    """Account by exact username, else by case-insensitive email if exactly one account has it."""
    identifiant = identifiant.strip()
    if not identifiant:
        return None
    compte = User.objects.filter(username=identifiant).first()
    if compte is not None:
        return compte
    if "@" not in identifiant:
        return None
    # email is not unique on AbstractUser: an ambiguous address must never pick an account.
    candidats = list(User.objects.filter(email__iexact=identifiant)[:2])
    return candidats[0] if len(candidats) == 1 else None


def _verifier_mot_de_passe(compte: User | None, mot_de_passe: str) -> bool:
    """Password check that always costs one hash (unknown account, unusable password)."""
    if compte is None or not compte.has_usable_password():
        make_password(mot_de_passe)  # same work as a real check: no timing oracle
        return False
    return compte.check_password(mot_de_passe)


def _journaliser_refus(motif: str, compte: User | None, adresse: str | None) -> None:
    logger_securite.warning(
        "Échec de connexion : motif=%s compte=%s adresse=%s",
        motif,
        compte.pk if compte is not None else "inconnu",
        adresse or "inconnue",
    )


def etape_apres_mot_de_passe(compte: User) -> Etape:
    if compte.otp_connexion_actif:
        return Etape.OTP
    return etape_apres_second_facteur(compte)


def etape_apres_second_facteur(compte: User) -> Etape:
    return Etape.CHANGER_MOT_DE_PASSE if compte.doit_changer_mot_de_passe else Etape.OK


def compte_utilisable(compte: User, now: datetime | None = None) -> str | None:
    """Reason why this account cannot open a session now, or None."""
    now = now or timezone.now()
    if compte.verrouille_jusqu_a is not None and compte.verrouille_jusqu_a > now:
        return "verrouille"
    if not compte.is_active:
        return "desactive"
    if compte.mot_de_passe_expire_le is not None and compte.mot_de_passe_expire_le <= now:
        return "mot_de_passe_temporaire_expire"
    return None


def _compter_echec(verrou: User, now: datetime, motif: str, adresse: str | None) -> None:
    """Count a failure on the row-locked, usable account; the 5th one locks it for 15 min.

    The counter restarts at zero when the lock is set: 5 new attempts once the lock ends.
    """
    verrou.echecs_connexion += 1
    champs = ["echecs_connexion"]
    if verrou.echecs_connexion >= ECHECS_AVANT_VERROUILLAGE:
        verrou.echecs_connexion = 0
        verrou.verrouille_jusqu_a = now + DUREE_VERROUILLAGE
        champs.append("verrouille_jusqu_a")
    verrou.save(update_fields=champs)
    _journaliser_refus(motif, verrou, adresse)
    if "verrouille_jusqu_a" in champs:
        logger_securite.warning(
            "Compte verrouillé %s minutes après %s échecs : compte=%s",
            int(DUREE_VERROUILLAGE.total_seconds() // 60),
            ECHECS_AVANT_VERROUILLAGE,
            verrou.pk,
        )


def _conclure(
    compte_id: int,
    secret_ok: bool,
    *,
    motif_echec: str,
    etape_de: Callable[[User], Etape],
    adresse: str | None,
) -> Resultat:
    """Decide on the account row as it is NOW (row-locked), after the slow secret check.

    Lock, active flag and temporary-password expiry are read again under
    ``select_for_update``: deciding on the row read before the hash would let a concurrent
    request clear a lock set meanwhile, or count a right password as a failure when the lock
    ended meanwhile. An unusable account gets the uniform refusal without counting or
    resetting anything (a failure while locked never extends the lock). A wrong secret on a
    usable account counts; a right one resets the counter, except when the next step is the
    OTP (the counter is then kept until the code is checked).
    """
    with transaction.atomic():
        verrou = User.objects.select_for_update().filter(pk=compte_id).first()
        if verrou is None:
            return _REFUS
        now = timezone.now()
        motif = compte_utilisable(verrou, now)
        if motif is not None:
            _journaliser_refus(motif, verrou, adresse)
            return _REFUS
        if not secret_ok:
            _compter_echec(verrou, now, motif_echec, adresse)
            return _REFUS
        etape = etape_de(verrou)
        if etape is not Etape.OTP:
            verrou.echecs_connexion = 0
            verrou.verrouille_jusqu_a = None
            champs = ["echecs_connexion", "verrouille_jusqu_a"]
            if verrou.premiere_connexion_le is None:
                verrou.premiere_connexion_le = now
                champs.append("premiere_connexion_le")
            verrou.save(update_fields=champs)
        return Resultat(user=verrou, etape=etape)


def authentifier(identifiant: str, mot_de_passe: str, *, adresse: str | None = None) -> Resultat:
    """Check a login. Every refusal looks the same to the caller (and costs one hash).

    Refused: unknown or ambiguous identifier, wrong password, locked, disabled, expired
    temporary password. Only a wrong password on a usable account counts as a failure.
    """
    compte = trouver_compte(identifiant)
    mot_de_passe_ok = _verifier_mot_de_passe(compte, mot_de_passe)
    if compte is None:
        _journaliser_refus("compte_inconnu", None, adresse)
        return _REFUS
    return _conclure(
        compte.pk,
        mot_de_passe_ok,
        motif_echec="mot_de_passe",
        etape_de=etape_apres_mot_de_passe,
        adresse=adresse,
    )


def authentifier_code(user_id: int, code: str, *, adresse: str | None = None) -> Resultat:
    """Second step of a login with OTP. A wrong code counts as a login failure."""
    compte = User.objects.filter(pk=user_id).first()
    if compte is None:
        return _REFUS
    # An account already unusable burns no code attempt; _conclure re-checks in any case.
    code_ok = compte_utilisable(compte) is None and verifier_otp(compte, ObjetOtp.LOGIN, code)
    return _conclure(
        compte.pk,
        code_ok,
        motif_echec="code_otp",
        etape_de=etape_apres_second_facteur,
        adresse=adresse,
    )


# No look-alike characters (0/O, 1/l/I) since the password is read from an email.
_ALPHABET_MDP = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
_BACKENDS_SANS_SMTP = ("console", "locmem")


def emettre_otp(user: User, objet: str) -> str:
    """Create a fresh code and return it in clear (only time it exists in clear).

    Any existing active code for (user, objet) is dropped first, even an expired one, since
    it would still occupy the unique active slot.
    """
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    with transaction.atomic():
        # Lock the user row so concurrent issuances for the same user serialize
        # (otherwise both delete, both insert, and the unique active slot raises).
        User.objects.select_for_update().get(pk=user.pk)
        CodeOtp.objects.filter(user=user, objet=objet, utilise_le__isnull=True).delete()
        CodeOtp.objects.create(
            user=user,
            objet=objet,
            code_hash=make_password(code),
            expire_le=timezone.now() + OTP_VALIDITE,
        )
    return code


def verifier_otp(user: User, objet: str, code: str) -> bool:
    """Check and consume the active code. Every failed check counts as an attempt."""
    with transaction.atomic():
        actif = (
            CodeOtp.objects.select_for_update()
            .filter(user=user, objet=objet, utilise_le__isnull=True)
            .first()
        )
        now = timezone.now()
        if actif is None or actif.expire_le <= now or actif.essais >= OTP_ESSAIS_MAX:
            make_password(code)  # same work as a real check: "no pending code" is no oracle
            return False
        actif.essais += 1
        if not check_password(code, actif.code_hash):
            actif.save(update_fields=["essais"])
            return False
        actif.utilise_le = now
        actif.save(update_fields=["essais", "utilise_le"])
        return True


def generer_mot_de_passe_temporaire() -> str:
    return "".join(secrets.choice(_ALPHABET_MDP) for _ in range(MOT_DE_PASSE_TEMPORAIRE_LONGUEUR))


def envoi_courriel_actif() -> bool:
    """True when an email can actually go out (SMTP host set, or console backend in dev)."""
    if getattr(settings, "EMAIL_HOST", ""):
        return True
    return any(nom in settings.EMAIL_BACKEND for nom in _BACKENDS_SANS_SMTP)


def quota_codes_reinitialisation(compte_id: int) -> bool:
    """Count one RESET code for this account; False past the cap of the 24 h window.

    Silent server-side cap (the forgot answer never changes): the per-identifier throttle
    keys on the typed text, so an account reachable by username and by email would get
    twice the codes, and every new code brings 5 fresh guesses. If the cache is down the
    code is allowed, like the throttles.
    """
    cle = f"onea_codes_reinitialisation_{compte_id}"
    try:
        cache.add(cle, 0, timeout=int(CODES_REINITIALISATION_FENETRE.total_seconds()))
        return int(cache.incr(cle)) <= CODES_REINITIALISATION_MAX
    except ValueError:  # the key expired between add and incr: a new window starts
        cache.set(cle, 1, timeout=int(CODES_REINITIALISATION_FENETRE.total_seconds()))
        return True
    except (RedisError, OSError) as exc:
        logger_securite.warning(
            "Quota des codes de réinitialisation non appliqué : cache indisponible (%s).",
            type(exc).__name__,
        )
        return True


def terminer_sessions(compte_id: int, *, sauf: str | None = None) -> int:
    """Delete every live session of this account, except ``sauf``. Returns the number deleted.

    Covers logged-in sessions (``_auth_user_id``) and logins waiting for their OTP step. The
    database store keeps the session data signed and serialized, so the rows cannot be
    filtered in SQL: the unexpired ones are decoded in chunks (expired rows can no longer be
    loaded and are left to the daily purge). Django's session hash check already refuses a
    session after a password change on its next request; this removes the rows outright.
    """
    store = SessionStore()
    cible = str(compte_id)
    cles: list[str] = []
    lignes = (
        Session.objects.filter(expire_date__gt=timezone.now())
        .values_list("session_key", "session_data")
        .iterator(chunk_size=500)
    )
    for cle, donnees in lignes:
        if cle == sauf:
            continue
        session = store.decode(donnees)
        if session.get(SESSION_KEY) == cible or session.get(CLE_OTP_COMPTE) == compte_id:
            cles.append(cle)
    supprimees, _ = Session.objects.filter(session_key__in=cles).delete()
    return supprimees


def _appliquer_mot_de_passe(verrou: User, nouveau: str) -> None:
    """Set the password on the row-locked account and lift every login hindrance.

    Codes still pending were issued under the old password (a login waiting for its OTP
    step, an earlier reset request): they are dropped. The account's active flag is never
    touched here.
    """
    verrou.set_password(nouveau)
    verrou.doit_changer_mot_de_passe = False
    verrou.mot_de_passe_expire_le = None
    verrou.echecs_connexion = 0
    verrou.verrouille_jusqu_a = None
    verrou.save(
        update_fields=[
            "password",
            "doit_changer_mot_de_passe",
            "mot_de_passe_expire_le",
            "echecs_connexion",
            "verrouille_jusqu_a",
        ]
    )
    CodeOtp.objects.filter(user=verrou, utilise_le__isnull=True).delete()


def reinitialiser_mot_de_passe(
    identifiant: str, code: str, nouveau: str, *, adresse: str | None = None
) -> User | None:
    """Reset a forgotten password with the RESET code. None = refused (reason never exposed).

    Refused alike: unknown or ambiguous identifier, disabled account, no code, wrong,
    expired, used or exhausted code. Every refusal costs exactly one hash. The new password
    is checked first without the account (raises ``ValidationError``: the answer cannot
    depend on the account), then against the account once the code is right; a password
    refused there rolls the code check back, so the code is not burnt. On success all the
    sessions of the account end and the login lock, failure count and forced change go.
    """
    validate_password(nouveau)
    compte = trouver_compte(identifiant)
    if compte is None:
        make_password(code)
        _journaliser_reinitialisation_refusee("compte_inconnu", None, adresse)
        return None
    with transaction.atomic():
        verrou = User.objects.select_for_update().filter(pk=compte.pk).first()
        if verrou is None or not verrou.is_active:
            make_password(code)
            _journaliser_reinitialisation_refusee("desactive", compte, adresse)
            return None
        if not verifier_otp(verrou, ObjetOtp.RESET, code):
            _journaliser_reinitialisation_refusee("code", verrou, adresse)
            return None
        validate_password(nouveau, verrou)  # raising rolls back the code consumption
        _appliquer_mot_de_passe(verrou, nouveau)
    sessions = terminer_sessions(verrou.pk)
    logger_securite.info(
        "Mot de passe réinitialisé par code : compte=%s adresse=%s sessions_terminees=%s",
        verrou.pk,
        adresse or "inconnue",
        sessions,
    )
    return verrou


def _journaliser_reinitialisation_refusee(
    motif: str, compte: User | None, adresse: str | None
) -> None:
    logger_securite.warning(
        "Échec de réinitialisation du mot de passe : motif=%s compte=%s adresse=%s",
        motif,
        compte.pk if compte is not None else "inconnu",
        adresse or "inconnue",
    )


def _reconfirmer(
    compte: User, mot_de_passe: str, *, motif: str, adresse: str | None
) -> User | None:
    """Re-check the password of a logged-in account before a sensitive change.

    Returns the row-locked account (call inside ``transaction.atomic`` to keep the lock for
    the change), or None. A wrong password counts as a login failure (5 lock the account for
    15 min) and a locked account is refused even with the right one: an open session cannot
    be used to guess the password.
    """
    mot_de_passe_ok = _verifier_mot_de_passe(compte, mot_de_passe)
    return _conclure(
        compte.pk,
        mot_de_passe_ok,
        motif_echec=motif,
        etape_de=etape_apres_second_facteur,
        adresse=adresse,
    ).user


def changer_mot_de_passe(
    compte: User, ancien: str, nouveau: str, *, adresse: str | None = None
) -> User | None:
    """Change the password of a logged-in account. None = current password refused.

    The new password is validated first (``ValidationError``, no hash spent), then the
    current one re-checked (``_reconfirmer``). The caller ends the other sessions and keeps
    the current one.
    """
    if nouveau == ancien:
        raise ValidationError(MEME_MOT_DE_PASSE, code="password_unchanged")
    validate_password(nouveau, compte)
    with transaction.atomic():
        verrou = _reconfirmer(compte, ancien, motif="ancien_mot_de_passe", adresse=adresse)
        if verrou is None:
            return None
        _appliquer_mot_de_passe(verrou, nouveau)
    logger_securite.info(
        "Mot de passe changé par son titulaire : compte=%s adresse=%s",
        verrou.pk,
        adresse or "inconnue",
    )
    return verrou


def _enregistrer_otp_connexion(compte: User, actif: bool, adresse: str | None) -> None:
    """Save the flag (the audit trail records it through auditlog) and log the event."""
    if compte.otp_connexion_actif != actif:
        compte.otp_connexion_actif = actif
        compte.save(update_fields=["otp_connexion_actif"])
    logger_securite.info(
        "Code de connexion par courriel %s : compte=%s adresse=%s",
        "activé" if actif else "désactivé",
        compte.pk,
        adresse or "inconnue",
    )


def activer_otp_connexion(compte: User, *, adresse: str | None = None) -> None:
    """Turn the login code on for the caller's own account.

    It needs a working email (and an address on the account): the account would otherwise be
    locked out at its next login.
    """
    if not envoi_courriel_actif():
        raise OtpImpossible(ENVOI_COURRIEL_NON_CONFIGURE)
    if not compte.email:
        raise OtpImpossible(COMPTE_SANS_COURRIEL)
    _enregistrer_otp_connexion(compte, True, adresse)


def desactiver_otp_connexion(
    compte: User, mot_de_passe: str, *, adresse: str | None = None
) -> User | None:
    """Turn the login code off for the caller's own account, on its current password.

    A stolen session must not be enough to remove the second factor: the password is
    re-checked like for a password change (``_reconfirmer``). None = password refused.
    Works without email (the way out of a login code that no longer arrives).
    """
    with transaction.atomic():
        verrou = _reconfirmer(compte, mot_de_passe, motif="confirmation_otp", adresse=adresse)
        if verrou is None:
            return None
        _enregistrer_otp_connexion(verrou, False, adresse)
    return verrou


def purger_codes_expires() -> int:
    """Delete codes that expired more than 24 h ago. Returns the number deleted."""
    limite = timezone.now() - OTP_PURGE_APRES
    supprimes, _ = CodeOtp.objects.filter(expire_le__lt=limite).delete()
    return supprimes
