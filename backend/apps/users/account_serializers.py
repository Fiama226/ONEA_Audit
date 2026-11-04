from typing import Any

from django.contrib.auth.validators import UnicodeUsernameValidator
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.fields import empty

from .models import DelegationGestionComptes, KeycloakSyncStatut, Role, User
from .provisioning import CSV_MAX_BYTES, EntreeAnnuaire, LigneIgnoree, RapportImport
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


class SyncKeycloakSerializer(serializers.Serializer[User]):
    """État de la propagation du compte vers Keycloak."""

    statut = serializers.ChoiceField(
        choices=KeycloakSyncStatut.choices, source="keycloak_sync_statut", read_only=True
    )
    erreur = serializers.CharField(source="keycloak_sync_erreur", read_only=True)
    derniere_tentative_le = serializers.DateTimeField(
        source="keycloak_sync_le", read_only=True, allow_null=True
    )
    tentatives = serializers.IntegerField(source="keycloak_sync_tentatives", read_only=True)
    manuel = serializers.BooleanField(
        source="keycloak_sync_manuel",
        read_only=True,
        help_text="Échec permanent : seule une relance manuelle peut le résoudre.",
    )


class ActionsCompteSerializer(serializers.Serializer[dict[str, bool]]):
    """Actions que l'utilisateur connecté (administrateur ou délégué) peut effectuer sur le
    compte."""

    modifier_profil = serializers.BooleanField()
    desactiver = serializers.BooleanField()
    reactiver = serializers.BooleanField()
    resynchroniser_profil = serializers.BooleanField()
    relancer_synchro_keycloak = serializers.BooleanField()
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
            "keycloak_sync_statut",
            "date_joined",
        )
        read_only_fields = fields


class CompteUtilisateurSerializer(CompteUtilisateurListeSerializer):
    keycloak_lie = serializers.SerializerMethodField()
    desactive_par = UserRefSerializer(read_only=True, allow_null=True)
    keycloak_sync = SyncKeycloakSerializer(source="*", read_only=True)
    actions = serializers.SerializerMethodField()

    class Meta(CompteUtilisateurListeSerializer.Meta):
        fields: tuple[str, ...] = (
            *CompteUtilisateurListeSerializer.Meta.fields,
            "first_name",
            "last_name",
            "keycloak_lie",
            "role_provisoire",
            "premiere_connexion_le",
            "profil_gere_localement",
            "desactive_le",
            "desactive_par",
            "motif_desactivation",
            "doit_changer_mot_de_passe",
            "mot_de_passe_expire_le",
            "verrouille_jusqu_a",
            "otp_connexion_actif",
            "keycloak_sync",
            "actions",
        )
        read_only_fields = fields

    @extend_schema_field(serializers.BooleanField())
    def get_keycloak_lie(self, obj: User) -> bool:
        return obj.keycloak_id is not None

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

    username = serializers.CharField(max_length=150, validators=[UnicodeUsernameValidator()])
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
            "Envoyer le courriel de bienvenue avec le mot de passe temporaire. Sinon (ou si "
            "l'envoi échoue), le mot de passe est renvoyé une seule fois dans la réponse."
        ),
    )


class ChangementRoleSerializer(serializers.Serializer[dict[str, str]]):
    role = serializers.ChoiceField(
        choices=Role.choices,
        help_text="Seul un administrateur attribue le rôle Administrateur.",
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
            "Envoyer le nouveau mot de passe temporaire par courriel. Sinon (ou si l'envoi "
            "échoue), il est renvoyé une seule fois dans la réponse."
        ),
    )


class MotDePasseTemporaireSerializer(serializers.Serializer[dict[str, Any]]):
    """Résultat d'une création ou d'une réinitialisation (réponse `Cache-Control: no-store`)."""

    compte = CompteUtilisateurSerializer()
    courriel_envoye = serializers.BooleanField()
    mot_de_passe_temporaire = serializers.CharField(
        allow_null=True,
        help_text=(
            "Affiché une seule fois, jamais relisible ensuite ; null quand il est parti par "
            "courriel."
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


class EntreeAnnuaireSerializer(serializers.Serializer[EntreeAnnuaire]):
    keycloak_id = serializers.UUIDField()
    username = serializers.CharField()
    email = serializers.CharField()
    nom_complet = serializers.CharField()
    direction = serializers.CharField()
    fonction = serializers.CharField()
    compte_id = serializers.IntegerField(allow_null=True)


class ImportAnnuaireSerializer(serializers.Serializer[dict[str, Any]]):
    keycloak_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1, max_length=50)


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


class LigneImportIgnoreeSerializer(serializers.Serializer[LigneIgnoree]):
    ligne = serializers.IntegerField(allow_null=True)
    identifiant = serializers.CharField()
    motif = serializers.CharField()


class RapportImportSerializer(serializers.Serializer[RapportImport]):
    dry_run = serializers.BooleanField()
    crees = serializers.ListField(child=serializers.CharField())
    mis_a_jour = serializers.ListField(child=serializers.CharField())
    ignores = LigneImportIgnoreeSerializer(many=True)
