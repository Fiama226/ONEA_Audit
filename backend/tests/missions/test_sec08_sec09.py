"""SEC-08 (conflits d'intérêts) et SEC-09 (réunion non tenue, vue de l'audité)."""

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.missions.models import DeclarationIndependance, Mission, Reunion, TypeReunion
from apps.users.models import User

Equipe = tuple[Mission, dict[str, User]]


@pytest.mark.parametrize(
    ("qui", "voit"),
    [
        ("rai", True),
        ("chef", True),
        ("auditeur_confirme", False),  # collègue : ne lit pas la déclaration d'un autre
        ("superviseur", False),
    ],
)
def test_sec08_conflit_masque_aux_collegues(
    api_client: APIClient, equipe_complete: Equipe, qui: str, voit: bool
) -> None:
    mission, users = equipe_complete
    d = DeclarationIndependance.objects.get(affectation__utilisateur=users["auditeur_non_confirme"])
    DeclarationIndependance.objects.filter(pk=d.pk).update(
        statut="CONFLIT_DECLARE",
        description_conflit="Parent dans l'entité",
        arbitrage_justification="Maintenu",
    )
    api_client.force_authenticate(users[qui])
    r = api_client.get(f"/api/v1/independence-declarations/{d.pk}/")
    assert r.status_code == 200, r.content
    attendu = "Parent dans l'entité" if voit else ""
    assert r.json()["description_conflit"] == attendu
    assert r.json()["arbitrage_justification"] == ("Maintenu" if voit else "")


def test_sec08_le_declarant_voit_sa_propre_declaration(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    _, users = equipe_complete
    d = DeclarationIndependance.objects.get(affectation__utilisateur=users["auditeur_confirme"])
    DeclarationIndependance.objects.filter(pk=d.pk).update(
        statut="CONFLIT_DECLARE", description_conflit="Ancien poste"
    )
    api_client.force_authenticate(users["auditeur_confirme"])
    r = api_client.get(f"/api/v1/independence-declarations/{d.pk}/")
    assert r.json()["description_conflit"] == "Ancien poste"


def test_sec09_audite_ne_lit_pas_une_reunion_non_tenue(
    api_client: APIClient, equipe_complete: Equipe
) -> None:
    mission, users = equipe_complete
    r = Reunion.objects.create(
        mission=mission,
        type=TypeReunion.OUVERTURE,
        date=timezone.now(),
        compte_rendu="Notes internes",
        decisions="Décision interne",
        created_by=users["chef"],
    )
    api_client.force_authenticate(users["audite_affecte"])
    j = api_client.get(f"/api/v1/meetings/{r.pk}/").json()
    assert j["compte_rendu"] == "" and j["decisions"] == ""
    Reunion.objects.filter(pk=r.pk).update(tenue_le=timezone.now())
    j = api_client.get(f"/api/v1/meetings/{r.pk}/").json()
    assert j["compte_rendu"] == "Notes internes" and j["decisions"] == "Décision interne"
    api_client.force_authenticate(users["chef"])
    Reunion.objects.filter(pk=r.pk).update(tenue_le=None)
    assert api_client.get(f"/api/v1/meetings/{r.pk}/").json()["compte_rendu"] == "Notes internes"
