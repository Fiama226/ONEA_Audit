"""OpenAPI helpers: the shared error envelope documented as component ``ApiError``."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers
from rest_framework.serializers import BaseSerializer


class ApiErrorSerializer(serializers.Serializer[dict[str, object]]):
    """Error body returned by the API exception handler (see apps.core.handlers)."""

    detail = serializers.CharField()
    errors = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))  # type: ignore[assignment]


# One entry per status code, so each endpoint documents only what it can really return.
ERROR_400 = {400: ApiErrorSerializer}
ERROR_401 = {401: ApiErrorSerializer}
ERROR_403 = {403: ApiErrorSerializer}
ERROR_404 = {404: ApiErrorSerializer}
ERROR_422 = {422: ApiErrorSerializer}
ERROR_503 = {503: ApiErrorSerializer}

# Default error responses for authenticated endpoints.
ERROR_RESPONSES = {**ERROR_401, **ERROR_403}


def crud_schema(serializer: type[BaseSerializer[Any]], tag: str, nom: str) -> Any:
    """Documente list / retrieve / create / partial_update / destroy avec leurs erreurs."""
    return extend_schema_view(
        list=extend_schema(
            tags=[tag],
            summary=f"Lister : {nom}",
            responses={200: serializer(many=True), **ERROR_400, **ERROR_RESPONSES},
        ),
        retrieve=extend_schema(
            tags=[tag],
            summary=f"Détail : {nom}",
            responses={200: serializer, **ERROR_RESPONSES, **ERROR_404},
        ),
        create=extend_schema(
            tags=[tag],
            summary=f"Créer : {nom}",
            responses={201: serializer, **ERROR_400, **ERROR_RESPONSES, **ERROR_422},
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


class SessionAuthentication401Scheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    """Document the project session (cookie) authentication in the schema."""

    target_class = "apps.users.authentication.SessionAuthentication401"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}


class OIDCBearerAuthenticationScheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    """Document the Keycloak bearer-token authentication in the schema."""

    target_class = "apps.users.authentication.OIDCBearerAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Jeton d'accès Keycloak (OIDC) dans l'en-tête Authorization: Bearer.",
        }
