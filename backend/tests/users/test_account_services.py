import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from auditlog.models import LogEntry
from django.db import close_old_connections

from apps.core.exceptions import RegleMetierError
from apps.referentiel.models import Direction, TypeEntite
from apps.users.models import KeycloakSyncStatut, OrigineCompte, Role, User
from apps.users.services import (
    COMPTE_PERSONNEL,
    DEJA_ACTIF,
    DEJA_DESACTIVE,
    DEJA_SYNCHRONISE,
    DERNIER_ADMIN,
    DIRECTION_INCONNUE,
    MATRICULE_PRIS,
    PROFILE_FIELDS,
    SYNCED_FIELDS,
    actions_compte,
    desactiver,
    direction_existe,
    modifier_profil,
    reactiver,
    resynchroniser_profil,
)

from ..factories import make_user


def _direction(code: str) -> Direction:
    return Direction.objects.create(code=code, libelle=code, type=TypeEntite.DIRECTION)


def test_constants() -> None:
    assert PROFILE_FIELDS == {"matricule", "direction_code", "fonction"}
    assert SYNCED_FIELDS == {"direction_code", "fonction"}
    assert OrigineCompte.CSV.label == "Import CSV"
    assert KeycloakSyncStatut.ECHEC.label == "Échec"


def test_desactiver_puis_reactiver(admin: User, user: User) -> None:
    user.keycloak_id = uuid.uuid4()
    user.save()
    desactiver(user, motif="Départ à la retraite", by=admin)
    user.refresh_from_db()
    assert (
        not user.is_active
        and user.desactive_par == admin
        and user.keycloak_sync_statut == "EN_ATTENTE"
    )
    reactiver(user, by=admin)
    user.refresh_from_db()
    assert user.is_active and user.desactive_le is None and user.motif_desactivation == ""
    assert user.keycloak_sync_statut == "EN_ATTENTE"
    changes = [e.changes_dict for e in LogEntry.objects.get_for_object(user).filter(actor=admin)]
    assert any(c.get("motif_desactivation") == ["", "Départ à la retraite"] for c in changes)


def test_desactiver_compte_non_lie_reste_a_jour(admin: User, user: User) -> None:
    desactiver(user, motif="x", by=admin)
    user.refresh_from_db()
    assert not user.is_active
    assert user.keycloak_sync_statut == KeycloakSyncStatut.A_JOUR


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
    other = make_user(Role.AUDITEUR)
    with pytest.raises(RegleMetierError) as exc:
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
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_desactivations_croisees_gardent_un_admin() -> None:
    a, b = make_user(Role.ADMIN), make_user(Role.ADMIN)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(_try_desactiver, [(b, a), (a, b)]))
    assert sorted(results) == sorted(["ok", DERNIER_ADMIN])
    assert User.objects.filter(role=Role.ADMIN, is_active=True).count() == 1


def test_matricule_seul_ne_pose_pas_le_drapeau(admin: User, user: User) -> None:
    modifier_profil(user, changes={"matricule": " M-1 "}, by=admin)
    user.refresh_from_db()
    assert user.matricule == "M-1" and not user.profil_gere_localement


def test_modifier_direction_pose_le_drapeau(admin: User, user: User) -> None:
    d = _direction("DIRX")
    modifier_profil(user, changes={"direction_code": d.code, "fonction": " Chef "}, by=admin)
    user.refresh_from_db()
    assert user.profil_gere_localement and user.direction_code == d.code
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


def test_resync_deja_synchronise_refuse(admin: User, user: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        resynchroniser_profil(user, by=admin)
    assert exc.value.message == DEJA_SYNCHRONISE
    assert DEJA_SYNCHRONISE == "Le profil est déjà synchronisé avec l'annuaire."


def test_resync_leve_le_drapeau(admin: User, user: User) -> None:
    User.objects.filter(pk=user.pk).update(profil_gere_localement=True)
    resynchroniser_profil(user, by=admin)
    user.refresh_from_db()
    assert not user.profil_gere_localement


@pytest.mark.parametrize(
    ("self_target", "active", "linked", "statut", "local", "expected"),
    [
        (False, True, True, "A_JOUR", False, (True, True, False, False, False)),
        (True, True, False, "A_JOUR", False, (True, False, False, False, False)),
        (False, False, True, "ECHEC", True, (True, False, True, True, True)),
        (False, False, True, "EN_ATTENTE", False, (True, False, True, False, True)),
        (False, False, False, "EN_ATTENTE", False, (True, False, True, False, False)),
    ],
)
def test_actions_compte(
    admin: User,
    user: User,
    self_target: bool,
    active: bool,
    linked: bool,
    statut: str,
    local: bool,
    expected: tuple[bool, ...],
) -> None:
    target = admin if self_target else user
    target.is_active = active
    target.keycloak_id = uuid.uuid4() if linked else None
    target.keycloak_sync_statut = statut
    target.profil_gere_localement = local
    actions = actions_compte(target, admin)
    assert tuple(actions.values()) == expected
    assert list(actions) == [
        "modifier_profil",
        "desactiver",
        "reactiver",
        "resynchroniser_profil",
        "relancer_synchro_keycloak",
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
    user.keycloak_id = uuid.uuid4()
    user.save()
    desactiver(user, motif="x", by=admin)
    all_changes: dict[str, Any] = {}
    for e in LogEntry.objects.get_for_object(user):
        all_changes.update(e.changes_dict)
    assert "keycloak_sync_le" not in all_changes
    assert "keycloak_sync_tentatives" not in all_changes
    assert "keycloak_sync_statut" in all_changes
