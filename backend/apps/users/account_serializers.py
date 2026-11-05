from typing import Any

from django.contrib.auth.validators import ASCIIUsernameValidator
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import empty

from .models import DelegationGestionComptes, Role, User
from .provisioning import CSV_MAX_BYTES, LigneIgnoree, RapportImport
from .services import PROFILE_FIELDS, ROLE_INVALIDE, ROLE_OBLIGATOIRE, actions_compte

MSG_ROLE = "Utilisez l'action « Changer le rôle »."
MSG_IDENTIFIANT = "L'identifiant ne peut pas être modifié."
MSG_ACTIF = "Utilisez les actions « Désactiver » et « Réactiver »."
MSG_AUTRE = "Champ non modifiable."
FICHIER_TROP_GROS = "Le fichier dépasse 1 Mo."
FICHIER_TYPE = "Le fichier doit être un fichier CSV (.csv)."
TYPES_CSV = frozenset(
    {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "text/plain",
        "application/octet-stream",
        "",
    }
)


def message_champ_refuse(champ: str) -> str:
    return {"role": MSG_ROLE, "username": MSG_IDENTIFIANT, "is_active": MSG_ACTIF}.get(
        champ, MSG_AUTRE
    )


class UserRefSerializer(serializers.ModelSerializer[User]):
    nom_complet = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ("id", "username", "nom_complet")
        read_only_fields = fields


class ActionsCompteSerializer(serializers.Serializer[dict[str, bool]]):
    """Actions que l'utilisateur connecté (administrateur ou délégué) peut effectuer sur le
    compte."""

    modifier_profil = serializers.BooleanField()
    desactiver = serializers.BooleanField()
    reactiver = serializers.BooleanField()
    reinitialiser_mot_de_passe = serializers.BooleanField()
    desactiver_otp = serializers.BooleanField()
    modifier_courriel = serializers.BooleanField()
    modifier_direction = serializers.BooleanField()
    changer_role = serializers.BooleanField()


class CompteUtilisateurListeSerializer(serializers.ModelSerializer[User]):
    nom_complet = serializers.CharField(read_only=True)
    direction_libelle = serializers.CharField(read_only=True, allow_null=True)
    en_attente_connexion = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields: tuple[str, ...] = (
            "id",
            "username",
            "nom_complet",
            "email",
            "role",
            "direction_code",
            "direction_libelle",
            "fonction",
            "matricule",
            "is_active",
            "origine",
            "en_attente_connexion",
            "date_joined",
        )
        read_only_fields = fields


class CompteUtilisateurSerializer(CompteUtilisateurListeSerializer):
    desactive_par = UserRefSerializer(read_only=True, allow_null=True)
    actions = serializers.SerializerMethodField()

    class Meta(CompteUtilisateurListeSerializer.Meta):
        fields: tuple[str, ...] = (
            *CompteUtilisateurListeSerializer.Meta.fields,
            "first_name",
            "last_name",
            "premiere_connexion_le",
            "desactive_le",
            "desactive_par",
            "motif_desactivation",
            "doit_changer_mot_de_passe",
            "mot_de_passe_expire_le",
            "verrouille_jusqu_a",
            "otp_connexion_actif",
            "actions",
        )
        read_only_fields = fields

    @extend_schema_field(ActionsCompteSerializer)
    def get_actions(self, obj: User) -> dict[str, bool]:
        return actions_compte(obj, self.context["request"].user)


class ProfilUtilisateurSerializer(serializers.Serializer[dict[str, str]]):
    """Champs de profil modifiables ; tout autre champ est refusé explicitement.

    Droit requis par champ modifié (administrateur ou délégué) : nom, prénom, matricule et
    fonction = « créer des comptes » ; courriel = « réinitialiser les mots de passe » ;
    direction = « changer les rôles »."""

    matricule = serializers.CharField(max_length=32, allow_blank=True)
    direction_code = serializers.CharField(max_length=16, allow_blank=True)
    fonction = serializers.CharField(max_length=128, allow_blank=True)
    email = serializers.EmailField(max_length=254, allow_blank=True)
    first_name = serializers.CharField(max_length=150, allow_blank=True)
    last_name = serializers.CharField(max_length=150, allow_blank=True)

    def to_internal_value(self, data: Any) -> Any:
        if hasattr(data, "keys"):
            refused = {
                str(key): [message_champ_refuse(str(key))]
                for key in list(data)
                if key not in PROFILE_FIELDS
            }
            if refused:
                raise serializers.ValidationError(refused)
        return super().to_internal_value(data)


class CreationCompteSerializer(serializers.Serializer[dict[str, Any]]):
    """Nouvel agent : le rôle est obligatoire ; le mot de passe est toujours généré."""

    # ASCII only (AUTH-11): no look-alike of another account (ɡ, full-width letters...).
    username = serializers.CharField(max_length=150, validators=[ASCIIUsernameValidator()])
    email = serializers.EmailField(max_length=254, required=False, allow_blank=True, default="")
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    role = serializers.ChoiceField(
        choices=Role.choices,
        error_messages={
            "required": ROLE_OBLIGATOIRE,
            "null": ROLE_OBLIGATOIRE,
            "invalid_choice": "Choisissez un rôle dans la liste.",
        },
    )
    matricule = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    direction_code = serializers.CharField(
        max_length=16, required=False, allow_blank=True, default=""
    )
    fonction = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    envoyer_courriel = serializers.BooleanField(
        default=True,
        help_text=(
            "Confier au service d'envoi le courriel de bienvenue avec le mot de passe "
            "temporaire. Sinon (ou si l'envoi n'est pas configuré ou pas disponible), le mot "
            "de passe est renvoyé une seule fois dans la réponse."
        ),
    )


