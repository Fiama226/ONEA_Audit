from typing import Any

from rest_framework import serializers

from apps.users.models import User


class AuteurRegleSerializer(serializers.Serializer[User]):
    id = serializers.IntegerField()
    nom_complet = serializers.CharField()


class RegleGouvernanceSerializer(serializers.Serializer[Any]):
    """État d'une règle de gouvernance (lecture ADMIN, RAI, DG)."""

    cle = serializers.CharField()
    libelle = serializers.CharField()
    description = serializers.CharField()
    reference = serializers.CharField(help_text="Norme ou fiche dont la règle est issue.")
    issue_des_normes = serializers.BooleanField(
        help_text="Règle issue des Normes IIA : assouplie, elle reste signalée en permanence."
    )
    valeur = serializers.DictField(child=serializers.JSONField(), help_text="Valeur effective.")
    defaut = serializers.DictField(
        child=serializers.JSONField(), help_text="Valeur de référence (la plus prudente)."
    )
    assouplie = serializers.BooleanField(
        help_text="La valeur effective est plus faible que la valeur de référence."
    )
    modifie_le = serializers.DateTimeField(allow_null=True)
    modifie_par = AuteurRegleSerializer(allow_null=True)
    motif = serializers.CharField(allow_blank=True)


class RegleGouvernanceEcritureSerializer(serializers.Serializer[dict[str, Any]]):
    valeur = serializers.DictField(
        child=serializers.JSONField(),
        help_text="Champs à changer (les autres gardent leur valeur). Validés par le service.",
    )
    motif = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=1000,
        default="",
        help_text="Obligatoire quand le changement assouplit un contrôle.",
    )


class EtapeADerogerSerializer(serializers.Serializer[Any]):
    """Étape ouverte bloquée par l'absence de réponse de l'audité (dérogation possible)."""

    etape = serializers.UUIDField(source="etape.pk")
    numero = serializers.IntegerField(source="etape.numero")
    romain = serializers.CharField()
    mission_id = serializers.UUIDField(source="etape.mission_id")
    mission_reference = serializers.CharField(source="etape.mission.reference")
    mission_titre = serializers.CharField(source="etape.mission.titre")
    manquants = serializers.ListField(child=serializers.CharField())


class DerogationReponseAuditeSerializer(serializers.Serializer[Any]):
    motif = serializers.CharField(
        max_length=2000,
        allow_blank=True,
        required=False,
        default="",
        help_text="Obligatoire quand la règle de gouvernance l'exige.",
    )
