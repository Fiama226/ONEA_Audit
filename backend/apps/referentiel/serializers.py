from typing import Any

from rest_framework import serializers

from apps.users.models import User

from .models import (
    CartographieVersion,
    Direction,
    NiveauRisque,
    ObjetAuditable,
    PrioriteRisque,
    Processus,
    ReponseRisque,
    Risque,
    StatutCartographie,
)
from .validators import CARACTERES_CONTROLE_RE, MSG_CARACTERES_CONTROLE

_TEXTES_LIBRES_RISQUE = (
    "libelle",
    "description",
    "vulnerabilite",
    "objectif_controle",
    "dispositif_controle",
)

# --------------------------------------------------------------------------- structure


class DirectionSerializer(serializers.ModelSerializer[Direction]):
    parent_code = serializers.CharField(source="parent.code", read_only=True, allow_null=True)

    class Meta:
        model = Direction
        fields = ("id", "code", "libelle", "type", "parent", "parent_code")
        read_only_fields = ("id",)


class DirectionResumeSerializer(serializers.ModelSerializer[Direction]):
    class Meta:
        model = Direction
        fields = ("id", "code", "libelle")
        read_only_fields = fields


class ProcessusSerializer(serializers.ModelSerializer[Processus]):
    directions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Direction.objects.all(),
        required=False,
        write_only=True,
        help_text="Identifiants des directions rattachées (écriture).",
    )
    directions_detail = DirectionResumeSerializer(source="directions", many=True, read_only=True)

    class Meta:
        model = Processus
        fields = ("id", "code", "libelle", "famille", "ordre", "directions", "directions_detail")
        read_only_fields = ("id",)


class ObjetAuditableSerializer(serializers.ModelSerializer[ObjetAuditable]):
    class Meta:
        model = ObjetAuditable
        fields = ("id", "processus", "parent", "nature", "libelle", "description", "ordre")
        read_only_fields = ("id",)


class DomaineArbreSerializer(serializers.ModelSerializer[ObjetAuditable]):
    operations = ObjetAuditableSerializer(many=True, read_only=True)

    class Meta:
        model = ObjetAuditable
        fields = ("id", "libelle", "description", "ordre", "operations")
        read_only_fields = fields


# --------------------------------------------------------------------------- cartographie


class ValideurSerializer(serializers.ModelSerializer[User]):
    nom_complet = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "nom_complet")
        read_only_fields = fields

    def get_nom_complet(self, obj: User) -> str:
        return obj.get_full_name() or obj.username


class CartographieVersionSerializer(serializers.ModelSerializer[CartographieVersion]):
    statut = serializers.ChoiceField(choices=StatutCartographie.choices, read_only=True)
    validee_par = ValideurSerializer(read_only=True, allow_null=True)
    nb_risques = serializers.IntegerField(read_only=True)
    source = serializers.PrimaryKeyRelatedField(  # type: ignore[assignment]  # shadows Field.source
        queryset=CartographieVersion.objects.all(),
        required=False,
        allow_null=True,
        help_text="Cartographie validée dont les risques sont copiés (création uniquement).",
    )

    class Meta:
        model = CartographieVersion
        fields = (
            "id",
            "annee",
            "libelle",
            "commentaire",
            "statut",
            "source",
            "validee_le",
            "validee_par",
            "nb_risques",
            "created_at",
        )
        read_only_fields = ("id", "validee_le", "created_at")
        # L'unicité de l'année est vérifiée par le service (422 sur « annee »).
        validators: list[Any] = []

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if self.instance is not None:
            if "annee" in attrs and attrs["annee"] != self.instance.annee:
                raise serializers.ValidationError(
                    {"annee": ["L'année d'une cartographie ne peut pas être modifiée."]}
                )
            if "source" in attrs and attrs["source"] != self.instance.source:
                raise serializers.ValidationError(
                    {"source": ["La source ne peut être indiquée qu'à la création."]}
                )
            attrs.pop("annee", None)
            attrs.pop("source", None)
        return attrs


class VersionResumeSerializer(serializers.ModelSerializer[CartographieVersion]):
    statut = serializers.ChoiceField(choices=StatutCartographie.choices, read_only=True)

    class Meta:
        model = CartographieVersion
        fields = ("id", "annee", "libelle", "statut")
        read_only_fields = fields


