from typing import Any, ClassVar

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Case, CharField, F, Q, Value, When
from django.db.models.lookups import GreaterThanOrEqual
from django.utils import timezone
from django_fsm import FSMField, transition

from apps.accomplissement.models import FicheDeTest
from apps.core.models import BaseModel
from apps.missions.models import Mission, MissionEnfantModel, RisqueMission
from apps.referentiel.models import Direction, NiveauRisque, Processus
from apps.referentiel.scoring import SEUIL_ELEVE, SEUIL_MOYEN

from .exceptions import MSG_EVENEMENT_AJOUT_SEUL, ReponseAjoutSeulError
from .managers import (
    JournalConstatAllManager,
    JournalConstatManager,
    ReponseAllManager,
    ReponseManager,
    SansUpsertAllManager,
    SansUpsertManager,
)


class StatutConstat(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    SOUMIS = "SOUMIS", "Soumis"
    VALIDE = "VALIDE", "Validé"
    RENVOYE = "RENVOYE", "Renvoyé"


class CategorieCause(models.TextChoices):
    MAIN_OEUVRE = "MAIN_OEUVRE", "Main-d'œuvre"
    METHODES = "METHODES", "Méthodes"
    MATERIEL = "MATERIEL", "Matériel"
    MILIEU = "MILIEU", "Milieu"
    MATIERE = "MATIERE", "Matière"
    MANAGEMENT = "MANAGEMENT", "Management"
    MOYENS_FINANCIERS = "MOYENS_FINANCIERS", "Moyens financiers"


class PrioriteRecommandation(models.TextChoices):
    HAUTE = "HAUTE", "Haute"
    MOYENNE = "MOYENNE", "Moyenne"
    FAIBLE = "FAIBLE", "Faible"


class PositionAudite(models.TextChoices):
    ACCORD = "ACCORD", "Accord"
    DESACCORD = "DESACCORD", "Désaccord"


class TypeEvenementConstat(models.TextChoices):
    SOUMIS = "SOUMIS", "Soumis"
    VALIDE = "VALIDE", "Validé"
    RENVOYE = "RENVOYE", "Renvoyé"
    ROUVERT = "ROUVERT", "Rouvert"


def _mission_fk(related_name: str) -> models.ForeignKey[Mission]:
    return models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name=related_name, verbose_name="mission"
    )


_PRODUIT = F("probabilite") * F("impact")
_EVALUE = Q(probabilite__isnull=False, impact__isnull=False)


