"""Statut dérivé d'une recommandation (D8, §14)."""

from collections.abc import Iterable

from ..models import AcceptationRisque, Action, StatutAction

RISQUE_ACCEPTE = "RISQUE_ACCEPTE"
SANS_ACTION = "SANS_ACTION"
A_LANCER = StatutAction.A_LANCER.value
EN_COURS = StatutAction.EN_COURS.value
REALISEE = StatutAction.REALISEE.value

LIBELLES = {
    RISQUE_ACCEPTE: "Risque accepté",
    SANS_ACTION: "Sans action",
    A_LANCER: "À lancer",
    EN_COURS: "En cours",
    REALISEE: "Réalisée",
}


class _Inconnu:
    """Marque « non fourni » : distingue l'absence d'acceptation de la non-lecture."""


INCONNU = _Inconnu()


def statut_depuis(statuts: Iterable[str], *, acceptee: bool) -> str:
    """Règle pure : acceptation, puis absence d'action, puis statuts des actions."""
    if acceptee:
        return RISQUE_ACCEPTE
    liste = list(statuts)
    if not liste:
        return SANS_ACTION
    cloturees = {StatutAction.REALISEE, StatutAction.ABANDONNEE}
    if all(s in cloturees for s in liste) and StatutAction.REALISEE in liste:
        return REALISEE
    if any(s in (StatutAction.EN_COURS, StatutAction.REALISEE) for s in liste):
        return EN_COURS
    return A_LANCER


def statut_recommandation(
    reco: object,
    *,
    actions: Iterable[Action] | None = None,
    acceptation: AcceptationRisque | None | _Inconnu = INCONNU,
) -> str:
    """Statut dérivé ; avec `actions` et `acceptation` fournis, aucune requête."""
    if acceptation is INCONNU:
        acceptee = AcceptationRisque.objects.filter(recommandation=reco).exists()
    else:
        acceptee = acceptation is not None
    if acceptee:
        return RISQUE_ACCEPTE
    if actions is None:
        statuts = list(Action.objects.filter(recommandation=reco).values_list("statut", flat=True))
    else:
        statuts = [a.statut for a in actions]
    return statut_depuis(statuts, acceptee=False)
