"""Modèles du rapport d'audit : rapport, provisoire, réponses, diffusion (lot 7, D4 à D12)."""

from typing import Any, ClassVar

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django_fsm import FSMField, transition

from apps.constats.models import Constat
from apps.core.models import BaseModel
from apps.documents.models import DocumentVersion
from apps.missions.models import Mission, MissionEnfantModel
from apps.signatures.models import Confirmation, ModeSignatureParametre

from .exceptions import AjoutSeulError
from .managers import (
    AjoutSeulAllManager,
    AjoutSeulManager,
    DestinataireAllManager,
    DestinataireManager,
    JournalAllManager,
    JournalManager,
    RapportAllManager,
    RapportManager,
)

REGEX_SHA256 = r"^[0-9a-f]{64}$"


class StatutRapport(models.TextChoices):
    BROUILLON = "BROUILLON", "En rédaction"
    SOUMIS = "SOUMIS", "Soumis au RAI"
    VALIDE = "VALIDE", "Validé"
    RENVOYE = "RENVOYE", "Renvoyé"
    DIFFUSE = "DIFFUSE", "Diffusé"
    REMPLACE = "REMPLACE", "Remplacé par un rapport corrigé"


class AppreciationGlobale(models.TextChoices):
    MAITRISE = "MAITRISE", "Maîtrise satisfaisante des risques"
    PERFECTIBLE = "PERFECTIBLE", "Maîtrise perfectible"
    INSUFFISANTE = "INSUFFISANTE", "Maîtrise insuffisante"


class CategorieDestinataire(models.TextChoices):
    DG = "DG", "Direction générale"
    AUDITE = "AUDITE", "Audité"
    EQUIPE = "EQUIPE", "Équipe d'audit"
    AUTRE = "AUTRE", "Autre destinataire"


class TypeEvenementRapport(models.TextChoices):
    CREE = "CREE", "Créé"
    PROVISOIRE_TRANSMIS = "PROVISOIRE_TRANSMIS", "Rapport provisoire transmis"
    SOUMIS = "SOUMIS", "Soumis"
    VALIDE = "VALIDE", "Validé"
    RENVOYE = "RENVOYE", "Renvoyé"
    REINITIALISE = "REINITIALISE", "Réinitialisé"
    DIFFUSE = "DIFFUSE", "Diffusé"
    CORRIGE = "CORRIGE", "Rapport corrigé émis"


def _mission_fk(related_name: str) -> models.ForeignKey[Mission]:
    return models.ForeignKey(
        Mission, on_delete=models.PROTECT, related_name=related_name, verbose_name="mission"
    )


def _utilisateur_fk(verbose_name: str, **kwargs: Any) -> models.ForeignKey[Any]:
    return models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=verbose_name,
        on_delete=models.PROTECT,
        related_name="+",
        **kwargs,
    )


