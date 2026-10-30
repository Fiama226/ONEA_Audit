"""Récepteurs de `etape_changee` pour le rapport (D9) : défense en profondeur du jalon XVIII.

Ils sont appelés dans la transaction du moteur d'étapes : une exception annule la transition.
"""

from typing import Any

from apps.core.exceptions import RegleMetierError
from apps.missions.models import EtapeMission, TypeEvenementEtape
from apps.missions.signals import etape_changee

from .models import Rapport, StatutRapport

ETAPE_VALIDATION = 18
ETAPES_RAPPORT = range(15, 19)
MSG_VALIDER_DEPUIS_RAPPORT = "Validez le rapport depuis l'écran du rapport."
MSG_DIFFUSE = "Le rapport est diffusé : émettez un rapport corrigé."


def _rapport_actif(mission_id: Any) -> Rapport | None:
    """Rapport actif de la mission, verrouillé (jamais le rapport remplacé)."""
    rapport: Rapport | None = (
        Rapport.objects.select_for_update()
        .filter(mission_id=mission_id)
        .exclude(statut=StatutRapport.REMPLACE)
        .order_by("numero_version")
        .last()
    )
    return rapport


def _sur_validee(
    sender: type[EtapeMission],  # noqa: ARG001
    *,
    etape: EtapeMission,
    type_evenement: str,
    **_: Any,
) -> None:
    """XVIII ne se valide que si le rapport est VALIDE (jamais par la route générique)."""
    if etape.numero != ETAPE_VALIDATION or type_evenement != TypeEvenementEtape.VALIDEE:
        return
    rapport = _rapport_actif(etape.mission_id)
    if rapport is None or rapport.statut != StatutRapport.VALIDE:
        raise RegleMetierError(MSG_VALIDER_DEPUIS_RAPPORT)


def _sur_renvoyee(
    sender: type[EtapeMission],  # noqa: ARG001
    *,
    etape: EtapeMission,
    par: Any,
    type_evenement: str,
    motif: str,
    **_: Any,
) -> None:
    """XVIII renvoyée : le rapport SOUMIS passe à RENVOYE avec le même motif."""
    from .services.validation import appliquer_renvoi

    if etape.numero != ETAPE_VALIDATION or type_evenement != TypeEvenementEtape.RENVOYEE:
        return
    rapport = _rapport_actif(etape.mission_id)
    if rapport is not None and rapport.statut == StatutRapport.SOUMIS:
        appliquer_renvoi(rapport, motif=motif, by=par)


def _sur_rouverte(
    sender: type[EtapeMission],  # noqa: ARG001
    *,
    etape: EtapeMission,
    par: Any,
    type_evenement: str,
    motif: str,
    **_: Any,
) -> None:
    """Réouverture de XV à XVIII : rapport réinitialisé, ou refus s'il est diffusé."""
    from .services.validation import reinitialiser_rapport

    if etape.numero not in ETAPES_RAPPORT or type_evenement != TypeEvenementEtape.ROUVERTE:
        return
    rapport = _rapport_actif(etape.mission_id)
    if rapport is None:
        return
    if rapport.statut == StatutRapport.DIFFUSE:
        raise RegleMetierError(MSG_DIFFUSE)
    if rapport.statut != StatutRapport.BROUILLON:
        reinitialiser_rapport(rapport, motif=motif, by=par)


def connecter() -> None:
    """Connexion idempotente (un `dispatch_uid` par récepteur)."""
    for recepteur, uid in (
        (_sur_validee, "communication.rapport.etape_validee"),
        (_sur_renvoyee, "communication.rapport.etape_renvoyee"),
        (_sur_rouverte, "communication.rapport.etape_rouverte"),
    ):
        etape_changee.connect(recepteur, sender=EtapeMission, dispatch_uid=uid)
