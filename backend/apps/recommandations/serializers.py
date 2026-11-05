"""Sérialiseurs de l'API du plan d'actions.

Les noms des classes (sans le suffixe `Serializer`) sont les noms des composants OpenAPI. Les
droits affichés (`actions_possibles`) viennent de `droits.py`, dont le contexte d'une mission
est calculé UNE FOIS par requête (clé `plan` du contexte du sérialiseur).
"""

from typing import Any, cast
from uuid import UUID

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.constats.models import PrioriteRecommandation, Recommandation
from apps.missions.models import Mission
from apps.missions.serializers import CleRelation
from apps.signatures.serializers import ConfirmationResumeSerializer
from apps.users.models import User
from apps.users.serializers import UtilisateurResumeSerializer

from . import droits
from .models import (
    AcceptationRisque,
    Action,
    DecisionAcceptation,
    EngagementPlanActions,
    StatutAction,
    ValidateurAcceptation,
    ValidationAcceptation,
)
from .services import statuts

MSG_CONFIRME = "Cochez la case de confirmation."

STATUT_DERIVE_CHOICES = [(code, libelle) for code, libelle in statuts.LIBELLES.items()]
ETAT_ENGAGEMENT_CHOICES = [
    ("CONFIRME", "Confirmé"),
    ("A_RENOUVELER", "À renouveler"),
    ("NON_CONFIRME", "Non confirmé"),
]


def _acteur(serializer: serializers.BaseSerializer[Any]) -> User:
    return cast(User, serializer.context["request"].user)


def _contexte(serializer: serializers.BaseSerializer[Any], mission: Mission) -> droits.ContextePlan:
    contexte = cast(dict[str, Any], serializer.context)
    caches: dict[UUID, droits.ContextePlan] = contexte.setdefault("plan", {})
    if mission.pk not in caches:
        caches[mission.pk] = droits.contexte_plan(mission, _acteur(serializer))
    return caches[mission.pk]


class ActionSerializer(serializers.ModelSerializer[Action]):
    mission = serializers.PrimaryKeyRelatedField[Mission](read_only=True)
    recommandation = CleRelation(queryset=Recommandation.objects.all())
    constat_reference = serializers.CharField(
        source="recommandation.constat.reference", read_only=True
    )
    reference = serializers.CharField(read_only=True)
    libelle = serializers.CharField()
    responsable = CleRelation(queryset=User.objects.all(), required=False, allow_null=True)
    responsable_detail = UtilisateurResumeSerializer(
        source="responsable", read_only=True, allow_null=True
    )
    statut = serializers.ChoiceField(choices=StatutAction.choices, read_only=True)
    proposee_par = serializers.PrimaryKeyRelatedField[User](read_only=True)
    actions_possibles = serializers.SerializerMethodField()

    class Meta:
        model = Action
        fields = (
            "id",
            "mission",
            "recommandation",
            "constat_reference",
            "reference",
            "libelle",
            "responsable",
            "responsable_detail",
            "echeance",
            "indicateur",
            "moyens",
            "ordre",
            "statut",
            "proposee_par",
            "actions_possibles",
        )
        read_only_fields = ("id",)

    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_actions_possibles(self, obj: Action) -> list[str]:
        return droits.actions_action(obj, _acteur(self), contexte=_contexte(self, obj.mission))


class ValidationAcceptationSerializer(serializers.ModelSerializer[ValidationAcceptation]):
    par = UtilisateurResumeSerializer(read_only=True)

    class Meta:
        model = ValidationAcceptation
        fields = ("niveau", "decision", "par", "le", "motif", "reference_conseil")
        read_only_fields = fields


class AcceptationRisqueSerializer(serializers.ModelSerializer[AcceptationRisque]):
    auteur = UtilisateurResumeSerializer(read_only=True)
    confirmation = ConfirmationResumeSerializer(read_only=True)
    texte = serializers.CharField(source="confirmation.texte", read_only=True)
    validation_requise = serializers.ChoiceField(
        choices=ValidateurAcceptation.choices,
        allow_blank=True,
        read_only=True,
        help_text=(
            "Autorité qui doit valider l'acceptation (règle de gouvernance, figée à la "
            "création) ; vide : aucune validation."
        ),
    )
    validation = serializers.SerializerMethodField()

    class Meta:
        model = AcceptationRisque
        fields = (
            "id",
            "recommandation",
            "justification",
            "auteur",
            "confirmation",
            "texte",
            "niveau_risque",
            "validation_requise",
            "validation",
        )
        read_only_fields = fields

    @extend_schema_field(ValidationAcceptationSerializer(allow_null=True))
    def get_validation(self, obj: AcceptationRisque) -> dict[str, Any] | None:
        validation = next(iter(obj.validations.all()), None)
        return dict(ValidationAcceptationSerializer(validation).data) if validation else None


