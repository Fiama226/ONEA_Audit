import pytest
from django.utils import timezone

from apps.missions.models import Mission, StatutEtape, TypeReunion
from apps.missions.services.etapes import rouvrir_etape
from apps.missions.services.livrables import CONTROLES, livrables_manquants
from apps.signatures.models import TypeDocumentSignable
from apps.users.models import User
from tests.factories import (
    ConfirmationFactory,
    EntretienFactory,
    ReunionFactory,
    RisqueMissionFactory,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_controles_enregistres_pour_I_II_IV_XI() -> None:
    assert sorted(CONTROLES) == [1, 2, 4, 11]


def test_etape_I_exige_l_ordre_de_mission(mission_lancee: Mission) -> None:
    etape = mission_lancee.etapes.get(numero=1)
    assert livrables_manquants(etape) == ["L'ordre de mission n'a pas été émis."]
    Mission.objects.filter(pk=mission_lancee.pk).update(ordre_mission_emis_le=timezone.now())
    assert livrables_manquants(mission_lancee.etapes.get(numero=1)) == []


def test_etape_II_et_XI(mission_lancee: Mission) -> None:
    ii = mission_lancee.etapes.get(numero=2)
    xi = mission_lancee.etapes.get(numero=11)
    assert livrables_manquants(xi) == ["La réunion de lancement n'est pas marquée comme tenue."]
    ReunionFactory(mission=mission_lancee, type=TypeReunion.OUVERTURE)  # pas tenue
    EntretienFactory(mission=mission_lancee)
    assert livrables_manquants(ii) == ["La réunion d'ouverture n'est pas marquée comme tenue."]


def test_etape_IV_exige_un_risque(mission_lancee: Mission) -> None:
    etape = mission_lancee.etapes.get(numero=4)
    assert livrables_manquants(etape) == ["Aucun risque n'est sélectionné pour la mission."]
    RisqueMissionFactory(mission=mission_lancee)
    assert livrables_manquants(etape) == []


@pytest.mark.parametrize(
    ("numero", "romain", "lot"),
    [(3, "III", 5), (7, "VII", 5), (8, "VIII", 6), (14, "XIV", 6), (17, "XVII", 7)],
)
def test_etapes_gerees_dans_un_lot_ulterieur(
    mission_lancee: Mission, numero: int, romain: str, lot: int
) -> None:
    etape = mission_lancee.etapes.get(numero=numero)
    assert livrables_manquants(etape) == [
        f"Les livrables de l'étape {romain} sont gérés à partir du lot {lot}."
    ]


def test_etape_I_rouverte_exige_une_nouvelle_emission(mission_lancee: Mission, rai: User) -> None:
    Mission.objects.filter(pk=mission_lancee.pk).update(ordre_mission_emis_le=timezone.now())
    forcer_etapes(mission_lancee, {1: StatutEtape.TERMINEE})
    rouvrir_etape(mission_lancee.etapes.get(numero=1), motif="Périmètre revu", by=rai)
    etape = mission_lancee.etapes.get(numero=1)
    assert livrables_manquants(etape) == ["L'ordre de mission n'a pas été émis."]
    ConfirmationFactory(objet=mission_lancee, type_document=TypeDocumentSignable.ORDRE_MISSION)
    assert livrables_manquants(etape) == []
