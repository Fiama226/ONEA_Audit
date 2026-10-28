"""ViewSets du référentiel : aucune logique métier, tout passe par `services`."""

import uuid
from typing import Any, ClassVar, cast

from django.db.models import Count, Model, Prefetch, Q, QuerySet
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.viewsets import ModelViewSet

from apps.core.filters import StableOrderingFilter
from apps.core.schema import ERROR_400, ERROR_404, ERROR_422, ERROR_RESPONSES
from apps.users.models import User

from . import services
from .filters import (
    CartographieFilter,
    DirectionFilter,
    ObjetAuditableFilter,
    ProcessusFilter,
    RisqueFilter,
)
from .models import (
    CartographieVersion,
    Direction,
    NatureObjet,
    ObjetAuditable,
    Processus,
    Risque,
)
from .permissions import (
    ECRITURE_CARTOGRAPHIE,
    ECRITURE_STRUCTURE,
    LECTURE_CARTOGRAPHIE,
    TOUS_ROLES,
    RolePermission,
)
from .serializers import (
    CartographieVersionSerializer,
    ComparaisonSerializer,
    DirectionSerializer,
    DomaineArbreSerializer,
    MatriceSerializer,
    ObjetAuditableSerializer,
    ProcessusSerializer,
    RisqueSerializer,
)


def crud_schema(serializer: type[BaseSerializer[Any]], tag: str, nom: str) -> Any:
    """Documente list / retrieve / create / partial_update / destroy avec leurs erreurs."""
    return extend_schema_view(
        list=extend_schema(
            tags=[tag],
            summary=f"Lister : {nom}",
            responses={200: serializer(many=True), **ERROR_400, **ERROR_RESPONSES},
        ),
        retrieve=extend_schema(
            tags=[tag],
            summary=f"Détail : {nom}",
            responses={200: serializer, **ERROR_RESPONSES, **ERROR_404},
        ),
        create=extend_schema(
            tags=[tag],
            summary=f"Créer : {nom}",
            responses={201: serializer, **ERROR_400, **ERROR_RESPONSES, **ERROR_422},
        ),
        partial_update=extend_schema(
            tags=[tag],
            summary=f"Modifier : {nom}",
            responses={
                200: serializer,
                **ERROR_400,
                **ERROR_RESPONSES,
                **ERROR_404,
                **ERROR_422,
            },
        ),
        destroy=extend_schema(
            tags=[tag],
            summary=f"Supprimer (logiquement) : {nom}",
            responses={204: None, **ERROR_RESPONSES, **ERROR_404, **ERROR_422},
        ),
    )


class ReferentielViewSet[M: Model](ModelViewSet[M]):
    """Base : droits par rôle, pas de PUT, création / modification / suppression par service."""

    permission_classes = [RolePermission]
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    read_roles: ClassVar[tuple[str, ...]] = TOUS_ROLES
    write_roles: ClassVar[tuple[str, ...]] = ECRITURE_STRUCTURE

    @property
    def acteur(self) -> User:
        return cast(User, self.request.user)

    def _cible(self, serializer: BaseSerializer[Any]) -> M:
        return cast(M, serializer.instance)

    def _publier(self, serializer: BaseSerializer[Any], obj: Model) -> None:
        """Renvoie la représentation de lecture (annotations et préchargements inclus)."""
        serializer.instance = self.get_queryset().get(pk=obj.pk)


# --------------------------------------------------------------------------- structure


@crud_schema(DirectionSerializer, "Référentiel", "directions et départements")
class DirectionViewSet(ReferentielViewSet[Direction]):
    queryset = Direction.objects.select_related("parent")
    serializer_class = DirectionSerializer
    filterset_class = DirectionFilter
    ordering_fields = ("code", "libelle")
    ordering = ("code",)

    def perform_create(self, serializer: BaseSerializer[Direction]) -> None:
        obj = services.creer_direction(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, obj)

    def perform_update(self, serializer: BaseSerializer[Direction]) -> None:
        obj = services.modifier_direction(
            self._cible(serializer), **serializer.validated_data, by=self.acteur
        )
        self._publier(serializer, obj)

    def perform_destroy(self, instance: Direction) -> None:
        services.supprimer_direction(instance, by=self.acteur)


