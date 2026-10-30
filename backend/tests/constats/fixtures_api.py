"""Équipe et constats pour les tests de l'API des constats (T8)."""

from dataclasses import dataclass

import pytest
from django.utils import timezone

from apps.constats.models import Constat
from apps.constats.services.constats import soumettre_constat
from apps.missions.models import Mission, RoleMission
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import make_user
from tests.missions.conftest import affecter


@dataclass
class EquipeConstats:
    mission: Mission
    brouillon: Constat
    soumis: Constat
    users: dict[str, User]


@pytest.fixture
def equipe_constats(
    mission_en_xiv: Mission, chef: User, auditeur_mission: User, audite_affecte: User
) -> EquipeConstats:
    Mission.objects.filter(pk=mission_en_xiv.pk).update(ordre_mission_emis_le=timezone.now())
    brouillon = ConstatFactory(mission=mission_en_xiv)
    soumis = ConstatFactory(mission=mission_en_xiv)
    soumettre_constat(soumis, by=chef)
    soumis.refresh_from_db()
    audite_affecte.direction_code = soumis.entite.code
    audite_affecte.save(update_fields=["direction_code"])
    autre_audite = make_user(Role.AUDITE, direction_code="AUTRE")
    affecter(mission_en_xiv, autre_audite, RoleMission.AUDITE)
    users = {
        "rai": make_user(Role.RAI),
        "chef": chef,
        "auditeur": auditeur_mission,
        "audite": audite_affecte,
        "autre_audite": autre_audite,
        "non_affecte": make_user(Role.AUDITEUR),
        "audite_non_affecte": make_user(Role.AUDITE),
        "admin": make_user(Role.ADMIN),
        "dg": make_user(Role.DG),
    }
    return EquipeConstats(mission_en_xiv, brouillon, soumis, users)
