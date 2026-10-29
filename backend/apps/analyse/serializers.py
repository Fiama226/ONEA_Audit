"""Sérialiseurs de l'API d'analyse.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI
consommés par le frontend. Les droits (`mes_droits`) viennent de `droits.py` ; les statuts des
étapes (`etape_close`) sont lus une fois par mission et par requête (clé `statuts_etapes` du
contexte), jamais par objet.
"""

from typing import Any, cast
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import Mission, RisqueMission
from apps.missions.serializers import CleRelation
from apps.referentiel.models import ObjetAuditable, Processus
from apps.signatures.serializers import ConfirmationResumeSerializer
from apps.users.serializers import UtilisateurResumeSerializer

from . import gardes
from .models import (
    Appreciation,
    AvisAudite,
    CategorieObjectif,
    Composante,
    CouvertureOrdre,
    DescriptionProcessus,
    EvaluationConception,
    ForceFaiblesse,
    GrilleSeparation,
    LigneMARC,
    MotifNonTest,
    NatureControle,
    ObjectifAudit,
    Questionnaire,
    QuestionQuestionnaire,
    RapportOrientation,
    RoleTache,
    StatutReferentiel,
    TypeAvis,
    TypeForceFaiblesse,
    TypeQuestionnaire,
    TypologieProcessus,
    VarianteOrientation,
)
from .services.grilles import analyser_grille

# --------------------------------------------------------------------------- gel par étape


class _ModeleEtapeClose(serializers.ModelSerializer[Any]):
    """Base des sérialiseurs qui exposent `etape_close` : statuts lus une fois par mission."""

    def statuts(self, mission_id: UUID) -> dict[int, str]:
        contexte = cast(dict[str, Any], self.context)
        cache: dict[UUID, dict[int, str]] = contexte.setdefault("statuts_etapes", {})
        if mission_id not in cache:
            cache[mission_id] = gardes.statuts_etapes(mission_id, (3, 5, 6, 7))
        return cache[mission_id]

    def close(self, mission_id: UUID, numero: int) -> bool:
        return self.statuts(mission_id).get(numero) in STATUTS_ETAPE_CLOSE


# --------------------------------------------------------------------------- étape III


class QuestionnaireSerializer(_ModeleEtapeClose):
    mission = CleRelation(queryset=Mission.objects.all())
    type = serializers.ChoiceField(choices=TypeQuestionnaire.choices)
    processus = CleRelation(queryset=Processus.objects.all(), required=False, allow_null=True)
    processus_code = serializers.CharField(source="processus.code", read_only=True, allow_null=True)
    titre = serializers.CharField(required=False, allow_blank=True, max_length=200)
    nb_questions = serializers.IntegerField(read_only=True)
    nb_repondues = serializers.IntegerField(read_only=True)
    etape_close = serializers.SerializerMethodField()

    class Meta:
        model = Questionnaire
        fields = (
            "id",
            "mission",
            "type",
            "processus",
            "processus_code",
            "titre",
            "nb_questions",
            "nb_repondues",
            "etape_close",
        )
        read_only_fields = ("id",)

    def get_etape_close(self, obj: Questionnaire) -> bool:
        if obj.type == TypeQuestionnaire.PRISE_CONNAISSANCE:
            return self.close(obj.mission_id, 3)
        return gardes.fenetre_marc_close(self.statuts(obj.mission_id))


class QuestionSerializer(serializers.ModelSerializer[QuestionQuestionnaire]):
    questionnaire = CleRelation(queryset=Questionnaire.objects.all())
    appreciation = serializers.ChoiceField(
        choices=Appreciation.choices, required=False, allow_blank=True
    )
    ordre = serializers.IntegerField(required=False, min_value=0, max_value=32767)
    repondue = serializers.BooleanField(read_only=True)

    class Meta:
        model = QuestionQuestionnaire
        fields = (
            "id",
            "questionnaire",
            "theme",
            "libelle",
            "reponse",
            "appreciation",
            "ordre",
            "repondue",
        )
        read_only_fields = ("id",)


class DescriptionProcessusSerializer(_ModeleEtapeClose):
    mission = CleRelation(queryset=Mission.objects.all())
    processus = CleRelation(queryset=Processus.objects.all())
    processus_code = serializers.CharField(source="processus.code", read_only=True)
    processus_libelle = serializers.CharField(source="processus.libelle", read_only=True)
    typologie = serializers.ChoiceField(
        choices=TypologieProcessus.choices, required=False, allow_blank=True
    )
    categories_objectifs = serializers.ListField(
        child=serializers.ChoiceField(choices=CategorieObjectif.choices), required=False
    )
    etape_close = serializers.SerializerMethodField()

    class Meta:
        model = DescriptionProcessus
        fields = (
            "id",
            "mission",
            "processus",
            "processus_code",
            "processus_libelle",
            "typologie",
            "categories_objectifs",
            "description",
            "objectifs",
            "indicateurs",
            "sources",
            "references_diagrammes",
            "etape_close",
        )
        read_only_fields = ("id",)

    def get_etape_close(self, obj: DescriptionProcessus) -> bool:
        return self.close(obj.mission_id, 3)


