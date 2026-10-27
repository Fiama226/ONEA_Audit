from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from config import __version__


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