class Rapport(MissionEnfantModel):
    """Rapport d'audit (D4, D5) : gelé hors rédaction, une seule version active par mission."""

    mission = _mission_fk("rapports")
    numero_version = models.PositiveSmallIntegerField("numéro de version", default=1)
    corrige_de = models.ForeignKey(
        "self",
        verbose_name="corrige le rapport",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="rapports_corriges",
    )
    motif_correction = models.TextField("motif de la correction", blank=True)
    statut = FSMField(  # type: ignore[no-untyped-call]  # django-fsm is untyped
        "statut",
        max_length=10,
        choices=StatutRapport.choices,
        default=StatutRapport.BROUILLON,
        # `protected=True` casserait `refresh_from_db` ; la garde du modèle impose D4 à l'écriture.
        protected=False,
    )
    # Sections saisies (D5).
    synthese = models.TextField("synthèse pour l'encadrement supérieur", blank=True)
    appreciation_globale = models.CharField(
        "appréciation globale", max_length=12, choices=AppreciationGlobale.choices, blank=True
    )
    commentaire_appreciation = models.TextField("commentaire de l'appréciation", blank=True)
    contexte = models.TextField("contexte", blank=True)
    objectifs_texte = models.TextField("objectifs", blank=True)
    perimetre_texte = models.TextField("périmètre", blank=True)
    methodologie = models.TextField("méthodologie", blank=True)
    conclusion = models.TextField("conclusion", blank=True)
    note_synthetique = models.TextField("note synthétique", blank=True)
    annexes_texte = models.TextField("annexes", blank=True)
    # Soumission, validation.
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
    instantane_soumis = models.JSONField(
        "instantané soumis", null=True, blank=True, encoder=DjangoJSONEncoder
    )
    empreinte_soumise = models.CharField("empreinte SHA-256 soumise", max_length=64, blank=True)
    valide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="validé par",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    valide_le = models.DateTimeField("validé le", null=True, blank=True)
    confirmation_validation = models.ForeignKey(
        Confirmation,
        verbose_name="confirmation de la validation",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    mode_signature = models.CharField(
        "mode de signature",
        max_length=30,
        choices=ModeSignatureParametre.choices,
        blank=True,
    )
    motif_renvoi = models.TextField("motif du renvoi", blank=True)

    # Colonnes écrites par la sauvegarde en cours (`update_fields`), lues par la garde.
    _champs_ecrits: frozenset[str] | None = None

    objects: ClassVar[RapportManager[Any]] = RapportManager()
    all_objects: ClassVar[RapportAllManager[Any]] = RapportAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "rapport"
        verbose_name_plural = "rapports"
        ordering = ("numero_version",)
        constraints = [
            # Jamais réattribué : sans condition, supprimés inclus.
            models.UniqueConstraint(
                fields=["mission", "numero_version"], name="rapport_numero_version_unique"
            ),
            models.UniqueConstraint(
                fields=["mission"],
                condition=~Q(statut="REMPLACE") & Q(deleted_at__isnull=True),
                name="rapport_un_actif_par_mission",
            ),
            models.CheckConstraint(
                condition=~Q(statut__in=["SOUMIS", "VALIDE", "DIFFUSE"])
                | Q(empreinte_soumise__regex=REGEX_SHA256),
                name="rapport_empreinte_soumise_sha256",
            ),
        ]

    def __str__(self) -> str:
        return f"Rapport v{self.numero_version}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_rapport(self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        champs = kwargs.get("update_fields")
        self._champs_ecrits = None if champs is None else frozenset(champs)
        try:
            super().save(*args, **kwargs)
        finally:
            self._champs_ecrits = None

    # Transitions de D4 : appelées par les services, qui posent aussi auteurs, dates, motifs,
    # instantané et événement, puis x

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutRapport.BROUILLON, StatutRapport.RENVOYE],
        target=StatutRapport.SOUMIS,
    )
    def soumettre(self) -> None:
        """BROUILLON ou RENVOYE -> SOUMIS."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutRapport.SOUMIS, target=StatutRapport.VALIDE
    )
    def valider(self) -> None:
        """SOUMIS -> VALIDE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutRapport.SOUMIS, target=StatutRapport.RENVOYE
    )
    def renvoyer(self) -> None:
        """SOUMIS -> RENVOYE (motif posé par le service)."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutRapport.VALIDE, target=StatutRapport.DIFFUSE
    )
    def diffuser(self) -> None:
        """VALIDE -> DIFFUSE."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut, source=StatutRapport.DIFFUSE, target=StatutRapport.REMPLACE
    )
    def remplacer(self) -> None:
        """DIFFUSE -> REMPLACE (rapport corrigé émis)."""

    @transition(  # type: ignore[untyped-decorator]  # django-fsm is untyped
        field=statut,
        source=[StatutRapport.SOUMIS, StatutRapport.VALIDE, StatutRapport.RENVOYE],
        target=StatutRapport.BROUILLON,
    )
    def reinitialiser(self) -> None:
        """SOUMIS, VALIDE ou RENVOYE -> BROUILLON (réouverture d'une étape XV à XVIII)."""


class _AjoutSeulModel(MissionEnfantModel):
    """Objet de mission en ajout seul : jamais modifié ni supprimé après sa création."""

    NOM_AJOUT_SEUL: ClassVar[str]

    objects: ClassVar[AjoutSeulManager[Any]] = AjoutSeulManager()
    all_objects: ClassVar[AjoutSeulAllManager[Any]] = AjoutSeulAllManager()  # noqa: DJ012

    class Meta:
        abstract = True

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            raise AjoutSeulError(self.NOM_AJOUT_SEUL)
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise AjoutSeulError(self.NOM_AJOUT_SEUL)


