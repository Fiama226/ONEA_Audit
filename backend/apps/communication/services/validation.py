"""Validation du rapport par le RAI (jalon XVIII, D9) : mode figé, confirmation, renvoi.

Garanties de sécurité :

- seul le RAI valide ou renvoie, jamais la personne qui a soumis le rapport (validation) ;
- l'instantané soumis est revérifié contre son empreinte avant toute validation ;
- le mode de signature est lu une seule fois et figé sur le rapport ;
- la confirmation (empreinte SHA-256 de l'instantané et du cycle) est créée dans la même
  transaction que le passage à VALIDE et que la validation de l'étape XVIII ;
- un rapport corrigé (D12) ne touche à aucune étape.
"""

import logging
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.exceptions import RegleMetierError
from apps.core.services import refuser, relire
from apps.missions.models import EtapeMission, StatutMission
from apps.missions.services import FUSEAU_ONEA
from apps.missions.services.declarations import nom_complet
from apps.missions.services.etapes import renvoyer_etape, valider_etape
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.parametres import exigences, mode_requis
from apps.signatures.services import confirmer, empreinte
from apps.users.models import Role, User

from ..models import Rapport, StatutRapport, TypeEvenementRapport
from ._ecriture import journaliser, ouvrir_mission, sauver_transition, verrouiller_etape
from ._versions import TYPE_NOTE_SYNTHETIQUE, TYPE_RAPPORT_FINAL, version_finale
from .diffusion import preremplir_destinataires

logger = logging.getLogger(__name__)

ETAPE_VALIDATION = 18
MSG_RAI = "Seul le responsable de l'audit interne peut valider ou renvoyer le rapport."
MSG_AUTEUR = "Le valideur ne peut pas être la personne qui a soumis le rapport."
MSG_STATUT = "Le rapport n'est pas soumis : il ne peut pas être validé ou renvoyé."
MSG_HORS_PHASE = "La mission n'est pas dans la phase où ce rapport peut être validé."
MSG_EMPREINTE = (
    "L'empreinte du rapport soumis ne correspond plus à son contenu : validation refusée."
)
MSG_MOTIF = "Le motif du renvoi est obligatoire."

CHAMPS_VALIDATION = [
    "statut",
    "valide_par",
    "valide_le",
    "confirmation_validation",
    "mode_signature",
]
CHAMPS_RENVOI = ["statut", "motif_renvoi"]
CHAMPS_REINITIALISATION = [
    "statut",
    "valide_par",
    "valide_le",
    "confirmation_validation",
    "mode_signature",
    "motif_renvoi",
]

__all__ = [
    "reinitialiser_rapport",
    "renvoyer_rapport",
    "valider_rapport",
    "version_finale",
]


def _exiger_rai(by: User) -> None:
    if by.role != Role.RAI:
        raise PermissionDenied(MSG_RAI)


def _statut_attendu(rapport: Rapport) -> str:
    """Rapport initial : mission en communication ; rapport corrigé (D12) : mission diffusée."""
    return str(
        StatutMission.RAPPORT_DIFFUSE
        if rapport.corrige_de_id is not None
        else StatutMission.EN_COMMUNICATION
    )


def _texte_confirmation(rapport: Rapport, by: User) -> str:
    instantane: dict[str, Any] = rapport.instantane_soumis or {}
    constats = instantane.get("constats", [])
    nb_recos = sum(len(c.get("recommandations", [])) for c in constats)
    mission = rapport.mission
    soumis_le = timezone.localtime(rapport.soumis_le, FUSEAU_ONEA) if rapport.soumis_le else None
    date = f"{soumis_le:%d/%m/%Y}" if soumis_le else "—"
    return (
        f"Je soussigné(e) {nom_complet(by)}, Responsable de l'Audit Interne, valide le rapport "
        f"d'audit de la mission {mission.reference} « {mission.titre} » "
        f"(version soumise le {date}, {len(constats)} constats, {nb_recos} recommandations), "
        "que j'atteste exact, objectif, clair, concis et constructif."
    )


def _demander_documents(rapport_id: Any, by: User) -> None:
    """Rapport final puis note synthétique (D10) ; un échec est journalisé sans rien bloquer."""
    from apps.documents.services.generation import demander_generation

    for type_document in (TYPE_RAPPORT_FINAL, TYPE_NOTE_SYNTHETIQUE):
        try:
            demander_generation(type_document=type_document, objet_id=rapport_id, by=by)
        except Exception:  # noqa: BLE001 - la validation est acquise, « Relancer » reste possible
            logger.warning(
                "Génération automatique de %s impossible pour le rapport %s.",
                type_document,
                rapport_id,
                exc_info=True,
            )


