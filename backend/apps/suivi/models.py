"""Suivi des recommandations : suivi d'action, événements, reports, preuves, relances (lot 8)."""

from typing import Any, ClassVar

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django_fsm import FSMField, transition

from apps.constats.models import Recommandation
from apps.core.models import BaseModel
from apps.missions.models import Mission, MissionEnfantModel
from apps.referentiel.models import Direction

from . import sources
from .exceptions import (
    AjoutSeulSuiviError,
    PreuveImmuableError,
    RelanceImmuableError,
    SuiviImmuableError,
)
from .managers import (
    ChampsFigesAllManager,
    ChampsFigesManager,
    JournalAllManager,
    JournalManager,
    RelanceAllManager,
    RelanceManager,
    attname_de,
    controler_champs_figes,
)

REGEX_SHA256 = r"^[0-9a-f]{64}$"


class StatutSuivi(models.TextChoices):
    A_LANCER = "A_LANCER", "À lancer"
    EN_COURS = "EN_COURS", "En cours"
    REALISEE = "REALISEE", "Réalisée, à vérifier"
    VERIFIEE = "VERIFIEE", "Vérifiée"
    CLOTUREE = "CLOTUREE", "Clôturée"
    ABANDON_PROPOSE = "ABANDON_PROPOSE", "Abandon proposé"
    ABANDONNEE = "ABANDONNEE", "Abandonnée (justifiée)"


STATUTS_CLOS: frozenset[str] = frozenset({StatutSuivi.CLOTUREE, StatutSuivi.ABANDONNEE})
STATUTS_RELANCABLES: frozenset[str] = frozenset({StatutSuivi.A_LANCER, StatutSuivi.EN_COURS})


class StatutRecommandationSuivi(models.TextChoices):
    """Statut dérivé d'une recommandation (jamais stocké)."""

    A_LANCER = "A_LANCER", "À lancer"
    EN_COURS = "EN_COURS", "En cours"
    REALISEE = "REALISEE", "Réalisée"
    ABANDONNEE = "ABANDONNEE", "Abandonnée"
    RISQUE_ACCEPTE = "RISQUE_ACCEPTE", "Risque accepté"
    SANS_ACTION = "SANS_ACTION", "Sans action"


class TypeEvenementSuivi(models.TextChoices):
    OUVERT = "OUVERT", "Suivi ouvert"
    DEMARRE = "DEMARRE", "Action démarrée"
    COMMENTAIRE = "COMMENTAIRE", "Commentaire"
    DECLAREE_REALISEE = "DECLAREE_REALISEE", "Déclarée réalisée"
    VERIFIEE = "VERIFIEE", "Vérifiée"
    REJETEE = "REJETEE", "Rejetée"
    CLOTUREE = "CLOTUREE", "Clôturée"
    ABANDON_PROPOSE = "ABANDON_PROPOSE", "Abandon proposé"
    ABANDON_ACCEPTE = "ABANDON_ACCEPTE", "Abandon accepté"
    ROUVERTE = "ROUVERTE", "Rouverte"
    RESPONSABLE_CHANGE = "RESPONSABLE_CHANGE", "Responsable changé"
    REPORT_DEMANDE = "REPORT_DEMANDE", "Report demandé"
    REPORT_ACCEPTE = "REPORT_ACCEPTE", "Report accepté"
    REPORT_REFUSE = "REPORT_REFUSE", "Report refusé"
    PREUVE_DEPOSEE = "PREUVE_DEPOSEE", "Preuve déposée"
    PREUVE_RETIREE = "PREUVE_RETIREE", "Preuve retirée"


class PalierRelance(models.TextChoices):
    J_MOINS_15 = "J_MOINS_15", "J-15"
    J = "J", "Jour de l'échéance"
    J_PLUS_15 = "J_PLUS_15", "J+15"


class StatutRelance(models.TextChoices):
    A_ENVOYER = "A_ENVOYER", "À envoyer"
    ENVOYEE = "ENVOYEE", "Envoyée"
    ECHEC = "ECHEC", "Échec d'envoi"
    SANS_ADRESSE = "SANS_ADRESSE", "Sans adresse"


class StatutDemandeReport(models.TextChoices):
    EN_ATTENTE = "EN_ATTENTE", "En attente"
    ACCEPTEE = "ACCEPTEE", "Acceptée"
    REFUSEE = "REFUSEE", "Refusée"


def _mission_fk(related_name: str) -> models.ForeignKey[Mission]:
    return models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name=related_name, verbose_name="mission"
    )


def _utilisateur_fk(verbose_name: str, **kwargs: Any) -> models.ForeignKey[Any]:
    kwargs.setdefault("related_name", "+")
    return models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=verbose_name, on_delete=models.PROTECT, **kwargs
    )


