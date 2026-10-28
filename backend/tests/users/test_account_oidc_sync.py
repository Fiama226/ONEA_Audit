import importlib
import uuid
from datetime import timedelta
from typing import Any
from unittest import mock

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from apps.users.models import Role, User
from apps.users.oidc import OneaOIDCBackend
from apps.users.services import resynchroniser_profil

from ..factories import make_user
from .test_oidc import claims, make_token


def _login(c: dict[str, Any]) -> User:
    with mock.patch.object(OneaOIDCBackend, "get_userinfo", return_value=c):
        user = OneaOIDCBackend().get_or_create_user(make_token(), None, None)
    assert user is not None
    return user


@pytest.fixture
def backend() -> OneaOIDCBackend:
    return OneaOIDCBackend()


def test_premiere_connexion_lie_le_compte_csv(db: None) -> None:
    pre = make_user(
        Role.AUDITEUR,
        username="kabore.l",
        keycloak_id=None,
        origine="CSV",
        role_provisoire=True,
        matricule="M-042",
        premiere_connexion_le=None,
    )
    sub = str(uuid.uuid4())
    lie = _login(claims(sub=sub, preferred_username="KABORE.L", roles=["AUDITE"], email="x@y.bf"))
    assert lie.pk == pre.pk and str(lie.keycloak_id) == sub and lie.role == "AUDITE"
    assert not lie.role_provisoire and lie.matricule == "M-042"
    assert lie.premiere_connexion_le is not None
    assert User.objects.filter(username__iexact="kabore.l").count() == 1


def test_sync_respecte_le_profil_local(backend: OneaOIDCBackend, db: None) -> None:
    u = make_user(profil_gere_localement=True, direction_code="X", fonction="Local")
    backend.update_user(u, claims(direction="DAI", fonction="Annuaire"))
    u.refresh_from_db()
    assert (u.direction_code, u.fonction) == ("X", "Local")


def test_resync_applique_les_claims(backend: OneaOIDCBackend, db: None) -> None:
    admin = make_user(Role.ADMIN)
    u = make_user(profil_gere_localement=True, direction_code="X", fonction="Local")
    resynchroniser_profil(u, by=admin)
    u.refresh_from_db()
    backend.update_user(u, claims(direction="DAI", fonction="Annuaire"))
    u.refresh_from_db()
    assert (u.direction_code, u.fonction) == ("DAI", "Annuaire")


def test_connexion_ne_reactive_pas(db: None) -> None:
    sub = uuid.uuid4()
    make_user(keycloak_id=sub, is_active=False, desactive_le=timezone.now())
    u = _login(claims(sub=str(sub)))
    u.refresh_from_db()
    assert u.is_active is False and u.desactive_le is not None


@pytest.mark.parametrize(
    "extra",
    [
        {"keycloak_id": uuid.uuid4()},
        {"is_staff": True},
        {"is_superuser": True},
        {"origine": "CONNEXION"},
    ],
)
def test_liaison_par_identifiant_ignore_compte_lie_ou_privilegie(
    db: None, extra: dict[str, Any]
) -> None:
    kwargs: dict[str, Any] = {"username": "kabore.l", "origine": "CSV", "keycloak_id": None}
    kwargs.update(extra)
    existing = make_user(**kwargs)
    sub = str(uuid.uuid4())
    new = _login(claims(sub=sub, preferred_username="kabore.l", email="n@y.bf"))
    assert new.pk != existing.pk
    existing.refresh_from_db()
    assert existing.keycloak_id == kwargs["keycloak_id"]


def test_liaison_identifiant_prioritaire_sur_email(db: None) -> None:
    by_name = make_user(username="kabore.l", origine="CSV", keycloak_id=None, email="a@y.bf")
    make_user(username="autre", origine="CSV", keycloak_id=None, email="rai@onea.bf")
    sub = str(uuid.uuid4())
    got = _login(claims(sub=sub, preferred_username="kabore.l"))
    assert got.pk == by_name.pk


def test_liaison_compte_inactif_passe_en_attente(db: None) -> None:
    pre = make_user(username="kabore.l", origine="ANNUAIRE", keycloak_id=None, is_active=False)
    got = _login(claims(sub=str(uuid.uuid4()), preferred_username="kabore.l"))
    assert got.pk == pre.pk
    got.refresh_from_db()
    assert got.keycloak_sync_statut == "EN_ATTENTE" and got.is_active is False


