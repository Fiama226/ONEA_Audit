import re
import tomllib
from pathlib import Path
from typing import Any

import yaml
from django.conf import settings
from django.contrib.staticfiles import finders
from rest_framework.test import APIClient

from apps.core.schema import OIDCBearerAuthenticationScheme
from apps.users.authentication import OIDCBearerAuthentication
from config import __version__

_ASSET_REF = re.compile(r"""<(?:script|link)\s[^>]*?\b(?:src|href)=["']([^"']+)["']""")


def _schema(api_client: APIClient) -> dict[str, Any]:
    r = api_client.get("/api/schema/")
    assert r.status_code == 200
    schema: dict[str, Any] = yaml.safe_load(r.content)
    return schema


def test_schema_lists_me_and_health_endpoints(api_client: APIClient) -> None:
    schema = _schema(api_client)
    assert "/api/v1/me/" in schema["paths"]
    assert "/api/v1/health/" in schema["paths"]
    assert schema["info"]["title"] == "API Audit Interne ONEA"
    assert schema["info"]["version"] == __version__


def test_schema_exposes_me_component_with_expected_fields(api_client: APIClient) -> None:
    schemas = _schema(api_client)["components"]["schemas"]
    assert set(schemas["Me"]["properties"]) == {
        "id",
        "username",
        "email",
        "first_name",
        "last_name",
        "role",
        "direction_code",
        "fonction",
        "tutoriel",
    }


def test_schema_exposes_api_error_component_on_me(api_client: APIClient) -> None:
    schema = _schema(api_client)
    api_error = schema["components"]["schemas"]["ApiError"]
    assert set(api_error["properties"]) == {"detail", "errors"}
    responses = schema["paths"]["/api/v1/me/"]["get"]["responses"]
    for code in ("401", "403"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ApiError"


def test_schema_has_a_single_error_component(api_client: APIClient) -> None:
    schemas = _schema(api_client)["components"]["schemas"]
    assert "ApiError" in schemas
    assert "ApiErrorResponse" not in schemas
    assert [name for name in schemas if name.startswith("ApiError")] == ["ApiError"]


def test_audit_log_endpoints_reference_api_error(api_client: APIClient) -> None:
    paths = _schema(api_client)["paths"]
    expected = "#/components/schemas/ApiError"

    def ref(path: str, code: str) -> str:
        responses = paths[path]["get"]["responses"]
        return str(responses[code]["content"]["application/json"]["schema"]["$ref"])

    for code in ("400", "401", "403"):
        assert ref("/api/v1/audit-log/", code) == expected
    for code in ("401", "403"):
        assert ref("/api/v1/audit-log/{id}/", code) == expected


def test_me_documents_auth_service_unavailable(api_client: APIClient) -> None:
    responses = _schema(api_client)["paths"]["/api/v1/me/"]["get"]["responses"]
    ref = responses["503"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/ApiError"


def test_docs_page_loads_assets_locally(api_client: APIClient) -> None:
    r = api_client.get("/api/docs/")
    assert r.status_code == 200
    html = r.content.decode()
    refs = _ASSET_REF.findall(html)
    assert refs
    assert not [ref for ref in refs if re.match(r"(?:https?:)?//", ref)]
    assert "/static/drf_spectacular_sidecar/" in html
    bundle = next(ref for ref in refs if "swagger-ui" in ref and ref.endswith(".js"))
    relative = bundle.removeprefix(settings.STATIC_URL)
    assert finders.find(relative), f"{relative} not found by staticfiles finders"


def test_schema_documents_bearer_only(api_client: APIClient) -> None:
    schemes = _schema(api_client)["components"]["securitySchemes"]
    assert "cookieAuth" not in schemes


def test_bearer_auth_extension_targets_existing_class(api_client: APIClient) -> None:
    # Same as the cookie guard: generate the schema first so the dotted target is resolved.
    schemes = _schema(api_client)["components"]["securitySchemes"]
    assert schemes["bearerAuth"]["type"] == "http"
    assert schemes["bearerAuth"]["scheme"] == "bearer"
    assert schemes["bearerAuth"]["bearerFormat"] == "JWT"
    target: object = OIDCBearerAuthenticationScheme.target_class
    assert target is OIDCBearerAuthentication
    dotted = f"{OIDCBearerAuthentication.__module__}.{OIDCBearerAuthentication.__qualname__}"
    assert dotted == "apps.users.authentication.OIDCBearerAuthentication"


def test_version_has_a_single_source() -> None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert declared == __version__
