import pytest

from apps.constats.models import Constat, Recommandation
from apps.missions.models import Mission, RoleMission, StatutEtape, StatutMission, TypeReunion
from apps.users.models import Role, User
from tests.constats.conftest import mission_en_xiv  # noqa: F401
from tests.constats.factories import ConstatFactory, RecommandationFactory
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


@pytest.fixture
def mission_en_communication(mission_en_xiv: Mission) -> Mission:  # noqa: F811
    """XIII validée, XIV terminée, mission EN_COMMUNICATION ; deux constats VALIDE, 3 recos."""
    a = ConstatFactory(mission=mission_en_xiv)
    b = ConstatFactory(mission=mission_en_xiv)
    RecommandationFactory(constat=a, mission=mission_en_xiv, ordre=2)
    for constat in (a, b):
        _valider(constat)
    for constat, nom in ((a, "a"), (b, "b")):
        audite = make_user(Role.AUDITE, direction_code=constat.entite.code)
        affecter(mission_en_xiv, audite, RoleMission.AUDITE)
        setattr(mission_en_xiv, f"_audite_{nom}", audite)
    ReunionFactory(mission=mission_en_xiv, type=TypeReunion.CLOTURE)
    forcer_etapes(
        mission_en_xiv,
        {14: StatutEtape.TERMINEE, 15: StatutEtape.EN_COURS, 16: StatutEtape.EN_COURS},
    )
    Mission.objects.filter(pk=mission_en_xiv.pk).update(statut=StatutMission.EN_COMMUNICATION)
    mission_en_xiv.refresh_from_db()
    return mission_en_xiv


@pytest.fixture
def recommandations(mission_en_communication: Mission) -> list[Recommandation]:
    return list(
        Recommandation.objects.filter(mission=mission_en_communication).order_by(
            "constat__numero", "ordre"
        )
    )


@pytest.fixture
def audite_entite_a(mission_en_communication: Mission) -> User:
    user: User = mission_en_communication._audite_a  # type: ignore[attr-defined]
    return user


@pytest.fixture
def audite_entite_b(mission_en_communication: Mission) -> User:
    user: User = mission_en_communication._audite_b  # type: ignore[attr-defined]
    return user
