import pytest

from apps.analyse.models import DescriptionProcessus
from apps.analyse.services.descriptions import enregistrer_description, retirer_description
from apps.core.exceptions import RegleMetierError
from apps.missions.exceptions import EtapeCloseError
from apps.missions.models import Mission, StatutEtape
from apps.users.models import User
from tests.factories import ProcessusFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_cree_puis_met_a_jour(mission_en_analyse: Mission, chef: User) -> None:
    p = mission_en_analyse.processus.first()
    d1 = enregistrer_description(
        mission_en_analyse,
        processus=p,
        by=chef,
        description="Achats.",
        categories_objectifs=["CONFORMITE", "CONFORMITE", "OPERATIONNELS"],
    )
    assert d1.categories_objectifs == ["CONFORMITE", "OPERATIONNELS"]
    d2 = enregistrer_description(mission_en_analyse, processus=p, by=chef, objectifs="Livrer.")
    assert d1.pk == d2.pk
    assert d2.description == "Achats."
    assert d2.objectifs == "Livrer."
    retirer_description(d2, by=chef)
    assert not DescriptionProcessus.objects.exists()


def test_description_processus_hors_mission_refuse(mission_en_analyse: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        enregistrer_description(mission_en_analyse, processus=ProcessusFactory(), by=chef)
    assert exc.value.errors["processus"] == ["Le processus doit être un processus de la mission."]


@pytest.mark.parametrize("valeur", [["INCONNUE"], "CONFORMITE", ["CONFORMITE", 3]])
def test_categories_hors_choix(mission_en_analyse: Mission, chef: User, valeur: object) -> None:
    with pytest.raises(RegleMetierError) as exc:
        enregistrer_description(
            mission_en_analyse,
            processus=mission_en_analyse.processus.first(),
            by=chef,
            categories_objectifs=valeur,
        )
    assert exc.value.errors["categories_objectifs"] == ["Catégorie d'objectifs inconnue."]


def test_typologie_invalide(mission_en_analyse: Mission, chef: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        enregistrer_description(
            mission_en_analyse,
            processus=mission_en_analyse.processus.first(),
            by=chef,
            typologie="XXX",
        )
    assert "typologie" in exc.value.errors


def test_champ_inconnu_refuse(mission_en_analyse: Mission, chef: User) -> None:
    with pytest.raises(ValueError, match="non modifiables"):
        enregistrer_description(
            mission_en_analyse,
            processus=mission_en_analyse.processus.first(),
            by=chef,
            mission_id=1,
        )


def test_fenetre_iii(mission_en_analyse: Mission, chef: User) -> None:
    p = mission_en_analyse.processus.first()
    forcer_etapes(mission_en_analyse, {3: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError) as exc:
        enregistrer_description(mission_en_analyse, processus=p, by=chef)
    assert exc.value.message == "Commencez l'étape III pour documenter la prise de connaissance."
    forcer_etapes(mission_en_analyse, {3: StatutEtape.TERMINEE})
    with pytest.raises(EtapeCloseError):
        enregistrer_description(mission_en_analyse, processus=p, by=chef)
