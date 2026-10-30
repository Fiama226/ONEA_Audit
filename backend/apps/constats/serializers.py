"""Sérialiseurs de l'API des constats.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI. Les
droits affichés (`actions_possibles`) viennent de `droits.py`. Le contexte de droits d'une
mission est calculé UNE FOIS par requête (clé `constats` du contexte du sérialiseur).
L'audité ne reçoit ni le détail des fiches, ni le motif de renvoi, ni le risque de la mission.
"""

from typing import Any, cast
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accomplissement.models import FicheDeTest
from apps.missions.models import Mission, RisqueMission
from apps.missions.serializers import CleRelation
from apps.referentiel.models import Direction, NiveauRisque, Processus
from apps.referentiel.serializers import DirectionResumeSerializer
from apps.signatures.serializers import ConfirmationResumeSerializer
from apps.users.models import Role, User
from apps.users.serializers import UtilisateurResumeSerializer

from . import droits
from .models import (
    CategorieCause,
    Constat,
    PositionAudite,
    PrioriteRecommandation,
    Recommandation,
    ReponseAudite,
    StatutConstat,
)
from .services.reponses import texte_reponse

MSG_CONFIRME = "Vous devez confirmer explicitement votre réponse."


def _acteur(serializer: serializers.BaseSerializer[Any]) -> User:
    return cast(User, serializer.context["request"].user)


def _contexte(
    serializer: serializers.BaseSerializer[Any], mission: Mission
) -> droits.ContexteConstats:
    contexte = cast(dict[str, Any], serializer.context)
    caches: dict[UUID, droits.ContexteConstats] = contexte.setdefault("constats", {})
    if mission.pk not in caches:
        caches[mission.pk] = droits.contexte_constats(mission, _acteur(serializer))
    return caches[mission.pk]


class ProcessusResumeSerializer(serializers.ModelSerializer[Processus]):
    class Meta:
        model = Processus
        fields = ("id", "code", "libelle")
        read_only_fields = fields


class FicheConstatResumeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    test_code = serializers.CharField()
    conclusion = serializers.CharField()


class CauseConstatSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(required=False)
    categorie = serializers.ChoiceField(choices=CategorieCause.choices)
    description = serializers.CharField()
    ordre = serializers.IntegerField(required=False, min_value=0)


class RecommandationSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField(required=False)
    libelle = serializers.CharField()
    priorite = serializers.ChoiceField(choices=PrioriteRecommandation.choices)
    ordre = serializers.IntegerField(required=False, min_value=0)


class RecommandationListeSerializer(serializers.ModelSerializer[Recommandation]):
    constat_reference = serializers.CharField(source="constat.reference", read_only=True)
    priorite = serializers.ChoiceField(choices=PrioriteRecommandation.choices, read_only=True)

    class Meta:
        model = Recommandation
        fields = ("id", "mission", "constat", "constat_reference", "libelle", "priorite", "ordre")
        read_only_fields = fields


class ReponseAuditeSerializer(serializers.ModelSerializer[ReponseAudite]):
    auteur = UtilisateurResumeSerializer(read_only=True)
    position = serializers.ChoiceField(choices=PositionAudite.choices, read_only=True)
    confirmation = ConfirmationResumeSerializer(read_only=True)
    version_anterieure = serializers.SerializerMethodField()
    texte = serializers.CharField(source="confirmation.texte", read_only=True)

    class Meta:
        model = ReponseAudite
        fields = (
            "id",
            "constat",
            "cycle",
            "auteur",
            "position",
            "commentaire",
            "confirmation",
            "version_anterieure",
            "texte",
        )
        read_only_fields = fields

    def get_version_anterieure(self, obj: ReponseAudite) -> bool:
        return obj.cycle != obj.constat.cycle


class ReponseRequestSerializer(serializers.Serializer[Any]):
    constat = CleRelation(queryset=Constat.objects.all())
    position = serializers.ChoiceField(choices=PositionAudite.choices)
    commentaire = serializers.CharField(required=False, allow_blank=True, default="")
    confirme = serializers.BooleanField(
        help_text="Doit être vrai : la confirmation explicite de l'audité."
    )
    empreinte_soumise = serializers.CharField(
        max_length=64,
        help_text="Empreinte de la version lue (champ `empreinte_soumise` du constat).",
    )

    def validate_confirme(self, valeur: bool) -> bool:
        if not valeur:
            raise serializers.ValidationError(MSG_CONFIRME)
        return valeur


