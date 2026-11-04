"""OpenAPI helpers: the shared error envelope documented as component ``ApiError``."""

from typing import Any

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.settings import spectacular_settings
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView


class ApiErrorSerializer(serializers.Serializer[dict[str, object]]):
    """Error body returned by the API exception handler (see apps.core.handlers)."""

    detail = serializers.CharField()
    errors = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))  # type: ignore[assignment]


# One entry per status code, so each endpoint documents only what it can really return.
ERROR_400 = {400: ApiErrorSerializer}
ERROR_401 = {401: ApiErrorSerializer}
ERROR_403 = {403: ApiErrorSerializer}
ERROR_404 = {404: ApiErrorSerializer}
ERROR_409 = {409: ApiErrorSerializer}
ERROR_422 = {422: ApiErrorSerializer}
ERROR_429 = {429: ApiErrorSerializer}  # en-tête Retry-After (secondes)
ERROR_503 = {503: ApiErrorSerializer}

# Default error responses for authenticated endpoints.
ERROR_RESPONSES = {**ERROR_401, **ERROR_403}


def crud_schema(
    serializer: type[BaseSerializer[Any]],
    tag: str,
    nom: str,
    *,
    liste: type[BaseSerializer[Any]] | None = None,
    creation_404: bool = False,
    upsert: bool = False,
) -> Any:
    """Documente list / retrieve / create / partial_update / destroy avec leurs erreurs.

    `liste` : sérialiseur allégé de la liste, quand il diffère de celui du détail.
    `creation_404` : la création répond 404 quand l'objet parent (mission) est invisible.
    `upsert` : le POST répond aussi 200 quand l'objet existait déjà (mise à jour).
    """
    return extend_schema_view(
        list=extend_schema(
            tags=[tag],
            summary=f"Lister : {nom}",
            responses={200: (liste or serializer)(many=True), **ERROR_400, **ERROR_RESPONSES},
        ),
        retrieve=extend_schema(
            tags=[tag],
            summary=f"Détail : {nom}",
            responses={200: serializer, **ERROR_RESPONSES, **ERROR_404},
        ),
        create=extend_schema(
            tags=[tag],
            summary=f"Créer : {nom}",
            responses={
                201: serializer,
                **({200: serializer} if upsert else {}),
                **ERROR_400,
                **ERROR_RESPONSES,
                **(ERROR_404 if creation_404 else {}),
                **ERROR_422,
            },
        ),
        partial_update=extend_schema(
            tags=[tag],
            summary=f"Modifier : {nom}",
            responses={
                200: serializer,
                **ERROR_400,
                **ERROR_RESPONSES,
                **ERROR_404,
                **ERROR_422,
            },
        ),
        destroy=extend_schema(
            tags=[tag],
            summary=f"Supprimer (logiquement) : {nom}",
            responses={204: None, **ERROR_RESPONSES, **ERROR_404, **ERROR_422},
        ),
    )


class SchemaAccess(BasePermission):
    """Permission of the schema/docs views: ``SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"]``,
    read at request time (IsAdminUser in production, open in dev/test)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        # spectacular_settings resolves the dotted paths to classes and follows overrides
        return all(
            cls().has_permission(request, view) for cls in spectacular_settings.SERVE_PERMISSIONS
        )


class SessionCookieAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    """Document the in-app session login (cookie + CSRF header on writes) in the schema."""

    target_class = "apps.users.authentication.SessionAuthentication401"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
            "description": (
                "Cookie de session ouvert par POST /api/v1/auth/login/ ; les requêtes "
                "d'écriture joignent l'en-tête X-CSRFToken (GET /api/v1/auth/csrf/)."
            ),
        }

