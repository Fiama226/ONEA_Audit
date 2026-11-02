from typing import cast

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet

from apps.core.filters import StableOrderingFilter
from apps.core.schema import ERROR_400, ERROR_503, ERROR_RESPONSES

from . import services
from .filters import UtilisateurFilter
from .models import Role, User
from .oidc import purge_userinfo
from .permissions import HasRole
from .serializers import (
    MeSerializer,
    TutorielActionSerializer,
    TutorielSerializer,
    UtilisateurResumeSerializer,
)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer, **ERROR_RESPONSES, **ERROR_503})
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(MeSerializer(user).data)


class TutorielView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentification"],
        summary="Enregistrer l'état du tutoriel d'accueil",
        request=TutorielActionSerializer,
        responses={200: TutorielSerializer, **ERROR_400, **ERROR_RESPONSES, **ERROR_503},
    )
    def post(self, request: Request) -> Response:
        serializer = TutorielActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        compte = services.mettre_a_jour_tutoriel(
            cast(User, request.user),
            action=serializer.validated_data["action"],
            version=serializer.validated_data["version"],
        )
        return Response(TutorielSerializer(compte).data)


class FinSessionView(APIView):
    """Fin de session (D5) : purge l'entree de cache userinfo du jeton presente, avant la
    deconnexion Keycloak. Sans jeton valide : 401."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Authentification"],
        summary="Fin de session : purge le cache userinfo du jeton",
        request=None,
        responses={204: None, **ERROR_RESPONSES, **ERROR_503},
    )
    def post(self, request: Request) -> Response:
        if isinstance(request.auth, str):
            purge_userinfo(request.auth)
        return Response(status=204)


@extend_schema_view(
    list=extend_schema(
        tags=["Utilisateurs"],
        summary="Annuaire des utilisateurs actifs",
        responses={200: UtilisateurResumeSerializer(many=True), **ERROR_400, **ERROR_RESPONSES},
    ),
)
class UtilisateurViewSet(ListModelMixin, GenericViewSet[User]):
    """Annuaire en lecture seule (sélecteurs d'équipe, de participants et d'interlocuteurs)."""

    permission_classes = [HasRole(Role.RAI, Role.AUDITEUR, Role.ADMIN)]
    serializer_class = UtilisateurResumeSerializer
    filter_backends = [DjangoFilterBackend, StableOrderingFilter]
    filterset_class = UtilisateurFilter
    ordering_fields = ("last_name",)
    ordering = ("last_name", "first_name", "username")

    def get_queryset(self) -> QuerySet[User]:
        return User.objects.filter(is_active=True)
