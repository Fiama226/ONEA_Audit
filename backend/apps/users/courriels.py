"""Authentication emails (plain text, French). Never logs a code or a password."""

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .auth_services import envoi_courriel_actif
from .models import ObjetOtp, User

logger = logging.getLogger(__name__)

_OBJETS = {
    ObjetOtp.RESET: "réinitialisation de votre mot de passe",
    ObjetOtp.LOGIN: "confirmation de votre connexion",
}


def _envoyer(user: User, sujet: str, template: str, contexte: dict[str, object]) -> bool:
    if not user.email or not envoi_courriel_actif():
        return False
    corps = render_to_string(f"email/{template}.txt", contexte)
    try:
        send_mail(f"[ONEA Audit] {sujet}", corps, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception as exc:  # noqa: BLE001 - SMTP failures must not break the caller
        logger.warning(
            "auth email %s failed for user %s: %s", template, user.pk, type(exc).__name__
        )
        return False
    return True


def envoyer_bienvenue(user: User, mot_de_passe: str) -> bool:
    return _envoyer(
        user,
        "Bienvenue sur la plateforme d'audit interne",
        "auth_bienvenue",
        {
            "name": user.nom_complet,
            "identifiant": user.username,
            "mot_de_passe": mot_de_passe,
            "url": settings.PLATEFORME_URL,
        },
    )


def envoyer_mot_de_passe_reinitialise(user: User, mot_de_passe: str) -> bool:
    """Temporary password set by an administrator (or delegate) on an existing account."""
    return _envoyer(
        user,
        "Votre mot de passe a été réinitialisé",
        "auth_reinitialisation_admin",
        {
            "name": user.nom_complet,
            "identifiant": user.username,
            "mot_de_passe": mot_de_passe,
            "url": settings.PLATEFORME_URL,
        },
    )


def envoyer_code(user: User, code: str, objet: str) -> bool:
    return _envoyer(
        user,
        f"Votre code de vérification : {_OBJETS[ObjetOtp(objet)]}",
        "auth_code",
        {"name": user.nom_complet, "code": code, "objet": _OBJETS[ObjetOtp(objet)]},
    )
