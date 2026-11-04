"""The authentication flows run under the restricted application role (C1, final review).

In production `web`, `worker`, `worker-auth` and `beat` connect as `onea_app`, which only has
the rights `gardes_sql._installer_droits` grants. Every other test runs as the database
owner: these ones switch to a role built like `onea_app` (`SET LOCAL ROLE`, inside the test
transaction) and replay each flow that deletes transient credentials (one-time codes, queued
temporary passwords, import password files, sessions).
"""

import csv
import io
import re
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from io import StringIO
from typing import Any

import pytest
from django.contrib.sessions.models import Session
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core import gardes_sql
from apps.core.gardes_sql import installer, verifier
from apps.users import tasks
from apps.users.auth_services import emettre_otp
from apps.users.models import (
    CodeOtp,
    EnvoiMotDePasse,
    FichierMotsDePasse,
    NatureEnvoi,
    ObjetOtp,
    Role,
    User,
)

from ..factories import make_user

pytestmark = pytest.mark.django_db

# Distinct from the role of tests/core/test_gardes_sql.py (roles are cluster-wide).
ROLE = "onea_tauth_app"
MDP = "Mot-de-passe-solide-2026"
NOUVEAU = "Nouvelle-phrase-secrete-77"
TABLES_TRANSITOIRES = ("users_codeotp", "users_envoimotdepasse", "users_fichiermotsdepasse")


@pytest.fixture
def role_app(db: None) -> str:
    """A role like `onea_app` (no privileges but those the installer grants)."""
    with connection.cursor() as c:
        c.execute(f"CREATE ROLE {ROLE} NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT")
    assert installer(role=ROLE)["droits"] is True
    return ROLE


@contextmanager
def comme(role: str) -> Iterator[None]:
    with connection.cursor() as c:
        c.execute(f"SET LOCAL ROLE {role}")
    try:
        yield
    finally:
        with connection.cursor() as c:
            c.execute("RESET ROLE")


def _code_du_courriel() -> str:
    trouve = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert trouve is not None
    return trouve.group(1)


def _login(client: APIClient, identifiant: str, mot_de_passe: str) -> Any:
    return client.post(
        "/api/v1/auth/login/",
        {"identifiant": identifiant, "mot_de_passe": mot_de_passe},
        format="json",
    )


def test_role_peut_supprimer_les_donnees_transitoires(role_app: str) -> None:
    with connection.cursor() as c:
        for table in TABLES_TRANSITOIRES:
            c.execute("SELECT has_table_privilege(%s, %s, 'DELETE')", [role_app, table])
            assert c.fetchone()[0] is True, table
        c.execute("SELECT has_table_privilege(%s, 'users_user', 'DELETE')", [role_app])
        assert c.fetchone()[0] is False
    assert verifier(role=role_app, exiger_role=True) == []


def test_une_table_gelee_ne_peut_pas_etre_transitoire(monkeypatch: pytest.MonkeyPatch) -> None:
    assert set(gardes_sql.tables_transitoires()) == set(TABLES_TRANSITOIRES)
    monkeypatch.setattr(
        gardes_sql, "TABLES_TRANSITOIRES", frozenset({"users.codeotp", "missions.mission"})
    )
    with pytest.raises(ValueError, match="gelé"):
        gardes_sql.tables_transitoires()


def test_premiere_connexion_et_changement_impose(role_app: str) -> None:
    compte = make_user(Role.AUDITEUR, username="awa", password=MDP)
    User.objects.filter(pk=compte.pk).update(doit_changer_mot_de_passe=True)
    client = APIClient()
    with comme(role_app):
        assert _login(client, "awa", MDP).json()["etape"] == "CHANGER_MOT_DE_PASSE"
        r = client.post(
            "/api/v1/auth/password/change/", {"ancien": MDP, "nouveau": NOUVEAU}, format="json"
        )
        assert r.status_code == 200, r.content
        assert client.get("/api/v1/auth/session/").status_code == 200
        assert client.post("/api/v1/auth/logout/").status_code in (200, 204)


def test_connexion_avec_code_puis_desactivation(role_app: str) -> None:
    compte = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    User.objects.filter(pk=compte.pk).update(otp_connexion_actif=True)
    # An expired code to drop at the next issue, and a stale one past the purge delay.
    emettre_otp(compte, ObjetOtp.LOGIN)
    CodeOtp.objects.update(expire_le=timezone.now() - timedelta(days=2))
    client = APIClient()
    with comme(role_app):
        assert _login(client, "awa", MDP).json()["etape"] == "OTP"
        r = client.post("/api/v1/auth/login/otp/", {"code": _code_du_courriel()}, format="json")
        assert r.status_code == 200, r.content
        r = client.post("/api/v1/auth/otp/disable/", {"mot_de_passe": MDP}, format="json")
        assert r.status_code == 200, r.content
        assert client.post("/api/v1/auth/otp/enable/").status_code == 200


