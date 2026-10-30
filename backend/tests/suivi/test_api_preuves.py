# ruff: noqa: F811, F401, F403
"""Preuves de mise en œuvre par l'API : dépôt multipart, téléchargement vérifié, droits, limites."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.consultations import Consultation
from apps.suivi.models import PreuveMiseEnOeuvre, StatutSuivi, SuiviAction
from apps.suivi.services.preuves import deposer_preuve
from tests.accomplissement.fixtures_api import client_de
from tests.suivi.fixtures_api import *
from tests.suivi.fixtures_api import ACTIONS, PDF, PREUVES, EquipeSuivi

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("stockage_temp")]


def _fichier(contenu: bytes = PDF, nom: str = "pv.pdf") -> SimpleUploadedFile:
    return SimpleUploadedFile(nom, contenu, content_type="application/pdf")


def _deposer(e: EquipeSuivi, qui: str = "responsable", **champs: Any) -> Any:
    s = champs.pop("suivi", e.suivi)
    corps = {"libelle": "PV de mise en place", "fichier": _fichier(), **champs}
    return client_de(e.users[qui]).post(f"{PREUVES}?action={s.pk}", corps, format="multipart")


def test_depot_multipart_et_telechargement_identique(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    r = _deposer(e, description="Procédure signée.")
    assert r.status_code == 201, r.content
    preuve = r.json()
    assert preuve["numero"] == 1
    assert preuve["libelle"] == "PV de mise en place"
    assert preuve["nom_fichier_original"] == "pv.pdf"
    assert preuve["taille_octets"] == len(PDF)
    assert preuve["type_mime"] == "application/pdf"
    assert preuve["empreinte_sha256"] == hashlib.sha256(PDF).hexdigest()
    assert preuve["deposee_par"]["id"] == e.users["responsable"].pk
    assert preuve["actions_possibles"] == ["MODIFIER", "RETIRER", "TELECHARGER"]
    assert "cle_stockage" not in preuve
    for qui in ("responsable", "rai", "chef", "audite"):
        d = client_de(e.users[qui]).get(f"{PREUVES}{preuve['id']}/download/")
        assert d.status_code == 200, qui
        assert d.content == PDF
        assert d["X-Content-Type-Options"] == "nosniff"
        assert d["Content-Security-Policy"] == "default-src 'none'; sandbox"
        assert d["Cache-Control"] == "private, no-store"
        assert d["Content-Disposition"].startswith("attachment;")
        assert d["Content-Length"] == str(len(PDF))
    assert Consultation.objects.filter(object_id=preuve["id"], action="TELECHARGEMENT").count() == 4
    assert (
        client_de(e.users["responsable"]).get(f"{ACTIONS}{e.suivi.pk}/").json()["nombre_preuves"]
        == 1
    )


def test_depot_action_dans_le_corps(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    r = client_de(e.users["responsable"]).post(
        PREUVES,
        {"action": str(e.suivi.pk), "libelle": "PV", "fichier": _fichier()},
        format="multipart",
    )
    assert r.status_code == 201, r.content
    sans = client_de(e.users["responsable"]).post(
        PREUVES, {"libelle": "PV", "fichier": _fichier()}, format="multipart"
    )
    assert sans.status_code == 400
    assert "action" in sans.json()["errors"]
    autre = e.suivis[1]
    diff = client_de(e.users["responsable"]).post(
        f"{PREUVES}?action={e.suivi.pk}",
        {"action": str(autre.pk), "libelle": "PV", "fichier": _fichier()},
        format="multipart",
    )
    assert diff.status_code == 400


def test_telechargement_altere_409(equipe_suivi: EquipeSuivi, stockage_temp: Path) -> None:
    e = equipe_suivi
    preuve = _deposer(e).json()
    cle = PreuveMiseEnOeuvre.objects.get(pk=preuve["id"]).cle_stockage
    (stockage_temp / cle).write_bytes(PDF[:-1] + b"Y")
    r = client_de(e.users["rai"]).get(f"{PREUVES}{preuve['id']}/download/")
    assert r.status_code == 409
    assert r.json()["errors"] == {}
    assert not Consultation.objects.filter(object_id=preuve["id"]).exists()


def test_droits_du_depot_avant_le_corps(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    # droit 403 avant le sérialiseur 400 : aucune validation du corps pour un non-autorisé
    for qui in ("audite", "chef", "auditeur", "dg"):
        r = client_de(e.users[qui]).post(f"{PREUVES}?action={e.suivi.pk}", {}, format="multipart")
        assert r.status_code == 403, qui
    for qui in ("non_affecte", "audite_non_affecte"):
        r = client_de(e.users[qui]).post(f"{PREUVES}?action={e.suivi.pk}", {}, format="multipart")
        assert r.status_code == 404, qui
    assert client_de(e.users["admin"]).post(PREUVES, {}, format="multipart").status_code == 403
    assert _deposer(e, libelle="").status_code == 400
    r = client_de(e.users["responsable"]).post(
        f"{PREUVES}?action={e.suivi.pk}", {"libelle": "PV"}, format="multipart"
    )
    assert r.status_code == 400
    assert (
        client_de(e.users["responsable"])
        .post(f"{PREUVES}?action=pas-un-uuid", {}, format="multipart")
        .status_code
        == 400
    )


def test_depot_refuse_fichier_et_statut(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    faux = _deposer(e, fichier=_fichier(b"MZ\x90\x00" + b"x" * 200, "faux.pdf"))
    assert faux.status_code == 400  # fichier refusé : 400, message sous errors.fichier
    assert "fichier" in faux.json()["errors"]
    # l'action déclarée réalisée n'accepte plus de preuve
    deposer_preuve(e.suivi, fichier=_fichier(), libelle="PV", by=e.users["responsable"])
    SuiviAction.objects.filter(pk=e.suivi.pk).update(statut=StatutSuivi.REALISEE)
    r = _deposer(e, fichier=_fichier(PDF + b"2"))
    assert r.status_code == 422


def test_depot_rai_pour_le_compte(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    sans = _deposer(e, "rai")
    assert sans.status_code == 422
    assert "commentaire" in sans.json()["errors"]
    assert _deposer(e, "rai", commentaire="Reçu par courriel.").status_code == 201


def test_liste_filtre_action_obligatoire(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    _deposer(e)
    client = client_de(e.users["auditeur"])
    assert client.get(PREUVES).status_code == 400
    assert client.get(PREUVES, {"action": "x"}).status_code == 400
    r = client.get(PREUVES, {"action": str(e.suivi.pk)})
    assert r.status_code == 200
    assert [p["numero"] for p in r.json()["results"]] == [1]
    assert r.json()["results"][0]["actions_possibles"] == ["TELECHARGER"]
    assert (
        client_de(e.users["non_affecte"]).get(PREUVES, {"action": str(e.suivi.pk)}).status_code
        == 404
    )
    assert client_de(e.users["admin"]).get(PREUVES, {"action": str(e.suivi.pk)}).status_code == 403
    dg = client_de(e.users["dg"])
    assert dg.get(PREUVES, {"action": str(e.suivi.pk)}).status_code == 200
    ligne = dg.get(PREUVES, {"action": str(e.suivi.pk)}).json()["results"][0]
    assert ligne["actions_possibles"] == []
    assert dg.get(f"{PREUVES}{ligne['id']}/download/").status_code == 403
    assert dg.get(f"{PREUVES}{ligne['id']}/").status_code == 200


def test_listes_requetes_bornees(
    equipe_suivi: EquipeSuivi, django_assert_max_num_queries: Any
) -> None:
    e = equipe_suivi
    for i in range(5):
        _deposer(e, fichier=_fichier(PDF + bytes([i])))
    for qui, borne in (("rai", 5), ("auditeur", 7)):
        client = client_de(e.users[qui])
        with django_assert_max_num_queries(borne):
            r = client.get(PREUVES, {"action": str(e.suivi.pk)})
        assert r.status_code == 200 and r.json()["count"] == 5


def test_modifier_et_retirer(equipe_suivi: EquipeSuivi) -> None:
    e = equipe_suivi
    preuve = _deposer(e).json()
    url = f"{PREUVES}{preuve['id']}/"
    resp = client_de(e.users["responsable"])
    r = resp.patch(url, {"libelle": "PV corrigé"}, format="json")
    assert r.status_code == 200 and r.json()["libelle"] == "PV corrigé"
    assert r.json()["empreinte_sha256"] == preuve["empreinte_sha256"]
    # champs de fichier ignorés (immuables) : le sérialiseur ne les connaît pas
    resp.patch(url, {"empreinte_sha256": "0" * 64, "taille_octets": 1}, format="json")
    assert PreuveMiseEnOeuvre.objects.get(pk=preuve["id"]).taille_octets == len(PDF)
    for qui in ("audite", "chef", "dg"):
        assert (
            client_de(e.users[qui]).patch(url, {"libelle": "x"}, format="json").status_code == 403
        )
        assert client_de(e.users[qui]).delete(url).status_code == 403
    assert client_de(e.users["non_affecte"]).delete(url).status_code == 404
    rai = client_de(e.users["rai"])
    sans = rai.delete(url)
    assert sans.status_code == 422
    assert rai.delete(url, {"commentaire": "Doublon."}, format="json").status_code == 204
    assert resp.get(url).status_code == 404
    assert PreuveMiseEnOeuvre.all_objects.get(pk=preuve["id"]).deleted_at is not None
    suivant = _deposer(e, fichier=_fichier(PDF + b"2")).json()
    assert suivant["numero"] == 2
    assert resp.delete(f"{PREUVES}{suivant['id']}/").status_code == 204


def test_gel_mission_cloturee(equipe_suivi: EquipeSuivi) -> None:
    from apps.missions.models import Mission, StatutMission

    e = equipe_suivi
    preuve = _deposer(e).json()
    Mission.objects.filter(pk=e.mission.pk).update(statut=StatutMission.CLOTUREE)
    assert _deposer(e, fichier=_fichier(PDF + b"3")).status_code == 422
    resp = client_de(e.users["responsable"])
    assert (
        resp.patch(f"{PREUVES}{preuve['id']}/", {"libelle": "x"}, format="json").status_code == 422
    )
    assert resp.delete(f"{PREUVES}{preuve['id']}/").status_code == 422
    lue = resp.get(f"{PREUVES}{preuve['id']}/").json()
    assert lue["actions_possibles"] == ["TELECHARGER"]
