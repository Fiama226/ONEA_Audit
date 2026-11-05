from typing import Any, ClassVar

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django_fsm import FSMField, transition

from apps.core.exceptions import RegleMetierError
from apps.core.models import BaseModel
from apps.missions.gardes import exiger_etape_ouverte
from apps.missions.models import (
    EtapeMission,
    Mission,
    MissionEnfantModel,
    RisqueMission,
)

from .exceptions import MSG_AJOUT_SEUL, InstantaneImmuableError
from .managers import (
    InstantaneAllManager,
    InstantaneManager,
    JournalFicheAllManager,
    JournalFicheManager,
    PieceAllManager,
    PieceManager,
)


class NatureTest(models.TextChoices):
    ENTRETIEN = "ENTRETIEN", "Entretien"
    QCI = "QCI", "Questionnaire de contrôle interne"
    OBSERVATION = "OBSERVATION", "Observation physique"
    EXAMEN_DOCUMENTAIRE = "EXAMEN_DOCUMENTAIRE", "Examen documentaire"
    PROCEDURE_ANALYTIQUE = "PROCEDURE_ANALYTIQUE", "Procédure analytique"
    PISTE_AUDIT = "PISTE_AUDIT", "Piste d'audit"
    CIRCULARISATION = "CIRCULARISATION", "Confirmation / circularisation"
    ECHANTILLONNAGE = "ECHANTILLONNAGE", "Échantillonnage"
    CAATS = "CAATS", "Analyse de données (CAATs)"
    TEST_CHEMINEMENT = "TEST_CHEMINEMENT", "Test de cheminement"
    AUTRE = "AUTRE", "Autre"


class MethodeSelection(models.TextChoices):
    EXHAUSTIF = "EXHAUSTIF", "Exhaustif"
    ALEATOIRE = "ALEATOIRE", "Aléatoire"
    STATISTIQUE = "STATISTIQUE", "Statistique"
    RAISONNE = "RAISONNE", "Raisonné"


class StatutTest(models.TextChoices):
    PREVU = "PREVU", "Prévu"
    ABANDONNE = "ABANDONNE", "Abandonné"


class StatutFiche(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    SOUMIS = "SOUMIS", "Soumise"
    VALIDE = "VALIDE", "Validée"
    RENVOYE = "RENVOYE", "Renvoyée"


class ConclusionTest(models.TextChoices):
    SATISFAISANT = "SATISFAISANT", "Satisfaisant"
    POINT_FORT = "POINT_FORT", "Point fort"
    ANOMALIE = "ANOMALIE", "Anomalie"


class TypeEvenementFiche(models.TextChoices):
    SOUMISE = "SOUMISE", "Soumise"
    VALIDEE = "VALIDEE", "Validée"
    RENVOYEE = "RENVOYEE", "Renvoyée"
    ROUVERTE = "ROUVERTE", "Rouverte"


def _mission_fk(related_name: str) -> models.ForeignKey[Mission]:
    return models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name=related_name, verbose_name="mission"
    )


class ProgrammeDeTravail(MissionEnfantModel):
    """Programme de travail d'un objectif d'audit retenu (D3)."""

    mission = _mission_fk("programmes")
    objectif = models.ForeignKey(
        "analyse.ObjectifAudit",
        verbose_name="objectif d'audit",
        on_delete=models.PROTECT,
        related_name="programmes",
    )
    techniques = models.TextField("techniques et sources d'information", blank=True)
    criteres_preuve = models.TextField("critères de preuve", blank=True)
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        verbose_name = "programme de travail"
        verbose_name_plural = "programmes de travail"
        ordering = ("created_at",)
        constraints = [
            models.UniqueConstraint(
                fields=["mission", "objectif"],
                condition=Q(deleted_at__isnull=True),
                name="programme_objectif_unique_actif",
            )
        ]

    def __str__(self) -> str:
        return f"Programme {self.objectif_id}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        exiger_etape_ouverte(self.mission_id, gardes.ETAPE_CONTENU)


