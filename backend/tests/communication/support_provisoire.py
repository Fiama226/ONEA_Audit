"""Fixtures partagées des tests du rapport provisoire et des réponses (tâche 7 du lot 7)."""

from datetime import date

import pytest
from django.utils import timezone

from apps.communication.models import Rapport, RapportProvisoire
from apps.communication.services import provisoire as service
from apps.constats.models import Constat
from apps.missions.models import Mission, RoleMission, StatutEtape, StatutMission, TypeReunion
from apps.users.models import Role, User
from tests.communication.factories import RapportFactory
from tests.constats.conftest import mission_en_xiv  # noqa: F401
from tests.constats.factories import ConstatFactory
from tests.factories import ReunionFactory, make_user
from tests.missions.conftest import (  # noqa: F401
    affecter,
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)


def _valider(constat: Constat) -> None:
    constat.soumettre()
    constat.save()
    constat.valider()
    constat.save()


def _ouvrir_communication(mission: Mission) -> None:
    ReunionFactory(mission=mission, type=TypeReunion.CLOTURE, tenue_le=timezone.now())
    forcer_etapes(
        mission, {14: StatutEtape.TERMINEE, 15: StatutEtape.EN_COURS, 16: StatutEtape.EN_COURS}
    )
    Mission.objects.filter(pk=mission.pk).update(statut=StatutMission.EN_COMMUNICATION)
    mission.refresh_from_db()


@pytest.fixture
def mission_xv_vide(mission_en_xiv: Mission) -> Mission:  # noqa: F811
    """Comme `mission_xv`, mais sans aucun constat."""
    _ouvrir_communication(mission_en_xiv)
    return mission_en_xiv


@pytest.fixture
def mission_xv(mission_en_xiv: Mission) -> Mission:  # noqa: F811
    """XIV terminée, XV et XVI en cours, EN_COMMUNICATION ; constats VALIDE A et B, C non validé."""
    a = ConstatFactory(mission=mission_en_xiv)
    b = ConstatFactory(mission=mission_en_xiv)
    mission_en_xiv._constat_c = ConstatFactory(mission=mission_en_xiv)  # type: ignore[attr-defined]
    for constat in (a, b):
        _valider(constat)
    for constat, nom in ((a, "a"), (b, "b")):
        audite = make_user(Role.AUDITE, direction_code=constat.entite.code)
        affecter(mission_en_xiv, audite, RoleMission.AUDITE)
        setattr(mission_en_xiv, f"_audite_{nom}", audite)
        setattr(mission_en_xiv, f"_constat_{nom}", constat)
    _ouvrir_communication(mission_en_xiv)
    return mission_en_xiv


@pytest.fixture
def rapport_xv(mission_xv: Mission) -> Rapport:
    rapport: Rapport = RapportFactory(mission=mission_xv)
    return rapport


@pytest.fixture
def constat_hors_provisoire(mission_xv: Mission) -> Constat:
    constat: Constat = mission_xv._constat_c  # type: ignore[attr-defined]
    return constat


@pytest.fixture
def constat_a(mission_xv: Mission) -> Constat:
    constat: Constat = mission_xv._constat_a  # type: ignore[attr-defined]
    return constat


@pytest.fixture
def constat_b(mission_xv: Mission) -> Constat:
    constat: Constat = mission_xv._constat_b  # type: ignore[attr-defined]
    return constat


@pytest.fixture
def audite_entite_a(mission_xv: Mission) -> User:
    user: User = mission_xv._audite_a  # type: ignore[attr-defined]
    return user


@pytest.fixture
def audite_entite_b(mission_xv: Mission) -> User:
    user: User = mission_xv._audite_b  # type: ignore[attr-defined]
    return user


@pytest.fixture
def provisoire_transmis(rapport_xv: Rapport, chef: User) -> RapportProvisoire:  # noqa: F811
    return service.transmettre_provisoire(rapport_xv, by=chef)


@pytest.fixture
def aujourd_hui_le(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Simule la date du jour (pas de pytest-freezer dans le projet)."""

    def deplacer(jour: date) -> None:
        monkeypatch.setattr(service, "aujourd_hui", lambda: jour)

    return deplacer
