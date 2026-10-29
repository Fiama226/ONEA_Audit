"""Cycle de vie de la mission, numérotation des références, ordre de mission (D2, D3, D10)."""

from collections.abc import Iterable
from typing import Any

from django.db import connection, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser
from apps.referentiel.models import Direction, Processus
from apps.referentiel.services import version_courante
from apps.signatures.models import Confirmation, TypeDocumentSignable
from apps.signatures.services import confirmer
from apps.users.models import User

from ..etapes import ETAPES
from ..gardes import verrouiller_mission
from ..models import (
    ROLES_INTERVENANTS,
    EtapeMission,
    EvenementEtape,
    Mission,
    RoleMission,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
)
from . import LOCK_REFERENCE_MISSION, aujourd_hui
from .declarations import nom_complet

CHAMPS_MODIFIABLES = {
    "titre",
    "type",
    "evenement_declencheur",
    "evenement_precision",
    "periode_debut",
    "periode_fin",
    "date_debut_prevue",
    "date_fin_prevue",
    "budget_jours",
    "objectifs",
    "perimetre",
    "exclusions",
    "clients",
    "livrables_attendus",
    "processus",
    "entites",
}
M2M = frozenset({"processus", "entites"})
SUSPENDABLES = frozenset(
    {
        StatutMission.PLANIFIEE,
        StatutMission.EN_PLANIFICATION,
        StatutMission.EN_ACCOMPLISSEMENT,
        StatutMission.EN_COMMUNICATION,
    }
)
MSG_OBLIGATOIRE_PLANIFIER = "Ce champ est obligatoire pour planifier la mission."
MSG_OBLIGATOIRE_ORDRE = "Ce champ est obligatoire pour émettre l'ordre de mission."
# Statuts où l'étape I peut être (ré)close par une émission : D8 laisse rouvrir I dans toute
# phase, et D17 impose alors une nouvelle émission.
STATUTS_ORDRE = frozenset(
    {
        StatutMission.EN_PLANIFICATION,
        StatutMission.EN_ACCOMPLISSEMENT,
        StatutMission.EN_COMMUNICATION,
    }
)
MSG_MOTIF = "Le motif est obligatoire."
MSG_CHEF = "Désignez un chef de mission avant de lancer la mission."

_TEXTE_ORDRE = (
    "Je soussigné(e) {nom_complet}, Responsable de l'Audit Interne, émets l'ordre de mission "
    "{reference} « {titre} » selon les objectifs, le périmètre, l'équipe et le calendrier "
    "enregistrés ce jour dans la plateforme."
)


def _pas_possible(mission: Mission, action: str) -> RegleMetierError:
    etat = mission.get_statut_display().lower()
    if mission.statut == StatutMission.BROUILLON:
        etat = f"en {etat}"
    msg = f"Impossible de {action} : la mission est {etat}."
    return refuser(msg, statut=msg)


def _motif(motif: str) -> str:
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    return motif


def _verifier_dates(mission: Mission) -> None:
    erreurs: dict[str, list[str]] = {}
    if (
        mission.date_debut_prevue
        and mission.date_fin_prevue
        and mission.date_fin_prevue < mission.date_debut_prevue
    ):
        erreurs["date_fin_prevue"] = ["La date de fin doit suivre la date de début."]
    if (
        mission.periode_debut
        and mission.periode_fin
        and mission.periode_fin < mission.periode_debut
    ):
        erreurs["periode_fin"] = ["La fin de la période doit suivre son début."]
    if mission.budget_jours is not None and mission.budget_jours < 0:
        erreurs["budget_jours"] = ["Le budget ne peut pas être négatif."]
    if erreurs:
        raise RegleMetierError("Données invalides.", erreurs)


def _poser_m2m(mission: Mission, champ: str, valeurs: Iterable[Processus | Direction]) -> None:
    cibles = {v.pk for v in valeurs}
    relation = getattr(mission, champ)
    if {o.pk for o in relation.all()} != cibles:
        relation.set(cibles)


@transaction.atomic
def creer_mission(
    *,
    titre: str,
    type: str,  # noqa: A002
    by: User,
    processus: Iterable[Processus] = (),
    entites: Iterable[Direction] = (),
    **champs: Any,
) -> Mission:
    version = version_courante()
    if version is None:
        msg = (
            "Aucune cartographie des risques validée : validez une cartographie "
            "avant de créer une mission."
        )
        raise refuser(msg, cartographie=msg)
    mission = Mission(titre=titre, type=type, cartographie=version)
    appliquer(mission, champs, CHAMPS_MODIFIABLES - M2M)
    _verifier_et_enregistrer(mission, by)
    for definition in ETAPES:
        etape = EtapeMission(mission=mission, numero=definition.numero)
        enregistrer(etape, by=by, creation=True)
    _poser_m2m(mission, "processus", processus)
    _poser_m2m(mission, "entites", entites)
    return mission


