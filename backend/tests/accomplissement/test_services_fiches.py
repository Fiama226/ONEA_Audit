import pytest
from django.core.exceptions import PermissionDenied

from apps.accomplissement.exceptions import FicheValideeError, FicheVerrouilleeError
from apps.accomplissement.models import (
    EvenementFiche,
    FicheDeTest,
    StatutFiche,
    StatutTest,
    TestPrevu,
    TypeEvenementFiche,
)
from apps.accomplissement.services.fiches import (
    creer_fiche,
    modifier_fiche,
    renvoyer_fiche,
    rouvrir_fiche,
    soumettre_fiche,
    valider_fiche,
)
from apps.accomplissement.services.pieces import deposer_piece
from apps.core.exceptions import RegleMetierError
from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.users.models import User
from tests.accomplissement.fixtures_fiches import ouvrir_xiii, pdf
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def test_creer_fiche(test_prevu: TestPrevu, auditeur_mission: User) -> None:
    fiche = creer_fiche(test_prevu, by=auditeur_mission)
    assert fiche.statut == StatutFiche.BROUILLON
    assert fiche.auteur == auditeur_mission
    assert fiche.mission_id == test_prevu.mission_id
    with pytest.raises(RegleMetierError, match="déjà une fiche"):
        creer_fiche(test_prevu, by=auditeur_mission)


def test_creer_fiche_refuse_test_abandonne(test_prevu: TestPrevu, auditeur_mission: User) -> None:
    TestPrevu.objects.filter(pk=test_prevu.pk).update(
        statut=StatutTest.ABANDONNE, motif_abandon="Sans objet"
    )
    test_prevu.refresh_from_db()
    with pytest.raises(RegleMetierError, match="abandonné"):
        creer_fiche(test_prevu, by=auditeur_mission)


def test_creer_fiche_fenetre_xii_et_droits(
    test_prevu: TestPrevu,
    mission_en_accomplissement: Mission,
    auditeur_mission: User,
    audite_affecte: User,
) -> None:
    with pytest.raises(PermissionDenied):
        creer_fiche(test_prevu, by=audite_affecte)
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError) as exc:
        creer_fiche(test_prevu, by=auditeur_mission)
    assert str(exc.value) == "Commencez l'étape XII pour saisir les fiches de test."


def test_creer_fiche_refuse_mission_suspendue(
    test_prevu: TestPrevu, mission_en_accomplissement: Mission, auditeur_mission: User
) -> None:
    Mission.objects.filter(pk=mission_en_accomplissement.pk).update(statut=StatutMission.SUSPENDUE)
    with pytest.raises(RegleMetierError):
        creer_fiche(test_prevu, by=auditeur_mission)
    assert not FicheDeTest.all_objects.exists()


def test_modifier_fiche(fiche_auditeur: FicheDeTest, auditeur_mission: User) -> None:
    fiche = modifier_fiche(fiche_auditeur, by=auditeur_mission, resultat="R", taille_testee=10)
    fiche.refresh_from_db()
    assert (fiche.resultat, fiche.taille_testee) == ("R", 10)
    with pytest.raises(ValueError, match="non modifiables"):
        modifier_fiche(fiche, by=auditeur_mission, statut="VALIDE")
    with pytest.raises(RegleMetierError):
        modifier_fiche(fiche, by=auditeur_mission, taille_testee=5, nombre_exceptions=9)


def test_modifier_fiche_refusee_si_soumise(
    fiche_soumise: FicheDeTest, auditeur_mission: User
) -> None:
    with pytest.raises(FicheVerrouilleeError):
        modifier_fiche(fiche_soumise, by=auditeur_mission, resultat="autre")


