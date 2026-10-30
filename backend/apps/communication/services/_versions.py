"""Versions de documents du rapport validé : rapport final et note synthétique (D10)."""

from django.contrib.contenttypes.models import ContentType

from apps.documents.models import DocumentVersion, StatutGeneration

from ..models import Rapport

TYPE_RAPPORT_FINAL = "RAPPORT_FINAL"
TYPE_NOTE_SYNTHETIQUE = "NOTE_SYNTHETIQUE"


def derniere_version(rapport: Rapport, type_document: str) -> DocumentVersion | None:
    """Dernière version PRETE du document, produite pour la confirmation de validation courante.

    Une version générée pour un cycle de validation antérieur (autre confirmation, ou date
    antérieure à la validation en l'absence de confirmation) n'est jamais retenue.
    """
    versions = DocumentVersion.objects.filter(
        document__type_document=type_document,
        document__object_id=rapport.pk,
        document__content_type=ContentType.objects.get_for_model(Rapport),
        statut=StatutGeneration.PRETE,
        confirmation_id=rapport.confirmation_validation_id,
    )
    if rapport.valide_le is not None:
        versions = versions.filter(created_at__gte=rapport.valide_le)
    return versions.order_by("-numero_version").first()


def version_finale(rapport: Rapport) -> DocumentVersion | None:
    """Dernière version PRETE du `RAPPORT_FINAL` de la confirmation de validation courante."""
    return derniere_version(rapport, TYPE_RAPPORT_FINAL)


def version_note(rapport: Rapport) -> DocumentVersion | None:
    return derniere_version(rapport, TYPE_NOTE_SYNTHETIQUE)
