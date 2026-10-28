from datetime import timedelta

import pytest
from auditlog.models import LogEntry
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.users.keycloak_admin import KeycloakIndisponible
from apps.users.keycloak_sync import (
    DEJA_SYNCHRONISE_KEYCLOAK,
    NON_LIE_ANNUAIRE,
    relancer_synchronisation,
    synchroniser_keycloak,
)
from apps.users.models import KeycloakSyncStatut, Role, User
from apps.users.services import desactiver, reactiver
from apps.users.tasks import synchroniser_comptes_keycloak

from ..conftest import FakeKeycloakAdmin
from ..factories import make_user


def _lie(fake: FakeKeycloakAdmin, **kwargs: object) -> User:
    return make_user(Role.AUDITEUR, keycloak_id=fake.add_user("auditeur2"), **kwargs)


def test_desactivation_keycloak_en_panne_reste_effective(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = _lie(fake_keycloak)
    fake_keycloak.fail_with(KeycloakIndisponible("Keycloak injoignable."), times=1)
    desactiver(cible, motif="Départ", by=admin)
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert not cible.is_active and cible.keycloak_sync_statut == "ECHEC"
    assert cible.keycloak_sync_erreur == "Keycloak injoignable."
    assert cible.keycloak_id is not None and fake_keycloak.enabled(cible.keycloak_id)
    cible = relancer_synchronisation(cible, by=admin)
    assert cible.keycloak_id is not None
    assert cible.keycloak_sync_statut == "A_JOUR" and not fake_keycloak.enabled(cible.keycloak_id)
    assert fake_keycloak.calls[-1] == ("logout", cible.keycloak_id)


def test_synchro_converge_si_reactive_entre_temps(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = _lie(fake_keycloak)
    desactiver(cible, motif="Erreur", by=admin)

    def race(*_: object) -> None:
        fake_keycloak.on_set_enabled(lambda *_: None)  # one shot
        reactiver(User.objects.get(pk=cible.pk), by=admin)

    fake_keycloak.on_set_enabled(race)
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert cible.is_active and cible.keycloak_sync_statut == "EN_ATTENTE"
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert cible.keycloak_sync_statut == "A_JOUR"
    assert cible.keycloak_id is not None and fake_keycloak.enabled(cible.keycloak_id)


def test_relance_apres_retablissement(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    cible = _lie(fake_keycloak)
    desactiver(cible, motif="x", by=admin)
    fake_keycloak.fail_with(KeycloakIndisponible("Keycloak injoignable."), times=1)
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert cible.keycloak_sync_tentatives == 1 and cible.keycloak_sync_le is not None
    cible = relancer_synchronisation(cible, by=admin)
    assert cible.keycloak_sync_statut == "A_JOUR" and cible.keycloak_sync_erreur == ""
    assert cible.keycloak_sync_tentatives == 2


def test_relance_a_jour_refusee(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    cible = _lie(fake_keycloak)
    with pytest.raises(RegleMetierError) as exc:
        relancer_synchronisation(cible, by=admin)
    assert exc.value.message == DEJA_SYNCHRONISE_KEYCLOAK


def test_relance_compte_non_lie_refusee(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    cible = make_user(Role.AUDITEUR, keycloak_id=None)
    with pytest.raises(RegleMetierError) as exc:
        relancer_synchronisation(cible, by=admin)
    assert exc.value.message == NON_LIE_ANNUAIRE


def test_synchro_ignore_compte_non_lie_ou_a_jour(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = make_user(Role.AUDITEUR, keycloak_id=None)
    assert synchroniser_keycloak(cible.pk).keycloak_sync_tentatives == 0
    assert fake_keycloak.calls == []


def test_reactivation_reactive_keycloak_sans_logout(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = _lie(fake_keycloak)
    assert cible.keycloak_id is not None
    desactiver(cible, motif="x", by=admin)
    synchroniser_keycloak(cible.pk, by=admin)
    assert not fake_keycloak.enabled(cible.keycloak_id)
    fake_keycloak.calls.clear()
    reactiver(User.objects.get(pk=cible.pk), by=admin)
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert cible.keycloak_id is not None
    assert cible.keycloak_sync_statut == "A_JOUR" and fake_keycloak.enabled(cible.keycloak_id)
    assert [c[0] for c in fake_keycloak.calls] == ["set_enabled"]


def test_404_desactivation_a_jour_reactivation_echec(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    cible = _lie(fake_keycloak)
    assert cible.keycloak_id is not None
    del fake_keycloak.users[cible.keycloak_id]
    desactiver(cible, motif="x", by=admin)
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert cible.keycloak_sync_statut == "A_JOUR"
    reactiver(cible, by=admin)
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert cible.keycloak_sync_statut == "ECHEC"
    assert cible.keycloak_sync_erreur == "Compte introuvable dans Keycloak."


def test_non_configure_reste_en_echec_avec_message(
    admin: User, settings: pytest.FixtureRequest
) -> None:
    settings.KEYCLOAK_ADMIN_API_CLIENT_SECRET = ""  # type: ignore[attr-defined]
    cible = make_user(Role.AUDITEUR, keycloak_id="6f9619ff-8b86-d011-b42d-00c04fc964ff")
    desactiver(cible, motif="x", by=admin)
    cible = synchroniser_keycloak(cible.pk, by=admin)
    assert cible.keycloak_sync_statut == "ECHEC" and not cible.is_active
    assert cible.keycloak_sync_erreur == "Synchronisation Keycloak non configurée."


def test_tache_beat_relance_les_echecs(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    now = timezone.now()
    comptes = [
        make_user(
            Role.AUDITEUR,
            keycloak_id=fake_keycloak.add_user(f"u{i}"),
            is_active=False,
            keycloak_sync_statut=KeycloakSyncStatut.ECHEC,
            keycloak_sync_le=now - timedelta(hours=3 - i),
        )
        for i in range(3)
    ]
    assert synchroniser_comptes_keycloak(limit=2) == 2
    for c in comptes:
        c.refresh_from_db()
    assert [c.keycloak_sync_statut for c in comptes] == ["A_JOUR", "A_JOUR", "ECHEC"]


def test_tache_beat_s_arrete_si_keycloak_indisponible(
    admin: User, fake_keycloak: FakeKeycloakAdmin
) -> None:
    for i in range(3):
        make_user(
            Role.AUDITEUR,
            keycloak_id=fake_keycloak.add_user(f"u{i}"),
            is_active=False,
            keycloak_sync_statut=KeycloakSyncStatut.EN_ATTENTE,
        )
    fake_keycloak.fail_with(KeycloakIndisponible("Keycloak injoignable."), times=3)
    assert synchroniser_comptes_keycloak() == 1
    assert len([c for c in fake_keycloak.calls if c[0] == "set_enabled"]) == 1
    assert User.objects.filter(keycloak_sync_statut="ECHEC").count() == 1


def test_synchro_historisee_avec_acteur(admin: User, fake_keycloak: FakeKeycloakAdmin) -> None:
    cible = _lie(fake_keycloak)
    desactiver(cible, motif="x", by=admin)
    synchroniser_keycloak(cible.pk, by=admin)
    last = LogEntry.objects.get_for_object(User.objects.get(pk=cible.pk)).order_by("-pk").first()
    assert last is not None and last.actor_id == admin.pk
    assert "keycloak_sync_statut" in last.changes_dict

    autre = _lie(fake_keycloak)
    desactiver(autre, motif="x", by=admin)
    synchroniser_keycloak(autre.pk, by=None)
    last = LogEntry.objects.get_for_object(User.objects.get(pk=autre.pk)).order_by("-pk").first()
    assert last is not None and last.actor_id is None
    assert "keycloak_sync_statut" in last.changes_dict