class TestPrevu(MissionEnfantModel):
    """Test prévu (D4). Le code `T-nn` n'est jamais réattribué, même supprimé."""

    __test__ = False  # n'est pas un test pytest

    mission = _mission_fk("tests_prevus")
    programme = models.ForeignKey(
        ProgrammeDeTravail,
        verbose_name="programme",
        on_delete=models.PROTECT,
        related_name="tests",
    )
    code = models.CharField("code", max_length=12)
    numero = models.PositiveIntegerField("numéro")
    libelle = models.CharField("libellé", max_length=300)
    objectif_test = models.TextField("objectif du test", blank=True)
    nature = models.CharField(
        "nature", max_length=24, choices=NatureTest.choices, default=NatureTest.AUTRE
    )
    procedure = models.TextField("procédure", blank=True)
    population = models.TextField("population", blank=True)
    taille_echantillon = models.PositiveIntegerField(
        "taille de l'échantillon", null=True, blank=True
    )
    methode_selection = models.CharField(
        "méthode de sélection", max_length=16, choices=MethodeSelection.choices, blank=True
    )
    auditeur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="auditeur",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    charge_prevue_jours = models.DecimalField(
        "charge prévue (jours)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    date_debut_prevue = models.DateField("début prévu", null=True, blank=True)
    date_fin_prevue = models.DateField("fin prévue", null=True, blank=True)
    risque_mission = models.ForeignKey(
        RisqueMission,
        verbose_name="risque de la mission",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    complementaire = models.BooleanField("test complémentaire", default=False)
    statut = models.CharField(
        "statut", max_length=12, choices=StatutTest.choices, default=StatutTest.PREVU
    )
    motif_abandon = models.TextField("motif d'abandon", blank=True)
    ordre = models.PositiveIntegerField("ordre", default=0)

    class Meta:
        verbose_name = "test prévu"
        verbose_name_plural = "tests prévus"
        ordering = ("numero",)
        constraints = [
            # Jamais réattribués : sans condition, supprimés inclus.
            models.UniqueConstraint(fields=["mission", "code"], name="test_prevu_code_unique"),
            models.UniqueConstraint(fields=["mission", "numero"], name="test_prevu_numero_unique"),
            models.CheckConstraint(
                condition=~Q(statut="ABANDONNE") | ~Q(motif_abandon=""),
                name="test_prevu_abandon_motive",
            ),
            models.CheckConstraint(
                condition=Q(charge_prevue_jours__isnull=True) | Q(charge_prevue_jours__gte=0),
                name="test_prevu_charge_positive",
            ),
            models.CheckConstraint(
                condition=Q(date_debut_prevue__isnull=True)
                | Q(date_fin_prevue__isnull=True)
                | Q(date_fin_prevue__gte=F("date_debut_prevue")),
                name="test_prevu_dates_coherentes",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.code} {self.libelle}"

    @property
    def fiche(self) -> "FicheDeTest | None":
        """Fiche active du test (au plus une)."""
        return self.fiches.first()

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_test(self)


class FicheDeTest(MissionEnfantModel):
    """Fiche de test (D7) : une fiche active par test."""

    mission = _mission_fk("fiches_test")
    test = models.ForeignKey(
        TestPrevu,
        verbose_name="test",
        on_delete=models.PROTECT,
        related_name="fiches",
        related_query_name="fiche",
    )
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        max_length=12,
        choices=StatutFiche.choices,
        default=StatutFiche.BROUILLON,
        protected=False,
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="auteur",
        on_delete=models.PROTECT,
        related_name="+",
    )
    date_realisation = models.DateField("date de réalisation", null=True, blank=True)
    travaux_realises = models.TextField("travaux réalisés", blank=True)
    echantillon_teste = models.TextField("échantillon testé", blank=True)
    taille_testee = models.PositiveIntegerField("taille testée", null=True, blank=True)
    nombre_exceptions = models.PositiveIntegerField("nombre d'exceptions", null=True, blank=True)
    resultat = models.TextField("résultat", blank=True)
    conclusion = models.CharField(
        "conclusion", max_length=16, choices=ConclusionTest.choices, blank=True
    )
    commentaire_conclusion = models.TextField("commentaire de la conclusion", blank=True)
    charge_reelle_jours = models.DecimalField(
        "charge réelle (jours)", max_digits=5, decimal_places=1, null=True, blank=True
    )
    justification_sans_piece = models.TextField("justification sans pièce", blank=True)
    soumise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="soumise par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    soumise_le = models.DateTimeField("soumise le", null=True, blank=True)
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validée par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    validee_le = models.DateTimeField("validée le", null=True, blank=True)
    motif_renvoi = models.TextField("motif du renvoi", blank=True)

    _rouverture: bool = False

    class Meta:
        verbose_name = "fiche de test"
        verbose_name_plural = "fiches de test"
        ordering = ("test__numero",)
        constraints = [
            models.UniqueConstraint(
                fields=["test"],
                condition=Q(deleted_at__isnull=True),
                name="fiche_test_unique_actif",
            ),
            models.CheckConstraint(
                condition=Q(nombre_exceptions__lte=F("taille_testee")),
                name="fiche_exceptions_dans_taille",
            ),
            models.CheckConstraint(
                condition=Q(statut__in=["BROUILLON", "RENVOYE"]) | ~Q(conclusion=""),
                name="fiche_soumise_conclue",
            ),
            models.CheckConstraint(
                condition=Q(charge_reelle_jours__isnull=True) | Q(charge_reelle_jours__gte=0),
                name="fiche_charge_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"Fiche {self.test_id}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_fiche(self)

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

    # Transitions de D7 : appelées par les services (qui posent aussi auteurs, dates, motifs
    # et l'événement). `protected=False` : le champ reste modifiable par `update`.

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutFiche.BROUILLON, StatutFiche.RENVOYE],
        target=StatutFiche.SOUMIS,
    )
    def soumettre(self) -> None:
        """BROUILLON ou RENVOYE -> SOUMIS."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutFiche.SOUMIS, target=StatutFiche.VALIDE
    )
    def valider(self) -> None:
        """SOUMIS -> VALIDE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutFiche.SOUMIS, target=StatutFiche.RENVOYE
    )
    def renvoyer(self) -> None:
        """SOUMIS -> RENVOYE (motif posé par le service)."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutFiche.VALIDE, target=StatutFiche.BROUILLON
    )
    def rouvrir(self) -> None:
        """VALIDE -> BROUILLON ; la sauvegarde qui suit est la seule permise sur une VALIDE."""
        self._rouverture = True


class EvenementFiche(BaseModel):
    """Journal des transitions d'une fiche : ajout seul."""

    fiche = models.ForeignKey(
        FicheDeTest,
        verbose_name="fiche",
        on_delete=models.PROTECT,
        related_name="evenements",
    )
    type = models.CharField("type", max_length=16, choices=TypeEvenementFiche.choices)
    par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="par"
    )
    le = models.DateTimeField("le", default=timezone.now)
    motif = models.TextField("motif", blank=True)
    statut_avant = models.CharField("statut avant", max_length=12, choices=StatutFiche.choices)
    statut_apres = models.CharField("statut après", max_length=12, choices=StatutFiche.choices)

    objects: ClassVar[JournalFicheManager[Any]] = JournalFicheManager()
    all_objects: ClassVar[JournalFicheAllManager[Any]] = JournalFicheAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "événement de fiche"
        verbose_name_plural = "événements de fiche"
        ordering = ("le", "created_at")

    def __str__(self) -> str:
        return f"{self.get_type_display()} ({self.le:%d/%m/%Y})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        from apps.core.exceptions import RegleMetierError
        from apps.missions.gardes import refuser_si_figee

        if not self._state.adding:
            raise RegleMetierError(MSG_AJOUT_SEUL)
        refuser_si_figee(self.fiche.mission_id)
        super().save(*args, **kwargs)

    @classmethod
    def journaliser(
        cls,
        fiche: FicheDeTest,
        type: str,  # noqa: A002
        *,
        par: Any,
        motif: str = "",
        statut_avant: str,
    ) -> "EvenementFiche":
        """Écrit l'événement ; `statut_apres` est le statut courant de la fiche."""
        evenement: EvenementFiche = cls.objects.create(
            fiche=fiche,
            type=type,
            par=par,
            motif=motif,
            statut_avant=statut_avant,
            statut_apres=fiche.statut,
        )
        return evenement