class CelluleGrilleSerializer(serializers.Serializer[Any]):
    tache = serializers.IntegerField()
    acteur = serializers.IntegerField()
    roles = serializers.ListField(child=serializers.ChoiceField(choices=RoleTache.choices))


class CumulSerializer(serializers.Serializer[Any]):
    tache = serializers.CharField()
    acteur = serializers.CharField()
    roles = serializers.ListField(child=serializers.ChoiceField(choices=RoleTache.choices))


class AnalyseGrilleSerializer(serializers.Serializer[Any]):
    taches_sans_acteur = serializers.ListField(child=serializers.CharField())
    taches_multi_executants = serializers.ListField(child=serializers.CharField())
    cumuls = CumulSerializer(many=True)


class GrilleSeparationSerializer(_ModeleEtapeClose):
    mission = CleRelation(queryset=Mission.objects.all())
    processus = CleRelation(queryset=Processus.objects.all())
    processus_code = serializers.CharField(source="processus.code", read_only=True)
    # Contenu laissé au service : la grille invalide répond 422 posé sur le champ.
    taches = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)
    acteurs = serializers.ListField(child=serializers.CharField(allow_blank=True), required=False)
    cellules = CelluleGrilleSerializer(many=True, required=False)
    analyse = serializers.SerializerMethodField()
    etape_close = serializers.SerializerMethodField()

    class Meta:
        model = GrilleSeparation
        fields = (
            "id",
            "mission",
            "processus",
            "processus_code",
            "taches",
            "acteurs",
            "cellules",
            "commentaire",
            "analyse",
            "etape_close",
        )
        read_only_fields = ("id",)

    @extend_schema_field(AnalyseGrilleSerializer)
    def get_analyse(self, obj: GrilleSeparation) -> dict[str, Any]:
        return cast(dict[str, Any], AnalyseGrilleSerializer(analyser_grille(obj)).data)

    def get_etape_close(self, obj: GrilleSeparation) -> bool:
        return self.close(obj.mission_id, 3)


# --------------------------------------------------------------------------- étapes V et VI


class LigneMARCSerializer(serializers.ModelSerializer[LigneMARC]):
    mission = CleRelation(queryset=Mission.objects.all())
    risque = CleRelation(queryset=RisqueMission.objects.all())
    risque_code = serializers.CharField(source="risque.code_source", read_only=True)
    risque_libelle = serializers.CharField(source="risque.libelle", read_only=True)
    risque_niveau = serializers.CharField(source="risque.niveau", read_only=True)
    risque_score = serializers.IntegerField(source="risque.score", read_only=True)
    processus_code = serializers.CharField(source="risque.processus.code", read_only=True)
    objet_auditable = CleRelation(
        queryset=ObjetAuditable.objects.all(), required=False, allow_null=True
    )
    objet_auditable_libelle = serializers.CharField(
        source="objet_auditable.libelle", read_only=True, allow_null=True
    )
    composante = serializers.ChoiceField(
        choices=Composante.choices, required=False, allow_blank=True
    )
    nature = serializers.ChoiceField(
        choices=NatureControle.choices, required=False, allow_blank=True
    )
    evaluation = serializers.ChoiceField(
        choices=EvaluationConception.choices, required=False, allow_blank=True
    )
    appreciation = serializers.ChoiceField(
        choices=TypeForceFaiblesse.choices, read_only=True, allow_null=True
    )
    ordre = serializers.IntegerField(required=False, min_value=0, max_value=32767)
    a_objectif = serializers.BooleanField(read_only=True)

    class Meta:
        model = LigneMARC
        fields = (
            "id",
            "mission",
            "risque",
            "risque_code",
            "risque_libelle",
            "risque_niveau",
            "risque_score",
            "processus_code",
            "objet_auditable",
            "objet_auditable_libelle",
            "operation",
            "objectif_controle",
            "controle_attendu",
            "controle_existant",
            "composante",
            "nature",
            "evaluation",
            "appreciation",
            "cle",
            "commentaire",
            "ordre",
            "a_objectif",
        )
        read_only_fields = ("id",)


class ForceFaiblesseSerializer(serializers.ModelSerializer[ForceFaiblesse]):
    mission = CleRelation(queryset=Mission.objects.all())
    type = serializers.ChoiceField(choices=TypeForceFaiblesse.choices)
    ligne_marc = serializers.UUIDField(source="ligne_marc_id", read_only=True, allow_null=True)
    liee = serializers.SerializerMethodField()
    processus = CleRelation(queryset=Processus.objects.all(), required=False, allow_null=True)
    processus_code = serializers.CharField(source="processus.code", read_only=True, allow_null=True)
    ordre = serializers.IntegerField(required=False, min_value=0, max_value=32767)

    class Meta:
        model = ForceFaiblesse
        fields = (
            "id",
            "mission",
            "type",
            "ligne_marc",
            "liee",
            "processus",
            "processus_code",
            "libelle",
            "consequence",
            "commentaire",
            "ordre",
        )
        read_only_fields = ("id",)

    def get_liee(self, obj: ForceFaiblesse) -> bool:
        return obj.ligne_marc_id is not None


