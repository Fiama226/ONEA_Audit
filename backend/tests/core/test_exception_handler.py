from rest_framework.test import APIClient

from apps.users.models import User
from tests.testapp.models import Exemple


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


def test_missing_object_404_uses_single_format(api_client: APIClient, db: None) -> None:
    r = api_client.get("/api/v1/_test/exemples/3f2b8c1e-0000-4000-8000-000000000000/")
    assert r.status_code == 404
    assert r.json() == {"detail": "Non trouvé.", "errors": {}}


def test_soft_deleted_object_404(api_client: APIClient, user: User) -> None:
    e = Exemple.objects.create(nom="x")
    e.soft_delete(by=user)
    r = api_client.get(f"/api/v1/_test/exemples/{e.pk}/")
    assert r.status_code == 404
    assert r.json() == {"detail": "Non trouvé.", "errors": {}}


def test_django_permission_denied_403_single_format(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/_test/interdit/")
    assert r.status_code == 403
    assert r.json() == {"detail": "Accès refusé.", "errors": {}}


def test_custom_permission_denied_message_passes_through(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/_test/interdit-custom/")
    assert r.status_code == 403
    assert r.json() == {"detail": "Seul le chef de mission peut valider.", "errors": {}}


def test_permission_class_message_passes_through(auth_client: APIClient) -> None:
    r = auth_client.get("/api/v1/_test/reserve-rai/")
    assert r.status_code == 403
    assert r.json() == {"detail": "Réservé au RAI.", "errors": {}}


def test_custom_404_message_passes_through(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/_test/introuvable-custom/")
    assert r.status_code == 404
    assert r.json() == {"detail": "Mission introuvable.", "errors": {}}


def test_drf_permission_denied_403_french(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/_test/interdit-drf/")
    assert r.status_code == 403
    assert r.json() == {"detail": "Accès refusé.", "errors": {}}
