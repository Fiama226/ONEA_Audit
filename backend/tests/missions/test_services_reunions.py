from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError, MissionFigeeError
from apps.missions.models import Mission, StatutEtape, StatutMission, TypeReunion
from apps.missions.services.reunions import (
    creer_reunion,
    marquer_reunion_tenue,
    modifier_reunion,
    supprimer_reunion,
)
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def futur() -> datetime:
    return timezone.now() + timedelta(days=5)


def test_reunion_unique_par_type(mission_lancee: Mission, rai: User, audite_affecte: User) -> None:
    reunion = creer_reunion(
        mission_lancee,
        type=TypeReunion.OUVERTURE,
        date=futur(),
        by=rai,
        participants=[audite_affecte],
        lieu="Salle A",
    )
    assert list(reunion.participants.all()) == [audite_affecte]
    with pytest.raises(RegleMetierError) as exc:
        creer_reunion(mission_lancee, type=TypeReunion.OUVERTURE, date=futur(), by=rai)
    assert exc.value.errors["type"] == ["Cette réunion existe déjà pour la mission."]


def test_reunion_tenue_exige_compte_rendu_et_date_passee(
    mission_lancee: Mission, rai: User
) -> None:
    reunion = creer_reunion(
        mission_lancee,
        type=TypeReunion.OUVERTURE,
        date=futur(),
        by=rai,
    )
    with pytest.raises(RegleMetierError) as exc:
        marquer_reunion_tenue(reunion, by=rai)
    assert exc.value.errors["compte_rendu"] == [
        "Saisissez le compte rendu avant de marquer la réunion comme tenue."
    ]
    reunion = modifier_reunion(reunion, by=rai, compte_rendu="Points abordés.")
    with pytest.raises(RegleMetierError) as exc:
        marquer_reunion_tenue(reunion, by=rai)
    assert exc.value.errors["date"] == ["Une réunion à venir ne peut pas être marquée comme tenue."]
    reunion = modifier_reunion(reunion, by=rai, date=timezone.now() - timedelta(hours=1))
    assert marquer_reunion_tenue(reunion, by=rai).tenue_le is not None


def test_reunion_ouverture_gelee_apres_II(mission_lancee: Mission, rai: User) -> None:
    reunion = creer_reunion(
        mission_lancee,
        type=TypeReunion.OUVERTURE,
        date=futur(),
        by=rai,
    )
    forcer_etapes(mission_lancee, {2: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        modifier_reunion(reunion, by=rai, lieu="Ailleurs")
    with pytest.raises(EtapeCloseError):
        supprimer_reunion(reunion, by=rai)
    # La réunion de lancement (étape XI) reste modifiable.
    creer_reunion(mission_lancee, type=TypeReunion.LANCEMENT, date=futur(), by=rai)


def test_reunion_refusee_hors_statut_de_travaux(mission_lancee: Mission, rai: User) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.BROUILLON)
    with pytest.raises(RegleMetierError) as exc:
        creer_reunion(mission_lancee, type=TypeReunion.OUVERTURE, date=futur(), by=rai)
    assert exc.value.message == "Les travaux commencent une fois la mission planifiée."
    Mission.objects.filter(pk=mission_lancee.pk).update(statut=StatutMission.SUSPENDUE)
    with pytest.raises(MissionFigeeError):
        creer_reunion(mission_lancee, type=TypeReunion.OUVERTURE, date=futur(), by=rai)
