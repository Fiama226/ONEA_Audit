from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .delegation import droits_effectifs
from .models import ActionTutoriel, User


class TutorielSerializer(serializers.Serializer[User]):
    """État du tutoriel d'accueil de l'utilisateur connecté."""

    version_vue = serializers.IntegerField(
        source="tutoriel_version_vue", allow_null=True, read_only=True
    )
    termine_le = serializers.DateTimeField(
        source="tutoriel_termine_le", allow_null=True, read_only=True
    )


class TutorielActionSerializer(serializers.Serializer[dict[str, object]]):
    action = serializers.ChoiceField(choices=ActionTutoriel.choices)
    version = serializers.IntegerField(min_value=1)


class DroitsGestionComptesSerializer(serializers.Serializer[dict[str, bool]]):
    """Droits effectifs de gestion des comptes (tous pour un administrateur)."""

    creer = serializers.BooleanField()
    reinitialiser = serializers.BooleanField()
    roles = serializers.BooleanField()
    desactiver = serializers.BooleanField()


class MeSerializer(serializers.ModelSerializer[User]):
    tutoriel = TutorielSerializer(source="*", read_only=True)
    gestion_comptes = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
            "direction_code",
            "fonction",
            "tutoriel",
            "otp_connexion_actif",
            "gestion_comptes",
        )
        read_only_fields = fields

    @extend_schema_field(DroitsGestionComptesSerializer)
    def get_gestion_comptes(self, obj: User) -> dict[str, bool]:
        return droits_effectifs(obj)


class UtilisateurResumeSerializer(serializers.ModelSerializer[User]):
    """Représentation minimale d'un utilisateur dans les réponses (annuaire, équipes)."""

    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "nom_complet", "role", "direction_code", "fonction")
        read_only_fields = fields

    def get_nom_complet(self, obj: User) -> str:
        return obj.get_full_name() or obj.username
