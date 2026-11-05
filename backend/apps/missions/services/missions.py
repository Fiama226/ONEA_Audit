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
from apps.gouvernance import regles_gouvernance
from apps.referentiel.models import Direction, Processus, Risque
from apps.referentiel.services import version_courante
from apps.signatures.models import Confirmation, TypeDocumentSignable
from apps.signatures.services import confirmer
from apps.users.models import User

from ..etapes import ETAPES
from ..gardes import verrouiller_mission
from ..models import (
    ROLES_INTERVENANTS,
    EtapeMission,
    EvenementDeclencheur,
    EvenementEtape,
    Mission,
    RoleMission,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
)
from ..notifications import notifier_ordre_emis
from . import LOCK_REFERENCE_MISSION, aujourd_hui, objectivite
from .declarations import nom_complet

MSG_DIFFUSION = (
    "Le rapport ne peut être diffusé que lorsque les étapes XV à XVIII sont closes "
    "et le rapport validé."
)
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
    "risques_couverts",
}
M2M = frozenset({"processus", "entites", "risques_couverts"})
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


MSG_RISQUES_REQUIS = (
    "Une mission inscrite au programme annuel doit désigner au moins un risque de la "
    "cartographie qu'elle couvre (règle de gouvernance « lien programme ↔ risque »)."
)
MSG_RISQUE_AUTRE_CARTOGRAPHIE = (
    "Les risques couverts doivent appartenir à la cartographie de référence de la mission."
)


def _verifier_risques(mission: Mission, risques: list[Risque]) -> None:
    """Risques de la cartographie de la mission ; au moins un pour une mission du programme
    quand la règle de gouvernance l'exige (lue au moment de l'action, jamais rétroactive)."""
    if any(r.version_id != mission.cartographie_id for r in risques):
        msg = MSG_RISQUE_AUTRE_CARTOGRAPHIE
        raise refuser(msg, risques_couverts=msg)
    if (
        not risques
        and mission.evenement_declencheur == EvenementDeclencheur.PROGRAMME_ANNUEL
        and regles_gouvernance.program_risk_link_required()
    ):
        raise refuser(MSG_RISQUES_REQUIS, risques_couverts=MSG_RISQUES_REQUIS)


def _poser_m2m(
    mission: Mission, champ: str, valeurs: Iterable[Processus | Direction | Risque]
) -> None:
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
    risques_couverts: Iterable[Risque] = (),
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
    risques = list(risques_couverts)
    _verifier_risques(mission, risques)
    _verifier_et_enregistrer(mission, by)
    for definition in ETAPES:
        etape = EtapeMission(mission=mission, numero=definition.numero)
        enregistrer(etape, by=by, creation=True)
    _poser_m2m(mission, "processus", processus)
    _poser_m2m(mission, "entites", entites)
    _poser_m2m(mission, "risques_couverts", risques)
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
    if "risques_couverts" in changes:
        changes["risques_couverts"] = list(changes["risques_couverts"])
        _verifier_risques(mission, changes["risques_couverts"])
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


def _verifier_programme_approuve(mission: Mission) -> None:
    """Mission du programme annuel : programme de l'année approuvé avant le lancement, quand la
    règle de gouvernance « approbation du programme annuel » l'exige (Normes IIA 9.4)."""
    if mission.evenement_declencheur != EvenementDeclencheur.PROGRAMME_ANNUEL:
        return
    regle = regles_gouvernance.program_approval()
    if regle["approver"] == "NONE" or not regle["required_before_launch"]:
        return
    from apps.programmation.services import programme_approuve_pour

    if not programme_approuve_pour(mission.annee):
        approbateur = "le DG et le Conseil" if regle["approver"] == "DG_AND_BOARD" else "le DG"
        msg = (
            f"Le programme annuel {mission.annee} n'est pas approuvé par {approbateur} : "
            "la mission ne peut pas être lancée (règle de gouvernance)."
        )
        raise refuser(msg, programme=msg)


@transaction.atomic
def lancer_mission(mission: Mission, *, by: User) -> Mission:
    mission = verrouiller_mission(mission)
    if mission.statut != StatutMission.PLANIFIEE:
        raise _pas_possible(mission, "lancer la mission")
    if not mission.affectations.filter(role_mission=RoleMission.CHEF_MISSION).exists():
        raise refuser(MSG_CHEF, chef_mission=MSG_CHEF)
    _verifier_programme_approuve(mission)
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
    objectivite.controler_equipe(mission, by=by)

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
    notifier_ordre_emis(mission, by=by)
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


@transaction.atomic
def marquer_rapport_diffuse(mission: Mission, *, by: User) -> Mission:
    """Passe EN_COMMUNICATION à RAPPORT_DIFFUSE quand XV à XVIII sont closes et XVIII validée."""
    mission = verrouiller_mission(mission)
    if mission.statut != StatutMission.EN_COMMUNICATION:
        raise _pas_possible(mission, "diffuser le rapport")
    statuts = dict(
        EtapeMission.objects.select_for_update()
        .filter(mission=mission, numero__gte=15)
        .values_list("numero", "statut")
    )
    closes = {StatutEtape.TERMINEE, StatutEtape.VALIDEE, StatutEtape.NON_APPLICABLE}
    pret = (
        all(statuts.get(n) in closes for n in range(15, 19))
        and statuts.get(18) == StatutEtape.VALIDEE
    )
    if not pret:
        raise RegleMetierError(MSG_DIFFUSION)
    mission.statut = StatutMission.RAPPORT_DIFFUSE
    enregistrer(mission, by=by)
    return mission
