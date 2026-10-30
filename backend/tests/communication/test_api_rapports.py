# ruff: noqa: F811, F401
"""API des rapports : rédaction, soumission, validation (confirmation explicite), renvoi."""

import pytest

from apps.communication.models import EvenementRapport, Rapport, StatutRapport
from apps.core.consultations import Consultation
from apps.missions.models import Mission, StatutEtape, StatutMission
from tests.accomplissement.fixtures_api import client_de
from tests.communication.fixtures_api import RAPPORTS, EquipeRapport, equipe
from tests.communication.support_t8 import (
    XV_A_XVII,
    admin,
    dg,
    rapport_soumis_reel,
    rapport_valide,
    signataire_factice,
)
from tests.missions.conftest import forcer_etapes

pytestmark = pytest.mark.django_db


def _url(rapport: Rapport, action: str = "") -> str:
    return f"{RAPPORTS}{rapport.pk}/{action}"


# --------------------------------------------------------------------------- création


def test_creation_preremplie(equipe: EquipeRapport) -> None:
    r = client_de(equipe.users["chef"]).post(
        RAPPORTS, {"mission": str(equipe.mission.pk)}, format="json"
    )
    assert r.status_code == 201, r.json()
    corps = r.json()
    assert corps["statut"] == "BROUILLON" and corps["numero_version"] == 1
    assert "MODIFIER" in corps["actions_possibles"]
    assert corps["version_finale"] is None and corps["diffusion"] is None
    assert [e["type"] for e in corps["evenements"]] == ["CREE"]
    # un seul rapport actif par mission : la règle métier répond 422
    again = client_de(equipe.users["rai"]).post(
        RAPPORTS, {"mission": str(equipe.mission.pk)}, format="json"
    )
    assert again.status_code == 422


@pytest.mark.parametrize(
    ("qui", "attendu"),
    [
        ("audite", 403),
        ("dg", 403),
        ("admin", 403),
        ("non_affecte", 404),
        ("audite_non_affecte", 403),
    ],
)
def test_creation_ordre_des_refus(equipe: EquipeRapport, qui: str, attendu: int) -> None:
    r = client_de(equipe.users[qui]).post(
        RAPPORTS, {"mission": str(equipe.mission.pk)}, format="json"
    )
    assert r.status_code == attendu


def test_creation_corps_invalide_400(equipe: EquipeRapport) -> None:
    client = client_de(equipe.users["chef"])
    assert client.post(RAPPORTS, {}, format="json").status_code == 400
    assert client.post(RAPPORTS, {"mission": "pas-un-uuid"}, format="json").status_code == 400


# --------------------------------------------------------------------------- sections


def test_modification_des_sections(equipe: EquipeRapport, rapport_redige: Rapport) -> None:
    client = client_de(equipe.users["chef"])
    r = client.patch(_url(rapport_redige), {"synthese": "Nouvelle synthèse"}, format="json")
    assert r.status_code == 200 and r.json()["synthese"] == "Nouvelle synthèse"
    assert (
        client.patch(_url(rapport_redige), {"appreciation_globale": "X"}, format="json").status_code
        == 400
    )
    # le statut ne se modifie jamais par PATCH : champ inconnu ignoré
    r = client.patch(_url(rapport_redige), {"statut": "VALIDE"}, format="json")
    assert r.status_code == 200 and r.json()["statut"] == "BROUILLON"
    # audité et DG : refus de rôle ; non affecté : 404
    assert (
        client_de(equipe.users["audite"]).patch(_url(rapport_redige), {}, format="json").status_code
        == 403
    )
    assert (
        client_de(equipe.users["dg"]).patch(_url(rapport_redige), {}, format="json").status_code
        == 403
    )
    assert (
        client_de(equipe.users["non_affecte"])
        .patch(_url(rapport_redige), {}, format="json")
        .status_code
        == 404
    )


def test_rapport_soumis_ne_se_modifie_plus_422(
    equipe: EquipeRapport, rapport_soumis_reel: Rapport
) -> None:
    r = client_de(equipe.users["chef"]).patch(
        _url(rapport_soumis_reel), {"synthese": "Trop tard"}, format="json"
    )
    assert r.status_code == 422


def test_apercu_equipe_seulement(equipe: EquipeRapport, rapport_redige: Rapport) -> None:
    r = client_de(equipe.users["auditeur"]).get(_url(rapport_redige, "preview/"))
    assert r.status_code == 200 and "constats" in r.json()
    assert (
        client_de(equipe.users["audite"]).get(_url(rapport_redige, "preview/")).status_code == 403
    )
    assert client_de(equipe.users["dg"]).get(_url(rapport_redige, "preview/")).status_code == 403
    assert (
        client_de(equipe.users["non_affecte"]).get(_url(rapport_redige, "preview/")).status_code
        == 404
    )


