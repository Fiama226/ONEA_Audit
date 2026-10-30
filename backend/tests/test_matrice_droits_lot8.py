# ruff: noqa: F811, F401
"""Matrice des droits du suivi (lot 8) : rôle × route.

Ordre des refus : rôle 403 -> objet invisible 404 -> droit 403 -> sérialiseur 400 -> règle 422.
"""

import datetime
from collections.abc import Callable
from typing import Any

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.suivi.models import StatutSuivi, SuiviAction
from apps.suivi.services import workflow
from apps.suivi.services.preuves import deposer_preuve
from tests.accomplissement.fixtures_api import client_de
from tests.suivi.factories import DemandeReportFactory, PreuveFactory
from tests.suivi.fixtures_api import *  # noqa: F403
from tests.suivi.fixtures_api import (
    ACTIONS,
    MISSIONS,
    PDF,
    PREUVES,
    REPORTS,
    EquipeSuivi,
)

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("stockage_temp")]

QUI = (
    "rai",
    "chef",
    "superviseur",
    "auditeur",
    "auditeur_non_leve",
    "responsable",
    "audite",
    "dg",
    "admin",
    "non_affecte",
    "audite_non_affecte",
)
INVISIBLES = {"non_affecte": 404, "audite_non_affecte": 404}


def _attendus(autorises: set[str], *, defaut: int = 403, **autres: int) -> dict[str, int]:
    """200 (ou le code donné) pour les autorisés ; 404 hors périmètre ; ADMIN 403 toujours."""
    attendu: dict[str, int] = {}
    for q in QUI:
        if q in autorises:
            attendu[q] = autres.get(q, 200)
        elif q in INVISIBLES:
            attendu[q] = 404
        else:
            attendu[q] = defaut
    return attendu


LECTURE = {
    "rai",
    "chef",
    "superviseur",
    "auditeur",
    "auditeur_non_leve",
    "responsable",
    "audite",
    "dg",
}
EXECUTANTS = {"rai", "responsable"}
VERIFIEURS = {"rai", "chef", "superviseur", "auditeur"}


def _avec_preuve(e: EquipeSuivi) -> SuiviAction:
    s = e.suivi
    PreuveFactory(suivi=s, deposee_par=e.users["responsable"])
    return s


def _declaree(e: EquipeSuivi) -> SuiviAction:
    s = _avec_preuve(e)
    workflow.declarer_realisee(s, commentaire="Fait.", by=e.users["responsable"])
    s.refresh_from_db()
    return s


def _verifiee(e: EquipeSuivi) -> SuiviAction:
    s = _declaree(e)
    workflow.verifier(s, by=e.users["auditeur"])
    s.refresh_from_db()
    return s


def _fichier() -> SimpleUploadedFile:
    return SimpleUploadedFile("pv.pdf", PDF, content_type="application/pdf")


# nom -> (préparation -> cible, appel(client, cible) -> réponse, attendus)
CAS: dict[
    str, tuple[Callable[[EquipeSuivi], Any], Callable[[APIClient, Any], Any], dict[str, int]]
] = {
    "lister": (
        lambda e: None,
        lambda c, _: c.get(ACTIONS),
        {**dict.fromkeys(QUI, 200), "admin": 403},
    ),
    "detail": (
        lambda e: e.suivi,
        lambda c, s: c.get(f"{ACTIONS}{s.pk}/"),
        _attendus(LECTURE),
    ),
    "demarrer": (
        lambda e: e.suivi,
        lambda c, s: c.post(
            f"{ACTIONS}{s.pk}/start/", {"commentaire": "Pour compte."}, format="json"
        ),
        _attendus(EXECUTANTS),
    ),
    "declarer": (
        _avec_preuve,
        lambda c, s: c.post(
            f"{ACTIONS}{s.pk}/declare-done/", {"commentaire": "Fait."}, format="json"
        ),
        _attendus(EXECUTANTS),
    ),
    "verifier": (
        _declaree,
        lambda c, s: c.post(f"{ACTIONS}{s.pk}/verify/", {}, format="json"),
        _attendus(VERIFIEURS),
    ),
    "cloturer": (
        _verifiee,
        lambda c, s: c.post(f"{ACTIONS}{s.pk}/close/", {}, format="json"),
        _attendus({"rai"}),
    ),
    "deposer_preuve": (
        lambda e: e.suivi,
        lambda c, s: c.post(
            f"{PREUVES}?action={s.pk}",
            {"libelle": "PV", "fichier": _fichier(), "commentaire": "Pour compte."},
            format="multipart",
        ),
        _attendus(EXECUTANTS, rai=201, responsable=201),
    ),
    "telecharger_preuve": (
        lambda e: deposer_preuve(
            e.suivi, fichier=_fichier(), libelle="PV", by=e.users["responsable"]
        ),
        lambda c, p: c.get(f"{PREUVES}{p.pk}/download/"),
        _attendus(LECTURE - {"dg"}),
    ),
    "demander_report": (
        lambda e: e.suivi,
        lambda c, s: c.post(
            REPORTS,
            {
                "action": str(s.pk),
                "nouvelle_echeance": (s.echeance + datetime.timedelta(days=30)).isoformat(),
                "motif": "Marché retardé.",
            },
            format="json",
        ),
        _attendus(EXECUTANTS, rai=201, responsable=201),
    ),
    "decider_report": (
        lambda e: DemandeReportFactory(suivi=e.suivi),
        lambda c, d: c.post(f"{REPORTS}{d.pk}/accept/", {}, format="json"),
        _attendus({"rai"}),
    ),
    "cloturer_mission": (
        lambda e: (
            SuiviAction.objects.filter(mission=e.mission).update(statut=StatutSuivi.CLOTUREE),
            e.mission,
        )[1],
        lambda c, m: c.post(f"{MISSIONS}{m.pk}/close/", {}, format="json"),
        # Route réservée au RAI : le rôle global refuse tout autre profil (403) avant la visibilité.
        {q: (200 if q == "rai" else 403) for q in QUI},
    ),
}

PARAMS = [(route, qui) for route in CAS for qui in QUI]


@pytest.mark.parametrize(("route", "qui"), PARAMS, ids=[f"{r}-{q}" for r, q in PARAMS])
def test_matrice_droits_lot8(equipe_suivi: EquipeSuivi, route: str, qui: str) -> None:
    preparer, appeler, attendus = CAS[route]
    cible = preparer(equipe_suivi)
    reponse = appeler(client_de(equipe_suivi.users[qui]), cible)
    assert reponse.status_code == attendus[qui], (route, qui, reponse.content[:300])
