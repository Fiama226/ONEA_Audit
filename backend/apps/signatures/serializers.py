from rest_framework import serializers

from apps.users.models import User

from .models import Confirmation


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
