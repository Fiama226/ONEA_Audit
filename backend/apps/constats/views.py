"""ViewSets de l'API des constats : aucune logique métier, tout passe par `services`.

Ordre des refus : rôle global (403) -> mission ou objet invisible (404) -> droit (403) ->
sérialiseur (400) -> règle métier, gel ou fenêtre d'écriture (422, portés par les services).
L'audité lit les constats soumis ou validés de sa direction et y répond ; rien d'autre.
Les réponses sont en ajout seul : aucune route de modification ni de suppression.
"""

from typing import Any

from django.db.models import Prefetch, QuerySet
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import ModelViewSet

from apps.accomplissement.views import MSG_PARAMETRE, _uuid, _uuid_du_corps
from apps.core.schema import (
    ERROR_400,
    ERROR_404,
    ERROR_RESPONSES,
    ERROR_422,
    crud_schema,
)
from apps.missions.models import Mission
from apps.missions.permissions import exiger, exiger_contribution, mission_visible
from apps.missions.serializers import MotifSerializer
from apps.missions.views import MissionApiViewSet, _action_schema
from apps.users.models import Role

from . import droits, filters, serializers
from .models import Constat, Recommandation, ReponseAudite
from .permissions import ConstatsAccessPermission, constats_lisibles
from .services import constats as svc_constats
from .services import reponses as svc_reponses

TAG_CONSTATS = "Constats"
TAG_REPONSES = "Réponses de l'audité"
TAG_RECOMMANDATIONS = "Recommandations"
_UUID_REGEX = "[0-9a-fA-F-]{36}"


class ConstatsBaseViewSet(MissionApiViewSet):
    """Base : liste bornée à une mission (ou un constat) visible, périmètre de l'audité."""

    permission_classes = [ConstatsAccessPermission]
    lookup_value_regex = _UUID_REGEX

    def verifier_portee(self, request: Request) -> None:
        """La liste exige `mission` (ou `constat` quand la vue le permet) visible, sinon 404."""
        constat = request.query_params.get("constat")
        if (
            constat
            and hasattr(self, "filterset_class")
            and "constat" in self.filterset_class.base_filters
        ):
            identifiant = _uuid(constat)
            if identifiant is None:
                raise ValidationError({"constat": ["Identifiant invalide."]})
            get_object_or_404(constats_lisibles(self.acteur), pk=identifiant)
            return
        brut = request.query_params.get("mission")
        if not brut:
            raise ValidationError({"mission": [MSG_PARAMETRE]})
        identifiant = _uuid(brut)
        if identifiant is None:
            raise ValidationError({"mission": ["Identifiant invalide."]})
        mission_visible(self.acteur, identifiant)

    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.verifier_portee(request)
        return super().list(request, *args, **kwargs)  # type: ignore[misc, no-any-return]

    def lire_donnees(self, pk: Any) -> Any:
        return self.get_serializer(self.get_queryset().get(pk=pk)).data


# --------------------------------------------------------------------------- constats


@crud_schema(serializers.ConstatSerializer, TAG_CONSTATS, "constats", creation_404=True)
class ConstatViewSet(ConstatsBaseViewSet, ModelViewSet[Constat]):
    serializer_class = serializers.ConstatSerializer
    queryset = Constat.objects.none()
    filterset_class = filters.ConstatFilter
    ordering_fields = ("numero", "reference", "score", "created_at")
    ordering = ("numero",)
    audite_actions = frozenset({"list", "retrieve"})
    actions_contribution = frozenset({"partial_update", "destroy"})
    actions_redaction = frozenset({"submit"})
    actions_validation = frozenset({"validate", "return_", "reopen"})

    def get_queryset(self) -> QuerySet[Constat]:
        return (
            constats_lisibles(self.acteur)
            .select_related("mission", "entite", "processus", "risque_mission")
            .prefetch_related(
                "causes",
                "recommandations",
                Prefetch("fiches", queryset=_fiches()),
                Prefetch(
                    "reponses",
                    queryset=ReponseAudite.objects.select_related(
                        "auteur", "confirmation__signataire", "constat"
                    ).order_by("-created_at", "-pk"),
                ),
            )
        )

    def get_object(self) -> Any:
        constat: Constat = super().get_object()
        if self.action in self.actions_redaction:
            exiger_contribution(self.acteur, constat.mission)
            exiger(droits.contexte_constats(constat.mission, self.acteur).chef_ou_rai)
        elif self.action in self.actions_validation:
            exiger(droits.contexte_constats(constat.mission, self.acteur).valideur)
        return constat

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        self.creer_pour_mission(request)
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer: BaseSerializer[Constat]) -> None:
        donnees = dict(serializer.validated_data)
        mission: Mission = donnees.pop("mission")
        titre = donnees.pop("titre", "")
        constat = svc_constats.creer_constat(
            mission,
            titre=titre,
            by=self.acteur,
            fiches=donnees.pop("fiches", ()),
            causes=donnees.pop("causes", ()),
            recommandations=donnees.pop("recommandations", ()),
            **donnees,
        )
        self._publier(serializer, constat)

    def perform_update(self, serializer: BaseSerializer[Constat]) -> None:
        instance = self._cible(serializer)
        changements = self.retirer_immuables(serializer.validated_data, instance, ("mission",))
        causes = changements.pop("causes", None)
        recommandations = changements.pop("recommandations", None)
        constat = svc_constats.modifier_constat(
            instance,
            by=self.acteur,
            causes=causes,
            recommandations=recommandations,
            **changements,
        )
        self._publier(serializer, constat)

    def perform_destroy(self, instance: Constat) -> None:
        svc_constats.supprimer_constat(instance, by=self.acteur)

    @_action_schema("Soumettre le constat", serializers.ConstatSerializer, tag=TAG_CONSTATS)
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def submit(self, request: Request, pk: str | None = None) -> Response:
        constat = self.get_object()
        svc_constats.soumettre_constat(constat, by=self.acteur)
        return Response(self.lire_donnees(constat.pk))

    @_action_schema("Valider le constat", serializers.ConstatSerializer, tag=TAG_CONSTATS)
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def validate(self, request: Request, pk: str | None = None) -> Response:
        constat = self.get_object()
        svc_constats.valider_constat(constat, by=self.acteur)
        return Response(self.lire_donnees(constat.pk))

    @_action_schema(
        "Renvoyer le constat (motif obligatoire)",
        serializers.ConstatSerializer,
        request=MotifSerializer,
        tag=TAG_CONSTATS,
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="return",
        url_name="return",
        pagination_class=None,
        filter_backends=[],
    )
    def return_(self, request: Request, pk: str | None = None) -> Response:
        constat = self.get_object()
        corps = MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_constats.renvoyer_constat(constat, motif=corps.validated_data["motif"], by=self.acteur)
        return Response(self.lire_donnees(constat.pk))

    @_action_schema(
        "Rouvrir un constat validé (motif obligatoire)",
        serializers.ConstatSerializer,
        request=MotifSerializer,
        tag=TAG_CONSTATS,
    )
    @action(detail=True, methods=["post"], pagination_class=None, filter_backends=[])
    def reopen(self, request: Request, pk: str | None = None) -> Response:
        constat = self.get_object()
        corps = MotifSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        svc_constats.rouvrir_constat(constat, motif=corps.validated_data["motif"], by=self.acteur)
        return Response(self.lire_donnees(constat.pk))


