from apps.documents.moteur.contrats import balises_racines, ecarts_contexte, empreinte_json

from .fabrique import CONTRAT_TEST


def test_balises_racines_incluent_les_blocs_communs() -> None:
    assert balises_racines(CONTRAT_TEST) == {"onea", "document", "mission", "equipe", "notes"}


def test_exemple_est_conforme() -> None:
    assert ecarts_contexte(CONTRAT_TEST, CONTRAT_TEST.exemple) == []


def test_ecarts_contexte() -> None:
    ctx = dict(CONTRAT_TEST.exemple)
    del ctx["notes"]
    ctx["intrus"] = "x"
    ctx["mission"] = {"reference": None, "titre": 3}
    texte = "\n".join(ecarts_contexte(CONTRAT_TEST, ctx))
    assert "notes" in texte  # manquant
    assert "intrus" in texte  # inattendu
    assert "mission.reference" in texte  # None
    assert "mission.titre" in texte  # mauvais type


def test_ecarts_contexte_liste_et_bloc_mal_formes() -> None:
    ctx = dict(CONTRAT_TEST.exemple)
    ctx["equipe"] = [{"nom": "A"}, "oups"]
    texte = "\n".join(ecarts_contexte(CONTRAT_TEST, ctx))
    assert "equipe[0].role" in texte
    assert "equipe[1]" in texte
    ctx["mission"] = "pas un bloc"
    assert "mission" in "\n".join(ecarts_contexte(CONTRAT_TEST, ctx))


def test_empreinte_json_independante_de_l_ordre() -> None:
    a = {"b": 1, "a": {"y": "é", "x": [1, 2]}}
    b = {"a": {"x": [1, 2], "y": "é"}, "b": 1}
    assert empreinte_json(a) == empreinte_json(b)
    assert len(empreinte_json(a)) == 64
    assert empreinte_json(a) != empreinte_json({"b": 2})
