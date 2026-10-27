from typing import cast

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.schema import ERROR_503, ERROR_RESPONSES

from .models import User
from .serializers import MeSerializer


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MeSerializer, **ERROR_RESPONSES, **ERROR_503})
    def get(self, request: Request) -> Response:
        user = cast(User, request.user)
        return Response(MeSerializer(user).data)
