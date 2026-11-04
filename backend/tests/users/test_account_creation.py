"""Account creation, password reset and login-code removal by the administrator."""

import json
import logging
import re
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from auditlog.models import LogEntry
from django.conf import settings
from django.contrib.sessions.models import Session
from django.core import mail
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction, TypeEntite
from apps.users import services
from apps.users.models import CodeOtp, ObjetOtp, OrigineCompte, Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/user-accounts/"
LOGIN = "/api/v1/auth/login/"
SESSION = "/api/v1/auth/session/"
MDP = "Mot-de-passe-solide-2026"
SANS_SMTP = {"EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": ""}
NOUVEL_AGENT: dict[str, Any] = {
    "username": "fatim.sawadogo",
    "email": "fatim.sawadogo@onea.bf",
    "first_name": "Fatimata",
    "last_name": "Sawadogo",
    "role": "AUDITEUR",
    "fonction": "Auditrice interne",
}


@pytest.fixture
def admin_client(api_client: APIClient, admin: User) -> APIClient:
    api_client.force_authenticate(admin)
    return api_client


@pytest.fixture
def agent() -> User:
    return make_user(Role.AUDITEUR, username="awa.ouedraogo", email="awa@onea.bf", password=MDP)


def _creer(client: APIClient, **extra: Any) -> Any:
    return client.post(BASE, {**NOUVEL_AGENT, **extra}, format="json")


def _login(identifiant: str, mot_de_passe: str) -> tuple[APIClient, Any]:
    client = APIClient()
    r = client.post(
        LOGIN, {"identifiant": identifiant, "mot_de_passe": mot_de_passe}, format="json"
    )
    return client, r


def _mot_de_passe_du_courriel() -> str:
    assert len(mail.outbox) == 1
    trouve = re.search(r"Mot de passe temporaire : (\S+)", str(mail.outbox[0].body))
    assert trouve is not None
    return trouve.group(1)


def _entrees(compte: User) -> list[LogEntry]:
    return list(LogEntry.objects.get_for_object(compte).order_by("pk"))


def _actions(compte: User) -> list[str]:
    return [(e.additional_data or {}).get("action", "") for e in _entrees(compte)]


# --- Creation ------------------------------------------------------------------------------


@pytest.mark.parametrize("role", [None, "", "SUPERADMIN"])
def test_create_requires_role(admin_client: APIClient, role: str | None) -> None:
    corps = {k: v for k, v in NOUVEL_AGENT.items() if k != "role"}
    if role is not None:
        corps["role"] = role
    r = admin_client.post(BASE, corps, format="json")
    assert r.status_code == 400
    assert "role" in r.json()["errors"]
    assert not User.objects.filter(username="fatim.sawadogo").exists()


def test_create_service_requires_role(admin: User) -> None:
    donnees = {k: v for k, v in NOUVEL_AGENT.items() if k != "role"}
    with pytest.raises(RegleMetierError) as exc:
        services.creer_compte(donnees=donnees, par=admin, envoyer_courriel=False)
    assert "role" in exc.value.errors
    assert not User.objects.filter(username="fatim.sawadogo").exists()


def test_create_sends_welcome_and_hides_password(admin_client: APIClient) -> None:
    avant = timezone.now()
    r = _creer(admin_client)
    assert r.status_code == 201
    corps = r.json()
    assert corps["courriel_envoye"] is True
    assert corps["mot_de_passe_temporaire"] is None
    assert corps["compte"]["username"] == "fatim.sawadogo"
    assert corps["compte"]["role"] == "AUDITEUR"
    assert r["Cache-Control"] == "no-store"
    mdp = _mot_de_passe_du_courriel()
    assert mail.outbox[0].to == ["fatim.sawadogo@onea.bf"]
    assert mdp not in r.content.decode()
    compte = User.objects.get(username="fatim.sawadogo")
    assert compte.check_password(mdp)
    assert compte.doit_changer_mot_de_passe is True
    assert compte.mot_de_passe_expire_le is not None
    assert (
        avant + timedelta(hours=72)
        <= compte.mot_de_passe_expire_le
        <= timezone.now() + timedelta(hours=72)
    )
    assert compte.role == Role.AUDITEUR
    assert compte.origine == OrigineCompte.ADMINISTRATION
    assert compte.is_active and compte.otp_connexion_actif is False
    assert "password" not in json.dumps(corps)
    assert compte.password not in r.content.decode()
    # The welcome password opens a session that must change it first.
    _, login = _login("fatim.sawadogo@onea.bf", mdp)
    assert login.status_code == 200 and login.json()["etape"] == "CHANGER_MOT_DE_PASSE"


