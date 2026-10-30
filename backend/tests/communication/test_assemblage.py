from collections.abc import Callable
from typing import Any

import pytest

from apps.communication.models import Rapport
from apps.communication.services import assemblage
from apps.communication.services.assemblage import assembler, statut_derive
from apps.constats.models import Constat, StatutConstat
from apps.missions.models import Mission
from tests.communication.factories import RapportProvisoireFactory, ReponseRapportFactory
from tests.constats.factories import ConstatFactory, ReponseFactory
from tests.factories import EntretienFactory, MissionFactory
from tests.recommandations.factories import AcceptationFactory, ActionFactory

_RANG = {"ELEVE": 0, "MOYEN": 1, "FAIBLE": 2}


def _ordre_niveau_puis_reference(donnees: dict[str, Any]) -> Callable[[str], tuple[int, str]]:
    niveaux = {c["reference"]: c["niveau"] for c in donnees["constats"]}
    return lambda reference: (_RANG.get(niveaux[reference], 3), reference)


def _valider(constat: Constat) -> Constat:
    constat.soumettre()
    constat.save()
    constat.valider()
    constat.save()
    return constat


def test_assemblage_n_inclut_que_les_constats_valides(
    constat_valide: Constat, constat_soumis_non_valide: Constat, rapport_brouillon: Rapport
) -> None:
    donnees = assembler(rapport_brouillon, provisoire=False)
    refs = [c["reference"] for c in donnees["constats"]]
    assert constat_valide.reference in refs
    assert constat_soumis_non_valide.reference not in refs
    assert refs == sorted(refs, key=_ordre_niveau_puis_reference(donnees))


@pytest.fixture
def constat_eleve(mission_lancee: Mission) -> Constat:
    constat: Constat = ConstatFactory(mission=mission_lancee, probabilite=5, impact=5)
    return _valider(constat)


@pytest.fixture
def vingt_constats(mission_lancee: Mission) -> list[Constat]:
    return [_valider(ConstatFactory(mission=mission_lancee)) for _ in range(20)]


def test_assemblage_tri_niveau_decroissant_puis_reference(
    constat_valide: Constat, constat_eleve: Constat, rapport_brouillon: Rapport
) -> None:
    donnees = assembler(rapport_brouillon, provisoire=False)
    assert [c["reference"] for c in donnees["constats"]][0] == constat_eleve.reference
    assert [c["niveau"] for c in donnees["constats"]] == ["ELEVE", "FAIBLE"]
    assert donnees["totaux"]["par_niveau"] == {"FAIBLE": 1, "MOYEN": 0, "ELEVE": 1}
    assert donnees["totaux"]["par_priorite"]["HAUTE"] == 2


def test_assemblage_cles_stables(rapport_redige: Rapport) -> None:
    donnees = assembler(rapport_redige, provisoire=False)
    assert set(donnees) == {
        "mission",
        "rapport",
        "sections",
        "objectifs",
        "methodologie",
        "constats",
        "points_forts",
        "engagements",
        "entretiens",
        "totaux",
    }
    assert donnees["rapport"] == {"numero_version": 1, "corrige_de": None, "motif_correction": ""}
    assert donnees["sections"]["appreciation_libelle"] == "Maîtrise perfectible"
    constat = donnees["constats"][0]
    assert constat["causes"] == {"METHODES": ["Procédure non formalisée."]}
    assert constat["position_audite"] is None
    assert constat["reponse_direction"] is None
    assert constat["recommandations"][0]["statut_derive"] == "SANS_ACTION"


def test_assemblage_requetes_bornees(
    vingt_constats: list[Constat],
    rapport_brouillon: Rapport,
    django_assert_max_num_queries: Any,
) -> None:
    with django_assert_max_num_queries(10):
        donnees = assembler(rapport_brouillon, provisoire=False)
    assert len(donnees["constats"]) == len(vingt_constats)