class RapportProvisoire(_AjoutSeulModel):
    """Rapport provisoire transmis aux audités (D6, D7) : instantané immuable."""

    NOM_AJOUT_SEUL = "Un rapport provisoire"

    mission = _mission_fk("rapports_provisoires")
    rapport = models.ForeignKey(
        Rapport, verbose_name="rapport", on_delete=models.PROTECT, related_name="provisoires"
    )
    numero = models.PositiveSmallIntegerField("numéro")
    transmis_le = models.DateTimeField("transmis le", default=timezone.now)
    transmis_par = _utilisateur_fk("transmis par")
    date_limite_reponses = models.DateField("date limite des réponses")
    instantane = models.JSONField("instantané", encoder=DjangoJSONEncoder)
    empreinte = models.CharField("empreinte SHA-256", max_length=64)

    class Meta:
        verbose_name = "rapport provisoire"
        verbose_name_plural = "rapports provisoires"
        ordering = ("numero",)
        constraints = [
            models.UniqueConstraint(fields=["rapport", "numero"], name="provisoire_numero_unique"),
            models.CheckConstraint(
                condition=Q(empreinte__regex=REGEX_SHA256), name="provisoire_empreinte_sha256"
            ),
        ]

    def __str__(self) -> str:
        return f"Rapport provisoire n°{self.numero}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_provisoire(self)


class ReponseRapport(_AjoutSeulModel):
    """Réponse d'un audité à un constat du provisoire (D7) : ajout seul, la dernière fait foi."""

    NOM_AJOUT_SEUL = "Une réponse au rapport provisoire"

    mission = _mission_fk("reponses_rapport")
    provisoire = models.ForeignKey(
        RapportProvisoire,
        verbose_name="rapport provisoire",
        on_delete=models.PROTECT,
        related_name="reponses",
    )
    constat = models.ForeignKey(
        Constat, verbose_name="constat", on_delete=models.PROTECT, related_name="+"
    )
    auteur = _utilisateur_fk("auteur")
    commentaire = models.TextField("commentaire")
    confirmation = models.ForeignKey(
        Confirmation, verbose_name="confirmation", on_delete=models.PROTECT, related_name="+"
    )
    hors_delai = models.BooleanField("hors délai", default=False)

    class Meta:
        verbose_name = "réponse au rapport provisoire"
        verbose_name_plural = "réponses au rapport provisoire"
        ordering = ("created_at",)
        constraints = [
            models.CheckConstraint(
                condition=Q(commentaire__regex=r"\S"), name="reponse_rapport_commentaire_non_vide"
            )
        ]

    def __str__(self) -> str:
        return f"Réponse au constat {self.constat_id}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_reponse(self)


class EvenementRapport(BaseModel):
    """Journal des transitions d'un rapport : ajout seul."""

    rapport = models.ForeignKey(
        Rapport, verbose_name="rapport", on_delete=models.PROTECT, related_name="evenements"
    )
    type = models.CharField("type", max_length=20, choices=TypeEvenementRapport.choices)
    par = _utilisateur_fk("par")
    le = models.DateTimeField("le", default=timezone.now)
    motif = models.TextField("motif", blank=True)
    statut_avant = models.CharField(
        "statut avant", max_length=10, choices=StatutRapport.choices, blank=True
    )
    statut_apres = models.CharField("statut après", max_length=10, choices=StatutRapport.choices)

    objects: ClassVar[JournalManager[Any]] = JournalManager()
    all_objects: ClassVar[JournalAllManager[Any]] = JournalAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "événement de rapport"
        verbose_name_plural = "événements de rapport"
        ordering = ("le", "created_at")

    def __str__(self) -> str:
        return f"{self.get_type_display()} ({self.le:%d/%m/%Y})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        from apps.missions.gardes import refuser_si_figee

        if not self._state.adding:
            raise AjoutSeulError("Un événement de rapport")
        refuser_si_figee(self.rapport.mission_id)
        super().save(*args, **kwargs)

    def soft_delete(self, by: Any) -> None:
        raise AjoutSeulError("Un événement de rapport")

    @classmethod
    def journaliser(
        cls,
        rapport: Rapport,
        type: str,  # noqa: A002
        *,
        par: Any,
        motif: str = "",
        statut_avant: str = "",
    ) -> "EvenementRapport":
        """Écrit l'événement ; `statut_apres` est le statut courant du rapport."""
        evenement: EvenementRapport = cls.objects.create(
            rapport=rapport,
            type=type,
            par=par,
            motif=motif,
            statut_avant=statut_avant,
            statut_apres=rapport.statut,
        )
        return evenement


