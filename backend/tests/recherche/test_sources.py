"""Documents d'index : champs, audiences, objets non indexables, aucun contenu de fichier."""

import json
from typing import Any

from django.utils import timezone

from apps.communication.models import Rapport, StatutRapport
from apps.constats.models import Constat, Recommandation
from apps.documents.models import StatutGeneration
from apps.missions.models import Mission, StatutMission
from apps.recherche.sources import SOURCES
from apps.suivi.models import SuiviAction
from tests.communication.factories import RapportFactory
from tests.constats.factories import ConstatFactory, RecommandationFactory
from tests.factories import MissionFactory
from tests.recherche.conftest import soumettre_en_base

CHAMPS = {
    "id",
    "type",
    "objet_id",
    "mission_id",
    "mission_reference",
    "reference",
    "titre",
    "sous_titre",
    "texte",
    "audience",
    "annee",
    "date",
}


def test_les_cinq_types_de_r14() -> None:
    assert set(SOURCES) == {"MISSION", "CONSTAT", "RECOMMANDATION", "ACTION", "DOCUMENT"}


def test_document_constat_champs_et_audience(mission_lancee: Mission) -> None:
    constat = ConstatFactory(mission=mission_lancee, fait_constate="x" * 1500)
    doc = SOURCES["CONSTAT"].document(constat)
    assert doc is not None
    assert set(doc) == CHAMPS
    assert doc["id"] == f"CONSTAT-{constat.pk}"
    assert doc["mission_id"] == str(mission_lancee.pk)
    assert doc["mission_reference"] == "DAI/2026/M01"
    assert len(doc["texte"]) == 1000
    assert doc["audience"] == ["EQUIPE"]


def test_constat_soumis_ouvre_l_audience_audite_et_dg(mission_lancee: Mission) -> None:
    constat = ConstatFactory(mission=mission_lancee)
    soumettre_en_base(constat)
    doc = SOURCES["CONSTAT"].document(constat)
    assert doc is not None
    assert doc["audience"] == ["EQUIPE", "AUDITE", "DG"]


def test_recommandation_suit_l_audience_du_constat(mission_lancee: Mission) -> None:
    constat = ConstatFactory(mission=mission_lancee)
    reco = Recommandation.objects.get(constat=constat)
    assert SOURCES["RECOMMANDATION"].document(reco)["audience"] == ["EQUIPE"]  # type: ignore[index]
    soumettre_en_base(constat)
    reco = Recommandation.objects.get(pk=reco.pk)
    doc: Any = SOURCES["RECOMMANDATION"].document(reco)
    assert doc["audience"] == ["EQUIPE", "AUDITE", "DG"]
    assert doc["reference"] == f"{constat.reference}-{reco.ordre}"
    assert [t for t, _ in SOURCES["CONSTAT"].dependants(constat)] == ["RECOMMANDATION"]


def test_objets_supprimes_ou_mission_brouillon_non_indexables(
    mission_lancee: Mission, rai: Any
) -> None:
    constat = ConstatFactory(mission=mission_lancee)
    reco = Recommandation.objects.get(constat=constat)
    assert SOURCES["MISSION"].document(mission_lancee) is not None
    brouillon = MissionFactory(statut=StatutMission.BROUILLON)
    assert SOURCES["MISSION"].document(brouillon) is None
    reco.soft_delete(rai)
    assert SOURCES["RECOMMANDATION"].document(reco) is None
    constat.soft_delete(rai)
    assert SOURCES["CONSTAT"].document(constat) is None
    autre = RecommandationFactory(constat=ConstatFactory(mission=mission_lancee))
    Constat.objects.get(pk=autre.constat_id).soft_delete(rai)
    assert SOURCES["RECOMMANDATION"].document(Recommandation.objects.get(pk=autre.pk)) is None


def test_document_sans_version_prete_non_indexable(
    mission_lancee: Mission, creer_document: Any
) -> None:
    sans = creer_document(mission_lancee, "ORDRE_MISSION", mission_lancee, version=None)
    en_attente = creer_document(
        mission_lancee, "PLAN_ACTIONS", mission_lancee, version=StatutGeneration.EN_ATTENTE
    )
    assert SOURCES["DOCUMENT"].document(sans) is None
    assert SOURCES["DOCUMENT"].document(en_attente) is None


def test_document_indexe_sans_contenu(mission_lancee: Mission, creer_document: Any) -> None:
    document = creer_document(mission_lancee, "ORDRE_MISSION", mission_lancee)
    doc: Any = SOURCES["DOCUMENT"].document(document)
    assert doc is not None
    serialise = json.dumps(doc)
    version = document.versions.first()
    assert "contexte" not in doc
    assert version.contexte["mission"]["objectifs"] not in serialise
    assert document.numero in doc["texte"]
    assert doc["type"] == "DOCUMENT"
    assert doc["audience"] == ["EQUIPE", "AUDITE"]


def test_document_hors_liste_audite_reste_equipe(
    mission_lancee: Mission, creer_document: Any, settings: Any
) -> None:
    settings.RECHERCHE_TYPES_DOCUMENTS_AUDITE = ["PV_OUVERTURE"]
    document = creer_document(mission_lancee, "ORDRE_MISSION", mission_lancee)
    doc: Any = SOURCES["DOCUMENT"].document(document)
    assert doc["audience"] == ["EQUIPE"]


def test_rapport_diffuse_ouvre_audite_et_dg(mission_en_suivi: Mission, creer_document: Any) -> None:
    rapport = Rapport.objects.get(mission=mission_en_suivi)
    document = creer_document(mission_en_suivi, "RAPPORT_FINAL", rapport)
    doc: Any = SOURCES["DOCUMENT"].document(document)
    assert doc["audience"] == ["EQUIPE", "AUDITE", "DG"]
    autre_mission = MissionFactory(statut=StatutMission.EN_COMMUNICATION, reference="DAI/2026/M09")
    brouillon = RapportFactory(mission=autre_mission)
    assert brouillon.statut != StatutRapport.DIFFUSE
    non_diffuse = creer_document(autre_mission, "RAPPORT_FINAL", brouillon)
    doc = SOURCES["DOCUMENT"].document(non_diffuse)
    assert doc["audience"] == ["EQUIPE"]


def test_document_action_et_mission(mission_en_suivi: Mission) -> None:
    suivi = SuiviAction.objects.filter(mission=mission_en_suivi).first()
    doc: Any = SOURCES["ACTION"].document(suivi)
    assert doc["id"] == f"ACTION-{suivi.pk}"
    assert doc["titre"] == suivi.action.libelle
    assert doc["sous_titre"] == suivi.responsable.nom_complet
    assert doc["audience"] == ["EQUIPE", "AUDITE", "DG"]
    mission_doc: Any = SOURCES["MISSION"].document(mission_en_suivi)
    assert mission_doc["audience"] == ["EQUIPE", "AUDITE", "DG"]
    assert mission_doc["date"] <= timezone.now().date().isoformat()
    suivi.soft_delete(mission_en_suivi.created_by or suivi.responsable)
    assert SOURCES["ACTION"].document(suivi) is None
