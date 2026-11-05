import csv
import io
import logging
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users.models import FichierMotsDePasse, Role, User

from ..factories import make_user

URL = "/api/v1/user-accounts/import-csv/"
FICHIER = "/api/v1/user-accounts/import-passwords/{}/"
ENTETE = "identifiant;email;prenom;nom;matricule;direction;fonction;role\n"


def _post(client: APIClient, contenu: bytes, **data: object) -> Any:
    fichier = SimpleUploadedFile("comptes.csv", contenu, content_type="text/csv")
    return client.post(URL, {"fichier": fichier, **data}, format="multipart")


@pytest.fixture
def admin_client(api_client: APIClient, admin: User) -> APIClient:
    api_client.force_authenticate(admin)
    return api_client


def _import_reel(client: APIClient) -> str:
    r = _post(
        client,
        (ENTETE + "awa;awa@onea.bf;;;;;;AUDITEUR\nsali;;;;;;;AUDITE\n").encode(),
        dry_run="false",
        envoyer_courriel="false",
    )
    assert r.status_code == 200
    fichier_id = r.json()["fichier_mots_de_passe_id"]
    assert isinstance(fichier_id, str)
    return fichier_id


def test_import_csv_dry_run_par_defaut(admin_client: APIClient) -> None:
    r = _post(admin_client, (ENTETE + "kabore.l;k@onea.bf;;;;;;AUDITEUR\n").encode())
    assert r.status_code == 200
    assert r.json() == {
        "dry_run": True,
        "crees": ["kabore.l"],
        "ignores": [],
        "fichier_mots_de_passe_id": None,
    }
    assert not User.objects.filter(username="kabore.l").exists()
    assert not FichierMotsDePasse.objects.exists()


@pytest.mark.parametrize(
    "contenu,fragment",
    [
        (b"\xff\xfe\x00bad", "UTF-8"),
        (b"a" * (1024 * 1024 + 10), "1 Mo"),
        (b"foo;bar\n1;2\n", "identifiant"),
    ],
)
def test_import_csv_400(admin_client: APIClient, contenu: bytes, fragment: str) -> None:
    r = _post(admin_client, contenu)
    assert r.status_code == 400
    assert fragment in r.json()["errors"]["fichier"][0]


def test_import_csv_fichier_absent_400(admin_client: APIClient) -> None:
    assert admin_client.post(URL, {}, format="multipart").status_code == 400


def test_import_csv_apply_historise_l_admin(admin_client: APIClient, admin: User) -> None:
    from auditlog.models import LogEntry

    r = _post(admin_client, (ENTETE + "nouveau;n@onea.bf;;;;;;RAI\n").encode(), dry_run="false")
    assert r.status_code == 200
    assert r.json()["dry_run"] is False
    cree = User.objects.get(username="nouveau")
    assert cree.origine == "CSV"
    entree = LogEntry.objects.filter(object_pk=str(cree.pk), action=LogEntry.Action.CREATE).get()
    assert entree.actor_id == admin.pk


def test_import_csv_emails_by_default(admin_client: APIClient) -> None:
    r = _post(admin_client, (ENTETE + "awa;awa@onea.bf;;;;;;AUDITEUR\n").encode(), dry_run="false")
    assert r.status_code == 200
    assert len(mail.outbox) == 1 and r.json()["fichier_mots_de_passe_id"] is None


def test_import_csv_type_refuse(admin_client: APIClient) -> None:
    fichier = SimpleUploadedFile("comptes.pdf", b"%PDF", content_type="application/pdf")
    r = admin_client.post(URL, {"fichier": fichier}, format="multipart")
    assert r.status_code == 400
    assert r.json()["errors"]["fichier"] == ["Le fichier doit être un fichier CSV (.csv)."]


