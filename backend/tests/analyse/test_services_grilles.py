from typing import Any

import pytest

from apps.analyse.models import GrilleSeparation
from apps.analyse.services.grilles import (
    INCOMPATIBLES,
    Cumul,
    analyser_grille,
    enregistrer_grille,
    retirer_grille,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _grille(mission: Mission, chef: User, **kw: Any) -> GrilleSeparation:
    params: dict[str, Any] = {
        "processus": mission.processus.first(),
        "taches": ["Émettre le bon de commande", "Réceptionner", "Payer"],
        "acteurs": ["Acheteur", "Magasinier", "Comptable"],
        "cellules": [
            {"tache": 0, "acteur": 0, "roles": ["EXECUTE", "AUTORISE"]},
            {"tache": 1, "acteur": 1, "roles": ["EXECUTE"]},
            {"tache": 1, "acteur": 2, "roles": ["EXECUTE"]},
        ],
    }
    params.update(kw)
    return enregistrer_grille(mission, by=chef, **params)


def test_analyse_grille_cumuls_et_trous(mission_en_analyse: Mission, chef: User) -> None:
    g = _grille(mission_en_analyse, chef)
    a = analyser_grille(g)
    assert a.taches_sans_acteur == ["Payer"]
    assert a.taches_multi_executants == ["Réceptionner"]
    assert a.cumuls == [Cumul("Émettre le bon de commande", "Acheteur", ("AUTORISE", "EXECUTE"))]


def test_incompatibles_d6() -> None:
    assert frozenset({"EXECUTE", "AUTORISE"}) in INCOMPATIBLES
    assert len(INCOMPATIBLES) == 3


def test_enregistrer_grille_met_a_jour(mission_en_analyse: Mission, chef: User) -> None:
    g1 = _grille(mission_en_analyse, chef)
    g2 = _grille(mission_en_analyse, chef, taches=["Seule tâche"], cellules=[])
    assert g1.pk == g2.pk
    assert GrilleSeparation.objects.filter(mission=mission_en_analyse).count() == 1
    assert g2.taches == ["Seule tâche"]


def test_retirer_grille(mission_en_analyse: Mission, chef: User) -> None:
    g = _grille(mission_en_analyse, chef)
    retirer_grille(g, by=chef)
    assert not GrilleSeparation.objects.filter(mission=mission_en_analyse).exists()


@pytest.mark.parametrize(
    ("kw", "champ", "message"),
    [
        (
            {"cellules": [{"tache": 3, "acteur": 0, "roles": ["EXECUTE"]}]},
            "cellules",
            "Indice de tâche hors de la grille : 3.",
        ),
        (
            {"cellules": [{"tache": 0, "acteur": -1, "roles": ["EXECUTE"]}]},
            "cellules",
            "Indice d'acteur hors de la grille : -1.",
        ),
        (
            {"cellules": [{"tache": 0, "acteur": 0, "roles": ["PATRON"]}]},
            "cellules",
            "Rôle inconnu : PATRON.",
        ),
        (
            {
                "cellules": [
                    {"tache": 0, "acteur": 0, "roles": ["EXECUTE"]},
                    {"tache": 0, "acteur": 0, "roles": ["CONTROLE"]},
                ]
            },
            "cellules",
            "Cellule en double pour la tâche 0 et l'acteur 0.",
        ),
        ({"taches": ["A", "  "], "cellules": []}, "taches", "Le libellé ne peut pas être vide."),
        ({"acteurs": [""], "cellules": []}, "acteurs", "Le libellé ne peut pas être vide."),
        (
            {"taches": [f"T{i}" for i in range(101)], "cellules": []},
            "taches",
            "La grille est limitée à 100 tâches et 30 acteurs.",
        ),
        (
            {"acteurs": [f"A{i}" for i in range(31)], "cellules": []},
            "acteurs",
            "La grille est limitée à 100 tâches et 30 acteurs.",
        ),
        ({"cellules": ["x"]}, "cellules", "Cellule invalide."),
    ],
)
def test_grille_entrees_invalides(
    mission_en_analyse: Mission, chef: User, kw: dict[str, Any], champ: str, message: str
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        _grille(mission_en_analyse, chef, **kw)
    assert exc.value.errors[champ] == [message]


def test_grille_processus_hors_mission(mission_en_analyse: Mission, chef: User) -> None:
    from tests.factories import ProcessusFactory

    with pytest.raises(RegleMetierError) as exc:
        _grille(mission_en_analyse, chef, processus=ProcessusFactory())
    assert exc.value.errors["processus"] == ["Le processus doit être un processus de la mission."]


def test_grille_avant_demarrage_refusee(mission_en_analyse: Mission, chef: User) -> None:
    forcer_etapes(mission_en_analyse, {3: StatutEtape.A_FAIRE})
    with pytest.raises(RegleMetierError) as exc:
        _grille(mission_en_analyse, chef)
    assert exc.value.message == "Commencez l'étape III pour documenter la prise de connaissance."
