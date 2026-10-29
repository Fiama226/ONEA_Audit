import pytest

from apps.analyse.services import marc
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, RisqueMission
from apps.missions.services.etapes import terminer_etape
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db

VIDE = "La matrice d'analyse des risques et contrôles est vide."


def _manquants(mission: Mission, numero: int, chef: User) -> list[str]:
    with pytest.raises(RegleMetierError) as e:
        terminer_etape(mission.etapes.get(numero=numero), by=chef)
    return e.value.errors["livrables"]


def test_terminer_v_et_vi_livrables(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    code = risque_eleve.code_source
    assert _manquants(mission_en_analyse, 5, chef) == [
        VIDE,
        f"Risques moyens ou élevés sans contrôle analysé : {code}",
    ]
    ligne = marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    assert _manquants(mission_en_analyse, 5, chef) == [
        "Lignes de la matrice sans évaluation de la conception : 1."
    ]
    marc.modifier_ligne_marc(ligne, by=chef, controle_existant="x", evaluation="ADEQUATE")
    terminer_etape(mission_en_analyse.etapes.get(numero=5), by=chef)
    forcer_etapes(mission_en_analyse, {6: "EN_COURS"})
    terminer_etape(mission_en_analyse.etapes.get(numero=6), by=chef)
    assert mission_en_analyse.etapes.get(numero=6).statut == "TERMINEE"


def test_vi_exige_v_terminee_et_matrice(mission_en_analyse: Mission, chef: User) -> None:
    forcer_etapes(mission_en_analyse, {6: "EN_COURS"})
    assert _manquants(mission_en_analyse, 6, chef) == [
        "Terminez l'étape V avant de soumettre le référentiel d'audit.",
        VIDE,
    ]
