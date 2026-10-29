"""Sérialiseurs de l'API de l'accomplissement.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI
consommés par le frontend. Les droits affichés (`actions_possibles`) viennent de `droits.py` et
`droits_fiches.py` ; rien n'est recalculé ici. Le contexte de droits (rôle, statuts d'étapes,
fiches des tests) est construit UNE FOIS par mission et par requête (clé `accomplissement` du
contexte du sérialiseur), jamais par objet.
"""

from dataclasses import dataclass, field
from typing import Any, ClassVar, cast
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.analyse.gardes import statuts_etapes
from apps.analyse.models import ObjectifAudit
from apps.analyse.services.objectifs import code_objectif
from apps.missions.models import Mission, RisqueMission
from apps.missions.serializers import CleRelation
from apps.missions.services.etapes import ContexteActions, contexte_actions
from apps.users.models import User
from apps.users.serializers import UtilisateurResumeSerializer

from . import droits, droits_fiches, gardes
from .models import (
    ConclusionTest,
    EvenementFiche,
    FicheDeTest,
    InstantaneProgramme,
    MethodeSelection,
    NatureTest,
    PieceJustificative,
    ProgrammeDeTravail,
    StatutFiche,
    StatutTest,
    TestPrevu,
    TypeEvenementFiche,
)

ETAPES_LUES = (
    droits.ETAPE_CONTENU,
    droits.ETAPE_RESSOURCES,
    droits.ETAPE_COMPLEMENTAIRES,
    gardes.ETAPE_VALIDATION_PREUVES,
)


@dataclass
class _Cache:
    """Données de droits d'une mission, lues une fois pour toute la requête."""

    contexte: ContexteActions
    statuts: dict[int, str]
    # test -> (fiche, statut, conclusion) ; chargé à la demande (listes de tests seulement)
    fiches: dict[UUID, tuple[UUID, str, str]] | None = field(default=None)

    def contexte_programme(self) -> droits.ContexteProgramme:
        assert self.fiches is not None  # noqa: S101
        return droits.ContexteProgramme(
            mission=self.contexte.mission,
            role_mission=self.contexte.role_mission,
            levee=self.contexte.levee,
            statuts=self.statuts,
            fiches={test: statut for test, (_, statut, _) in self.fiches.items()},
        )


def cache_mission(
    serializer: serializers.BaseSerializer[Any], mission: Mission, *, avec_fiches: bool = False
) -> _Cache:
    """Cache de droits de `mission` : une requête de statuts (+ une pour les fiches si demandé)."""
    contexte = cast(dict[str, Any], serializer.context)
    caches: dict[UUID, _Cache] = contexte.setdefault("accomplissement", {})
    if mission.pk not in caches:
        user = cast(User, contexte["request"].user)
        caches[mission.pk] = _Cache(
            contexte=contexte_actions(mission, user),
            statuts=statuts_etapes(mission.pk, ETAPES_LUES),
        )
    cache = caches[mission.pk]
    if avec_fiches and cache.fiches is None:
        cache.fiches = {
            test_id: (pk, statut, conclusion)
            for test_id, pk, statut, conclusion in FicheDeTest.objects.filter(
                mission=mission
            ).values_list("test_id", "pk", "statut", "conclusion")
        }
    return cache


def _acteur(serializer: serializers.BaseSerializer[Any]) -> User:
    return cast(User, serializer.context["request"].user)


# --------------------------------------------------------------------------- programme


class ObjectifResumeSerializer(serializers.ModelSerializer[ObjectifAudit]):
    code = serializers.SerializerMethodField()

    class Meta:
        model = ObjectifAudit
        fields = ("id", "code", "libelle")
        read_only_fields = fields

    def get_code(self, obj: ObjectifAudit) -> str:
        return code_objectif(obj)


class ProgrammeDeTravailSerializer(serializers.ModelSerializer[ProgrammeDeTravail]):
    mission = CleRelation(queryset=Mission.objects.all())
    objectif = CleRelation(queryset=ObjectifAudit.objects.all())
    objectif_detail = ObjectifResumeSerializer(source="objectif", read_only=True)
    nb_tests = serializers.IntegerField(read_only=True)
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = ProgrammeDeTravail
        fields = (
            "id",
            "mission",
            "objectif",
            "objectif_detail",
            "techniques",
            "criteres_preuve",
            "commentaire",
            "nb_tests",
            "actions_possibles",
        )
        read_only_fields = ("id",)

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: ProgrammeDeTravail) -> list[str]:
        cache = cache_mission(self, obj.mission, avec_fiches=True)
        return droits.actions_programme_depuis(_acteur(self), cache.contexte_programme())