def _fiches() -> QuerySet[Any]:
    from apps.accomplissement.models import FicheDeTest

    return FicheDeTest.objects.select_related("test")


# --------------------------------------------------------------------------- réponses


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_REPONSES],
        summary="Lister : réponses de l'audité",
        responses={
            200: serializers.ReponseAuditeSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_REPONSES],
        summary="Détail : réponse de l'audité",
        responses={200: serializers.ReponseAuditeSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
    create=extend_schema(
        tags=[TAG_REPONSES],
        summary="Répondre à un constat (accord ou désaccord, confirmé)",
        request=serializers.ReponseRequestSerializer,
        responses={
            201: serializers.ReponseAuditeSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    ),
)
class ReponseViewSet(
    ConstatsBaseViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    serializer_class = serializers.ReponseAuditeSerializer
    queryset = ReponseAudite.objects.none()
    filterset_class = filters.ReponseFilter
    ordering_fields = ("created_at",)
    ordering = ("created_at",)
    audite_actions = frozenset({"list", "retrieve", "create"})

    def get_queryset(self) -> QuerySet[ReponseAudite]:
        return ReponseAudite.objects.filter(
            constat__in=constats_lisibles(self.acteur)
        ).select_related("auteur", "confirmation__signataire", "constat")

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        exiger(self.acteur.role == Role.AUDITE)
        identifiant = _uuid_du_corps(request, "constat")
        constat = None
        if identifiant is not None:
            constat = get_object_or_404(
                constats_lisibles(self.acteur).select_related("mission", "entite__parent"),
                pk=identifiant,
            )
        corps = serializers.ReponseRequestSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        donnees = corps.validated_data
        if constat is None:  # pragma: no cover - identifiant valide garanti par le sérialiseur
            constat = get_object_or_404(constats_lisibles(self.acteur), pk=donnees["constat"].pk)
        reponse = svc_reponses.repondre(
            constat,
            position=donnees["position"],
            commentaire=donnees["commentaire"],
            empreinte_soumise=donnees["empreinte_soumise"],
            by=self.acteur,
            adresse_ip=self.adresse_ip,
        )
        lue = self.get_queryset().get(pk=reponse.pk)
        return Response(self.get_serializer(lue).data, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------- recommandations


@extend_schema_view(
    list=extend_schema(
        tags=[TAG_RECOMMANDATIONS],
        summary="Lister : recommandations",
        responses={
            200: serializers.RecommandationListeSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_404,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG_RECOMMANDATIONS],
        summary="Détail : recommandation",
        responses={200: serializers.RecommandationListeSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
)
class RecommandationViewSet(
    ConstatsBaseViewSet,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
):
    """Lecture seule : l'écriture passe par les constats (listes imbriquées)."""

    serializer_class = serializers.RecommandationListeSerializer
    queryset = Recommandation.objects.none()
    filterset_class = filters.RecommandationFilter
    ordering_fields = ("ordre", "created_at")
    ordering = ("constat__numero", "ordre")
    audite_actions = frozenset({"list", "retrieve"})

    def get_queryset(self) -> QuerySet[Recommandation]:
        return Recommandation.objects.filter(
            constat__in=constats_lisibles(self.acteur)
        ).select_related("constat")
