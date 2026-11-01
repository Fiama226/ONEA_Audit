import hmac
from typing import cast

from auditlog.models import LogEntry
from django.conf import settings
from django.http import Http404, HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.core import metriques
from apps.core.schema import ERROR_400, ERROR_RESPONSES
from apps.documents.stockage import etat_stockage
from apps.users.models import User
from apps.users.permissions import IsAdmin, IsRAIOrAdmin
from config import __version__

from . import parametres
from .filters import AuditLogFilter
from .serializers import (
    AuditLogSerializer,
    ParametreJournalEcritureSerializer,
    ParametreJournalSerializer,
)


@extend_schema(
    responses=inline_serializer(
        "Health",
        {
            "status": serializers.CharField(),
            "version": serializers.CharField(),
            "stockage_documents": serializers.CharField(),
        },
    )
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    # The documents storage state is informative: it never alters `status`.
    return Response({"status": "ok", "version": __version__, "stockage_documents": etat_stockage()})


@extend_schema(exclude=True)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def ready(request: Request) -> Response:
    """Readiness probe: 503 if the database or Redis is down, 200 degraded otherwise."""
    composants = metriques.etat_composants()
    if "indisponible" in (composants["base"], composants["redis"]):
        return Response({"status": "indisponible", "composants": composants}, status=503)
    degrade = composants["gotenberg"] != "ok" or composants["beat"] == "perime"
    return Response({"status": "degrade" if degrade else "ok", "composants": composants})


@extend_schema(exclude=True)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def metrics(request: Request) -> HttpResponse:
    """Protected metrics: 404 unless the configured bearer token is presented."""
    attendu = settings.METRICS_TOKEN
    entete = request.headers.get("Authorization", "")
    fourni = entete[7:] if entete.lower().startswith("bearer ") else ""
    if not attendu or not hmac.compare_digest(fourni.encode(), attendu.encode()):
        raise Http404
    return HttpResponse(metriques.exposition(), content_type="text/plain; version=0.0.4")


@extend_schema_view(
    list=extend_schema(
        operation_id="audit_log_list",
        summary="Piste d'audit (ADMIN, RAI)",
        responses={200: AuditLogSerializer(many=True), **ERROR_400, **ERROR_RESPONSES},
    ),
    retrieve=extend_schema(
        operation_id="audit_log_retrieve",
        responses={200: AuditLogSerializer, **ERROR_RESPONSES},
    ),
)
class AuditLogViewSet(ReadOnlyModelViewSet[LogEntry]):
    """Immutable, read-only view of the audit trail."""

    queryset = LogEntry.objects.select_related("actor", "content_type").order_by(
        "-timestamp", "-id"
    )
    serializer_class = AuditLogSerializer
    permission_classes = [IsRAIOrAdmin]
    filterset_class = AuditLogFilter
    filter_backends = [DjangoFilterBackend]


def _reglage_journal() -> dict[str, object]:
    ligne = parametres.ligne_contenu_journal()
    valeur = ligne.valeur if ligne else parametres.ContenuJournal.COMPLET
    return {
        "valeur": parametres.contenu_journal(),
        "valeur_libelle": parametres.ContenuJournal.LIBELLES[valeur]
        if valeur in parametres.ContenuJournal.LIBELLES
        else valeur,
        "modifie_le": ligne.updated_at if ligne else None,
        "modifie_par": ligne.updated_by if ligne else None,
    }


class ParametreJournalView(APIView):
    """Contenu des missions dans la piste d'audit pour l'ADMIN (SEC-02) : lecture ADMIN/RAI."""

    def get_permissions(self) -> list[BasePermission]:
        return [(IsAdmin if self.request.method == "PATCH" else IsRAIOrAdmin)()]

    @extend_schema(
        operation_id="audit_log_settings_retrieve",
        summary="Réglage : contenu des missions dans la piste d'audit",
        responses={200: ParametreJournalSerializer, **ERROR_RESPONSES},
    )
    def get(self, request: Request) -> Response:
        return Response(ParametreJournalSerializer(_reglage_journal()).data)

    @extend_schema(
        operation_id="audit_log_settings_partial_update",
        summary="Modifier : contenu des missions dans la piste d'audit",
        request=ParametreJournalEcritureSerializer,
        responses={200: ParametreJournalSerializer, **ERROR_RESPONSES, **ERROR_400},
    )
    def patch(self, request: Request) -> Response:
        corps = ParametreJournalEcritureSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        parametres.modifier_contenu_journal(
            corps.validated_data["valeur"], by=cast(User, request.user)
        )
        return Response(ParametreJournalSerializer(_reglage_journal()).data)
