# ruff: noqa: F811, F401
"""Contrat JSON de la communication (fixtures MSW du frontend, lot 7 T13 à T15).

La forme (clés et types) des réponses est comparée au fichier `contrat_lot7.json`. Pour le
régénérer après une évolution volontaire de l'API : `UPDATE_CONTRAT_LOT7=1 pytest <ce fichier>`.
Le contrat du lot 7 est GELÉ à la fin de la tâche 11 : toute évolution est une décision de revue.
"""

import json
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest

from apps.communication.models import Rapport, RapportProvisoire
from apps.constats.models import Constat
from apps.users.models import User
from tests.accomplissement.fixtures_api import client_de
from tests.communication.fixtures_api import RAPPORTS, REPONSES, EquipeRapport, equipe
from tests.communication.support_provisoire import (  # noqa: F401
    affecter,
    audite_affecte,
    audite_entite_a,
    audite_entite_b,
    auditeur_mission,
    aujourd_hui_le,
    chef,
    constat_a,
    constat_b,
    mission_en_xiv,
    mission_lancee,
    mission_xv,
    provisoire_transmis,
    rapport_xv,
)
from tests.communication.support_t8 import (
    admin,
    creer_version,
    dg,
    rapport_soumis_reel,
    rapport_valide,
    signataire_factice,
)
from tests.communication.test_api_provisoire import _corps, equipe_xv

pytestmark = pytest.mark.django_db
GOLDEN = Path(__file__).with_name("contrat_lot7.json")


def forme(valeur: Any) -> Any:
    """Réduit un JSON à ses clés et à ses types (les valeurs varient d'une exécution à l'autre)."""
    if isinstance(valeur, dict):
        return {k: forme(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, list):
        return [forme(valeur[0])] if valeur else []
    if valeur is None:
        return "null"
    return type(valeur).__name__


def comparer(partie: str, contrat: dict[str, Any]) -> None:
    complet: dict[str, Any] = json.loads(GOLDEN.read_text("utf-8")) if GOLDEN.exists() else {}
    if os.environ.get("UPDATE_CONTRAT_LOT7"):
        complet[partie] = contrat
        GOLDEN.write_text(json.dumps(complet, indent=2, ensure_ascii=False) + "\n", "utf-8")
    assert contrat == complet[partie]


def test_contrat_rapport_soumis(equipe: EquipeRapport, rapport_soumis_reel: Rapport) -> None:
    rai = client_de(equipe.users["rai"])
    url = f"{RAPPORTS}{rapport_soumis_reel.pk}/"
    rapport = rai.get(url).json()
    assert rapport["statut"] == "SOUMIS" and rapport["actions_possibles"] == ["VALIDER", "RENVOYER"]
    comparer(
        "rapport_soumis",
        {
            "rapport": forme(rapport),
            "liste": forme(rai.get(f"{RAPPORTS}?mission={equipe.mission.pk}").json()),
            "texte_validation": forme(rai.get(f"{url}validation-text/").json()),
        },
    )


def test_contrat_provisoire_et_reponses(
    equipe_xv: EquipeRapport,
    provisoire_transmis: RapportProvisoire,
    constat_a: Constat,
    constat_b: Constat,
    aujourd_hui_le,  # type: ignore[no-untyped-def]
) -> None:
    e = equipe_xv
    texte = client_de(e.users["audite_a"]).get(
        f"{REPONSES}texte/?provisoire={provisoire_transmis.pk}&constat={constat_a.pk}"
    )
    dans_les_delais = client_de(e.users["audite_a"]).post(
        REPONSES, _corps(provisoire_transmis, constat_a), format="json"
    )
    aujourd_hui_le(provisoire_transmis.date_limite_reponses + timedelta(days=2))
    hors_delai = client_de(e.users["audite_b"]).post(
        REPONSES, _corps(provisoire_transmis, constat_b), format="json"
    )
    assert (dans_les_delais.json()["hors_delai"], hors_delai.json()["hors_delai"]) == (False, True)
    chef = client_de(e.users["chef"])
    liste = chef.get(f"{REPONSES}?provisoire={provisoire_transmis.pk}").json()
    assert liste["count"] == 2
    comparer(
        "provisoire",
        {
            "provisoire": forme(
                chef.get(f"/api/v1/draft-reports/{provisoire_transmis.pk}/").json()
            ),
            "provisoire_audite": forme(
                client_de(e.users["audite_a"])
                .get(f"/api/v1/draft-reports/{provisoire_transmis.pk}/")
                .json()
            ),
            "reponse": forme(dans_les_delais.json()),
            "reponses": forme(liste),
            "texte_reponse": forme(texte.json()),
        },
    )


def test_contrat_rapport_diffuse_vu_par_le_dg(
    equipe: EquipeRapport, rapport_valide: Rapport
) -> None:
    creer_version(rapport_valide)
    creer_version(rapport_valide, "NOTE_SYNTHETIQUE")
    rai = client_de(equipe.users["rai"])
    diffuse = rai.post(
        f"{RAPPORTS}{rapport_valide.pk}/distribute/", {"message": "Info."}, format="json"
    )
    assert diffuse.status_code == 200
    dg = client_de(equipe.users["dg"])
    vu = dg.get(f"{RAPPORTS}{rapport_valide.pk}/").json()
    assert vu["actions_possibles"] == ["ACCUSER_RECEPTION"]
    comparer(
        "rapport_diffuse_dg",
        {
            "rapport": forme(vu),
            "liste": forme(dg.get(RAPPORTS).json()),
            "rapport_interne_diffuse": forme(rai.get(f"{RAPPORTS}{rapport_valide.pk}/").json()),
            "destinataires": forme(
                rai.get(f"/api/v1/report-recipients/?rapport={rapport_valide.pk}").json()
            ),
        },
    )
