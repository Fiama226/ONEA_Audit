"""One-time codes (OTP) and temporary passwords for the in-app authentication."""

import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from .models import CodeOtp, User

OTP_VALIDITE = timedelta(minutes=10)
OTP_ESSAIS_MAX = 5
OTP_PURGE_APRES = timedelta(hours=24)
MOT_DE_PASSE_TEMPORAIRE_LONGUEUR = 16

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
