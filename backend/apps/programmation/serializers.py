from typing import Any

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.referentiel.models import Direction, ObjetAuditable, Processus
from apps.referentiel.serializers import ValideurSerializer

from .models import (
    LigneProgramme,
    NiveauApprobation,
    ProgrammeAnnuel,
    StatutProgramme,
    TypeIntervention,
)
from .services import etat_approbation

MSG_INTROUVABLE = "Objet introuvable."


class _Relation(serializers.PrimaryKeyRelatedField):  # type: ignore[type-arg]
    default_error_messages = {
        "does_not_exist": MSG_INTROUVABLE,
        "incorrect_type": MSG_INTROUVABLE,
    }


class AuteurApprobationSerializer(serializers.Serializer[Any]):
    id = serializers.IntegerField()
    nom_complet = serializers.CharField()


class ApprobationLueSerializer(serializers.Serializer[Any]):
    niveau = serializers.ChoiceField(choices=NiveauApprobation.choices)
    niveau_libelle = serializers.CharField()
    approuve_par = AuteurApprobationSerializer()
    approuve_le = serializers.DateTimeField()
    date_decision = serializers.DateField()
    reference = serializers.CharField(allow_blank=True)
    commentaire = serializers.CharField(allow_blank=True)


class EtatApprobationSerializer(serializers.Serializer[Any]):
    approbateur = serializers.ChoiceField(
        choices=["NONE", "DG", "DG_AND_BOARD"],
        help_text="Approbateur exigé par la règle de gouvernance en vigueur.",
    )
    requise = serializers.BooleanField()
    approuve = serializers.BooleanField()
    manquantes = serializers.ListField(child=serializers.ChoiceField(NiveauApprobation.choices))
    approbations = ApprobationLueSerializer(many=True)


class ApprobationEcritureSerializer(serializers.Serializer[Any]):
    niveau = serializers.ChoiceField(choices=NiveauApprobation.choices)
    date_decision = serializers.DateField(required=False, allow_null=True)
    reference = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=120,
        default="",
        help_text="Référence de la délibération : obligatoire pour le Conseil.",
    )
    commentaire = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=2000
    )


class ProgrammeAnnuelSerializer(serializers.ModelSerializer[ProgrammeAnnuel]):
    statut = serializers.ChoiceField(choices=StatutProgramme.choices, read_only=True)
    valide_par = ValideurSerializer(read_only=True, allow_null=True)
    nb_lignes = serializers.IntegerField(read_only=True)
    charge_totale_jours = serializers.DecimalField(max_digits=10, decimal_places=1, read_only=True)
    annee = serializers.IntegerField(
        min_value=2000,
        max_value=2100,
        help_text="Écriture à la création seulement : l'année est ensuite immuable.",
    )
    libelle = serializers.CharField(max_length=200, required=False, allow_blank=True)
    approbation = serializers.SerializerMethodField()

    class Meta:
        model = ProgrammeAnnuel
        fields = (
            "id",
            "annee",
            "libelle",
            "commentaire",
            "statut",
            "valide_le",
            "valide_par",
            "approbation",
            "nb_lignes",
            "charge_totale_jours",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "valide_le", "created_at", "updated_at")
        # L'unicité de l'année est vérifiée par le service (422 sur « annee »).
        validators: list[Any] = []

    @extend_schema_field(EtatApprobationSerializer)
    def get_approbation(self, obj: ProgrammeAnnuel) -> dict[str, Any]:
        return dict(EtatApprobationSerializer(etat_approbation(obj)).data)


class EntiteResumeSerializer(serializers.ModelSerializer[Direction]):
    supprime = serializers.SerializerMethodField()

    class Meta:
        model = Direction
        fields = ("id", "code", "libelle", "supprime")
        read_only_fields = fields

    def get_supprime(self, obj: Direction) -> bool:
        return obj.deleted_at is not None


class LigneProgrammeSerializer(serializers.ModelSerializer[LigneProgramme]):
    programme = _Relation(
        queryset=ProgrammeAnnuel.objects.all(),
        help_text="Écriture à la création seulement.",
    )
    programme_annee = serializers.IntegerField(source="programme.annee", read_only=True)
    programme_statut = serializers.ChoiceField(
        choices=StatutProgramme.choices, source="programme.statut", read_only=True
    )
    type = serializers.ChoiceField(choices=TypeIntervention.choices)
    processus = _Relation(queryset=Processus.objects.all())
    processus_code = serializers.CharField(source="processus.code", read_only=True)
    processus_libelle = serializers.CharField(source="processus.libelle", read_only=True)
    processus_supprime = serializers.SerializerMethodField()
    objet_auditable = _Relation(
        queryset=ObjetAuditable.objects.all(), required=False, allow_null=True
    )
    objet_auditable_libelle = serializers.CharField(
        source="objet_auditable.libelle", read_only=True, allow_null=True
    )
    objet_auditable_supprime = serializers.SerializerMethodField()
    entites = serializers.ManyRelatedField(
        child_relation=_Relation(queryset=Direction.objects.all()),
        required=False,
        write_only=True,
        help_text="Identifiants des entités concernées (écriture).",
    )
    entites_detail = EntiteResumeSerializer(source="entites", many=True, read_only=True)
    trimestre = serializers.SerializerMethodField()
    charge_prevue_jours = serializers.DecimalField(
        max_digits=6, decimal_places=1, min_value=0, required=False, allow_null=True
    )

    class Meta:
        model = LigneProgramme
        fields = (
            "id",
            "programme",
            "programme_annee",
            "programme_statut",
            "numero",
            "titre",
            "type",
            "processus",
            "processus_code",
            "processus_libelle",
            "processus_supprime",
            "objet_auditable",
            "objet_auditable_libelle",
            "objet_auditable_supprime",
            "entites",
            "entites_detail",
            "debut_prevu",
            "fin_prevue",
            "trimestre",
            "charge_prevue_jours",
            "justification",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "numero", "created_at", "updated_at")
        validators: list[Any] = []

    def get_processus_supprime(self, obj: LigneProgramme) -> bool:
        return obj.processus.deleted_at is not None

    def get_objet_auditable_supprime(self, obj: LigneProgramme) -> bool:
        return obj.objet_auditable is not None and obj.objet_auditable.deleted_at is not None

    @extend_schema_field(serializers.IntegerField(min_value=1, max_value=4))
    def get_trimestre(self, obj: LigneProgramme) -> int:
        return (obj.debut_prevu.month - 1) // 3 + 1


class ParTypeSerializer(serializers.Serializer[dict[str, int]]):
    ASSURANCE = serializers.IntegerField()
    CONSEIL = serializers.IntegerField()


# Clés « 1 » à « 4 » : déclarées dynamiquement (identifiants non valides en syntaxe de classe).
ParTrimestreSerializer: Any = type(
    "ParTrimestreSerializer",
    (serializers.Serializer,),
    {str(n): serializers.IntegerField() for n in range(1, 5)},
)


class SyntheseProgrammeSerializer(serializers.Serializer[dict[str, Any]]):
    nb_lignes = serializers.IntegerField()
    charge_totale_jours = serializers.DecimalField(max_digits=10, decimal_places=1)
    par_type = ParTypeSerializer()
    par_trimestre = ParTrimestreSerializer()
