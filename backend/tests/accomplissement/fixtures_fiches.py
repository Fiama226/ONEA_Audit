"""Fixtures partagées des tests T5 (fiches, pièces, intégrité)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accomplissement.models import FicheDeTest, TestPrevu
from apps.accomplissement.services.fiches import creer_fiche, modifier_fiche, soumettre_fiche
from apps.accomplissement.services.pieces import deposer_piece
from apps.missions.models import Mission, RoleMission, StatutEtape
from apps.users.models import Role, User
from tests.factories import make_user
from tests.missions.conftest import affecter, forcer_etapes

PDF = b"%PDF-1.7\n" + b"x" * 1000


def pdf(nom: str = "facture.pdf", contenu: bytes = PDF) -> SimpleUploadedFile:
    return SimpleUploadedFile(nom, contenu)


@pytest.fixture
def rai(db: None) -> User:
    return make_user(Role.RAI)


@pytest.fixture
def superviseur(mission_en_accomplissement: Mission) -> User:
    user = make_user(Role.AUDITEUR)
    affecter(mission_en_accomplissement, user, RoleMission.SUPERVISEUR)
    return user


@pytest.fixture
def superviseur_non_leve(mission_en_accomplissement: Mission) -> User:
    user = make_user(Role.AUDITEUR)
    affecter(mission_en_accomplissement, user, RoleMission.SUPERVISEUR, confirmee=False)
    return user


@pytest.fixture
def autre_auditeur(mission_en_accomplissement: Mission) -> User:
    """Intervenant levé, auditeur d'un AUTRE test."""
    user = make_user(Role.AUDITEUR)
    affecter(mission_en_accomplissement, user, RoleMission.AUDITEUR)
    return user


@pytest.fixture
def test_prevu(mission_en_accomplissement: Mission, auditeur_mission: User) -> TestPrevu:
    """Premier test, confié à `auditeur_mission` ; le second l'est à `autre_auditeur`."""
    forcer_etapes(mission_en_accomplissement, {9: StatutEtape.EN_COURS})
    premier, second = mission_en_accomplissement.tests_prevus.order_by("numero")
    premier.auditeur = auditeur_mission
    premier.save()
    forcer_etapes(mission_en_accomplissement, {9: StatutEtape.TERMINEE})
    premier.refresh_from_db()
    assert second.auditeur_id is None
    return premier


@pytest.fixture
def fiche_auditeur(test_prevu: TestPrevu, auditeur_mission: User) -> FicheDeTest:
    """Fiche BROUILLON créée par l'auditeur de la mission (l'auteur est l'auditeur)."""
    return creer_fiche(test_prevu, by=auditeur_mission)


@pytest.fixture
def fiche_complete(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> FicheDeTest:
    modifier_fiche(
        fiche_auditeur,
        by=auditeur_mission,
        resultat="Aucune anomalie relevée.",
        conclusion="SATISFAISANT",
        taille_testee=30,
        nombre_exceptions=0,
    )
    return fiche_auditeur


@pytest.fixture
def fiche_soumise(fiche_complete: FicheDeTest, auditeur_mission: User) -> FicheDeTest:
    deposer_piece(fiche_complete, fichier=pdf(), libelle="Facture 2026-031", by=auditeur_mission)
    soumettre_fiche(fiche_complete, by=auditeur_mission)
    fiche_complete.refresh_from_db()
    return fiche_complete


def ouvrir_xiii(mission: Mission) -> None:
    forcer_etapes(mission, {13: StatutEtape.EN_COURS})
