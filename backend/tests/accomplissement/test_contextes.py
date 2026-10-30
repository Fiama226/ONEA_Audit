import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.accomplissement.contextes import (
    CONTEXTES_FICHE,
    CONTEXTES_MISSION,
    empreinte_abregee,
    formater_decimal,
)
from apps.accomplissement.models import FicheDeTest, StatutTest, TestPrevu
from apps.documents.management.commands.contrats_documents import Command
from apps.documents.moteur.contrats import EXEMPLE_COMMUN, ecarts_contexte
from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import type_document
from apps.missions.models import Mission
from tests.accomplissement.factories import FicheFactory, PieceFactory, TestPrevuFactory
from tests.factories import MissionFactory

pytestmark = pytest.mark.django_db

CODES_MISSION = list(CONTEXTES_MISSION)
CODES_FICHE = list(CONTEXTES_FICHE)
DOCS = Path(__file__).resolve().parents[3] / "docs" / "documents" / "contrats"
MAX_REQUETES = 6


def _objet(code: str, mission: Mission, fiche: FicheDeTest) -> Any:
    return mission if code in CONTEXTES_MISSION else fiche


def _contexte(code: str, objet: Any) -> dict[str, Any]:
    fonction = CONTEXTES_MISSION.get(code) or CONTEXTES_FICHE[code]
    resultat: dict[str, Any] = fonction(objet)
    return resultat


@pytest.mark.parametrize("code", CODES_MISSION + CODES_FICHE)
def test_contexte_conforme_au_contrat_et_borne(
    code: str, mission_en_accomplissement: Mission, fiche_soumise: FicheDeTest
) -> None:
    objet = _objet(code, mission_en_accomplissement, fiche_soumise)
    with CaptureQueriesContext(connection) as requetes:
        contexte = _contexte(code, objet)
    assert len(requetes) <= MAX_REQUETES
    json.dumps(contexte)
    contrat = type_document(code).contrat
    assert ecarts_contexte(contrat, EXEMPLE_COMMUN | contexte) == []
    assert type_document(code).fournisseur.contexte(objet) == contexte


@pytest.mark.parametrize("code", CODES_MISSION + CODES_FICHE)
def test_exemple_du_contrat_conforme(code: str) -> None:
    contrat = type_document(code).contrat
    assert ecarts_contexte(contrat, contrat.exemple) == []


@pytest.mark.parametrize("code", CODES_MISSION + CODES_FICHE)
def test_page_du_contrat_liste_toutes_les_balises(code: str) -> None:
    page = (DOCS / f"{code}.md").read_text(encoding="utf-8")
    contrat = type_document(code).contrat
    for champ in contrat.champs:
        assert f"`{champ.nom}`" in page
    assert f"`{code}`" in page


@pytest.mark.parametrize("code", CODES_MISSION + CODES_FICHE)
def test_gabarit_provisoire_constructible(code: str) -> None:
    assert construire_gabarit_provisoire(type_document(code))


def test_documentation_des_contrats_a_jour() -> None:
    call_command(Command(), "--verifier")


def test_programme_totaux_et_formats(mission_en_accomplissement: Mission) -> None:
    Mission.objects.filter(pk=mission_en_accomplissement.pk).update(budget_jours=Decimal("3.0"))
    mission_en_accomplissement.refresh_from_db()
    TestPrevu._base_manager.filter(mission=mission_en_accomplissement).update(
        charge_prevue_jours=Decimal("2.5"), date_debut_prevue=date(2026, 3, 2)
    )
    c = CONTEXTES_MISSION["PROGRAMME_TRAVAIL"](mission_en_accomplissement)
    assert c["totaux"] == {
        "nb_tests": "2",
        "charge_jours": "5,0",
        "budget_jours": "3,0",
        "depassement_budget": "Oui",
    }
    assert c["tests_sans_auditeur"] == ["T-01", "T-02"]
    assert c["objectifs"][0]["code"] == "OA-01"
    assert c["objectifs"][0]["tests"][0]["date_debut_prevue"] == "02/03/2026"
    assert c["objectifs"][0]["tests"][0]["charge_prevue_jours"] == "2,5"
    assert c["provisoire"] == "Oui"
    assert c["instantane"] == {"le": "", "par": "", "empreinte": ""}


