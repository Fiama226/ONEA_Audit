"""Service de recherche : aucune fuite, second filtre en base, validation, indisponibilité."""

from typing import Any

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.communication.models import Rapport
from apps.constats.models import Constat, StatutConstat
from apps.missions.models import Mission
from apps.recherche import client, tasks
from apps.recherche.client import Hit
from apps.recherche.exceptions import RechercheIndisponibleError
from apps.recherche.services import nettoyer_requete, rechercher, reconcilier_index
from apps.suivi.models import SuiviAction
from apps.users.models import User
from tests.factories import DirectionFactory


@pytest.mark.parametrize(
    "acteur, attendu",
    [
        ("rai", {"CONSTAT-brouillon", "CONSTAT-soumis"}),
        ("auditeur_mission", {"CONSTAT-brouillon", "CONSTAT-soumis"}),
        ("autre_auditeur", set()),
        ("audite_affecte", {"CONSTAT-soumis"}),
        ("dg", set()),  # mission non diffusée
        ("admin", set()),
    ],
)
def test_recherche_ne_fuit_pas_hors_perimetre(
    index_peuple: dict[str, str], acteur: str, attendu: set[str], request: Any
) -> None:
    user = request.getfixturevalue(acteur)
    ids = {h.id for h in rechercher(user, "Rapprochement bancaire", types=["CONSTAT"]).resultats}
    assert ids == {index_peuple[a] for a in attendu}


def test_audite_d_une_autre_direction_ne_voit_rien(
    index_peuple: dict[str, str], audite_affecte: User
) -> None:
    autre = DirectionFactory()
    User.objects.filter(pk=audite_affecte.pk).update(direction_code=autre.code)
    audite_affecte.refresh_from_db()
    # Le premier filtre laisse passer (même mission, audience AUDITE) ; le second filtre rejette.
    assert rechercher(audite_affecte, "Rapprochement bancaire", types=["CONSTAT"]).resultats == []


