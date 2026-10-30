"""Équipe complète et fiches pour les tests de l'API de l'accomplissement (T7)."""

from dataclasses import dataclass

import pytest
from rest_framework.test import APIClient

from apps.accomplissement.models import FicheDeTest, TestPrevu
from apps.accomplissement.services.fiches import creer_fiche, modifier_fiche, soumettre_fiche
from apps.missions.models import Mission, RoleMission, StatutEtape
from apps.users.models import Role, User
from tests.accomplissement.fixtures_fiches import ouvrir_xiii
from tests.factories import make_user
from tests.missions.conftest import affecter, forcer_etapes


@dataclass
class Equipe:
    mission: Mission
    test1: TestPrevu  # confié à `auditeur`
    test2: TestPrevu  # confié à `autre`
    fiche1: FicheDeTest  # BROUILLON, auteur `auditeur`
    fiche2: FicheDeTest  # SOUMIS par `autre`
    users: dict[str, User]


def _confier(mission: Mission, test: TestPrevu, user: User) -> None:
    forcer_etapes(mission, {9: StatutEtape.EN_COURS})
    test.auditeur = user
    test.save()
    forcer_etapes(mission, {9: StatutEtape.TERMINEE})


@pytest.fixture
def equipe_api(
    mission_en_accomplissement: Mission,
    chef: User,
    auditeur_mission: User,
    rai: User,
    superviseur: User,
    autre_auditeur: User,
    audite_affecte: User,
) -> Equipe:
    m = mission_en_accomplissement
    test1, test2 = m.tests_prevus.order_by("numero")
    _confier(m, test1, auditeur_mission)
    _confier(m, test2, autre_auditeur)
    fiche1 = creer_fiche(test1, by=auditeur_mission)
    fiche2 = creer_fiche(test2, by=autre_auditeur)
    modifier_fiche(
        fiche2,
        by=autre_auditeur,
        resultat="RAS",
        conclusion="SATISFAISANT",
        justification_sans_piece="Entretien sans document.",
    )
    soumettre_fiche(fiche2, by=autre_auditeur)
    fiche2.refresh_from_db()
    ouvrir_xiii(m)
    users = {
        "rai": rai,
        "chef": chef,
        "superviseur": superviseur,
        "auditeur": auditeur_mission,
        "autre": autre_auditeur,
        "non_confirme": make_user(Role.AUDITEUR),
        "non_affecte": make_user(Role.AUDITEUR),
        "audite": audite_affecte,
        "admin": make_user(Role.ADMIN),
        "dg": make_user(Role.DG),
    }
    affecter(m, users["non_confirme"], RoleMission.AUDITEUR, confirmee=False)
    return Equipe(m, test1, test2, fiche1, fiche2, users)


def client_de(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user)
    return client
