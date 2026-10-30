"""Semis complementaire des lots 5 a 8 (constats, plan d'actions, suivi, rapports).

Les peuplements de demonstration de ces lots sont vides : on cree ici, par les fabriques de
tests, de quoi depasser deux pages de 25 elements sur chaque liste.
"""

from typing import Any

from apps.constats.models import Constat, Recommandation
from apps.missions.models import EtapeMission, Mission, StatutEtape, StatutMission
from apps.recommandations.models import Action
from apps.suivi.models import SuiviAction
from tests.accomplissement.factories import FicheFactory, PieceFactory
from tests.communication.factories import (
    DestinataireFactory,
    RapportFactory,
    RapportProvisoireFactory,
    ReponseRapportFactory,
)
from tests.constats.factories import ConstatFactory, ReponseFactory, fiche_anomalie
from tests.factories import EtapeMissionFactory, MissionFactory
from tests.recommandations.factories import AcceptationFactory, ActionFactory, EngagementFactory
from tests.suivi.factories import (
    DemandeReportFactory,
    PreuveFactory,
    RelanceFactory,
    SuiviActionFactory,
)

N = 52  # plus que deux pages de 25 et que la page de 50 du test d'independance


def _etapes(mission: Mission, statuts: dict[int, str]) -> None:
    for numero, statut in statuts.items():
        EtapeMission.objects.filter(mission=mission, numero=numero).update(statut=statut)


def semer_domaine() -> dict[str, Any]:
    """Cree une mission chargee (N elements par liste) ; retourne les parametres de requete."""
    mission = MissionFactory(
        statut=StatutMission.EN_PLANIFICATION, reference="DAI/2026/M99", annee=2026, numero=99
    )
    for numero in range(1, 19):
        EtapeMissionFactory(mission=mission, numero=numero, statut=StatutEtape.A_FAIRE)
    fiche_anomalie(mission)
    brouillon = FicheFactory(test__mission=mission, test__programme__mission=mission)
    for _ in range(N):
        PieceFactory(fiche=brouillon)
    _etapes(mission, {**{n: StatutEtape.VALIDEE for n in range(1, 14)}, 14: StatutEtape.EN_COURS})
    constats: list[Constat] = [ConstatFactory(mission=mission) for _ in range(N)]
    _etapes(mission, {14: StatutEtape.TERMINEE, 15: StatutEtape.EN_COURS, 16: StatutEtape.EN_COURS})
    Mission.objects.filter(pk=mission.pk).update(statut=StatutMission.EN_COMMUNICATION)
    mission.refresh_from_db()
    recos = list(Recommandation.objects.filter(mission=mission).order_by("created_at"))
    actions: list[Action] = [ActionFactory(recommandation=r) for r in recos]
    suivis: list[SuiviAction] = [SuiviActionFactory(action=a) for a in actions]
    for s in suivis:
        PreuveFactory(suivi=s)
        DemandeReportFactory(suivi=s)
        RelanceFactory(suivi=s)
    for c in constats:
        ReponseFactory(constat=c)
    for r in recos:
        AcceptationFactory(recommandation=r)
    EngagementFactory(mission=mission)
    rapport = RapportFactory(mission=mission)
    provisoire = RapportProvisoireFactory(rapport=rapport)
    for c in constats:
        ReponseRapportFactory(provisoire=provisoire, constat=c)
    for _ in range(N):
        DestinataireFactory(rapport=rapport)
    Mission.objects.filter(pk=mission.pk).update(statut=StatutMission.EN_SUIVI)
    return {
        "mission": str(mission.pk),
        "constat": str(constats[0].pk),
        "provisoire": str(provisoire.pk),
        "rapport": str(rapport.pk),
        "action": str(suivis[0].pk),
    }
