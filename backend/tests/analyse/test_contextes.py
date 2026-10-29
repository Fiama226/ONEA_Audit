import json
from datetime import date

import pytest
from django.core.management import call_command

from apps.analyse.contextes import CONTEXTES, CodeDocumentAnalyse, bloc_mission
from apps.analyse.models import LigneMARC, TypeQuestionnaire
from apps.analyse.services import marc
from apps.analyse.services.questionnaires import creer_questionnaire
from apps.analyse.services.referentiel import referentiel_valide
from apps.documents.management.commands.contrats_documents import Command
from apps.documents.moteur.contrats import EXEMPLE_COMMUN, ecarts_contexte
from apps.documents.moteur.registre import type_document
from apps.missions.models import EtapeMission, Mission, RisqueMission
from apps.missions.services.etapes import rouvrir_etape, valider_etape
from apps.users.models import User
from tests.factories import GrilleSeparationFactory
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db

_COMMUNES = {"mission", "provisoire"}
CLES_CONTRAT: dict[str, set[str]] = {
    "QUESTIONNAIRE_PRISE_CONNAISSANCE": _COMMUNES | {"questionnaires"},
    "QCI": _COMMUNES | {"questionnaires"},
    "GRILLE_SEPARATION_TACHES": _COMMUNES | {"grilles"},
    "MARC": _COMMUNES | {"lignes", "validation"},
    "FORCES_FAIBLESSES": _COMMUNES | {"forces", "faiblesses", "validation"},
    "RAPPORT_ORIENTATION": _COMMUNES
    | {
        "variante",
        "rappel_ordre",
        "contexte",
        "approche",
        "risques_majeurs",
        "forces",
        "faiblesses",
        "objectifs_retenus",
        "objectifs_non_retenus",
        "couverture",
        "calendrier",
        "equipe",
        "validation_referentiel",
        "observations",
    },
}
CODES = [c.value for c in CodeDocumentAnalyse]


def _valider_vi(mission: Mission, chef: User, rai: User) -> None:
    forcer_etapes(mission, {5: "TERMINEE", 6: "TERMINEE"})
    EtapeMission.objects.filter(mission=mission, numero=6).update(terminee_par=chef)
    valider_etape(mission.etapes.get(numero=6), by=rai)


def test_six_codes_et_contextes() -> None:
    assert set(CONTEXTES) == set(CODES) == set(CLES_CONTRAT)


@pytest.mark.parametrize("code", CODES)
def test_contextes_serialisables_json(code: str, mission_en_analyse: Mission) -> None:
    json.dumps(CONTEXTES[code](mission_en_analyse))


@pytest.mark.parametrize("code", CODES)
def test_cles_conformes_au_contrat(code: str, mission_en_analyse: Mission) -> None:
    assert set(CONTEXTES[code](mission_en_analyse)) == CLES_CONTRAT[code]


@pytest.mark.parametrize("code", CODES)
def test_contexte_conforme_au_contrat_lot4(
    code: str, mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User
) -> None:
    marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="x",
        evaluation="ADEQUATE",
    )
    creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.QCI, by=chef)
    contexte = CONTEXTES[code](mission_en_analyse)
    assert ecarts_contexte(type_document(code).contrat, EXEMPLE_COMMUN | contexte) == []
    assert type_document(code).fournisseur.contexte(mission_en_analyse) == contexte


def test_exemples_des_contrats_conformes() -> None:
    for code in CODES:
        c = type_document(code).contrat
        assert ecarts_contexte(c, c.exemple) == []
        assert set(c.exemple) - set(EXEMPLE_COMMUN) == CLES_CONTRAT[code]


def test_documentation_des_contrats_generee_a_jour() -> None:
    call_command(Command(), "--verifier")


def test_dates_au_format_francais(mission_en_analyse: Mission) -> None:
    Mission._base_manager.filter(pk=mission_en_analyse.pk).update(
        date_debut_prevue=date(2026, 3, 2),
        periode_debut=date(2025, 1, 1),
        periode_fin=date(2025, 12, 31),
    )
    mission_en_analyse.refresh_from_db()
    bloc = bloc_mission(mission_en_analyse)
    assert bloc["date_debut_prevue"] == "02/03/2026"
    assert bloc["periode"] == "01/01/2025 au 31/12/2025"
    c = CONTEXTES["RAPPORT_ORIENTATION"](mission_en_analyse)
    assert c["calendrier"]["date_debut_prevue"] == bloc["date_debut_prevue"]
    assert all(isinstance(v, str) for v in c["calendrier"].values())


