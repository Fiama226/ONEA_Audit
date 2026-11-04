from rest_framework.test import APIClient

from apps.users.models import User


def test_me_returns_profile(auth_client: APIClient, user: User) -> None:
    r = auth_client.get("/api/v1/me/")
    assert r.status_code == 200
    assert r.json() == {
        "id": user.pk,
        "username": user.username,
        "email": user.email,
        "first_name": "Awa",
        "last_name": "Ouedraogo",
        "role": "AUDITEUR",
        "direction_code": "DAI",
        "fonction": "Auditeur interne",
        "tutoriel": {"version_vue": None, "termine_le": None},
        "otp_connexion_actif": False,
        "gestion_comptes": {
            "creer": False,
            "reinitialiser": False,
            "roles": False,
            "desactiver": False,
        },
    }


def test_me_anonymous_401(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/me/")
    assert r.status_code == 401
    assert "WWW-Authenticate" in r.headers


def test_me_is_read_only(auth_client: APIClient) -> None:
    assert auth_client.post("/api/v1/me/", {"role": "ADMIN"}, format="json").status_code == 405


def test_schema_exposes_me_component(api_client: APIClient) -> None:
    schema = api_client.get("/api/schema/?format=json").json()
    assert "Me" in schema["components"]["schemas"]


def test_tutoriel_terminer_enregistre_version(auth_client: APIClient, user: User) -> None:
    r = auth_client.post(
        "/api/v1/me/tutoriel/", {"action": "terminer", "version": 2}, format="json"
    )
    assert r.status_code == 200
    corps = r.json()
    assert corps["version_vue"] == 2
    assert corps["termine_le"] is not None
    user.refresh_from_db()
    assert user.tutoriel_version_vue == 2
    assert auth_client.get("/api/v1/me/").json()["tutoriel"] == corps


def test_tutoriel_ignorer_pose_aussi_la_version(auth_client: APIClient, user: User) -> None:
    r = auth_client.post("/api/v1/me/tutoriel/", {"action": "ignorer", "version": 1}, format="json")
    assert r.status_code == 200
    assert r.json()["version_vue"] == 1
    assert r.json()["termine_le"] is not None


def test_tutoriel_reinitialiser_remet_a_zero(auth_client: APIClient, user: User) -> None:
    auth_client.post("/api/v1/me/tutoriel/", {"action": "terminer", "version": 3}, format="json")
    r = auth_client.post(
        "/api/v1/me/tutoriel/", {"action": "reinitialiser", "version": 3}, format="json"
    )
    assert r.status_code == 200
    assert r.json() == {"version_vue": None, "termine_le": None}
    user.refresh_from_db()
    assert user.tutoriel_version_vue is None
    assert user.tutoriel_termine_le is None


def test_tutoriel_est_propre_a_chaque_utilisateur(
    auth_client: APIClient, user: User, rai: User
) -> None:
    auth_client.post("/api/v1/me/tutoriel/", {"action": "terminer", "version": 1}, format="json")
    rai.refresh_from_db()
    assert rai.tutoriel_version_vue is None


def test_tutoriel_action_inconnue_400_en_francais(auth_client: APIClient) -> None:
    r = auth_client.post("/api/v1/me/tutoriel/", {"action": "x", "version": 1}, format="json")
    assert r.status_code == 400
    assert "action" in r.json()["errors"]
    assert "n'est pas un choix valide" in r.json()["errors"]["action"][0]


def test_tutoriel_version_invalide_400(auth_client: APIClient) -> None:
    for version in (0, -1, "a", None):
        r = auth_client.post(
            "/api/v1/me/tutoriel/", {"action": "terminer", "version": version}, format="json"
        )
        assert r.status_code == 400, version
        assert "version" in r.json()["errors"]


def test_tutoriel_anonyme_401(api_client: APIClient) -> None:
    r = api_client.post("/api/v1/me/tutoriel/", {"action": "terminer", "version": 1}, format="json")
    assert r.status_code == 401