def test_assemblage_aucune_autre_mission(rapport_redige: Rapport, constat_valide: Constat) -> None:
    autre = MissionFactory()
    etranger = ConstatFactory(mission=autre)
    _valider(etranger)
    refs = [c["reference"] for c in assembler(rapport_redige, provisoire=False)["constats"]]
    assert refs == [constat_valide.reference]
    assert etranger.statut == StatutConstat.VALIDE


def test_assemblage_provisoire_sans_reponses_ni_actions(
    rapport_redige: Rapport,
    constat_valide: Constat,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(assemblage, "_etat_engagement", lambda mission, user: "NON_CONFIRME")
    reco = constat_valide.recommandations.get()
    action = ActionFactory(recommandation=reco)
    provisoire = RapportProvisoireFactory(rapport=rapport_redige)
    ReponseRapportFactory(provisoire=provisoire, constat=constat_valide)
    ReponseFactory(constat=constat_valide, cycle=constat_valide.cycle)

    complet = assembler(rapport_redige, provisoire=False)["constats"][0]
    assert complet["reponse_direction"]["commentaire"].startswith("La direction")
    assert complet["reponse_direction"]["hors_delai"] is False
    assert complet["recommandations"][0]["actions"][0]["reference"] == action.reference
    assert complet["recommandations"][0]["actions"][0]["responsable"] == "Awa Ouedraogo"

    provisoire_donnees = assembler(rapport_redige, provisoire=True)
    constat = provisoire_donnees["constats"][0]
    assert constat["reponse_direction"] is None
    assert constat["position_audite"]["position"] == "ACCORD"
    assert constat["recommandations"][0]["actions"] == []
    assert constat["recommandations"][0]["acceptation"] is None
    assert provisoire_donnees["engagements"] == []
    assert provisoire_donnees["totaux"]["nb_actions"] == 0


def test_assemblage_engagements_et_acceptation(
    rapport_redige: Rapport, constat_valide: Constat, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(assemblage, "_etat_engagement", lambda mission, user: "CONFIRME")
    reco = constat_valide.recommandations.get()
    ActionFactory(recommandation=reco)
    donnees = assembler(rapport_redige, provisoire=False)
    assert donnees["engagements"] == [
        {"responsable": "Awa Ouedraogo", "nb_actions": 1, "etat": "CONFIRME"}
    ]
    assert donnees["constats"][0]["recommandations"][0]["statut_derive"] == "A_LANCER"
    assert donnees["totaux"]["nb_actions"] == 1


def test_assemblage_acceptation_du_risque(rapport_redige: Rapport, constat_valide: Constat) -> None:
    AcceptationFactory(recommandation=constat_valide.recommandations.get())
    reco = assembler(rapport_redige, provisoire=False)["constats"][0]["recommandations"][0]
    assert reco["statut_derive"] == "RISQUE_ACCEPTE"
    assert reco["acceptation"]["justification"].startswith("Coût")


def test_assemblage_entretiens_realises_seulement(rapport_redige: Rapport) -> None:
    from django.utils import timezone

    from apps.missions.models import StatutEntretien

    EntretienFactory(
        mission=rapport_redige.mission, statut=StatutEntretien.REALISE, realise_le=timezone.now()
    )
    EntretienFactory(mission=rapport_redige.mission)
    assert len(assembler(rapport_redige, provisoire=False)["entretiens"]) == 1


@pytest.mark.parametrize(
    ("statuts", "acceptee", "attendu"),
    [
        ([], True, "RISQUE_ACCEPTE"),
        ([], False, "SANS_ACTION"),
        (["A_LANCER"], False, "A_LANCER"),
        (["A_LANCER", "EN_COURS"], False, "EN_COURS"),
        (["REALISEE", "ABANDONNEE"], False, "REALISEE"),
        (["ABANDONNEE"], False, "A_LANCER"),
        (["REALISEE", "A_LANCER"], False, "EN_COURS"),
    ],
)
def test_statut_derive(statuts: list[str], acceptee: bool, attendu: str) -> None:
    assert statut_derive(statuts, acceptee=acceptee) == attendu
