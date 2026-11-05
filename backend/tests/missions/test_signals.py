from typing import Any

import pytest

from apps.missions.models import EtapeMission, Mission, StatutEtape
from apps.missions.services.etapes import demarrer_etape
from apps.missions.signals import etape_changee
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_signal_emis_par_transition(mission_lancee: Mission, chef: User) -> None:
    recus: list[dict[str, Any]] = []

    def recepteur(sender: Any, etape: EtapeMission, evenement: Any, par: User, **kw: Any) -> None:
        recus.append(
            {
                "sender": sender,
                "numero": etape.numero,
                "type": evenement.type,
                "evenement_etape": evenement.etape_id,
                "par": par.pk,
                **kw,
            }
        )

    forcer_etapes(mission_lancee, {1: "TERMINEE", 2: "TERMINEE", 4: "TERMINEE"})
    etape_changee.connect(recepteur, weak=False)
    try:
        demarrer_etape(mission_lancee.etapes.get(numero=3), by=chef)
        demarrer_etape(mission_lancee.etapes.get(numero=5), by=chef)
    finally:
        etape_changee.disconnect(recepteur)
    assert [(r["numero"], r["type"], r["par"]) for r in recus] == [
        (3, "DEMARREE", chef.pk),
        (5, "DEMARREE", chef.pk),
    ]
    assert all(r["sender"] is EtapeMission for r in recus)
    assert all(r["evenement_etape"] for r in recus)
    assert [(r["type_evenement"], r["motif"], r["statut_avant"]) for r in recus] == [
        ("DEMARREE", "", StatutEtape.A_FAIRE),
        ("DEMARREE", "", StatutEtape.A_FAIRE),
    ]


def test_exception_du_recepteur_annule_la_transition(mission_lancee: Mission, chef: User) -> None:
    def recepteur(**_: Any) -> None:
        raise RuntimeError("boom")

    forcer_etapes(mission_lancee, {1: "TERMINEE", 2: "TERMINEE"})
    etape_changee.connect(recepteur, weak=False)
    try:
        with pytest.raises(RuntimeError):
            demarrer_etape(mission_lancee.etapes.get(numero=3), by=chef)
    finally:
        etape_changee.disconnect(recepteur)
    etape = mission_lancee.etapes.get(numero=3)
    assert etape.statut != StatutEtape.EN_COURS
    assert not etape.evenements.exists()
