import datetime
import itertools
from collections.abc import Callable
from typing import Any

import pytest
from django.utils import timezone

from apps.constats.models import Constat
from apps.missions.models import Mission, StatutMission
from apps.referentiel.models import (
    CartographieVersion,
    Direction,
    StatutCartographie,
)
from apps.suivi.models import StatutSuivi, SuiviAction
from apps.users.models import Role, User
from tests.constats.factories import ConstatFactory
from tests.factories import (
    CartographieVersionFactory,
    DirectionFactory,
    MissionFactory,
    RisqueFactory,
    make_user,
)
from tests.recommandations.factories import ActionFactory
from tests.suivi.conftest import (  # noqa: F401
    affecter,
    audite_affecte,
    auditeur_mission,
    chef,
    forcer_etapes,
    mission_lancee,
)
from tests.suivi.factories import SuiviActionFactory

AUJOURD_HUI = datetime.date(2026, 10, 29)
DIFFUSE_LE = datetime.date(2026, 9, 15)


@pytest.fixture
def aujourd_hui() -> datetime.date:
    return AUJOURD_HUI


_numeros = itertools.count(10)


def faire_mission(
    statut: str = StatutMission.EN_SUIVI, annee: int = 2026, **kwargs: Any
) -> Mission:
    """Mission de l'année avec une référence unique (exigée hors brouillon)."""
    if statut == StatutMission.BROUILLON:
        return MissionFactory(statut=statut, annee=annee, **kwargs)  # type: ignore[no-any-return]
    numero = next(_numeros)
    reference = f"DAI/{annee}/M{numero:02d}"
    return MissionFactory(  # type: ignore[no-any-return]
        statut=statut, annee=annee, numero=numero, reference=reference, **kwargs
    )


@pytest.fixture
def mission_diffusee(db: None) -> Mission:
    """Mission de 2026 au rapport diffusé, sans constat ni suivi."""
    mission = faire_mission()
    Mission.objects.filter(pk=mission.pk).update(ordre_mission_emis_le=timezone.now())
    mission.refresh_from_db()
    return mission


@pytest.fixture
def creer_suivi() -> Callable[..., SuiviAction]:
    """Crée un suivi ; un seul constat par couple (mission, entité)."""
    constats: dict[tuple[Any, Any], Constat] = {}

    def _creer(
        mission: Mission,
        entite: Direction,
        statut: str = StatutSuivi.A_LANCER,
        echeance: datetime.date = datetime.date(2027, 1, 1),
        responsable: User | None = None,
    ) -> SuiviAction:
        cle = (mission.pk, entite.pk)
        if cle not in constats:
            constats[cle] = ConstatFactory(mission=mission, entite=entite)
        reco = constats[cle].recommandations.first()
        kwargs: dict[str, Any] = {"recommandation": reco, "echeance": echeance}
        if responsable is not None:
            kwargs["responsable"] = responsable
        action = ActionFactory(**kwargs)
        suivi = SuiviActionFactory(action=action, diffuse_le=DIFFUSE_LE)
        SuiviAction.objects.filter(pk=suivi.pk).update(
            statut=statut, justification_abandon="Sans objet." if "ABANDON" in statut else ""
        )
        suivi.refresh_from_db()
        return suivi

    return _creer


@pytest.fixture
def fabrique_suivis(
    mission_diffusee: Mission, creer_suivi: Callable[..., SuiviAction]
) -> Callable[..., Any]:
    def _fabriquer(cloturees: int = 0, abandonnees: int = 0, ouvertes: int = 0) -> Any:
        entite = DirectionFactory()
        pks = [
            creer_suivi(mission_diffusee, entite, statut).pk
            for statut, nombre in (
                (StatutSuivi.CLOTUREE, cloturees),
                (StatutSuivi.ABANDONNEE, abandonnees),
                (StatutSuivi.EN_COURS, ouvertes),
            )
            for _ in range(nombre)
        ]
        return SuiviAction.objects.filter(pk__in=pks)

    return _fabriquer


@pytest.fixture
def rai_user(db: None) -> User:
    return make_user(Role.RAI)


@pytest.fixture
def valider_carto() -> Callable[[CartographieVersion], CartographieVersion]:
    def _valider(version: CartographieVersion) -> CartographieVersion:
        CartographieVersion._base_manager.filter(pk=version.pk).update(  # noqa: SLF001
            statut=StatutCartographie.VALIDEE,
            validee_le=timezone.now(),
            validee_par=make_user(Role.RAI),
        )
        version.refresh_from_db()
        return version

    return _valider


@pytest.fixture
def jeu_complet(
    mission_diffusee: Mission,
    creer_suivi: Callable[..., SuiviAction],
    valider_carto: Callable[[CartographieVersion], CartographieVersion],
) -> Mission:
    """Mission au rapport diffusé : trois suivis de trois directions, une cartographie validée."""
    version = CartographieVersionFactory(annee=2025)
    RisqueFactory(version=version, probabilite=5, impact=5)
    valider_carto(version)
    for statut in (StatutSuivi.CLOTUREE, StatutSuivi.EN_COURS, StatutSuivi.ABANDONNEE):
        creer_suivi(mission_diffusee, DirectionFactory(), statut, datetime.date(2026, 10, 1))
    return mission_diffusee
