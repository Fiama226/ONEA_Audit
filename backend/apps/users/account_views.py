"""Admin API for user accounts: no business logic here, everything goes through services."""

from typing import Any, cast

from django.db.models import OuterRef, QuerySet, Subquery
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, serializers
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core.filters import StableOrderingFilter
from apps.core.schema import ERROR_400, ERROR_404, ERROR_422, ERROR_503, ERROR_RESPONSES
from apps.referentiel.models import Direction

from . import provisioning, services
from .account_filters import UserAccountFilter
from .account_permissions import AccountAdminPermission
from .account_serializers import (
    CompteUtilisateurListeSerializer,
    CompteUtilisateurSerializer,
    EntreeAnnuaireSerializer,
    ImportAnnuaireSerializer,
    ImportCsvSerializer,
    MotifDesactivationSerializer,
    ProfilUtilisateurSerializer,
    RapportImportSerializer,
)
from .keycloak_admin import KeycloakIndisponible, KeycloakNonConfigure
from .keycloak_sync import relancer_synchronisation, synchroniser_keycloak
from .models import User
from .provisioning import FichierImportInvalide

TAG = "Comptes utilisateurs"
ANNUAIRE_INDISPONIBLE = "L'annuaire (Keycloak) est momentanément indisponible. Réessayez plus tard."
Q_MIN, Q_MAX = 2, 100

_COMPTE = {"200": None}
_ERREURS_ACTION = {**ERROR_RESPONSES, **ERROR_404, **ERROR_422}


def _annuaire_indisponible() -> Response:
    return Response({"detail": ANNUAIRE_INDISPONIBLE, "errors": {}}, status=503)


class _RechercheSerializer(serializers.Serializer[dict[str, str]]):
    q = serializers.CharField(min_length=Q_MIN, max_length=Q_MAX)


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Lister : comptes utilisateurs",
        responses={
            200: CompteUtilisateurListeSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
        },
    ),
    retrieve=extend_schema(
        tags=[TAG],
        summary="Détail : compte utilisateur",
        responses={200: CompteUtilisateurSerializer, **ERROR_RESPONSES, **ERROR_404},
    ),
)
class UserAccountViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, GenericViewSet[User]):
    permission_classes = [AccountAdminPermission]
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    filterset_class = UserAccountFilter
    http_method_names = ["get", "patch", "post"]
    lookup_value_regex = r"\d+"
    ordering_fields = (
        "last_name",
        "username",
        "role",
        "direction_code",
        "is_active",
        "date_joined",
    )
    ordering = ("last_name", "first_name", "pk")

    def get_queryset(self) -> QuerySet[User]:
        libelle = Direction.objects.filter(
            code=OuterRef("direction_code"), deleted_at__isnull=True
        ).values("libelle")[:1]
        return User.objects.select_related("desactive_par").annotate(
            direction_libelle=Subquery(libelle)
        )

    def get_serializer_class(self) -> type[serializers.BaseSerializer[Any]]:
        if self.action == "list":
            return CompteUtilisateurListeSerializer
        return CompteUtilisateurSerializer

    @property
    def acteur(self) -> User:
        return cast(User, self.request.user)

    def _reponse(self, compte: User) -> Response:
        frais = self.get_queryset().get(pk=compte.pk)
        data = CompteUtilisateurSerializer(frais, context=self.get_serializer_context()).data
        return Response(data)

    @extend_schema(
        tags=[TAG],
        summary="Modifier le profil d'un compte",
        request=ProfilUtilisateurSerializer,
        responses={200: CompteUtilisateurSerializer, **ERROR_400, **_ERREURS_ACTION},
    )
    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        compte = self.get_object()
        serializer = ProfilUtilisateurSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.modifier_profil(compte, changes=serializer.validated_data, by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Désactiver un compte",
        request=MotifDesactivationSerializer,
        responses={200: CompteUtilisateurSerializer, **ERROR_400, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        serializer = MotifDesactivationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.desactiver(compte, motif=serializer.validated_data["motif"], by=self.acteur)
        synchroniser_keycloak(compte.pk, by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Réactiver un compte",
        request=None,
        responses={200: CompteUtilisateurSerializer, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["post"])
    def reactivate(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        services.reactiver(compte, by=self.acteur)
        synchroniser_keycloak(compte.pk, by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Rendre direction et fonction à l'annuaire",
        request=None,
        responses={200: CompteUtilisateurSerializer, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["post"], url_path="resync-profile")
    def resync_profile(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        services.resynchroniser_profil(compte, by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Relancer la synchronisation avec Keycloak",
        request=None,
        responses={200: CompteUtilisateurSerializer, **_ERREURS_ACTION},
    )
    @action(detail=True, methods=["post"], url_path="retry-keycloak-sync")
    def retry_keycloak_sync(self, request: Request, pk: str) -> Response:
        compte = self.get_object()
        relancer_synchronisation(compte, by=self.acteur)
        return self._reponse(compte)

    @extend_schema(
        tags=[TAG],
        summary="Rechercher dans l'annuaire Keycloak",
        parameters=[
            OpenApiParameter(
                "q", OpenApiTypes.STR, required=True, description="2 à 100 caractères."
            )
        ],
        responses={
            200: EntreeAnnuaireSerializer(many=True),
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_503,
        },
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="directory-search",
        filter_backends=[],
        pagination_class=None,
    )
    def directory_search(self, request: Request) -> Response:
        recherche = _RechercheSerializer(data=request.query_params)
        recherche.is_valid(raise_exception=True)
        try:
            entrees = provisioning.rechercher_annuaire(recherche.validated_data["q"])
        except (KeycloakIndisponible, KeycloakNonConfigure):
            return _annuaire_indisponible()
        return Response(EntreeAnnuaireSerializer(entrees, many=True).data)  # type: ignore[arg-type]

    @extend_schema(
        tags=[TAG],
        summary="Importer des comptes depuis l'annuaire Keycloak",
        request=ImportAnnuaireSerializer,
        responses={200: RapportImportSerializer, **ERROR_400, **ERROR_RESPONSES, **ERROR_503},
    )
    @action(detail=False, methods=["post"], url_path="import-directory")
    def import_directory(self, request: Request) -> Response:
        serializer = ImportAnnuaireSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rapport = provisioning.importer_depuis_annuaire(
                serializer.validated_data["keycloak_ids"], by=self.acteur, dry_run=False
            )
        except (KeycloakIndisponible, KeycloakNonConfigure):
            return _annuaire_indisponible()
        return Response(RapportImportSerializer(rapport).data)

    @extend_schema(
        tags=[TAG],
        summary="Importer des comptes depuis un fichier CSV",
        request={"multipart/form-data": ImportCsvSerializer},
        responses={200: RapportImportSerializer, **ERROR_400, **ERROR_RESPONSES},
    )
    @action(detail=False, methods=["post"], url_path="import-csv", parser_classes=[MultiPartParser])
    def import_csv(self, request: Request) -> Response:
        serializer = ImportCsvSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        contenu = serializer.validated_data["fichier"].read(provisioning.CSV_MAX_BYTES + 1)
        try:
            rapport = provisioning.importer_csv(
                contenu, by=self.acteur, dry_run=serializer.validated_data["dry_run"]
            )
        except FichierImportInvalide as exc:
            raise serializers.ValidationError({"fichier": [exc.message]}) from exc
        return Response(RapportImportSerializer(rapport).data)
