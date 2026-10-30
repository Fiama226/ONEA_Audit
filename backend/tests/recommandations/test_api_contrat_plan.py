"""Contrat JSON du plan d'actions : synthèse et action (fixtures MSW du frontend, lot 7 T14).

La forme (clés et types) des réponses est comparée au fichier `contrat_plan.json`. Pour le
régénérer après une évolution volontaire de l'API : `UPDATE_CONTRAT_PLAN=1 pytest <ce fichier>`.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests.accomplissement.fixtures_api import client_de
from tests.recommandations.fixtures_api import (
    ACTIONS,
    ENGAGEMENTS,
    SYNTHESE,
    EquipePlan,
    equipe_plan,
)

# ruff: noqa: F811, F401
pytestmark = pytest.mark.django_db
GOLDEN = Path(__file__).with_name("contrat_plan.json")


def forme(valeur: Any) -> Any:
    """Réduit un JSON à ses clés et à ses types (les valeurs varient d'une exécution à l'autre)."""
    if isinstance(valeur, dict):
        return {k: forme(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, list):
        return [forme(valeur[0])] if valeur else []
    if valeur is None:
        return "null"
    return type(valeur).__name__


def test_contrat_plan(equipe_plan: EquipePlan) -> None:
    e = equipe_plan
    audite = client_de(e.users["audite_a"])
    rai = client_de(e.users["rai"])
    audite.post(ENGAGEMENTS, {"mission": str(e.mission.pk), "confirme": True}, format="json")
    synthese = rai.get(f"{SYNTHESE}?mission={e.mission.pk}").json()
    action = rai.get(f"{ACTIONS}{e.action_resp.pk}/").json()
    liste = rai.get(f"{ACTIONS}?mission={e.mission.pk}").json()
    texte = audite.get(f"{ENGAGEMENTS}texte/?mission={e.mission.pk}").json()
    engagements = rai.get(f"{ENGAGEMENTS}?mission={e.mission.pk}").json()
    contrat = {
        "synthese": forme(synthese),
        "action": forme(action),
        "actions_liste": forme(liste),
        "texte_engagement": forme(texte),
        "engagements_liste": forme(engagements),
    }
    assert action["actions_possibles"] == ["MODIFIER", "SUPPRIMER"]
    if os.environ.get("UPDATE_CONTRAT_PLAN"):
        GOLDEN.write_text(json.dumps(contrat, indent=2, ensure_ascii=False) + "\n", "utf-8")
    assert contrat == json.loads(GOLDEN.read_text("utf-8"))