class Constat(MissionEnfantModel):
    """Constat (fiche d'observation, D10) : gelé dès qu'il est validé ou que XIV est close."""

    mission = _mission_fk("constats")
    reference = models.CharField("référence", max_length=12)
    numero = models.PositiveIntegerField("numéro")
    titre = models.CharField("titre", max_length=300, blank=True)
    fiches = models.ManyToManyField(
        FicheDeTest, verbose_name="fiches de test", related_name="constats", blank=True
    )
    entite = models.ForeignKey(
        Direction, verbose_name="entité", on_delete=models.PROTECT, related_name="+"
    )
    processus = models.ForeignKey(
        Processus, verbose_name="processus", on_delete=models.PROTECT, related_name="+"
    )
    risque_mission = models.ForeignKey(
        RisqueMission,
        verbose_name="risque de la mission",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    fait_constate = models.TextField("fait constaté", blank=True)
    referentiel = models.TextField("référentiel (critère)", blank=True)
    consequence = models.TextField("conséquence", blank=True)
    conclusion = models.TextField("conclusion", blank=True)
    probabilite = models.PositiveSmallIntegerField("probabilité", null=True, blank=True)
    impact = models.PositiveSmallIntegerField("impact", null=True, blank=True)
    score = models.GeneratedField(
        expression=_PRODUIT,
        output_field=models.PositiveSmallIntegerField(null=True),
        db_persist=True,
        verbose_name="score",
    )
    # Mêmes seuils que `RisqueMission` ; nul tant que P et I ne sont pas saisis.
    niveau = models.GeneratedField(
        expression=Case(
            When(~_EVALUE, then=Value(None, output_field=CharField(max_length=8))),
            When(GreaterThanOrEqual(_PRODUIT, Value(SEUIL_ELEVE)), then=Value(NiveauRisque.ELEVE)),
            When(GreaterThanOrEqual(_PRODUIT, Value(SEUIL_MOYEN)), then=Value(NiveauRisque.MOYEN)),
            default=Value(NiveauRisque.FAIBLE),
            output_field=CharField(max_length=8),
        ),
        output_field=CharField(max_length=8, null=True, choices=NiveauRisque.choices),
        db_persist=True,
        verbose_name="niveau",
    )
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        max_length=12,
        choices=StatutConstat.choices,
        default=StatutConstat.BROUILLON,
        protected=False,
    )
    cycle = models.PositiveSmallIntegerField("cycle de soumission", default=0)
    soumis_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="soumis par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    soumis_le = models.DateTimeField("soumis le", null=True, blank=True)
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validé par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    validee_le = models.DateTimeField("validé le", null=True, blank=True)
    motif_renvoi = models.TextField("motif du renvoi", blank=True)
    version_soumise = models.JSONField(
        "version soumise", null=True, blank=True, encoder=DjangoJSONEncoder
    )
    empreinte_soumise = models.CharField("empreinte SHA-256 soumise", max_length=64, blank=True)

    _rouverture: bool = False

    objects: ClassVar[SansUpsertManager[Any]] = SansUpsertManager()
    all_objects: ClassVar[SansUpsertAllManager[Any]] = SansUpsertAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "constat"
        verbose_name_plural = "constats"
        ordering = ("numero",)
        constraints = [
            # Jamais réattribués : sans condition, supprimés inclus.
            models.UniqueConstraint(
                fields=["mission", "reference"], name="constat_reference_unique"
            ),
            models.UniqueConstraint(fields=["mission", "numero"], name="constat_numero_unique"),
            models.CheckConstraint(
                condition=Q(probabilite__isnull=True) | Q(probabilite__gte=1, probabilite__lte=5),
                name="constat_probabilite_1_5",
            ),
            models.CheckConstraint(
                condition=Q(impact__isnull=True) | Q(impact__gte=1, impact__lte=5),
                name="constat_impact_1_5",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reference} {self.titre}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_constat(self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._rouverture or self._state.adding:
            super().save(*args, **kwargs)
            return
        from . import gardes

        try:
            with gardes.reouverture(self.pk):
                super().save(*args, **kwargs)
        finally:
            self._rouverture = False

    # Transitions de D10 : appelées par les services (qui posent aussi auteurs, dates, motifs,
    # cycle, version figée et événement). `protected=False` : le champ reste modifiable.

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutConstat.BROUILLON, StatutConstat.RENVOYE],
        target=StatutConstat.SOUMIS,
    )
    def soumettre(self) -> None:
        """BROUILLON ou RENVOYE -> SOUMIS."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutConstat.SOUMIS, target=StatutConstat.VALIDE
    )
    def valider(self) -> None:
        """SOUMIS -> VALIDE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutConstat.SOUMIS, target=StatutConstat.RENVOYE
    )
    def renvoyer(self) -> None:
        """SOUMIS -> RENVOYE (motif posé par le service)."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutConstat.VALIDE, target=StatutConstat.BROUILLON
    )
    def rouvrir(self) -> None:
        """VALIDE -> BROUILLON ; la sauvegarde qui suit est la seule permise sur un VALIDE."""
        self._rouverture = True


class CauseConstat(MissionEnfantModel):
    """Cause d'un constat (méthode des 7M)."""

    mission = _mission_fk("causes_constat")
    constat = models.ForeignKey(
        Constat, verbose_name="constat", on_delete=models.PROTECT, related_name="causes"
    )
    categorie = models.CharField("catégorie", max_length=20, choices=CategorieCause.choices)
    description = models.TextField("description")
    ordre = models.PositiveIntegerField("ordre", default=0)

    objects: ClassVar[SansUpsertManager[Any]] = SansUpsertManager()
    all_objects: ClassVar[SansUpsertAllManager[Any]] = SansUpsertAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "cause de constat"
        verbose_name_plural = "causes de constat"
        ordering = ("ordre", "created_at")

    def __str__(self) -> str:
        return f"{self.get_categorie_display()} : {self.description[:40]}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_dependant(self)


