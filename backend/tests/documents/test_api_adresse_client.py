# ruff: noqa: F401, F811
"""Bout en bout : l'adresse du journal des consultations vient du pair de confiance."""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.documents.models import ConsultationDocument, DocumentVersion
from apps.users.models import User

from .api_fixtures import utilisateurs, version_prete_mission

pytestmark = pytest.mark.django_db

PROXY = "172.18.0.5"


def _telecharger(api_client: APIClient, version: DocumentVersion, rai: User, **extra: str) -> str:
    api_client.force_authenticate(rai)
    r = api_client.get(f"/api/v1/document-versions/{version.pk}/download/?format=docx", **extra)
    assert r.status_code == 200
    return str(ConsultationDocument.objects.latest("le").adresse_ip)


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_consultation_pair_non_fiable_en_tetes_forges_ignores(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    ip = _telecharger(
        api_client,
        version_prete_mission,
        rai,
        REMOTE_ADDR="198.51.100.9",
        HTTP_X_FORWARDED_FOR="6.6.6.6",
        HTTP_X_REAL_IP="6.6.6.7",
    )
    assert ip == "198.51.100.9"


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_consultation_proxy_de_confiance_retient_x_real_ip(
    api_client: APIClient, version_prete_mission: DocumentVersion, rai: User
) -> None:
    ip = _telecharger(
        api_client,
        version_prete_mission,
        rai,
        REMOTE_ADDR=PROXY,
        HTTP_X_FORWARDED_FOR="6.6.6.6",
        HTTP_X_REAL_IP="203.0.113.7",
    )
    assert ip == "203.0.113.7"
