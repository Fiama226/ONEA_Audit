"""Registre des recommandations : statut de suivi dérivé (jamais stocké), en SQL et en Python.

La même règle existe deux fois : `statut_recommandation(compteurs)` (fonction pure, testée en
table) et `statut_recommandation_expr()` (`Case` / `When` sur des comptes filtrés). Un test
vérifie qu'elles concordent.

Règle : aucune action → « sans action » (ou « risque accepté ») ; toutes closes → « réalisée »
(au moins une clôturée) ou « abandonnée » (toutes abandonnées) ; toutes à lancer → « à lancer » ;
sinon « en cours ».
"""

from dataclasses import dataclass
from datetime import date

from django.db.models import (
    Case,
    Count,
    F,
    IntegerField,
    Min,
    Q,
    QuerySet,
    Value,
    When,
)
from django.db.models.expressions import Combinable

from apps.constats.models import PrioriteRecommandation, Recommandation

from .. import sources
from ..models import STATUTS_CLOS, StatutRecommandationSuivi, StatutSuivi
from .commun import EXPR_EN_RETARD

_ACTIF = Q(suivis__deleted_at__isnull=True)


@dataclass(frozen=True)
class Compteurs:
    total: int
    cloturees: int
    abandonnees: int
    a_lancer: int
    risque_accepte: bool = False


def statut_recommandation(compteurs: Compteurs) -> str:
    """Fonction pure : statut dérivé d'une recommandation à partir des comptes de ses actions."""
    c = compteurs
    if c.total == 0:
        return (
            StatutRecommandationSuivi.RISQUE_ACCEPTE
            if c.risque_accepte
            else StatutRecommandationSuivi.SANS_ACTION
        )
    if c.cloturees + c.abandonnees == c.total:
        return (
            StatutRecommandationSuivi.REALISEE
            if c.cloturees > 0
            else StatutRecommandationSuivi.ABANDONNEE
        )
    if c.a_lancer == c.total:
        return StatutRecommandationSuivi.A_LANCER
    return StatutRecommandationSuivi.EN_COURS


def _compte(*conditions: Q) -> Count:
    critere = _ACTIF
    for condition in conditions:
        critere &= condition
    return Count("suivis", filter=critere, distinct=True)


def _acceptee() -> Combinable:
    champ = sources.CHAMP_RISQUE_ACCEPTE
    if champ is None:
        return Value(0, output_field=IntegerField())
    return Count(champ, filter=Q(**{f"{champ}__deleted_at__isnull": True}), distinct=True)


def statut_recommandation_expr() -> Case:
    """`Case` / `When` sur les comptes annotés par `annoter_registre` (même règle que ci-dessus)."""
    return Case(
        When(Q(actions_total=0, nb_acceptations__gt=0), then=Value("RISQUE_ACCEPTE")),
        When(actions_total=0, then=Value("SANS_ACTION")),
        When(
            Q(actions_total=F("nb_cloturees") + F("nb_abandonnees")) & Q(nb_cloturees__gt=0),
            then=Value("REALISEE"),
        ),
        When(
            actions_total=F("nb_cloturees") + F("nb_abandonnees"),
            then=Value("ABANDONNEE"),
        ),
        When(actions_total=F("nb_a_lancer"), then=Value("A_LANCER")),
        default=Value("EN_COURS"),
    )


def annoter_registre(
    queryset: "QuerySet[Recommandation]", aujourd_hui: date
) -> "QuerySet[Recommandation]":
    """Comptes des actions, statut dérivé et prochaine échéance, sans requête par ligne."""
    ouverte = ~Q(suivis__statut__in=STATUTS_CLOS)
    return (
        queryset.annotate(
            actions_total=_compte(),
            nb_cloturees=_compte(Q(suivis__statut=StatutSuivi.CLOTUREE)),
            nb_abandonnees=_compte(Q(suivis__statut=StatutSuivi.ABANDONNEE)),
            nb_a_lancer=_compte(Q(suivis__statut=StatutSuivi.A_LANCER)),
            actions_closes=_compte(Q(suivis__statut__in=STATUTS_CLOS)),
            actions_en_retard=_compte(EXPR_EN_RETARD(aujourd_hui, "suivis__")),
            nb_acceptations=_acceptee(),
            prochaine_echeance=Min("suivis__echeance", filter=_ACTIF & ouverte),
            priorite_rang=Case(
                When(priorite=PrioriteRecommandation.HAUTE, then=Value(0)),
                When(priorite=PrioriteRecommandation.MOYENNE, then=Value(1)),
                default=Value(2),
                output_field=IntegerField(),
            ),
        )
        .annotate(statut_suivi=statut_recommandation_expr())
        .select_related("mission", "constat__entite")
    )
