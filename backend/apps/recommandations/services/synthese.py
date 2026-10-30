"""Synthèse du plan d'actions (D8) : 4 requêtes, avertissements non bloquants."""

import datetime
from dataclasses import dataclass, field

from apps.constats.models import Recommandation, StatutConstat
from apps.missions.models import Mission
from apps.users.models import User

from ..models import AcceptationRisque, Action, EngagementPlanActions, StatutAction
from .engagements import EtatEngagement, etat_depuis
from .statuts import SANS_ACTION, statut_recommandation


@dataclass(frozen=True)
class LigneRecommandation:
    constat: str
    reference: str
    libelle: str
    priorite: str
    statut_derive: str
    nb_actions: int
    acceptation: AcceptationRisque | None


@dataclass(frozen=True)
class LigneResponsable:
    utilisateur: User
    nb_actions: int
    prochaine_echeance: datetime.date | None
    engagement: EtatEngagement


@dataclass(frozen=True)
class SynthesePlan:
    recommandations: list[LigneRecommandation] = field(default_factory=list)
    responsables: list[LigneResponsable] = field(default_factory=list)
    recommandations_sans_suite: list[str] = field(default_factory=list)
    actions_incompletes: list[str] = field(default_factory=list)
    engagements_manquants: list[str] = field(default_factory=list)


_OUVERTES = (StatutAction.A_LANCER, StatutAction.EN_COURS)


def synthese_plan(mission: Mission) -> SynthesePlan:
    recos = list(
        Recommandation.objects.filter(mission=mission, constat__statut=StatutConstat.VALIDE)
        .select_related("constat")
        .order_by("constat__numero", "ordre")
    )
    actions = list(Action.objects.filter(mission=mission).select_related("responsable"))
    acceptations = {
        a.recommandation_id: a for a in AcceptationRisque.objects.filter(mission=mission)
    }
    dernier: dict[object, EngagementPlanActions] = {}
    for e in EngagementPlanActions.objects.filter(mission=mission).order_by("-created_at", "-pk"):
        dernier.setdefault(e.auteur_id, e)

    par_reco: dict[object, list[Action]] = {}
    par_responsable: dict[object, list[Action]] = {}
    for a in actions:
        par_reco.setdefault(a.recommandation_id, []).append(a)
        if a.responsable_id is not None:
            par_responsable.setdefault(a.responsable_id, []).append(a)

    resultat = SynthesePlan()
    for r in recos:
        liees = par_reco.get(r.pk, [])
        acceptation = acceptations.get(r.pk)
        statut = statut_recommandation(r, actions=liees, acceptation=acceptation)
        reference = f"{r.constat.reference}-{r.ordre}"
        resultat.recommandations.append(
            LigneRecommandation(
                r.constat.reference,
                reference,
                r.libelle,
                r.priorite,
                statut,
                len(liees),
                acceptation,
            )
        )
        if statut == SANS_ACTION:
            resultat.recommandations_sans_suite.append(reference)
    resultat.actions_incompletes.extend(
        a.reference
        for a in sorted(actions, key=lambda x: x.numero)
        if a.responsable_id is None or a.echeance is None or not a.indicateur.strip()
    )
    for pk, liees in par_responsable.items():
        echeances = [a.echeance for a in liees if a.echeance and a.statut in _OUVERTES]
        utilisateur = liees[0].responsable
        etat = etat_depuis(sorted(liees, key=lambda x: x.numero), dernier.get(pk))
        resultat.responsables.append(
            LigneResponsable(utilisateur, len(liees), min(echeances, default=None), etat)
        )
        if etat != "CONFIRME":
            resultat.engagements_manquants.append(utilisateur.nom_complet)
    resultat.responsables.sort(key=lambda x: x.utilisateur.nom_complet)
    return resultat
