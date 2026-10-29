from typing import Any, ClassVar

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q

from apps.core.exceptions import RegleMetierError
from apps.core.models import BaseModel
from apps.missions.models import Mission
from apps.signatures.models import Confirmation
from apps.users.models import User

from .exceptions import (
    ConsultationImmuableError,
    DocumentFigeError,
    GabaritFigeError,
    VersionFigeeError,
)
from .managers import (
    CHAMPS_DOCUMENT_FIGES,
    CHAMPS_GABARIT_FIGES,
    ConsultationAllManager,
    ConsultationManager,
    DocumentAllManager,
    DocumentManager,
    GabaritAllManager,
    GabaritManager,
    VersionAllManager,
    VersionManager,
    _nom,
    controler_version,
)
from .stockage import stockage_documents

_HEX64 = r"^[0-9a-f]{64}$"
_HEX64_OU_VIDE = r"^([0-9a-f]{64})?$"


class StatutGabarit(models.TextChoices):
    DEPOSE = "DEPOSE", "Déposé"
    ACTIF = "ACTIF", "Actif"
    ARCHIVE = "ARCHIVE", "Archivé"


class StatutGeneration(models.TextChoices):
    EN_ATTENTE = "EN_ATTENTE", "En attente"
    EN_COURS = "EN_COURS", "En cours"
    PRETE = "PRETE", "Prête"
    ECHEC = "ECHEC", "Échec"


class StatutPdf(models.TextChoices):
    NON_DEMANDE = "NON_DEMANDE", "Non demandé"
    EN_COURS = "EN_COURS", "En cours"
    PRET = "PRET", "Prêt"
    ECHEC = "ECHEC", "Échec"


class PorteeNumerotation(models.TextChoices):
    MISSION = "MISSION", "Par mission"
    ANNEE = "ANNEE", "Par année"


class FormatFichier(models.TextChoices):
    DOCX = "DOCX", "Word"
    PDF = "PDF", "PDF"


def _valeur(instance: models.Model, attname: str) -> Any:
    valeur = getattr(instance, attname)
    return valeur.name if isinstance(valeur, models.fields.files.FieldFile) else valeur


def _en_base(instance: models.Model, attnames: list[str]) -> dict[str, Any] | None:
    manager: Any = type(instance).all_objects  # type: ignore[attr-defined]
    return manager.filter(pk=instance.pk).values(*attnames).first()  # type: ignore[no-any-return]


class GabaritDocument(BaseModel):
    """One uploaded version of the Word template of a document type."""

    type_document = models.CharField("type de document", max_length=40)
    version = models.PositiveIntegerField("version")
    statut = models.CharField(
        "statut", max_length=10, choices=StatutGabarit, default=StatutGabarit.DEPOSE
    )
    fichier = models.FileField("fichier", storage=stockage_documents, max_length=200)
    nom_original = models.CharField("nom d'origine", max_length=255)
    taille = models.PositiveIntegerField("taille (octets)")
    empreinte = models.CharField("empreinte SHA-256", max_length=64)
    balises = models.JSONField("balises", default=list, blank=True)
    contrat_version = models.PositiveSmallIntegerField("version du contrat")
    provisoire = models.BooleanField("provisoire", default=False)
    commentaire = models.TextField("commentaire", blank=True)
    active_par = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    active_le = models.DateTimeField("activé le", null=True, blank=True)

    objects: ClassVar[GabaritManager] = GabaritManager()
    all_objects: ClassVar[GabaritAllManager] = GabaritAllManager()  # noqa: DJ012

    class Meta:
        ordering = ["type_document", "-version"]
        constraints = [
            models.UniqueConstraint(
                fields=["type_document", "version"], name="gabarit_type_version_unique"
            ),
            models.UniqueConstraint(
                fields=["type_document"],
                condition=Q(statut="ACTIF"),
                name="gabarit_un_seul_actif_par_type",
            ),
            models.CheckConstraint(
                condition=Q(empreinte__regex=_HEX64), name="gabarit_empreinte_sha256"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type_document} v{self.version}"

    def soft_delete(self, by: User) -> None:
        if self.statut == StatutGabarit.ACTIF:
            raise RegleMetierError("Un gabarit actif ne peut pas être supprimé : archivez-le.")
        super().soft_delete(by)

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            en_base = _en_base(self, sorted(CHAMPS_GABARIT_FIGES))
            if en_base is not None and any(
                _valeur(self, champ) != valeur for champ, valeur in en_base.items()
            ):
                raise GabaritFigeError
        super().save(*args, **kwargs)


class FormatNumerotation(BaseModel):
    """Numbering format of a document type, editable by the administrator."""

    type_document = models.CharField("type de document", max_length=40, unique=True)
    modele = models.CharField("modèle", max_length=80)
    portee = models.CharField(
        "portée", max_length=10, choices=PorteeNumerotation, default=PorteeNumerotation.MISSION
    )
    abreviation = models.CharField("abréviation", max_length=8)

    class Meta:
        ordering = ["type_document"]

    def __str__(self) -> str:
        return f"{self.type_document} : {self.modele}"

    def soft_delete(self, by: User) -> None:
        raise RegleMetierError("Un format de numérotation ne peut pas être supprimé.")


class Document(BaseModel):
    """A business document of one source object; its generated versions are kept."""

    type_document = models.CharField("type de document", max_length=40)
    mission = models.ForeignKey(Mission, on_delete=models.PROTECT, related_name="+")
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="+")
    object_id = models.UUIDField("objet")
    numero = models.CharField("numéro", max_length=40, unique=True)  # deleted rows included
    annee = models.PositiveSmallIntegerField("année")
    sequence = models.PositiveIntegerField("séquence")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["mission", "type_document"], name="document_mission_type")]
        constraints = [
            models.UniqueConstraint(
                fields=["type_document", "content_type", "object_id"],
                condition=Q(deleted_at__isnull=True),
                name="document_un_actif_par_objet",
            )
        ]

    objects: ClassVar[DocumentManager] = DocumentManager()
    all_objects: ClassVar[DocumentAllManager] = DocumentAllManager()  # noqa: DJ012

    def __str__(self) -> str:
        return self.numero

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            noms = [
                f.attname for f in self._meta.concrete_fields if f.name in CHAMPS_DOCUMENT_FIGES
            ]
            en_base = _en_base(self, noms)
            if en_base is not None and any(
                _valeur(self, n) != valeur for n, valeur in en_base.items()
            ):
                raise DocumentFigeError
        super().save(*args, **kwargs)