class AcceptationAValiderSerializer(serializers.Serializer[Any]):
    """Acceptation de risque en attente de la décision de l'utilisateur (RAI ou DG)."""

    id = serializers.UUIDField()
    mission_id = serializers.UUIDField()
    mission_reference = serializers.CharField(source="mission.reference")
    mission_titre = serializers.CharField(source="mission.titre")
    constat_reference = serializers.CharField(source="recommandation.constat.reference")
    constat_titre = serializers.CharField(source="recommandation.constat.titre")
    recommandation = serializers.CharField(source="recommandation.libelle")
    niveau_risque = serializers.CharField()
    justification = serializers.CharField()
    auteur = UtilisateurResumeSerializer()
    acceptee_le = serializers.DateTimeField(source="created_at")
    validation_requise = serializers.ChoiceField(choices=ValidateurAcceptation.choices)


class DecisionAcceptationSerializer(serializers.Serializer[Any]):
    decision = serializers.ChoiceField(choices=DecisionAcceptation.choices)
    motif = serializers.CharField(max_length=2000, allow_blank=True)
    reference_conseil = serializers.CharField(
        max_length=120,
        required=False,
        allow_blank=True,
        default="",
        help_text="Obligatoire quand la décision est celle du Conseil.",
    )


class _ConfirmeMixin(serializers.Serializer[Any]):
    confirme = serializers.BooleanField(
        help_text="Doit être vrai : la confirmation explicite de l'audité."
    )

    def validate_confirme(self, valeur: bool) -> bool:
        if not valeur:
            raise serializers.ValidationError(MSG_CONFIRME)
        return valeur


class AcceptationRequestSerializer(_ConfirmeMixin):
    recommandation = CleRelation(queryset=Recommandation.objects.all())
    justification = serializers.CharField(allow_blank=True)


class EngagementPlanActionsSerializer(serializers.ModelSerializer[EngagementPlanActions]):
    auteur = UtilisateurResumeSerializer(read_only=True)
    confirmation = ConfirmationResumeSerializer(read_only=True)
    texte = serializers.CharField(source="confirmation.texte", read_only=True)

    class Meta:
        model = EngagementPlanActions
        fields = ("id", "mission", "auteur", "confirmation", "texte", "empreinte_actions")
        read_only_fields = fields


class EngagementRequestSerializer(_ConfirmeMixin):
    mission = CleRelation(queryset=Mission.objects.all())


class TexteEngagementSerializer(serializers.Serializer[Any]):
    texte = serializers.CharField(help_text="Texte exact que l'audité confirme.")
    nb_actions = serializers.IntegerField()
    etat = serializers.ChoiceField(choices=ETAT_ENGAGEMENT_CHOICES)


class AcceptationResumeSerializer(serializers.Serializer[Any]):
    id = serializers.UUIDField()
    auteur = serializers.IntegerField(source="auteur_id")
    justification = serializers.CharField()


class LigneRecommandationSerializer(serializers.Serializer[Any]):
    constat = serializers.CharField()
    reference = serializers.CharField()
    libelle = serializers.CharField()
    priorite = serializers.ChoiceField(choices=PrioriteRecommandation.choices)
    statut_derive = serializers.ChoiceField(choices=STATUT_DERIVE_CHOICES)
    nb_actions = serializers.IntegerField()
    acceptation = AcceptationResumeSerializer(allow_null=True)


class LigneResponsableSerializer(serializers.Serializer[Any]):
    utilisateur = UtilisateurResumeSerializer()
    nb_actions = serializers.IntegerField()
    prochaine_echeance = serializers.DateField(allow_null=True)
    engagement = serializers.ChoiceField(choices=ETAT_ENGAGEMENT_CHOICES)


class SynthesePlanSerializer(serializers.Serializer[Any]):
    recommandations = LigneRecommandationSerializer(many=True)
    responsables = LigneResponsableSerializer(many=True)
    recommandations_sans_suite = serializers.ListField(child=serializers.CharField())
    actions_incompletes = serializers.ListField(child=serializers.CharField())
    engagements_manquants = serializers.ListField(child=serializers.CharField())
