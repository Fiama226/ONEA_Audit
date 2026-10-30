"""Contexte de la fiche d'observation (contrat du moteur de documents, lot 4).

Document remis à l'audité : il ne contient que ce que l'audité peut voir. Ni fiches de test,
ni pièces, ni probabilité ni impact (évaluation interne), ni motif de renvoi, ni version figée,
ni identifiant d'utilisateur. Six requêtes au plus, bloc `mission` compris : le constat, ses
causes, ses recommandations et sa dernière réponse (annotée sur le constat) n'en coûtent que
trois de plus. Même conventions de format que `apps.accomplissement.contextes`.
"""

from typing import Any

from django.db.models import OuterRef, Subquery

from apps.accomplissement.contextes import OUI
from apps.analyse.contextes import _date, _libelle, bloc_mission
from apps.referentiel.models import NiveauRisque

from .models import (
    CategorieCause,
    CauseConstat,
    Constat,
    PositionAudite,
    PrioriteRecommandation,
    Recommandation,
    ReponseAudite,
    StatutConstat,
)

CODE_FICHE_OBSERVATION = "FICHE_OBSERVATION"


def _constat_charge(constat: Constat) -> Constat:
    """Le constat avec ses relations et sa dernière réponse du cycle courant, en une requête."""
    courante = ReponseAudite.objects.filter(
        constat=OuterRef("pk"), cycle=OuterRef("cycle")
    ).order_by("-created_at", "-pk")
    charge: Constat = (
        Constat.objects.select_related("mission", "entite", "processus")
        .annotate(
            reponse_position=Subquery(courante.values("position")[:1]),
            reponse_commentaire=Subquery(courante.values("commentaire")[:1]),
            reponse_le=Subquery(courante.values("created_at")[:1]),
        )
        .get(pk=constat.pk)
    )
    return charge


def contexte_fiche_observation(constat: Constat) -> dict[str, Any]:
    c = _constat_charge(constat)
    causes: dict[str, list[str]] = {}
    for cause in CauseConstat.objects.filter(constat=c).order_by("ordre", "created_at"):
        causes.setdefault(cause.categorie, []).append(cause.description)
    recommandations = Recommandation.objects.filter(constat=c).order_by("ordre", "created_at")
    return {
        "mission": bloc_mission(c.mission),
        "provisoire": "" if c.statut == StatutConstat.VALIDE else OUI,
        "constat": {
            "reference": c.reference,
            "titre": c.titre,
            "entite": c.entite.libelle,
            "processus": c.processus.libelle,
            "fait_constate": c.fait_constate,
            "referentiel": c.referentiel,
            "consequence": c.consequence,
            "conclusion": c.conclusion,
            "niveau": _libelle(NiveauRisque, c.niveau),
            "statut": _libelle(StatutConstat, c.statut),
            "soumis_le": _date(c.soumis_le),
            "validee_le": _date(c.validee_le),
        },
        "causes": [
            {"categorie": str(categorie.label), "descriptions": causes[categorie.value]}
            for categorie in CategorieCause
            if categorie.value in causes
        ],
        "recommandations": [
            {
                "numero": str(i),
                "libelle": r.libelle,
                "priorite": _libelle(PrioriteRecommandation, r.priorite),
            }
            for i, r in enumerate(recommandations, start=1)
        ],
        "reponse": {
            "position": _libelle(PositionAudite, getattr(c, "reponse_position", "")),
            "commentaire": getattr(c, "reponse_commentaire", None) or "",
            "le": _date(getattr(c, "reponse_le", None)),
        },
    }
