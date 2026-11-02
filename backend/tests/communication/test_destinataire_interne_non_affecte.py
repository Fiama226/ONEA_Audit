# ruff: noqa: F811, F401
"""Destinataire interne non affecté (écart 1, changement B) : lit le rapport diffusé et accuse
réception, sans aucun accès au reste de la mission."""

import hashlib
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from apps.communication.models import CategorieDestinataire, DestinataireDiffusion, Rapport
from apps.communication.services.diffusion import (
    ajouter_destinataire,
    diffuser,
    retirer_destinataire,
)
from apps.constats.models import Constat
from apps.documents.stockage import cle_version, ecrire
from apps.users.models import Role
from config.documents_settings import configuration_stockage
from tests.accomplissement.fixtures_api import client_de
from tests.communication.fixtures_api import DESTINATAIRES, RAPPORTS, EquipeRapport, equipe
from tests.communication.support_t8 import (
    admin,
    creer_version,
    dg,
    rapport_soumis_reel,
    rapport_valide,
    signataire_factice,
)
from tests.factories import make_user

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.7 rapport final"
INTERNES = ("non_affecte", "audite_non_affecte")


@pytest.fixture(autouse=True)
def stockage_tmp(tmp_path: Path, settings: Any) -> Path:
    settings.DOCUMENTS_ROOT = str(tmp_path)
    settings.STORAGES = {
        **settings.STORAGES,
        "documents": configuration_stockage(
            {"DOCUMENTS_STORAGE": "filesystem", "DOCUMENTS_ROOT": str(tmp_path)}
        ),
    }
    return tmp_path


def _version(rapport: Rapport, type_document: str = "RAPPORT_FINAL") -> Any:
    cle = uuid4()
    return creer_version(
        rapport,
        type_document,
        fichier_pdf=ecrire(cle_version(cle, 1, "pdf"), PDF),
        empreinte_pdf=hashlib.sha256(PDF).hexdigest(),
        fichier_docx=ecrire(cle_version(cle, 1, "docx"), b"PK docx"),
        empreinte_docx=hashlib.sha256(b"PK docx").hexdigest(),
    )


@pytest.fixture
def valide_avec_interne(equipe: EquipeRapport, rapport_valide: Rapport, rai: Any) -> Rapport:
    """Rapport validé (pas encore diffusé) dont deux non affectés sont destinataires."""
    for qui in INTERNES:
        ajouter_destinataire(
            rapport_valide,
            by=rai,
            categorie=CategorieDestinataire.AUTRE.value,
            utilisateur=equipe.users[qui],
        )
    return rapport_valide


@pytest.fixture
def diffuse(valide_avec_interne: Rapport, rai: Any) -> Rapport:
    _version(valide_avec_interne)
    _version(valide_avec_interne, "NOTE_SYNTHETIQUE")
    diffuser(valide_avec_interne, by=rai)
    return Rapport.objects.get(pk=valide_avec_interne.pk)


@pytest.mark.parametrize("qui", INTERNES)
def test_destinataire_lit_le_rapport_diffuse(
    equipe: EquipeRapport, diffuse: Rapport, qui: str
) -> None:
    c = client_de(equipe.users[qui])
    r = c.get(f"{RAPPORTS}{diffuse.pk}/")
    assert r.status_code == 200
    assert "ACCUSER_RECEPTION" in r.json()["actions_possibles"]
    assert "constats" not in r.json() and "mission" not in r.json()
    liste = c.get(RAPPORTS).json()["results"]
    assert [x["id"] for x in liste] == [str(diffuse.pk)]
    for document in ("rapport", "note"):
        d = c.get(f"{RAPPORTS}{diffuse.pk}/download/?format=pdf&document={document}")
        assert d.status_code == 200, document


@pytest.mark.parametrize("qui", INTERNES)
def test_destinataire_accuse_reception(equipe: EquipeRapport, diffuse: Rapport, qui: str) -> None:
    c = client_de(equipe.users[qui])
    r = c.post(f"{RAPPORTS}{diffuse.pk}/acknowledge/", {"confirme": True}, format="json")
    assert r.status_code == 200, r.content
    assert r.json()["mon_accuse_reception"] is not None
    ligne = DestinataireDiffusion.objects.get(rapport=diffuse, utilisateur=equipe.users[qui])
    assert ligne.accuse_reception_le is not None
    mine = c.get(f"{DESTINATAIRES}?rapport={diffuse.pk}").json()["results"]
    assert [x["id"] for x in mine] == [str(ligne.pk)]  # sa seule ligne


