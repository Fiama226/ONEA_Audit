"""Quota de stockage unique (`DOCUMENTS_QUOTA_MO`, 0 = sans quota).

Une seule fonction pour tous les dépôts. Sont comptés, lignes supprimées logiquement comprises
(leurs fichiers restent sur le disque) : les gabarits, les versions Word et PDF des documents
générés, les pièces justificatives et les preuves de mise en œuvre du suivi.
"""

from django.apps import apps
from django.conf import settings
from django.db.models import Sum

from apps.core.exceptions import RegleMetierError

from ..models import DocumentVersion, GabaritDocument

MSG_QUOTA = "Le quota de stockage des documents est atteint : contactez l'administrateur."


def utilise_octets() -> int:
    """Octets occupés par les gabarits, les versions de documents et les pièces justificatives."""
    gabarits = GabaritDocument.all_objects.aggregate(t=Sum("taille"))["t"] or 0
    versions = DocumentVersion.all_objects.aggregate(d=Sum("taille_docx"), p=Sum("taille_pdf"))
    piece = apps.get_model("accomplissement", "PieceJustificative")
    pieces = piece.all_objects.aggregate(t=Sum("taille_octets"))["t"] or 0
    preuve = apps.get_model("suivi", "PreuveMiseEnOeuvre")
    preuves = preuve.all_objects.aggregate(t=Sum("taille_octets"))["t"] or 0
    return int(gabarits + (versions["d"] or 0) + (versions["p"] or 0) + pieces + preuves)


def controler_quota(ajout_octets: int) -> None:
    """Refuse (422) si l'ajout dépasse le quota. `ajout_octets` = 0 : taille inconnue (génération)
    — refusé seulement si le quota est déjà atteint."""
    quota_mo = int(settings.DOCUMENTS_QUOTA_MO)
    if quota_mo <= 0:
        return
    if utilise_octets() + max(ajout_octets, 1) > quota_mo * 1024 * 1024:
        raise RegleMetierError(MSG_QUOTA)