def test_premiere_connexion_le_pose_une_seule_fois(db: None) -> None:
    sub = str(uuid.uuid4())
    first = _login(claims(sub=sub))
    t0 = first.premiere_connexion_le
    assert t0 is not None
    earlier = t0 - timedelta(days=1)
    User.objects.filter(pk=first.pk).update(premiere_connexion_le=earlier)
    again = _login(claims(sub=sub))
    assert again.premiere_connexion_le == earlier


def test_update_user_seul_ne_pose_pas_premiere_connexion(
    backend: OneaOIDCBackend, db: None
) -> None:
    u = make_user(origine="ANNUAIRE", keycloak_id=None, premiere_connexion_le=None)
    backend.update_user(u, claims())
    u.refresh_from_db()
    assert u.premiere_connexion_le is None and u.keycloak_id is not None


def test_migration_renseigne_premiere_connexion(db: None) -> None:
    mod = importlib.import_module("apps.users.migrations.0002_account_administration")
    linked = make_user(keycloak_id=uuid.uuid4(), premiere_connexion_le=None)
    unlinked = make_user(keycloak_id=None, premiere_connexion_le=None)
    mod.backfill_premiere_connexion(django_apps, None)
    linked.refresh_from_db()
    unlinked.refresh_from_db()
    assert linked.premiere_connexion_le == linked.date_joined
    assert unlinked.premiere_connexion_le is None


def test_liaison_ne_perd_pas_une_desactivation_concurrente(
    backend: OneaOIDCBackend, db: None
) -> None:
    pre = make_user(username="kabore.l", origine="CSV", keycloak_id=None)
    stale = User.objects.get(pk=pre.pk)  # read while still active
    User.objects.filter(pk=pre.pk).update(is_active=False)
    backend.update_user(stale, claims(sub=str(uuid.uuid4())))
    pre.refresh_from_db()
    assert pre.keycloak_id is not None and pre.is_active is False
    assert pre.keycloak_sync_statut == "EN_ATTENTE"
    assert pre.keycloak_sync_tentatives == 0 and pre.keycloak_sync_erreur == ""


def test_premiere_connexion_atomique(backend: OneaOIDCBackend, db: None) -> None:
    u = make_user(keycloak_id=uuid.uuid4(), premiere_connexion_le=None)
    stale = User.objects.get(pk=u.pk)
    earlier = timezone.now() - timedelta(days=2)
    User.objects.filter(pk=u.pk).update(premiere_connexion_le=earlier)
    with mock.patch(
        "mozilla_django_oidc.auth.OIDCAuthenticationBackend.get_or_create_user",
        return_value=stale,
    ):
        backend.get_or_create_user(make_token(), None, None)
    u.refresh_from_db()
    assert u.premiere_connexion_le == earlier


def test_compte_inactif_refuse_garde_en_attente_de_connexion(db: None) -> None:
    pre = make_user(username="kabore.l", origine="CSV", keycloak_id=None, is_active=False)
    got = _login(claims(sub=str(uuid.uuid4()), preferred_username="kabore.l"))
    got.refresh_from_db()
    assert got.pk == pre.pk and got.en_attente_connexion


def test_nom_complet_et_en_attente_connexion(db: None) -> None:
    u = make_user(first_name="Awa", last_name="Sawadogo", premiere_connexion_le=None)
    assert u.nom_complet == "Awa Sawadogo" and u.en_attente_connexion
    u2 = make_user(
        first_name="", last_name="", username="solo", premiere_connexion_le=timezone.now()
    )
    assert u2.nom_complet == "solo" and not u2.en_attente_connexion


def test_liaison_identifiant_avertit_sans_donnee_personnelle(
    db: None, caplog: pytest.LogCaptureFixture
) -> None:
    make_user(username="kabore.l", origine="CSV", keycloak_id=None, email="a@y.bf")
    make_user(username="autre", origine="CSV", keycloak_id=None, email="rai@onea.bf")
    with caplog.at_level("WARNING", logger="apps.users.oidc"):
        _login(claims(sub=str(uuid.uuid4()), preferred_username="kabore.l"))
    msgs = [r.getMessage() for r in caplog.records if "different local accounts" in r.getMessage()]
    assert msgs
    assert all("kabore" not in m and "rai@onea.bf" not in m for m in msgs)


def test_email_non_verifie_ne_lie_pas_un_compte_csv(db: None) -> None:
    pre = make_user(username="csv.u", origine="CSV", keycloak_id=None, email="rai@onea.bf")
    new = _login(claims(sub=str(uuid.uuid4()), preferred_username="autre", email_verified=False))
    assert new.pk != pre.pk
    pre.refresh_from_db()
    assert pre.keycloak_id is None