def test_detail_non_diffuse_journalise(equipe: EquipeRapport, rapport_redige: Rapport) -> None:
    avant = Consultation.objects.count()
    r = client_de(equipe.users["rai"]).get(_url(rapport_redige))
    assert r.status_code == 200 and r.json()["id"] == str(rapport_redige.pk)
    assert Consultation.objects.count() == avant + 1
    ligne = Consultation.objects.latest("created_at")
    assert (ligne.object_id, ligne.action) == (rapport_redige.pk, "CONSULTATION")


def test_audite_403_sur_rapport_interne(equipe: EquipeRapport, rapport_redige: Rapport) -> None:
    client = client_de(equipe.users["audite"])
    assert client.get(_url(rapport_redige)).status_code == 403
    # la liste de la mission ne lui montre que les rapports diffusés
    liste = client.get(f"{RAPPORTS}?mission={equipe.mission.pk}")
    assert liste.status_code == 200 and liste.json()["count"] == 0


# --------------------------------------------------------------------------- soumission, validation


def test_soumission_par_le_chef(equipe: EquipeRapport, rapport_redige: Rapport) -> None:
    forcer_etapes(equipe.mission, XV_A_XVII)
    assert (
        client_de(equipe.users["auditeur"]).post(_url(rapport_redige, "submit/")).status_code == 403
    )
    assert (
        client_de(equipe.users["audite"]).post(_url(rapport_redige, "submit/")).status_code == 403
    )
    r = client_de(equipe.users["chef"]).post(_url(rapport_redige, "submit/"))
    assert r.status_code == 200, r.json()
    assert r.json()["statut"] == "SOUMIS" and r.json()["actions_possibles"] == []
    assert len(r.json()["empreinte_soumise"]) == 64


def test_validate_sans_confirme_400(equipe: EquipeRapport, rapport_soumis_reel: Rapport) -> None:
    rai = client_de(equipe.users["rai"])
    for corps in ({}, {"confirme": False}, {"confirme": "false"}, {"confirme": None}):
        r = rai.post(_url(rapport_soumis_reel, "validate/"), corps, format="json")
        assert r.status_code == 400, corps
        assert "Cochez la case de confirmation." in str(r.json()) or "confirme" in str(r.json())
    rapport_soumis_reel.refresh_from_db()
    assert rapport_soumis_reel.statut == StatutRapport.SOUMIS
    assert rapport_soumis_reel.valide_par_id is None


def test_validate_refus_avant_confirmation(
    equipe: EquipeRapport, rapport_soumis_reel: Rapport
) -> None:
    """Le droit (403) est évalué avant le sérialiseur (400) : chef et audité sans `confirme`."""
    url = _url(rapport_soumis_reel, "validate/")
    assert client_de(equipe.users["chef"]).post(url, {}, format="json").status_code == 403
    assert client_de(equipe.users["audite"]).post(url, {}, format="json").status_code == 403
    assert client_de(equipe.users["dg"]).post(url, {}, format="json").status_code == 403
    assert client_de(equipe.users["non_affecte"]).post(url, {}, format="json").status_code == 404
    assert (
        client_de(equipe.users["chef"]).post(url, {"confirme": True}, format="json").status_code
        == 403
    )


def test_validation_confirmee(equipe: EquipeRapport, rapport_soumis_reel: Rapport) -> None:
    rai = client_de(equipe.users["rai"])
    texte = rai.get(_url(rapport_soumis_reel, "validation-text/"))
    assert texte.status_code == 200
    assert "valide le rapport d'audit" in texte.json()["texte"]
    assert texte.json()["confirmation_requise"] is True
    r = rai.post(_url(rapport_soumis_reel, "validate/"), {"confirme": True}, format="json")
    assert r.status_code == 200, r.json()
    corps = r.json()
    assert corps["statut"] == "VALIDE" and corps["confirmation_validation"]["empreinte"]
    assert corps["mode_signature"] == "CONFIRMATION"
    assert corps["signature_electronique_requise"] is False
    # deuxième validation : le rapport n'est plus soumis (422)
    again = rai.post(_url(rapport_soumis_reel, "validate/"), {"confirme": True}, format="json")
    assert again.status_code == 422