class DestinataireDiffusion(MissionEnfantModel):
    """Destinataire de la liste de diffusion (D11) : figée à la diffusion, hors suivi."""

    mission = _mission_fk("destinataires_diffusion")
    rapport = models.ForeignKey(
        Rapport, verbose_name="rapport", on_delete=models.PROTECT, related_name="destinataires"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="utilisateur",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    nom_externe = models.CharField("nom (destinataire externe)", max_length=200, blank=True)
    qualite = models.CharField("qualité", max_length=200, blank=True)
    categorie = models.CharField("catégorie", max_length=10, choices=CategorieDestinataire.choices)
    notifie_le = models.DateTimeField("notifié le", null=True, blank=True)
    premiere_consultation_le = models.DateTimeField(
        "première consultation le", null=True, blank=True
    )
    accuse_reception_le = models.DateTimeField("accusé de réception le", null=True, blank=True)
    remis_hors_plateforme_le = models.DateTimeField(
        "remis hors plateforme le", null=True, blank=True
    )

    _champs_ecrits: frozenset[str] | None = None

    objects: ClassVar[DestinataireManager[Any]] = DestinataireManager()
    all_objects: ClassVar[DestinataireAllManager[Any]] = DestinataireAllManager()  # noqa: DJ012

    class Meta:
        verbose_name = "destinataire de diffusion"
        verbose_name_plural = "destinataires de diffusion"
        ordering = ("created_at",)
        constraints = [
            # Exactement un des deux : un utilisateur de la plateforme ou un nom externe.
            models.CheckConstraint(
                condition=(Q(utilisateur__isnull=False) & Q(nom_externe=""))
                | (Q(utilisateur__isnull=True) & ~Q(nom_externe="")),
                name="destinataire_interne_ou_externe",
            ),
            models.UniqueConstraint(
                fields=["rapport", "utilisateur"],
                condition=Q(deleted_at__isnull=True),
                name="destinataire_un_actif_par_utilisateur",
            ),
        ]

    def __str__(self) -> str:
        return self.nom_externe or str(self.utilisateur_id)

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_destinataire(self)

    def save(self, *args: Any, **kwargs: Any) -> None:
        champs = kwargs.get("update_fields")
        self._champs_ecrits = None if champs is None else frozenset(champs)
        try:
            super().save(*args, **kwargs)
        finally:
            self._champs_ecrits = None


class Diffusion(_AjoutSeulModel):
    """Diffusion d'un rapport (D11) : pointe les versions exactes diffusées, immuable."""

    NOM_AJOUT_SEUL = "Une diffusion"

    mission = _mission_fk("diffusions_rapport")
    rapport = models.OneToOneField(
        Rapport, verbose_name="rapport", on_delete=models.PROTECT, related_name="diffusion"
    )
    version_rapport = models.ForeignKey(
        DocumentVersion,
        verbose_name="version du rapport",
        on_delete=models.PROTECT,
        related_name="+",
    )
    version_note = models.ForeignKey(
        DocumentVersion,
        verbose_name="version de la note",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    diffusee_le = models.DateTimeField("diffusée le", default=timezone.now)
    diffusee_par = _utilisateur_fk("diffusée par")
    message = models.TextField("message", blank=True)

    class Meta:
        verbose_name = "diffusion"
        verbose_name_plural = "diffusions"

    def __str__(self) -> str:
        return f"Diffusion du {self.diffusee_le:%d/%m/%Y}"

    def exiger_travaux_ouverts(self) -> None:
        from . import gardes

        gardes.controler_diffusion(self)


__all__ = [
    "AppreciationGlobale",
    "CategorieDestinataire",
    "DestinataireDiffusion",
    "Diffusion",
    "EvenementRapport",
    "Rapport",
    "RapportProvisoire",
    "ReponseRapport",
    "StatutRapport",
    "TypeEvenementRapport",
]
