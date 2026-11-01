"""Équipe complète et routes pour les tests de l'API du suivi (lot 8, T10)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from apps.missions.models import Mission, RoleMission
from apps.suivi.models import SuiviAction
from apps.users.models import Role, User
from config.documents_settings import configuration_stockage
from tests.factories import make_user
from tests.missions.conftest import (  # noqa: F401
    affecter,
    audite_affecte,
    auditeur_mission,
    chef,
    mission_lancee,
)
from tests.suivi.conftest import mission_en_suivi, responsable  # noqa: F401

BASE = "/api/v1/follow-up"
ACTIONS = f"{BASE}/actions/"
RECOMMANDATIONS = f"{BASE}/recommendations/"
PREUVES = f"{BASE}/evidence/"
REPORTS = f"{BASE}/extension-requests/"
MISSIONS = f"{BASE}/missions/"

PDF = b"%PDF-1.7\n" + b"x" * 500

__all__ = [
    "ACTIONS",
    "audite_affecte",
    "auditeur_mission",
    "chef",
    "mission_en_suivi",
    "mission_lancee",
    "responsable",
    "MISSIONS",
    "PDF",
    "PREUVES",
    "RECOMMANDATIONS",
    "REPORTS",
    "EquipeSuivi",
    "equipe_suivi",
    "stockage_temp",
]


@dataclass
class EquipeSuivi:
    mission: Mission
    users: dict[str, User]

    @property
    def suivis(self) -> list[SuiviAction]:
        return list(SuiviAction.objects.filter(mission=self.mission).order_by("action__numero"))

    @property
    def suivi(self) -> SuiviAction:
        return self.suivis[0]


@pytest.fixture
def stockage_temp(settings: Any, tmp_path: Path) -> Path:
    racine = tmp_path / "documents"
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(racine)}
        ),
    }
    return racine


@pytest.fixture
def equipe_suivi(
    mission_en_suivi: Mission,
    chef: User,
    auditeur_mission: User,
    responsable: User,
    audite_affecte: User,
    rai: User,
    dg: User,
    admin: User,
) -> EquipeSuivi:
    superviseur = make_user(Role.AUDITEUR)
    affecter(mission_en_suivi, superviseur, RoleMission.SUPERVISEUR)
    non_leve = make_user(Role.AUDITEUR)
    affecter(mission_en_suivi, non_leve, RoleMission.AUDITEUR, confirmee=False)
    users = {
        "rai": rai,
        "chef": chef,
        "superviseur": superviseur,
        "auditeur": auditeur_mission,
        "auditeur_non_leve": non_leve,
        "responsable": responsable,
        "audite": audite_affecte,
        "dg": dg,
        "admin": admin,
        "non_affecte": make_user(Role.AUDITEUR),
        "audite_non_affecte": make_user(Role.AUDITE),
    }
    return EquipeSuivi(mission_en_suivi, users)
