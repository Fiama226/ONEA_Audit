from datetime import datetime, timedelta

import pytest
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, StatutEntretien, StatutEtape
from apps.missions.services.entretiens import (
    annuler_entretien,
    creer_entretien,
    marquer_entretien_realise,
    modifier_entretien,
    supprimer_entretien,
)
from apps.users.models import User
from tests.factories import EtapeMissionFactory, MissionFactory, make_user
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def prevue() -> datetime:
    return timezone.now() + timedelta(days=2)


def test_creer_entretien_avec_equipe(
    mission_lancee: Mission, rai: User, chef: User, audite_affecte: User
) -> None:
    etape = mission_lancee.etapes.get(numero=3)
    entretien = creer_entretien(
        mission_lancee,
        objet="Entretien DAF",
        date_prevue=prevue(),
        by=rai,
        etape=etape,
        auditeurs=[chef],
        interlocuteurs=[audite_affecte],
        duree_minutes=60,
    )
    assert entretien.statut == StatutEntretien.PLANIFIE
    assert list(entretien.auditeurs.all()) == [chef]
    assert list(entretien.interlocuteurs.all()) == [audite_affecte]


def test_entretien_auditeur_hors_equipe_refuse(
    mission_lancee: Mission, rai: User, audite_affecte: User
) -> None:
    for intrus in (make_user(), audite_affecte):
        with pytest.raises(RegleMetierError) as exc:
            creer_entretien(
                mission_lancee,
                objet="X",
                date_prevue=prevue(),
                by=rai,
                auditeurs=[intrus],
            )
        assert exc.value.errors["auditeurs"] == [
            "Les auditeurs doivent faire partie de l'équipe de la mission."
        ]


def test_entretien_etape_d_une_autre_mission_refuse(mission_lancee: Mission, rai: User) -> None:
    autre = MissionFactory()
    etrangere = EtapeMissionFactory(mission=autre, numero=3)
    with pytest.raises(RegleMetierError) as exc:
        creer_entretien(
            mission_lancee,
            objet="X",
            date_prevue=prevue(),
            by=rai,
            etape=etrangere,
        )
    assert "etape" in exc.value.errors
    entretien = creer_entretien(mission_lancee, objet="X", date_prevue=prevue(), by=rai)
    with pytest.raises(RegleMetierError) as exc:
        modifier_entretien(entretien, by=rai, etape=etrangere)
    assert "etape" in exc.value.errors


def test_entretien_realise_exige_compte_rendu(mission_lancee: Mission, rai: User) -> None:
    entretien = creer_entretien(mission_lancee, objet="X", date_prevue=prevue(), by=rai)
    with pytest.raises(RegleMetierError) as exc:
        marquer_entretien_realise(entretien, by=rai)
    assert "compte_rendu" in exc.value.errors
    entretien = modifier_entretien(entretien, by=rai, compte_rendu="Échanges.", note_synthese="RAS")
    entretien = marquer_entretien_realise(entretien, by=rai)
    assert entretien.statut == StatutEntretien.REALISE
    assert entretien.realise_le is not None


def test_annuler_entretien(mission_lancee: Mission, rai: User) -> None:
    entretien = creer_entretien(mission_lancee, objet="X", date_prevue=prevue(), by=rai)
    with pytest.raises(RegleMetierError) as exc:
        annuler_entretien(entretien, motif=" ", by=rai)
    assert exc.value.errors["motif"] == ["Le motif est obligatoire."]
    entretien = annuler_entretien(entretien, motif="Indisponible", by=rai)
    assert entretien.statut == StatutEntretien.ANNULE
    with pytest.raises(RegleMetierError):
        modifier_entretien(entretien, by=rai, lieu="Salle")


def test_entretien_gele_quand_l_etape_rattachee_est_close(
    mission_lancee: Mission, rai: User
) -> None:
    etape = mission_lancee.etapes.get(numero=3)
    entretien = creer_entretien(
        mission_lancee,
        objet="X",
        date_prevue=prevue(),
        by=rai,
        etape=etape,
    )
    forcer_etapes(mission_lancee, {3: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        modifier_entretien(entretien, by=rai, lieu="Salle")
    with pytest.raises(EtapeCloseError):
        supprimer_entretien(entretien, by=rai)


def test_duree_hors_bornes(mission_lancee: Mission, rai: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        creer_entretien(
            mission_lancee,
            objet="X",
            date_prevue=prevue(),
            by=rai,
            duree_minutes=700,
        )
    assert "duree_minutes" in exc.value.errors
