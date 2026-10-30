# ruff: noqa: F811, F401
"""API de la diffusion : liste de diffusion, diffusion, accusé de réception, rapport corrigé."""

from typing import Any

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.communication.models import DestinataireDiffusion, Rapport, StatutRapport
from apps.users.models import Role
from tests.accomplissement.fixtures_api import client_de
from tests.communication.factories import (
    DestinataireFactory,
    RapportFactory,
    RapportProvisoireFactory,
)
from tests.communication.fixtures_api import (
    DESTINATAIRES,
    RAPPORTS,
    EquipeRapport,
    equipe,
)
from tests.communication.support_t8 import (
    admin,
    creer_version,
    dg,
    rapport_diffuse,
    rapport_soumis_reel,
    rapport_valide,
    signataire_factice,
)
from tests.factories import make_user

pytestmark = pytest.mark.django_db


def _url(rapport: Rapport, action: str = "") -> str:
    return f"{RAPPORTS}{rapport.pk}/{action}"


def _preparer_versions(rapport: Rapport) -> None:
    creer_version(rapport)
    creer_version(rapport, "NOTE_SYNTHETIQUE")


# --------------------------------------------------------------------------- liste de diffusion


def test_liste_de_diffusion_prerempli_et_lecture(
    equipe: EquipeRapport, rapport_valide: Rapport
) -> None:
    url = f"{DESTINATAIRES}?rapport={rapport_valide.pk}"
    r = client_de(equipe.users["rai"]).get(url)
    assert r.status_code == 200
    categories = sorted(ligne["categorie"] for ligne in r.json()["results"])
    assert categories == ["AUDITE", "DG", "EQUIPE"]
    assert client_de(equipe.users["chef"]).get(url).json()["count"] == 3
    # un destinataire ne lit que sa ligne, et seulement une fois le rapport diffusé
    assert client_de(equipe.users["dg"]).get(url).status_code == 404
    assert client_de(equipe.users["auditeur"]).get(url).json()["count"] == 0
    assert client_de(equipe.users["admin"]).get(url).status_code == 403
    assert client_de(equipe.users["non_affecte"]).get(url).status_code == 404
    assert client_de(equipe.users["rai"]).get(DESTINATAIRES).status_code == 400


def test_gestion_de_la_liste_par_le_rai(equipe: EquipeRapport, rapport_valide: Rapport) -> None:
    rai = client_de(equipe.users["rai"])
    externe = {
        "rapport": str(rapport_valide.pk),
        "nom_externe": "Cour des comptes",
        "qualite": "Contrôle externe",
        "categorie": "AUTRE",
    }
    r = rai.post(DESTINATAIRES, externe, format="json")
    assert r.status_code == 201, r.json()
    ligne = r.json()
    assert ligne["utilisateur"] is None and ligne["nom_externe"] == "Cour des comptes"
    # ni les deux, ni aucun : règle métier (422)
    both = {**externe, "utilisateur": equipe.users["auditeur"].pk}
    assert rai.post(DESTINATAIRES, both, format="json").status_code == 422
    assert (
        rai.post(DESTINATAIRES, {"rapport": externe["rapport"]}, format="json").status_code == 422
    )
    # modification et retrait
    url = f"{DESTINATAIRES}{ligne['id']}/"
    r = rai.patch(url, {"qualite": "Inspection"}, format="json")
    assert r.status_code == 200 and r.json()["qualite"] == "Inspection"
    assert rai.delete(url).status_code == 204
    assert rai.get(url).status_code == 404
    # chef : lecture seule ; audité et DG : refus de rôle ; non-RAI sur objet inexistant : 403
    assert (
        client_de(equipe.users["chef"]).post(DESTINATAIRES, externe, format="json").status_code
        == 403
    )
    assert (
        client_de(equipe.users["chef"]).delete(f"{DESTINATAIRES}{ligne['id']}/").status_code == 403
    )
    assert (
        client_de(equipe.users["audite"]).post(DESTINATAIRES, externe, format="json").status_code
        == 403
    )
    assert (
        client_de(equipe.users["dg"]).post(DESTINATAIRES, externe, format="json").status_code == 403
    )
    assert (
        client_de(equipe.users["admin"]).post(DESTINATAIRES, externe, format="json").status_code
        == 403
    )


def test_liste_figee_apres_diffusion_422(equipe: EquipeRapport, rapport_diffuse: Rapport) -> None:
    rai = client_de(equipe.users["rai"])
    corps = {"rapport": str(rapport_diffuse.pk), "nom_externe": "Tiers", "categorie": "AUTRE"}
    assert rai.post(DESTINATAIRES, corps, format="json").status_code == 422
    une = DestinataireDiffusion.objects.filter(rapport=rapport_diffuse).first()
    assert rai.delete(f"{DESTINATAIRES}{une.pk}/").status_code == 422
    assert (
        rai.patch(f"{DESTINATAIRES}{une.pk}/", {"qualite": "x"}, format="json").status_code == 422
    )