class TexteReponseSerializer(serializers.Serializer[Any]):
    accord = serializers.CharField()
    desaccord = serializers.CharField()


class ConstatSerializer(serializers.ModelSerializer[Constat]):
    mission = CleRelation(queryset=Mission.objects.all())
    reference = serializers.CharField(read_only=True)
    titre = serializers.CharField(max_length=300, required=False, allow_blank=True)
    statut = serializers.ChoiceField(choices=StatutConstat.choices, read_only=True)
    fiches = CleRelation(queryset=FicheDeTest.objects.all(), many=True, required=False)
    fiches_detail = serializers.SerializerMethodField()
    entite = CleRelation(queryset=Direction.objects.all())
    entite_detail = DirectionResumeSerializer(source="entite", read_only=True)
    processus = CleRelation(queryset=Processus.objects.all())
    processus_detail = ProcessusResumeSerializer(source="processus", read_only=True)
    risque_mission = CleRelation(
        queryset=RisqueMission.objects.all(), required=False, allow_null=True
    )
    score = serializers.IntegerField(read_only=True, allow_null=True)
    niveau = serializers.ChoiceField(choices=NiveauRisque.choices, read_only=True, allow_null=True)
    causes = CauseConstatSerializer(many=True, required=False)
    recommandations = RecommandationSerializer(many=True, required=False)
    motif_renvoi = serializers.CharField(read_only=True, allow_null=True)
    derniere_reponse = serializers.SerializerMethodField()
    reponse_cycle_courant = serializers.SerializerMethodField()
    texte_reponse = serializers.SerializerMethodField()
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = Constat
        fields = (
            "id",
            "mission",
            "reference",
            "titre",
            "statut",
            "fiches",
            "fiches_detail",
            "entite",
            "entite_detail",
            "processus",
            "processus_detail",
            "risque_mission",
            "fait_constate",
            "referentiel",
            "consequence",
            "conclusion",
            "probabilite",
            "impact",
            "score",
            "niveau",
            "causes",
            "recommandations",
            "cycle",
            "soumis_par",
            "soumis_le",
            "validee_par",
            "validee_le",
            "motif_renvoi",
            "empreinte_soumise",
            "derniere_reponse",
            "reponse_cycle_courant",
            "texte_reponse",
            "actions_possibles",
        )
        read_only_fields = (
            "id",
            "cycle",
            "soumis_par",
            "soumis_le",
            "validee_par",
            "validee_le",
            "empreinte_soumise",
        )

    def _audite(self) -> bool:
        return _acteur(self).role == Role.AUDITE

    def to_representation(self, instance: Constat) -> Any:
        donnees = super().to_representation(instance)
        if self._audite():
            donnees["fiches_detail"] = None
            donnees["motif_renvoi"] = None
            donnees["risque_mission"] = None
        return donnees

    @extend_schema_field(FicheConstatResumeSerializer(many=True, allow_null=True))
    def get_fiches_detail(self, obj: Constat) -> list[dict[str, Any]] | None:
        if self._audite():
            return None
        return [
            {"id": f.pk, "test_code": f.test.code, "conclusion": f.conclusion}
            for f in obj.fiches.all()
        ]

    def _reponses(self, obj: Constat) -> list[ReponseAudite]:
        return list(obj.reponses.all())  # préchargées, de la plus récente à la plus ancienne

    @extend_schema_field(ReponseAuditeSerializer(allow_null=True))
    def get_derniere_reponse(self, obj: Constat) -> dict[str, Any] | None:
        reponses = self._reponses(obj)
        if not reponses:
            return None
        return dict(ReponseAuditeSerializer(reponses[0], context=self.context).data)

    def get_reponse_cycle_courant(self, obj: Constat) -> bool:
        reponses = self._reponses(obj)
        return bool(reponses) and reponses[0].cycle == obj.cycle

    @extend_schema_field(TexteReponseSerializer(allow_null=True))
    def get_texte_reponse(self, obj: Constat) -> dict[str, str] | None:
        """Textes exacts que l'audité confirme, pour la version lue (signés tels quels)."""
        if not self._audite() or not obj.empreinte_soumise:
            return None
        acteur = _acteur(self)
        return {
            "accord": texte_reponse(obj, PositionAudite.ACCORD, by=acteur),
            "desaccord": texte_reponse(obj, PositionAudite.DESACCORD, by=acteur),
        }

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: Constat) -> list[str]:
        return droits.actions_constat(obj, _acteur(self), contexte=_contexte(self, obj.mission))
