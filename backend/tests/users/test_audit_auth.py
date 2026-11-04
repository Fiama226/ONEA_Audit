"""Audit trail of the password and login-code actions (final review I1 and M2).

django-auditlog writes an entry only when a tracked field changes, and `password` is not
tracked: a plain password change or a reset by code left no trace. Each action now writes
exactly one entry naming it (`additional_data["action"]`), with its actor, and no secret.
"""

import json
import re
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.core import mail
from rest_framework.test import APIClient

from apps.users import services
from apps.users.delegation import ACTIONS
from apps.users.models import Role, User

from ..factories import make_user

pytestmark = pytest.mark.django_db

MDP = "Mot-de-passe-solide-2026"
NOUVEAU = "Nouvelle-phrase-secrete-77"


def _entrees(compte: User) -> list[LogEntry]:
    return list(LogEntry.objects.get_for_object(compte).order_by("pk"))


def _nouvelles(compte: User, avant: int) -> list[LogEntry]:
    return _entrees(compte)[avant:]


def _action(entree: LogEntry) -> str | None:
    return (entree.additional_data or {}).get("action")


def _sans_secret(entree: LogEntry, *secrets: str) -> None:
    assert "password" not in entree.changes_dict
    brut = json.dumps([entree.changes, entree.additional_data, entree.serialized_data], default=str)
    for secret in secrets:
        assert secret not in brut


def _connecte(identifiant: str, mot_de_passe: str = MDP) -> APIClient:
    client = APIClient()
    r = client.post(
        "/api/v1/auth/login/",
        {"identifiant": identifiant, "mot_de_passe": mot_de_passe},
        format="json",
    )
    assert r.status_code == 200, r.content
    return client


def _changer(client: APIClient, ancien: str = MDP, nouveau: str = NOUVEAU) -> Any:
    return client.post(
        "/api/v1/auth/password/change/", {"ancien": ancien, "nouveau": nouveau}, format="json"
    )


@pytest.fixture
def agent() -> User:
    return make_user(Role.AUDITEUR, username="awa", email="awa@onea.bf", password=MDP)


def test_changement_volontaire_du_mot_de_passe(agent: User) -> None:
    client = _connecte("awa")
    avant = len(_entrees(agent))
    assert _changer(client).status_code == 200
    (entree,) = _nouvelles(agent, avant)
    assert _action(entree) == "changement_mot_de_passe"
    assert entree.actor_id == agent.pk
    assert entree.action == LogEntry.Action.UPDATE
    _sans_secret(entree, MDP, NOUVEAU)


def test_changement_refuse_sans_entree(agent: User) -> None:
    client = _connecte("awa")
    avant = len(_entrees(agent))
    assert _changer(client, ancien="Pas-le-bon-mot-de-passe-1").status_code != 200
    assert _nouvelles(agent, avant) == []


def test_changement_impose_a_la_premiere_connexion(agent: User) -> None:
    User.objects.filter(pk=agent.pk).update(doit_changer_mot_de_passe=True)
    client = _connecte("awa")
    avant = len(_entrees(agent))
    assert _changer(client).status_code == 200
    (entree,) = _nouvelles(agent, avant)  # one entry, not one per mechanism
    assert _action(entree) == "changement_mot_de_passe_impose"
    assert entree.actor_id == agent.pk
    assert entree.changes_dict["doit_changer_mot_de_passe"] == ["True", "False"]
    _sans_secret(entree, MDP, NOUVEAU)


def test_reinitialisation_par_code(agent: User) -> None:
    APIClient().post("/api/v1/auth/password/forgot/", {"identifiant": "awa"}, format="json")
    trouve = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert trouve is not None
    code = trouve.group(1)
    avant = len(_entrees(agent))
    r = APIClient().post(
        "/api/v1/auth/password/reset/",
        {"identifiant": "awa", "code": code, "nouveau_mot_de_passe": NOUVEAU},
        format="json",
    )
    assert r.status_code == 204
    (entree,) = _nouvelles(agent, avant)
    assert _action(entree) == "reinitialisation_par_code"
    assert entree.actor_id == agent.pk
    _sans_secret(entree, MDP, NOUVEAU, code)


def test_reinitialisation_par_code_refusee_sans_entree(agent: User) -> None:
    APIClient().post("/api/v1/auth/password/forgot/", {"identifiant": "awa"}, format="json")
    avant = len(_entrees(agent))
    r = APIClient().post(
        "/api/v1/auth/password/reset/",
        {"identifiant": "awa", "code": "000000", "nouveau_mot_de_passe": NOUVEAU},
        format="json",
    )
    assert r.status_code == 400
    assert _nouvelles(agent, avant) == []


