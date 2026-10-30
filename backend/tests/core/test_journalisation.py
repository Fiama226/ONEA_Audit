import io
import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.core import journalisation
from apps.core.journalisation import FormateurJson, MasquageFiltre


def _journal(niveau: int = logging.INFO) -> tuple[logging.Logger, io.StringIO]:
    flux = io.StringIO()
    handler = logging.StreamHandler(flux)
    handler.setFormatter(FormateurJson())
    handler.addFilter(MasquageFiltre())
    logger = logging.getLogger("test.journal")
    logger.handlers = [handler]
    logger.setLevel(niveau)
    logger.propagate = False
    return logger, flux


def _lignes(flux: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(ligne) for ligne in flux.getvalue().splitlines()]


def test_chaque_enregistrement_est_un_json_valide() -> None:
    logger, flux = _journal()
    logger.info("bonjour %s", "monde")
    try:
        raise ValueError("boum")
    except ValueError:
        logger.exception("échec")
    lignes = _lignes(flux)
    assert len(lignes) == 2
    assert {"ts", "niveau", "logger", "message", "correlation_id"} <= lignes[0].keys()
    assert lignes[0]["message"] == "bonjour monde"
    assert lignes[0]["niveau"] == "INFO"
    assert "ValueError" in lignes[1]["exception"]


def test_aucune_donnee_personnelle_dans_les_journaux() -> None:
    logger, flux = _journal()
    logger.info("mail de agent.dupont@onea.bf envoyé")
    logger.info("en-tête Authorization: Bearer eyJhbGciOi.eyJzdWIi.sig")
    logger.info("connexion password=Secr3t! réussie")
    logger.info("GET /api/v1/missions/?q=Kaboré terminé")
    logger.info("jeton eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxIn0.c2ln seul")
    sortie = flux.getvalue()
    for interdit in ("@onea", "Bearer eyJ", "Secr3t", "Kaboré", "eyJhbGci", "?q="):
        assert interdit not in sortie
    assert all("?" not in ligne["message"] for ligne in _lignes(flux))


def test_arguments_de_journal_masques_aussi() -> None:
    logger, flux = _journal()
    logger.info("utilisateur %s", "a.b@onea.bf")
    assert "@onea" not in flux.getvalue()


def test_correlation_reprise_de_l_en_tete(api_client: APIClient) -> None:
    r = api_client.get("/api/v1/health/", HTTP_X_CORRELATION_ID="abc-12345678")
    assert r["X-Correlation-ID"] == "abc-12345678"


def test_correlation_generee_si_absente_ou_invalide(api_client: APIClient) -> None:
    r1 = api_client.get("/api/v1/health/")
    r2 = api_client.get("/api/v1/health/", HTTP_X_CORRELATION_ID="x y\nz")
    assert len(r1["X-Correlation-ID"]) >= 16
    assert r2["X-Correlation-ID"] != "x y\nz"


def test_journal_de_requete_sans_chaine_de_requete(
    api_client: APIClient, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO, logger="onea.requete")
    api_client.get("/api/v1/audit-log/?q=Kaboré", HTTP_X_CORRELATION_ID="corr-87654321")
    rec = next(r for r in caplog.records if r.name == "onea.requete")
    assert rec.chemin == "/api/v1/audit-log/"  # type: ignore[attr-defined]
    assert rec.statut in {401, 403}  # type: ignore[attr-defined]
    assert rec.methode == "GET"  # type: ignore[attr-defined]
    assert rec.duree_ms >= 0  # type: ignore[attr-defined]


def test_correlation_propagee_a_la_tache_celery() -> None:
    journalisation.correlation_id_var.set("corr-propage-1")
    headers: dict[str, Any] = {}
    journalisation.avant_publication(headers=headers)
    journalisation.correlation_id_var.set("")
    tache = SimpleNamespace(name="core.tasks.send_mail_task", request=SimpleNamespace(**headers))
    journalisation.avant_execution(task=tache, task_id="t1")
    logger, flux = _journal()
    logger.info("dans la tâche")
    ligne = _lignes(flux)[0]
    assert ligne["correlation_id"] == "corr-propage-1"
    assert ligne["tache"] == "core.tasks.send_mail_task"
    journalisation.apres_execution(task=tache)
    assert journalisation.correlation_id_var.get() == ""


def test_echec_de_tache_journalise_sans_arguments(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR, logger="onea.celery")
    journalisation.echec_tache(
        sender=SimpleNamespace(name="core.tasks.send_mail_task"),
        task_id="t1",
        exception=ValueError("a@onea.bf"),
        args=["a@onea.bf"],
        kwargs={"password": "x"},
    )
    texte = " ".join(r.getMessage() for r in caplog.records)
    assert "core.tasks.send_mail_task" in texte
    assert "ValueError" in texte
    assert "a@onea.bf" not in texte
    assert "password" not in texte
