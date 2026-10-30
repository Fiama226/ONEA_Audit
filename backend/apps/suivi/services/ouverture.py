"""Ouverture du suivi (R6) : un suivi par action du plan diffusé, idempotent."""

import logging

from django.db import transaction
from django.utils import timezone

from apps.constats.models import Recommandation
from apps.core.audit import actor_scope
from apps.missions.exceptions import MissionFigeeError
from apps.missions.gardes import verrouiller_mission
from apps.missions.models import Mission, StatutMission
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.users.models import User

from .. import sources
from ..models import EvenementSuivi, SuiviAction, TypeEvenementSuivi
from . import commun

logger = logging.getLogger(__name__)

STATUTS_OUVRABLES = (StatutMission.RAPPORT_DIFFUSE, StatutMission.EN_SUIVI)


def _ouvrir(mission: Mission, by: User | None) -> tuple[list[SuiviAction], int]:
    mission = verrouiller_mission(mission)
    if mission.statut not in STATUTS_OUVRABLES:
        return [], 0
    plan = sources.actions_du_plan(mission)
    existants = {s.action_id: s for s in SuiviAction.all_objects.filter(mission=mission)}
    recommandations = {
        r.pk: r
        for r in Recommandation.objects.filter(
            pk__in={a.recommandation_id for a in plan}
        ).select_related("constat")
    }
    diffuse_le = sources.date_diffusion(mission) or timezone.localdate()
    suivis: list[SuiviAction] = []
    crees: list[SuiviAction] = []
    ignorees: list[sources.ActionPlan] = []
    with actor_scope(by):
        for action in plan:
            if action.id in existants:
                suivis.append(existants[action.id])
                continue
            if action.responsable_id is None or action.echeance is None:
                ignorees.append(action)
                continue
            reco = recommandations[action.recommandation_id]
            suivi = SuiviAction.objects.create(
                mission=mission,
                action_id=action.id,
                recommandation=reco,
                entite_id=reco.constat.entite_id,
                responsable_id=action.responsable_id,
                echeance_initiale=action.echeance,
                echeance=action.echeance,
                diffuse_le=diffuse_le,
                created_by=by,
            )
            EvenementSuivi.journaliser(suivi, TypeEvenementSuivi.OUVERT, par=by, statut_avant="")
            suivis.append(suivi)
            crees.append(suivi)
        if suivis and mission.statut == StatutMission.RAPPORT_DIFFUSE:
            mission.statut = StatutMission.EN_SUIVI
            mission.updated_by = by
            mission.save(update_fields=["statut", "updated_by", "updated_at"])
    for suivi in crees:
        notifier(
            [suivi.responsable],
            type=TypeNotification.SUIVI_OUVERT,
            titre="Nouvelle action à suivre",
            message=f"{mission.reference} : {suivi.action.libelle[:200]} (échéance "
            f"{suivi.echeance:%d/%m/%Y})",
            lien=commun.lien(suivi),
            objet=suivi,
            cle=f"SUIVI_OUVERT:{suivi.pk}",
        )
    for action in ignorees:
        logger.warning(
            "Action %s ignorée à l'ouverture du suivi de la mission %s : "
            "responsable ou échéance manquant.",
            action.id,
            mission.pk,
        )
        notifier(
            commun.rai_actifs(),
            type=TypeNotification.ACTION_IGNOREE,
            titre="Action ignorée à l'ouverture du suivi",
            message=f"{mission.reference} : {action.libelle[:200]} — responsable ou échéance "
            "manquant ; complétez le plan d'actions.",
            lien=f"/missions/{mission.pk}",
            cle=f"ACTION_IGNOREE:{action.id}",
        )
    return suivis, len(crees)


@transaction.atomic
def initialiser_suivi(mission: Mission, *, by: User | None = None) -> list[SuiviAction]:
    """Ouvre le suivi de chaque action active du plan ; idempotent.

    Renvoie tous les suivis de la mission (existants et créés). Une action sans responsable ou
    sans échéance est ignorée, tracée dans les journaux et signalée au RAI.
    """
    return _ouvrir(mission, by)[0]


def reconcilier() -> int:
    """Ouvre les suivis manquants des missions diffusées ; renvoie le nombre créé."""
    total = 0
    missions = Mission.objects.filter(statut__in=STATUTS_OUVRABLES)
    for mission in missions:
        suivies = set(
            SuiviAction.all_objects.filter(mission=mission).values_list("action_id", flat=True)
        )
        if all(
            a.id in suivies or a.responsable_id is None or a.echeance is None
            for a in sources.actions_du_plan(mission)
        ):
            continue
        try:
            with transaction.atomic():
                total += _ouvrir(mission, None)[1]
        except MissionFigeeError:  # pragma: no cover - course avec une suspension
            continue
    return total
