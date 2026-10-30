"""Sérialiseurs de l'API de la communication.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI. Les
droits affichés (`actions_possibles`) viennent de `droits.py`, dont les contextes (par mission)
sont calculés UNE FOIS par requête (clé `communication` du contexte du sérialiseur).
Le DG et l'audité ne reçoivent que `RapportDiffuse` : aucune section interne, aucun événement,
aucun motif de renvoi.
"""

from typing import Any, cast
from uuid import UUID

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.constats.models import Constat
from apps.documents.models import DocumentVersion, StatutGeneration, StatutPdf
from apps.missions.models import Mission
from apps.missions.serializers import CleRelation
from apps.signatures.models import ModeSignatureParametre, TypeDocumentSignable
from apps.signatures.parametres import MODES_ELECTRONIQUES, exigences
from apps.signatures.serializers import ConfirmationResumeSerializer
from apps.users.models import User
from apps.users.serializers import UtilisateurResumeSerializer

from . import droits
from .gardes import CHAMPS_REDACTION
from .models import (
    AppreciationGlobale,
    CategorieDestinataire,
    DestinataireDiffusion,
    Diffusion,
    EvenementRapport,
    Rapport,
    RapportProvisoire,
    ReponseRapport,
    StatutRapport,
    TypeEvenementRapport,
)
from .permissions import STATUTS_DIFFUSES
from .services._versions import version_finale

MSG_CONFIRME = "Cochez la case de confirmation."
TYPE_DOCUMENT_PROVISOIRE = "RAPPORT_PROVISOIRE"
FORMATS = ("pdf", "docx")
DOCUMENTS = ("rapport", "note")


def _acteur(serializer: serializers.BaseSerializer[Any]) -> User:
    return cast(User, serializer.context["request"].user)


def _contexte_rapport(
    serializer: serializers.BaseSerializer[Any], mission: Mission
) -> droits.ContexteRapport:
    contexte = cast(dict[str, Any], serializer.context)
    caches: dict[UUID, droits.ContexteRapport] = contexte.setdefault("communication", {})
    if mission.pk not in caches:
        caches[mission.pk] = droits.contexte_rapport(mission, _acteur(serializer))
    return caches[mission.pk]


def _contexte_provisoire(
    serializer: serializers.BaseSerializer[Any], mission: Mission
) -> droits.ContexteProvisoire:
    contexte = cast(dict[str, Any], serializer.context)
    caches: dict[UUID, droits.ContexteProvisoire] = contexte.setdefault("provisoire", {})
    if mission.pk not in caches:
        caches[mission.pk] = droits.contexte_provisoire(mission, _acteur(serializer))
    return caches[mission.pk]


# --------------------------------------------------------------------------- résumés


class VersionRapportResumeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    numero = serializers.IntegerField(source="numero_version")
    statut = serializers.ChoiceField(choices=StatutGeneration.choices)
    statut_pdf = serializers.ChoiceField(choices=StatutPdf.choices)


class RapportProvisoireResumeSerializer(serializers.ModelSerializer[RapportProvisoire]):
    class Meta:
        model = RapportProvisoire
        fields = ("id", "numero", "transmis_le", "date_limite_reponses")
        read_only_fields = fields


class DiffusionResumeSerializer(serializers.ModelSerializer[Diffusion]):
    diffusee_par = UtilisateurResumeSerializer(read_only=True)
    version_rapport = VersionRapportResumeSerializer(read_only=True)
    version_note = VersionRapportResumeSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Diffusion
        fields = (
            "id",
            "diffusee_le",
            "diffusee_par",
            "message",
            "version_rapport",
            "version_note",
        )
        read_only_fields = fields


class EvenementRapportSerializer(serializers.ModelSerializer[EvenementRapport]):
    type = serializers.ChoiceField(choices=TypeEvenementRapport.choices, read_only=True)
    par = UtilisateurResumeSerializer(read_only=True)
    statut_avant = serializers.ChoiceField(
        choices=StatutRapport.choices, read_only=True, allow_blank=True
    )
    statut_apres = serializers.ChoiceField(choices=StatutRapport.choices, read_only=True)

    class Meta:
        model = EvenementRapport
        fields = ("id", "type", "par", "le", "motif", "statut_avant", "statut_apres")
        read_only_fields = fields


# --------------------------------------------------------------------------- rapport


