# ruff: noqa: F811, F401, F403
"""API des actions suivies : lecture, filtres, transitions, refus, concordance des droits."""

import datetime
from typing import Any

import pytest
from django.db import transaction
from django.utils import timezone

from apps.missions.models import Mission, StatutEtape, StatutMission
from apps.suivi.models import EvenementSuivi, StatutSuivi, SuiviAction
from apps.users.models import Role
from tests.accomplissement.fixtures_api import client_de
from tests.factories import make_user
from tests.missions.conftest import affecter, forcer_etapes
from tests.recommandations.factories import ActionFactory
from tests.suivi.factories import PreuveFactory, SuiviActionFactory
from tests.suivi.fixtures_api import *
from tests.suivi.fixtures_api import ACTIONS, PREUVES, REPORTS, EquipeSuivi

pytestmark = pytest.mark.django_db


def _suivi_en_plus(e: EquipeSuivi, **kw: Any) -> SuiviAction:
    """Nouveau suivi : l'étape XVI est rouverte le temps de créer l'action (garde du lot 7)."""
    forcer_etapes(e.mission, {16: StatutEtape.EN_COURS})
    suivi = SuiviActionFactory(
        action=ActionFactory(
            recommandation=kw.pop("recommandation", e.suivi.recommandation),
            responsable=kw.pop("responsable", e.users["responsable"]),
            proposee_par=e.users["chef"],
            **kw,
        )
    )
    forcer_etapes(e.mission, {16: StatutEtape.VALIDEE})
    return suivi


def _get(e: EquipeSuivi, qui: str, url: str = ACTIONS, **params: Any) -> Any:
    return client_de(e.users[qui]).get(url, params)


def _post(e: EquipeSuivi, qui: str, suivi: SuiviAction, route: str, corps: dict[str, Any]) -> Any:
    return client_de(e.users[qui]).post(f"{ACTIONS}{suivi.pk}/{route}/", corps, format="json")


def test_liste_forme_et_requetes_bornees(
    equipe_suivi: EquipeSuivi, django_assert_max_num_queries: Any
) -> None:
    e = equipe_suivi
    for _ in range(57):
        _suivi_en_plus(e)
    assert SuiviAction.objects.filter(mission=e.mission).count() == 60
    for qui in ("auditeur", "rai", "responsable"):
        client = client_de(e.users[qui])
        with django_assert_max_num_queries(6):
            reponse = client.get(ACTIONS, {"page_size": 60})
        assert reponse.status_code == 200
        assert reponse.json()["count"] == 60
        assert len(reponse.json()["results"]) == 60


