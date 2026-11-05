# ruff: noqa: F811
"""Notifications des intervenants et des audités (D5) : réunions, référentiel, constats."""

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.missions.models import Mission, StatutEtape, TypeReunion
from apps.missions.services.etapes import demarrer_etape
from apps.missions.services.reunions import creer_reunion, modifier_reunion
from apps.notifications.models import Notification
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import (  # noqa: F401
    affecter,
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)

pytestmark = pytest.mark.django_db


def _recus(user: User, type_: str) -> list[Notification]:
    return list(Notification.objects.filter(destinataire=user, type=type_))


def test_creer_reunion_convoque_les_participants_sauf_l_auteur(
    mission_lancee: Mission, chef: User, auditeur_mission: User, audite_affecte: User
) -> None:
    reunion = creer_reunion(
        mission_lancee,
        type=TypeReunion.OUVERTURE,
        date=timezone.now() + timedelta(days=3),
        by=chef,
        participants=[chef, auditeur_mission, audite_affecte],
    )
    assert len(_recus(audite_affecte, "REUNION_CONVOQUEE")) == 1
    assert len(_recus(auditeur_mission, "REUNION_CONVOQUEE")) == 1
    assert _recus(chef, "REUNION_CONVOQUEE") == []
    notification = _recus(audite_affecte, "REUNION_CONVOQUEE")[0]
    assert notification.lien == f"/missions/{mission_lancee.pk}/reunions"
    assert reunion.get_type_display().lower() in notification.message.lower()


def test_ajouter_un_participant_le_convoque_une_seule_fois(
    mission_lancee: Mission, chef: User, audite_affecte: User
) -> None:
    reunion = creer_reunion(
        mission_lancee,
        type=TypeReunion.OUVERTURE,
        date=timezone.now() + timedelta(days=3),
        by=chef,
    )
    modifier_reunion(reunion, by=chef, participants=[audite_affecte])
    modifier_reunion(reunion, by=chef, participants=[audite_affecte, chef])
    assert len(_recus(audite_affecte, "REUNION_CONVOQUEE")) == 1


def test_demarrer_vi_demande_leur_avis_aux_audites(
    mission_lancee: Mission, chef: User, audite_affecte: User
) -> None:
    forcer_etapes(mission_lancee, {n: StatutEtape.TERMINEE for n in range(1, 6)})
    demarrer_etape(mission_lancee.etapes.get(numero=6), by=chef)
    recus = _recus(audite_affecte, "REFERENTIEL_A_VALIDER")
    assert len(recus) == 1
    assert recus[0].lien.startswith(f"/missions/{mission_lancee.pk}")


def test_aucune_notification_hors_etape_vi(
    mission_lancee: Mission, chef: User, audite_affecte: User
) -> None:
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE})
    demarrer_etape(mission_lancee.etapes.get(numero=2), by=chef)
    assert _recus(audite_affecte, "REFERENTIEL_A_VALIDER") == []


def test_notifier_ignore_les_destinataires_desactives(mission_lancee: Mission, chef: User) -> None:
    inactif = make_user(Role.AUDITE)
    affecter(mission_lancee, inactif, "AUDITE")
    type(inactif).objects.filter(pk=inactif.pk).update(is_active=False)
    creer_reunion(
        mission_lancee,
        type=TypeReunion.OUVERTURE,
        date=timezone.now() + timedelta(days=3),
        by=chef,
        participants=[inactif],
    )
    assert Notification.objects.filter(destinataire=inactif).count() == 0