@transaction.atomic
def valider_rapport(rapport: Rapport, *, by: User, adresse_ip: str | None = None) -> Rapport:
    """Valide le rapport soumis (RAI, jamais l'auteur de la soumission).

    Fige le mode de signature, crée la confirmation (si le mode l'exige), passe le rapport à
    VALIDE puis valide l'étape XVIII (rapport initial seulement). Après validation de la
    transaction, demande la génération du rapport final et de la note synthétique.
    """
    _exiger_rai(by)
    mission = ouvrir_mission(rapport.mission_id)
    verrouiller_etape(mission.pk, ETAPE_VALIDATION)
    rapport = relire(rapport)
    if rapport.statut != StatutRapport.SOUMIS:
        raise RegleMetierError(MSG_STATUT)
    if mission.statut != _statut_attendu(rapport):
        raise RegleMetierError(MSG_HORS_PHASE)
    if rapport.soumis_par_id == by.pk:
        raise RegleMetierError(MSG_AUTEUR)
    instantane = rapport.instantane_soumis
    if instantane is None or empreinte("rapport", instantane) != rapport.empreinte_soumise:
        raise RegleMetierError(MSG_EMPREINTE)
    corrige = rapport.corrige_de_id is not None

    mode = mode_requis(TypeDocumentSignable.VALIDATION_RAPPORT)
    exigees = exigences(TypeDocumentSignable.VALIDATION_RAPPORT)
    confirmation = None
    if exigees.confirmation:
        confirmation = confirmer(
            type_document=TypeDocumentSignable.VALIDATION_RAPPORT,
            objet=rapport,
            texte=_texte_confirmation(rapport, by),
            donnees={
                **instantane,
                "cycle": rapport.cycle,
                "empreinte_soumise": rapport.empreinte_soumise,
            },
            by=by,
            adresse_ip=adresse_ip,
        )
    avant = rapport.statut
    rapport.valider()
    rapport.valide_par = by
    rapport.valide_le = timezone.now()
    rapport.confirmation_validation = confirmation
    rapport.mode_signature = str(mode)
    sauver_transition(rapport, CHAMPS_VALIDATION, by=by)
    journaliser(rapport, TypeEvenementRapport.VALIDE, by=by, avant=avant)
    if not corrige:
        etape = EtapeMission.objects.get(mission_id=mission.pk, numero=ETAPE_VALIDATION)
        valider_etape(etape, by=by)
        preremplir_destinataires(rapport, by=by)
    rapport_id = rapport.pk
    transaction.on_commit(lambda: _demander_documents(rapport_id, by), robust=True)
    return rapport


def appliquer_renvoi(rapport: Rapport, *, motif: str, by: User) -> None:
    """SOUMIS -> RENVOYE, motif et évènement ; la transaction de l'appelant s'applique."""
    avant = rapport.statut
    rapport.renvoyer()
    rapport.motif_renvoi = motif
    sauver_transition(rapport, CHAMPS_RENVOI, by=by)
    journaliser(rapport, TypeEvenementRapport.RENVOYE, by=by, avant=avant, motif=motif)


def reinitialiser_rapport(rapport: Rapport, *, motif: str, by: User) -> None:
    """SOUMIS, VALIDE ou RENVOYE -> BROUILLON ; efface la validation (la confirmation reste)."""
    avant = rapport.statut
    rapport.reinitialiser()
    rapport.valide_par = None
    rapport.valide_le = None
    rapport.confirmation_validation = None
    rapport.mode_signature = ""
    rapport.motif_renvoi = ""
    sauver_transition(rapport, CHAMPS_REINITIALISATION, by=by)
    journaliser(rapport, TypeEvenementRapport.REINITIALISE, by=by, avant=avant, motif=motif)


@transaction.atomic
def renvoyer_rapport(rapport: Rapport, *, motif: str, by: User) -> Rapport:
    """Renvoie le rapport soumis à l'équipe (RAI, motif obligatoire).

    Rapport initial : `renvoyer_etape(XVIII)` ; le récepteur `etape_changee` applique la
    transition du rapport. Rapport corrigé : transition directe, sans toucher aux étapes.
    """
    _exiger_rai(by)
    mission = ouvrir_mission(rapport.mission_id)
    verrouiller_etape(mission.pk, ETAPE_VALIDATION)
    rapport = relire(rapport)
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    if rapport.statut != StatutRapport.SOUMIS:
        raise RegleMetierError(MSG_STATUT)
    if mission.statut != _statut_attendu(rapport):
        raise RegleMetierError(MSG_HORS_PHASE)
    if rapport.corrige_de_id is not None:
        appliquer_renvoi(rapport, motif=motif, by=by)
        return rapport
    etape = EtapeMission.objects.get(mission_id=mission.pk, numero=ETAPE_VALIDATION)
    renvoyer_etape(etape, motif=motif, by=by)
    rapport = relire(rapport)
    if rapport.statut != StatutRapport.RENVOYE:  # défense : le récepteur n'est pas connecté
        raise RegleMetierError(MSG_STATUT)
    return rapport
