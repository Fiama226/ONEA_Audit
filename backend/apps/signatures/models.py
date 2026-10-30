from typing import Any, ClassVar

from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q

from apps.core.exceptions import RegleMetierError
from apps.core.models import BaseModel
from apps.users.models import User

from .exceptions import ConfirmationImmuableError
from .managers import ConfirmationAllManager, ConfirmationManager


class TypeDocumentSignable(models.TextChoices):
    ORDRE_MISSION = "ORDRE_MISSION", "Ordre de mission"
    DECLARATION_INDEPENDANCE = "DECLARATION_INDEPENDANCE", "Déclaration d'indépendance"
    VALIDATION_RAPPORT = "VALIDATION_RAPPORT", "Validation du rapport"
    VALIDATION_REFERENTIEL = "VALIDATION_REFERENTIEL", "Validation du référentiel d'audit"
    REPONSE_CONSTAT = "REPONSE_CONSTAT", "Réponse à un constat"
    REPONSE_RAPPORT_PROVISOIRE = "REPONSE_RAPPORT_PROVISOIRE", "Réponse au rapport provisoire"
    ACCEPTATION_RISQUE = "ACCEPTATION_RISQUE", "Acceptation du risque"
    ENGAGEMENT_PLAN_ACTIONS = "ENGAGEMENT_PLAN_ACTIONS", "Engagement sur le plan d'actions"


class ModeSignature(models.TextChoices):
    CONFIRMATION = "CONFIRMATION", "Confirmation horodatée"


class ModeSignatureParametre(models.TextChoices):
    """Mode de signature exigé pour un type de document (D9, §15.1)."""

    CONFIRMATION = "CONFIRMATION", "Confirmation horodatée"
    SIGNATURE_ELECTRONIQUE = "SIGNATURE_ELECTRONIQUE", "Signature électronique (PAdES)"
    CONFIRMATION_ET_SIGNATURE = (
        "CONFIRMATION_ET_SIGNATURE",
        "Confirmation et signature électronique",
    )


TYPES_PARAMETRABLES: tuple[str, ...] = (
    TypeDocumentSignable.ORDRE_MISSION,
    TypeDocumentSignable.DECLARATION_INDEPENDANCE,
    TypeDocumentSignable.VALIDATION_RAPPORT,
)


class ParametreSignature(BaseModel):
    """Mode de signature d'un type de document, modifiable par l'administrateur.

    Absence de ligne = confirmation horodatée. Jamais supprimé ; chaque changement est tracé
    dans le journal d'audit.
    """

    type_document = models.CharField(
        "type de document",
        max_length=30,
        choices=[(t, TypeDocumentSignable(t).label) for t in TYPES_PARAMETRABLES],
    )
    mode = models.CharField(
        "mode",
        max_length=30,
        choices=ModeSignatureParametre,
        default=ModeSignatureParametre.CONFIRMATION,
    )

    class Meta:
        ordering = ["type_document"]
        constraints = [
            models.UniqueConstraint(
                fields=["type_document"],
                condition=Q(deleted_at__isnull=True),
                name="parametre_signature_un_actif",
            )
        ]

    def __str__(self) -> str:
        return f"{self.type_document} : {self.mode}"

    def soft_delete(self, by: User) -> None:
        raise RegleMetierError("Un paramètre de signature ne peut pas être supprimé.")


class Confirmation(BaseModel):
    """Confirmation horodatée et immuable d'un document par un utilisateur authentifié."""

    type_document = models.CharField(
        "type de document", max_length=30, choices=TypeDocumentSignable
    )
    mode = models.CharField(
        "mode", max_length=20, choices=ModeSignature, default=ModeSignature.CONFIRMATION
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.UUIDField("objet")
    signataire = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    confirme_le = models.DateTimeField("confirmé le")
    texte = models.TextField("texte confirmé")
    donnees = models.JSONField("données confirmées", encoder=DjangoJSONEncoder, blank=True)
    empreinte = models.CharField("empreinte SHA-256", max_length=64)
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)

    objects: ClassVar[ConfirmationManager] = ConfirmationManager()
    all_objects: ClassVar[ConfirmationAllManager] = ConfirmationAllManager()  # noqa: DJ012

    class Meta:
        ordering = ["-confirme_le"]
        indexes = [
            models.Index(
                fields=["content_type", "object_id", "type_document", "-confirme_le"],
                name="confirmation_objet_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(empreinte__regex=r"^[0-9a-f]{64}$"),
                name="confirmation_empreinte_sha256",
            )
        ]

    def __str__(self) -> str:
        return f"{self.type_document} {self.object_id} ({self.confirme_le:%d/%m/%Y})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding or kwargs.get("force_update") or kwargs.get("update_fields"):
            raise ConfirmationImmuableError
        super().save(*args, **kwargs)

    def soft_delete(self, by: User) -> None:
        raise ConfirmationImmuableError
