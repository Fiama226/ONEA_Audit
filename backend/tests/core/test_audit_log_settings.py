"""SEC-02 : contenu des missions dans la piste d'audit, paramétrable par l'ADMIN."""

import pytest
from auditlog.models import LogEntry
from rest_framework.test import APIClient

from apps.core.models import ParametrePlateforme
from apps.core.parametres import CLE_JOURNAL_CONTENU, ContenuJournal, contenu_journal
from apps.users.models import Role, User

from ..factories import MissionFactory, make_user

pytestmark = pytest.mark.django_db
LOG = "/api/v1/audit-log/"
REGLAGE = "/api/v1/audit-log-settings/"
MASQUE = "[masqué]"


def _client(u: User | None) -> APIClient:
    c = APIClient()
    if u is not None:
        c.force_authenticate(user=u)
    return c


@pytest.fixture
def entree_mission(rai: User) -> LogEntry:
    """Une entrée de journal portant sur un objet de mission (contenu confidentiel)."""
    from apps.core.audit import actor_scope

    with actor_scope(rai):
        mission = MissionFactory(titre="Titre confidentiel", created_by=rai, updated_by=rai)
    return LogEntry.objects.filter(object_pk=str(mission.pk)).order_by("-id").first()


def _item(client: APIClient, entree: LogEntry) -> dict:
    res = client.get(LOG, {"object_id": entree.object_pk})
    assert res.status_code == 200
    return res.json()["results"][0]


def test_defaut_complet(admin: User, entree_mission: LogEntry) -> None:
    assert contenu_journal() == ContenuJournal.COMPLET
    item = _item(_client(admin), entree_mission)
    assert "Titre confidentiel" in str(item["changes"])
    assert item["object_repr"] != MASQUE


def test_masque_pour_admin_pas_pour_rai(admin: User, rai: User, entree_mission: LogEntry) -> None:
    assert _client(admin).patch(REGLAGE, {"valeur": "MASQUE"}, format="json").status_code == 200
    item = _item(_client(admin), entree_mission)
    assert "Titre confidentiel" not in str(item)
    assert item["actor"] is not None and item["timestamp"] and item["action"] == "create"
    assert item["model"] == "missions.mission" and item["object_id"] == entree_mission.object_pk
    assert item["object_repr"] == MASQUE
    assert all(v == [MASQUE, MASQUE] for v in item["changes"].values()) and item["changes"]
    rai_item = _item(_client(rai), entree_mission)
    assert "Titre confidentiel" in str(rai_item["changes"])


def test_masque_garde_entites_hors_mission(admin: User) -> None:
    _client(admin).patch(REGLAGE, {"valeur": "MASQUE"}, format="json")
    cible = make_user(Role.AUDITE)
    cible.fonction = "Chef de service"
    cible.save()
    res = _client(admin).get(LOG, {"object_id": str(cible.pk), "action": "update"})
    assert res.json()["results"][0]["changes"]["fonction"] == [
        "Auditeur interne",
        "Chef de service",
    ]


def test_masque_aussi_sur_le_detail(admin: User, entree_mission: LogEntry) -> None:
    _client(admin).patch(REGLAGE, {"valeur": "MASQUE"}, format="json")
    res = _client(admin).get(f"{LOG}{entree_mission.pk}/")
    assert res.status_code == 200 and "Titre confidentiel" not in str(res.json())


def test_lecture_du_reglage(admin: User, rai: User, user: User, audite: User) -> None:
    assert _client(admin).get(REGLAGE).json()["valeur"] == "COMPLET"
    assert _client(rai).get(REGLAGE).status_code == 200
    for u in (user, audite):
        assert _client(u).get(REGLAGE).status_code == 403
    assert _client(None).get(REGLAGE).status_code in (401, 403)


def test_non_admin_ne_peut_pas_modifier(rai: User, user: User, audite: User, dg: User) -> None:
    for u in (rai, user, audite, dg):
        res = _client(u).patch(REGLAGE, {"valeur": "MASQUE"}, format="json")
        assert res.status_code == 403
    assert not ParametrePlateforme.objects.exists()
    assert contenu_journal() == ContenuJournal.COMPLET


def test_valeur_invalide_champ_en_erreur(admin: User) -> None:
    res = _client(admin).patch(REGLAGE, {"valeur": "AUTRE"}, format="json")
    assert res.status_code == 400
    assert not ParametrePlateforme.objects.exists()


def test_changement_audite(admin: User) -> None:
    _client(admin).patch(REGLAGE, {"valeur": "MASQUE"}, format="json")
    ligne = ParametrePlateforme.objects.get(cle=CLE_JOURNAL_CONTENU)
    entrees = LogEntry.objects.filter(object_pk=str(ligne.pk), actor=admin)
    assert entrees.exists()
    dernier = entrees.order_by("-id").first()
    assert dernier.changes_dict["valeur"] == ["COMPLET", "MASQUE"]
    # Le changement reste lisible par l'ADMIN en mode masqué (entité hors mission).
    item = _client(admin).get(LOG, {"object_id": str(ligne.pk)}).json()["results"][0]
    assert item["changes"]["valeur"] == ["COMPLET", "MASQUE"]
    data = _client(admin).get(REGLAGE).json()
    assert data["valeur"] == "MASQUE" and data["modifie_par"]["id"] == admin.pk
    _client(admin).patch(REGLAGE, {"valeur": "COMPLET"}, format="json")
    assert contenu_journal() == ContenuJournal.COMPLET
