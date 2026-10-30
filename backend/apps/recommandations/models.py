"""Plan d'actions (étape XVI) : actions correctives, acceptations du risque, engagements."""

from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q

from apps.constats.models import Recommandation
from apps.missions.gardes import exiger_etape_ouverte
from apps.missions.models import Mission, MissionEnfantModel

from .exceptions import EngagementAjoutSeulError
from .managers import (
    AcceptationAllManager,
    AcceptationManager,
    ActionAllManager,
    ActionManager,
    EngagementAllManager,
    EngagementManager,
)

ETAPE_PLAN_ACTIONS = 16


class StatutAction(models.TextChoices):
    A_LANCER = "A_LANCER", "À lancer"
    EN_COURS = "EN_COURS", "En cours"
    REALISEE = "REALISEE", "Réalisée"
    ABANDONNEE = "ABANDONNEE", "Abandonnée (justifiée)"


def _utilisateur_fk(**kwargs: Any) -> models.ForeignKey[Any]:
    return models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", **kwargs
    )


def _mission_fk(related_name: str) -> models.ForeignKey[Mission]:
    return models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name=related_name, verbose_name="mission"
    )


class Action(MissionEnfantModel):
    """Action corrective rattachée à une recommandation (D8)."""

    mission = _mission_fk("actions")
    recommandation = models.ForeignKey(
        Recommandation,
        verbose_name="recommandation",
        on_delete=models.PROTECT,
        related_name="actions",
    )
    reference = models.CharField("référence", max_length=12)
    numero = models.PositiveIntegerField("numéro")
    libelle = models.TextField("mesure corrective")
    responsable = _utilisateur_fk(verbose_name="responsable", null=True, blank=True)
    echeance = models.DateField("échéance", null=True, blank=True)
    indicateur = models.TextField("indicateur de mise en œuvre", blank=True)
    moyens = models.TextField("moyens (ressources et budget)", blank=True)
    ordre = models.PositiveIntegerField("ordre", default=0)
    statut = models.CharField(
        "statut", max_length=12, choices=StatutAction.choices, default=StatutAction.A_LANCER
    )
    proposee_par = _utilisateur_fk(verbose_name="proposée par")

    objects: ClassVar[ActionManager[Any]] = ActionManager()
    all_objects: ClassVar[ActionAllManager[Any]] = ActionAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "action corrective"
        verbose_name_plural = "actions correctives"
        ordering = ("numero",)
        constraints = [
            # Jamais réattribuées : sans condition, supprimées incluses.
            models.UniqueConstraint(
                fields=["mission", "reference"], name="action_reference_unique"
            ),
            models.UniqueConstraint(fields=["mission", "numero"], name="action_numero_unique"),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.libelle[:40]}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        from . import gardes

        avant = None if self._state.adding else Action.all_objects.filter(pk=self.pk).first()
        update_fields = kwargs.get("update_fields")
        gardes.controler_action(
            avant, self, touches=None if update_fields is None else set(update_fields)
        )
        super().save(*args, **kwargs)


class AcceptationRisque(MissionEnfantModel):
    """Risque accepté par la direction concernée, sans plan d'actions (D8)."""

    mission = _mission_fk("acceptations_risque")
    recommandation = models.ForeignKey(
        Recommandation,
        verbose_name="recommandation",
        on_delete=models.PROTECT,
        related_name="acceptations",
    )
    justification = models.TextField("justification")
    auteur = _utilisateur_fk(verbose_name="auteur")
    confirmation = models.ForeignKey(
        "signatures.Confirmation",
        verbose_name="confirmation",
        on_delete=models.PROTECT,
        related_name="+",
    )

    objects: ClassVar[AcceptationManager[Any]] = AcceptationManager()
    all_objects: ClassVar[AcceptationAllManager[Any]] = AcceptationAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "acceptation du risque"
        verbose_name_plural = "acceptations du risque"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["recommandation"],
                condition=Q(deleted_at__isnull=True),
                name="acceptation_active_unique",
            ),
            models.CheckConstraint(
                condition=~Q(justification=""), name="acceptation_justification_non_vide"
            ),
        ]

    def __str__(self) -> str:
        return f"Acceptation ({self.recommandation_id})"

    def exiger_travaux_ouverts(self) -> None:
        exiger_etape_ouverte(self.mission_id, ETAPE_PLAN_ACTIONS)

    def save(self, *args: Any, **kwargs: Any) -> None:
        from . import gardes

        avant = (
            None if self._state.adding else AcceptationRisque.all_objects.filter(pk=self.pk).first()
        )
        update_fields = kwargs.get("update_fields")
        gardes.controler_acceptation(
            avant, self, touches=None if update_fields is None else set(update_fields)
        )
        super().save(*args, **kwargs)


class EngagementPlanActions(MissionEnfantModel):
    """Engagement d'un responsable sur ses actions : ajout seul."""

    mission = _mission_fk("engagements_plan_actions")
    auteur = _utilisateur_fk(verbose_name="auteur")
    confirmation = models.ForeignKey(
        "signatures.Confirmation",
        verbose_name="confirmation",
        on_delete=models.PROTECT,
        related_name="+",
    )
    empreinte_actions = models.CharField("empreinte SHA-256 des actions", max_length=64)

    objects: ClassVar[EngagementManager[Any]] = EngagementManager()
    all_objects: ClassVar[EngagementAllManager[Any]] = EngagementAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "engagement sur le plan d'actions"
        verbose_name_plural = "engagements sur le plan d'actions"
        ordering = ("created_at",)

    def __str__(self) -> str:
        return f"Engagement ({self.auteur_id})"

    def exiger_travaux_ouverts(self) -> None:
        exiger_etape_ouverte(self.mission_id, ETAPE_PLAN_ACTIONS)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise EngagementAjoutSeulError
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise EngagementAjoutSeulError
