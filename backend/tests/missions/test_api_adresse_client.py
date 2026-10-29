"""Bout en bout : l'adresse enregistrée dans la confirmation vient du pair, pas de l'en-tête."""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.missions.models import DeclarationIndependance, Mission
from apps.signatures.models import Confirmation
from apps.users.models import User

Equipe = tuple[Mission, dict[str, User]]

PROXY = "172.18.0.5"


def _confirmer(api_client: APIClient, equipe: Equipe, **extra: str) -> Confirmation:
    m, users = equipe
    declaration = DeclarationIndependance.objects.get(
        affectation__mission=m, affectation__utilisateur=users["auditeur_non_confirme"]
    )
    api_client.force_authenticate(users["auditeur_non_confirme"])
    r = api_client.post(
        f"/api/v1/independence-declarations/{declaration.id}/confirm/",
        {"confirme": True},
        format="json",
        **extra,
    )
    assert r.status_code == 200, r.json()
    return Confirmation.objects.get(object_id=declaration.id)


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_confirmation_pair_non_fiable_en_tetes_forges_ignores(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    c = _confirmer(
        api_client,
        equipe_complete,
        REMOTE_ADDR="198.51.100.9",
        HTTP_X_FORWARDED_FOR="6.6.6.6",
        HTTP_X_REAL_IP="6.6.6.7",
    )
    assert c.adresse_ip == "198.51.100.9"


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_confirmation_proxy_de_confiance_retient_x_real_ip(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    c = _confirmer(
        api_client,
        equipe_complete,
        REMOTE_ADDR=PROXY,
        HTTP_X_FORWARDED_FOR="6.6.6.6",
        HTTP_X_REAL_IP="203.0.113.7",
    )
    assert c.adresse_ip == "203.0.113.7"


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [("fe80::1%eth0", PROXY), ("::ffff:203.0.113.7", "203.0.113.7")],
)
@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_confirmation_x_real_ip_ipv6_normalise(
    api_client: APIClient, equipe_complete: Equipe, brut: str, attendu: str
) -> None:
    c = _confirmer(api_client, equipe_complete, REMOTE_ADDR=PROXY, HTTP_X_REAL_IP=brut)
    assert c.adresse_ip == attendu
