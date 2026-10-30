"""Contrat JSON du lot 6 : constat soumis avec réponse en désaccord (fixture MSW du frontend).

La forme (clés et types) de la réponse API est comparée au fichier `contrat_lot6.json`. Pour le
régénérer après une évolution volontaire de l'API : `UPDATE_CONTRAT_LOT6=1 pytest <ce fichier>`.
Le frontend recopie ce JSON dans `frontend/src/features/constats/testUtils.tsx`.
"""

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tests.accomplissement.fixtures_api import client_de
from tests.constats.fixtures_api import EquipeConstats

pytestmark = pytest.mark.django_db
GOLDEN = Path(__file__).with_name("contrat_lot6.json")
RESERVES_AUDITE = (
    "fiches_detail",
    "motif_renvoi",
    "risque_mission",
)


def forme(valeur: Any) -> Any:
    """Réduit un JSON à ses clés et à ses types (les valeurs varient d'une exécution à l'autre)."""
    if isinstance(valeur, dict):
        return {k: forme(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, list):
        return [forme(valeur[0])] if valeur else []
    if valeur is None:
        return "null"
    return type(valeur).__name__


def _desaccord(e: EquipeConstats) -> dict[str, Any]:
    audite = client_de(e.users["audite"])
    r = audite.post(
        "/api/v1/finding-responses/",
        {
            "constat": str(e.soumis.pk),
            "position": "DESACCORD",
            "commentaire": "Le contrôle existe.",
            "confirme": True,
            "empreinte_soumise": e.soumis.empreinte_soumise,
        },
        format="json",
    )
    assert r.status_code == 201, r.json()
    corps: dict[str, Any] = r.json()
    return corps


def test_contrat_constat_soumis_avec_reponse_en_desaccord(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    reponse = _desaccord(e)
    chef = client_de(e.users["chef"]).get(f"/api/v1/findings/{e.soumis.pk}/").json()
    audite = client_de(e.users["audite"]).get(f"/api/v1/findings/{e.soumis.pk}/").json()
    liste = client_de(e.users["chef"]).get(f"/api/v1/finding-responses/?constat={e.soumis.pk}")
    contrat = {
        "constat_chef": forme(chef),
        "constat_audite": forme(audite),
        "reponse": forme(reponse),
        "reponses_liste": forme(liste.json()),
    }
    if os.environ.get("UPDATE_CONTRAT_LOT6"):
        GOLDEN.write_text(json.dumps(contrat, indent=2, ensure_ascii=False) + "\n", "utf-8")
    assert contrat == json.loads(GOLDEN.read_text("utf-8"))
    assert chef["derniere_reponse"]["position"] == "DESACCORD"
    assert chef["reponse_cycle_courant"] is True
    assert chef["derniere_reponse"]["version_anterieure"] is False
    assert audite["actions_possibles"] == ["REPONDRE"]


def test_audite_ne_recoit_aucun_champ_interne(equipe_constats: EquipeConstats) -> None:
    e = equipe_constats
    audite = client_de(e.users["audite"]).get(f"/api/v1/findings/{e.soumis.pk}/").json()
    for champ in RESERVES_AUDITE:
        assert audite[champ] is None, champ