class RapportSerializer(serializers.ModelSerializer[Rapport]):
    """Rapport vu de l'équipe d'audit et du RAI."""

    statut = serializers.ChoiceField(choices=StatutRapport.choices, read_only=True)
    appreciation_globale = serializers.ChoiceField(
        choices=AppreciationGlobale.choices, read_only=True, allow_blank=True
    )
    mode_signature = serializers.ChoiceField(
        choices=ModeSignatureParametre.choices, read_only=True, allow_blank=True
    )
    confirmation_validation = ConfirmationResumeSerializer(read_only=True, allow_null=True)
    signature_electronique_requise = serializers.SerializerMethodField()
    provisoire_courant = serializers.SerializerMethodField()
    version_finale = serializers.SerializerMethodField()
    diffusion = serializers.SerializerMethodField()
    evenements = EvenementRapportSerializer(many=True, read_only=True)
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = Rapport
        fields = (
            "id",
            "mission",
            "numero_version",
            "corrige_de",
            "motif_correction",
            "statut",
            "synthese",
            "appreciation_globale",
            "commentaire_appreciation",
            "contexte",
            "objectifs_texte",
            "perimetre_texte",
            "methodologie",
            "conclusion",
            "note_synthetique",
            "annexes_texte",
            "cycle",
            "soumis_par",
            "soumis_le",
            "empreinte_soumise",
            "valide_par",
            "valide_le",
            "confirmation_validation",
            "mode_signature",
            "signature_electronique_requise",
            "motif_renvoi",
            "provisoire_courant",
            "version_finale",
            "diffusion",
            "evenements",
            "actions_possibles",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_signature_electronique_requise(self, obj: Rapport) -> bool:
        """Mode figé à la validation ; avant elle, le mode en vigueur."""
        if obj.mode_signature:
            return obj.mode_signature in MODES_ELECTRONIQUES
        contexte = cast(dict[str, Any], self.context)
        if "electronique_courant" not in contexte:
            contexte["electronique_courant"] = exigences(
                TypeDocumentSignable.VALIDATION_RAPPORT
            ).electronique
        return bool(contexte["electronique_courant"])

    @extend_schema_field(RapportProvisoireResumeSerializer(allow_null=True))
    def get_provisoire_courant(self, obj: Rapport) -> dict[str, Any] | None:
        provisoires = list(obj.provisoires.all())
        if not provisoires:
            return None
        dernier = max(provisoires, key=lambda p: p.numero)
        return dict(RapportProvisoireResumeSerializer(dernier).data)

    @extend_schema_field(VersionRapportResumeSerializer(allow_null=True))
    def get_version_finale(self, obj: Rapport) -> dict[str, Any] | None:
        version: DocumentVersion | None
        if obj.statut in STATUTS_DIFFUSES:
            try:
                version = obj.diffusion.version_rapport
            except ObjectDoesNotExist:
                return None
        elif obj.statut == StatutRapport.VALIDE:
            version = version_finale(obj)
        else:
            return None
        return None if version is None else dict(VersionRapportResumeSerializer(version).data)

    @extend_schema_field(DiffusionResumeSerializer(allow_null=True))
    def get_diffusion(self, obj: Rapport) -> dict[str, Any] | None:
        try:
            diffusion = obj.diffusion
        except ObjectDoesNotExist:
            return None
        return dict(DiffusionResumeSerializer(diffusion).data)

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: Rapport) -> list[str]:
        return droits.actions_rapport(
            obj, _acteur(self), contexte=_contexte_rapport(self, obj.mission)
        )


class RapportDiffuseSerializer(serializers.ModelSerializer[Rapport]):
    """Rapport diffusé vu du DG et de l'audité : synthèse et appréciation, rien d'interne."""

    mission_reference = serializers.CharField(source="mission.reference", read_only=True)
    mission_titre = serializers.CharField(source="mission.titre", read_only=True)
    numero_document = serializers.SerializerMethodField()
    appreciation_globale = serializers.ChoiceField(
        choices=AppreciationGlobale.choices, read_only=True, allow_blank=True
    )
    diffuse_le = serializers.SerializerMethodField()
    mention_correction = serializers.SerializerMethodField()
    mon_accuse_reception = serializers.SerializerMethodField()
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = Rapport
        fields = (
            "id",
            "mission_reference",
            "mission_titre",
            "numero_version",
            "numero_document",
            "valide_le",
            "diffuse_le",
            "synthese",
            "appreciation_globale",
            "mention_correction",
            "mon_accuse_reception",
            "actions_possibles",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_numero_document(self, obj: Rapport) -> str:
        try:
            return str(obj.diffusion.version_rapport.document.numero)
        except ObjectDoesNotExist:
            return ""

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_diffuse_le(self, obj: Rapport) -> Any:
        try:
            return serializers.DateTimeField().to_representation(obj.diffusion.diffusee_le)
        except ObjectDoesNotExist:
            return None

    @extend_schema_field(serializers.CharField())
    def get_mention_correction(self, obj: Rapport) -> str:
        if obj.statut == StatutRapport.REMPLACE:
            return "Ce rapport a été remplacé par un rapport corrigé."
        if obj.corrige_de_id is not None:
            return (
                f"Rapport corrigé (version {obj.numero_version}) : {obj.motif_correction}".strip()
            )
        return ""

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_mon_accuse_reception(self, obj: Rapport) -> Any:
        contexte = cast(dict[str, Any], self.context)
        if "accuses" not in contexte:
            contexte["accuses"] = dict(
                DestinataireDiffusion.objects.filter(utilisateur=_acteur(self)).values_list(
                    "rapport_id", "accuse_reception_le"
                )
            )
        accuse = contexte["accuses"].get(obj.pk)
        return None if accuse is None else serializers.DateTimeField().to_representation(accuse)

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: Rapport) -> list[str]:
        return droits.actions_rapport(
            obj, _acteur(self), contexte=_contexte_rapport(self, obj.mission)
        )