def test_texte_de_validation_reserve_au_rai(
    equipe: EquipeRapport, rapport_soumis_reel: Rapport, rapport_redige: Rapport
) -> None:
    url = _url(rapport_soumis_reel, "validation-text/")
    assert client_de(equipe.users["chef"]).get(url).status_code == 403
    assert client_de(equipe.users["audite"]).get(url).status_code == 403
    assert client_de(equipe.users["rai"]).get(url).status_code == 200


def test_renvoi_avec_motif(equipe: EquipeRapport, rapport_soumis_reel: Rapport) -> None:
    url = _url(rapport_soumis_reel, "return/")
    assert (
        client_de(equipe.users["chef"]).post(url, {"motif": "Non."}, format="json").status_code
        == 403
    )
    rai = client_de(equipe.users["rai"])
    assert rai.post(url, {}, format="json").status_code == 400
    assert rai.post(url, {"motif": "  "}, format="json").status_code == 422
    r = rai.post(url, {"motif": "Compléter la conclusion."}, format="json")
    assert r.status_code == 200, r.json()
    assert (
        r.json()["statut"] == "RENVOYE" and r.json()["motif_renvoi"] == "Compléter la conclusion."
    )
    assert EvenementRapport.objects.filter(rapport=rapport_soumis_reel, type="RENVOYE").exists()


# --------------------------------------------------------------------------- concordance, gel


def _concorde(actions: list[str], nom: str, statut: int, qui: str) -> None:
    """Action annoncée : la route n'est jamais refusée par un droit ; absente : 403 ou 422."""
    if nom in actions:
        assert statut not in (403, 404), (qui, nom, statut)
    else:
        assert statut in (403, 422), (qui, nom, statut)


def test_actions_possibles_concorde_avec_les_routes(
    equipe: EquipeRapport, rapport_redige: Rapport
) -> None:
    forcer_etapes(equipe.mission, XV_A_XVII)
    for qui in ("rai", "chef", "auditeur"):
        client = client_de(equipe.users[qui])
        actions = client.get(_url(rapport_redige)).json()["actions_possibles"]
        patch = client.patch(_url(rapport_redige), {"synthese": f"Par {qui}"}, format="json")
        _concorde(actions, "MODIFIER", patch.status_code, qui)
    # soumission : seul le chef l'annonce, et la route répond
    for qui in ("rai", "auditeur", "chef"):  # le chef en dernier : il fige le rapport
        client = client_de(equipe.users[qui])
        actions = client.get(_url(rapport_redige)).json()["actions_possibles"]
        soumis = client.post(_url(rapport_redige, "submit/"))
        _concorde(actions, "SOUMETTRE", soumis.status_code, qui)
        assert (soumis.status_code == 200) == ("SOUMETTRE" in actions), qui
    # validation et renvoi : le RAI (qui n'a pas soumis) les annonce ; le chef non
    for qui, attendu in (("chef", False), ("rai", True)):
        client = client_de(equipe.users[qui])
        actions = client.get(_url(rapport_redige)).json()["actions_possibles"]
        assert ("VALIDER" in actions) is attendu and ("RENVOYER" in actions) is attendu
        renvoi = client.post(_url(rapport_redige, "return/"), {"motif": "Revoir."}, format="json")
        _concorde(actions, "RENVOYER", renvoi.status_code, qui)
        if attendu:
            assert renvoi.status_code == 200  # renvoyé : il faut re-soumettre pour valider


def test_api_gel_422_routes_lot7(equipe: EquipeRapport, rapport_redige: Rapport) -> None:
    """Mission hors communication : le droit reste évalué avant le gel (403/404), puis 422."""
    forcer_etapes(equipe.mission, XV_A_XVII)
    Mission.objects.filter(pk=equipe.mission.pk).update(statut=StatutMission.EN_ACCOMPLISSEMENT)
    chef, rai = client_de(equipe.users["chef"]), client_de(equipe.users["rai"])
    assert (
        chef.patch(_url(rapport_redige), {"synthese": "Trop tard"}, format="json").status_code
        == 422
    )
    assert chef.post(_url(rapport_redige, "submit/")).status_code == 422
    assert chef.post(_url(rapport_redige, "transmit-draft/"), {}, format="json").status_code == 422
    assert rai.post(RAPPORTS, {"mission": str(equipe.mission.pk)}, format="json").status_code == 422
    actions = chef.get(_url(rapport_redige)).json()["actions_possibles"]
    assert actions == []
    assert (
        client_de(equipe.users["audite"]).patch(_url(rapport_redige), {}, format="json").status_code
        == 403
    )
    assert (
        client_de(equipe.users["non_affecte"])
        .patch(_url(rapport_redige), {}, format="json")
        .status_code
        == 404
    )
