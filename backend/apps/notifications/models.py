from typing import Any, ClassVar

from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q

from apps.core.models import BaseModel
from apps.users.models import User

from .exceptions import NotificationImmuableError
from .managers import NotificationAllManager, NotificationManager, verifier_champs


class TypeNotification(models.TextChoices):
    SUIVI_OUVERT = "SUIVI_OUVERT", "Suivi ouvert"
    ACTION_DECLAREE = "ACTION_DECLAREE", "Action déclarée"
    ACTION_VERIFIEE = "ACTION_VERIFIEE", "Action vérifiée"
    ACTION_REJETEE = "ACTION_REJETEE", "Action rejetée"
    ACTION_CLOTUREE = "ACTION_CLOTUREE", "Action clôturée"
    ABANDON_PROPOSE = "ABANDON_PROPOSE", "Abandon proposé"
    ABANDON_DECIDE = "ABANDON_DECIDE", "Abandon décidé"
    REPORT_DEMANDE = "REPORT_DEMANDE", "Report demandé"
    REPORT_DECIDE = "REPORT_DECIDE", "Report décidé"
    RESPONSABLE_CHANGE = "RESPONSABLE_CHANGE", "Responsable changé"
    RELANCE = "RELANCE", "Relance"
    MISSION_A_CLOTURER = "MISSION_A_CLOTURER", "Mission à clôturer"
    MISSION_CLOTUREE = "MISSION_CLOTUREE", "Mission clôturée"
    ACTION_IGNOREE = "ACTION_IGNOREE", "Action ignorée"


class Notification(BaseModel):
    """Notification dans la plateforme, lisible par son seul destinataire."""

    destinataire = models.ForeignKey(User, on_delete=models.PROTECT, related_name="notifications")
    type = models.CharField("type", max_length=30, choices=TypeNotification)
    titre = models.CharField("titre", max_length=200)
    message = models.CharField("message", max_length=1000)
    lien = models.CharField("lien", max_length=300)
    content_type = models.ForeignKey(
        ContentType, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    object_id = models.UUIDField("objet", null=True, blank=True)
    lue_le = models.DateTimeField("lue le", null=True, blank=True)
    cle = models.CharField("clé de dédoublonnage", max_length=120, blank=True, default="")

    objects: ClassVar[NotificationManager] = NotificationManager()
    all_objects: ClassVar[NotificationAllManager] = NotificationAllManager()  # noqa: DJ012

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["destinataire", "lue_le", "created_at"], name="notification_boite_idx"
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["destinataire", "cle"],
                condition=~Q(cle="") & Q(deleted_at__isnull=True),
                name="notification_cle_unique",
            ),
            # Lien interne : "/chemin", jamais "//hote" ni "/\hote" (redirection externe).
            models.CheckConstraint(
                condition=Q(lien__regex=r"^/([^/\\]|$)"), name="notification_lien_relatif"
            ),
            models.CheckConstraint(
                condition=Q(content_type__isnull=True, object_id__isnull=True)
                | Q(content_type__isnull=False, object_id__isnull=False),
                name="notification_objet_coherent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type} -> {self.destinataire_id}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            champs = kwargs.get("update_fields")
            if champs is None:
                raise NotificationImmuableError
            verifier_champs(champs)
        super().save(*args, **kwargs)