def test_programme_exclut_tests_abandonnes(mission_en_accomplissement: Mission) -> None:
    TestPrevu.objects.filter(mission=mission_en_accomplissement, numero=1).update(
        statut=StatutTest.ABANDONNE, motif_abandon="Doublon"
    )
    c = CONTEXTES_MISSION["PROGRAMME_TRAVAIL"](mission_en_accomplissement)
    assert c["totaux"]["nb_tests"] == "1"


def test_couverture_classe_les_tests(mission_en_accomplissement: Mission) -> None:
    premier, second = mission_en_accomplissement.tests_prevus.order_by("numero")
    TestPrevu.objects.filter(pk=second.pk).update(
        statut=StatutTest.ABANDONNE, motif_abandon="Doublon du premier"
    )
    TestPrevuFactory(
        mission=mission_en_accomplissement, programme=premier.programme, complementaire=True
    )
    c = CONTEXTES_MISSION["FEUILLE_COUVERTURE"](mission_en_accomplissement)
    assert [t["code"] for t in c["tests_prevus"]] == ["T-01"]
    assert [t["code"] for t in c["tests_complementaires"]] == ["T-03"]
    assert c["tests_abandonnes"][0]["motif"] == "Doublon du premier"
    assert c["tests_prevus"][0]["statut_fiche"] == "Aucune fiche"
    assert c["synthese"]["nb_abandonnes"] == "1"
    assert c["provisoire"] == "Oui"


def test_feuille_de_travail_formats(fiche_soumise: FicheDeTest) -> None:
    FicheDeTest.objects.filter(pk=fiche_soumise.pk).update(
        date_realisation=date(2026, 3, 9), nombre_exceptions=0, taille_testee=30
    )
    c = CONTEXTES_FICHE["FEUILLE_TRAVAIL"](fiche_soumise)
    assert c["realisation"]["date_realisation"] == "09/03/2026"
    assert c["realisation"]["taux_exception"] == "0 %"
    assert c["realisation"]["conclusion"] == "Satisfaisant"
    assert c["test"]["objectif_audit"].startswith("OA-01 — ")
    assert c["provisoire"] == "Oui"


def test_fiche_test_pieces_sans_donnee_interne(fiche_soumise: FicheDeTest) -> None:
    c = CONTEXTES_FICHE["FICHE_TEST"](fiche_soumise)
    piece = c["pieces"][0]
    assert set(piece) == {"numero", "libelle", "nom_fichier", "empreinte"}
    assert len(piece["empreinte"]) == 17
    assert "…" in piece["empreinte"]
    assert [e["evenement"] for e in c["journal"]] == ["Soumise"]


def test_aucune_donnee_d_une_autre_mission(mission_en_accomplissement: Mission) -> None:
    autre = MissionFactory()
    etrangere = FicheFactory(test__mission=autre, test__programme__mission=autre)
    PieceFactory(fiche=etrangere, libelle="Pièce étrangère")
    for code in CODES_MISSION:
        texte = json.dumps(_contexte(code, mission_en_accomplissement))
        assert autre.titre not in texte
        assert etrangere.test.libelle not in texte
    texte = json.dumps(
        _contexte("FICHE_TEST", FicheDeTest.objects.get(pk=etrangere.pk)), ensure_ascii=False
    )
    assert "Pièce étrangère" in texte
    assert mission_en_accomplissement.titre not in texte


def test_formateurs() -> None:
    assert formater_decimal(Decimal("40.5")) == "40,5"
    assert formater_decimal(None) == ""
    assert empreinte_abregee("a" * 8 + "m" * 48 + "z" * 8) == "aaaaaaaa…zzzzzzzz"
