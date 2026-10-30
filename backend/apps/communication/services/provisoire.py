"""Rapport provisoire (étape XV) et réponses des audités (étape XVI), D7 et D13 du plan du lot 7."""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, QuerySet

from apps.constats.models import Constat, StatutConstat
from apps.core.exceptions import RegleMetierError
from apps.core.services import enregistrer, refuser, relire
from apps.missions.acces import (
    declaration_levee,
    est_chef,
    est_responsable_entite,
    role_dans_mission,
)
from apps.missions.etapes import romain
from apps.missions.exceptions import EtapeCloseError
from apps.missions.gardes import STATUTS_ETAPE_CLOSE
from apps.missions.models import (
    AffectationMission,
    Mission,
    Reunion,
    RoleMission,
    StatutMission,
    TypeReunion,
)
from apps.missions.services import aujourd_hui
from apps.signatures.models import TypeDocumentSignable
from apps.signatures.services import confirmer, empreinte
from apps.users.models import Role, User

from ..droits import peut_lire_rapport_interne
from ..models import (
    Rapport,
    RapportProvisoire,
    ReponseRapport,
    TypeEvenementRapport,
)
from ._ecriture import journaliser, ouvrir_mission, verrouiller_etape
from ._textes import texte_reponse_provisoire
from .assemblage import assembler

logger = logging.getLogger(__name__)

ETAPE_CLOTURE = 15
ETAPE_REPONSES = 16
DELAI_MIN, DELAI_MAX = 1, 60
TYPE_DOCUMENT_PROVISOIRE = "RAPPORT_PROVISOIRE"

MSG_DROIT = "Seul le chef de mission ou le RAI peut transmettre le rapport provisoire."
MSG_REUNION = "Tenez la réunion de clôture avant de transmettre le rapport provisoire."
MSG_AUCUN_CONSTAT = "Aucun constat validé : il n'y a pas de rapport provisoire à transmettre."
MSG_DELAI = "Le délai de réponse doit être compris entre 1 et 60 jours."
MSG_HORS_COMMUNICATION = (
    "La mission n'est pas en phase de communication : le rapport provisoire ne peut pas être "
    "transmis."
)
MSG_AUTRE_MISSION = "Ce rapport n'appartient pas à cette mission."
MSG_CONSTAT_ABSENT = "Ce constat ne figure pas dans le rapport provisoire."
MSG_DROIT_REPONSE = "Seul l'audité responsable de l'entité du constat peut répondre."
MSG_COMMENTAIRE = "Saisissez la réponse de votre direction."
MSG_REPONSES_CLOSES = "La période de réponse au rapport provisoire est close."


@dataclass(frozen=True)
class EtatReponse:
    """Situation de la réponse de la direction à un constat du rapport provisoire."""

    constat_id: UUID
    reference: str
    titre: str
    entite: str
    attendue_de: str
    recue_le: datetime | None
    hors_delai: bool


def provisoire_courant(rapport: Rapport) -> RapportProvisoire | None:
    """Dernier rapport provisoire transmis (le plus récent fait foi)."""
    return RapportProvisoire.objects.filter(rapport=rapport).order_by("-numero").first()


def _references(provisoire: RapportProvisoire) -> list[str]:
    instantane: dict[str, Any] = provisoire.instantane or {}
    return [c["reference"] for c in instantane.get("constats") or []]


def _destinataires(mission: Mission) -> list[User]:
    affectations = AffectationMission.objects.filter(
        mission=mission, role_mission=RoleMission.AUDITE
    ).select_related("utilisateur")
    return [a.utilisateur for a in affectations if a.utilisateur.email]


def _notifier(mission_id: UUID, date_limite: date, nb_constats: int) -> None:
    """Message sans pièce jointe aux audités affectés (appelé après validation)."""
    from apps.core.tasks import send_mail_task

    mission = Mission.objects.get(pk=mission_id)
    for user in _destinataires(mission):
        try:
            send_mail_task.delay(
                [user.email],
                f"Rapport provisoire de la mission {mission.reference}",
                "provisoire_transmis",
                {
                    "name": user.nom_complet,
                    "mission": mission.reference,
                    "titre": mission.titre,
                    "date_limite": date_limite.strftime("%d/%m/%Y"),
                    "nb_constats": nb_constats,
                },
            )
        except Exception:
            logger.warning("Envoi du rapport provisoire impossible à %s", user.pk, exc_info=True)


def _generer(provisoire_id: UUID, by: User) -> None:
    """Demande non bloquante du document : une erreur est journalisée, jamais remontée."""
    from apps.documents.services.generation import demander_generation

    try:
        demander_generation(type_document=TYPE_DOCUMENT_PROVISOIRE, objet_id=provisoire_id, by=by)
    except Exception:
        logger.warning(
            "Génération du rapport provisoire %s impossible", provisoire_id, exc_info=True
        )


def _peut_transmettre(user: User, mission: Mission) -> bool:
    if user.role == Role.RAI:
        return True
    return est_chef(user, mission) and declaration_levee(user, mission)


