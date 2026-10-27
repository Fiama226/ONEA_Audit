"""OpenAPI helpers: the shared error envelope documented as component ``ApiError``."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import serializers


class ApiErrorSerializer(serializers.Serializer[dict[str, object]]):
    """Error body returned by the API exception handler (see apps.core.handlers)."""

    detail = serializers.CharField()
    errors = serializers.DictField(child=serializers.ListField(child=serializers.CharField()))  # type: ignore[assignment]


# Default error responses for authenticated endpoints.
ERROR_RESPONSES = {
    401: ApiErrorSerializer,
    403: ApiErrorSerializer,
}


class SessionAuthentication401Scheme(OpenApiAuthenticationExtension):  # type: ignore[no-untyped-call]
    """Document the project session (cookie) authentication in the schema."""

    target_class = "apps.users.authentication.SessionAuthentication401"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema: object) -> dict[str, str]:
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
