"""In-app authentication: password login with lockout, one-time codes, temporary passwords."""

import logging
import secrets
import string
from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

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


def _trouver_compte(identifiant: str) -> User | None:
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


def compte_utilisable(compte: User) -> str | None:
    """Reason why this account cannot open a session now, or None."""
    now = timezone.now()
    if compte.verrouille_jusqu_a is not None and compte.verrouille_jusqu_a > now:
        return "verrouille"
    if not compte.is_active:
        return "desactive"
    if compte.mot_de_passe_expire_le is not None and compte.mot_de_passe_expire_le <= now:
        return "mot_de_passe_temporaire_expire"
    return None


def enregistrer_echec(compte: User, motif: str, adresse: str | None = None) -> None:
    """Count a failure on the account; the 5th consecutive one locks it for 15 minutes.

    A failure while locked neither counts nor extends the lock (no lock-forever by a third
    party). The counter restarts at zero when the lock is set.
    """
    with transaction.atomic():
        verrou = User.objects.select_for_update().get(pk=compte.pk)
        now = timezone.now()
        if verrou.verrouille_jusqu_a is not None and verrou.verrouille_jusqu_a > now:
            _journaliser_refus("verrouille", verrou, adresse)
            return
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


def enregistrer_succes(compte: User) -> None:
    """Full login success: reset the failure counter and mark the first login."""
    now = timezone.now()
    User.objects.filter(pk=compte.pk).update(echecs_connexion=0, verrouille_jusqu_a=None)
    User.objects.filter(pk=compte.pk, premiere_connexion_le__isnull=True).update(
        premiere_connexion_le=now
    )
    compte.refresh_from_db(
        fields=["echecs_connexion", "verrouille_jusqu_a", "premiere_connexion_le"]
    )


def authentifier(identifiant: str, mot_de_passe: str, *, adresse: str | None = None) -> Resultat:
    """Check a login. Every refusal looks the same to the caller (and costs one hash).

    Refused: unknown or ambiguous identifier, wrong password, locked, disabled, expired
    temporary password. Only a wrong password on an open account counts as a failure.
    When the next step is the OTP, the failure counter is kept until the code is checked.
    """
    compte = _trouver_compte(identifiant)
    mot_de_passe_ok = _verifier_mot_de_passe(compte, mot_de_passe)
    if compte is None:
        _journaliser_refus("compte_inconnu", None, adresse)
        return _REFUS
    motif = compte_utilisable(compte)
    if motif == "verrouille" or (motif is None and not mot_de_passe_ok):
        enregistrer_echec(compte, "mot_de_passe", adresse)
        return _REFUS
    if motif is not None:  # disabled or expired temporary password
        _journaliser_refus(motif, compte, adresse)
        return _REFUS
    etape = etape_apres_mot_de_passe(compte)
    if etape is not Etape.OTP:
        enregistrer_succes(compte)
    return Resultat(user=compte, etape=etape)


def authentifier_code(user_id: int, code: str, *, adresse: str | None = None) -> Resultat:
    """Second step of a login with OTP. A wrong code counts as a login failure."""
    compte = User.objects.filter(pk=user_id).first()
    if compte is None:
        return _REFUS
    motif = compte_utilisable(compte)
    if motif is not None:
        _journaliser_refus(motif, compte, adresse)
        return _REFUS
    if not verifier_otp(compte, ObjetOtp.LOGIN, code):
        enregistrer_echec(compte, "code_otp", adresse)
        return _REFUS
    enregistrer_succes(compte)
    return Resultat(user=compte, etape=etape_apres_second_facteur(compte))


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


def purger_codes_expires() -> int:
    """Delete codes that expired more than 24 h ago. Returns the number deleted."""
    limite = timezone.now() - OTP_PURGE_APRES
    supprimes, _ = CodeOtp.objects.filter(expire_le__lt=limite).delete()
    return supprimes
