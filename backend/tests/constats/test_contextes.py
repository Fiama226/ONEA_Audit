import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.constats.contextes import contexte_fiche_observation
from apps.constats.documents import FournisseurFicheObservation
from apps.constats.models import CategorieCause, Constat, PositionAudite, StatutConstat
from apps.documents.management.commands.contrats_documents import Command
from apps.documents.moteur.contrats import EXEMPLE_COMMUN, ecarts_contexte
from apps.documents.moteur.provisoires import construire_gabarit_provisoire
from apps.documents.moteur.registre import type_document
from apps.missions.models import Mission
from tests.constats.factories import CauseFactory, ConstatFactory, ReponseFactory
from tests.factories import MissionFactory

pytestmark = pytest.mark.django_db

CODE = "FICHE_OBSERVATION"
DOCS = Path(__file__).resolve().parents[3] / "docs" / "documents" / "contrats"


def test_contexte_conforme_au_contrat_et_borne(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    ReponseFactory(constat=constat, mission=mission_en_xiv, cycle=constat.cycle)
    with CaptureQueriesContext(connection) as requetes:
        contexte = contexte_fiche_observation(constat)
    assert len(requetes) <= 6
    json.dumps(contexte)
    contrat = type_document(CODE).contrat
    assert ecarts_contexte(contrat, EXEMPLE_COMMUN | contexte) == []
    assert contexte["reponse"]["position"] == "Accord"
    assert type_document(CODE).fournisseur.contexte(constat) == contexte


def test_exemple_gabarit_et_documentation() -> None:
    contrat = type_document(CODE).contrat
    assert ecarts_contexte(contrat, contrat.exemple) == []
    assert construire_gabarit_provisoire(type_document(CODE))
    assert f"`{CODE}`" in (DOCS / f"{CODE}.md").read_text(encoding="utf-8")
    call_command(Command(), "--verifier")


def test_causes_groupees_7m_et_sans_donnee_interne(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv)
    CauseFactory(constat=constat, mission=mission_en_xiv, categorie=CategorieCause.MANAGEMENT)
    CauseFactory(constat=constat, mission=mission_en_xiv, description="Autre cause.")
    c = contexte_fiche_observation(constat)
    assert [g["categorie"] for g in c["causes"]] == ["Méthodes", "Management"]
    assert len(c["causes"][0]["descriptions"]) == 2
    texte = json.dumps(c)
    for fiche in constat.fiches.all():
        assert fiche.test.code not in texte
    assert set(c["constat"]) >= {"niveau"}
    assert "probabilite" not in c["constat"] and "impact" not in c["constat"]


def test_derniere_reponse_du_cycle_courant(mission_en_xiv: Mission) -> None:
    constat = ConstatFactory(mission=mission_en_xiv, statut=StatutConstat.SOUMIS, cycle=1)
    assert contexte_fiche_observation(constat)["reponse"] == {
        "position": "",
        "commentaire": "",
        "le": "",
    }
    ReponseFactory(constat=constat, mission=mission_en_xiv, cycle=1)
    ReponseFactory(
        constat=constat,
        mission=mission_en_xiv,
        cycle=1,
        position=PositionAudite.DESACCORD,
        commentaire="Faits contestés.",
    )
    reponse = contexte_fiche_observation(constat)["reponse"]
    assert reponse["position"] == "Désaccord"
    assert reponse["commentaire"] == "Faits contestés."


def test_aucune_donnee_d_une_autre_mission(mission_en_xiv: Mission) -> None:
    ConstatFactory(mission=MissionFactory(), titre="Constat étranger")
    constat = ConstatFactory(mission=mission_en_xiv)
    assert "Constat étranger" not in json.dumps(contexte_fiche_observation(constat))


def test_fournisseur_non_generable_avant_soumission(mission_en_xiv: Mission) -> None:
    constat: Constat = ConstatFactory(mission=mission_en_xiv)
    f = FournisseurFicheObservation()
    assert f.raison_non_generable(constat) == (
        "Soumettez le constat avant de générer sa fiche d'observation."
    )
    constat.statut = StatutConstat.SOUMIS
    assert f.raison_non_generable(constat) is None