class PieceJustificative(MissionEnfantModel):
    """Pièce justificative d'une fiche : fichier à écriture unique, empreinte SHA-256 (D8)."""

    mission = _mission_fk("pieces_justificatives")
    fiche = models.ForeignKey(
        FicheDeTest, verbose_name="fiche", on_delete=models.PROTECT, related_name="pieces"
    )
    numero = models.PositiveIntegerField("numéro")
    libelle = models.CharField("libellé", max_length=200)
    description = models.TextField("description", blank=True)
    cle_stockage = models.CharField("clé de stockage", max_length=255, unique=True)
    empreinte_sha256 = models.CharField("empreinte SHA-256", max_length=64)
    taille_octets = models.BigIntegerField("taille (octets)")
    type_mime = models.CharField("type MIME", max_length=100)
    nom_fichier_original = models.CharField("nom du fichier d'origine", max_length=255)
    deposee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="déposée par",
        on_delete=models.PROTECT,
        related_name="+",
    )
    deposee_le = models.DateTimeField("déposée le", default=timezone.now)

    # Pas un champ : posé par `deposer_piece` quand les mêmes octets étaient déjà déposés.
    doublon: bool = False

    objects: ClassVar[PieceManager[Any]] = PieceManager()
    all_objects: ClassVar[PieceAllManager[Any]] = PieceAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "pièce justificative"
        verbose_name_plural = "pièces justificatives"
        ordering = ("numero",)
        constraints = [
            models.UniqueConstraint(fields=["mission", "numero"], name="piece_numero_unique"),
            models.CheckConstraint(
                condition=Q(empreinte_sha256__regex=r"^[0-9a-f]{64}$"),
                name="piece_empreinte_sha256",
            ),
            models.CheckConstraint(condition=Q(taille_octets__gt=0), name="piece_taille_positive"),
        ]

    def __str__(self) -> str:
        return f"Pièce {self.numero} : {self.libelle}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_piece(self)