class AvisAuditeSerializer(serializers.ModelSerializer[AvisAudite]):
    auteur = UtilisateurResumeSerializer(read_only=True)
    avis = serializers.ChoiceField(choices=TypeAvis.choices, read_only=True)

    class Meta:
        model = AvisAudite
        fields = ("id", "auteur", "avis", "commentaire", "donne_le")
        read_only_fields = fields


class AvisRequestSerializer(serializers.Serializer[Any]):
    avis = serializers.ChoiceField(choices=TypeAvis.choices)
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")


class MissionRequestSerializer(serializers.Serializer[Any]):
    mission = CleRelation(queryset=Mission.objects.all())


class DroitsAnalyseSerializer(serializers.Serializer[Any]):
    voir_travaux = serializers.BooleanField()
    contribuer_iii = serializers.BooleanField()
    contribuer_v = serializers.BooleanField()
    donner_avis = serializers.BooleanField()
    voir_referentiel = serializers.BooleanField()
    contribuer_vii = serializers.BooleanField()


class ReferentielAuditSerializer(serializers.Serializer[Any]):
    """Synthèse du référentiel ; `data` est un dict déjà assemblé par la vue."""

    mission = serializers.UUIDField()
    statut = serializers.ChoiceField(choices=StatutReferentiel.choices)
    statut_v = serializers.CharField()
    statut_vi = serializers.CharField()
    nb_lignes = serializers.IntegerField()
    nb_forces = serializers.IntegerField()
    nb_faiblesses = serializers.IntegerField()
    risques_non_couverts = serializers.ListField(child=serializers.CharField())
    validation = ConfirmationResumeSerializer(allow_null=True)
    validation_verifiee = serializers.BooleanField()
    avis = AvisAuditeSerializer(many=True)
    mes_droits = DroitsAnalyseSerializer()


class InstantaneReferentielSerializer(serializers.Serializer[Any]):
    confirmation = ConfirmationResumeSerializer()
    donnees = serializers.DictField()


# --------------------------------------------------------------------------- étape VII


class ObjectifAuditSerializer(serializers.ModelSerializer[ObjectifAudit]):
    mission = CleRelation(queryset=Mission.objects.all())
    ligne_marc = CleRelation(queryset=LigneMARC.objects.all())
    code = serializers.CharField(read_only=True)
    numero = serializers.IntegerField(read_only=True)
    libelle = serializers.CharField(required=False, allow_blank=True, max_length=500)
    retenu = serializers.BooleanField(required=False)
    motif_non_test = serializers.ChoiceField(
        choices=MotifNonTest.choices, required=False, allow_blank=True
    )
    risque_code = serializers.CharField(source="ligne_marc.risque.code_source", read_only=True)
    controle_existant = serializers.CharField(source="ligne_marc.controle_existant", read_only=True)

    class Meta:
        model = ObjectifAudit
        fields = (
            "id",
            "mission",
            "ligne_marc",
            "code",
            "numero",
            "libelle",
            "retenu",
            "motif_non_test",
            "justification",
            "risque_code",
            "controle_existant",
        )
        read_only_fields = ("id",)


class RappelOrdreSerializer(serializers.Serializer[Any]):
    objectifs = serializers.CharField()
    perimetre = serializers.CharField()
    exclusions = serializers.CharField()
    clients = serializers.CharField()
    livrables_attendus = serializers.CharField()


class RapportOrientationSerializer(_ModeleEtapeClose):
    mission = serializers.UUIDField(source="mission_id", read_only=True)
    variante = serializers.ChoiceField(choices=VarianteOrientation.choices, required=False)
    couverture_ordre = serializers.ChoiceField(
        choices=CouvertureOrdre.choices, required=False, allow_blank=True
    )
    rappel_ordre = serializers.SerializerMethodField()
    etape_close = serializers.SerializerMethodField()

    class Meta:
        model = RapportOrientation
        fields = (
            "mission",
            "variante",
            "contexte",
            "approche",
            "observations",
            "couverture_ordre",
            "justification_couverture",
            "rappel_ordre",
            "etape_close",
        )

    @extend_schema_field(RappelOrdreSerializer)
    def get_rappel_ordre(self, obj: RapportOrientation) -> dict[str, str]:
        m = obj.mission
        return {
            "objectifs": m.objectifs,
            "perimetre": m.perimetre,
            "exclusions": m.exclusions,
            "clients": m.clients,
            "livrables_attendus": m.livrables_attendus,
        }

    def get_etape_close(self, obj: RapportOrientation) -> bool:
        return self.close(obj.mission_id, 7)
