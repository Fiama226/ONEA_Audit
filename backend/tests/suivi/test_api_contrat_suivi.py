# ruff: noqa: F811, F401, F403
"""Contrat JSON du suivi (fixtures MSW du frontend, lot 8 T12).

La forme (clés et types) des réponses est comparée au fichier `contrat_suivi.json`. Pour le
régénérer après une évolution volontaire de l'API : `UPDATE_CONTRAT_SUIVI=1 pytest <ce fichier>`.
Les valeurs exactes sont figées pour une action VERIFIEE dont un report a été refusé.
"""

import datetime
import json
import os
from pathlib import Path
from typing import Any

import pytest

from apps.suivi.services import preuves
from tests.accomplissement.fixtures_api import client_de
from tests.suivi.fixtures_api import *
from tests.suivi.fixtures_api import ACTIONS, PDF, PREUVES, RECOMMANDATIONS, REPORTS, EquipeSuivi

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("stockage_temp")]
GOLDEN = Path(__file__).with_name("contrat_suivi.json")


def forme(valeur: Any) -> Any:
    """Réduit un JSON à ses clés et à ses types (les valeurs varient d'une exécution à l'autre)."""
    if isinstance(valeur, dict):
        return {k: forme(v) for k, v in sorted(valeur.items())}
    if isinstance(valeur, list):
        return [forme(valeur[0])] if valeur else []
    if valeur is None:
        return "null"
    return type(valeur).__name__


def _post(e: EquipeSuivi, qui: str, url: str, corps: dict[str, Any]) -> Any:
    reponse = client_de(e.users[qui]).post(url, corps, format="json")
    assert reponse.status_code in (200, 201), (url, reponse.content)
    return reponse.json()


def test_contrat_suivi(equipe_suivi: EquipeSuivi) -> None:
    from django.core.files.uploadedfile import SimpleUploadedFile

    e = equipe_suivi
    verifiee, en_attente = e.suivis[0], e.suivis[1]
    rai = client_de(e.users["rai"])
    # action VERIFIEE, avec une demande de report refusée
    demande = _post(
        e,
        "responsable",
        REPORTS,
        {
            "action": str(verifiee.pk),
            "nouvelle_echeance": (verifiee.echeance + datetime.timedelta(days=30)).isoformat(),
            "motif": "Marché retardé.",
        },
    )
    refusee = _post(e, "rai", f"{REPORTS}{demande['id']}/refuse/", {"commentaire": "Trop long."})
    preuve = preuves.deposer_preuve(
        verifiee,
        fichier=SimpleUploadedFile("pv.pdf", PDF),
        libelle="PV de mise en place",
        by=e.users["responsable"],
    )
    _post(e, "responsable", f"{ACTIONS}{verifiee.pk}/declare-done/", {"commentaire": "Fait."})
    _post(e, "auditeur", f"{ACTIONS}{verifiee.pk}/verify/", {"commentaire": "Conforme."})
    action = rai.get(f"{ACTIONS}{verifiee.pk}/").json()
    assert action["statut"] == "VERIFIEE"
    assert action["actions_possibles"] == [
        "REJETER",
        "CLOTURER",
        "COMMENTER",
        "CHANGER_RESPONSABLE",
    ]
    assert refusee["statut"] == "REFUSEE"
    # action à lancer avec une demande de report en attente (forme du bloc imbriqué)
    _post(
        e,
        "responsable",
        REPORTS,
        {
            "action": str(en_attente.pk),
            "nouvelle_echeance": (en_attente.echeance + datetime.timedelta(days=15)).isoformat(),
            "motif": "Délai.",
        },
    )
    avec_report = rai.get(f"{ACTIONS}{en_attente.pk}/").json()
    assert avec_report["demande_report_en_attente"]["statut"] == "EN_ATTENTE"
    contrat = {
        "action_verifiee": forme(action),
        "action_avec_report_en_attente": forme(avec_report),
        "actions_liste": forme(rai.get(ACTIONS).json()),
        "evenements": forme(rai.get(f"{ACTIONS}{verifiee.pk}/events/").json()),
        "demande_report_refusee": forme(refusee),
        "reports_liste": forme(rai.get(REPORTS).json()),
        "preuve": forme(rai.get(f"{PREUVES}{preuve.pk}/").json()),
        "preuves_liste": forme(rai.get(PREUVES, {"action": str(verifiee.pk)}).json()),
        "registre_ligne": forme(rai.get(RECOMMANDATIONS).json()),
        "erreur": forme(rai.post(f"{ACTIONS}{verifiee.pk}/reject/", {}, format="json").json()),
    }
    # valeurs exactes de la demande refusée
    assert refusee["motif"] == "Marché retardé."
    assert refusee["commentaire_decision"] == "Trop long."
    assert refusee["actions_possibles"] == []
    if os.environ.get("UPDATE_CONTRAT_SUIVI"):
        GOLDEN.write_text(json.dumps(contrat, indent=2, ensure_ascii=False) + "\n", "utf-8")
    assert contrat == json.loads(GOLDEN.read_text("utf-8"))
