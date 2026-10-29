"""Fiches de test (étape XII) et validation des preuves (étape XIII).

Ordre de verrouillage, partout : mission -> étape -> entité. Chaque écriture exige la fenêtre de
l'étape (XII pour le contenu et la soumission ; XIII pour valider, renvoyer, rouvrir), avec un
message explicite, avant même les gardes de gel des modèles (qui restent la dernière défense).
"""

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import EtapeMission, Mission
from apps.missions.services.travaux import verrouiller_travaux
from apps.users.models import User

from .. import droits_fiches as droits
from ..exceptions import FicheValideeError, FicheVerrouilleeError
from ..gardes import ETAPE_FICHES, ETAPE_VALIDATION_PREUVES
from ..models import (
    EvenementFiche,
    FicheDeTest,
    StatutFiche,
    StatutTest,
    TestPrevu,
    TypeEvenementFiche,
)

MSG_XII = "Commencez l'étape XII pour saisir les fiches de test."
MSG_XIII = "Commencez l'étape XIII pour valider les preuves."
MSG_MOTIF = "Le motif est obligatoire."
MSG_RESULTAT = "Saisissez le résultat et la conclusion avant de soumettre."
MSG_PIECE = "Déposez une pièce justificative ou justifiez son absence."
MSG_AUTEUR = "Le valideur ne peut pas être l'auteur de la fiche."

_MODIFIABLES = {
    "date_realisation",
    "travaux_realises",
    "echantillon_teste",
    "taille_testee",
    "nombre_exceptions",
    "resultat",
    "conclusion",
    "commentaire_conclusion",
    "charge_reelle_jours",
    "justification_sans_piece",
}


def ouvrir_fenetre(mission: Mission, numero: int, message: str) -> Mission:
    """Verrouille la mission puis l'étape `numero` (transaction requise) ; exige l'étape active."""
    verrouillee = verrouiller_travaux(mission)
    etape = (
        EtapeMission.objects.select_for_update()
        .filter(mission=verrouillee, numero=numero)
        .values_list("statut", flat=True)
        .first()
    )
    if etape not in droits.ACTIFS:
        raise RegleMetierError(message)
    return verrouillee


def exiger_fiche_modifiable(fiche: FicheDeTest) -> None:
    """Seules les fiches BROUILLON et RENVOYE (lues sous verrou) acceptent une écriture."""
    code = fiche.test.code
    if fiche.statut == StatutFiche.VALIDE:
        raise FicheValideeError(code)
    if fiche.statut == StatutFiche.SOUMIS:
        raise FicheVerrouilleeError(code)


def _journaliser(fiche: FicheDeTest, type_: str, *, by: User, avant: str, motif: str = "") -> None:
    EvenementFiche.journaliser(fiche, type_, par=by, motif=motif, statut_avant=avant)


@transaction.atomic
def creer_fiche(test: TestPrevu, *, by: User) -> FicheDeTest:
    mission = ouvrir_fenetre(test.mission, ETAPE_FICHES, MSG_XII)
    test = TestPrevu.objects.select_for_update().get(pk=test.pk)
    droits.exiger_redacteur(by, mission, test)
    if test.statut != StatutTest.PREVU:
        message = f"Le test {test.code} est abandonné : il n'a pas de fiche."
        raise refuser(message, test=message)
    if FicheDeTest.objects.filter(test=test).exists():
        message = f"Le test {test.code} a déjà une fiche."
        raise refuser(message, test=message)
    fiche = FicheDeTest(mission=mission, test=test, auteur=by)
    enregistrer(fiche, by=by, creation=True)
    return fiche


@transaction.atomic
def modifier_fiche(fiche: FicheDeTest, *, by: User, **changes: Any) -> FicheDeTest:
    mission = ouvrir_fenetre(fiche.mission, ETAPE_FICHES, MSG_XII)
    fiche = relire(fiche)
    droits.exiger_redacteur(by, mission, fiche.test)
    exiger_fiche_modifiable(fiche)
    appliquer(fiche, changes, _MODIFIABLES)
    if (
        fiche.nombre_exceptions is not None
        and fiche.taille_testee is not None
        and fiche.nombre_exceptions > fiche.taille_testee
    ):
        message = "Le nombre d'exceptions ne peut pas dépasser la taille testée."
        raise refuser(message, nombre_exceptions=message)
    enregistrer(fiche, by=by)
    return fiche