class ChangementRoleSerializer(serializers.Serializer[dict[str, str]]):
    role = serializers.ChoiceField(
        choices=Role.choices,
        help_text=(
            "Seul un administrateur attribue les rôles Administrateur, RAI et Direction générale."
        ),
        error_messages={
            "required": ROLE_OBLIGATOIRE,
            "null": ROLE_OBLIGATOIRE,
            "invalid_choice": ROLE_INVALIDE,
        },
    )


class DelegationGestionComptesSerializer(serializers.ModelSerializer[DelegationGestionComptes]):
    """Droits de gestion des comptes délégués à un agent (lecture et écriture : ADMIN)."""

    creer = serializers.BooleanField(help_text="Créer des comptes.")
    reinitialiser = serializers.BooleanField(
        help_text="Réinitialiser les mots de passe et désactiver le code de connexion."
    )
    roles = serializers.BooleanField(help_text="Changer les rôles (et la direction).")
    desactiver = serializers.BooleanField(help_text="Désactiver et réactiver des comptes.")
    accorde_par = UserRefSerializer(read_only=True, allow_null=True)
    accorde_le = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = DelegationGestionComptes
        fields = ("creer", "reinitialiser", "roles", "desactiver", "accorde_par", "accorde_le")
        read_only_fields = ("accorde_par", "accorde_le")


class ReinitialisationCompteSerializer(serializers.Serializer[dict[str, bool]]):
    envoyer_courriel = serializers.BooleanField(
        default=True,
        help_text=(
            "Confier au service d'envoi le courriel du nouveau mot de passe temporaire. Sinon "
            "(ou si l'envoi n'est pas configuré ou pas disponible), il est renvoyé une seule "
            "fois dans la réponse."
        ),
    )


class MotDePasseTemporaireSerializer(serializers.Serializer[dict[str, Any]]):
    """Résultat d'une création ou d'une réinitialisation (réponse `Cache-Control: no-store`)."""

    compte = CompteUtilisateurSerializer()
    courriel_envoye = serializers.BooleanField(
        help_text=(
            "Vrai : le courriel est confié au service d'envoi (il part en différé ; un échec "
            "d'envoi est journalisé et demande une nouvelle réinitialisation)."
        )
    )
    mot_de_passe_temporaire = serializers.CharField(
        allow_null=True,
        help_text=(
            "Affiché une seule fois, jamais relisible ensuite ; null quand il part par courriel."
        ),
    )


class MotifDesactivationSerializer(serializers.Serializer[dict[str, str]]):
    motif = serializers.CharField(
        min_length=1,
        max_length=2000,
        trim_whitespace=True,
        error_messages={
            "required": "Le motif est obligatoire.",
            "blank": "Le motif est obligatoire.",
            "null": "Le motif est obligatoire.",
        },
    )


class DefaultTrueBooleanField(serializers.BooleanField):
    """Valeur multipart absente = défaut (les formulaires HTML omettent le champ)."""

    default_empty_html = empty


class ImportCsvSerializer(serializers.Serializer[dict[str, Any]]):
    fichier = serializers.FileField()

    def validate_fichier(self, fichier: Any) -> Any:
        if fichier.size > CSV_MAX_BYTES:
            raise serializers.ValidationError(FICHIER_TROP_GROS)
        nom = str(fichier.name or "").lower()
        type_mime = str(fichier.content_type or "").split(";")[0].strip().lower()
        if not nom.endswith(".csv") and type_mime not in TYPES_CSV:
            raise serializers.ValidationError(FICHIER_TYPE)
        return fichier

    dry_run = DefaultTrueBooleanField(
        default=True, help_text="Simulation sans écriture (par défaut)."
    )
    envoyer_courriel = DefaultTrueBooleanField(
        default=True,
        help_text=(
            "Envoyer à chaque compte créé son courriel de bienvenue avec son mot de passe "
            "temporaire (par défaut). Les mots de passe qui ne partent pas par courriel vont "
            "dans un fichier téléchargeable une seule fois."
        ),
    )


class LigneImportIgnoreeSerializer(serializers.Serializer[LigneIgnoree]):
    ligne = serializers.IntegerField()
    identifiant = serializers.CharField()
    motif = serializers.CharField()


class RapportImportSerializer(serializers.Serializer[RapportImport]):
    dry_run = serializers.BooleanField()
    crees = serializers.ListField(child=serializers.CharField())
    ignores = LigneImportIgnoreeSerializer(many=True)
    fichier_mots_de_passe_id = serializers.UUIDField(
        allow_null=True,
        help_text=(
            "Import CSV appliqué : fichier des mots de passe temporaires non envoyés par "
            "courriel, à télécharger une seule fois, sous 24 h, par l'auteur de l'import "
            "(`GET /user-accounts/import-passwords/{id}/`) ; null sinon."
        ),
    )
