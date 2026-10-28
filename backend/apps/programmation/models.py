from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django_fsm import FSMField, transition

from apps.core.exceptions import RegleMetierError
from apps.core.models import BaseModel

from .exceptions import ProgrammeFigeError
from .managers import (
    LigneProgrammeAllManager,
    LigneProgrammeManager,
    ProgrammeAllManager,
    ProgrammeManager,
    champs_execution_seuls,
)

# Champs d'une ligne modifiables même dans un programme validé (suivi d'exécution).
# Vide pour l'instant : aucune donnée d'exécution n'existe encore (décision D8).
CHAMPS_EXECUTION: frozenset[str] = frozenset()


class StatutProgramme(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    VALIDE = "VALIDE", "Validé"


class TypeIntervention(models.TextChoices):
    ASSURANCE = "ASSURANCE", "Assurance"
    CONSEIL = "CONSEIL", "Conseil"


class ProgrammeAnnuel(BaseModel):
    annee = models.PositiveSmallIntegerField("année")
    libelle = models.CharField("libellé", max_length=200)
    commentaire = models.TextField("commentaire", blank=True)
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        default=StatutProgramme.BROUILLON,
        choices=StatutProgramme.choices,
        protected=False,
    )
    valide_le = models.DateTimeField("validé le", null=True, blank=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validé par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    objects: ClassVar[ProgrammeManager] = ProgrammeManager()
    all_objects: ClassVar[ProgrammeAllManager] = ProgrammeAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "programme annuel d'audit"
        verbose_name_plural = "programmes annuels d'audit"
        ordering = ("-annee",)
        constraints = [
            models.CheckConstraint(
                condition=Q(annee__gte=2000, annee__lte=2100),
                name="programme_annee_2000_2100",
            ),
            models.UniqueConstraint(
                fields=["annee"],
                condition=Q(deleted_at__isnull=True),
                name="programme_annee_unique_actif",
            ),
            models.CheckConstraint(
                condition=(
                    ~Q(statut=StatutProgramme.VALIDE)
                    | Q(valide_le__isnull=False, valide_par__isnull=False)
                ),
                name="programme_valide_signe",
            ),
        ]

    def __str__(self) -> str:
        return f"Programme annuel {self.annee}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Le contrôle porte sur la ligne EN BASE : la sauvegarde qui valide passe
        # (la base dit encore BROUILLON), toute sauvegarde suivante est refusée.
        if not self._state.adding:
            en_base = (
                ProgrammeAnnuel.all_objects.filter(pk=self.pk)
                .values_list("statut", "annee")
                .first()
            )
            if en_base is not None and en_base[0] == StatutProgramme.VALIDE:
                raise ProgrammeFigeError(en_base[1])
        super().save(*args, **kwargs)

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=StatutProgramme.BROUILLON,
        target=StatutProgramme.VALIDE,
    )
    def valider(self) -> None:
        """Passage BROUILLON -> VALIDE ; appelée uniquement par le service."""


class LigneProgramme(BaseModel):
    programme = models.ForeignKey(
        ProgrammeAnnuel,
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="lignes",
    )
    numero = models.PositiveSmallIntegerField("numéro")
    titre = models.CharField("titre", max_length=300)
    type = models.CharField("type d'intervention", max_length=20, choices=TypeIntervention.choices)
    processus = models.ForeignKey(
        "referentiel.Processus",
        verbose_name="processus",
        on_delete=models.PROTECT,
        related_name="lignes_programme",
    )
    objet_auditable = models.ForeignKey(
        "referentiel.ObjetAuditable",
        verbose_name="objet auditable",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="lignes_programme",
    )
    entites = models.ManyToManyField(
        "referentiel.Direction",
        verbose_name="entités concernées",
        blank=True,
        related_name="lignes_programme",
    )
    debut_prevu = models.DateField("début prévu")
    fin_prevue = models.DateField("fin prévue")
    charge_prevue_jours = models.DecimalField(
        "charge prévue (jours)", max_digits=6, decimal_places=1, null=True, blank=True
    )
    justification = models.TextField("justification", blank=True)

    objects: ClassVar[LigneProgrammeManager] = LigneProgrammeManager()
    all_objects: ClassVar[LigneProgrammeAllManager] = LigneProgrammeAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "ligne de programme"
        verbose_name_plural = "lignes de programme"
        ordering = ("debut_prevu", "numero")
        indexes = [
            models.Index(fields=["programme", "debut_prevu"], name="ligne_programme_debut_idx")
        ]
        constraints = [
            models.UniqueConstraint(fields=["programme", "numero"], name="ligne_numero_unique"),
            models.CheckConstraint(condition=Q(numero__gte=1), name="ligne_numero_positif"),
            models.CheckConstraint(
                condition=Q(charge_prevue_jours__isnull=True) | Q(charge_prevue_jours__gte=0),
                name="ligne_charge_positive",
            ),
            models.CheckConstraint(
                condition=Q(fin_prevue__gte=models.F("debut_prevu")),
                name="ligne_periode_ordonnee",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.numero}. {self.titre}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Contrôle sur les lignes EN BASE : le programme actuel de la ligne (déplacement
        # impossible hors d'un programme validé) et le programme visé.
        en_base = (
            LigneProgramme.all_objects.filter(pk=self.pk)
            .values_list("programme_id", "programme__statut", "programme__annee")
            .first()
        )
        champs = kwargs.get("update_fields")
        execution_seule = champs is not None and champs_execution_seuls(champs)
        if en_base is not None and en_base[1] == StatutProgramme.VALIDE and not execution_seule:
            raise ProgrammeFigeError(en_base[2])
        if en_base is None or en_base[0] != self.programme_id:
            cible = (
                ProgrammeAnnuel.all_objects.filter(pk=self.programme_id)
                .values_list("statut", "annee")
                .first()
            )
            if cible is not None and cible[0] == StatutProgramme.VALIDE:
                raise ProgrammeFigeError(cible[1])
            if en_base is not None:
                raise RegleMetierError(
                    "Une ligne ne peut pas changer de programme.",
                    {"programme": ["Une ligne ne peut pas changer de programme."]},
                )
        super().save(*args, **kwargs)


@receiver(m2m_changed, sender=LigneProgramme.entites.through)
def _garder_entites(
    sender: Any, instance: Any, action: str, reverse: bool, pk_set: Any, **kwargs: Any
) -> None:
    """Refuse toute modification des entités d'une ligne d'un programme validé."""
    if action not in {"pre_add", "pre_remove", "pre_clear"} or "entites" in CHAMPS_EXECUTION:
        return
    if not reverse:
        lignes = LigneProgramme.all_objects.filter(pk=instance.pk)
    elif action == "pre_clear":  # direction.lignes_programme.clear() : instance = Direction
        lignes = LigneProgramme.all_objects.filter(entites=instance)
    else:
        lignes = LigneProgramme.all_objects.filter(pk__in=pk_set or [])
    annee = (
        ProgrammeAnnuel.all_objects.filter(
            statut=StatutProgramme.VALIDE, pk__in=lignes.order_by().values("programme_id")
        )
        .values_list("annee", flat=True)
        .first()
    )
    if annee is not None:
        raise ProgrammeFigeError(annee)