@crud_schema(ProcessusSerializer, "Référentiel", "processus")
class ProcessusViewSet(ReferentielViewSet[Processus]):
    queryset = Processus.objects.prefetch_related("directions")
    serializer_class = ProcessusSerializer
    filterset_class = ProcessusFilter
    ordering_fields = ("ordre", "code", "libelle")
    ordering = ("ordre", "code")

    def perform_create(self, serializer: BaseSerializer[Processus]) -> None:
        obj = services.creer_processus(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, obj)

    def perform_update(self, serializer: BaseSerializer[Processus]) -> None:
        obj = services.modifier_processus(
            self._cible(serializer), **serializer.validated_data, by=self.acteur
        )
        self._publier(serializer, obj)

    def perform_destroy(self, instance: Processus) -> None:
        services.supprimer_processus(instance, by=self.acteur)


@crud_schema(ObjetAuditableSerializer, "Cartographie", "objets auditables")
class ObjetAuditableViewSet(ReferentielViewSet[ObjetAuditable]):
    queryset = ObjetAuditable.objects.all()
    serializer_class = ObjetAuditableSerializer
    filterset_class = ObjetAuditableFilter
    ordering_fields = ("ordre", "libelle")
    ordering = ("ordre", "libelle")
    read_roles = LECTURE_CARTOGRAPHIE
    write_roles = ECRITURE_CARTOGRAPHIE

    def perform_create(self, serializer: BaseSerializer[ObjetAuditable]) -> None:
        obj = services.creer_objet(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, obj)

    def perform_update(self, serializer: BaseSerializer[ObjetAuditable]) -> None:
        obj = services.modifier_objet(
            self._cible(serializer), **serializer.validated_data, by=self.acteur
        )
        self._publier(serializer, obj)

    def perform_destroy(self, instance: ObjetAuditable) -> None:
        services.supprimer_objet(instance, by=self.acteur)

    @extend_schema(
        tags=["Cartographie"],
        summary="Arbre domaines / opérations d'un processus",
        parameters=[
            OpenApiParameter("processus", OpenApiTypes.UUID, required=True),
        ],
        responses={200: DomaineArbreSerializer(many=True), **ERROR_400, **ERROR_RESPONSES},
    )
    @action(detail=False, methods=["get"], pagination_class=None, filter_backends=[])
    def tree(self, request: Request) -> Response:
        brut = request.query_params.get("processus")
        if not brut:
            raise ValidationError({"processus": ["Ce paramètre est obligatoire."]})
        try:
            processus_id = uuid.UUID(brut)
        except ValueError as e:
            raise ValidationError({"processus": ["Identifiant invalide."]}) from e
        domaines = ObjetAuditable.objects.filter(
            processus_id=processus_id, nature=NatureObjet.DOMAINE
        ).prefetch_related(
            Prefetch(
                "operations", queryset=ObjetAuditable.objects.order_by("ordre", "libelle", "pk")
            )
        )
        return Response(
            DomaineArbreSerializer(domaines.order_by("ordre", "libelle", "pk"), many=True).data
        )


# --------------------------------------------------------------------------- cartographie