def test_destinataire_sans_acces_au_reste_de_la_mission(
    equipe: EquipeRapport, diffuse: Rapport, constat_valide: Constat
) -> None:
    mission = equipe.mission
    for qui in INTERNES:
        c = client_de(equipe.users[qui])
        for url in (
            f"/api/v1/missions/{mission.pk}/",
            f"/api/v1/findings/{constat_valide.pk}/",
            f"/api/v1/mission-steps/?mission={mission.pk}",
            f"{RAPPORTS}?mission={mission.pk}",
            f"/api/v1/draft-reports/?mission={mission.pk}",
        ):
            r = c.get(url)
            assert r.status_code in (403, 404), (qui, url, r.status_code)
        assert c.get("/api/v1/findings/").json().get("results", []) == []
        assert c.post(f"{RAPPORTS}{diffuse.pk}/submit/").status_code in (403, 404)
        assert c.get(f"{RAPPORTS}{diffuse.pk}/preview/").status_code in (403, 404)


def test_pas_d_oracle_entre_destinataire_et_etranger(
    equipe: EquipeRapport, diffuse: Rapport, constat_valide: Constat
) -> None:
    """Un destinataire reçoit, sur les ressources de la mission, la même réponse qu'un étranger."""
    etranger = client_de(make_user(Role.AUDITE))
    destinataire = client_de(equipe.users["audite_non_affecte"])
    for url in (
        f"/api/v1/missions/{equipe.mission.pk}/",
        f"/api/v1/findings/{constat_valide.pk}/",
        f"/api/v1/mission-steps/?mission={equipe.mission.pk}",
    ):
        a, b = etranger.get(url), destinataire.get(url)
        assert a.status_code == b.status_code, url


def test_non_destinataire_reste_refuse(
    equipe: EquipeRapport, rapport_valide: Rapport, rai: Any
) -> None:
    _version(rapport_valide)
    diffuser(rapport_valide, by=rai)
    c = client_de(equipe.users["non_affecte"])
    assert c.get(f"{RAPPORTS}{rapport_valide.pk}/").status_code == 404
    assert c.get(f"{RAPPORTS}{rapport_valide.pk}/download/?format=pdf").status_code == 404
    assert c.post(f"{RAPPORTS}{rapport_valide.pk}/acknowledge/").status_code == 404
    assert c.get(RAPPORTS).json()["results"] == []


def test_avant_diffusion_refuse(equipe: EquipeRapport, valide_avec_interne: Rapport) -> None:
    for qui in INTERNES:
        c = client_de(equipe.users[qui])
        assert c.get(f"{RAPPORTS}{valide_avec_interne.pk}/").status_code == 404
        assert c.get(f"{RAPPORTS}{valide_avec_interne.pk}/download/?format=pdf").status_code == 404
        assert c.post(f"{RAPPORTS}{valide_avec_interne.pk}/acknowledge/").status_code == 404
        assert c.get(RAPPORTS).json()["results"] == []
        assert c.get(f"{DESTINATAIRES}?rapport={valide_avec_interne.pk}").status_code == 404


def test_destinataire_retire_avant_diffusion_refuse(
    equipe: EquipeRapport, valide_avec_interne: Rapport, rai: Any
) -> None:
    ligne = DestinataireDiffusion.objects.get(
        rapport=valide_avec_interne, utilisateur=equipe.users["non_affecte"]
    )
    retirer_destinataire(ligne, by=rai)
    _version(valide_avec_interne)
    diffuser(valide_avec_interne, by=rai)
    c = client_de(equipe.users["non_affecte"])
    assert c.get(f"{RAPPORTS}{valide_avec_interne.pk}/").status_code == 404
    assert c.post(f"{RAPPORTS}{valide_avec_interne.pk}/acknowledge/").status_code == 404
    autre = client_de(equipe.users["audite_non_affecte"])
    assert autre.get(f"{RAPPORTS}{valide_avec_interne.pk}/").status_code == 200


def test_destinataire_recoit_la_vue_diffusee_pas_la_vue_interne(
    equipe: EquipeRapport, diffuse: Rapport
) -> None:
    donnees = client_de(equipe.users["audite_non_affecte"]).get(f"{RAPPORTS}{diffuse.pk}/").json()
    interne = client_de(equipe.users["rai"]).get(f"{RAPPORTS}{diffuse.pk}/").json()
    assert "mission_reference" in donnees and "mission_reference" not in interne
    # la vue diffusée ne porte aucun champ de la vue interne hors identité et synthèse
    interdits = set(interne) - set(donnees)
    assert interdits  # la vue interne contient bien davantage
    assert not interdits & set(donnees)