def test_soumettre_exige_resultat_conclusion_et_piece_ou_justification(
    fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    with pytest.raises(RegleMetierError) as exc:
        soumettre_fiche(fiche_auditeur, by=auditeur_mission)
    assert str(exc.value) == "Saisissez le résultat et la conclusion avant de soumettre."
    modifier_fiche(fiche_auditeur, by=auditeur_mission, resultat="R", conclusion="ANOMALIE")
    with pytest.raises(RegleMetierError) as exc:
        soumettre_fiche(fiche_auditeur, by=auditeur_mission)
    assert str(exc.value) == "Déposez une pièce justificative ou justifiez son absence."
    modifier_fiche(fiche_auditeur, by=auditeur_mission, justification_sans_piece="Entretien oral")
    fiche = soumettre_fiche(fiche_auditeur, by=auditeur_mission)
    assert fiche.statut == StatutFiche.SOUMIS
    assert fiche.soumise_par == auditeur_mission
    assert fiche.soumise_le is not None
    evenement = EvenementFiche.objects.get(fiche=fiche)
    assert evenement.type == TypeEvenementFiche.SOUMISE
    assert (evenement.statut_avant, evenement.statut_apres) == ("BROUILLON", "SOUMIS")


def test_soumission_avec_piece(fiche_complete: FicheDeTest, auditeur_mission: User) -> None:
    deposer_piece(fiche_complete, fichier=pdf(), libelle="Facture", by=auditeur_mission)
    assert soumettre_fiche(fiche_complete, by=auditeur_mission).statut == StatutFiche.SOUMIS


def test_soumission_refusee_xii_close(
    fiche_complete: FicheDeTest, mission_en_accomplissement: Mission, auditeur_mission: User
) -> None:
    modifier_fiche(fiche_complete, by=auditeur_mission, justification_sans_piece="Oral")
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.TERMINEE})
    with pytest.raises(RegleMetierError) as exc:
        soumettre_fiche(fiche_complete, by=auditeur_mission)
    assert str(exc.value) == "Commencez l'étape XII pour saisir les fiches de test."


def test_valider_fenetre_xiii(fiche_soumise: FicheDeTest, rai: User) -> None:
    with pytest.raises(RegleMetierError) as exc:
        valider_fiche(fiche_soumise, by=rai)
    assert str(exc.value) == "Commencez l'étape XIII pour valider les preuves."


