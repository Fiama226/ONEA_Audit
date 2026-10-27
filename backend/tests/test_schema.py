import tomllib
from pathlib import Path
from typing import Any

import yaml
from rest_framework.test import APIClient

from config import __version__


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
    }


def test_schema_exposes_api_error_component_on_me(api_client: APIClient) -> None:
    schema = _schema(api_client)
    api_error = schema["components"]["schemas"]["ApiError"]
    assert set(api_error["properties"]) == {"detail", "errors"}
    responses = schema["paths"]["/api/v1/me/"]["get"]["responses"]
    for code in ("401", "403"):
        ref = responses[code]["content"]["application/json"]["schema"]["$ref"]
        assert ref == "#/components/schemas/ApiError"


def test_docs_page_does_not_use_a_cdn(api_client: APIClient) -> None:
    r = api_client.get("/api/docs/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "cdn.jsdelivr.net" not in html
    assert "swagger-ui" in html


def test_version_has_a_single_source() -> None:
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
    assert declared == __version__
