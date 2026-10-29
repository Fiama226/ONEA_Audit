"""Droits de rédaction des fiches (D13) : RAI, chef de mission, auditeur du test."""

import pytest
from django.core.exceptions import PermissionDenied

from apps.accomplissement.droits_fiches import actions_fiche, actions_piece
from apps.accomplissement.models import FicheDeTest, TestPrevu
from apps.accomplissement.services.fiches import (
    creer_fiche,
    modifier_fiche,
    soumettre_fiche,
    valider_fiche,
)
from apps.accomplissement.services.pieces import deposer_piece, modifier_piece, retirer_piece
from apps.missions.models import Mission
from apps.missions.services.etapes import contexte_actions
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import ouvrir_xiii, pdf

pytestmark = pytest.mark.django_db

AUTORISES = ["rai", "chef", "auditeur_mission"]
REFUSES = ["autre_auditeur", "superviseur", "audite_affecte"]


@pytest.mark.parametrize("role", AUTORISES)
def test_creer_fiche_autorise(
    role: str, test_prevu: TestPrevu, request: pytest.FixtureRequest
) -> None:
    user: User = request.getfixturevalue(role)
    assert creer_fiche(test_prevu, by=user).auteur == user


@pytest.mark.parametrize("role", REFUSES)
def test_creer_fiche_refuse(
    role: str, test_prevu: TestPrevu, request: pytest.FixtureRequest
) -> None:
    user: User = request.getfixturevalue(role)
    with pytest.raises(PermissionDenied):
        creer_fiche(test_prevu, by=user)
    assert not FicheDeTest.all_objects.exists()


@pytest.mark.parametrize("role", AUTORISES)
def test_ecritures_autorisees(
    role: str, fiche_complete: FicheDeTest, request: pytest.FixtureRequest
) -> None:
    user: User = request.getfixturevalue(role)
    modifier_fiche(fiche_complete, by=user, commentaire_conclusion="ok")
    piece = deposer_piece(fiche_complete, fichier=pdf(), libelle="A", by=user)
    modifier_piece(piece, by=user, libelle="B")
    retirer_piece(piece, by=user)
    modifier_fiche(fiche_complete, by=user, justification_sans_piece="Oral")
    assert soumettre_fiche(fiche_complete, by=user).soumise_par == user


@pytest.mark.parametrize("role", REFUSES)
def test_ecritures_refusees(
    role: str,
    fiche_complete: FicheDeTest,
    auditeur_mission: User,
    request: pytest.FixtureRequest,
) -> None:
    user: User = request.getfixturevalue(role)
    piece = deposer_piece(fiche_complete, fichier=pdf(), libelle="A", by=auditeur_mission)
    with pytest.raises(PermissionDenied):
        modifier_fiche(fiche_complete, by=user, resultat="x")
    with pytest.raises(PermissionDenied):
        soumettre_fiche(fiche_complete, by=user)
    with pytest.raises(PermissionDenied):
        deposer_piece(fiche_complete, fichier=pdf("b.pdf", b"%PDF-1.4 b"), libelle="B", by=user)
    with pytest.raises(PermissionDenied):
        modifier_piece(piece, by=user, libelle="x")
    with pytest.raises(PermissionDenied):
        retirer_piece(piece, by=user)


def test_actions_de_redaction_par_role(
    fiche_complete: FicheDeTest,
    mission_en_accomplissement: Mission,
    request: pytest.FixtureRequest,
) -> None:
    for role in AUTORISES:
        user: User = request.getfixturevalue(role)
        ctx = contexte_actions(mission_en_accomplissement, user)
        assert {"MODIFIER", "SOUMETTRE", "DEPOSER_PIECE"} <= set(
            actions_fiche(fiche_complete, user, contexte=ctx)
        ), role
    for role in REFUSES:
        user = request.getfixturevalue(role)
        ctx = contexte_actions(mission_en_accomplissement, user)
        assert not {"MODIFIER", "SOUMETTRE", "DEPOSER_PIECE"} & set(
            actions_fiche(fiche_complete, user, contexte=ctx)
        ), role


def test_actions_de_piece_par_role(
    fiche_complete: FicheDeTest,
    mission_en_accomplissement: Mission,
    auditeur_mission: User,
    autre_auditeur: User,
    audite_affecte: User,
) -> None:
    piece = deposer_piece(fiche_complete, fichier=pdf(), libelle="A", by=auditeur_mission)
    ctx = contexte_actions(mission_en_accomplissement, auditeur_mission)
    assert set(actions_piece(piece, auditeur_mission, contexte=ctx)) == {
        "TELECHARGER",
        "MODIFIER",
        "RETIRER",
    }
    ctx = contexte_actions(mission_en_accomplissement, autre_auditeur)
    assert actions_piece(piece, autre_auditeur, contexte=ctx) == ["TELECHARGER"]
    ctx = contexte_actions(mission_en_accomplissement, audite_affecte)
    assert actions_piece(piece, audite_affecte, contexte=ctx) == []


def test_valider_non_propose_a_celui_qui_a_soumis(
    fiche_complete: FicheDeTest,
    mission_en_accomplissement: Mission,
    auditeur_mission: User,
    rai: User,
) -> None:
    modifier_fiche(fiche_complete, by=auditeur_mission, justification_sans_piece="Oral")
    soumettre_fiche(fiche_complete, by=rai)  # auteur : auditeur ; soumise par le RAI
    ouvrir_xiii(mission_en_accomplissement)
    fiche_complete.refresh_from_db()
    ctx = contexte_actions(mission_en_accomplissement, rai)
    actions = actions_fiche(fiche_complete, rai, contexte=ctx)
    assert "VALIDER" not in actions
    assert "RENVOYER" in actions
    from apps.core.exceptions import RegleMetierError

    with pytest.raises(RegleMetierError):
        valider_fiche(fiche_complete, by=rai)
