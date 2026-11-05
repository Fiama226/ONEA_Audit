"""Contrôles de clôture qui exigent la participation de l'audité, et dérogation motivée.

Règle de gouvernance « réponse de l'audité » : trois contrôles, activables séparément,
s'ajoutent aux livrables des étapes XIII (accord de l'entité sur les résultats des tests), XIV
(position de l'audité sur chaque constat validé) et XVI (réponse au rapport provisoire, ou délai
échu). Quand l'audité ne répond pas, l'autorité désignée par la règle (RAI ou DG) peut déroger,
avec un motif (obligatoire selon la règle) écrit au journal de l'étape. La dérogation vaut pour
l'étape tant qu'elle n'est pas rouverte.

Les applications enregistrent leur contrôle par `enregistrer_controle_audite` (dans `ready`).
"""

from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import refuser, relire
from apps.gouvernance import regles_gouvernance
from apps.users.models import User

from ..etapes import romain
from ..gardes import STATUTS_FIGES, verrouiller_mission
from ..models import EtapeMission, EvenementEtape, StatutEtape, TypeEvenementEtape
from .livrables import Controle, enregistrer_controles

ETAPES_REPONSE_AUDITE = (13, 14, 16)
STATUTS_OUVERTS = (StatutEtape.EN_COURS, StatutEtape.RENVOYEE)
MSG_MOTIF = "Le motif de la dérogation est obligatoire."
MSG_RIEN = "Rien n'attend la réponse de l'audité sur cette étape : aucune dérogation n'est utile."
MSG_ETAPE = "Seules les étapes XIII, XIV et XVI ouvertes admettent cette dérogation."
MSG_DEJA = "Une dérogation est déjà accordée pour cette étape."
MSG_DROIT = {
    "RAI": "Seul le RAI peut déroger à l'absence de réponse de l'audité (règle de gouvernance).",
    "DG": "Seul le DG peut déroger à l'absence de réponse de l'audité (règle de gouvernance).",
}

# Étape -> contrôles bruts (règle active, sans tenir compte d'une dérogation).
_CONTROLES: dict[int, list[Controle]] = {}


def enregistrer_controle_audite(numero: int, champ_regle: str, controle: Controle) -> None:
    """Ajoute un contrôle « réponse de l'audité » à l'étape `numero`.

    Le contrôle ne joue que si le champ `champ_regle` de la règle est vrai, et se tait quand une
    dérogation est accordée pour l'étape. À appeler une fois (au chargement de l'application).
    """

    def brut(etape: EtapeMission) -> str | list[str] | None:
        if not regles_gouvernance.auditee_response()[champ_regle]:
            return None
        return controle(etape)

    def garde(etape: EtapeMission) -> str | list[str] | None:
        if derogation_active(etape):
            return None
        return brut(etape)

    _CONTROLES.setdefault(numero, []).append(brut)
    enregistrer_controles(numero, garde)


def manquants_audite(etape: EtapeMission) -> list[str]:
    """Messages des contrôles « réponse de l'audité » de l'étape (dérogation ignorée)."""
    messages: list[str] = []
    for controle in _CONTROLES.get(etape.numero, []):
        resultat = controle(etape)
        if isinstance(resultat, str):
            resultat = [resultat]
        messages.extend(m for m in resultat or [] if m)
    return messages


def derogation_active(etape: EtapeMission) -> bool:
    """Une dérogation journalisée après la dernière réouverture de l'étape."""
    evenements = EvenementEtape.objects.filter(
        etape_id=etape.pk,
        type__in=(TypeEvenementEtape.DEROGATION, TypeEvenementEtape.ROUVERTE),
    ).order_by("-le", "-created_at")
    dernier = evenements.values_list("type", flat=True).first()
    return dernier == TypeEvenementEtape.DEROGATION


def _exiger_role(by: User) -> dict[str, Any]:
    regle = regles_gouvernance.auditee_response()
    if by.role != regle["waiver_by"] or not by.is_active:
        raise PermissionDenied(MSG_DROIT[regle["waiver_by"]])
    return regle


@transaction.atomic
def deroger(etape: EtapeMission, *, motif: str, by: User) -> EvenementEtape:
    """Dérogation motivée à l'absence de réponse de l'audité, écrite au journal de l'étape."""
    regle = _exiger_role(by)
    verrouiller_mission(etape.mission_id)
    etape = relire(etape)
    if etape.numero not in ETAPES_REPONSE_AUDITE or etape.statut not in STATUTS_OUVERTS:
        raise RegleMetierError(MSG_ETAPE)
    motif = motif.strip()
    if regle["reason_required"] and not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    if derogation_active(etape):
        raise RegleMetierError(MSG_DEJA)
    manquants = manquants_audite(etape)
    if not manquants:
        raise RegleMetierError(MSG_RIEN)
    texte = (
        f"Dérogation à la réponse de l'audité (étape {romain(etape.numero)}) : "
        f"{motif or 'sans motif (non exigé par la règle)'}. Manquait : {' '.join(manquants)}"
    )
    with actor_scope(by):
        return EvenementEtape.journaliser(
            etape, TypeEvenementEtape.DEROGATION, par=by, motif=texte, statut_avant=etape.statut
        )


def etapes_a_deroger(user: User) -> list[dict[str, Any]]:
    """Étapes ouvertes bloquées par l'absence de réponse de l'audité, pour l'autorité désignée."""
    regle = regles_gouvernance.auditee_response()
    if user.role != regle["waiver_by"] or not user.is_active:
        return []
    etapes = (
        EtapeMission.objects.filter(numero__in=ETAPES_REPONSE_AUDITE, statut__in=STATUTS_OUVERTS)
        .exclude(mission__statut__in=STATUTS_FIGES)
        .select_related("mission")
        .order_by("mission__reference", "numero")
    )
    resultat: list[dict[str, Any]] = []
    for etape in etapes:
        if derogation_active(etape):
            continue
        manquants = manquants_audite(etape)
        if manquants:
            resultat.append(
                {"etape": etape, "romain": romain(etape.numero), "manquants": manquants}
            )
    return resultat
