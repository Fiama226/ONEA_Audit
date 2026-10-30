"""ViewSets de l'API du plan d'actions : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403) -> mission ou objet invisible (404) -> droit (403, calculé
par `droits.py`) -> sérialiseur (400, dont `confirme` absent ou faux) -> règle métier, gel ou
fenêtre d'écriture (422, portés par les services).
Les engagements et les acceptations sont en ajout seul : jamais de modification.
"""

import dataclasses
from typing import Any

from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import ModelViewSet

from apps.accomplissement.views import MSG_PARAMETRE, PARAM_MISSION, _uuid, _uuid_du_corps
from apps.constats.permissions import constats_lisibles
from apps.core.schema import (
    ERROR_400,
    ERROR_404,
    ERROR_422,
    ERROR_RESPONSES,
    crud_schema,
)
from apps.missions.models import Mission
from apps.missions.permissions import exiger, mission_du_corps, mission_visible
from apps.missions.views import MissionApiViewSet
from apps.users.models import Role

from . import droits, filters, serializers
from .models import AcceptationRisque, Action, EngagementPlanActions
from .permissions import (
    RecommandationsAccessPermission,
    acceptations_lisibles,
    actions_lisibles,
    engagements_lisibles,
    recommandations_lisibles,
)
from .services import acceptations as svc_acceptations
from .services import actions as svc_actions
from .services import engagements as svc_engagements
from .services.synthese import SynthesePlan, synthese_plan

TAG_ACTIONS = "Actions correctives"
TAG_ACCEPTATIONS = "Acceptations du risque"
TAG_ENGAGEMENTS = "Engagements sur le plan d'actions"
TAG_PLAN = "Plan d'actions"
_UUID_REGEX = "[0-9a-fA-F-]{36}"


class PlanBaseViewSet(MissionApiViewSet):
    """Base : liste bornée à une mission (ou une recommandation) visible, sinon 404."""

    permission_classes = [RecommandationsAccessPermission]
    lookup_value_regex = _UUID_REGEX

    def mission_requise(self, request: Request) -> Mission:
        brut = request.query_params.get("mission")
        if not brut:
            raise ValidationError({"mission": [MSG_PARAMETRE]})
        identifiant = _uuid(brut)
        if identifiant is None:
            raise ValidationError({"mission": ["Identifiant invalide."]})
        return mission_visible(self.acteur, identifiant)

    def verifier_portee(self, request: Request) -> None:
        self.mission_requise(request)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.verifier_portee(request)
        return super().list(request, *args, **kwargs)  # type: ignore[misc, no-any-return]

    def recommandation_du_corps(self, request: Request) -> Any:
        """Recommandation lisible du corps (404 sinon) ; `None` : le sérialiseur répondra 400."""
        identifiant = _uuid_du_corps(request, "recommandation")
        if identifiant is None:
            return None
        return get_object_or_404(
            recommandations_lisibles(self.acteur).select_related("constat", "mission"),
            pk=identifiant,
        )


# --------------------------------------------------------------------------- actions


