from django.conf import settings
from django.db import models
from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.lookups import GreaterThanOrEqual
from django_fsm import FSMField

from apps.core.models import BaseModel

from .validators import valider_code_direction, valider_code_processus, valider_code_risque


class TypeEntite(models.TextChoices):
    DIRECTION = "DIRECTION", "Direction"
    DEPARTEMENT = "DEPARTEMENT", "Département"


class FamilleProcessus(models.TextChoices):
    PILOTAGE = "PILOTAGE", "Pilotage"
    REALISATION = "REALISATION", "Réalisation"
    SUPPORT = "SUPPORT", "Support"


class NatureObjet(models.TextChoices):
    DOMAINE = "DOMAINE", "Domaine"
    OPERATION = "OPERATION", "Opération"


class StatutCartographie(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    VALIDEE = "VALIDEE", "Validée"


class NiveauRisque(models.TextChoices):
    FAIBLE = "FAIBLE", "Faible"
    MOYEN = "MOYEN", "Moyen"
    ELEVE = "ELEVE", "Élevé"


class ReponseRisque(models.TextChoices):
    TRAITER = "TRAITER", "Traiter"
    TRANSFERER = "TRANSFERER", "Transférer"
    TERMINER = "TERMINER", "Terminer"
    TOLERER = "TOLERER", "Tolérer"


class PrioriteRisque(models.IntegerChoices):
    PRIORITAIRE = 1, "Prioritaire"
    AMELIORATION = 2, "Amélioration"
    OBSERVATION = 3, "Observation"


class Direction(BaseModel):
    code = models.CharField("code", max_length=16, validators=[valider_code_direction])
    libelle = models.CharField("libellé", max_length=200)
    type = models.CharField("type", max_length=16, choices=TypeEntite.choices)
    parent = models.ForeignKey(
        "self",
        verbose_name="direction de rattachement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="departements",
    )

    class Meta:
        verbose_name = "direction"
        verbose_name_plural = "directions"
        ordering = ("code",)
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(deleted_at__isnull=True),
                name="direction_code_unique_actif",
            ),
            models.CheckConstraint(
                condition=(
                    Q(type=TypeEntite.DIRECTION, parent__isnull=True)
                    | Q(type=TypeEntite.DEPARTEMENT, parent__isnull=False)
                ),
                name="direction_parent_coherent",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.libelle}"


class Processus(BaseModel):
    code = models.CharField("code", max_length=5, validators=[valider_code_processus])
    libelle = models.CharField("libellé", max_length=200)
    famille = models.CharField("famille", max_length=16, choices=FamilleProcessus.choices)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)
    directions = models.ManyToManyField(
        Direction,
        verbose_name="directions",
        blank=True,
        related_name="processus",
    )

    class Meta:
        verbose_name = "processus"
        verbose_name_plural = "processus"
        ordering = ("ordre", "code")
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(deleted_at__isnull=True),
                name="processus_code_unique_actif",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} - {self.libelle}"


class ObjetAuditable(BaseModel):
    processus = models.ForeignKey(
        Processus,
        verbose_name="processus",
        on_delete=models.PROTECT,
        related_name="objets",
    )
    parent = models.ForeignKey(
        "self",
        verbose_name="domaine parent",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="operations",
    )
    nature = models.CharField("nature", max_length=16, choices=NatureObjet.choices)
    libelle = models.CharField("libellé", max_length=300)
    description = models.TextField("description", blank=True)
    ordre = models.PositiveSmallIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "objet auditable"
        verbose_name_plural = "objets auditables"
        ordering = ("ordre", "libelle")
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(nature=NatureObjet.DOMAINE, parent__isnull=True)
                    | Q(nature=NatureObjet.OPERATION, parent__isnull=False)
                ),
                name="objet_parent_coherent",
            ),
        ]

    def __str__(self) -> str:
        return self.libelle


