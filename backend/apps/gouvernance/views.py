"""API des règles de gouvernance : lecture ADMIN, RAI et DG ; écriture ADMIN (le service
revérifie le droit en base, aucune délégation ne le donne)."""

from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.schema import ERROR_400, ERROR_404, ERROR_RESPONSES
from apps.users.models import Role, User
from apps.users.permissions import HasRole, IsAdmin

from . import regles_gouvernance as rg
from .serializers import RegleGouvernanceEcritureSerializer, RegleGouvernanceSerializer

TAG = "Règles de gouvernance"
LectureRegles = HasRole(Role.ADMIN, Role.RAI, Role.DG)


def _etat(cle: str) -> dict[str, object]:
    return next(e for e in rg.etat_regles() if e["cle"] == cle)


class RegleGouvernanceListeView(APIView):
    permission_classes = [LectureRegles]

    @extend_schema(
        tags=[TAG],
        operation_id="governance_rules_list",
        summary="Règles de gouvernance (ADMIN, RAI, DG)",
        responses={200: RegleGouvernanceSerializer(many=True), **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        return Response(RegleGouvernanceSerializer(rg.etat_regles(), many=True).data)


class RegleGouvernanceDetailView(APIView):
    def get_permissions(self) -> list[BasePermission]:
        return [(IsAdmin if self.request.method == "PATCH" else LectureRegles)()]

    @extend_schema(
        tags=[TAG],
        operation_id="governance_rules_retrieve",
        summary="Une règle de gouvernance",
        responses={200: RegleGouvernanceSerializer, **ERROR_RESPONSES, **ERROR_404},
    )
    def get(self, request: Request, cle: str) -> Response:
        rg.regle(cle)
        return Response(RegleGouvernanceSerializer(_etat(cle)).data)

    @extend_schema(
        tags=[TAG],
        operation_id="governance_rules_partial_update",
        summary="Modifier une règle de gouvernance (ADMIN)",
        description=(
            "Validation stricte (énumérations, bornes, champs inconnus refusés). Un changement "
            "qui assouplit un contrôle exige un motif et notifie le DG et le RAI. Chaque "
            "changement est écrit dans le journal d'audit."
        ),
        request=RegleGouvernanceEcritureSerializer,
        responses={200: RegleGouvernanceSerializer, **ERROR_400, **ERROR_RESPONSES, **ERROR_404},
    )
    def patch(self, request: Request, cle: str) -> Response:
        rg.regle(cle)
        corps = RegleGouvernanceEcritureSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        rg.modifier(
            cle,
            corps.validated_data["valeur"],
            motif=corps.validated_data["motif"],
            by=cast(User, request.user),
        )
        return Response(RegleGouvernanceSerializer(_etat(cle)).data)