@pytest.mark.parametrize("role", ["RAI", "AUDITEUR", "AUDITE", "DG"])
def test_import_csv_admin_only(api_client: APIClient, db: None, role: str) -> None:
    api_client.force_authenticate(make_user(role))
    r = _post(api_client, (ENTETE + "x;;;;;;;AUDITE\n").encode(), dry_run="false")
    assert r.status_code == 403
    assert not User.objects.filter(username="x").exists()


# --- One-time password file ------------------------------------------------------------------


def test_password_file_downloadable_once(admin_client: APIClient) -> None:
    fichier_id = _import_reel(admin_client)
    r = admin_client.get(FICHIER.format(fichier_id))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("text/csv")
    assert r["Content-Disposition"].startswith("attachment;")
    assert "no-store" in r["Cache-Control"]
    texte = r.content.decode("utf-8-sig")
    lignes = {
        ligne["identifiant"]: ligne for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")
    }
    assert set(lignes) == {"awa", "sali"}
    for identifiant, ligne in lignes.items():
        compte = User.objects.get(username=identifiant)
        assert compte.check_password(ligne["mot_de_passe_temporaire"])
    # Second call: gone, and the stored content with it.
    assert admin_client.get(FICHIER.format(fichier_id)).status_code == 404
    assert not FichierMotsDePasse.objects.exists()


def test_password_file_accepts_any_accept_header(admin_client: APIClient) -> None:
    fichier_id = _import_reel(admin_client)
    r = admin_client.get(FICHIER.format(fichier_id), HTTP_ACCEPT="text/csv")
    assert r.status_code == 200


def test_password_file_other_admin_403(api_client: APIClient, admin_client: APIClient) -> None:
    fichier_id = _import_reel(admin_client)
    autre = APIClient()
    autre.force_authenticate(make_user(Role.ADMIN))
    assert autre.get(FICHIER.format(fichier_id)).status_code == 403
    assert FichierMotsDePasse.objects.exists()  # not consumed by the refused attempt
    assert admin_client.get(FICHIER.format(fichier_id)).status_code == 200


@pytest.mark.parametrize("role", ["RAI", "AUDITEUR", "AUDITE", "DG"])
def test_password_file_non_admin_403(admin_client: APIClient, role: str) -> None:
    fichier_id = _import_reel(admin_client)
    client = APIClient()
    client.force_authenticate(make_user(role))
    assert client.get(FICHIER.format(fichier_id)).status_code == 403
    assert FichierMotsDePasse.objects.exists()


def test_password_file_anonymous_refused(admin_client: APIClient) -> None:
    fichier_id = _import_reel(admin_client)
    assert APIClient().get(FICHIER.format(fichier_id)).status_code in (401, 403)
    assert FichierMotsDePasse.objects.exists()


def test_password_file_expired_404(admin_client: APIClient) -> None:
    fichier_id = _import_reel(admin_client)
    FichierMotsDePasse.objects.update(expire_le=timezone.now() - timedelta(seconds=1))
    assert admin_client.get(FICHIER.format(fichier_id)).status_code == 404
    assert not FichierMotsDePasse.objects.exists()


def test_password_file_unknown_404(admin_client: APIClient) -> None:
    assert admin_client.get(FICHIER.format(uuid4())).status_code == 404


def test_password_file_download_not_logged(
    admin_client: APIClient, admin: User, caplog: pytest.LogCaptureFixture
) -> None:
    fichier_id = _import_reel(admin_client)
    with caplog.at_level(logging.DEBUG):
        r = admin_client.get(FICHIER.format(fichier_id))
    texte = r.content.decode("utf-8-sig")
    mots_de_passe = [
        ligne["mot_de_passe_temporaire"]
        for ligne in csv.DictReader(io.StringIO(texte), delimiter=";")
    ]
    assert len(mots_de_passe) == 2
    for mdp in mots_de_passe:
        assert mdp not in caplog.text
    securite = [r.getMessage() for r in caplog.records if r.name == "onea.securite"]
    assert any(f"par={admin.pk}" in m and "comptes=2" in m for m in securite)