class DocumentVersion(BaseModel):
    """One generation of a document: final once ready (only PDF fields move afterwards)."""

    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="versions")
    numero_version = models.PositiveSmallIntegerField("numéro de version")
    statut = models.CharField(
        "statut", max_length=10, choices=StatutGeneration, default=StatutGeneration.EN_ATTENTE
    )
    gabarit = models.ForeignKey(GabaritDocument, on_delete=models.PROTECT, related_name="+")
    contexte = models.JSONField("contexte", encoder=DjangoJSONEncoder, default=dict, blank=True)
    empreinte_contexte = models.CharField("empreinte du contexte", max_length=64, blank=True)
    confirmation = models.ForeignKey(
        Confirmation, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    demandee_par = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    fichier_docx = models.FileField(
        "fichier Word", storage=stockage_documents, max_length=200, blank=True
    )
    fichier_pdf = models.FileField(
        "fichier PDF", storage=stockage_documents, max_length=200, blank=True
    )
    empreinte_docx = models.CharField("empreinte Word", max_length=64, blank=True)
    empreinte_pdf = models.CharField("empreinte PDF", max_length=64, blank=True)
    taille_docx = models.PositiveIntegerField("taille Word (octets)", null=True, blank=True)
    taille_pdf = models.PositiveIntegerField("taille PDF (octets)", null=True, blank=True)
    statut_pdf = models.CharField(
        "statut du PDF", max_length=12, choices=StatutPdf, default=StatutPdf.NON_DEMANDE
    )
    genere_le = models.DateTimeField("généré le", null=True, blank=True)
    pdf_le = models.DateTimeField("PDF produit le", null=True, blank=True)
    erreur = models.TextField("erreur", blank=True)
    erreur_pdf = models.TextField("erreur PDF", blank=True)
    debut_traitement = models.DateTimeField("début du traitement", null=True, blank=True)

    objects: ClassVar[VersionManager] = VersionManager()
    all_objects: ClassVar[VersionAllManager] = VersionAllManager()  # noqa: DJ012

    class Meta:
        ordering = ["document", "-numero_version"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "numero_version"], name="version_numero_unique"
            ),
            models.CheckConstraint(
                condition=Q(empreinte_docx__regex=_HEX64_OU_VIDE), name="version_empreinte_docx"
            ),
            models.CheckConstraint(
                condition=Q(empreinte_pdf__regex=_HEX64_OU_VIDE), name="version_empreinte_pdf"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.document_id} v{self.numero_version}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding:
            demandes = set(kwargs.get("update_fields") or ())
            champs = [
                f.attname
                for f in self._meta.concrete_fields
                if not demandes or f.name in demandes or f.attname in demandes
            ]
            en_base = _en_base(self, [f.attname for f in self._meta.concrete_fields])
            if en_base is not None:
                controler_version(
                    {_nom(k): v for k, v in en_base.items()},
                    {_nom(n): _valeur(self, n) for n in champs},
                )
        super().save(*args, **kwargs)

    def soft_delete(self, by: User) -> None:
        raise VersionFigeeError


class ConsultationDocument(BaseModel):
    """Append-only trace of who opened or downloaded a version or a template."""

    version = models.ForeignKey(
        DocumentVersion, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    gabarit = models.ForeignKey(
        GabaritDocument, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    le = models.DateTimeField("le")
    format = models.CharField("format", max_length=4, choices=FormatFichier)  # noqa: A003
    adresse_ip = models.GenericIPAddressField("adresse IP", null=True, blank=True)

    objects: ClassVar[ConsultationManager] = ConsultationManager()
    all_objects: ClassVar[ConsultationAllManager] = ConsultationAllManager()  # noqa: DJ012

    class Meta:
        ordering = ["-le"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(version__isnull=False) & Q(gabarit__isnull=True))
                | (Q(version__isnull=True) & Q(gabarit__isnull=False)),
                name="consultation_une_seule_cible",
            )
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self._state.adding or kwargs.get("force_update") or kwargs.get("update_fields"):
            raise ConsultationImmuableError
        super().save(*args, **kwargs)

    def soft_delete(self, by: User) -> None:
        raise ConsultationImmuableError