def _verifier_et_enregistrer(mission: Mission, by: User) -> None:
    # `enregistrer` rend d'abord les erreurs de champs ; les dates sont contrôlées avant pour
    # que le CHECK de base ne soit jamais la première garde atteinte.
    _verifier_dates(mission)
    enregistrer(mission, by=by, creation=True)


@transaction.atomic
def modifier_mission(mission: Mission, *, by: User, **changes: Any) -> Mission:
    mission = verrouiller_mission(mission)
    appliquer(mission, changes, CHAMPS_MODIFIABLES, m2m=M2M)
    _verifier_dates(mission)
    enregistrer(mission, by=by)
    for champ in M2M & set(changes):
        _poser_m2m(mission, champ, changes[champ])
    return mission


@transaction.atomic
def supprimer_mission(mission: Mission, *, by: User) -> None:
    mission = verrouiller_mission(mission)
    if mission.statut != StatutMission.BROUILLON:
        msg = "Seule une mission en brouillon peut être supprimée ; annulez-la."
        raise refuser(msg, statut=msg)
    for affectation in mission.affectations.all():
        declaration = getattr(affectation, "declaration", None)
        if declaration is not None and declaration.deleted_at is None:
            declaration.soft_delete(by)
        affectation.soft_delete(by)
    for etape in mission.etapes.all():
        etape.soft_delete(by)
    mission.soft_delete(by)


def _manquants_planification(mission: Mission) -> dict[str, list[str]]:
    manquants = {
        "titre": not mission.titre.strip(),
        "type": not mission.type,
        "processus": not mission.processus.exists(),
        "entites": not mission.entites.exists(),
        "date_debut_prevue": mission.date_debut_prevue is None,
        "date_fin_prevue": mission.date_fin_prevue is None,
    }
    return {champ: [MSG_OBLIGATOIRE_PLANIFIER] for champ, vide in manquants.items() if vide}


@transaction.atomic
def planifier_mission(mission: Mission, *, by: User) -> Mission:
    mission = verrouiller_mission(mission)
    if mission.statut != StatutMission.BROUILLON:
        raise _pas_possible(mission, "planifier la mission")
    erreurs = _manquants_planification(mission)
    if erreurs or mission.date_debut_prevue is None:
        raise RegleMetierError("Des informations obligatoires manquent.", erreurs)
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_REFERENCE_MISSION])
    annee = mission.date_debut_prevue.year
    dernier = Mission.all_objects.filter(annee=annee).aggregate(m=Max("numero"))["m"] or 0
    mission.annee = annee
    mission.numero = dernier + 1
    mission.reference = f"DAI/{annee}/M{mission.numero:02d}"
    mission.statut = StatutMission.PLANIFIEE
    enregistrer(mission, by=by)
    return mission


def _etape(mission: Mission, numero: int) -> EtapeMission:
    etape: EtapeMission = EtapeMission.objects.select_for_update().get(
        mission=mission, numero=numero
    )
    return etape


@transaction.atomic
def lancer_mission(mission: Mission, *, by: User) -> Mission:
    mission = verrouiller_mission(mission)
    if mission.statut != StatutMission.PLANIFIEE:
        raise _pas_possible(mission, "lancer la mission")
    if not mission.affectations.filter(role_mission=RoleMission.CHEF_MISSION).exists():
        raise refuser(MSG_CHEF, chef_mission=MSG_CHEF)
    mission.statut = StatutMission.EN_PLANIFICATION
    enregistrer(mission, by=by)
    etape = _etape(mission, 1)
    avant = etape.statut
    etape.demarrer()
    etape.date_debut_reelle = aujourd_hui()
    enregistrer(etape, by=by)
    with actor_scope(by):
        EvenementEtape.journaliser(etape, TypeEvenementEtape.DEMARREE, par=by, statut_avant=avant)
    return mission


