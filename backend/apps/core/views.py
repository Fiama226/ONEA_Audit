from auditlog.models import LogEntry
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.core.schema import ERROR_400, ERROR_RESPONSES
from apps.users.permissions import IsRAIOrAdmin
from config import __version__

from .filters import AuditLogFilter
from .serializers import AuditLogSerializer


@extend_schema(
    responses=inline_serializer(
        "Health",
        {"status": serializers.CharField(), "version": serializers.CharField()},
    )
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    return Response({"status": "ok", "version": __version__})


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