class LigneObjectifProgrammeSerializer(serializers.Serializer[Any]):
    code = serializers.CharField()
    libelle = serializers.CharField()
    nb_tests = serializers.IntegerField()
    charge = serializers.DecimalField(max_digits=8, decimal_places=1)


class LigneAuditeurProgrammeSerializer(serializers.Serializer[Any]):
    utilisateur = UtilisateurResumeSerializer()
    nb_tests = serializers.IntegerField()
    charge = serializers.DecimalField(max_digits=8, decimal_places=1)


class SyntheseProgrammeTravailSerializer(serializers.Serializer[Any]):
    objectifs = LigneObjectifProgrammeSerializer(many=True)
    auditeurs = LigneAuditeurProgrammeSerializer(many=True)
    total_charge = serializers.DecimalField(max_digits=8, decimal_places=1)
    budget_jours = serializers.DecimalField(max_digits=8, decimal_places=1)
    depassement_budget = serializers.BooleanField()
    tests_sans_auditeur = serializers.ListField(child=serializers.CharField())


class InstantaneResumeSerializer(serializers.ModelSerializer[InstantaneProgramme]):
    valide_par = UtilisateurResumeSerializer(read_only=True)

    class Meta:
        model = InstantaneProgramme
        fields: ClassVar[list[str]] = ["id", "valide_par", "valide_le", "empreinte"]
        read_only_fields = fields


class InstantaneSerializer(InstantaneResumeSerializer):
    donnees = serializers.JSONField(read_only=True)

    class Meta(InstantaneResumeSerializer.Meta):
        fields = [*InstantaneResumeSerializer.Meta.fields, "donnees"]
        read_only_fields = fields


# --------------------------------------------------------------------------- tests prévus


class FicheResumeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    statut = serializers.ChoiceField(choices=StatutFiche.choices)
    conclusion = serializers.ChoiceField(choices=ConclusionTest.choices, allow_blank=True)


class TestPrevuSerializer(serializers.ModelSerializer[TestPrevu]):
    __test__ = False  # n'est pas un test pytest

    programme = CleRelation(queryset=ProgrammeDeTravail.objects.all())
    auditeur = CleRelation(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True
    )
    auditeur_detail = UtilisateurResumeSerializer(source="auditeur", read_only=True)
    risque_mission = CleRelation(
        queryset=RisqueMission.objects.all(), required=False, allow_null=True
    )
    risque_code = serializers.SerializerMethodField()
    nature = serializers.ChoiceField(choices=NatureTest.choices, required=False)
    methode_selection = serializers.ChoiceField(
        choices=MethodeSelection.choices, required=False, allow_blank=True
    )
    statut = serializers.ChoiceField(choices=StatutTest.choices, read_only=True)
    fiche = serializers.SerializerMethodField()
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = TestPrevu
        fields = (
            "id",
            "mission",
            "programme",
            "code",
            "libelle",
            "objectif_test",
            "nature",
            "procedure",
            "population",
            "taille_echantillon",
            "methode_selection",
            "auditeur",
            "auditeur_detail",
            "charge_prevue_jours",
            "date_debut_prevue",
            "date_fin_prevue",
            "risque_mission",
            "risque_code",
            "complementaire",
            "statut",
            "motif_abandon",
            "fiche",
            "actions_possibles",
        )
        read_only_fields = ("id", "mission", "code", "complementaire", "motif_abandon")

    def get_risque_code(self, obj: TestPrevu) -> str:
        return obj.risque_mission.code_source if obj.risque_mission is not None else ""

    @extend_schema_field(FicheResumeSerializer(allow_null=True))
    def get_fiche(self, obj: TestPrevu) -> dict[str, Any] | None:
        fiches = cache_mission(self, obj.mission, avec_fiches=True).fiches or {}
        ligne = fiches.get(obj.pk)
        if ligne is None:
            return None
        return {"id": ligne[0], "statut": ligne[1], "conclusion": ligne[2]}

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: TestPrevu) -> list[str]:
        cache = cache_mission(self, obj.mission, avec_fiches=True)
        return droits.actions_test(obj, _acteur(self), contexte=cache.contexte_programme())


# --------------------------------------------------------------------------- pièces