def test_representation_d_une_action(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    corps = _get(e, "rai", f"{ACTIONS}{s.pk}/").json()
    assert corps["id"] == str(s.pk)
    assert corps["mission"] == {
        "id": str(e.mission.pk),
        "reference": e.mission.reference,
        "titre": e.mission.titre,
        "statut": "RAPPORT_DIFFUSE",
    }
    assert corps["statut"] == "A_LANCER"
    assert corps["en_retard"] is False
    assert corps["jours_retard"] is None
    assert corps["responsable"]["id"] == e.users["responsable"].pk
    assert corps["nombre_preuves"] == 0
    assert corps["demande_report_en_attente"] is None
    assert corps["action_libelle"] == s.action.libelle
    assert corps["recommandation"]["id"] == str(s.recommandation_id)
    assert corps["entite"]["id"] == str(s.entite_id)
    assert "DEMARRER" in corps["actions_possibles"]


def test_filtres_en_retard_mine_statut_echeance(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    reco = e.suivi.recommandation
    hier = datetime.date.today() - datetime.timedelta(days=10)
    tard = _suivi_en_plus(e, echeance=hier)
    SuiviAction.objects.filter(pk=tard.pk).update(statut=StatutSuivi.EN_COURS)
    autre = make_user(Role.AUDITE)
    affecter(e.mission, autre, "AUDITE")
    propre = _suivi_en_plus(e, responsable=autre)

    def ids(qui: str, **params: Any) -> set[str]:
        reponse = _get(e, qui, **params)
        assert reponse.status_code == 200, reponse.content
        return {r["id"] for r in reponse.json()["results"]}

    assert ids("rai", en_retard="true") == {str(tard.pk)}
    assert str(tard.pk) not in ids("rai", en_retard="false")
    ligne = _get(e, "rai", f"{ACTIONS}{tard.pk}/").json()
    assert ligne["en_retard"] is True
    assert ligne["jours_retard"] == 10
    assert ids("rai", mine="true") == set()
    assert ids("rai", responsable=autre.pk) == {str(propre.pk)}
    assert str(propre.pk) not in ids("responsable", mine="true")
    assert ids("rai", statut=["EN_COURS", "REALISEE"]) == {str(tard.pk)}
    assert ids("rai", echeance_avant=hier.isoformat()) == {str(tard.pk)}
    assert str(tard.pk) not in ids(
        "rai", echeance_apres=(hier + datetime.timedelta(days=1)).isoformat()
    )
    assert ids("rai", recommandation=reco.pk) >= {str(tard.pk), str(propre.pk)}
    assert ids("rai", entite=tard.entite_id)
    assert ids("rai", annee=e.mission.annee)
    assert ids("rai", annee=1999 + 2) == set()
    assert _get(e, "rai", echeance_avant="31/12/2026").status_code == 400
    ordre = _get(e, "rai", ordering="-echeance").json()["results"]
    assert [r["echeance"] for r in ordre] == sorted((r["echeance"] for r in ordre), reverse=True)


def test_parcours_complet_par_l_api(equipe_suivi: EquipeSuivi, stockage_temp: Any) -> None:
    e = equipe_suivi
    s = e.suivi
    r = _post(e, "responsable", s, "start", {})
    assert r.status_code == 200 and r.json()["statut"] == "EN_COURS"
    # preuve absente : règle métier 422 ; commentaire manquant : sérialiseur 400 (avant la règle)
    assert _post(e, "responsable", s, "declare-done", {}).status_code == 400
    refus = _post(e, "responsable", s, "declare-done", {"commentaire": "Fait."})
    assert refus.status_code == 422
    assert "preuve" in refus.json()["detail"].lower()
    PreuveFactory(suivi=s, deposee_par=e.users["responsable"])
    r = _post(e, "responsable", s, "declare-done", {"commentaire": "Fait."})
    assert r.status_code == 200 and r.json()["statut"] == "REALISEE"
    assert r.json()["declaree_par"]["id"] == e.users["responsable"].pk
    assert r.json()["nombre_preuves"] == 1
    r = _post(e, "auditeur", s, "reject", {"motif": "Preuve insuffisante."})
    assert r.status_code == 200 and r.json()["statut"] == "EN_COURS"
    assert r.json()["motif_dernier_rejet"] == "Preuve insuffisante."
    _post(e, "responsable", s, "declare-done", {"commentaire": "Complété."})
    r = _post(e, "auditeur", s, "verify", {"commentaire": "Conforme."})
    assert r.status_code == 200 and r.json()["statut"] == "VERIFIEE"
    assert r.json()["verifiee_par"]["id"] == e.users["auditeur"].pk
    r = _post(e, "rai", s, "close", {})
    assert r.status_code == 200 and r.json()["statut"] == "CLOTUREE"
    assert r.json()["actions_possibles"] == ["ROUVRIR", "COMMENTER"]
    r = _post(e, "rai", s, "reopen", {"motif": "Preuve contestée."})
    assert r.status_code == 200 and r.json()["statut"] == "EN_COURS"
    r = _post(e, "audite", s, "comment", {"texte": "Point de situation."})
    assert r.status_code == 200
    evenements = _get(e, "dg", f"{ACTIONS}{s.pk}/events/").json()
    types = [ev["type"] for ev in evenements]
    assert types[0] == "DEMARRE" and types[-1] == "COMMENTAIRE"
    assert types.count("DECLAREE_REALISEE") == 2
    assert set(evenements[0]) == {
        "id",
        "type",
        "par",
        "pour_compte_de",
        "le",
        "statut_avant",
        "statut_apres",
        "texte",
    }


def test_abandon_par_l_api(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    assert _post(e, "responsable", s, "propose-abandon", {}).status_code == 400
    r = _post(e, "responsable", s, "propose-abandon", {"justification": "Obsolète."})
    assert r.status_code == 200 and r.json()["statut"] == "ABANDON_PROPOSE"
    assert r.json()["justification_abandon"] == "Obsolète."
    assert _post(e, "rai", s, "accept-abandon", {}).status_code == 400
    r = _post(e, "rai", s, "accept-abandon", {"commentaire": "D'accord."})
    assert r.status_code == 200 and r.json()["statut"] == "ABANDONNEE"


def test_saisie_pour_compte_par_le_rai(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    sans = _post(e, "rai", s, "start", {})
    assert sans.status_code == 422
    assert "commentaire" in sans.json()["errors"]
    r = _post(e, "rai", s, "start", {"commentaire": "Appel téléphonique."})
    assert r.status_code == 200
    evenement = EvenementSuivi.objects.filter(suivi=s).order_by("le").last()
    assert evenement.pour_compte_de_id == e.users["responsable"].pk
    assert evenement.texte.startswith("Saisi par le RAI pour le compte de ")


def test_ordre_des_refus(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    # rôle global 403 avant tout (même pour une action inexistante)
    assert _post(e, "admin", s, "start", {}).status_code == 403
    # objet invisible : 404 avant le droit et le sérialiseur
    assert _post(e, "non_affecte", s, "reject", {}).status_code == 404
    assert _post(e, "audite_non_affecte", s, "start", {}).status_code == 404
    # droit 403 avant le sérialiseur 400
    assert _post(e, "dg", s, "reject", {}).status_code == 403
    assert _post(e, "responsable", s, "verify", {}).status_code == 403
    # sérialiseur 400 avant la règle 422
    assert _post(e, "rai", s, "reject", {}).status_code == 400
    # règle métier 422 : l'action n'est pas réalisée
    assert _post(e, "rai", s, "verify", {}).status_code == 422
    assert _post(e, "rai", s, "reject", {"motif": "x"}).status_code == 422


def test_declarant_ne_verifie_pas(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    PreuveFactory(suivi=s, deposee_par=e.users["responsable"])
    r = _post(e, "rai", s, "declare-done", {"commentaire": "Saisie pour compte."})
    assert r.status_code == 200
    refus = _post(e, "rai", s, "verify", {})
    assert refus.status_code == 422
    assert "déclaré" in refus.json()["detail"]
    assert "VERIFIER" not in r.json()["actions_possibles"]
    assert _post(e, "auditeur", s, "verify", {}).status_code == 200


def test_changer_responsable(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    nouveau = make_user(Role.AUDITE)
    patch = lambda qui, corps: client_de(e.users[qui]).patch(  # noqa: E731
        f"{ACTIONS}{s.pk}/", corps, format="json"
    )
    assert patch("responsable", {"responsable": nouveau.pk}).status_code == 403
    assert patch("chef", {"responsable": nouveau.pk}).status_code == 403
    assert patch("non_affecte", {"responsable": nouveau.pk}).status_code == 404
    assert patch("rai", {}).status_code == 400
    assert patch("rai", {"responsable": 999_999}).status_code == 400
    refus = patch("rai", {"responsable": nouveau.pk})
    assert refus.status_code == 422
    assert "Affectez d'abord" in refus.json()["errors"]["responsable"][0]
    affecter(e.mission, nouveau, "AUDITE")
    r = patch("rai", {"responsable": nouveau.pk})
    assert r.status_code == 200 and r.json()["responsable"]["id"] == nouveau.pk


# Code de droit -> (route, corps) ; `{}` : corps valide pour les routes sans champ obligatoire.
ROUTES_PAR_CODE: dict[str, tuple[str, dict[str, Any]]] = {
    "DEMARRER": ("start", {"commentaire": "Pour compte."}),
    "DECLARER_REALISEE": ("declare-done", {"commentaire": "Fait."}),
    "PROPOSER_ABANDON": ("propose-abandon", {"justification": "Obsolète."}),
    "VERIFIER": ("verify", {}),
    "REJETER": ("reject", {"motif": "Insuffisant."}),
    "CLOTURER": ("close", {}),
    "ACCEPTER_ABANDON": ("accept-abandon", {"commentaire": "Oui."}),
    "ROUVRIR": ("reopen", {"motif": "Contesté."}),
    "COMMENTER": ("comment", {"texte": "Note."}),
}


def _appeler(e: EquipeSuivi, qui: str, s: SuiviAction, code: str) -> int:
    client = client_de(e.users[qui])
    if code in ROUTES_PAR_CODE:
        route, corps = ROUTES_PAR_CODE[code]
        return int(client.post(f"{ACTIONS}{s.pk}/{route}/", corps, format="json").status_code)
    if code == "CHANGER_RESPONSABLE":
        return int(
            client.patch(
                f"{ACTIONS}{s.pk}/", {"responsable": s.responsable_id}, format="json"
            ).status_code
        )
    assert code == "DEMANDER_REPORT"
    corps = {
        "action": str(s.pk),
        "nouvelle_echeance": (s.echeance + datetime.timedelta(days=30)).isoformat(),
        "motif": "Marché retardé.",
    }
    return int(client.post(REPORTS, corps, format="json").status_code)


@pytest.mark.parametrize("etat", ["A_LANCER", "REALISEE", "CLOTUREE"])
def test_actions_possibles_concorde_avec_les_routes(equipe_suivi: EquipeSuivi, etat: str) -> None:
    from apps.suivi.droits import CODES

    e = equipe_suivi
    s = e.suivi
    PreuveFactory(suivi=s, deposee_par=e.users["responsable"])  # précondition de la déclaration
    if etat != "A_LANCER":
        SuiviAction.objects.filter(pk=s.pk).update(
            statut=StatutSuivi.REALISEE if etat == "REALISEE" else StatutSuivi.CLOTUREE,
            declaree_par=e.users["responsable"],
            declaree_le=timezone.now(),
        )
        s.refresh_from_db()
    for qui in (
        "rai",
        "chef",
        "superviseur",
        "auditeur",
        "auditeur_non_leve",
        "responsable",
        "audite",
    ):
        codes = _get(e, qui, f"{ACTIONS}{s.pk}/").json()["actions_possibles"]
        for code in CODES:
            if code == "DEPOSER_PREUVE":
                continue  # route multipart : couverte par test_api_preuves
            with transaction.atomic():
                statut = _appeler(e, qui, s, code)
                transaction.set_rollback(True)
            if code in codes:
                assert statut in (200, 201), (etat, qui, code, statut)
            else:
                assert statut in (403, 422), (etat, qui, code, statut)


def test_gel_mission_cloturee_422_sur_toutes_les_routes(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    s = e.suivi
    Mission.objects.filter(pk=e.mission.pk).update(statut=StatutMission.CLOTUREE)
    assert _get(e, "rai", f"{ACTIONS}{s.pk}/").json()["actions_possibles"] == []
    for code in (
        "DEMARRER",
        "COMMENTER",
        "CHANGER_RESPONSABLE",
        "DEMANDER_REPORT",
        "PROPOSER_ABANDON",
    ):
        assert _appeler(e, "rai", s, code) == 422, code
    for qui in ("rai", "responsable"):
        assert _appeler(e, qui, s, "COMMENTER") == 422


def test_mission_suspendue_hors_visibilite_404(equipe_suivi: EquipeSuivi) -> None:
    """Une mission suspendue sort de la visibilité R11 : 404, jamais une écriture."""
    e = equipe_suivi
    s = e.suivi
    Mission.objects.filter(pk=e.mission.pk).update(statut=StatutMission.SUSPENDUE)
    assert _post(e, "rai", s, "start", {"commentaire": "x"}).status_code == 404
    assert _get(e, "rai", f"{ACTIONS}{s.pk}/").status_code == 404
