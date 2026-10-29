import pytest
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.analyse.models import AvisAudite, StatutReferentiel
from apps.analyse.services import marc
from apps.analyse.services.referentiel import (
    TEXTE_VALIDATION,
    deposer_avis,
    figer_referentiel,
    instantane_referentiel,
    referentiel_valide,
    synthese_referentiel,
)
from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, Mission, RisqueMission
from apps.missions.services.etapes import rouvrir_etape, valider_etape
from apps.signatures.services import verifier
from apps.users.models import User
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _valider_vi(mission: Mission, chef: User, rai: User) -> None:
    forcer_etapes(mission, {5: "TERMINEE", 6: "TERMINEE"})
    EtapeMission.objects.filter(mission=mission, numero=6).update(terminee_par=chef)
    valider_etape(mission.etapes.get(numero=6), by=rai)


def test_validation_vi_cree_instantane_verifiable(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User, rai: User
) -> None:
    ligne = marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Double signature des bons",
        evaluation="ADEQUATE",
        cle=True,
    )
    source = risque_eleve.risque_source
    assert source is not None
    assert ligne.objectif_controle == source.objectif_controle
    _valider_vi(mission_en_analyse, chef, rai)
    c = referentiel_valide(mission_en_analyse)
    assert c is not None
    assert verifier(c) and c.donnees["lignes_marc"][0]["appreciation"] == "FORCE"
    assert c.signataire == rai
    assert c.texte.startswith("Je soussigné(e) ")
    assert "(1 lignes de la matrice" in c.texte
    assert synthese_referentiel(mission_en_analyse).statut == "VALIDE"


def test_texte_validation_mot_pour_mot() -> None:
    assert TEXTE_VALIDATION == (
        "Je soussigné(e) {nom_complet}, valide le référentiel d'audit de la mission "
        "{reference} « {titre} » ({n} lignes de la matrice d'analyse des risques et "
        "contrôles), qui servira de référence à l'évaluation du dispositif de contrôle "
        "interne."
    )


def test_revalidation_nouvel_instantane(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User, rai: User
) -> None:
    marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    _valider_vi(mission_en_analyse, chef, rai)
    premiere = referentiel_valide(mission_en_analyse)
    assert premiere is not None
    rouvrir_etape(mission_en_analyse.etapes.get(numero=4), motif="Risque ajouté", by=rai)
    assert mission_en_analyse.etapes.get(numero=6).statut == "A_REVALIDER"
    assert referentiel_valide(mission_en_analyse) is None
    assert synthese_referentiel(mission_en_analyse).statut == StatutReferentiel.A_REVALIDER
    valider_etape(mission_en_analyse.etapes.get(numero=6), by=rai)
    seconde = referentiel_valide(mission_en_analyse)
    assert seconde is not None and seconde.pk != premiere.pk
    assert verifier(premiere) and verifier(seconde)


def test_instantane_contenu_et_requetes(
    mission_en_analyse: Mission,
    risque_eleve: RisqueMission,
    chef: User,
    audite_affecte: User,
) -> None:
    marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Contrôle",
        evaluation="INSUFFISANTE",
    )
    forcer_etapes(mission_en_analyse, {6: "EN_COURS"})
    deposer_avis(mission_en_analyse, avis="ACCORD", commentaire="", by=audite_affecte)
    with CaptureQueriesContext(connection) as ctx:
        data = instantane_referentiel(mission_en_analyse)
    assert len(ctx) <= 5
    assert set(data) == {"mission", "risques", "lignes_marc", "forces_faiblesses", "avis"}
    assert data["mission"] == {
        "reference": mission_en_analyse.reference,
        "titre": mission_en_analyse.titre,
    }
    assert len(data["risques"]) == 2
    assert data["forces_faiblesses"][0]["type"] == "FAIBLESSE"
    assert data["avis"][0]["avis"] == "ACCORD"
    assert data == instantane_referentiel(mission_en_analyse)


def test_avis_audite_fenetre_et_auteur(
    mission_en_analyse: Mission,
    chef: User,
    rai: User,
    auditeur_mission: User,
    audite_affecte: User,
    risque_eleve: RisqueMission,
) -> None:
    with pytest.raises(PermissionDenied):
        deposer_avis(mission_en_analyse, avis="ACCORD", commentaire="", by=auditeur_mission)
    # VI pas démarrée
    with pytest.raises(RegleMetierError):
        deposer_avis(mission_en_analyse, avis="ACCORD", commentaire="", by=audite_affecte)
    forcer_etapes(mission_en_analyse, {6: "EN_COURS"})
    with pytest.raises(RegleMetierError) as e:
        deposer_avis(mission_en_analyse, avis="REMARQUES", commentaire=" ", by=audite_affecte)
    assert "commentaire" in e.value.errors
    deposer_avis(mission_en_analyse, avis="REMARQUES", commentaire="Réserve", by=audite_affecte)
    deposer_avis(mission_en_analyse, avis="ACCORD", commentaire="", by=audite_affecte)
    assert AvisAudite.objects.filter(mission=mission_en_analyse).count() == 2
    marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    _valider_vi(mission_en_analyse, chef, rai)
    with pytest.raises(RegleMetierError):
        deposer_avis(mission_en_analyse, avis="ACCORD", commentaire="", by=audite_affecte)


def test_synthese_requetes_bornees(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User, rai: User
) -> None:
    marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Contrôle",
        evaluation="ADEQUATE",
    )
    s0 = synthese_referentiel(mission_en_analyse)
    assert (s0.nb_lignes, s0.nb_forces, s0.nb_faiblesses) == (1, 1, 0)
    assert s0.statut == StatutReferentiel.BROUILLON and s0.validation is None
    _valider_vi(mission_en_analyse, chef, rai)
    synthese_referentiel(mission_en_analyse)  # réchauffe le cache des types de contenu
    with CaptureQueriesContext(connection) as ctx:
        s = synthese_referentiel(mission_en_analyse)
    assert len(ctx) <= 6
    assert s.validation is not None and s.statut_vi == "VALIDEE"


def test_figer_referentiel_direct(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User, rai: User
) -> None:
    marc.ajouter_ligne_marc(mission_en_analyse, risque=risque_eleve, by=chef)
    c = figer_referentiel(mission_en_analyse, by=rai)
    assert verifier(c)
