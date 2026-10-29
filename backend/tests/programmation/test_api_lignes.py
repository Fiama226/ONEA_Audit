from datetime import date
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.programmation.models import LigneProgramme
from apps.users.models import Role
from tests.factories import make_user
from tests.referentiel.typed import direction as make_direction
from tests.referentiel.typed import objet as make_objet
from tests.referentiel.typed import processus as make_processus

from .factories import ligne, programme

URL = "/api/v1/audit-plan-lines/"


@pytest.fixture
def rai_client(api_client: APIClient, db: None) -> APIClient:
    api_client.force_authenticate(make_user(Role.RAI))
    return api_client


def _corps(p: Any, proc: Any, **extra: Any) -> dict[str, Any]:
    base = {
        "programme": str(p.id),
        "titre": "Achats",
        "type": "ASSURANCE",
        "processus": str(proc.id),
        "debut_prevu": "2026-03-02",
        "fin_prevue": "2026-04-30",
    }
    base.update(extra)
    return base


def test_creer_ligne_numerotee(rai_client: APIClient) -> None:
    p, proc = programme(annee=2026), make_processus()
    d = make_direction()
    r = rai_client.post(
        URL, _corps(p, proc, entites=[str(d.id)], charge_prevue_jours="5.5"), format="json"
    )
    assert r.status_code == 201, r.content
    corps = r.json()
    assert corps["numero"] == 1
    assert corps["trimestre"] == 1
    assert corps["charge_prevue_jours"] == "5.5"
    assert [e["id"] for e in corps["entites_detail"]] == [str(d.id)]
    assert "entites" not in corps
    r2 = rai_client.post(URL, _corps(p, proc), format="json")
    assert r2.json()["numero"] == 2


def test_objet_autre_processus_422_sur_le_champ(rai_client: APIClient) -> None:
    p, proc = programme(annee=2026), make_processus()
    objet = make_objet()
    r = rai_client.post(URL, _corps(p, proc, objet_auditable=str(objet.id)), format="json")
    assert r.status_code == 422
    assert "objet_auditable" in r.json()["errors"]


def test_fin_avant_debut_422_sur_fin_prevue(rai_client: APIClient) -> None:
    p, proc = programme(annee=2026), make_processus()
    r = rai_client.post(URL, _corps(p, proc, fin_prevue="2026-02-01"), format="json")
    assert r.status_code == 422
    assert "fin_prevue" in r.json()["errors"]


def test_processus_inconnu_400(rai_client: APIClient) -> None:
    p, proc = programme(annee=2026), make_processus()
    corps = _corps(p, proc, processus="00000000-0000-0000-0000-000000000000")
    r = rai_client.post(URL, corps, format="json")
    assert r.status_code == 400
    assert r.json()["errors"]["processus"] == ["Objet introuvable."]


def test_processus_supprime_refuse_en_ecriture_400(rai_client: APIClient) -> None:
    p, proc = programme(annee=2026), make_processus()
    proc.soft_delete(make_user(Role.ADMIN))
    r = rai_client.post(URL, _corps(p, proc), format="json")
    assert r.status_code == 400