def _utilisateur_nullable(verbose_name: str) -> models.ForeignKey[Any]:
    return _utilisateur_fk(verbose_name, null=True, blank=True)


class SuiviAction(MissionEnfantModel):
    """Suivi d'une action du plan diffusé (R1) : l'action du lot 7 reste figée."""

    mission = _mission_fk("suivis_actions")
    action = models.OneToOneField(
        sources.MODELE_ACTION,
        verbose_name="action du plan",
        on_delete=models.PROTECT,
        related_name="suivi",
    )
    recommandation = models.ForeignKey(
        Recommandation,
        verbose_name="recommandation",
        on_delete=models.PROTECT,
        related_name="suivis",
    )
    entite = models.ForeignKey(
        Direction, verbose_name="entité", on_delete=models.PROTECT, related_name="+"
    )
    responsable = _utilisateur_fk("responsable", related_name="suivis_responsable")
    echeance_initiale = models.DateField("échéance initiale")
    echeance = models.DateField("échéance courante")
    diffuse_le = models.DateField("date de diffusion du rapport")
    nombre_reports = models.PositiveSmallIntegerField("nombre de reports", default=0)
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        max_length=16,
        choices=StatutSuivi.choices,
        default=StatutSuivi.A_LANCER,
        # `protected=True` casserait `refresh_from_db` ; les services imposent R2.
        protected=False,
    )
    declaree_par = _utilisateur_nullable("déclarée réalisée par")
    declaree_le = models.DateTimeField("déclarée réalisée le", null=True, blank=True)
    verifiee_par = _utilisateur_nullable("vérifiée par")
    verifiee_le = models.DateTimeField("vérifiée le", null=True, blank=True)
    cloturee_par = _utilisateur_nullable("clôturée par")
    cloturee_le = models.DateTimeField("clôturée le", null=True, blank=True)
    justification_abandon = models.TextField("justification de l'abandon", blank=True)
    motif_dernier_rejet = models.TextField("motif du dernier rejet", blank=True)
    derniere_activite_le = models.DateTimeField("dernière activité le", default=timezone.now)

    objects: ClassVar[ChampsFigesManager[Any]] = ChampsFigesManager()
    all_objects: ClassVar[ChampsFigesAllManager[Any]] = ChampsFigesAllManager()  # noqa: DJ012

    # Copies faites à l'ouverture (R1) : immuables, sauvegarde comme écriture en masse.
    CHAMPS_FIGES: ClassVar[tuple[str, ...]] = (
        "recommandation",
        "entite",
        "echeance_initiale",
        "diffuse_le",
        "action",
        "mission",
    )

    class Meta:
        verbose_name = "suivi d'action"
        verbose_name_plural = "suivis d'actions"
        ordering = ("echeance", "created_at")
        constraints = [
            models.CheckConstraint(
                condition=~Q(statut__in=["ABANDON_PROPOSE", "ABANDONNEE"])
                | ~Q(justification_abandon=""),
                name="suivi_abandon_justifie",
            ),
            models.CheckConstraint(
                condition=Q(echeance__gte=F("echeance_initiale")),
                name="suivi_echeance_apres_initiale",
            ),
        ]
        indexes = [
            models.Index(fields=["statut", "echeance"], name="suivi_statut_echeance_idx"),
            models.Index(fields=["responsable", "statut"], name="suivi_responsable_statut_idx"),
        ]

    def __str__(self) -> str:
        return f"Suivi {self.action_id}"

    @classmethod
    def champs_figes(cls) -> set[str]:
        return {attname_de(cls, c) for c in cls.CHAMPS_FIGES}

    @classmethod
    def erreur_champs_figes(cls, champs: list[str]) -> SuiviImmuableError:
        return SuiviImmuableError(champs)

    def save(self, *args: Any, **kwargs: Any) -> None:
        controler_champs_figes(self, kwargs.get("update_fields"))
        super().save(*args, **kwargs)

    # Transitions de R2 : sans effet de bord (auteurs, dates, motifs : services de T5).
    @transition(  # type: ignore[untyped-decorator]
        field=statut, source=StatutSuivi.A_LANCER, target=StatutSuivi.EN_COURS
    )
    def demarrer(self) -> None:
        pass

    @transition(  # type: ignore[untyped-decorator]
        field=statut,
        source=[StatutSuivi.A_LANCER, StatutSuivi.EN_COURS],
        target=StatutSuivi.REALISEE,
    )
    def declarer_realisee(self) -> None:
        pass

    @transition(  # type: ignore[untyped-decorator]
        field=statut,
        source=[StatutSuivi.A_LANCER, StatutSuivi.EN_COURS],
        target=StatutSuivi.ABANDON_PROPOSE,
    )
    def proposer_abandon(self) -> None:
        pass

    @transition(  # type: ignore[untyped-decorator]
        field=statut, source=StatutSuivi.REALISEE, target=StatutSuivi.VERIFIEE
    )
    def verifier(self) -> None:
        pass

    @transition(  # type: ignore[untyped-decorator]
        field=statut,
        source=[StatutSuivi.REALISEE, StatutSuivi.VERIFIEE, StatutSuivi.ABANDON_PROPOSE],
        target=StatutSuivi.EN_COURS,
    )
    def rejeter(self) -> None:
        pass

    @transition(  # type: ignore[untyped-decorator]
        field=statut, source=StatutSuivi.VERIFIEE, target=StatutSuivi.CLOTUREE
    )
    def cloturer(self) -> None:
        pass

    @transition(  # type: ignore[untyped-decorator]
        field=statut, source=StatutSuivi.ABANDON_PROPOSE, target=StatutSuivi.ABANDONNEE
    )
    def accepter_abandon(self) -> None:
        pass

    @transition(  # type: ignore[untyped-decorator]
        field=statut,
        source=[StatutSuivi.CLOTUREE, StatutSuivi.ABANDONNEE],
        target=StatutSuivi.EN_COURS,
    )
    def rouvrir(self) -> None:
        pass