class InstantaneProgramme(BaseModel):
    """Instantané immuable du programme au moment de la validation de l'étape X (D14)."""

    mission = _mission_fk("instantanes_programme")
    etape = models.ForeignKey(
        EtapeMission,
        verbose_name="étape",
        on_delete=models.PROTECT,
        related_name="+",
    )
    donnees = models.JSONField("données", encoder=DjangoJSONEncoder)
    empreinte = models.CharField("empreinte SHA-256", max_length=64)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validé par",
        on_delete=models.PROTECT,
        related_name="+",
    )
    valide_le = models.DateTimeField("validé le")

    objects: ClassVar[InstantaneManager] = InstantaneManager()
    all_objects: ClassVar[InstantaneAllManager] = InstantaneAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "instantané du programme"
        verbose_name_plural = "instantanés du programme"
        ordering = ("-valide_le",)
        constraints = [
            models.CheckConstraint(
                condition=Q(empreinte__regex=r"^[0-9a-f]{64}$"),
                name="instantane_empreinte_sha256",
            )
        ]

    def __str__(self) -> str:
        return f"Instantané {self.valide_le:%d/%m/%Y}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        from apps.missions.gardes import refuser_si_figee

        if not self._state.adding or kwargs.get("force_update") or kwargs.get("update_fields"):
            raise InstantaneImmuableError
        refuser_si_figee(self.mission_id)
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise InstantaneImmuableError


class PositionAccord(models.TextChoices):
    ACCORD = "ACCORD", "Accord"
    DESACCORD = "DESACCORD", "Désaccord"


class AccordResultats(BaseModel):
    """Position de l'entité auditée sur les résultats des tests (fiche XIII, « avec les
    audités ») : accord, ou désaccord motivé. Ajout seul ; la dernière position fait foi.

    Exigée pour clore l'étape XIII quand la règle de gouvernance « réponse de l'audité »
    l'active (contrôle `evidence_agreement`), sauf dérogation motivée.
    """

    mission = models.ForeignKey(
        "missions.Mission",
        on_delete=models.PROTECT,
        related_name="accords_resultats",
        verbose_name="mission",
    )
    entite = models.ForeignKey(
        "referentiel.Direction",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="entité",
    )
    auteur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="auteur",
    )
    position = models.CharField("position", max_length=10, choices=PositionAccord.choices)
    commentaire = models.TextField("commentaire", blank=True)

    class Meta:
        verbose_name = "accord sur les résultats des tests"
        verbose_name_plural = "accords sur les résultats des tests"
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=~Q(position="DESACCORD") | ~Q(commentaire=""),
                name="accord_resultats_desaccord_motive",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_position_display()} ({self.entite_id})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise RegleMetierError("Une position sur les résultats ne peut pas être modifiée.")
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise RegleMetierError("Une position sur les résultats ne peut pas être supprimée.")