# --------------------------------------------------------------------------- risques


class RisqueSerializer(serializers.ModelSerializer[Risque]):
    version_annee = serializers.IntegerField(source="version.annee", read_only=True)
    version_statut = serializers.ChoiceField(
        choices=StatutCartographie.choices, source="version.statut", read_only=True
    )
    processus_code = serializers.CharField(source="processus.code", read_only=True)
    objet_auditable_libelle = serializers.CharField(
        source="objet_auditable.libelle", read_only=True, allow_null=True
    )
    niveau = serializers.ChoiceField(choices=NiveauRisque.choices, read_only=True)
    probabilite = serializers.IntegerField(min_value=1, max_value=5)
    impact = serializers.IntegerField(min_value=1, max_value=5)
    reponse = serializers.ChoiceField(
        choices=ReponseRisque.choices, required=False, allow_blank=True
    )
    priorite = serializers.ChoiceField(
        choices=PrioriteRisque.choices,
        required=False,
        help_text="Par défaut dérivée du niveau : ÉLEVÉ 1, MOYEN 2, FAIBLE 3.",
    )

    class Meta:
        model = Risque
        fields = (
            "id",
            "version",
            "version_annee",
            "version_statut",
            "processus",
            "processus_code",
            "objet_auditable",
            "objet_auditable_libelle",
            "numero",
            "rang",
            "code",
            "score",
            "niveau",
            "libelle",
            "description",
            "probabilite",
            "impact",
            "vulnerabilite",
            "reponse",
            "priorite",
            "objectif_controle",
            "dispositif_controle",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "numero",
            "rang",
            "code",
            "score",
            "niveau",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        interdits = {
            champ: [MSG_CARACTERES_CONTROLE]
            for champ in _TEXTES_LIBRES_RISQUE
            if isinstance(attrs.get(champ), str) and CARACTERES_CONTROLE_RE.search(attrs[champ])
        }
        if interdits:
            raise serializers.ValidationError(interdits)
        if self.instance is not None:
            if "version" in attrs and attrs["version"].pk != self.instance.version_id:
                raise serializers.ValidationError(
                    {"version": ["Un risque ne peut pas changer de cartographie."]}
                )
            if "processus" in attrs and attrs["processus"].pk != self.instance.processus_id:
                raise serializers.ValidationError(
                    {"processus": ["Le processus d'un risque ne peut pas être modifié."]}
                )
            attrs.pop("version", None)
            attrs.pop("processus", None)
        return attrs


# --------------------------------------------------------------------------- matrice, comparaison


class CelluleMatriceSerializer(serializers.Serializer[Any]):
    probabilite = serializers.IntegerField(min_value=1, max_value=5)
    impact = serializers.IntegerField(min_value=1, max_value=5)
    score = serializers.IntegerField()
    niveau = serializers.ChoiceField(choices=NiveauRisque.choices)
    nombre = serializers.IntegerField()
    codes = serializers.ListField(child=serializers.CharField())


class ParNiveauSerializer(serializers.Serializer[Any]):
    FAIBLE = serializers.IntegerField()
    MOYEN = serializers.IntegerField()
    ELEVE = serializers.IntegerField()


class MatriceSerializer(serializers.Serializer[Any]):
    version = VersionResumeSerializer()
    total = serializers.IntegerField()
    par_niveau = ParNiveauSerializer()
    cellules = CelluleMatriceSerializer(many=True)


class RisqueResumeSerializer(serializers.ModelSerializer[Risque]):
    niveau = serializers.ChoiceField(choices=NiveauRisque.choices, read_only=True)

    class Meta:
        model = Risque
        fields = ("id", "code", "libelle", "score", "niveau")
        read_only_fields = fields


class RisqueModifieSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    changements = serializers.DictField(
        child=serializers.ListField(
            child=serializers.CharField(allow_null=True), min_length=2, max_length=2
        ),
        help_text="Par champ : [valeur avant, valeur après].",
    )


class ComparaisonSerializer(serializers.Serializer[Any]):
    reference = VersionResumeSerializer()
    cible = VersionResumeSerializer()
    ajoutes = RisqueResumeSerializer(many=True)
    retires = RisqueResumeSerializer(many=True)
    modifies = RisqueModifieSerializer(many=True)