@transaction.atomic
def soumettre_fiche(fiche: FicheDeTest, *, by: User) -> FicheDeTest:
    mission = ouvrir_fenetre(fiche.mission, ETAPE_FICHES, MSG_XII)
    fiche = relire(fiche)
    droits.exiger_redacteur(by, mission, fiche.test)
    exiger_fiche_modifiable(fiche)
    if not fiche.resultat.strip() or not fiche.conclusion:
        raise refuser(MSG_RESULTAT, resultat=MSG_RESULTAT)
    if not fiche.pieces.exists() and not fiche.justification_sans_piece.strip():
        raise refuser(MSG_PIECE, justification_sans_piece=MSG_PIECE)
    avant = fiche.statut
    fiche.soumettre()
    fiche.soumise_par = by
    fiche.soumise_le = timezone.now()
    fiche.motif_renvoi = ""
    enregistrer(fiche, by=by)
    _journaliser(fiche, TypeEvenementFiche.SOUMISE, by=by, avant=avant)
    return fiche


@transaction.atomic
def supprimer_fiche(fiche: FicheDeTest, *, by: User) -> None:
    """Suppression logique d'un brouillon vide (ni pièce, ni événement) par un rédacteur."""
    mission = ouvrir_fenetre(fiche.mission, ETAPE_FICHES, MSG_XII)
    fiche = relire(fiche)
    droits.exiger_redacteur(by, mission, fiche.test)
    exiger_fiche_modifiable(fiche)
    if fiche.statut != StatutFiche.BROUILLON or fiche.evenements.exists() or fiche.pieces.exists():
        raise refuser("Seul un brouillon sans pièce ni historique peut être supprimé.")
    fiche.soft_delete(by)


def _ouvrir_validation(fiche: FicheDeTest, by: User) -> FicheDeTest:
    mission = ouvrir_fenetre(fiche.mission, ETAPE_VALIDATION_PREUVES, MSG_XIII)
    droits.exiger_valideur(by, mission)
    return relire(fiche)


def _exiger_statut(fiche: FicheDeTest, statut: StatutFiche, message: str) -> None:
    if fiche.statut != statut:
        raise RegleMetierError(message)


@transaction.atomic
def valider_fiche(fiche: FicheDeTest, *, by: User) -> FicheDeTest:
    fiche = _ouvrir_validation(fiche, by)
    _exiger_statut(fiche, StatutFiche.SOUMIS, "Seule une fiche soumise peut être validée.")
    if by.pk in (fiche.auteur_id, fiche.soumise_par_id):
        raise RegleMetierError(MSG_AUTEUR)
    avant = fiche.statut
    fiche.valider()
    fiche.validee_par = by
    fiche.validee_le = timezone.now()
    enregistrer(fiche, by=by)
    _journaliser(fiche, TypeEvenementFiche.VALIDEE, by=by, avant=avant)
    return fiche


@transaction.atomic
def renvoyer_fiche(fiche: FicheDeTest, *, motif: str, by: User) -> FicheDeTest:
    fiche = _ouvrir_validation(fiche, by)
    _exiger_statut(fiche, StatutFiche.SOUMIS, "Seule une fiche soumise peut être renvoyée.")
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    avant = fiche.statut
    fiche.renvoyer()
    fiche.motif_renvoi = motif
    enregistrer(fiche, by=by)
    _journaliser(fiche, TypeEvenementFiche.RENVOYEE, by=by, avant=avant, motif=motif)
    return fiche


@transaction.atomic
def rouvrir_fiche(fiche: FicheDeTest, *, motif: str, by: User) -> FicheDeTest:
    fiche = _ouvrir_validation(fiche, by)
    _exiger_statut(fiche, StatutFiche.VALIDE, "Seule une fiche validée peut être rouverte.")
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    avant = fiche.statut
    fiche.rouvrir()
    fiche.validee_par = None
    fiche.validee_le = None
    enregistrer(fiche, by=by)
    _journaliser(fiche, TypeEvenementFiche.ROUVERTE, by=by, avant=avant, motif=motif)
    return fiche
