from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied
from django.db import close_old_connections
from django.test import Client
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction, TypeEntite
from apps.users.delegation import DROIT_REFUSE, acteur_systeme
from apps.users.models import OrigineCompte, Role, User
from apps.users.services import (
    COMPTE_PERSONNEL,
    DEJA_ACTIF,
    DEJA_DESACTIVE,
    DERNIER_ADMIN,
    DIRECTION_INCONNUE,
    MATRICULE_PRIS,
    PROFILE_FIELDS,
    actions_compte,
    desactiver,
    direction_existe,
    modifier_profil,
    reactiver,
)

from ..connexion import connecter
from ..factories import make_user


def _direction(code: str) -> Direction:
    return Direction.objects.create(code=code, libelle=code, type=TypeEntite.DIRECTION)


def test_constants() -> None:
    assert PROFILE_FIELDS == {
        "matricule",
        "direction_code",
        "fonction",
        "email",
        "first_name",
        "last_name",
    }
    assert OrigineCompte.CSV.label == "Import CSV"
    assert User().origine == OrigineCompte.ADMINISTRATION


def test_desactiver_puis_reactiver(admin: User, user: User) -> None:
    desactiver(user, motif="Départ à la retraite", by=admin)
    user.refresh_from_db()
    assert not user.is_active and user.desactive_par == admin and user.desactive_le is not None
    reactiver(user, by=admin)
    user.refresh_from_db()
    assert user.is_active and user.desactive_le is None and user.motif_desactivation == ""
    changes = [e.changes_dict for e in LogEntry.objects.get_for_object(user).filter(actor=admin)]
    assert any(c.get("motif_desactivation") == ["", "Départ à la retraite"] for c in changes)


def _sessions_de(compte: User) -> int:
    return sum(
        1 for s in Session.objects.all() if s.get_decoded().get("_auth_user_id") == str(compte.pk)
    )


def test_desactiver_termine_les_sessions(admin: User, user: User) -> None:
    connecter(Client(), user)
    connecter(Client(), user)
    connecter(Client(), admin)
    assert _sessions_de(user) == 2
    desactiver(user, motif="x", by=admin)
    assert _sessions_de(user) == 0
    assert _sessions_de(admin) == 1


def test_desactiver_soi_meme_refuse(admin: User) -> None:
    make_user(Role.ADMIN)
    with pytest.raises(RegleMetierError) as exc:
        desactiver(admin, motif="x", by=admin)
    assert exc.value.message == COMPTE_PERSONNEL
    assert COMPTE_PERSONNEL == "Vous ne pouvez pas désactiver votre propre compte."


def test_desactiver_deux_fois_refuse(admin: User, user: User) -> None:
    desactiver(user, motif="x", by=admin)
    with pytest.raises(RegleMetierError) as exc:
        desactiver(user, motif="y", by=admin)
    assert exc.value.message == DEJA_DESACTIVE == "Ce compte est déjà désactivé."


def test_reactiver_actif_refuse(admin: User, user: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        reactiver(user, by=admin)
    assert exc.value.message == DEJA_ACTIF == "Ce compte est déjà actif."


def test_dernier_admin_refuse(admin: User) -> None:
    # The services check rights now: an inactive admin acts only as an explicit system
    # actor (like the demo one), and is not an active admin keeping the platform run.
    other = make_user(Role.ADMIN, is_active=False)
    with acteur_systeme(other), pytest.raises(RegleMetierError) as exc:
        desactiver(admin, motif="x", by=other)
    assert exc.value.message == DERNIER_ADMIN
    assert (
        DERNIER_ADMIN
        == "Impossible de désactiver le dernier administrateur actif de la plateforme."
    )


def _try_desactiver(args: tuple[User, User]) -> str:
    cible, par = args
    try:
        desactiver(cible, motif="x", by=par)
        return "ok"
    except RegleMetierError as exc:
        return exc.message
    except PermissionDenied as exc:
        return str(exc)
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_desactivations_croisees_gardent_un_admin() -> None:
    a, b = make_user(Role.ADMIN), make_user(Role.ADMIN)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(_try_desactiver, [(b, a), (a, b)]))
    # Serialized on the locked rows: the second caller has just been deactivated, so his
    # rights, re-read under the lock, are gone (an inactive admin is no admin). Before the
    # actor lock and the inactive-admin rule, the last-admin guard refused it instead.
    assert sorted(results) == sorted(["ok", DROIT_REFUSE])
    assert User.objects.filter(role=Role.ADMIN, is_active=True).count() == 1