def test_valider_par_rai(
    fiche_soumise: FicheDeTest, mission_en_accomplissement: Mission, rai: User
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    fiche = valider_fiche(fiche_soumise, by=rai)
    fiche.refresh_from_db()
    assert fiche.statut == StatutFiche.VALIDE
    assert fiche.validee_par == rai
    assert fiche.validee_le is not None
    assert EvenementFiche.objects.filter(fiche=fiche, type=TypeEvenementFiche.VALIDEE).exists()
    with pytest.raises(FicheValideeError):
        modifier_fiche(fiche, by=rai, resultat="x")


def test_valider_par_superviseur_leve(
    fiche_soumise: FicheDeTest, mission_en_accomplissement: Mission, superviseur: User
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    assert valider_fiche(fiche_soumise, by=superviseur).statut == StatutFiche.VALIDE


def test_superviseur_non_leve_refuse(
    fiche_soumise: FicheDeTest, mission_en_accomplissement: Mission, superviseur_non_leve: User
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    with pytest.raises(PermissionDenied):
        valider_fiche(fiche_soumise, by=superviseur_non_leve)


def test_valideur_auteur_refuse(
    fiche_soumise: FicheDeTest, mission_en_accomplissement: Mission, superviseur: User
) -> None:
    """Le valideur ne peut pas être l'auteur : la fiche est créée par le superviseur."""
    from apps.accomplissement.models import FicheDeTest as F

    F.objects.filter(pk=fiche_soumise.pk).update(auteur=superviseur)
    ouvrir_xiii(mission_en_accomplissement)
    with pytest.raises(RegleMetierError) as exc:
        valider_fiche(fiche_soumise, by=superviseur)
    assert str(exc.value) == "Le valideur ne peut pas être l'auteur de la fiche."


def test_valideur_auditeur_simple_ou_audite_refuse(
    fiche_soumise: FicheDeTest,
    mission_en_accomplissement: Mission,
    auditeur_mission: User,
    audite_affecte: User,
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    for user in (auditeur_mission, audite_affecte):
        with pytest.raises(PermissionDenied):
            valider_fiche(fiche_soumise, by=user)


def test_valider_exige_statut_soumis(
    fiche_auditeur: FicheDeTest, mission_en_accomplissement: Mission, rai: User
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    with pytest.raises(RegleMetierError, match="soumise"):
        valider_fiche(fiche_auditeur, by=rai)


def test_renvoyer_exige_motif_puis_resoumettre(
    fiche_soumise: FicheDeTest,
    mission_en_accomplissement: Mission,
    rai: User,
    auditeur_mission: User,
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    with pytest.raises(RegleMetierError) as exc:
        renvoyer_fiche(fiche_soumise, motif=" ", by=rai)
    assert str(exc.value) == "Le motif est obligatoire."
    fiche = renvoyer_fiche(fiche_soumise, motif="Pièce illisible", by=rai)
    fiche.refresh_from_db()
    assert fiche.statut == StatutFiche.RENVOYE
    assert fiche.motif_renvoi == "Pièce illisible"
    evenement = EvenementFiche.objects.get(fiche=fiche, type=TypeEvenementFiche.RENVOYEE)
    assert evenement.motif == "Pièce illisible"
    # Correction dans la fenêtre XII puis nouvelle soumission.
    forcer_etapes(mission_en_accomplissement, {12: StatutEtape.RENVOYEE})
    modifier_fiche(fiche, by=auditeur_mission, resultat="Corrigé")
    fiche = soumettre_fiche(fiche, by=auditeur_mission)
    assert fiche.statut == StatutFiche.SOUMIS
    assert fiche.motif_renvoi == ""


def test_rouvrir_fiche_validee(
    fiche_soumise: FicheDeTest,
    mission_en_accomplissement: Mission,
    rai: User,
    auditeur_mission: User,
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    valider_fiche(fiche_soumise, by=rai)
    with pytest.raises(RegleMetierError) as exc:
        rouvrir_fiche(fiche_soumise, motif="", by=rai)
    assert str(exc.value) == "Le motif est obligatoire."
    fiche = rouvrir_fiche(fiche_soumise, motif="Erreur de saisie", by=rai)
    fiche.refresh_from_db()
    assert fiche.statut == StatutFiche.BROUILLON
    assert fiche.validee_par is None
    assert EvenementFiche.objects.filter(fiche=fiche, type=TypeEvenementFiche.ROUVERTE).exists()
    assert EvenementFiche.objects.filter(fiche=fiche).count() == 3  # soumise, validée, rouverte


def test_rouvrir_exige_fiche_validee_et_droit(
    fiche_soumise: FicheDeTest,
    mission_en_accomplissement: Mission,
    rai: User,
    auditeur_mission: User,
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    with pytest.raises(RegleMetierError, match="validée"):
        rouvrir_fiche(fiche_soumise, motif="x", by=rai)
    valider_fiche(fiche_soumise, by=rai)
    with pytest.raises(PermissionDenied):
        rouvrir_fiche(fiche_soumise, motif="x", by=auditeur_mission)


def test_xiii_close_refuse_validation_renvoi_reouverture(
    fiche_soumise: FicheDeTest, mission_en_accomplissement: Mission, rai: User
) -> None:
    ouvrir_xiii(mission_en_accomplissement)
    forcer_etapes(mission_en_accomplissement, {13: StatutEtape.TERMINEE})
    for action in (
        lambda: valider_fiche(fiche_soumise, by=rai),
        lambda: renvoyer_fiche(fiche_soumise, motif="m", by=rai),
    ):
        with pytest.raises(RegleMetierError) as exc:
            action()
        assert str(exc.value) == "Commencez l'étape XIII pour valider les preuves."


@pytest.mark.parametrize("operation", ["creer", "modifier", "soumettre"])
def test_gel_suspendue_toutes_ecritures_lot6_fiches(
    operation: str,
    test_prevu: TestPrevu,
    fiche_complete: FicheDeTest,
    mission_en_accomplissement: Mission,
    auditeur_mission: User,
) -> None:
    Mission.objects.filter(pk=mission_en_accomplissement.pk).update(statut=StatutMission.SUSPENDUE)
    avant = fiche_complete.statut
    with pytest.raises(RegleMetierError):
        if operation == "creer":
            creer_fiche(mission_en_accomplissement.tests_prevus.last(), by=auditeur_mission)
        elif operation == "modifier":
            modifier_fiche(fiche_complete, by=auditeur_mission, resultat="x")
        else:
            soumettre_fiche(fiche_complete, by=auditeur_mission)
    fiche_complete.refresh_from_db()
    assert fiche_complete.statut == avant


def test_references_croisees_refusees(
    mission_en_accomplissement: Mission, fiche_auditeur: FicheDeTest, auditeur_mission: User
) -> None:
    """Un auditeur d'une mission ne dépose rien sur la fiche d'une autre mission."""
    from tests.accomplissement.factories import FicheFactory

    autre = FicheFactory()  # autre mission
    with pytest.raises(PermissionDenied):
        deposer_piece(autre, fichier=pdf(), libelle="x", by=auditeur_mission)