class CartographieVersion(BaseModel):
    annee = models.PositiveSmallIntegerField("année")
    libelle = models.CharField("libellé", max_length=200)
    commentaire = models.TextField("commentaire", blank=True)
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        default=StatutCartographie.BROUILLON,
        choices=StatutCartographie.choices,
        protected=False,
    )
    source = models.ForeignKey(
        "self",
        verbose_name="cartographie source",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    validee_le = models.DateTimeField("validée le", null=True, blank=True)
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validée par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        verbose_name = "cartographie des risques"
        verbose_name_plural = "cartographies des risques"
        ordering = ("-annee",)
        constraints = [
            models.CheckConstraint(
                condition=Q(annee__gte=2000, annee__lte=2100),
                name="cartographie_annee_2000_2100",
            ),
            models.UniqueConstraint(
                fields=["annee"],
                condition=Q(deleted_at__isnull=True),
                name="cartographie_annee_unique_actif",
            ),
        ]

    def __str__(self) -> str:
        return f"Cartographie {self.annee}"


_PRODUIT = F("probabilite") * F("impact")


class Risque(BaseModel):
    version = models.ForeignKey(
        CartographieVersion,
        verbose_name="cartographie",
        on_delete=models.PROTECT,
        related_name="risques",
    )
    processus = models.ForeignKey(
        Processus,
        verbose_name="processus",
        on_delete=models.PROTECT,
        related_name="risques",
    )
    objet_auditable = models.ForeignKey(
        ObjetAuditable,
        verbose_name="objet auditable",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="risques",
    )
    numero = models.PositiveIntegerField("numéro")
    rang = models.PositiveIntegerField("rang")
    code = models.CharField("code", max_length=32, validators=[valider_code_risque])
    libelle = models.CharField("libellé", max_length=500)
    description = models.TextField("description", blank=True)
    probabilite = models.PositiveSmallIntegerField("probabilité")
    impact = models.PositiveSmallIntegerField("impact")
    score = models.GeneratedField(
        expression=_PRODUIT,
        output_field=models.PositiveSmallIntegerField(),
        db_persist=True,
        verbose_name="score",
    )
    niveau = models.GeneratedField(
        expression=Case(
            When(GreaterThanOrEqual(_PRODUIT, Value(15)), then=Value(NiveauRisque.ELEVE)),
            When(GreaterThanOrEqual(_PRODUIT, Value(8)), then=Value(NiveauRisque.MOYEN)),
            default=Value(NiveauRisque.FAIBLE),
            output_field=CharField(max_length=8),
        ),
        output_field=CharField(max_length=8),
        db_persist=True,
        verbose_name="niveau",
    )
    vulnerabilite = models.TextField("vulnérabilité", blank=True)
    reponse = models.CharField(
        "réponse au risque", max_length=16, choices=ReponseRisque.choices, blank=True
    )
    priorite = models.PositiveSmallIntegerField("priorité", choices=PrioriteRisque.choices)
    objectif_controle = models.TextField("objectif de contrôle", blank=True)
    dispositif_controle = models.TextField("dispositif de contrôle interne", blank=True)

    class Meta:
        verbose_name = "risque"
        verbose_name_plural = "risques"
        ordering = ("numero",)
        constraints = [
            models.CheckConstraint(condition=Q(rang__gte=1), name="risque_rang_positif"),
            models.CheckConstraint(
                condition=Q(probabilite__gte=1, probabilite__lte=5),
                name="risque_probabilite_1_5",
            ),
            models.CheckConstraint(
                condition=Q(impact__gte=1, impact__lte=5), name="risque_impact_1_5"
            ),
            models.CheckConstraint(
                condition=Q(priorite__gte=1, priorite__lte=3), name="risque_priorite_1_3"
            ),
            models.UniqueConstraint(
                fields=["version", "code"],
                condition=Q(deleted_at__isnull=True),
                name="risque_code_unique_par_version",
            ),
            models.UniqueConstraint(
                fields=["version", "numero"],
                condition=Q(deleted_at__isnull=True),
                name="risque_numero_unique_par_version",
            ),
            models.UniqueConstraint(
                fields=["version", "processus", "rang"],
                condition=Q(deleted_at__isnull=True),
                name="risque_rang_unique_par_processus",
            ),
        ]
        indexes = [
            models.Index(fields=["version", "probabilite", "impact"], name="risque_matrice_idx"),
        ]

    def __str__(self) -> str:
        return self.code