class EvenementSuivi(BaseModel):
    """Journal du suivi d'une action : ajout seul (`par` nul = système)."""

    suivi = models.ForeignKey(
        SuiviAction, verbose_name="suivi", on_delete=models.PROTECT, related_name="evenements"
    )
    type = models.CharField("type", max_length=24, choices=TypeEvenementSuivi.choices)
    par = _utilisateur_nullable("par")
    pour_compte_de = _utilisateur_nullable("pour le compte de")
    le = models.DateTimeField("le", default=timezone.now)
    statut_avant = models.CharField("statut avant", max_length=16, blank=True)
    statut_apres = models.CharField("statut après", max_length=16, blank=True)
    texte = models.TextField("texte", blank=True)
    donnees = models.JSONField("données", default=dict, blank=True)

    objects: ClassVar[JournalManager[Any]] = JournalManager()
    all_objects: ClassVar[JournalAllManager[Any]] = JournalAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "événement de suivi"
        verbose_name_plural = "événements de suivi"
        ordering = ("le", "created_at")
        indexes = [models.Index(fields=["suivi", "le"], name="evt_suivi_suivi_le_idx")]

    def __str__(self) -> str:
        return f"{self.type} ({self.suivi_id})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise AjoutSeulSuiviError
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise AjoutSeulSuiviError

    @classmethod
    def journaliser(
        cls,
        suivi: SuiviAction,
        type: str,  # noqa: A002
        *,
        par: Any,
        texte: str = "",
        donnees: dict[str, Any] | None = None,
        statut_avant: str = "",
        pour_compte_de: Any = None,
    ) -> "EvenementSuivi":
        """Ajoute un événement ; `statut_apres` est le statut courant du suivi."""
        evenement: EvenementSuivi = cls.objects.create(
            suivi=suivi,
            type=type,
            par=par,
            pour_compte_de=pour_compte_de,
            statut_avant=statut_avant,
            statut_apres=suivi.statut,
            texte=texte,
            donnees=donnees or {},
            created_by=par,
        )
        return evenement


class DemandeReport(MissionEnfantModel):
    """Demande de report d'échéance (R5) ; une seule demande en attente par suivi."""

    suivi = models.ForeignKey(
        SuiviAction,
        verbose_name="suivi",
        on_delete=models.PROTECT,
        related_name="demandes_report",
    )
    mission = _mission_fk("demandes_report")
    echeance_actuelle = models.DateField("échéance actuelle")
    nouvelle_echeance = models.DateField("nouvelle échéance")
    motif = models.TextField("motif")
    demandee_par = _utilisateur_fk("demandée par")
    statut = models.CharField(
        "statut",
        max_length=12,
        choices=StatutDemandeReport.choices,
        default=StatutDemandeReport.EN_ATTENTE,
    )
    decidee_par = _utilisateur_nullable("décidée par")
    decidee_le = models.DateTimeField("décidée le", null=True, blank=True)
    commentaire_decision = models.TextField("commentaire de la décision", blank=True)

    class Meta:
        verbose_name = "demande de report"
        verbose_name_plural = "demandes de report"
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(nouvelle_echeance__gt=F("echeance_actuelle")),
                name="report_nouvelle_echeance_posterieure",
            ),
            models.CheckConstraint(condition=~Q(motif=""), name="report_motif_non_vide"),
            models.UniqueConstraint(
                fields=["suivi"],
                condition=Q(statut="EN_ATTENTE") & Q(deleted_at__isnull=True),
                name="report_une_demande_en_attente",
            ),
        ]

    def __str__(self) -> str:
        return f"Report vers le {self.nouvelle_echeance:%d/%m/%Y}"