def test_remise_hors_plateforme(equipe: EquipeRapport, rapport_valide: Rapport) -> None:
    rai = client_de(equipe.users["rai"])
    externe = rai.post(
        DESTINATAIRES,
        {"rapport": str(rapport_valide.pk), "nom_externe": "Tiers", "categorie": "AUTRE"},
        format="json",
    ).json()
    _preparer_versions(rapport_valide)
    assert rai.post(_url(rapport_valide, "distribute/"), {}, format="json").status_code == 200
    url = f"{DESTINATAIRES}{externe['id']}/delivered/"
    from apps.missions.services import aujourd_hui

    assert rai.post(url, {}, format="json").status_code == 400
    assert (
        client_de(equipe.users["chef"])
        .post(url, {"le": str(aujourd_hui())}, format="json")
        .status_code
        == 403
    )
    r = rai.post(url, {"le": str(aujourd_hui())}, format="json")
    assert r.status_code == 200 and r.json()["remis_hors_plateforme_le"] is not None
    # un destinataire interne ne se « remet » pas hors plateforme
    interne = DestinataireDiffusion.objects.filter(
        rapport=rapport_valide, utilisateur__isnull=False
    ).first()
    r = rai.post(
        f"{DESTINATAIRES}{interne.pk}/delivered/", {"le": str(aujourd_hui())}, format="json"
    )
    assert r.status_code == 422


# --------------------------------------------------------------------------- diffusion


def test_diffusion_par_le_rai(equipe: EquipeRapport, rapport_valide: Rapport) -> None:
    url = _url(rapport_valide, "distribute/")
    rai = client_de(equipe.users["rai"])
    assert rai.post(url, {}, format="json").status_code == 422  # rapport final non généré
    _preparer_versions(rapport_valide)
    for qui, statut in (
        ("chef", 403),
        ("auditeur", 403),
        ("audite", 403),
        ("dg", 403),
        ("admin", 403),
        ("non_affecte", 404),
    ):
        assert client_de(equipe.users[qui]).post(url, {}, format="json").status_code == statut, qui
    r = rai.post(url, {"message": "Pour information."}, format="json")
    assert r.status_code == 200, r.json()
    corps = r.json()
    assert corps["statut"] == "DIFFUSE"
    assert corps["diffusion"]["message"] == "Pour information."
    assert corps["diffusion"]["version_rapport"]["statut_pdf"] == "PRET"
    assert corps["diffusion"]["version_note"] is not None
    assert corps["version_finale"]["id"] == corps["diffusion"]["version_rapport"]["id"]
    assert "CORRIGER" in corps["actions_possibles"]


def test_accuse_reception(equipe: EquipeRapport, rapport_diffuse: Rapport) -> None:
    url = _url(rapport_diffuse, "acknowledge/")
    # ni destinataire (RAI, auditeur) : 403 ; hors périmètre : 404 ; ADMIN : refus de rôle
    assert client_de(equipe.users["rai"]).post(url).status_code == 403
    assert client_de(equipe.users["auditeur"]).post(url).status_code == 403
    assert client_de(equipe.users["admin"]).post(url).status_code == 403
    assert client_de(equipe.users["non_affecte"]).post(url).status_code == 404
    assert client_de(equipe.users["audite_non_affecte"]).post(url).status_code == 404
    dg = client_de(equipe.users["dg"])
    avant = dg.get(_url(rapport_diffuse)).json()
    assert (
        avant["mon_accuse_reception"] is None and "ACCUSER_RECEPTION" in avant["actions_possibles"]
    )
    r = dg.post(url)
    assert r.status_code == 200, r.json()
    assert r.json()["mon_accuse_reception"] is not None
    assert "ACCUSER_RECEPTION" not in r.json()["actions_possibles"]
    # la première date fait foi
    assert dg.post(url).json()["mon_accuse_reception"] == r.json()["mon_accuse_reception"]
    assert client_de(equipe.users["audite"]).post(url).status_code == 200


def test_rapport_non_diffuse_non_accusable(equipe: EquipeRapport, rapport_valide: Rapport) -> None:
    assert (
        client_de(equipe.users["audite"]).post(_url(rapport_valide, "acknowledge/")).status_code
        == 403
    )
    assert (
        client_de(equipe.users["dg"]).post(_url(rapport_valide, "acknowledge/")).status_code == 404
    )


# --------------------------------------------------------------------------- rapport corrigé


