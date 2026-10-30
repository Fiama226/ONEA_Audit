"""Saisie pour le compte du responsable (R3), partagée par les preuves et les reports."""

from typing import Any

from apps.core.services import refuser
from apps.users.models import Role, User

from ..models import SuiviAction

MSG_COMMENTAIRE_COMPTE = (
    "Un commentaire est obligatoire pour une saisie pour le compte du responsable."
)


def pour_compte(suivi: SuiviAction, by: User, commentaire: str) -> tuple[str, Any]:
    """Texte de l'événement et `pour_compte_de` : le RAI qui n'est pas le responsable agit pour lui.

    Le commentaire est alors obligatoire et préfixé « Saisi par le RAI pour le compte de … : ».
    """
    commentaire = commentaire.strip()
    if by.role != Role.RAI or by.pk == suivi.responsable_id:
        return commentaire, None
    if not commentaire:
        raise refuser(MSG_COMMENTAIRE_COMPTE, commentaire=MSG_COMMENTAIRE_COMPTE)
    nom = suivi.responsable.nom_complet or suivi.responsable.email
    return f"Saisi par le RAI pour le compte de {nom} : {commentaire}", suivi.responsable
