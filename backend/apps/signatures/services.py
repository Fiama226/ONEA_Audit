"""Confirmation horodatée (D10) : création, empreinte canonique et vérification."""

import hashlib
import json
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.core.models import BaseModel
from apps.core.services import enregistrer
from apps.users.models import User

from .models import Confirmation


def empreinte(texte: str, donnees: dict[str, Any]) -> str:
    """SHA-256 de `{"texte", "donnees"}` sérialisé de façon canonique."""
    canonique = json.dumps(
        {"texte": texte, "donnees": donnees},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        cls=DjangoJSONEncoder,
    )
    return hashlib.sha256(canonique.encode("utf-8")).hexdigest()


def confirmer(
    *,
    type_document: str,
    objet: BaseModel,
    texte: str,
    donnees: dict[str, Any],
    by: User,
    adresse_ip: str | None = None,
) -> Confirmation:
    confirmation = Confirmation(
        type_document=type_document,
        content_type=ContentType.objects.get_for_model(objet),
        object_id=objet.pk,
        signataire=by,
        confirme_le=timezone.now(),
        texte=texte,
        donnees=json.loads(json.dumps(donnees, cls=DjangoJSONEncoder)),
        empreinte=empreinte(texte, donnees),
        adresse_ip=adresse_ip,
    )
    enregistrer(confirmation, by=by, creation=True)
    return confirmation


def verifier(confirmation: Confirmation) -> bool:
    """Recalcule l'empreinte depuis la base ; faux si texte ou données ont été altérés."""
    texte, donnees, attendue = Confirmation.all_objects.values_list(
        "texte", "donnees", "empreinte"
    ).get(pk=confirmation.pk)
    return bool(empreinte(texte, donnees) == attendue)


def derniere_confirmation(objet: BaseModel, type_document: str) -> Confirmation | None:
    return (
        Confirmation.objects.filter(
            content_type=ContentType.objects.get_for_model(objet),
            object_id=objet.pk,
            type_document=type_document,
        )
        .order_by("-confirme_le")
        .first()
    )