def test_create_without_email_returns_password_once(admin_client: APIClient) -> None:
    r = _creer(admin_client, envoyer_courriel=False)
    assert r.status_code == 201
    corps = r.json()
    assert corps["courriel_envoye"] is False
    mdp = corps["mot_de_passe_temporaire"]
    assert isinstance(mdp, str) and len(mdp) >= 16
    assert r["Cache-Control"] == "no-store"
    assert mail.outbox == []
    compte = User.objects.get(username="fatim.sawadogo")
    assert compte.check_password(mdp)
    assert compte.doit_changer_mot_de_passe is True


@override_settings(**SANS_SMTP)
def test_create_without_smtp_returns_password(admin_client: APIClient) -> None:
    r = _creer(admin_client)
    assert r.status_code == 201
    assert r.json()["courriel_envoye"] is False
    assert r.json()["mot_de_passe_temporaire"]
    assert mail.outbox == []


def test_create_without_address_returns_password(admin_client: APIClient) -> None:
    r = _creer(admin_client, email="")
    assert r.status_code == 201
    assert r.json()["courriel_envoye"] is False and r.json()["mot_de_passe_temporaire"]


def test_create_send_failure_returns_password(admin: User) -> None:
    with mock.patch("apps.users.courriels.send_mail", side_effect=OSError("smtp down")):
        compte, mdp = services.creer_compte(
            donnees=dict(NOUVEL_AGENT), par=admin, envoyer_courriel=True
        )
    assert mdp is not None and compte.check_password(mdp)


def test_create_service_hides_password_when_sent(admin: User) -> None:
    compte, mdp = services.creer_compte(
        donnees=dict(NOUVEL_AGENT), par=admin, envoyer_courriel=True
    )
    assert mdp is None
    assert compte.check_password(_mot_de_passe_du_courriel())


def test_second_read_never_returns_password(admin_client: APIClient) -> None:
    r = _creer(admin_client, envoyer_courriel=False)
    mdp = r.json()["mot_de_passe_temporaire"]
    compte = User.objects.get(username="fatim.sawadogo")
    for url in (f"{BASE}{compte.id}/", BASE, f"{BASE}?search=fatim"):
        lecture = admin_client.get(url)
        assert lecture.status_code == 200
        contenu = lecture.content.decode()
        assert mdp not in contenu
        assert compte.password not in contenu
        assert "mot_de_passe_temporaire" not in contenu
        assert '"password"' not in contenu
    detail = admin_client.get(f"{BASE}{compte.id}/").json()
    assert detail["doit_changer_mot_de_passe"] is True
    # No column keeps the temporary password in clear.
    for champ in User._meta.concrete_fields:
        assert mdp not in str(getattr(compte, champ.attname)), champ.name


def test_create_refuses_taken_username_and_email(admin_client: APIClient, agent: User) -> None:
    r = _creer(admin_client, username="AWA.ouedraogo")
    assert r.status_code == 422 and "username" in r.json()["errors"]
    r = _creer(admin_client, email="AWA@onea.bf")
    assert r.status_code == 422 and "email" in r.json()["errors"]
    assert mail.outbox == []
    assert not User.objects.filter(username="fatim.sawadogo").exists()


def test_create_validates_direction(admin_client: APIClient) -> None:
    r = _creer(admin_client, direction_code="INCONNUE")
    assert r.status_code == 422 and "direction_code" in r.json()["errors"]
    Direction.objects.create(
        code="DCREA", libelle="Direction de la création", type=TypeEntite.DIRECTION
    )
    r = _creer(admin_client, direction_code="DCREA")
    assert r.status_code == 201
    assert r.json()["compte"]["direction_libelle"] == "Direction de la création"