def test_contexte_marc_lu_dans_l_instantane_si_valide(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User, rai: User
) -> None:
    marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="Double signature",
        evaluation="ADEQUATE",
        cle=True,
    )
    _valider_vi(mission_en_analyse, chef, rai)
    avant = CONTEXTES["MARC"](mission_en_analyse)
    assert avant["provisoire"] == ""
    assert avant["lignes"][0]["controle_existant"] == "Double signature"
    assert avant["lignes"][0]["cle"] == "Oui"
    assert avant["validation"]["par"] == (rai.get_full_name() or rai.username)
    assert len(avant["validation"]["empreinte"]) == 64
    LigneMARC._base_manager.filter(mission=mission_en_analyse).update(controle_existant="Modifié")
    assert CONTEXTES["MARC"](mission_en_analyse) == avant
    ff = CONTEXTES["FORCES_FAIBLESSES"](mission_en_analyse)
    assert ff["provisoire"] == "" and len(ff["forces"]) == 1


def test_contexte_marc_provisoire_apres_reouverture(
    mission_en_analyse: Mission, risque_eleve: RisqueMission, chef: User, rai: User
) -> None:
    marc.ajouter_ligne_marc(
        mission_en_analyse,
        risque=risque_eleve,
        by=chef,
        controle_existant="A",
        evaluation="ADEQUATE",
    )
    _valider_vi(mission_en_analyse, chef, rai)
    assert referentiel_valide(mission_en_analyse) is not None
    rouvrir_etape(mission_en_analyse.etapes.get(numero=4), motif="Risque ajouté", by=rai)
    LigneMARC._base_manager.filter(mission=mission_en_analyse).update(controle_existant="B")
    c = CONTEXTES["MARC"](mission_en_analyse)
    assert c["provisoire"] == "Oui"
    assert c["lignes"][0]["controle_existant"] == "B"
    assert c["validation"] == {"le": "", "par": "", "empreinte": ""}


def test_rapport_orientation_mission_vide(mission_en_analyse: Mission) -> None:
    c = CONTEXTES["RAPPORT_ORIENTATION"](mission_en_analyse)
    assert c["provisoire"] == "Oui"
    for cle in ("forces", "faiblesses", "objectifs_retenus", "objectifs_non_retenus"):
        assert c[cle] == []
    assert c["variante"] == "" and c["couverture"] == {"valeur": "", "justification": ""}
    assert c["validation_referentiel"]["empreinte"] == ""


def test_grille_codes_roles(mission_en_analyse: Mission) -> None:
    GrilleSeparationFactory(
        mission=mission_en_analyse,
        processus=mission_en_analyse.processus.first(),
        taches=["Saisir", "Payer"],
        acteurs=["Agent", "Chef"],
        cellules=[
            {"tache": 0, "acteur": 0, "roles": ["EXECUTE", "CONTROLE"]},
            {"tache": 0, "acteur": 1, "roles": ["AUTORISE"]},
        ],
    )
    g = CONTEXTES["GRILLE_SEPARATION_TACHES"](mission_en_analyse)["grilles"][0]
    assert g["acteurs"] == ["Agent", "Chef"]
    assert g["lignes"][0] == {"tache": "Saisir", "roles_par_acteur": ["E / C", "A"]}
    assert g["lignes"][1]["roles_par_acteur"] == ["", ""]
    assert g["cumuls"] == [{"tache": "Saisir", "acteur": "Agent", "roles": "E / C"}]
    assert g["taches_sans_acteur"] == ["Payer"]
    assert g["taches_multi_executants"] == []


def test_questionnaire_themes_et_numeros(mission_en_analyse: Mission, chef: User) -> None:
    creer_questionnaire(mission_en_analyse, type=TypeQuestionnaire.PRISE_CONNAISSANCE, by=chef)
    q = CONTEXTES["QUESTIONNAIRE_PRISE_CONNAISSANCE"](mission_en_analyse)["questionnaires"]
    assert len(q) == 1
    numeros = [x["numero"] for t in q[0]["themes"] for x in t["questions"]]
    assert numeros == [str(i) for i in range(1, 12)]
    assert CONTEXTES["QCI"](mission_en_analyse)["questionnaires"] == []
