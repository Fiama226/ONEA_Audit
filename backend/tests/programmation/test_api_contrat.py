"""Contrat JSON du programme annuel, recopié dans les fixtures MSW du frontend (lot 3 T5-T7)."""

from datetime import date
from typing import Any

import yaml
from rest_framework.test import APIClient

from apps.users.models import Role
from tests.factories import make_user
from tests.referentiel.typed import direction as make_direction
from tests.referentiel.typed import objet as make_objet
from tests.referentiel.typed import processus as make_processus

from .factories import ligne, programme


def test_api_contrat_ligne(api_client: APIClient, db: None) -> None:
    api_client.force_authenticate(make_user(Role.RAI))
    p = programme(annee=2026)
    proc = make_processus(code="FEP", libelle="Approvisionnement")
    objet = make_objet(processus=proc, libelle="Marchés")
    dir_ = make_direction(code="DAF", libelle="Direction administrative")
    une = ligne(
        programme=p,
        numero=1,
        titre="Audit des achats",
        type="ASSURANCE",
        processus=proc,
        objet_auditable=objet,
        debut_prevu=date(2026, 5, 4),
        fin_prevue=date(2026, 6, 30),
        charge_prevue_jours="20.0",
        justification="Risque élevé",
    )
    une.entites.add(dir_)

    corps = api_client.get(f"/api/v1/audit-plan-lines/{une.id}/").json()
    horodatages = (corps.pop("created_at"), corps.pop("updated_at"))
    assert all(horodatages)
    assert corps == {
        "id": str(une.id),
        "programme": str(p.id),
        "programme_annee": 2026,
        "programme_statut": "BROUILLON",
        "numero": 1,
        "titre": "Audit des achats",
        "type": "ASSURANCE",
        "processus": str(proc.id),
        "processus_code": "FEP",
        "processus_libelle": "Approvisionnement",
        "processus_supprime": False,
        "objet_auditable": str(objet.id),
        "objet_auditable_libelle": "Marchés",
        "objet_auditable_supprime": False,
        "entites_detail": [
            {
                "id": str(dir_.id),
                "code": "DAF",
                "libelle": "Direction administrative",
                "supprime": False,
            }
        ],
        "debut_prevu": "2026-05-04",
        "fin_prevue": "2026-06-30",
        "trimestre": 2,
        "charge_prevue_jours": "20.0",
        "justification": "Risque élevé",
    }

    synthese = api_client.get(f"/api/v1/audit-plans/{p.id}/summary/").json()
    assert synthese == {
        "nb_lignes": 1,
        "charge_totale_jours": "20.0",
        "par_type": {"ASSURANCE": 1, "CONSEIL": 0},
        "par_trimestre": {"1": 0, "2": 1, "3": 0, "4": 0},
    }

    liste = api_client.get("/api/v1/audit-plans/").json()
    assert set(liste) == {"count", "next", "previous", "results"}
    assert set(liste["results"][0]) == {
        "id",
        "annee",
        "libelle",
        "commentaire",
        "approbation",
        "statut",
        "valide_le",
        "valide_par",
        "nb_lignes",
        "charge_totale_jours",
        "created_at",
        "updated_at",
    }


def _schema(api_client: APIClient) -> dict[str, Any]:
    r = api_client.get("/api/schema/")
    assert r.status_code == 200
    schema: dict[str, Any] = yaml.safe_load(r.content)
    return schema


def test_schema_expose_les_routes_programme(api_client: APIClient) -> None:
    schema = _schema(api_client)
    paths = schema["paths"]
    assert "post" in paths["/api/v1/audit-plans/{id}/validate/"]
    assert "get" in paths["/api/v1/audit-plans/{id}/summary/"]
    assert "/api/v1/audit-plan-lines/{id}/" in paths
    composants = schema["components"]["schemas"]
    for nom in ("ProgrammeAnnuel", "LigneProgramme", "SyntheseProgramme"):
        assert nom in composants
    assert "StatutProgrammeEnum" in composants
    # Mêmes choix que missions.TypeMission : un seul enum partagé dans le schéma.
    assert "TypeMissionEnum" in composants
    assert paths["/api/v1/audit-plans/{id}/validate/"]["post"]["tags"] == ["Programme annuel"]


def test_spectacular_validate_sans_avertissement() -> None:
    import io

    from django.core.management import call_command

    out, err = io.StringIO(), io.StringIO()
    call_command(
        "spectacular",
        "--validate",
        "--fail-on-warn",
        "--urlconf=config.urls",
        stdout=out,
        stderr=err,
    )
    assert "Warning" not in err.getvalue()