def test_activation_et_desactivation_du_code_par_le_titulaire(agent: User) -> None:
    client = _connecte("awa")
    avant = len(_entrees(agent))
    assert client.post("/api/v1/auth/otp/enable/code/").status_code == 202
    code = re.search(r"\b(\d{6})\b", str(mail.outbox[-1].body))
    assert code is not None
    activation = client.post("/api/v1/auth/otp/enable/", {"code": code.group(1)}, format="json")
    assert activation.status_code == 200
    (entree,) = _nouvelles(agent, avant)
    assert _action(entree) == "activation_otp"
    assert entree.actor_id == agent.pk
    assert entree.changes_dict["otp_connexion_actif"] == ["False", "True"]
    # Turning on what is already on changes nothing: no entry.
    assert client.post("/api/v1/auth/otp/enable/").status_code == 200
    assert len(_nouvelles(agent, avant)) == 1
    r = client.post("/api/v1/auth/otp/disable/", {"mot_de_passe": MDP}, format="json")
    assert r.status_code == 200
    entree = _nouvelles(agent, avant)[-1]
    assert _action(entree) == "desactivation_otp"
    assert entree.actor_id == agent.pk
    assert len(_nouvelles(agent, avant)) == 2
    _sans_secret(entree, MDP)


@pytest.mark.parametrize("delegue", [False, True])
def test_reinitialisation_par_l_administration(agent: User, delegue: bool) -> None:
    admin = make_user(Role.ADMIN, username="chef")
    acteur = admin
    if delegue:
        acteur = make_user(Role.AUDITEUR, username="adjoint")
        droits: dict[str, bool] = {**dict.fromkeys(ACTIONS, False), "reinitialiser": True}
        services.definir_delegation(acteur, droits=droits, par=admin)
    client = APIClient()
    client.force_authenticate(acteur)
    for _ in range(2):  # the second reset changes no flag but the expiry: still logged
        avant = len(_entrees(agent))
        r = client.post(
            f"/api/v1/user-accounts/{agent.pk}/reset-password/",
            {"envoyer_courriel": False},
            format="json",
        )
        assert r.status_code == 200, r.content
        (entree,) = _nouvelles(agent, avant)
        assert _action(entree) == "reinitialisation_mot_de_passe"
        assert entree.actor_id == acteur.pk
        _sans_secret(entree, r.json()["mot_de_passe_temporaire"])


def test_journal_expose_l_action_metier(agent: User) -> None:
    rai = make_user(Role.RAI, username="rai")
    client = _connecte("awa")
    assert _changer(client).status_code == 200
    lecteur = APIClient()
    lecteur.force_authenticate(rai)
    r = lecteur.get("/api/v1/audit-log/", {"model": "users.user", "object_id": str(agent.pk)})
    assert r.status_code == 200
    actions = [item["action_metier"] for item in r.json()["results"]]
    assert "changement_mot_de_passe" in actions
    assert all(a is None or isinstance(a, str) for a in actions)


def test_desactivation_et_reactivation_nomment_leur_action(agent: User) -> None:
    admin = make_user(Role.ADMIN, username="chef")
    avant = len(_entrees(agent))
    services.desactiver(agent, motif="Départ", by=admin)
    (entree,) = _nouvelles(agent, avant)
    assert _action(entree) == "desactivation_compte"
    assert entree.actor_id == admin.pk
    services.reactiver(agent, by=admin)
    entree = _nouvelles(agent, avant)[-1]
    assert _action(entree) == "reactivation_compte"
    assert entree.actor_id == admin.pk


def test_delegation_nomme_son_action(agent: User) -> None:
    from apps.users.models import DelegationGestionComptes

    admin = make_user(Role.ADMIN, username="chef")
    tous: dict[str, bool] = dict.fromkeys(ACTIONS, True)
    delegation = services.definir_delegation(agent, droits=tous, par=admin)
    (entree,) = LogEntry.objects.get_for_object(delegation)
    assert _action(entree) == "attribution_delegation"
    assert entree.actor_id == admin.pk
    services.definir_delegation(agent, droits=dict.fromkeys(ACTIONS, False), par=admin)
    entrees = list(LogEntry.objects.get_for_object(delegation).order_by("pk"))
    assert _action(entrees[-1]) == "retrait_delegation"
    # Disabling a delegate drops his rights: the entry names the withdrawal too.
    services.definir_delegation(agent, droits=tous, par=admin)
    services.desactiver(agent, motif="Départ", by=admin)
    derniere = (
        LogEntry.objects.get_for_object(DelegationGestionComptes.objects.get(user=agent))
        .order_by("pk")
        .last()
    )
    assert derniere is not None
    assert _action(derniere) == "retrait_delegation"