@transaction.atomic
def transmettre_provisoire(
    rapport: Rapport, *, by: User, delai_jours: int = 15
) -> RapportProvisoire:
    """Fige l'instantané provisoire et ouvre la période de réponse (XV ouverte, réunion tenue)."""
    mission = ouvrir_mission(rapport.mission_id)
    if not _peut_transmettre(by, mission):
        raise PermissionDenied(MSG_DROIT)
    if not DELAI_MIN <= delai_jours <= DELAI_MAX:
        raise refuser(MSG_DELAI, delai_jours=MSG_DELAI)
    statut_xv = verrouiller_etape(mission.pk, ETAPE_CLOTURE)
    if statut_xv in STATUTS_ETAPE_CLOSE:
        raise EtapeCloseError(romain(ETAPE_CLOTURE))
    rapport = relire(rapport)
    if mission.statut != StatutMission.EN_COMMUNICATION:
        raise RegleMetierError(MSG_HORS_COMMUNICATION)
    if rapport.mission_id != mission.pk:
        raise RegleMetierError(MSG_AUTRE_MISSION)
    tenue = Reunion.objects.filter(
        mission=mission, type=TypeReunion.CLOTURE, tenue_le__isnull=False
    ).exists()
    if not tenue:
        raise RegleMetierError(MSG_REUNION)
    if not Constat.objects.filter(mission=mission, statut=StatutConstat.VALIDE).exists():
        raise RegleMetierError(MSG_AUCUN_CONSTAT)
    instantane = assembler(rapport, provisoire=True)
    numero = (
        RapportProvisoire.objects.filter(rapport=rapport).aggregate(m=Max("numero"))["m"] or 0
    ) + 1
    limite = aujourd_hui() + timedelta(days=delai_jours)
    provisoire = RapportProvisoire(
        mission=mission,
        rapport=rapport,
        numero=numero,
        transmis_par=by,
        date_limite_reponses=limite,
        instantane=instantane,
        empreinte=empreinte("rapport_provisoire", instantane),
    )
    enregistrer(provisoire, by=by, creation=True)
    journaliser(rapport, TypeEvenementRapport.PROVISOIRE_TRANSMIS, by=by, avant=rapport.statut)
    nb = len(instantane.get("constats") or [])
    mission_id, provisoire_id = mission.pk, provisoire.pk
    transaction.on_commit(lambda: _notifier(mission_id, limite, nb))
    transaction.on_commit(lambda: _generer(provisoire_id, by))
    return provisoire


@transaction.atomic
def repondre_provisoire(
    provisoire: RapportProvisoire,
    *,
    constat: Constat,
    commentaire: str,
    by: User,
    adresse_ip: str | None = None,
) -> ReponseRapport:
    """Réponse confirmée de la direction à un constat du rapport provisoire (D7)."""
    mission = ouvrir_mission(provisoire.mission_id)
    if by.role != Role.AUDITE:
        raise PermissionDenied(MSG_DROIT_REPONSE)
    statut_xvi = verrouiller_etape(mission.pk, ETAPE_REPONSES)
    if statut_xvi in STATUTS_ETAPE_CLOSE:
        raise RegleMetierError(MSG_REPONSES_CLOSES)
    provisoire = relire(provisoire)
    constat = relire(constat)
    if constat.mission_id != mission.pk or constat.reference not in _references(provisoire):
        raise RegleMetierError(MSG_CONSTAT_ABSENT)
    if constat.entite_id is None or not est_responsable_entite(by, mission, constat.entite_id):
        raise PermissionDenied(MSG_DROIT_REPONSE)
    commentaire = commentaire.strip()
    if not commentaire:
        raise refuser(MSG_COMMENTAIRE, commentaire=MSG_COMMENTAIRE)
    courant = provisoire_courant(provisoire.rapport) or provisoire
    hors_delai = aujourd_hui() > courant.date_limite_reponses
    confirmation = confirmer(
        type_document=TypeDocumentSignable.REPONSE_RAPPORT_PROVISOIRE,
        objet=provisoire,
        texte=texte_reponse_provisoire(
            constat, provisoire, by, mission_reference=mission.reference
        ),
        donnees={
            "provisoire": str(provisoire.pk),
            "numero": provisoire.numero,
            "empreinte": provisoire.empreinte,
            "constat": constat.reference,
            "commentaire": commentaire,
            "hors_delai": hors_delai,
        },
        by=by,
        adresse_ip=adresse_ip,
    )
    reponse = ReponseRapport(
        mission=mission,
        provisoire=provisoire,
        constat=constat,
        auteur=by,
        commentaire=commentaire,
        confirmation=confirmation,
        hors_delai=hors_delai,
    )
    enregistrer(reponse, by=by, creation=True)
    return reponse


def reponses_visibles(user: User, provisoire: RapportProvisoire) -> QuerySet[ReponseRapport]:
    """RAI et intervenants : toutes ; audité affecté : les siennes ; autres : aucune (D13)."""
    qs = ReponseRapport.objects.filter(provisoire=provisoire)
    mission = provisoire.mission
    if peut_lire_rapport_interne(user, mission):
        return qs
    if user.role == Role.AUDITE and role_dans_mission(user, mission) == RoleMission.AUDITE:
        return qs.filter(auteur=user)
    return qs.none()


def etat_reponses(provisoire: RapportProvisoire) -> list[EtatReponse]:
    """Par constat du provisoire : direction attendue, date de la dernière réponse, retard."""
    constats = {
        c.reference: c
        for c in Constat.objects.filter(
            mission_id=provisoire.mission_id, reference__in=_references(provisoire)
        ).select_related("entite")
    }
    dernieres: dict[UUID, ReponseRapport] = {}
    for reponse in ReponseRapport.objects.filter(provisoire=provisoire).order_by(
        "created_at", "pk"
    ):
        dernieres[reponse.constat_id] = reponse
    etats: list[EtatReponse] = []
    for reference in _references(provisoire):
        constat = constats.get(reference)
        if constat is None:
            continue
        reponse = dernieres.get(constat.pk)
        entite = constat.entite.libelle if constat.entite_id else ""
        etats.append(
            EtatReponse(
                constat_id=constat.pk,
                reference=constat.reference,
                titre=constat.titre,
                entite=entite,
                attendue_de=entite,
                recue_le=reponse.created_at if reponse else None,
                hors_delai=reponse.hors_delai if reponse else False,
            )
        )
    return etats