class Recommandation(MissionEnfantModel):
    """Recommandation d'un constat ; les lots 7 et 8 y rattachent leurs actions (D2)."""

    mission = _mission_fk("recommandations")
    constat = models.ForeignKey(
        Constat, verbose_name="constat", on_delete=models.PROTECT, related_name="recommandations"
    )
    libelle = models.TextField("libellé")
    priorite = models.CharField("priorité", max_length=8, choices=PrioriteRecommandation.choices)
    ordre = models.PositiveIntegerField("ordre", default=0)

    objects: ClassVar[SansUpsertManager[Any]] = SansUpsertManager()
    all_objects: ClassVar[SansUpsertAllManager[Any]] = SansUpsertAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "recommandation"
        verbose_name_plural = "recommandations"
        ordering = ("ordre", "created_at")

    def __str__(self) -> str:
        return self.libelle[:60]

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_dependant(self)


class ReponseAudite(MissionEnfantModel):
    """Réponse de l'audité à un constat (D11) : historique en ajout seul."""

    mission = _mission_fk("reponses_constat")
    constat = models.ForeignKey(
        Constat, verbose_name="constat", on_delete=models.PROTECT, related_name="reponses"
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="auteur",
        on_delete=models.PROTECT,
        related_name="+",
    )
    cycle = models.PositiveSmallIntegerField("cycle")
    position = models.CharField("position", max_length=10, choices=PositionAudite.choices)
    commentaire = models.TextField("commentaire", blank=True)
    confirmation = models.ForeignKey(
        "signatures.Confirmation",
        verbose_name="confirmation",
        on_delete=models.PROTECT,
        related_name="+",
    )

    objects: ClassVar[ReponseManager[Any]] = ReponseManager()
    all_objects: ClassVar[ReponseAllManager[Any]] = ReponseAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "réponse de l'audité"
        verbose_name_plural = "réponses de l'audité"
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(position="DESACCORD") | ~Q(commentaire=""),
                name="reponse_desaccord_motive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_position_display()} ({self.constat_id})"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_reponse(self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise ReponseAjoutSeulError
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise ReponseAjoutSeulError


class EvenementConstat(BaseModel):
    """Journal des transitions d'un constat : ajout seul."""

    constat = models.ForeignKey(
        Constat, verbose_name="constat", on_delete=models.PROTECT, related_name="evenements"
    )
    type = models.CharField("type", max_length=16, choices=TypeEvenementConstat.choices)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="par"
    )
    le = models.DateTimeField("le", default=timezone.now)
    motif = models.TextField("motif", blank=True)
    statut_avant = models.CharField("statut avant", max_length=12, choices=StatutConstat.choices)
    statut_apres = models.CharField("statut après", max_length=12, choices=StatutConstat.choices)

    objects: ClassVar[JournalConstatManager[Any]] = JournalConstatManager()
    all_objects: ClassVar[JournalConstatAllManager[Any]] = JournalConstatAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "événement de constat"
        verbose_name_plural = "événements de constat"
        ordering = ("le", "created_at")

    def __str__(self) -> str:
        return f"{self.get_type_display()} ({self.le:%d/%m/%Y})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        from apps.core.exceptions import RegleMetierError
        from apps.missions.gardes import refuser_si_figee

        if not self._state.adding:
            raise RegleMetierError(MSG_EVENEMENT_AJOUT_SEUL)
        refuser_si_figee(self.constat.mission_id)
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        from apps.core.exceptions import RegleMetierError

        raise RegleMetierError(MSG_EVENEMENT_AJOUT_SEUL)

    @classmethod
    def journaliser(
        cls,
        constat: Constat,
        type: str,  # noqa: A002
        *,
        par: Any,
        motif: str = "",
        statut_avant: str,
    ) -> "EvenementConstat":
        """Écrit l'événement ; `statut_apres` est le statut courant du constat."""
        evenement: EvenementConstat = cls.objects.create(
            constat=constat,
            type=type,
            par=par,
            motif=motif,
            statut_avant=statut_avant,
            statut_apres=constat.statut,
        )
        return evenement