class RapportCreationRequestSerializer(serializers.Serializer[Any]):
    mission = CleRelation(queryset=Mission.objects.all())


class RapportModificationRequestSerializer(serializers.Serializer[Any]):
    """Sections saisies (D5) ; tous les champs sont facultatifs."""

    synthese = serializers.CharField(required=False, allow_blank=True)
    appreciation_globale = serializers.ChoiceField(
        choices=AppreciationGlobale.choices, required=False, allow_blank=True
    )
    commentaire_appreciation = serializers.CharField(required=False, allow_blank=True)
    contexte = serializers.CharField(required=False, allow_blank=True)
    objectifs_texte = serializers.CharField(required=False, allow_blank=True)
    perimetre_texte = serializers.CharField(required=False, allow_blank=True)
    methodologie = serializers.CharField(required=False, allow_blank=True)
    conclusion = serializers.CharField(required=False, allow_blank=True)
    note_synthetique = serializers.CharField(required=False, allow_blank=True)
    annexes_texte = serializers.CharField(required=False, allow_blank=True)


assert set(RapportModificationRequestSerializer().fields) == set(CHAMPS_REDACTION)  # noqa: S101


class _ConfirmeMixin(serializers.Serializer[Any]):
    confirme = serializers.BooleanField(
        help_text="Doit être vrai : la confirmation explicite de l'utilisateur."
    )

    def validate_confirme(self, valeur: bool) -> bool:
        if not valeur:
            raise serializers.ValidationError(MSG_CONFIRME)
        return valeur


class ValidationRequestSerializer(_ConfirmeMixin):
    """Validation du rapport : `confirme` doit être vrai (jamais pré-coché)."""


class MotifRequestSerializer(serializers.Serializer[Any]):
    motif = serializers.CharField(allow_blank=True)


class DiffusionRequestSerializer(serializers.Serializer[Any]):
    message = serializers.CharField(required=False, allow_blank=True, default="")


class TransmissionRequestSerializer(serializers.Serializer[Any]):
    delai_jours = serializers.IntegerField(required=False, default=15)


class TelechargementQuerySerializer(serializers.Serializer[Any]):
    format = serializers.ChoiceField(choices=FORMATS, default="pdf")  # noqa: A003
    document = serializers.ChoiceField(choices=DOCUMENTS, default="rapport")


class TexteValidationSerializer(serializers.Serializer[Any]):
    texte = serializers.CharField(help_text="Texte exact que le RAI confirme.")
    mode = serializers.ChoiceField(choices=ModeSignatureParametre.choices)
    confirmation_requise = serializers.BooleanField()
    signature_electronique_requise = serializers.BooleanField()


# --------------------------------------------------------------------------- provisoire


class ConstatProvisoireSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    reference = serializers.CharField()
    titre = serializers.CharField()
    entite = serializers.CharField()
    niveau = serializers.CharField(allow_blank=True)
    a_repondre = serializers.BooleanField()


class VersionProvisoireSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    statut = serializers.ChoiceField(choices=StatutGeneration.choices)


