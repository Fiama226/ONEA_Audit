"""API `signature-settings` : un réglage par type paramétrable, jamais de suppression."""

from typing import Any, cast

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from apps.core.schema import ERROR_400, ERROR_422, ERROR_RESPONSES
from apps.users.models import User

from . import parametres, serializers
from .models import (
    TYPES_PARAMETRABLES,
    ModeSignatureParametre,
    ParametreSignature,
    TypeDocumentSignable,
)
from .permissions import EcrivainAdmin, LecteurAdminRai

TAG = "Signatures : paramètres"


def _ligne(type_document: str, ligne: ParametreSignature | None) -> dict[str, Any]:
    mode = ModeSignatureParametre(ligne.mode if ligne else ModeSignatureParametre.CONFIRMATION)
    return {
        "type_document": type_document,
        "type_libelle": TypeDocumentSignable(type_document).label,
        "mode": mode.value,
        "mode_libelle": mode.label,
        "modes_disponibles": [
            {"mode": m.value, "libelle": m.label} for m in parametres.modes_disponibles()
        ],
        "modifie_le": ligne.updated_at if ligne else None,
        "modifie_par": ligne.updated_by if ligne else None,
    }


@extend_schema_view(
    list=extend_schema(
        tags=[TAG],
        summary="Lister : modes de signature par type de document",
        responses={200: serializers.ParametreSignatureSerializer(many=True), **ERROR_RESPONSES},
    ),
    partial_update=extend_schema(
        tags=[TAG],
        summary="Modifier : mode de signature d'un type de document",
        request=serializers.ParametreSignatureEcritureSerializer,
        responses={
            200: serializers.ParametreSignatureSerializer,
            **ERROR_RESPONSES,
            **ERROR_400,
            **ERROR_422,
        },
    ),
)
class ParametreSignatureViewSet(GenericViewSet[ParametreSignature]):
    http_method_names = ["get", "patch", "head", "options"]  # ni POST, ni PUT, ni DELETE
    serializer_class = serializers.ParametreSignatureSerializer  # type: ignore[assignment]
    pagination_class = None
    filter_backends = ()
    queryset = ParametreSignature.objects.none()
    lookup_field = "type_document"
    lookup_value_regex = "[A-Za-z0-9_]+"

    def get_permissions(self) -> list[BasePermission]:
        classe = EcrivainAdmin if self.action == "partial_update" else LecteurAdminRai
        return [classe()]

    def list(self, request: Request) -> Response:
        lignes = {
            p.type_document: p
            for p in ParametreSignature.objects.select_related("updated_by").all()
        }
        data = [_ligne(t, lignes.get(t)) for t in TYPES_PARAMETRABLES]
        sortie = serializers.ParametreSignatureSerializer(data, many=True)  # type: ignore[arg-type]
        return Response(sortie.data)

    def partial_update(self, request: Request, type_document: str) -> Response:
        corps = serializers.ParametreSignatureEcritureSerializer(data=request.data)
        corps.is_valid(raise_exception=True)
        ligne = parametres.modifier_mode(
            type_document, mode=corps.validated_data["mode"], by=cast(User, request.user)
        )
        return Response(serializers.ParametreSignatureSerializer(_ligne(type_document, ligne)).data)
