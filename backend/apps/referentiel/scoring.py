from .models import NiveauRisque, PrioriteRisque

SEUIL_MOYEN = 8
SEUIL_ELEVE = 15


def niveau_pour_score(score: int) -> NiveauRisque:
    """Niveau de risque : FAIBLE 1-7, MOYEN 8-14, ELEVE 15-25."""
    if score >= SEUIL_ELEVE:
        return NiveauRisque.ELEVE
    if score >= SEUIL_MOYEN:
        return NiveauRisque.MOYEN
    return NiveauRisque.FAIBLE


def priorite_par_defaut(niveau: NiveauRisque) -> PrioriteRisque:
    """Priorité proposée à partir du niveau (modifiable ensuite)."""
    return {
        NiveauRisque.ELEVE: PrioriteRisque.PRIORITAIRE,
        NiveauRisque.MOYEN: PrioriteRisque.AMELIORATION,
        NiveauRisque.FAIBLE: PrioriteRisque.OBSERVATION,
    }[NiveauRisque(niveau)]