class RapportProvisoireSerializer(serializers.ModelSerializer[RapportProvisoire]):
    transmis_par = serializers.PrimaryKeyRelatedField[User](read_only=True)
    constats = serializers.SerializerMethodField()
    version_document = serializers.SerializerMethodField()

    class Meta:
        model = RapportProvisoire
        fields = (
            "id",
            "rapport",
            "mission",
            "numero",
            "transmis_le",
            "transmis_par",
            "date_limite_reponses",
            "constats",
            "version_document",
            "empreinte",
        )
        read_only_fields = fields

    @extend_schema_field(ConstatProvisoireSerializer(many=True))
    def get_constats(self, obj: RapportProvisoire) -> list[dict[str, Any]]:
        from .permissions import constats_du_provisoire

        utilisateur = _acteur(self)
        lignes = [c for c in (obj.instantane or {}).get("constats") or []]
        constats = {
            c.reference: c
            for c in constats_du_provisoire(utilisateur).filter(
                mission_id=obj.mission_id, reference__in=[ligne["reference"] for ligne in lignes]
            )
        }
        a_repondre = set(droits.constats_a_repondre(utilisateur, obj))
        sortie: list[dict[str, Any]] = []
        for ligne in lignes:
            constat: Constat | None = constats.get(ligne["reference"])
            if constat is None:
                continue
            sortie.append(
                {
                    "id": constat.pk,
                    "reference": ligne["reference"],
                    "titre": ligne.get("titre", ""),
                    "entite": ligne.get("entite", ""),
                    "niveau": ligne.get("niveau") or "",
                    "a_repondre": constat.pk in a_repondre,
                }
            )
        return [dict(ligne) for ligne in ConstatProvisoireSerializer(sortie, many=True).data]

    @extend_schema_field(VersionProvisoireSerializer(allow_null=True))
    def get_version_document(self, obj: RapportProvisoire) -> dict[str, Any] | None:
        version = (
            DocumentVersion.objects.filter(
                document__type_document=TYPE_DOCUMENT_PROVISOIRE,
                document__object_id=obj.pk,
                document__content_type=ContentType.objects.get_for_model(RapportProvisoire),
            )
            .order_by("-numero_version")
            .first()
        )
        return None if version is None else {"id": version.pk, "statut": version.statut}


class ReponseRapportSerializer(serializers.ModelSerializer[ReponseRapport]):
    auteur = UtilisateurResumeSerializer(read_only=True)
    confirmation = ConfirmationResumeSerializer(read_only=True)
    texte = serializers.CharField(source="confirmation.texte", read_only=True)

    class Meta:
        model = ReponseRapport
        fields = (
            "id",
            "provisoire",
            "constat",
            "auteur",
            "commentaire",
            "confirmation",
            "hors_delai",
            "texte",
        )
        read_only_fields = fields


class ReponseRapportRequestSerializer(_ConfirmeMixin):
    provisoire = CleRelation(queryset=RapportProvisoire.objects.all())
    constat = CleRelation(queryset=Constat.objects.all())
    commentaire = serializers.CharField(allow_blank=True)


class TexteReponseRapportSerializer(serializers.Serializer[Any]):
    texte = serializers.CharField(help_text="Texte exact que l'audité confirme.")
    date_limite_reponses = serializers.DateField()
    hors_delai = serializers.BooleanField()


# --------------------------------------------------------------------------- destinataires


class DestinataireSerializer(serializers.ModelSerializer[DestinataireDiffusion]):
    categorie = serializers.ChoiceField(choices=CategorieDestinataire.choices, read_only=True)
    utilisateur = serializers.PrimaryKeyRelatedField[User](read_only=True, allow_null=True)
    utilisateur_detail = UtilisateurResumeSerializer(
        source="utilisateur", read_only=True, allow_null=True
    )

    class Meta:
        model = DestinataireDiffusion
        fields = (
            "id",
            "rapport",
            "utilisateur",
            "utilisateur_detail",
            "nom_externe",
            "qualite",
            "categorie",
            "notifie_le",
            "premiere_consultation_le",
            "accuse_reception_le",
            "remis_hors_plateforme_le",
        )
        read_only_fields = fields


class DestinataireCreationRequestSerializer(serializers.Serializer[Any]):
    rapport = CleRelation(queryset=Rapport.objects.all())
    utilisateur = CleRelation(queryset=User.objects.all(), required=False, allow_null=True)
    nom_externe = serializers.CharField(required=False, allow_blank=True, default="")
    qualite = serializers.CharField(required=False, allow_blank=True, default="")
    categorie = serializers.ChoiceField(
        choices=CategorieDestinataire.choices, default=CategorieDestinataire.AUTRE
    )


class DestinataireModificationRequestSerializer(serializers.Serializer[Any]):
    nom_externe = serializers.CharField(required=False, allow_blank=True)
    qualite = serializers.CharField(required=False, allow_blank=True)
    categorie = serializers.ChoiceField(choices=CategorieDestinataire.choices, required=False)


class RemiseRequestSerializer(serializers.Serializer[Any]):
    le = serializers.DateField()
