"""Erreurs aux limites (recette QA niveau 4) : toujours le format {detail, errors}, en français."""

from rest_framework.test import APIClient


def test_json_mal_forme_donne_un_message_francais(api_client: APIClient) -> None:
    r = api_client.post("/api/v1/_test/validation/", data="{bad", content_type="application/json")
    assert r.status_code == 400
    assert "JSON parse error" not in r.json()["detail"]
    assert r.json()["errors"] == {}
    assert "requête" in r.json()["detail"].lower()


def test_json_trop_imbrique_est_refuse_sans_erreur_500(api_client: APIClient) -> None:
    corps = "[" * 5000 + "]" * 5000
    r = api_client.post("/api/v1/_test/validation/", data=corps, content_type="application/json")
    assert r.status_code == 400
    assert set(r.json()) == {"detail", "errors"}


def test_multipart_illisible_donne_un_message_francais(api_client: APIClient) -> None:
    r = api_client.post(
        "/api/v1/_test/validation/",
        data=b"--x\r\nbroken",
        content_type="multipart/form-data; boundary=x",
    )
    assert r.status_code == 400
    assert "Multipart" not in r.json()["detail"]


def test_url_api_inconnue_repond_en_json(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/n-existe-pas/")
    assert r.status_code == 404
    assert r["Content-Type"].startswith("application/json")
    assert r.json() == {"detail": "Non trouvé.", "errors": {}}


def test_url_hors_api_garde_la_page_html_standard(api_client: APIClient) -> None:
    r = api_client.get("/n-existe-pas")
    assert r.status_code == 404
    assert not r["Content-Type"].startswith("application/json")
