"""Journal des consultations et téléchargements (§6.10, §14) : ajout seul.

`journaliser_consultation` est l'interface partagée avec le lot 4 (même signature).
"""

from typing import Any, ClassVar, Literal

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from .exceptions import RegleMetierError
from .managers import AllObjectsManager, SoftDeleteManager, SoftDeleteQuerySet
from .models import BaseModel

_MSG = "Le journal des consultations est en ajout seul."


class ConsultationQuerySet(SoftDeleteQuerySet["Consultation"]):
    def update(self, **kwargs: Any) -> int:
        raise RegleMetierError(_MSG)

    def bulk_update(self, objs: Any, fields: Any, batch_size: int | None = None) -> int:
        raise RegleMetierError(_MSG)

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list["Consultation"]:
        if kwargs.get("update_conflicts"):
            raise RegleMetierError(_MSG)
        return super().bulk_create(objs, *args, **kwargs)


class ConsultationManager(SoftDeleteManager["Consultation"]):
    def get_queryset(self) -> ConsultationQuerySet:
        return ConsultationQuerySet(self.model, using=self._db).filter(deleted_at__isnull=True)


class ConsultationAllManager(AllObjectsManager["Consultation"]):
    def get_queryset(self) -> ConsultationQuerySet:
        return ConsultationQuerySet(self.model, using=self._db)


class Consultation(BaseModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.UUIDField("objet")
    par = models.ForeignKey(
        "users.User", on_delete=models.PROTECT, related_name="+", verbose_name="par"
    )
    le = models.DateTimeField("le", default=timezone.now)
    action = models.CharField(
        "action",
        max_length=16,
        choices=[("CONSULTATION", "Consultation"), ("TELECHARGEMENT", "Téléchargement")],
    )
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)

    objects: ClassVar[ConsultationManager] = ConsultationManager()
    all_objects: ClassVar[ConsultationAllManager] = ConsultationAllManager()  # noqa: DJ012

    class Meta:
        app_label = "core"
        verbose_name = "consultation"
        ordering = ("-le",)
        indexes = [models.Index(fields=["content_type", "object_id", "-le"], name="consult_objet")]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise RegleMetierError(_MSG)
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise RegleMetierError(_MSG)


def journaliser_consultation(
    objet: BaseModel,
    *,
    par: Any,
    action: Literal["CONSULTATION", "TELECHARGEMENT"],
    adresse_ip: str | None,
) -> None:
    Consultation.objects.create(
        content_type=ContentType.objects.get_for_model(objet),
        object_id=objet.pk,
        par=par,
        action=action,
        adresse_ip=adresse_ip,
    )