def test_mot_de_passe_oublie_puis_reinitialisation(role_app: str) -> None:
    make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    client = APIClient()
    with comme(role_app):
        assert (
            client.post(
                "/api/v1/auth/password/forgot/", {"identifiant": "awa"}, format="json"
            ).status_code
            == 202
        )
        r = client.post(
            "/api/v1/auth/password/reset/",
            {"identifiant": "awa", "code": _code_du_courriel(), "nouveau_mot_de_passe": NOUVEAU},
            format="json",
        )
        assert r.status_code == 204, r.content
        assert _login(APIClient(), "awa", NOUVEAU).status_code == 200


def test_actions_de_l_administrateur(role_app: str) -> None:
    admin = make_user(Role.ADMIN, username="chef")
    agent = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    User.objects.filter(pk=agent.pk).update(otp_connexion_actif=True)
    emettre_otp(agent, ObjetOtp.LOGIN)
    session = APIClient()
    assert _login(session, "awa", MDP).status_code == 200
    client = APIClient()
    client.force_authenticate(admin)
    base = f"/api/v1/user-accounts/{agent.pk}/"
    with comme(role_app):
        r = client.post(base + "disable-otp/")
        assert r.status_code == 200, r.content
        r = client.patch(base, {"email": "awa.o@onea.bf"}, format="json")
        assert r.status_code == 200, r.content
        # Queued email (the worker reads and deletes the row) and one shown password.
        r = client.post(base + "reset-password/", {"envoyer_courriel": True}, format="json")
        assert r.status_code == 200, r.content
        r = client.post(base + "reset-password/", {"envoyer_courriel": False}, format="json")
        assert r.status_code == 200, r.content
    assert not EnvoiMotDePasse.objects.exists()
    assert not Session.objects.exists()


def test_import_et_fichier_des_mots_de_passe(role_app: str) -> None:
    admin = make_user(Role.ADMIN, username="chef")
    client = APIClient()
    client.force_authenticate(admin)
    contenu = (
        b"identifiant;email;prenom;nom;matricule;direction;fonction;role\n"
        b"awa;awa@onea.bf;;;;;;AUDITEUR\nsali;;;;;;;AUDITE\n"
    )
    with comme(role_app):
        r = client.post(
            "/api/v1/user-accounts/import-csv/",
            {
                "fichier": SimpleUploadedFile("c.csv", contenu, content_type="text/csv"),
                "dry_run": "false",
                "envoyer_courriel": "true",
            },
            format="multipart",
        )
        assert r.status_code == 200, r.content
        fichier_id = r.json()["fichier_mots_de_passe_id"]
        r = client.get(f"/api/v1/user-accounts/import-passwords/{fichier_id}/")
        assert r.status_code == 200, r.content
    lignes = list(csv.DictReader(io.StringIO(r.content.decode("utf-8-sig")), delimiter=";"))
    assert [ligne["identifiant"] for ligne in lignes] == ["sali"]
    assert not FichierMotsDePasse.objects.exists()


def test_purges_quotidiennes(role_app: str) -> None:
    admin = make_user(Role.ADMIN, username="chef")
    agent = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf")
    passe = timezone.now() - timedelta(days=2)
    CodeOtp.objects.create(user=agent, objet=ObjetOtp.RESET, code_hash="x", expire_le=passe)
    FichierMotsDePasse.objects.create(
        cree_par=admin, contenu=b"x", nombre_comptes=1, expire_le=passe
    )
    EnvoiMotDePasse.objects.create(
        user=agent, nature=NatureEnvoi.REINITIALISATION, contenu=b"x", expire_le=passe
    )
    Session.objects.create(session_key="k" * 32, session_data="x", expire_date=passe)
    with comme(role_app):
        assert tasks.purger_codes() == 3
        tasks.purger_sessions()
    assert not Session.objects.exists()


def test_reprise_d_un_administrateur_par_la_commande(role_app: str) -> None:
    admin = make_user(Role.ADMIN, username="chef", email="chef@onea.bf")
    emettre_otp(admin, ObjetOtp.LOGIN)
    with comme(role_app):
        call_command("creer_administrateur", "--identifiant", "chef", stdout=StringIO())
    assert not CodeOtp.objects.filter(utilise_le__isnull=True).exists()
