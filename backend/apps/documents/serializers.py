"""Sérialiseurs de l'API des documents.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI
consommés par le frontend. Le contexte JSON d'une version n'est jamais exposé, ni les clés de
stockage des fichiers : un fichier ne sort que par les routes `download` et `file`.
"""

from typing import Any, cast

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.core.exceptions import RegleMetierError
from apps.missions.serializers import MissionResumeSerializer
from apps.signatures.serializers import ConfirmationResumeSerializer
from apps.users.models import User
from apps.users.serializers import UtilisateurResumeSerializer

from .models import (
    ConsultationDocument,
    Document,
    DocumentVersion,
    FormatNumerotation,
    GabaritDocument,
    PorteeNumerotation,
    StatutPdf,
)
from .moteur.contrats import Champ, TypeChamp
from .moteur.registre import type_document as type_enregistre
from .numerotation import apercu_numero

TYPE_CHAMP_CHOICES = [(t.value, t.value) for t in TypeChamp]


def libelle_type(code: str) -> str:
    try:
        return type_enregistre(code).libelle
    except RegleMetierError:
        return code


class ChampContratSerializer(serializers.Serializer[Champ]):
    nom = serializers.CharField()
    type = serializers.ChoiceField(choices=TYPE_CHAMP_CHOICES)  # noqa: A003
    description = serializers.CharField()
    enfants = serializers.SerializerMethodField()

    @extend_schema_field({"type": "array", "items": {"$ref": "#/components/schemas/ChampContrat"}})
    def get_enfants(self, obj: Champ) -> list[dict[str, Any]]:
        return cast(
            list[dict[str, Any]], cast(Any, ChampContratSerializer)(obj.enfants, many=True).data
        )


class GabaritResumeSerializer(serializers.ModelSerializer[GabaritDocument]):
    class Meta:
        model = GabaritDocument
        fields = ("id", "version", "statut", "provisoire", "active_le")
        read_only_fields = fields


class GabaritRefSerializer(serializers.ModelSerializer[GabaritDocument]):
    class Meta:
        model = GabaritDocument
        fields = ("id", "version", "provisoire")
        read_only_fields = fields


class FormatNumerotationSerializer(serializers.ModelSerializer[FormatNumerotation]):
    apercu = serializers.SerializerMethodField()

    class Meta:
        model = FormatNumerotation
        fields = ("type_document", "modele", "portee", "abreviation", "apercu")
        read_only_fields = fields

    def get_apercu(self, obj: FormatNumerotation) -> str | None:
        try:
            return apercu_numero(obj.modele, obj.portee, obj.abreviation)
        except (KeyError, IndexError, ValueError):
            return None


class FormatNumerotationEcritureSerializer(serializers.Serializer[dict[str, Any]]):
    modele = serializers.CharField(max_length=80, required=False)
    portee = serializers.ChoiceField(choices=PorteeNumerotation.choices, required=False)
    abreviation = serializers.CharField(max_length=8, required=False)


class ApercuFormatSerializer(serializers.Serializer[dict[str, Any]]):
    modele = serializers.CharField(max_length=80)
    portee = serializers.CharField(max_length=10)
    abreviation = serializers.CharField(max_length=8)


class ApercuNumeroSerializer(serializers.Serializer[dict[str, Any]]):
    numero = serializers.CharField(allow_null=True)
    errors = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))  # type: ignore[assignment]


class TypeDocumentSerializer(serializers.Serializer[dict[str, Any]]):
    """Entrée du registre : `champs` = contrat complet (blocs communs compris)."""

    code = serializers.CharField()
    libelle = serializers.CharField()
    etape = serializers.IntegerField(allow_null=True)
    etape_romain = serializers.CharField(allow_null=True)
    contrat_version = serializers.IntegerField()
    champs = ChampContratSerializer(many=True)
    gabarit_actif = GabaritResumeSerializer(allow_null=True)
    format_numerotation = FormatNumerotationSerializer()


class GabaritDocumentSerializer(serializers.ModelSerializer[GabaritDocument]):
    type_document_libelle = serializers.SerializerMethodField()
    created_by = UtilisateurResumeSerializer(read_only=True, allow_null=True)
    active_par = UtilisateurResumeSerializer(read_only=True, allow_null=True)

    class Meta:
        model = GabaritDocument
        fields = (
            "id",
            "type_document",
            "type_document_libelle",
            "version",
            "statut",
            "nom_original",
            "taille",
            "empreinte",
            "balises",
            "contrat_version",
            "provisoire",
            "commentaire",
            "created_by",
            "created_at",
            "active_par",
            "active_le",
        )
        read_only_fields = fields

    def get_type_document_libelle(self, obj: GabaritDocument) -> str:
        return libelle_type(obj.type_document)


class GabaritDepotSerializer(serializers.Serializer[dict[str, Any]]):
    type_document = serializers.CharField(max_length=40)
    fichier = serializers.FileField(allow_empty_file=False)
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")


