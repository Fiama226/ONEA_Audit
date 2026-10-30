"""Textes exacts de confirmation du lot 7 communication (D7, D9), partagés par les tâches 7 et 8.

Les textes sont à confirmer avec ONEA ; ils sont figés dans l'empreinte de la `Confirmation`.
"""

from datetime import date, datetime
from typing import Any

from django.utils import timezone

from apps.constats.models import Constat
from apps.users.models import User

from ..models import Rapport, RapportProvisoire

FONCTION_RAI = "Responsable de l'Audit Interne"


def _date(valeur: date | datetime | str | None) -> str:
    """JJ/MM/AAAA (heure locale pour un instant), vide si absent."""
    if not valeur:
        return ""
    if isinstance(valeur, str):
        valeur = datetime.fromisoformat(valeur)
    if isinstance(valeur, datetime) and timezone.is_aware(valeur):
        valeur = timezone.localtime(valeur)
    return valeur.strftime("%d/%m/%Y")


def _qui(user: User) -> str:
    return user.nom_complet + (f", {user.fonction}" if user.fonction else "")


def texte_reponse_provisoire(
    constat: Constat, provisoire: RapportProvisoire, user: User, *, mission_reference: str
) -> str:
    """Texte confirmé par l'audité qui répond à un constat du rapport provisoire (D7)."""
    return (
        f"Je soussigné(e) {_qui(user)}, transmets la réponse de ma direction au constat "
        f"{constat.reference} « {constat.titre} » du rapport provisoire de la mission "
        f"{mission_reference} transmis le {_date(provisoire.transmis_le)}."
    )


def _compter(instantane: dict[str, Any]) -> tuple[int, int]:
    constats = instantane.get("constats") or []
    return len(constats), sum(len(c.get("recommandations") or []) for c in constats)


def texte_validation(rapport: Rapport, user: User) -> str:
    """Texte confirmé par le RAI qui valide le rapport soumis (D9)."""
    instantane: dict[str, Any] = rapport.instantane_soumis or {}
    constats, recommandations = _compter(instantane)
    mission = instantane.get("mission") or {}
    return (
        f"Je soussigné(e) {user.nom_complet}, {FONCTION_RAI}, valide le rapport d'audit de la "
        f"mission {mission.get('reference', '')} « {mission.get('titre', '')} » "
        f"(version soumise le {_date(rapport.soumis_le)}, {constats} constats, "
        f"{recommandations} recommandations), que j'atteste exact, objectif, clair, concis "
        f"et constructif."
    )