def _donnees_ordre(mission: Mission) -> dict[str, Any]:
    equipe = [
        {"nom": nom_complet(a.utilisateur), "role_mission": a.role_mission}
        for a in mission.affectations.filter(role_mission__in=ROLES_INTERVENANTS)
        .select_related("utilisateur")
        .order_by("created_at")
    ]
    return {
        "reference": mission.reference,
        "titre": mission.titre,
        "type": mission.type,
        "objectifs": mission.objectifs,
        "perimetre": mission.perimetre,
        "exclusions": mission.exclusions,
        "clients": mission.clients,
        "livrables_attendus": mission.livrables_attendus,
        "processus": sorted(mission.processus.values_list("code", flat=True)),
        "entites": sorted(mission.entites.values_list("code", flat=True)),
        "periode_debut": mission.periode_debut,
        "periode_fin": mission.periode_fin,
        "date_debut_prevue": mission.date_debut_prevue,
        "date_fin_prevue": mission.date_fin_prevue,
        "equipe": equipe,
    }


@transaction.atomic
def emettre_ordre_mission(
    mission: Mission, *, by: User, adresse_ip: str | None = None
) -> Confirmation:
    mission = verrouiller_mission(mission)
    if mission.statut not in STATUTS_ORDRE:
        raise _pas_possible(mission, "émettre l'ordre de mission")
    etape = _etape(mission, 1)
    if etape.statut not in (StatutEtape.EN_COURS, StatutEtape.RENVOYEE):
        msg = "L'ordre de mission a déjà été émis."
        raise refuser(msg, statut=msg)
    erreurs = {
        champ: [MSG_OBLIGATOIRE_ORDRE]
        for champ in ("objectifs", "perimetre")
        if not getattr(mission, champ).strip()
    }
    if erreurs:
        raise RegleMetierError("Des informations obligatoires manquent.", erreurs)

    texte = _TEXTE_ORDRE.format(
        nom_complet=nom_complet(by), reference=mission.reference, titre=mission.titre
    )
    confirmation = confirmer(
        type_document=TypeDocumentSignable.ORDRE_MISSION,
        objet=mission,
        texte=texte,
        donnees=_donnees_ordre(mission),
        by=by,
        adresse_ip=adresse_ip,
    )
    if mission.ordre_mission_emis_le is None:
        mission.ordre_mission_emis_le = confirmation.confirme_le
        enregistrer(mission, by=by)
    avant = etape.statut
    etape.terminer()
    etape.terminee_par = by
    etape.date_fin_reelle = aujourd_hui()
    enregistrer(etape, by=by)
    with actor_scope(by):
        EvenementEtape.journaliser(etape, TypeEvenementEtape.TERMINEE, par=by, statut_avant=avant)
    return confirmation


@transaction.atomic
def suspendre_mission(mission: Mission, *, motif: str, by: User) -> Mission:
    mission = verrouiller_mission(mission)
    if mission.statut not in SUSPENDABLES:
        raise _pas_possible(mission, "suspendre la mission")
    mission.statut_avant_suspension = mission.statut
    mission.motif_suspension = _motif(motif)
    mission.statut = StatutMission.SUSPENDUE
    enregistrer(mission, by=by)
    return mission


def _verrouiller_sans_garde(mission: Mission) -> Mission:
    """Verrou de ligne sans refus des missions figées (reprise et annulation depuis SUSPENDUE)."""
    verrouillee = Mission.objects.select_for_update().filter(pk=mission.pk).first()
    if verrouillee is None:
        raise Http404("Mission introuvable.")
    return verrouillee


def _sauver_champs(mission: Mission, champs: list[str], by: User) -> None:
    mission.updated_by = by
    mission.updated_at = timezone.now()
    with actor_scope(by):
        mission.save(update_fields=[*champs, "updated_by", "updated_at"])


@transaction.atomic
def reprendre_mission(mission: Mission, *, by: User) -> Mission:
    mission = _verrouiller_sans_garde(mission)
    if mission.statut != StatutMission.SUSPENDUE:
        raise _pas_possible(mission, "reprendre la mission")
    mission.statut = mission.statut_avant_suspension
    mission.statut_avant_suspension = ""
    _sauver_champs(mission, ["statut", "statut_avant_suspension"], by)
    return mission


@transaction.atomic
def annuler_mission(mission: Mission, *, motif: str, by: User) -> Mission:
    mission = _verrouiller_sans_garde(mission)
    if mission.statut not in SUSPENDABLES | {StatutMission.SUSPENDUE}:
        raise _pas_possible(mission, "annuler la mission")
    mission.motif_annulation = _motif(motif)
    mission.statut = StatutMission.ANNULEE
    _sauver_champs(mission, ["statut", "motif_annulation"], by)
    return mission
