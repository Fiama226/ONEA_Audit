from auditlog.models import LogEntry
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.users.permissions import IsRAIOrAdmin

from .filters import AuditLogFilter
from .serializers import AuditLogSerializer

VERSION = "0.1.0"


@extend_schema(
    responses=inline_serializer(
        "Health",
        {"status": serializers.CharField(), "version": serializers.CharField()},
    )
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request: Request) -> Response:
    return Response({"status": "ok", "version": VERSION})


@extend_schema_view(
    list=extend_schema(operation_id="audit_log_list", summary="Piste d'audit (ADMIN, RAI)"),
    retrieve=extend_schema(operation_id="audit_log_retrieve"),
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