def test_create_ignores_password_sent_by_client(admin_client: APIClient) -> None:
    choisi = "Choisi-par-l-admin-2026"
    r = _creer(admin_client, password=choisi, envoyer_courriel=False)
    assert r.status_code == 201
    compte = User.objects.get(username="fatim.sawadogo")
    assert not compte.check_password(choisi)
    assert compte.check_password(r.json()["mot_de_passe_temporaire"])


# --- Reset by the administrator ------------------------------------------------------------


def test_reset_unlocks_account_and_kills_sessions(admin_client: APIClient, agent: User) -> None:
    session_agent, r = _login("awa.ouedraogo", MDP)
    assert r.status_code == 200
    assert session_agent.get(SESSION).status_code == 200
    cle_session = session_agent.cookies[settings.SESSION_COOKIE_NAME].value
    assert Session.objects.filter(session_key=cle_session).exists()
    agent.echecs_connexion = 3
    agent.verrouille_jusqu_a = timezone.now() + timedelta(minutes=10)
    agent.save(update_fields=["echecs_connexion", "verrouille_jusqu_a"])
    CodeOtp.objects.create(
        user=agent, objet=ObjetOtp.RESET, code_hash="x", expire_le=timezone.now()
    )

    r = admin_client.post(f"{BASE}{agent.id}/reset-password/", {"envoyer_courriel": False})
    assert r.status_code == 200
    assert r["Cache-Control"] == "no-store"
    corps = r.json()
    mdp = corps["mot_de_passe_temporaire"]
    assert corps["courriel_envoye"] is False and len(mdp) >= 16
    assert corps["compte"]["verrouille_jusqu_a"] is None
    agent.refresh_from_db()
    assert agent.echecs_connexion == 0 and agent.verrouille_jusqu_a is None
    assert agent.doit_changer_mot_de_passe is True
    assert agent.mot_de_passe_expire_le is not None
    assert agent.mot_de_passe_expire_le > timezone.now() + timedelta(hours=71)
    assert not CodeOtp.objects.filter(user=agent, utilise_le__isnull=True).exists()
    # The open session is gone; the old password no longer works.
    assert not Session.objects.filter(session_key=cle_session).exists()
    assert session_agent.get(SESSION).status_code == 401
    assert _login("awa.ouedraogo", MDP)[1].status_code == 401
    _, r = _login("awa.ouedraogo", mdp)
    assert r.status_code == 200 and r.json()["etape"] == "CHANGER_MOT_DE_PASSE"


def test_reset_emails_new_password_by_default(admin_client: APIClient, agent: User) -> None:
    r = admin_client.post(f"{BASE}{agent.id}/reset-password/", {}, format="json")
    assert r.status_code == 200
    assert r.json()["courriel_envoye"] is True
    assert r.json()["mot_de_passe_temporaire"] is None
    mdp = _mot_de_passe_du_courriel()
    assert mail.outbox[0].to == ["awa@onea.bf"]
    assert "réinitialisé" in str(mail.outbox[0].subject)
    assert mdp not in r.content.decode()
    agent.refresh_from_db()
    assert agent.check_password(mdp)


def test_reset_service_returns_password_only_when_not_sent(admin: User, agent: User) -> None:
    mdp, envoye = services.reinitialiser_mot_de_passe(agent, par=admin)
    assert (mdp, envoye) == ("", True)
    with override_settings(**SANS_SMTP):
        mdp, envoye = services.reinitialiser_mot_de_passe(agent, par=admin)
    assert envoye is False and len(mdp) >= 16
    agent.refresh_from_db()
    assert agent.check_password(mdp)


def test_reset_refused_on_disabled_account(admin_client: APIClient, agent: User) -> None:
    agent.is_active = False
    agent.save(update_fields=["is_active"])
    ancien_hash = agent.password
    r = admin_client.post(f"{BASE}{agent.id}/reset-password/", {"envoyer_courriel": False})
    assert r.status_code == 422
    assert "mot_de_passe_temporaire" not in r.json()
    agent.refresh_from_db()
    assert agent.password == ancien_hash and agent.is_active is False
    assert mail.outbox == []


