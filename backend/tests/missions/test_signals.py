from typing import Any

import pytest

from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services.etapes import demarrer_etape
from apps.missions.signals import etape_changee
from apps.users.models import User

pytestmark = pytest.mark.django_db


def test_signal_emis_par_transition(mission_lancee: Mission, chef: User) -> None:
    recus: list[tuple[int, str, object]] = []

    def recepteur(sender: Any, etape: EtapeMission, evenement: Any, par: User, **_: Any) -> None:
        recus.append((etape.numero, evenement.type, par.pk))

    etape_changee.connect(recepteur, weak=False)
    try:
        demarrer_etape(mission_lancee.etapes.get(numero=3), by=chef)
    finally:
        etape_changee.disconnect(recepteur)
    assert recus == [(3, "DEMARREE", chef.pk)]


def test_exception_du_recepteur_annule_la_transition(mission_lancee: Mission, chef: User) -> None:
    def recepteur(**_: Any) -> None:
        raise RuntimeError("boom")

    etape_changee.connect(recepteur, weak=False)
    try:
        with pytest.raises(RuntimeError):
            demarrer_etape(mission_lancee.etapes.get(numero=3), by=chef)
    finally:
        etape_changee.disconnect(recepteur)
    etape = mission_lancee.etapes.get(numero=3)
    assert etape.statut != StatutEtape.EN_COURS
    assert not etape.evenements.exists()
