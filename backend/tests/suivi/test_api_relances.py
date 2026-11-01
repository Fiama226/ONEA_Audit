"""Journal des relances : réservé au RAI, filtres, forme."""

import datetime
from typing import Any

import pytest

from apps.suivi.models import PalierRelance, Relance, StatutRelance
from apps.users.models import Role
from tests.accomplissement.fixtures_api import client_de
from tests.factories import make_user
from tests.suivi.conftest import mission_en_suivi  # noqa: F401
from tests.suivi.factories import RelanceFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/reminders/"


def test_reminders_reserve_au_rai(mission_en_suivi: Any) -> None:  # noqa: F811
    for role in (Role.AUDITEUR, Role.AUDITE, Role.DG, Role.ADMIN):
        reponse = client_de(make_user(role)).get(URL)
        assert reponse.status_code == 403, role
        assert set(reponse.json()) == {"detail", "errors"}
    assert client_de(make_user(Role.RAI)).get(URL).status_code == 200


def test_reminders_anonyme_401(api_client: Any) -> None:
    assert api_client.get(URL).status_code == 401


def test_reminders_forme_et_filtres(mission_en_suivi: Any) -> None:  # noqa: F811
    suivis = list(mission_en_suivi.suivis_actions.order_by("action__numero")[:2])
    a = RelanceFactory(suivi=suivis[0], palier=PalierRelance.J_MOINS_15)
    b = RelanceFactory(suivi=suivis[1], palier=PalierRelance.J)
    Relance.all_objects.filter(pk=b.pk).update(statut=StatutRelance.ECHEC, erreur="SMTPException")
    client = client_de(make_user(Role.RAI))
    corps = client.get(URL).json()
    assert corps["count"] == 2
    ligne = next(r for r in corps["results"] if r["id"] == str(a.pk))
    assert set(ligne) == {
        "id",
        "suivi",
        "mission_id",
        "mission_reference",
        "action_libelle",
        "palier",
        "echeance_reference",
        "destinataire",
        "copie",
        "statut",
        "tentatives",
        "envoyee_le",
        "erreur",
        "created_at",
    }
    assert ligne["mission_reference"] == mission_en_suivi.reference
    assert {r["id"] for r in client.get(URL, {"statut": "ECHEC"}).json()["results"]} == {str(b.pk)}
    assert {r["id"] for r in client.get(URL, {"palier": "J_MOINS_15"}).json()["results"]} == {
        str(a.pk)
    }
    assert client.get(URL, {"mission": str(mission_en_suivi.pk)}).json()["count"] == 2
    assert client.get(URL, {"mission": "00000000-0000-0000-0000-000000000000"}).json()["count"] == 0
    assert client.get(URL, {"date_apres": "2999-01-01"}).json()["count"] == 0
    assert client.get(URL, {"date_apres": datetime.date.today().isoformat()}).json()["count"] == 2
    assert client.get(URL, {"statut": "INCONNU"}).status_code == 400
    assert client.get(URL, {"date_apres": "pas-une-date"}).status_code == 400


def test_reminders_lecture_seule(mission_en_suivi: Any) -> None:  # noqa: F811
    client = client_de(make_user(Role.RAI))
    assert client.post(URL, {}).status_code == 405