@crud_schema(serializers.ActionSerializer, TAG_ACTIONS, "actions correctives", creation_404=True)
class ActionViewSet(PlanBaseViewSet, ModelViewSet[Action]):
    serializer_class = serializers.ActionSerializer
    queryset = Action.objects.none()
    filterset_class = filters.ActionFilter
    ordering_fields = ("numero", "reference", "echeance", "created_at")
    ordering = ("numero",)
    audite_actions = frozenset({"list", "retrieve", "create", "partial_update", "destroy"})

    def get_queryset(self) -> QuerySet[Action]:
        return actions_lisibles(self.acteur).select_related(
            "mission", "recommandation__constat", "responsable"
        )

    def get_object(self) -> Any:
        action_ = super().get_object()
        if self.action in ("partial_update", "destroy"):
            contexte = droits.contexte_plan(action_.mission, self.acteur)
            exiger(droits.peut_ecrire_action(action_, self.acteur, contexte=contexte))
        return action_

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        recommandation = self.recommandation_du_corps(request)
        if recommandation is not None:
            contexte = droits.contexte_plan(recommandation.mission, self.acteur)
            exiger(droits.peut_proposer(contexte, recommandation.constat.entite_id))
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[Action]) -> None:
        donnees = dict(serializer.validated_data)
        recommandation = donnees.pop("recommandation")
        libelle = donnees.pop("libelle")
        action_ = svc_actions.creer_action(
            recommandation, libelle=libelle, by=self.acteur, **donnees
        )
        self._publier(serializer, action_)

    def perform_update(self, serializer: BaseSerializer[Action]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(
            serializer.validated_data, instance, ("recommandation",)
        )
        action_ = svc_actions.modifier_action(instance, by=self.acteur, **changements)
        self._publier(serializer, action_)

    def perform_destroy(self, instance: Action) -> None:
        svc_actions.supprimer_action(instance, by=self.acteur)


# --------------------------------------------------------------------------- acceptations


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_ACCEPTATIONS],
        summary="Lister : acceptations du risque",
        responses={
            200: serializers.AcceptationRisqueSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_ACCEPTATIONS],
        summary="Détail : acceptation du risque",
        responses={
            200: serializers.AcceptationRisqueSerializer,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    create=extend_schema(
        tags=[TAG_ACCEPTATIONS],
        summary="Accepter le risque d'une recommandation (confirmé)",
        request=serializers.AcceptationRequestSerializer,
        responses={
            201: serializers.AcceptationRisqueSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class AcceptationViewSet(
    PlanBaseViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
):
    serializer_class = serializers.AcceptationRisqueSerializer
    queryset = AcceptationRisque.objects.none()
    filterset_class = filters.AcceptationFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)
    audite_actions = frozenset({"list", "retrieve", "create", "withdraw"})

    def get_queryset(self) -> QuerySet[AcceptationRisque]:
        return acceptations_lisibles(self.acteur).select_related(
            "auteur", "confirmation__signataire", "recommandation"
        )

    def verifier_portee(self, request: Request) -> None:
        brut = request.query_params.get("recommandation")
        if brut:
            identifiant = _uuid(brut)
            if identifiant is None:
                raise ValidationError({"recommandation": ["Identifiant invalide."]})
            get_object_or_404(recommandations_lisibles(self.acteur), pk=identifiant)
            return
        self.mission_requise(request)

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        exiger(self.acteur.role == Role.AUDITE)
        recommandation = self.recommandation_du_corps(request)
        if recommandation is not None:
            contexte = droits.contexte_plan(recommandation.mission, self.acteur)
            exiger(
                contexte.audite and droits.peut_proposer(contexte, recommandation.constat.entite_id)
            )
        corps = serializers.AcceptationRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        acceptation = svc_acceptations.accepter_risque(
            recommandation or corps.validated_data["recommandation"],
            justification=corps.validated_data["justification"],
            by=self.acteur,
            adresse_ip=self.adresse_ip,
        )
        lue = self.get_queryset().get(pk=acceptation.pk)
        return Response(self.get_serializer(lue).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=[TAG_ACCEPTATIONS],
        summary="Retirer l'acceptation du risque (auteur ou RAI)",
        request=None,
        responses={204: None, **ERROR_RESPONSES, **ERROR_404, **ERROR_422},
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def withdraw(self, request: Request, pk: str | None = None) -> Response:
        acceptation = self.get_object()
        exiger(self.acteur.role == Role.RAI or acceptation.auteur_id == self.acteur.pk)
        svc_acceptations.retirer_acceptation(acceptation, by=self.acteur)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- engagements


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_ENGAGEMENTS],
        summary="Lister : engagements sur le plan d'actions",
        responses={
            200: serializers.EngagementPlanActionsSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    create=extend_schema(
        tags=[TAG_ENGAGEMENTS],
        summary="S'engager sur ses actions (confirmé)",
        request=serializers.EngagementRequestSerializer,
        responses={
            201: serializers.EngagementPlanActionsSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class EngagementViewSet(PlanBaseViewSet, mixins.ListModelMixin, mixins.CreateModelMixin):
    serializer_class = serializers.EngagementPlanActionsSerializer
    queryset = EngagementPlanActions.objects.none()
    filterset_class = filters.EngagementFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)
    audite_actions = frozenset({"list", "create", "texte"})

    def get_queryset(self) -> QuerySet[EngagementPlanActions]:
        return engagements_lisibles(self.acteur).select_related(
            "auteur", "confirmation__signataire"
        )

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        exiger(self.acteur.role == Role.AUDITE)
        mission = mission_du_corps(request)
        if mission is not None:
            exiger(droits.contexte_plan(mission, self.acteur).audite)
        corps = serializers.EngagementRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        engagement = svc_engagements.engager(
            mission or corps.validated_data["mission"],
            by=self.acteur,
            adresse_ip=self.adresse_ip,
        )
        lu = self.get_queryset().get(pk=engagement.pk)
        return Response(self.get_serializer(lu).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        tags=[TAG_ENGAGEMENTS],
        summary="Texte exact à confirmer pour s'engager",
        parameters=[PARAM_MISSION],
        responses={
            200: serializers.TexteEngagementSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    )
    @action(detail=False, methods=["get"], pagination_class=None, filter_backends=[])
    def texte(self, request: Request) -> Response:
        mission = self.mission_requise(request)
        exiger(droits.contexte_plan(mission, self.acteur).audite)
        actions = svc_engagements.actions_du_responsable(mission, self.acteur)
        donnees = {
            "texte": svc_engagements.texte_engagement(mission, self.acteur),
            "nb_actions": len(actions),
            "etat": svc_engagements.etat_depuis(
                actions, svc_engagements.dernier_engagement(mission, self.acteur)
            ),
        }
        return Response(serializers.TexteEngagementSerializer(donnees).data)


# --------------------------------------------------------------------------- synthèse


def _restreindre_a_l_audite(synthese: SynthesePlan, mission: Mission, user: Any) -> SynthesePlan:
    """L'audité ne voit que les lignes de son périmètre : ses constats, ses actions, lui-même."""
    constats = set(
        constats_lisibles(user).filter(mission=mission).values_list("reference", flat=True)
    )
    actions = set(
        actions_lisibles(user).filter(mission=mission).values_list("reference", flat=True)
    )
    responsables = [r for r in synthese.responsables if r.utilisateur.pk == user.pk]
    return dataclasses.replace(
        synthese,
        recommandations=[r for r in synthese.recommandations if r.constat in constats],
        responsables=responsables,
        recommandations_sans_suite=[
            r for r in synthese.recommandations_sans_suite if r.rsplit("-", 1)[0] in constats
        ],
        actions_incompletes=[a for a in synthese.actions_incompletes if a in actions],
        engagements_manquants=[
            r.utilisateur.nom_complet for r in responsables if r.engagement != "CONFIRME"
        ],
    )


class PlanActionsViewSet(MissionApiViewSet):
    """Synthèse du plan d'actions d'une mission (non paginée)."""

    permission_classes = [RecommandationsAccessPermission]
    serializer_class = serializers.SynthesePlanSerializer
    queryset = Mission.objects.none()
    audite_actions = frozenset({"summary"})

    @extend_schema(
        tags=[TAG_PLAN],
        summary="Synthèse du plan d'actions (périmètre de l'audité pour l'audité)",
        parameters=[PARAM_MISSION],
        responses={
            200: serializers.SynthesePlanSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    )
    @action(detail=False, methods=["get"], pagination_class=None, filter_backends=[])
    def summary(self, request: Request) -> Response:
        brut = request.query_params.get("mission")
        if not brut:
            raise ValidationError({"mission": [MSG_PARAMETRE]})
        identifiant = _uuid(brut)
        if identifiant is None:
            raise ValidationError({"mission": ["Identifiant invalide."]})
        mission = mission_visible(self.acteur, identifiant)
        synthese = synthese_plan(mission)
        if self.acteur.role == Role.AUDITE:
            synthese = _restreindre_a_l_audite(synthese, mission, self.acteur)
        return Response(serializers.SynthesePlanSerializer(synthese).data)
