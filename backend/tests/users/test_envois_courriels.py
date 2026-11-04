"""AUTH-01: every authentication email leaves from the worker, never from `web`.

In production `web` has no route to the SMTP relay (only `worker` is on `mail-out` and holds
the `email_password` secret). The web process therefore only queues a task, whose payload
never carries a secret: the login code is issued by the worker itself; a temporary password
is stored encrypted (Fernet, key derived from SECRET_KEY) in a short-lived row that the task
reads once and deletes. Here the queueing is observed with `delay` mocked (no eager run), so
that nothing is sent from the "web" side; the task is then run as the worker would.
"""

import re
from collections.abc import Iterator
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.core import mail
from django.core.mail.backends.base import BaseEmailBackend
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.users import envois, tasks
from apps.users.models import CodeOtp, EnvoiMotDePasse, NatureEnvoi, ObjetOtp, Role, User
from apps.users.provisioning import importer_csv, lire_fichier_mots_de_passe

from ..factories import make_user

pytestmark = pytest.mark.django_db

BASE = "/api/v1/user-accounts/"
LOGIN = "/api/v1/auth/login/"
LOGIN_OTP = "/api/v1/auth/login/otp/"
MDP = "Mot-de-passe-solide-2026"
SANS_SMTP = {"EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": ""}


class EnvoiInterditDepuisWeb(BaseEmailBackend):
    """Email backend of the "web" process in these tests: any send is a test failure."""

    def send_messages(self, email_messages: Any) -> int:
        raise AssertionError("an email was sent from the web process")


# Sending is configured (EMAIL_HOST set), as in production, but web cannot send.
WEB = {
    "EMAIL_BACKEND": "tests.users.test_envois_courriels.EnvoiInterditDepuisWeb",
    "EMAIL_HOST": "smtp.onea.bf",
}
WORKER = {"EMAIL_BACKEND": "django.core.mail.backends.locmem.EmailBackend"}


@pytest.fixture
def web_sans_smtp() -> Iterator[None]:
    with override_settings(**WEB):
        yield


def _comme_le_worker() -> Any:
    return override_settings(**WORKER)


@pytest.fixture
def file_mot_de_passe() -> Iterator[mock.MagicMock]:
    with mock.patch.object(tasks.envoyer_mot_de_passe_temporaire, "delay") as delay:
        yield delay


@pytest.fixture
def file_code_connexion() -> Iterator[mock.MagicMock]:
    with mock.patch.object(tasks.envoyer_code_connexion, "delay") as delay:
        yield delay


