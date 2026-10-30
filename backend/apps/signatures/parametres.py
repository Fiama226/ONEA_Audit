"""Mode de signature par type de document (D9, §15.1)."""

from dataclasses import dataclass

from django.db import transaction
from rest_framework.exceptions import PermissionDenied

from apps.core.handlers import FORBIDDEN
from apps.core.services import enregistrer, refuser
from apps.users.models import Role, User

from .electronique import signataire_electronique
from .models import TYPES_PARAMETRABLES, ModeSignatureParametre, ParametreSignature

MODES_ELECTRONIQUES = (
    ModeSignatureParametre.SIGNATURE_ELECTRONIQUE,
    ModeSignatureParametre.CONFIRMATION_ET_SIGNATURE,
)


@dataclass(frozen=True)
class Exigences:
    confirmation: bool
    electronique: bool


def mode_requis(type_document: str) -> ModeSignatureParametre:
    """CONFIRMATION sans ligne, ou hors types paramétrables."""
    if type_document not in TYPES_PARAMETRABLES:
        return ModeSignatureParametre.CONFIRMATION
    ligne = ParametreSignature.objects.filter(type_document=type_document).first()
    return ModeSignatureParametre(ligne.mode) if ligne else ModeSignatureParametre.CONFIRMATION


def exigences(type_document: str) -> Exigences:
    mode = mode_requis(type_document)
    return Exigences(
        confirmation=mode != ModeSignatureParametre.SIGNATURE_ELECTRONIQUE,
        electronique=mode in MODES_ELECTRONIQUES,
    )


def modes_disponibles() -> list[ModeSignatureParametre]:
    """Les modes électroniques ne sont proposés que si un signataire est enregistré."""
    if signataire_electronique() is None:
        return [ModeSignatureParametre.CONFIRMATION]
    return list(ModeSignatureParametre)


def modifier_mode(type_document: str, *, mode: str, by: User) -> ParametreSignature:
    if not by.has_role(Role.ADMIN):
        raise PermissionDenied(FORBIDDEN)
    if type_document not in TYPES_PARAMETRABLES:
        raise refuser("Ce type de document n'a pas de mode de signature paramétrable.")
    if mode not in ModeSignatureParametre.values:
        raise refuser("Données invalides.", mode="Mode de signature inconnu.")
    if mode in MODES_ELECTRONIQUES and signataire_electronique() is None:
        raise refuser("La signature électronique n'est pas encore disponible sur cette plateforme.")
    with transaction.atomic():
        ligne = (
            ParametreSignature.objects.select_for_update().filter(type_document=type_document)
        ).first()
        if ligne is None:
            # Création au mode par défaut, puis changement : l'audit garde un « avant ».
            ligne = ParametreSignature(type_document=type_document)
            enregistrer(ligne, by=by, creation=True)
        if ligne.mode != mode:
            ligne.mode = mode
            enregistrer(ligne, by=by)
    return ligne