def test_second_filtre_retire_les_hits_perimes(
    index_peuple: dict[str, str],
    audite_affecte: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    demandes: list[tuple[str, str]] = []
    monkeypatch.setattr(
        tasks.indexer_objet, "delay", lambda type_, pk: demandes.append((type_, pk))
    )
    soumis = Constat.objects.get(pk=index_peuple["CONSTAT-soumis"].removeprefix("CONSTAT-"))
    # Écriture en masse sans réindexation : le constat est renvoyé, l'index le croit encore soumis.
    Constat.objects.filter(pk=soumis.pk).update(statut=StatutConstat.RENVOYE)
    res = rechercher(audite_affecte, "Rapprochement bancaire")
    assert res.resultats == []
    assert ("CONSTAT", str(soumis.pk)) in demandes


def test_hit_forge_ou_hors_types_est_rejete(
    index_peuple: dict[str, str], rai: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Faux:
        def rechercher(self, q: str, *, filtre: str, limite: int) -> list[Hit]:
            return [
                Hit("CONSTAT-pas-un-uuid", "CONSTAT", "pas-un-uuid", None, "t", "", ""),
                Hit("INCONNU-1", "INCONNU", "1", None, "t", "", ""),
                Hit("MISSION-" + "0" * 32, "MISSION", "0" * 32, None, "t", "", ""),
            ]

    monkeypatch.setattr("apps.recherche.services.moteur", lambda: Faux())
    monkeypatch.setattr(tasks.indexer_objet, "delay", lambda *a: None)
    assert rechercher(rai, "Rapprochement").resultats == []


def test_filtre_types_et_types_inconnus(index_peuple: dict[str, str], rai: User) -> None:
    tous = rechercher(rai, "Rapprochement bancaire").resultats
    assert {h.type for h in tous} >= {"CONSTAT"}
    assert rechercher(rai, "Rapprochement bancaire", types=["MISSION"]).resultats == []
    with pytest.raises(ValidationError) as exc:
        rechercher(rai, "Rapprochement", types=['CONSTAT" OR audience = "DG'])
    assert "types" in exc.value.detail  # type: ignore[operator]


def test_plus_sans_total(index_peuple: dict[str, str], rai: User) -> None:
    res = rechercher(rai, "Rapprochement bancaire", types=["CONSTAT"], limite=1)
    assert len(res.resultats) == 1
    assert res.plus is True
    assert not hasattr(res, "total")
    complet = rechercher(rai, "Rapprochement bancaire", types=["CONSTAT"], limite=2)
    assert len(complet.resultats) == 2
    assert complet.plus is False


def test_surlignage_par_marqueurs(index_peuple: dict[str, str], rai: User) -> None:
    hit = rechercher(rai, "rapprochement", types=["CONSTAT"]).resultats[0]
    assert client.MARQUEUR_DEBUT in hit.titre
    assert "<" not in hit.titre.replace(client.MARQUEUR_DEBUT, "")


class MoteurEspion:
    def __init__(self) -> None:
        self.appels = 0

    def rechercher(self, q: str, *, filtre: str, limite: int) -> list[Hit]:
        self.appels += 1
        return []


def test_admin_et_liste_vide_sans_appel_au_moteur(
    mission_lancee: Mission,
    admin: User,
    dg: User,
    autre_auditeur: User,
    autre_audite: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    espion = MoteurEspion()
    monkeypatch.setattr("apps.recherche.services.moteur", lambda: espion)
    for user in (admin, dg, autre_auditeur, autre_audite):
        res = rechercher(user, "Rapprochement")
        assert res.resultats == [] and res.plus is False
    assert espion.appels == 0


@pytest.mark.parametrize("q", ["", "a", "  a  ", "\u0002\u0003", "x" * 201])
def test_requete_trop_courte_ou_trop_longue(rai: User, q: str) -> None:
    with pytest.raises(ValidationError) as exc:
        rechercher(rai, q)
    assert "q" in exc.value.detail  # type: ignore[operator]


def test_requete_nettoyee() -> None:
    assert nettoyer_requete("  Rapprochement \t\n bancaire\u0002\u0003 ") == (
        "Rapprochement bancaire"
    )


def test_requete_sans_marqueur_injectable(index_peuple: dict[str, str], rai: User) -> None:
    res = rechercher(rai, "rappro\u0002chement")
    assert res.resultats  # les marqueurs sont retirés avant la recherche


def test_moteur_indisponible_donne_503(rai: User, monkeypatch: pytest.MonkeyPatch) -> None:
    class Panne:
        def rechercher(self, *a: Any, **k: Any) -> list[Hit]:
            raise RechercheIndisponibleError

    monkeypatch.setattr("apps.recherche.services.moteur", lambda: Panne())
    with pytest.raises(RechercheIndisponibleError) as exc:
        rechercher(rai, "Rapprochement", types=["DOCUMENT"])
    assert exc.value.status_http == 503


def test_moteur_indisponible_repli_sur_les_missions(
    rai: User, mission_lancee: Mission, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Panne:
        def rechercher(self, *a: Any, **k: Any) -> list[Hit]:
            raise RechercheIndisponibleError

    monkeypatch.setattr("apps.recherche.services.moteur", lambda: Panne())
    res = rechercher(rai, mission_lancee.titre[:8])
    assert res.degrade is True
    assert [h.objet_id for h in res.resultats] == [str(mission_lancee.pk)]


# ---------------------------------------------------------------- missions, actions, DG


def test_dg_voit_les_missions_diffusees_leurs_actions_et_le_rapport(
    mission_en_suivi: Mission, dg: User, creer_document: Any
) -> None:
    rapport = Rapport.objects.get(mission=mission_en_suivi)
    creer_document(mission_en_suivi, "RAPPORT_FINAL", rapport)
    creer_document(mission_en_suivi, "ORDRE_MISSION", mission_en_suivi)
    reconcilier_index()
    types = {h.type for h in rechercher(dg, "DAI/2026/M01").resultats}
    assert "MISSION" in types and "DOCUMENT" in types
    documents = [h for h in rechercher(dg, "DAI/2026", types=["DOCUMENT"]).resultats]
    # Seul le rapport diffusé est lisible par le DG, jamais l'ordre de mission.
    assert [h.titre for h in documents] == ["Rapport d'audit"]
    actions = rechercher(dg, SuiviAction.objects.first().action.libelle[:12], types=["ACTION"])
    assert actions.resultats


def test_audite_ne_lit_que_les_documents_autorises(
    mission_en_suivi: Mission, responsable: User, creer_document: Any
) -> None:
    Mission.objects.filter(pk=mission_en_suivi.pk).update(ordre_mission_emis_le=timezone.now())
    rapport = Rapport.objects.get(mission=mission_en_suivi)
    creer_document(mission_en_suivi, "RAPPORT_FINAL", rapport)
    creer_document(mission_en_suivi, "FICHE_SUIVI_MISSION", mission_en_suivi)
    reconcilier_index()
    res = rechercher(responsable, "DAI/2026/M01", types=["DOCUMENT"]).resultats
    assert [h.titre for h in res] == ["Rapport d'audit"]