def test_admin_cannot_reset_or_disable_otp_on_own_account(
    admin_client: APIClient, admin: User
) -> None:
    admin.otp_connexion_actif = True
    admin.save(update_fields=["otp_connexion_actif"])
    ancien_hash = admin.password
    assert admin_client.post(f"{BASE}{admin.id}/reset-password/").status_code == 422
    assert admin_client.post(f"{BASE}{admin.id}/disable-otp/").status_code == 422
    admin.refresh_from_db()
    assert admin.password == ancien_hash and admin.otp_connexion_actif is True


# --- Login code removal --------------------------------------------------------------------


def test_disable_otp_logged(
    admin_client: APIClient, admin: User, agent: User, caplog: pytest.LogCaptureFixture
) -> None:
    agent.otp_connexion_actif = True
    agent.save(update_fields=["otp_connexion_actif"])
    deja = {e.pk for e in _entrees(agent)}
    with caplog.at_level(logging.INFO, logger="onea.securite"):
        r = admin_client.post(f"{BASE}{agent.id}/disable-otp/")
    assert r.status_code == 200
    assert r.json()["otp_connexion_actif"] is False
    assert r.json()["actions"]["desactiver_otp"] is False
    agent.refresh_from_db()
    assert agent.otp_connexion_actif is False
    (entree,) = [e for e in _entrees(agent) if e.pk not in deja]
    assert entree.actor_id == admin.id
    assert entree.additional_data == {"action": "desactivation_otp"}
    assert entree.changes_dict["otp_connexion_actif"] == ["True", "False"]
    messages = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any(f"compte={agent.pk}" in m and f"par={admin.pk}" in m for m in messages)
    # Already off: refused, nothing more logged.
    assert admin_client.post(f"{BASE}{agent.id}/disable-otp/").status_code == 422
    assert len(_entrees(agent)) == len(deja) + 1


# --- Audit trail ---------------------------------------------------------------------------


def test_audit_entry_has_no_secret(
    admin_client: APIClient, admin: User, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        r = _creer(admin_client, envoyer_courriel=False)
        compte = User.objects.get(username="fatim.sawadogo")
        mdp_creation = r.json()["mot_de_passe_temporaire"]
        r = admin_client.post(f"{BASE}{compte.id}/reset-password/", {"envoyer_courriel": False})
        mdp_reset = r.json()["mot_de_passe_temporaire"]
        r = admin_client.post(f"{BASE}{compte.id}/reset-password/", {})
    mdp_courriel = _mot_de_passe_du_courriel()
    compte.refresh_from_db()
    entrees = _entrees(compte)
    assert len(entrees) == 3
    assert _actions(compte) == [
        "creation_compte",
        "reinitialisation_mot_de_passe",
        "reinitialisation_mot_de_passe",
    ]
    for entree in entrees:
        assert entree.actor_id == admin.id
        assert entree.object_id == compte.id
        assert "password" not in entree.changes_dict
        brut = json.dumps(
            [entree.changes, entree.additional_data, entree.serialized_data, entree.object_repr],
            default=str,
        )
        for secret in (mdp_creation, mdp_reset, mdp_courriel, compte.password):
            assert secret not in brut
    for secret in (mdp_creation, mdp_reset, mdp_courriel, compte.password):
        assert secret not in caplog.text
    securite = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any(f"compte={compte.pk}" in m and f"par={admin.pk}" in m for m in securite)


# --- Rights --------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["RAI", "AUDITEUR", "AUDITE", "DG"])
def test_new_routes_admin_only(api_client: APIClient, agent: User, role: str) -> None:
    agent.otp_connexion_actif = True
    agent.save(update_fields=["otp_connexion_actif"])
    ancien_hash = agent.password
    api_client.force_authenticate(make_user(role))
    assert _creer(api_client).status_code == 403
    assert api_client.post(f"{BASE}{agent.id}/reset-password/").status_code == 403
    assert api_client.post(f"{BASE}{agent.id}/disable-otp/").status_code == 403
    agent.refresh_from_db()
    assert agent.password == ancien_hash and agent.otp_connexion_actif is True
    assert not User.objects.filter(username="fatim.sawadogo").exists()
    assert mail.outbox == []