class GenerationSerializer(serializers.Serializer[dict[str, Any]]):
    type_document = serializers.CharField(max_length=40)
    objet = serializers.UUIDField()

    def validate_type_document(self, valeur: str) -> str:
        try:
            type_enregistre(valeur)
        except RegleMetierError as exc:
            raise ValidationError(exc.message) from exc
        return valeur


class FormatQuerySerializer(serializers.Serializer[dict[str, Any]]):
    format = serializers.ChoiceField(choices=["docx", "pdf"], default="docx")  # noqa: A003


class MissionQuerySerializer(serializers.Serializer[dict[str, Any]]):
    mission = serializers.UUIDField()


class VersionDocumentResumeSerializer(serializers.ModelSerializer[DocumentVersion]):
    class Meta:
        model = DocumentVersion
        fields = ("id", "numero_version", "statut", "statut_pdf", "genere_le")
        read_only_fields = fields


class DocumentVersionSerializer(serializers.ModelSerializer[DocumentVersion]):
    gabarit = GabaritRefSerializer(read_only=True)
    demandee_par = UtilisateurResumeSerializer(read_only=True)
    confirmation = ConfirmationResumeSerializer(read_only=True, allow_null=True)
    peut_relancer_pdf = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = (
            "id",
            "document",
            "numero_version",
            "statut",
            "statut_pdf",
            "gabarit",
            "demandee_par",
            "created_at",
            "genere_le",
            "pdf_le",
            "empreinte_docx",
            "empreinte_pdf",
            "taille_docx",
            "taille_pdf",
            "erreur",
            "erreur_pdf",
            "confirmation",
            "peut_relancer_pdf",
        )
        read_only_fields = fields

    def get_peut_relancer_pdf(self, obj: DocumentVersion) -> bool:
        if obj.statut_pdf != StatutPdf.ECHEC:
            return False
        request = self.context.get("request")
        if request is None:
            return False
        cache: dict[Any, bool] = cast(dict[str, Any], self.context).setdefault("_peut_generer", {})
        if obj.document_id not in cache:
            from .permissions import peut_generer

            cache[obj.document_id] = peut_generer(cast(User, request.user), obj.document)
        return cache[obj.document_id]


class DocumentListeSerializer(serializers.ModelSerializer[Document]):
    type_document_libelle = serializers.SerializerMethodField()
    mission = MissionResumeSerializer(read_only=True)
    derniere_version = serializers.SerializerMethodField()
    nombre_versions = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields: tuple[str, ...] = (
            "id",
            "type_document",
            "type_document_libelle",
            "numero",
            "mission",
            "derniere_version",
            "nombre_versions",
        )
        read_only_fields = fields

    def get_type_document_libelle(self, obj: Document) -> str:
        return libelle_type(obj.type_document)

    def _versions(self, obj: Document) -> list[DocumentVersion]:
        return list(obj.versions.all())  # prefetched by the views

    @extend_schema_field(VersionDocumentResumeSerializer(allow_null=True))
    def get_derniere_version(self, obj: Document) -> dict[str, Any] | None:
        versions = self._versions(obj)
        if not versions:
            return None
        derniere = max(versions, key=lambda v: v.numero_version)
        return cast(dict[str, Any], VersionDocumentResumeSerializer(derniere).data)

    def get_nombre_versions(self, obj: Document) -> int:
        return len(self._versions(obj))


class DocumentSerializer(DocumentListeSerializer):
    objet_id = serializers.UUIDField(source="object_id", read_only=True)
    versions = serializers.SerializerMethodField()

    class Meta(DocumentListeSerializer.Meta):
        fields = (*DocumentListeSerializer.Meta.fields, "objet_id", "versions")
        read_only_fields = fields

    @extend_schema_field(DocumentVersionSerializer(many=True))
    def get_versions(self, obj: Document) -> list[dict[str, Any]]:
        triees = sorted(self._versions(obj), key=lambda v: -v.numero_version)
        return cast(
            list[dict[str, Any]],
            DocumentVersionSerializer(triees, many=True, context=self.context).data,
        )


class DocumentDisponibleSerializer(serializers.Serializer[dict[str, Any]]):
    type_document = serializers.CharField()
    libelle = serializers.CharField()
    etape = serializers.IntegerField(allow_null=True)
    objet_id = serializers.UUIDField()
    document = DocumentListeSerializer(allow_null=True)
    peut_generer = serializers.BooleanField()
    raison = serializers.CharField(allow_null=True)
    en_cours = serializers.BooleanField()


class ConsultationSerializer(serializers.ModelSerializer[ConsultationDocument]):
    utilisateur = UtilisateurResumeSerializer(read_only=True)

    class Meta:
        model = ConsultationDocument
        fields = ("utilisateur", "le", "format", "adresse_ip")
        read_only_fields = fields