class PreuveMiseEnOeuvre(MissionEnfantModel):
    """Preuve de mise en œuvre : fichier en écriture unique, empreinte SHA-256 (R8)."""

    suivi = models.ForeignKey(
        SuiviAction, verbose_name="suivi", on_delete=models.PROTECT, related_name="preuves"
    )
    mission = _mission_fk("preuves_mise_en_oeuvre")
    numero = models.PositiveIntegerField("numéro")
    libelle = models.CharField("libellé", max_length=200)
    description = models.TextField("description", blank=True)
    # Jamais réattribuée : unique sans condition, preuves retirées incluses.
    cle_stockage = models.CharField("clé de stockage", max_length=255, unique=True)
    empreinte_sha256 = models.CharField("empreinte SHA-256", max_length=64)
    taille_octets = models.PositiveBigIntegerField("taille (octets)")
    type_mime = models.CharField("type MIME", max_length=120)
    nom_fichier_original = models.CharField("nom du fichier d'origine", max_length=255)
    deposee_par = _utilisateur_fk("déposée par")
    deposee_le = models.DateTimeField("déposée le", default=timezone.now)

    objects: ClassVar[ChampsFigesManager[Any]] = ChampsFigesManager()
    all_objects: ClassVar[ChampsFigesAllManager[Any]] = ChampsFigesAllManager()  # noqa: DJ012

    CHAMPS_FICHIER: ClassVar[tuple[str, ...]] = (
        "cle_stockage",
        "empreinte_sha256",
        "taille_octets",
        "type_mime",
        "nom_fichier_original",
    )

    class Meta:
        verbose_name = "preuve de mise en œuvre"
        verbose_name_plural = "preuves de mise en œuvre"
        ordering = ("numero",)
        constraints = [
            models.UniqueConstraint(fields=["suivi", "numero"], name="preuve_numero_unique"),
            models.CheckConstraint(
                condition=Q(empreinte_sha256__regex=REGEX_SHA256),
                name="preuve_empreinte_sha256",
            ),
        ]

    def __str__(self) -> str:
        return f"Preuve {self.numero} ({self.suivi_id})"

    @classmethod
    def champs_figes(cls) -> set[str]:
        return {attname_de(cls, c) for c in cls.CHAMPS_FICHIER}

    @classmethod
    def erreur_champs_figes(cls, champs: list[str]) -> PreuveImmuableError:
        return PreuveImmuableError()

    def save(self, *args: Any, **kwargs: Any) -> None:
        controler_champs_figes(self, kwargs.get("update_fields"))
        super().save(*args, **kwargs)


class Relance(BaseModel):
    """Relance automatique d'un suivi (R9) : seul l'état d'envoi change après création."""

    suivi = models.ForeignKey(
        SuiviAction, verbose_name="suivi", on_delete=models.PROTECT, related_name="relances"
    )
    palier = models.CharField("palier", max_length=12, choices=PalierRelance.choices)
    echeance_reference = models.DateField("échéance de référence")
    destinataire = _utilisateur_fk("destinataire")
    copie = _utilisateur_nullable("en copie")
    statut = models.CharField(
        "statut", max_length=12, choices=StatutRelance.choices, default=StatutRelance.A_ENVOYER
    )
    tentatives = models.PositiveSmallIntegerField("tentatives", default=0)
    envoyee_le = models.DateTimeField("envoyée le", null=True, blank=True)
    erreur = models.CharField("erreur", max_length=500, blank=True)

    objects: ClassVar[RelanceManager[Any]] = RelanceManager()
    all_objects: ClassVar[RelanceAllManager[Any]] = RelanceAllManager()  # noqa: DJ012

    MODIFIABLES: ClassVar[frozenset[str]] = frozenset(
        {
            "statut",
            "tentatives",
            "envoyee_le",
            "erreur",
            "updated_at",
            "updated_by_id",
            "deleted_at",
        }
    )

    class Meta:
        verbose_name = "relance"
        verbose_name_plural = "relances"
        ordering = ("created_at",)
        constraints = [
            # Idempotence : jamais réattribuée, supprimées incluses.
            models.UniqueConstraint(
                fields=["suivi", "palier", "echeance_reference"], name="relance_unique_par_cycle"
            ),
        ]

    def __str__(self) -> str:
        return f"Relance {self.palier} ({self.suivi_id})"

    @classmethod
    def champs_figes(cls) -> set[str]:
        return {f.attname for f in cls._meta.concrete_fields} - cls.MODIFIABLES

    @classmethod
    def erreur_champs_figes(cls, champs: list[str]) -> RelanceImmuableError:
        return RelanceImmuableError(champs)

    def save(self, *args: Any, **kwargs: Any) -> None:
        controler_champs_figes(self, kwargs.get("update_fields"))
        super().save(*args, **kwargs)