def test_modifier_matricule(admin: User, user: User) -> None:
    modifier_profil(user, changes={"matricule": " M-1 "}, by=admin)
    user.refresh_from_db()
    assert user.matricule == "M-1"


def test_modifier_direction_et_fonction(admin: User, user: User) -> None:
    d = _direction("DIRX")
    modifier_profil(user, changes={"direction_code": d.code, "fonction": " Chef "}, by=admin)
    user.refresh_from_db()
    assert user.direction_code == d.code
    assert user.fonction == "Chef"


def test_direction_inconnue_refusee(admin: User, user: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        modifier_profil(user, changes={"direction_code": "ZZZ"}, by=admin)
    assert exc.value.errors == {"direction_code": [DIRECTION_INCONNUE]}


def test_direction_inchangee_non_controlee(admin: User) -> None:
    u = make_user(Role.AUDITEUR, direction_code="DAI")  # not in referentiel
    modifier_profil(u, changes={"direction_code": "DAI", "matricule": "M-9"}, by=admin)
    u.refresh_from_db()
    assert u.matricule == "M-9"


def test_matricule_duplique_refuse(admin: User, user: User) -> None:
    make_user(matricule="M-1")
    with pytest.raises(RegleMetierError) as exc:
        modifier_profil(user, changes={"matricule": "M-1"}, by=admin)
    assert exc.value.errors == {"matricule": [MATRICULE_PRIS]}
    assert MATRICULE_PRIS == "Ce matricule est déjà attribué à un autre utilisateur."


def test_matricules_vides_multiples_acceptes(db: None) -> None:
    make_user(matricule="")
    make_user(matricule="")
    assert User.objects.filter(matricule="").count() >= 2


@pytest.mark.parametrize(
    ("self_target", "active", "otp", "expected"),
    [
        (False, True, False, (True, True, False, True, False, True, True, True)),
        (True, True, True, (True, False, False, False, False, True, True, False)),
        (False, False, False, (True, False, True, False, False, True, True, True)),
        (False, False, True, (True, False, True, False, True, True, True, True)),
        (False, True, True, (True, True, False, True, True, True, True, True)),
    ],
)
def test_actions_compte(
    admin: User,
    user: User,
    self_target: bool,
    active: bool,
    otp: bool,
    expected: tuple[bool, ...],
) -> None:
    target = admin if self_target else user
    target.otp_connexion_actif = otp
    target.is_active = active
    actions = actions_compte(target, admin)
    assert tuple(actions.values()) == expected
    assert list(actions) == [
        "modifier_profil",
        "desactiver",
        "reactiver",
        "reinitialiser_mot_de_passe",
        "desactiver_otp",
        "modifier_courriel",
        "modifier_direction",
        "changer_role",
    ]


def test_direction_existe_ignore_les_supprimees(db: None) -> None:
    d = _direction("ABC")
    assert direction_existe("ABC")
    assert not direction_existe("")
    d.soft_delete(by=make_user(Role.ADMIN))
    assert not direction_existe("ABC")
    assert Direction.all_objects.filter(code="ABC").exists()


def test_ecritures_historisees_avec_l_admin_pour_acteur(admin: User, user: User) -> None:
    modifier_profil(user, changes={"fonction": "Chef"}, by=admin)
    entries = LogEntry.objects.get_for_object(user).filter(actor=admin)
    assert any("fonction" in e.changes_dict for e in entries)


def test_champs_techniques_hors_historique(admin: User, user: User) -> None:
    user.echecs_connexion = 3
    user.last_login = timezone.now()
    user.set_password("un-autre-mot-de-passe-2026")
    user.save()
    desactiver(user, motif="x", by=admin)
    all_changes: dict[str, Any] = {}
    for e in LogEntry.objects.get_for_object(user):
        all_changes.update(e.changes_dict)
    assert not {"echecs_connexion", "last_login", "password"} & set(all_changes)
    assert "is_active" in all_changes


def test_migration_refuse_les_matricules_en_double(db: None) -> None:
    import importlib

    from django.apps import apps as django_apps
    from django.db import connection

    mod = importlib.import_module("apps.users.migrations.0002_account_administration")
    constraint = next(
        c for c in User._meta.constraints if c.name == "users_matricule_unique_non_vide"
    )
    with connection.schema_editor() as editor:
        editor.remove_constraint(User, constraint)
    make_user(matricule="M-7")
    make_user(matricule="M-7")
    with pytest.raises(RuntimeError, match="M-7"):
        mod.verifier_matricules_uniques(django_apps, None)
