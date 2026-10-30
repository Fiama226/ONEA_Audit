# ruff: noqa: F811
import logging
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied

from apps.communication.models import EvenementRapport, Rapport, RapportProvisoire
from apps.communication.services import provisoire as service
from apps.communication.services.provisoire import provisoire_courant, transmettre_provisoire
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, Reunion, StatutEtape
from apps.signatures.services import empreinte
from apps.users.models import User
from tests.communication.factories import RapportFactory
from tests.communication.support_provisoire import (  # noqa: F401
    affecter,
    audite_affecte,
    audite_entite_a,
    audite_entite_b,
    auditeur_mission,
    aujourd_hui_le,
    chef,
    constat_a,
    constat_b,
    mission_en_xiv,
    mission_lancee,
    mission_xv,
    mission_xv_vide,
    provisoire_transmis,
    rapport_xv,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_transmission_fige_l_instantane(rapport_xv: Rapport, chef: User) -> None:
    p = transmettre_provisoire(rapport_xv, by=chef, delai_jours=10)
    assert p.numero == 1 and p.transmis_par == chef
    assert [c["reference"] for c in p.instantane["constats"]]
    assert p.empreinte == empreinte("rapport_provisoire", p.instantane)
    assert all(c["reponse_direction"] is None for c in p.instantane["constats"])
    assert (p.date_limite_reponses - p.transmis_le.date()) <= timedelta(days=10)
    evenement = EvenementRapport.objects.get(rapport=rapport_xv, type="PROVISOIRE_TRANSMIS")
    assert evenement.par == chef
    assert provisoire_courant(rapport_xv) == p


def test_transmission_par_le_rai(rapport_xv: Rapport, rai: User) -> None:
    assert transmettre_provisoire(rapport_xv, by=rai).numero == 1


def test_transmission_refusee_hors_chef_ou_rai(
    rapport_xv: Rapport, auditeur_mission: User, audite_entite_a: User
) -> None:
    for user in (auditeur_mission, audite_entite_a):
        with pytest.raises(PermissionDenied):
            transmettre_provisoire(rapport_xv, by=user)


@pytest.mark.parametrize("delai", [0, 61])
def test_delai_borne(rapport_xv: Rapport, chef: User, delai: int) -> None:
    with pytest.raises(RegleMetierError):
        transmettre_provisoire(rapport_xv, by=chef, delai_jours=delai)


def test_transmission_exige_reunion_tenue(rapport_xv: Rapport, chef: User) -> None:
    Reunion.objects.filter(mission=rapport_xv.mission).update(tenue_le=None)
    with pytest.raises(RegleMetierError) as exc:
        transmettre_provisoire(rapport_xv, by=chef)
    assert exc.value.message == (
        "Tenez la réunion de clôture avant de transmettre le rapport provisoire."
    )


def test_transmission_exige_un_constat_valide(mission_xv_vide: Mission, chef: User) -> None:
    rapport = RapportFactory(mission=mission_xv_vide)
    with pytest.raises(RegleMetierError) as exc:
        transmettre_provisoire(rapport, by=chef)
    assert exc.value.message == (
        "Aucun constat validé : il n'y a pas de rapport provisoire à transmettre."
    )


def test_transmission_refusee_xv_close(rapport_xv: Rapport, chef: User) -> None:
    forcer_etapes(rapport_xv.mission, {15: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        transmettre_provisoire(rapport_xv, by=chef)


def test_transmission_mail_aux_audites(
    rapport_xv: Rapport,
    chef: User,
    audite_entite_a: User,
    audite_entite_b: User,
    mailoutbox: list,  # type: ignore[type-arg]
    django_capture_on_commit_callbacks,  # type: ignore[no-untyped-def]
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        transmettre_provisoire(rapport_xv, by=chef)
    destinataires = {m.to[0] for m in mailoutbox}
    assert {audite_entite_a.email, audite_entite_b.email} <= destinataires
    assert all(not m.attachments for m in mailoutbox)
    assert all(rapport_xv.mission.reference in m.subject for m in mailoutbox)


def test_transmission_echec_generation_non_bloquant(
    rapport_xv: Rapport,
    chef: User,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    django_capture_on_commit_callbacks,  # type: ignore[no-untyped-def]
) -> None:
    def echec(**_: object) -> None:
        raise RegleMetierError("Gabarit absent.")

    monkeypatch.setattr("apps.documents.services.generation.demander_generation", echec)
    with caplog.at_level(logging.WARNING), django_capture_on_commit_callbacks(execute=True):
        p = transmettre_provisoire(rapport_xv, by=chef)
    assert RapportProvisoire.objects.filter(pk=p.pk).exists()
    assert "impossible" in caplog.text


def test_generation_demandee_apres_validation(
    rapport_xv: Rapport,
    chef: User,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks,  # type: ignore[no-untyped-def]
) -> None:
    appels: list[dict[str, object]] = []
    monkeypatch.setattr(
        "apps.documents.services.generation.demander_generation",
        lambda **kw: appels.append(kw),
    )
    with django_capture_on_commit_callbacks(execute=True):
        p = transmettre_provisoire(rapport_xv, by=chef)
    assert appels == [{"type_document": "RAPPORT_PROVISOIRE", "objet_id": p.pk, "by": chef}]


def test_retransmission_tant_que_XV_ouverte(
    rapport_xv: Rapport,
    chef: User,
    aujourd_hui_le,  # noqa: F811
) -> None:
    from datetime import date

    aujourd_hui_le(date(2026, 11, 1))
    premier = transmettre_provisoire(rapport_xv, by=chef, delai_jours=10)
    aujourd_hui_le(date(2026, 11, 5))
    second = transmettre_provisoire(rapport_xv, by=chef, delai_jours=10)
    assert second.numero == 2
    assert provisoire_courant(rapport_xv) == second
    assert second.date_limite_reponses > premier.date_limite_reponses
    assert service.RapportProvisoire.objects.filter(rapport=rapport_xv).count() == 2


def test_rapport_d_une_autre_mission_refuse(
    rapport_xv: Rapport,
    chef: User,
    mission_lancee: Mission,  # noqa: F811
) -> None:
    autre = RapportFactory()
    with pytest.raises(PermissionDenied):
        transmettre_provisoire(autre, by=chef)
