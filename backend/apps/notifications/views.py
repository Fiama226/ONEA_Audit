"""API des notifications : chacun ne voit et ne modifie que les siennes (autrui : 404)."""

from typing import cast

from django.db.models import QuerySet
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core.schema import ERROR_400, ERROR_404, ERROR_RESPONSES
from apps.users.models import User

from . import services
from .filters import NotificationFilter
from .models import Notification
from .serializers import CompteSerializer, NotificationSerializer

TAG = "Notifications"


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Lister mes notifications",
        responses={200: NotificationSerializer(many=True), **ERROR_400, **ERROR_RESPONSES},
    ),
)
class NotificationViewSet(mixins.ListModelMixin, GenericViewSet[Notification]):
    serializer_class = NotificationSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = NotificationFilter

    def get_queryset(self) -> QuerySet[Notification]:
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(destinataire=cast(User, self.request.user)).order_by(
            "-created_at", "-id"
        )

    @extend_schema(
        tags=[TAG],
        summary="Marquer une notification comme lue",
        request=None,
        responses={200: NotificationSerializer, **ERROR_RESPONSES, **ERROR_404},
    )
    @action(detail=True, methods=["post"], filter_backends=[], pagination_class=None)
    def read(self, request: Request, pk: str | None = None) -> Response:
        notification = self.get_object()
        services.marquer_lue(notification, by=cast(User, request.user))
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        tags=[TAG],
        summary="Marquer toutes mes notifications comme lues",
        request=None,
        responses={200: CompteSerializer, **ERROR_RESPONSES},
    )
    @action(
        detail=False,
        methods=["post"],
        url_path="read-all",
        filter_backends=[],
        pagination_class=None,
    )
    def read_all(self, request: Request) -> Response:
        nombre = services.marquer_toutes_lues(cast(User, request.user))
        return Response({"count": nombre})

    @extend_schema(
        tags=[TAG],
        summary="Nombre de notifications non lues",
        responses={200: CompteSerializer, **ERROR_RESPONSES},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="unread-count",
        filter_backends=[],
        pagination_class=None,
    )
    def unread_count(self, request: Request) -> Response:
        return Response({"count": services.nombre_non_lues(cast(User, request.user))})
