# ruff: noqa: F811, F401
"""Jeu de données des tests d'API des tableaux de bord (importé par les fichiers de test)."""

import datetime
from collections.abc import Callable
from dataclasses import dataclass

import pytest
from django.utils import timezone

from apps.constats.models import Constat, StatutConstat
from apps.missions.models import Mission, RoleMission
from apps.referentiel.models import Direction
from apps.suivi.models import StatutSuivi, SuiviAction
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import DirectionFactory, make_user
from tests.missions.conftest import affecter
from tests.suivi.factories import DemandeReportFactory
from tests.tableaux_de_bord.conftest import (
    AUJOURD_HUI,
    creer_suivi,
    jeu_complet,
    mission_diffusee,
    valider_carto,
)


@dataclass
class JeuApi:
    mission: Mission
    auditeur: User
    audite: User
    rai: User
    dg: User
    entite: Direction


@pytest.fixture
def figer_la_date(monkeypatch: pytest.MonkeyPatch) -> datetime.date:
    """Les vues lisent « aujourd'hui » : on la fige sur la date des jeux de données."""
    monkeypatch.setattr("apps.tableaux_de_bord.views.aujourd_hui", lambda: AUJOURD_HUI)
    return AUJOURD_HUI


@pytest.fixture
def jeu_api(
    jeu_complet: Mission, creer_suivi: Callable[..., SuiviAction], figer_la_date: datetime.date
) -> JeuApi:
    """Rapport diffusé en 2026 : suivis en retard, réalisé, clos ; un constat à répondre."""
    mission = jeu_complet
    auditeur = make_user(Role.AUDITEUR)
    affecter(mission, auditeur, RoleMission.AUDITEUR)
    audite = make_user(Role.AUDITE)
    affecter(mission, audite, RoleMission.AUDITE)
    entite = DirectionFactory()
    User.objects.filter(pk=audite.pk).update(direction_code=entite.code)
    audite.refresh_from_db()
    constat: Constat = ConstatFactory(mission=mission, entite=entite)
    Constat.objects.filter(pk=constat.pk).update(
        statut=StatutConstat.SOUMIS, cycle=1, soumis_le=timezone.now()
    )
    creer_suivi(mission, entite, StatutSuivi.EN_COURS, datetime.date(2026, 10, 19), audite)
    bientot = creer_suivi(mission, entite, StatutSuivi.A_LANCER, datetime.date(2026, 12, 1), audite)
    realisee = creer_suivi(
        mission, entite, StatutSuivi.REALISEE, datetime.date(2026, 12, 2), audite
    )
    SuiviAction.objects.filter(pk=realisee.pk).update(declaree_le=timezone.now())
    DemandeReportFactory(suivi=bientot, demandee_par=audite)
    return JeuApi(mission, auditeur, audite, make_user(Role.RAI), make_user(Role.DG), entite)
