"""API des règles de gouvernance : lecture ADMIN, RAI et DG ; écriture ADMIN (le service
revérifie le droit en base, aucune délégation ne le donne)."""

from typing import cast
from uuid import UUID

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.schema import ERROR_400, ERROR_404, ERROR_422, ERROR_RESPONSES
from apps.missions.models import EtapeMission
from apps.missions.services import derogations
from apps.users.models import Role, User
from apps.users.permissions import HasRole, IsAdmin

from . import regles_gouvernance as rg
from .serializers import (
    DerogationSerializer,
    EtapeADerogerSerializer,
    RegleGouvernanceEcritureSerializer,
    RegleGouvernanceSerializer,
)

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


class DerogationsReponseAuditeView(APIView):
    """Étapes XIII, XIV et XVI bloquées par l'absence de réponse de l'audité : file de
    l'autorité désignée par la règle « réponse de l'audité » (RAI ou DG)."""

    permission_classes = [HasRole(Role.RAI, Role.DG)]

    @extend_schema(
        tags=[TAG],
        operation_id="auditee_response_waivers_list",
        summary="Étapes en attente d'une dérogation (réponse de l'audité)",
        responses={200: EtapeADerogerSerializer(many=True), **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        attendues = derogations.etapes_a_deroger(cast(User, request.user))
        return Response(EtapeADerogerSerializer(attendues, many=True).data)


class DerogerView(APIView):
    permission_classes = [HasRole(Role.RAI, Role.DG)]

    @extend_schema(
        tags=[TAG],
        operation_id="auditee_response_waivers_waive",
        summary="Déroger à l'absence de réponse de l'audité (motif journalisé)",
        request=DerogationSerializer,
        responses={204: None, **ERROR_400, **ERROR_RESPONSES, **ERROR_404, **ERROR_422},
    )
    def post(self, request: Request, etape_id: UUID) -> Response:
        etape = get_object_or_404(
            EtapeMission.objects.filter(numero__in=derogations.ETAPES_REPONSE_AUDITE),
            pk=etape_id,
        )
        corps = DerogationSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        derogations.deroger(etape, motif=corps.validated_data["motif"], by=cast(User, request.user))
        return Response(status=status.HTTP_204_NO_CONTENT)