def test_modifier_ligne_programme_valide_422(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    une = ligne(programme=p)
    rai_client.post(f"/api/v1/audit-plans/{p.id}/validate/")
    r = rai_client.patch(f"{URL}{une.id}/", {"titre": "Autre"}, format="json")
    assert r.status_code == 422
    assert (
        r.json()["detail"] == "Le programme annuel 2026 est validé : il ne peut plus être modifié."
    )


def test_modifier_ligne(rai_client: APIClient) -> None:
    une = ligne(programme=programme(annee=2026))
    r = rai_client.patch(f"{URL}{une.id}/", {"titre": "Autre"}, format="json")
    assert r.status_code == 200
    assert r.json()["titre"] == "Autre"


def test_changer_de_programme_422(rai_client: APIClient) -> None:
    une = ligne(programme=programme(annee=2026))
    autre = programme(annee=2027)
    r = rai_client.patch(f"{URL}{une.id}/", {"programme": str(autre.id)}, format="json")
    assert r.status_code == 422
    assert "programme" in r.json()["errors"]


def test_supprimer_ligne_204(rai_client: APIClient) -> None:
    une = ligne(programme=programme(annee=2026))
    assert rai_client.delete(f"{URL}{une.id}/").status_code == 204
    assert not LigneProgramme.objects.filter(pk=une.pk).exists()


def test_trimestre_invalide_400(rai_client: APIClient) -> None:
    assert rai_client.get(f"{URL}?trimestre=5").status_code == 400
    assert rai_client.get(f"{URL}?trimestre=abc").status_code == 400


def test_filtre_trimestre_et_processus(rai_client: APIClient) -> None:
    p, proc = programme(annee=2026), make_processus()
    t1 = ligne(
        programme=p, processus=proc, debut_prevu=date(2026, 2, 1), fin_prevue=date(2026, 2, 5)
    )
    ligne(programme=p, debut_prevu=date(2026, 5, 1), fin_prevue=date(2026, 5, 5))
    r = rai_client.get(f"{URL}?trimestre=1")
    assert [x["id"] for x in r.json()["results"]] == [str(t1.id)]
    r = rai_client.get(f"{URL}?processus={proc.id}&trimestre=2")
    assert r.json()["results"] == []
    r = rai_client.get(f"{URL}?processus={proc.id}")
    assert [x["id"] for x in r.json()["results"]] == [str(t1.id)]


def test_filtres_q_type_entite_programme(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    d = make_direction()
    a = ligne(programme=p, titre="Achats groupés", type="CONSEIL")
    a.entites.add(d)
    ligne(programme=p, titre="Paie")
    assert [x["id"] for x in rai_client.get(f"{URL}?q=achats").json()["results"]] == [str(a.id)]
    assert [x["id"] for x in rai_client.get(f"{URL}?type=CONSEIL").json()["results"]] == [str(a.id)]
    assert [x["id"] for x in rai_client.get(f"{URL}?entite={d.id}").json()["results"]] == [
        str(a.id)
    ]
    assert len(rai_client.get(f"{URL}?programme={p.id}").json()["results"]) == 2


def test_tri_par_defaut(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    tard = ligne(programme=p, debut_prevu=date(2026, 9, 1), fin_prevue=date(2026, 9, 2))
    tot = ligne(programme=p, debut_prevu=date(2026, 1, 5), fin_prevue=date(2026, 1, 6))
    ids = [x["id"] for x in rai_client.get(URL).json()["results"]]
    assert ids == [str(tot.id), str(tard.id)]


def test_processus_supprime_affiche_en_lecture(rai_client: APIClient) -> None:
    p, proc = programme(annee=2026), make_processus(code="FEP")
    d = make_direction()
    objet = make_objet(processus=proc)
    une = ligne(programme=p, processus=proc, objet_auditable=objet)
    une.entites.add(d)
    admin = make_user(Role.ADMIN)
    d.soft_delete(admin)
    objet.soft_delete(admin)
    proc.soft_delete(admin)
    corps = rai_client.get(f"{URL}{une.id}/").json()
    assert corps["processus_supprime"] is True
    assert corps["processus_code"] == "FEP"
    assert corps["objet_auditable_supprime"] is True
    assert corps["entites_detail"][0]["supprime"] is True


def test_liste_lignes_requetes_bornees(
    rai_client: APIClient, django_assert_max_num_queries: Any
) -> None:
    p = programme(annee=2026)
    d = make_direction()
    for _ in range(30):
        ligne(programme=p).entites.add(d)
    with django_assert_max_num_queries(4):
        r = rai_client.get(f"{URL}?page_size=50")
    assert len(r.json()["results"]) == 30


def test_page_size_plafonne_a_200(rai_client: APIClient) -> None:
    p = programme(annee=2026)
    for _ in range(201):
        ligne(programme=p)
    r = rai_client.get(f"{URL}?page_size=5000")
    assert r.status_code == 200
    assert len(r.json()["results"]) == 200


def test_erreurs_au_format_unique(rai_client: APIClient) -> None:
    for r in (
        rai_client.get(f"{URL}?trimestre=9"),
        rai_client.post(URL, {}, format="json"),
        rai_client.get(f"{URL}00000000-0000-0000-0000-000000000000/"),
    ):
        assert set(r.json()) >= {"detail"}
        assert r.status_code in (400, 404)
    assert "errors" in rai_client.post(URL, {}, format="json").json()