@crud_schema(CartographieVersionSerializer, "Cartographie", "cartographies des risques")
class CartographieVersionViewSet(ReferentielViewSet[CartographieVersion]):
    serializer_class = CartographieVersionSerializer
    filterset_class = CartographieFilter
    ordering_fields = ("annee",)
    ordering = ("-annee",)
    read_roles = LECTURE_CARTOGRAPHIE
    write_roles = ECRITURE_CARTOGRAPHIE

    def get_queryset(self) -> QuerySet[CartographieVersion]:
        return CartographieVersion.objects.select_related("validee_par").annotate(
            nb_risques=Count("risques", filter=Q(risques__deleted_at__isnull=True))
        )

    def perform_create(self, serializer: BaseSerializer[CartographieVersion]) -> None:
        obj = services.creer_version(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, obj)

    def perform_update(self, serializer: BaseSerializer[CartographieVersion]) -> None:
        obj = services.modifier_version(
            self._cible(serializer), **serializer.validated_data, by=self.acteur
        )
        self._publier(serializer, obj)

    def perform_destroy(self, instance: CartographieVersion) -> None:
        services.supprimer_version(instance, by=self.acteur)

    @extend_schema(
        tags=["Cartographie"],
        summary="Valider (figer) une cartographie",
        request=None,
        responses={
            200: CartographieVersionSerializer,
            **ERROR_RESPONSES,
            **ERROR_404,
            **ERROR_422,
        },
    )
    @action(detail=True, methods=["post"], pagination_class=None)
    def validate(self, request: Request, pk: str | None = None) -> Response:
        version = self.get_object()
        services.valider_version(version, by=self.acteur)
        return Response(CartographieVersionSerializer(self.get_queryset().get(pk=version.pk)).data)

    @extend_schema(
        tags=["Cartographie"],
        summary="Matrice 5x5 des risques d'une cartographie",
        responses={200: MatriceSerializer, **ERROR_RESPONSES, **ERROR_404},
    )
    @action(detail=True, methods=["get"], pagination_class=None)
    def matrix(self, request: Request, pk: str | None = None) -> Response:
        return Response(MatriceSerializer(services.resume_matrice(self.get_object())).data)

    @extend_schema(
        tags=["Cartographie"],
        summary="Comparer deux cartographies (référence = celle de l'URL)",
        parameters=[
            OpenApiParameter(
                "with",
                OpenApiTypes.UUID,
                required=True,
                description="Cartographie cible : « ajoutés » = présents dans la cible seulement.",
            ),
        ],
        responses={200: ComparaisonSerializer, **ERROR_400, **ERROR_RESPONSES, **ERROR_404},
    )
    @action(detail=True, methods=["get"], pagination_class=None)
    def compare(self, request: Request, pk: str | None = None) -> Response:
        reference = self.get_object()
        brut = request.query_params.get("with")
        if not brut:
            raise ValidationError({"with": ["Ce paramètre est obligatoire."]})
        try:
            cible_id = uuid.UUID(brut)
        except ValueError as e:
            raise ValidationError({"with": ["Identifiant invalide."]}) from e
        cible = get_object_or_404(CartographieVersion.objects.all(), pk=cible_id)
        resultat = services.comparer_versions(reference, cible)
        return Response(
            ComparaisonSerializer(
                {
                    "reference": reference,
                    "cible": cible,
                    "ajoutes": resultat.ajoutes,
                    "retires": resultat.retires,
                    "modifies": resultat.modifies,
                }
            ).data
        )


@crud_schema(RisqueSerializer, "Cartographie", "risques")
class RisqueViewSet(ReferentielViewSet[Risque]):
    queryset = Risque.objects.select_related("version", "processus", "objet_auditable")
    serializer_class = RisqueSerializer
    filterset_class = RisqueFilter
    ordering_fields = ("numero", "code", "score")
    ordering = ("numero",)
    read_roles = LECTURE_CARTOGRAPHIE
    write_roles = ECRITURE_CARTOGRAPHIE

    def perform_create(self, serializer: BaseSerializer[Risque]) -> None:
        obj = services.creer_risque(**serializer.validated_data, by=self.acteur)
        self._publier(serializer, obj)

    def perform_update(self, serializer: BaseSerializer[Risque]) -> None:
        obj = services.modifier_risque(
            self._cible(serializer), **serializer.validated_data, by=self.acteur
        )
        self._publier(serializer, obj)

    def perform_destroy(self, instance: Risque) -> None:
        services.supprimer_risque(instance, by=self.acteur)