class PieceJustificativeSerializer(serializers.ModelSerializer[PieceJustificative]):
    fiche = serializers.PrimaryKeyRelatedField(read_only=True)  # type: ignore[var-annotated]
    deposee_par = UtilisateurResumeSerializer(read_only=True)
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = PieceJustificative
        fields = (
            "id",
            "fiche",
            "numero",
            "libelle",
            "description",
            "nom_fichier_original",
            "type_mime",
            "taille_octets",
            "empreinte_sha256",
            "deposee_par",
            "deposee_le",
            "actions_possibles",
        )
        read_only_fields = (
            "id",
            "numero",
            "nom_fichier_original",
            "type_mime",
            "taille_octets",
            "empreinte_sha256",
            "deposee_le",
        )

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: PieceJustificative) -> list[str]:
        cache = cache_mission(self, obj.mission)
        return droits_fiches.actions_piece(
            obj,
            _acteur(self),
            contexte=cache.contexte,
            statuts=cache.statuts,
            fiche=(obj.fiche.statut, obj.fiche.test.auditeur_id),
        )


class DepotPieceSerializer(serializers.Serializer[Any]):
    """Dépôt d'une pièce (multipart/form-data) ; le fichier n'est lu que par le service."""

    fiche = CleRelation(queryset=FicheDeTest.objects.all())
    fichier = serializers.FileField()
    libelle = serializers.CharField(max_length=200)
    description = serializers.CharField(required=False, allow_blank=True, default="")


# --------------------------------------------------------------------------- fiches


class ConstatResumeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    reference = serializers.CharField()


class EvenementFicheSerializer(serializers.ModelSerializer[EvenementFiche]):
    type = serializers.ChoiceField(choices=TypeEvenementFiche.choices)
    statut_avant = serializers.ChoiceField(choices=StatutFiche.choices)
    statut_apres = serializers.ChoiceField(choices=StatutFiche.choices)
    par = UtilisateurResumeSerializer(read_only=True)

    class Meta:
        model = EvenementFiche
        fields = ("id", "type", "par", "le", "motif", "statut_avant", "statut_apres")
        read_only_fields = fields


class FicheDeTestListeSerializer(serializers.ModelSerializer[FicheDeTest]):
    test = CleRelation(queryset=TestPrevu.objects.all())
    test_code = serializers.CharField(source="test.code", read_only=True)
    test_libelle = serializers.CharField(source="test.libelle", read_only=True)
    objectif_code = serializers.SerializerMethodField()
    statut = serializers.ChoiceField(choices=StatutFiche.choices, read_only=True)
    auteur_detail = UtilisateurResumeSerializer(source="auteur", read_only=True)
    conclusion = serializers.ChoiceField(
        choices=ConclusionTest.choices, required=False, allow_blank=True
    )
    constats = serializers.SerializerMethodField()
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = FicheDeTest
        fields: ClassVar[list[str]] = [
            "id",
            "mission",
            "test",
            "test_code",
            "test_libelle",
            "objectif_code",
            "statut",
            "auteur_detail",
            "date_realisation",
            "travaux_realises",
            "echantillon_teste",
            "taille_testee",
            "nombre_exceptions",
            "resultat",
            "conclusion",
            "commentaire_conclusion",
            "charge_reelle_jours",
            "justification_sans_piece",
            "soumise_par",
            "soumise_le",
            "validee_par",
            "validee_le",
            "motif_renvoi",
            "constats",
            "actions_possibles",
        ]
        read_only_fields = (
            "id",
            "mission",
            "soumise_par",
            "soumise_le",
            "validee_par",
            "validee_le",
            "motif_renvoi",
        )

    def get_objectif_code(self, obj: FicheDeTest) -> str:
        return code_objectif(obj.test.programme.objectif)

    @extend_schema_field(ConstatResumeSerializer(many=True))
    def get_constats(self, obj: FicheDeTest) -> list[dict[str, Any]]:
        return [{"id": c.pk, "reference": c.reference} for c in obj.constats.all()]

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: FicheDeTest) -> list[str]:
        cache = cache_mission(self, obj.mission)
        return droits_fiches.actions_fiche(
            obj,
            _acteur(self),
            contexte=cache.contexte,
            statuts=cache.statuts,
            auditeur_id=obj.test.auditeur_id,
        )


class FicheDeTestSerializer(FicheDeTestListeSerializer):
    pieces = PieceJustificativeSerializer(many=True, read_only=True)
    evenements = EvenementFicheSerializer(many=True, read_only=True)

    class Meta(FicheDeTestListeSerializer.Meta):
        fields = [*FicheDeTestListeSerializer.Meta.fields, "pieces", "evenements"]