def test_rapport_corrige(equipe: EquipeRapport, rapport_diffuse: Rapport) -> None:
    url = _url(rapport_diffuse, "correct/")
    rai = client_de(equipe.users["rai"])
    assert (
        client_de(equipe.users["chef"]).post(url, {"motif": "Erreur."}, format="json").status_code
        == 403
    )
    assert (
        client_de(equipe.users["dg"]).post(url, {"motif": "Erreur."}, format="json").status_code
        == 403
    )
    assert rai.post(url, {}, format="json").status_code == 400
    assert rai.post(url, {"motif": " "}, format="json").status_code == 422
    r = rai.post(url, {"motif": "Montant corrigé."}, format="json")
    assert r.status_code == 201, r.json()
    corrige = r.json()
    assert corrige["numero_version"] == 2 and corrige["statut"] == "BROUILLON"
    assert corrige["corrige_de"] == str(rapport_diffuse.pk)
    assert corrige["motif_correction"] == "Montant corrigé."
    ancien = rai.get(_url(rapport_diffuse)).json()
    assert ancien["statut"] == "REMPLACE" and ancien["actions_possibles"] == []
    # la liste de diffusion est recopiée
    assert rai.get(f"{DESTINATAIRES}?rapport={corrige['id']}").json()["count"] == 3
    # le DG voit l'ancien rapport marqué remplacé
    vu = client_de(equipe.users["dg"]).get(_url(rapport_diffuse)).json()
    assert "remplacé" in vu["mention_correction"]
    # on ne corrige pas deux fois le même rapport
    assert rai.post(url, {"motif": "Encore."}, format="json").status_code == 422


# --------------------------------------------------------------------------- DG, audité, requêtes

CLES_DIFFUSE = {
    "id",
    "mission_reference",
    "mission_titre",
    "numero_version",
    "numero_document",
    "valide_le",
    "diffuse_le",
    "synthese",
    "appreciation_globale",
    "mention_correction",
    "mon_accuse_reception",
    "actions_possibles",
}


def test_dg_ne_voit_que_les_rapports_diffuses(
    equipe: EquipeRapport, rapport_valide: Rapport
) -> None:
    dg = client_de(equipe.users["dg"])
    # VALIDE non diffusé : invisible pour le DG (404), liste vide
    assert dg.get(_url(rapport_valide)).status_code == 404
    assert dg.get(RAPPORTS).json()["count"] == 0
    assert dg.get(f"{RAPPORTS}?mission={equipe.mission.pk}").json()["count"] == 0
    _preparer_versions(rapport_valide)
    client_de(equipe.users["rai"]).post(_url(rapport_valide, "distribute/"), {}, format="json")
    liste = dg.get(RAPPORTS).json()
    assert liste["count"] == 1 and set(liste["results"][0]) == CLES_DIFFUSE
    detail = dg.get(_url(rapport_valide))
    assert detail.status_code == 200 and set(detail.json()) == CLES_DIFFUSE
    assert detail.json()["mission_reference"] == equipe.mission.reference
    assert dg.get(f"{RAPPORTS}?mission={equipe.mission.pk}").json()["count"] == 1
    # ni modification, ni action interne
    assert dg.patch(_url(rapport_valide), {}, format="json").status_code == 403
    assert dg.get(_url(rapport_valide, "preview/")).status_code == 403


def test_audite_voit_le_rapport_diffuse_sans_section_interne(
    equipe: EquipeRapport, rapport_valide: Rapport
) -> None:
    audite = client_de(equipe.users["audite"])
    _preparer_versions(rapport_valide)
    assert audite.get(_url(rapport_valide)).status_code == 403  # validé, pas encore diffusé
    client_de(equipe.users["rai"]).post(_url(rapport_valide, "distribute/"), {}, format="json")
    detail = audite.get(_url(rapport_valide))
    assert detail.status_code == 200 and set(detail.json()) == CLES_DIFFUSE
    texte = str(detail.json())
    assert "evenements" not in texte and "motif_renvoi" not in texte
    liste = audite.get(f"{RAPPORTS}?mission={equipe.mission.pk}").json()
    assert liste["count"] == 1 and set(liste["results"][0]) == CLES_DIFFUSE


def _compter(client: Any, url: str) -> int:
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx)


def test_listes_requetes_bornees_rapports_et_destinataires(
    equipe: EquipeRapport, rapport_valide: Rapport
) -> None:
    rai = client_de(equipe.users["rai"])
    urls = (
        f"{RAPPORTS}?mission={equipe.mission.pk}",
        f"{DESTINATAIRES}?rapport={rapport_valide.pk}",
    )

    def ajouter(numeros: range) -> None:
        for n in numeros:
            r = RapportFactory(
                mission=equipe.mission, numero_version=n, statut=StatutRapport.REMPLACE
            )
            RapportProvisoireFactory(rapport=r)
            DestinataireFactory(rapport=rapport_valide, categorie="AUTRE")

    ajouter(range(2, 4))  # le coût fixe (mode de signature en vigueur) est déjà payé
    avant = [_compter(rai, url) for url in urls]
    ajouter(range(4, 22))
    apres = [_compter(rai, url) for url in urls]
    assert apres == avant, (avant, apres)
    assert rai.get(urls[0]).json()["count"] == 21 and rai.get(urls[1]).json()["count"] == 23
