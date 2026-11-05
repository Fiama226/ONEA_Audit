from rest_framework import serializers

from .auth_services import Etape
from .serializers import MeSerializer

# Upper bounds keep a hostile body from costing an unbounded hash.
IDENTIFIANT_MAX = 254
MOT_DE_PASSE_MAX = 256


class ConnexionSerializer(serializers.Serializer[None]):
    identifiant = serializers.CharField(max_length=IDENTIFIANT_MAX)
    mot_de_passe = serializers.CharField(
        max_length=MOT_DE_PASSE_MAX, trim_whitespace=False, write_only=True
    )


class CodeConnexionSerializer(serializers.Serializer[None]):
    code = serializers.RegexField(r"^\d{6}$", max_length=6)


class EtatSessionSerializer(serializers.Serializer[None]):
    """Answer of login, login OTP and session: next step and the `me` profile (null at OTP)."""

    etape = serializers.ChoiceField(choices=[e.value for e in Etape])
    me = MeSerializer(allow_null=True)


class JetonCsrfSerializer(serializers.Serializer[None]):
    csrf_token = serializers.CharField()


def _mot_de_passe() -> serializers.CharField:
    return serializers.CharField(
        max_length=MOT_DE_PASSE_MAX, trim_whitespace=False, write_only=True
    )


class MotDePasseOublieSerializer(serializers.Serializer[None]):
    identifiant = serializers.CharField(max_length=IDENTIFIANT_MAX)


class ReinitialisationSerializer(serializers.Serializer[None]):
    identifiant = serializers.CharField(max_length=IDENTIFIANT_MAX)
    code = serializers.RegexField(r"^\d{6}$", max_length=6)
    nouveau_mot_de_passe = _mot_de_passe()


class ChangementMotDePasseSerializer(serializers.Serializer[None]):
    ancien = _mot_de_passe()
    nouveau = _mot_de_passe()


class ConfirmationMotDePasseSerializer(serializers.Serializer[None]):
    mot_de_passe = _mot_de_passe()


class MessageSerializer(serializers.Serializer[None]):
    detail = serializers.CharField()


class EtatOtpSerializer(serializers.Serializer[None]):
    otp_connexion_actif = serializers.BooleanField()
