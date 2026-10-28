from rest_framework import serializers

from .models import User


class MeSerializer(serializers.ModelSerializer[User]):
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
        )
        read_only_fields = fields


class UtilisateurResumeSerializer(serializers.ModelSerializer[User]):
    """Représentation minimale d'un utilisateur dans les réponses (annuaire, équipes)."""

    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "nom_complet", "role", "direction_code", "fonction")
        read_only_fields = fields

    def get_nom_complet(self, obj: User) -> str:
        return obj.get_full_name() or obj.username
