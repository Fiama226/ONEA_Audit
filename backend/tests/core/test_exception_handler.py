from rest_framework.test import APIClient


def test_regle_metier_error_becomes_422(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/_test/regle-metier/")
    assert r.status_code == 422
    assert r.json() == {
        "detail": "Montant négatif interdit.",
        "errors": {"montant": ["Doit être positif."]},
    }


def test_regle_metier_error_without_errors(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/_test/regle-metier-simple/")
    assert r.status_code == 422
    assert r.json() == {"detail": "Transition interdite.", "errors": {}}


def test_nested_validation_error_is_flattened(api_client: APIClient) -> None:
    r = api_client.post("/api/v1/_test/validation/", {"adresse": {"ville": ""}}, format="json")
    assert r.status_code == 400
    assert r.json()["detail"] == "Données invalides."
    assert r.json()["errors"] == {"adresse.ville": ["Ce champ ne peut être vide."]}


def test_list_item_errors_use_index_paths(api_client: APIClient) -> None:
    payload = {"adresse": {"ville": "Ouaga"}, "items": [{"nom": "ok"}, {"nom": ""}]}
    r = api_client.post("/api/v1/_test/validation/", payload, format="json")
    assert r.status_code == 400
    assert r.json()["errors"] == {"items.1.nom": ["Ce champ ne peut être vide."]}


def test_missing_field_error(api_client: APIClient) -> None:
    r = api_client.post("/api/v1/_test/validation/", {}, format="json")
    assert r.status_code == 400
    assert r.json()["errors"] == {"adresse": ["Ce champ est obligatoire."]}


def test_non_field_error(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/_test/validation-plate/")
    assert r.status_code == 400
    assert r.json() == {
        "detail": "Données invalides.",
        "errors": {"non_field_errors": ["Incohérent."]},
    }


def test_other_api_errors_keep_detail_and_get_errors_key(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert set(r.json()) == {"detail", "errors"}
    assert r.json()["errors"] == {}
