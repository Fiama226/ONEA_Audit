"""Shared helpers of the mission document type tests (mission order and opening minutes)."""

from typing import Any

import pytest

from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import type_document
from apps.documents.services.gabarits import activer_gabarit, deposer_gabarit
from apps.missions.models import Mission
from apps.missions.services.missions import emettre_ordre_mission, modifier_mission
from apps.users.models import User

COMMUN_X: dict[str, Any] = {
    "onea": {"nom": "x", "sigle": "x", "departement": "x"},
    "document": {"numero": "x", "version": "1", "type": "x", "genere_le": "x", "genere_par": "x"},
}


def installer_provisoire(code: str, by: User) -> None:
    gabarit = deposer_gabarit(
        type_document=code,
        contenu=construire_gabarit_provisoire(type_document(code)),
        nom_original=f"provisoire-{code.lower()}.docx",
        by=by,
        provisoire=True,
    )
    activer_gabarit(gabarit, by=by)


@pytest.fixture
def gabarits_provisoires(rai: User, pdf_factice: bytes) -> None:
    """Installs the provisional templates of both mission document types (PDF faked)."""
    installer_provisoire("ORDRE_MISSION", rai)
    installer_provisoire("PV_OUVERTURE", rai)


def emettre_ordre(mission: Mission, rai: User) -> Any:
    """Fills the required fields of the mission then issues the order (lot 3 services)."""
    modifier_mission(mission, by=rai, objectifs="O", perimetre="P")
    return emettre_ordre_mission(mission, by=rai)
