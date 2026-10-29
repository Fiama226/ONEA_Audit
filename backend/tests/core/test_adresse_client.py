"""Adresse IP réelle du client : l'en-tête n'est cru que d'un proxy de confiance."""

from typing import Any

import pytest
from django.http import HttpRequest
from django.test import RequestFactory, override_settings

from apps.core.middleware import AdresseClientMiddleware, LazyActorAuditlogMiddleware
from apps.core.reseau import adresse_client

PROXY = "172.18.0.5"


def _passer(rf: RequestFactory, peer: str, **headers: str) -> HttpRequest:
    captured: dict[str, Any] = {}

    def vue(request: HttpRequest) -> Any:
        captured["request"] = request
        return None

    extra = {f"HTTP_{k.upper().replace('-', '_')}": v for k, v in headers.items()}
    request = rf.get("/", REMOTE_ADDR=peer, **extra)
    AdresseClientMiddleware(vue)(request)
    return captured["request"]


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_pair_de_confiance_et_x_real_ip_valide(rf: RequestFactory) -> None:
    request = _passer(rf, PROXY, **{"X-Real-IP": "203.0.113.7"})
    assert adresse_client(request) == "203.0.113.7"
    assert request.META["ONEA_PROXY_ADDR"] == PROXY


@override_settings(TRUSTED_PROXY_CIDRS=["2001:db8::/32"])
def test_pair_ipv6_de_confiance_et_client_ipv6(rf: RequestFactory) -> None:
    request = _passer(rf, "2001:db8::1", **{"X-Real-IP": "2001:db8:abcd::9"})
    assert adresse_client(request) == "2001:db8:abcd::9"


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_entete_client_ignore_hors_proxy_de_confiance(rf: RequestFactory) -> None:
    request = _passer(rf, "198.51.100.9", **{"X-Real-IP": "203.0.113.7"})
    assert adresse_client(request) == "198.51.100.9"
    assert "ONEA_PROXY_ADDR" not in request.META


@override_settings(TRUSTED_PROXY_CIDRS=[])
def test_liste_vide_ne_fait_confiance_a_personne(rf: RequestFactory) -> None:
    request = _passer(rf, PROXY, **{"X-Real-IP": "203.0.113.7"})
    assert adresse_client(request) == PROXY


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
@pytest.mark.parametrize(
    "valeur",
    ["1.2.3.4, 5.6.7.8", "n'importe quoi", "", "1.2.3.4:80", "999.1.1.1", "<script>"],
)
def test_valeur_invalide_ignoree_sans_etre_journalisee(
    rf: RequestFactory, valeur: str, caplog: pytest.LogCaptureFixture
) -> None:
    request = _passer(rf, PROXY, **{"X-Real-IP": valeur})
    assert adresse_client(request) == PROXY
    if valeur:
        assert valeur not in caplog.text


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_x_forwarded_for_du_client_jamais_retenu(rf: RequestFactory) -> None:
    request = _passer(rf, PROXY, **{"X-Forwarded-For": "6.6.6.6", "X-Real-IP": "203.0.113.7"})
    assert adresse_client(request) == "203.0.113.7"
    seul = _passer(rf, PROXY, **{"X-Forwarded-For": "6.6.6.6"})
    assert adresse_client(seul) == PROXY


@override_settings(TRUSTED_PROXY_CIDRS=["172.18.0.0/16"])
def test_piste_d_audit_ignore_x_forwarded_for(rf: RequestFactory) -> None:
    request = _passer(rf, PROXY, **{"X-Forwarded-For": "6.6.6.6", "X-Real-IP": "203.0.113.7"})
    data = LazyActorAuditlogMiddleware(lambda r: None).get_extra_data(request)  # type: ignore[arg-type,return-value]
    assert data["remote_addr"] == "203.0.113.7"


@override_settings(TRUSTED_PROXY_CIDRS=["not-a-cidr", "172.18.0.0/16"])
def test_cidr_mal_forme_ignore(rf: RequestFactory) -> None:
    request = _passer(rf, PROXY, **{"X-Real-IP": "203.0.113.7"})
    assert adresse_client(request) == "203.0.113.7"