@pytest.fixture
def admin_client(admin: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(admin)
    return client


def _mot_de_passe_du_courriel() -> str:
    trouve = re.search(r"Mot de passe temporaire\s*:\s*(\S+)", str(mail.outbox[-1].body))
    assert trouve is not None, mail.outbox[-1].body
    return trouve.group(1)


def _sans_secret(appel: Any, *secrets: str) -> None:
    """The broker payload: ids only, no secret in any argument."""
    texte = repr(appel.args) + repr(appel.kwargs)
    for secret in secrets:
        assert secret not in texte


# --- login code ----------------------------------------------------------------------------


@pytest.mark.usefixtures("web_sans_smtp")
def test_login_code_issued_and_sent_by_the_worker(file_code_connexion: mock.MagicMock) -> None:
    agent = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    agent.otp_connexion_actif = True
    agent.save()
    client = APIClient()
    r = client.post(LOGIN, {"identifiant": "awa", "mot_de_passe": MDP}, format="json")
    assert r.status_code == 200 and r.json() == {"etape": "OTP", "me": None}
    # web only queued the account id: no code exists yet, nothing was sent.
    file_code_connexion.assert_called_once_with(agent.pk)
    assert not CodeOtp.objects.exists()
    assert mail.outbox == []

    with _comme_le_worker():
        assert tasks.envoyer_code_connexion(agent.pk) is True
    code = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert code is not None
    ok = client.post(LOGIN_OTP, {"code": code.group(1)}, format="json")
    assert ok.status_code == 200 and ok.json()["etape"] == "OK"


def test_login_code_task_refuses_accounts_that_no_longer_qualify() -> None:
    sans_otp = make_user(Role.AUDITEUR, email="a@onea.bf")
    inactif = make_user(Role.AUDITEUR, email="b@onea.bf", otp_connexion_actif=True)
    inactif.is_active = False
    inactif.save()
    verrouille = make_user(Role.AUDITEUR, email="c@onea.bf", otp_connexion_actif=True)
    verrouille.verrouille_jusqu_a = timezone.now() + timedelta(minutes=5)
    verrouille.save()
    for compte in (sans_otp, inactif, verrouille):
        assert tasks.envoyer_code_connexion(compte.pk) is False
    assert tasks.envoyer_code_connexion(999_999) is False
    assert mail.outbox == [] and not CodeOtp.objects.exists()


@pytest.mark.usefixtures("web_sans_smtp")
def test_login_answer_unchanged_when_the_broker_is_down(
    file_code_connexion: mock.MagicMock,
) -> None:
    file_code_connexion.side_effect = OSError("broker down")
    agent = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    agent.otp_connexion_actif = True
    agent.save()
    r = APIClient().post(LOGIN, {"identifiant": "awa", "mot_de_passe": MDP}, format="json")
    assert r.status_code == 200 and r.json() == {"etape": "OTP", "me": None}


# --- temporary passwords (creation, reset by an administrator) ------------------------------


@pytest.mark.usefixtures("web_sans_smtp")
def test_creation_queues_the_welcome_without_the_password(
    admin_client: APIClient, file_mot_de_passe: mock.MagicMock
) -> None:
    r = admin_client.post(
        BASE,
        {"username": "fatim", "email": "fatim@onea.bf", "role": "AUDITEUR"},
        format="json",
    )
    assert r.status_code == 201
    assert r.json()["courriel_envoye"] is True and r.json()["mot_de_passe_temporaire"] is None
    assert mail.outbox == []
    file_mot_de_passe.assert_called_once()
    (envoi_id,) = file_mot_de_passe.call_args.args
    envoi = EnvoiMotDePasse.objects.get(pk=envoi_id)
    compte = User.objects.get(username="fatim")
    assert envoi.user_id == compte.pk and envoi.nature == NatureEnvoi.BIENVENUE
    assert timezone.now() < envoi.expire_le <= timezone.now() + envois.DUREE_ENVOI_EN_ATTENTE

    # The worker reads the row once, deletes it and sends the welcome email.
    with _comme_le_worker():
        assert tasks.envoyer_mot_de_passe_temporaire(envoi_id) is True
    mdp = _mot_de_passe_du_courriel()
    assert mail.outbox[-1].to == ["fatim@onea.bf"]
    assert compte.check_password(mdp)
    assert mdp.encode() not in bytes(envoi.contenu)  # stored encrypted
    _sans_secret(file_mot_de_passe.call_args, mdp)
    assert not EnvoiMotDePasse.objects.exists()
    with _comme_le_worker():
        assert tasks.envoyer_mot_de_passe_temporaire(envoi_id) is False  # read once
    assert len(mail.outbox) == 1


@pytest.mark.usefixtures("web_sans_smtp")
def test_reset_by_admin_queues_the_new_password(
    admin_client: APIClient, file_mot_de_passe: mock.MagicMock
) -> None:
    agent = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    r = admin_client.post(f"{BASE}{agent.pk}/reset-password/", {}, format="json")
    assert r.status_code == 200
    assert r.json()["courriel_envoye"] is True and r.json()["mot_de_passe_temporaire"] is None
    (envoi_id,) = file_mot_de_passe.call_args.args
    assert EnvoiMotDePasse.objects.get(pk=envoi_id).nature == NatureEnvoi.REINITIALISATION
    assert mail.outbox == []
    with _comme_le_worker():
        assert tasks.envoyer_mot_de_passe_temporaire(envoi_id) is True
    assert "réinitialisé" in str(mail.outbox[-1].subject)
    agent.refresh_from_db()
    assert agent.check_password(_mot_de_passe_du_courriel())


@pytest.mark.usefixtures("web_sans_smtp")
def test_broker_down_shows_the_password_once_and_keeps_no_row(
    admin_client: APIClient, file_mot_de_passe: mock.MagicMock
) -> None:
    file_mot_de_passe.side_effect = OSError("broker down")
    r = admin_client.post(
        BASE, {"username": "fatim", "email": "fatim@onea.bf", "role": "AUDITE"}, format="json"
    )
    assert r.status_code == 201
    assert r.json()["courriel_envoye"] is False
    mdp = r.json()["mot_de_passe_temporaire"]
    assert User.objects.get(username="fatim").check_password(mdp)
    assert not EnvoiMotDePasse.objects.exists()


@pytest.mark.usefixtures("web_sans_smtp")
@override_settings(**SANS_SMTP)
def test_sending_not_configured_shows_the_password_and_queues_nothing(
    admin_client: APIClient, file_mot_de_passe: mock.MagicMock
) -> None:
    r = admin_client.post(
        BASE, {"username": "fatim", "email": "fatim@onea.bf", "role": "AUDITE"}, format="json"
    )
    assert r.json()["courriel_envoye"] is False and r.json()["mot_de_passe_temporaire"]
    file_mot_de_passe.assert_not_called()
    assert not EnvoiMotDePasse.objects.exists()


def test_worker_never_sends_a_password_that_is_no_longer_current(
    admin: User, file_mot_de_passe: mock.MagicMock
) -> None:
    agent = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    from apps.users import services

    services.reinitialiser_mot_de_passe(agent, par=admin)
    (envoi_id,) = file_mot_de_passe.call_args.args
    agent.set_password("Un-autre-mot-de-passe-2026")
    agent.save()
    assert tasks.envoyer_mot_de_passe_temporaire(envoi_id) is False
    assert mail.outbox == [] and not EnvoiMotDePasse.objects.exists()


def test_worker_drops_an_expired_row(admin: User, file_mot_de_passe: mock.MagicMock) -> None:
    agent = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    from apps.users import services

    services.reinitialiser_mot_de_passe(agent, par=admin)
    (envoi_id,) = file_mot_de_passe.call_args.args
    EnvoiMotDePasse.objects.update(expire_le=timezone.now() - timedelta(seconds=1))
    assert tasks.envoyer_mot_de_passe_temporaire(envoi_id) is False
    assert mail.outbox == [] and not EnvoiMotDePasse.objects.exists()


def test_worker_send_failure_is_logged_and_the_row_is_gone(
    admin: User, file_mot_de_passe: mock.MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    agent = make_user(Role.AUDITEUR, email="awa@onea.bf", password=MDP)
    from apps.users import services

    mdp, envoye = services.reinitialiser_mot_de_passe(agent, par=admin)
    assert (mdp, envoye) == ("", True)
    (envoi_id,) = file_mot_de_passe.call_args.args
    with mock.patch("apps.users.courriels.send_mail", side_effect=OSError("smtp down")):
        assert tasks.envoyer_mot_de_passe_temporaire(envoi_id) is False
    assert not EnvoiMotDePasse.objects.exists()
    assert any(
        r.name == "onea.securite" and r.levelname == "ERROR" and f"compte={agent.pk}" in r.message
        for r in caplog.records
    )


def test_daily_purge_removes_expired_rows(admin: User, file_mot_de_passe: mock.MagicMock) -> None:
    from apps.users import services

    for _ in range(2):
        services.reinitialiser_mot_de_passe(make_user(email="x@onea.bf"), par=admin)
    perime, valide = EnvoiMotDePasse.objects.order_by("cree_le")
    EnvoiMotDePasse.objects.filter(pk=perime.pk).update(
        expire_le=timezone.now() - timedelta(minutes=1)
    )
    assert tasks.purger_codes() >= 1
    assert list(EnvoiMotDePasse.objects.values_list("pk", flat=True)) == [valide.pk]


# --- CSV import ------------------------------------------------------------------------------


@pytest.mark.usefixtures("web_sans_smtp")
def test_import_queues_one_task_per_address_and_files_the_rest(
    admin: User, file_mot_de_passe: mock.MagicMock
) -> None:
    rapport = importer_csv(
        b"identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\nsali;;AUDITE\n",
        by=admin,
        dry_run=False,
        envoyer_courriel=True,
    )
    assert file_mot_de_passe.call_count == 1
    (envoi_id,) = file_mot_de_passe.call_args.args
    assert EnvoiMotDePasse.objects.get(pk=envoi_id).user.username == "awa"
    assert rapport.fichier_mots_de_passe_id is not None
    texte = lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=admin)
    assert "sali" in texte and "awa" not in texte
    assert mail.outbox == []
    with _comme_le_worker():
        assert tasks.envoyer_mot_de_passe_temporaire(envoi_id) is True
    assert User.objects.get(username="awa").check_password(_mot_de_passe_du_courriel())


@pytest.mark.usefixtures("web_sans_smtp")
def test_import_stops_queueing_when_the_broker_is_down(
    admin: User, file_mot_de_passe: mock.MagicMock
) -> None:
    file_mot_de_passe.side_effect = OSError("broker down")
    rapport = importer_csv(
        b"identifiant;email;role\nawa;awa@onea.bf;AUDITEUR\nali;ali@onea.bf;AUDITE\n",
        by=admin,
        dry_run=False,
        envoyer_courriel=True,
    )
    assert file_mot_de_passe.call_count == 1  # no new attempt per remaining account
    assert rapport.fichier_mots_de_passe_id is not None
    texte = lire_fichier_mots_de_passe(rapport.fichier_mots_de_passe_id, par=admin)
    assert "awa" in texte and "ali" in texte
    assert not EnvoiMotDePasse.objects.exists()


def test_reset_code_still_issued_by_the_worker_only() -> None:
    """Unchanged since before AUTH-01: the forgotten-password code never left the worker."""
    agent = make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)
    with mock.patch.object(tasks.envoyer_code_reinitialisation, "delay") as delay:
        r = APIClient().post("/api/v1/auth/password/forgot/", {"identifiant": "awa"}, format="json")
    assert r.status_code == 202
    delay.assert_called_once_with(agent.pk)
    assert not CodeOtp.objects.filter(objet=ObjetOtp.RESET).exists()
