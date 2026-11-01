"""Réglages de plateforme (clé, valeur) et contenu des missions dans la piste d'audit (SEC-02)."""

from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.core.handlers import FORBIDDEN
from apps.core.services import enregistrer, refuser
from apps.users.models import Role, User

from .models import ParametrePlateforme

CLE_JOURNAL_CONTENU = "journal_audit_contenu_missions"


class ContenuJournal:
    """Valeurs de `journal_audit_contenu_missions` (« complet » par défaut, « masqué »)."""

    COMPLET = "COMPLET"
    MASQUE = "MASQUE"
    VALEURS = (COMPLET, MASQUE)
    LIBELLES = {COMPLET: "Complet", MASQUE: "Masqué"}


def contenu_journal() -> str:
    ligne = ParametrePlateforme.objects.filter(cle=CLE_JOURNAL_CONTENU).first()
    return (
        ligne.valeur if ligne and ligne.valeur in ContenuJournal.VALEURS else ContenuJournal.COMPLET
    )


def ligne_contenu_journal() -> ParametrePlateforme | None:
    return (
        ParametrePlateforme.objects.select_related("updated_by")
        .filter(cle=CLE_JOURNAL_CONTENU)
        .first()
    )


def modifier_contenu_journal(valeur: str, *, by: User) -> ParametrePlateforme:
    if not by.has_role(Role.ADMIN):
        raise PermissionDenied(FORBIDDEN)
    if valeur not in ContenuJournal.VALEURS:
        raise refuser("Données invalides.", valeur="Valeur inconnue.")
    with transaction.atomic():
        ligne = (
            ParametrePlateforme.objects.select_for_update().filter(cle=CLE_JOURNAL_CONTENU).first()
        )
        if ligne is None:
            # Création à la valeur par défaut, puis changement : l'audit garde un « avant ».
            ligne = ParametrePlateforme(cle=CLE_JOURNAL_CONTENU, valeur=ContenuJournal.COMPLET)
            enregistrer(ligne, by=by, creation=True)
        if ligne.valeur != valeur:
            ligne.valeur = valeur
            enregistrer(ligne, by=by)
    return ligne
