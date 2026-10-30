from typing import Any

from rest_framework import serializers

from apps.users.models import User

from .models import Confirmation, ModeSignatureParametre


class SignataireSerializer(serializers.ModelSerializer[User]):
    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "nom_complet")
        read_only_fields = fields

    def get_nom_complet(self, obj: User) -> str:
        return obj.get_full_name() or obj.username


class ConfirmationResumeSerializer(serializers.ModelSerializer[Confirmation]):
    signataire = SignataireSerializer(read_only=True)

    class Meta:
        model = Confirmation
        fields = ("id", "type_document", "signataire", "confirme_le", "empreinte")
        read_only_fields = fields


class ModeDisponibleSerializer(serializers.Serializer[dict[str, str]]):
    mode = serializers.ChoiceField(choices=ModeSignatureParametre.choices)
    libelle = serializers.CharField()


class ParametreSignatureSerializer(serializers.Serializer[dict[str, Any]]):
    """Une ligne par type paramétrable (modèle sans ligne : mode par défaut)."""

    type_document = serializers.CharField()
    type_libelle = serializers.CharField()
    mode = serializers.ChoiceField(choices=ModeSignatureParametre.choices)
    mode_libelle = serializers.CharField()
    modes_disponibles = ModeDisponibleSerializer(many=True)
    modifie_le = serializers.DateTimeField(allow_null=True)
    modifie_par = SignataireSerializer(allow_null=True)


class ParametreSignatureEcritureSerializer(serializers.Serializer[dict[str, str]]):
    mode = serializers.ChoiceField(choices=ModeSignatureParametre.choices)
