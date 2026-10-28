"""Moteur des 18 étapes (D8) : transitions, changements de phase (D2) et droits d'action (D4)."""

from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import models, transaction
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.users.models import Role, User

from .. import acces
from ..etapes import ETAPES_DE_PHASE, JALON_DE_PHASE, JALONS, PHASE_DU_STATUT, romain
from ..gardes import verrouiller_mission
from ..models import (
    EtapeMission,
    EvenementEtape,
    Mission,
    Phase,
    StatutEtape,
    StatutMission,
    TypeEvenementEtape,
    TypeMission,
)
from .livrables import declarations_en_attente, livrables_manquants

MSG_MOTIF = "Le motif est obligatoire."
MSG_DECLARATION = "Confirmez votre déclaration d'indépendance avant de contribuer à la mission."
MSG_DROIT = "Vous n'avez pas le droit d'effectuer cette action."

CLOSES = frozenset({StatutEtape.TERMINEE, StatutEtape.VALIDEE, StatutEtape.NON_APPLICABLE})
BLOQUANTS = frozenset({StatutEtape.RENVOYEE, StatutEtape.A_REVALIDER})
_ORDRE_PHASE = {Phase.PLANIFICATION: 0, Phase.ACCOMPLISSEMENT: 1, Phase.COMMUNICATION: 2}
_CHAMPS_PLANIFIABLES = {
    "date_debut_prevue",
    "date_fin_prevue",
    "charge_prevue_jours",
    "charge_reelle_jours",
}


class ActionEtape(models.TextChoices):
    DEMARRER = "DEMARRER", "Démarrer"
    TERMINER = "TERMINER", "Terminer"
    VALIDER = "VALIDER", "Valider"
    RENVOYER = "RENVOYER", "Renvoyer"
    ROUVRIR = "ROUVRIR", "Rouvrir"
    NON_APPLICABLE = "NON_APPLICABLE", "Marquer non applicable"
    RETABLIR = "RETABLIR", "Rétablir"
    PLANIFIER = "PLANIFIER", "Planifier"


A = ActionEtape


# --------------------------------------------------------------------------- règles d'état


def _phase_de(etape: EtapeMission) -> Phase:
    return etape.definition.phase


def _verifier_etat(action: str, etape: EtapeMission, mission: Mission, user: User) -> None:
    """Règles de D8 portant sur l'état ; lève `RegleMetierError` avec le message métier."""
    statut = etape.statut
    if mission.statut not in PHASE_DU_STATUT:
        if mission.statut == StatutMission.PLANIFIEE:
            raise RegleMetierError("Lancez la mission avant de conduire ses étapes.")
        raise RegleMetierError("Les étapes de cette mission ne sont plus modifiables.")
    if action == A.PLANIFIER:
        return
    if action == A.DEMARRER:
        if statut != StatutEtape.A_FAIRE:
            raise RegleMetierError("Seule une étape à faire peut être démarrée.")
        courante = PHASE_DU_STATUT[mission.statut]
        if _ORDRE_PHASE[_phase_de(etape)] > _ORDRE_PHASE[courante]:
            raise RegleMetierError(
                f"L'étape {romain(etape.numero)} appartient à une phase qui n'a pas commencé."
            )
    elif action == A.TERMINER:
        if etape.numero == 1:
            raise RegleMetierError("L'étape I se termine par l'émission de l'ordre de mission.")
        if statut not in (StatutEtape.EN_COURS, StatutEtape.RENVOYEE):
            raise RegleMetierError("Seule une étape en cours ou renvoyée peut être terminée.")
    elif action in (A.VALIDER, A.RENVOYER):
        if etape.numero not in JALONS:
            raise RegleMetierError("Seuls les jalons VI, X, XIII et XVIII sont validés.")
        autorises = (
            (StatutEtape.TERMINEE, StatutEtape.A_REVALIDER)
            if action == A.VALIDER
            else (StatutEtape.TERMINEE,)
        )
        if statut not in autorises:
            raise RegleMetierError("Le jalon n'est pas dans un état permettant cette action.")
        if etape.terminee_par_id is not None and etape.terminee_par_id == user.pk:
            raise RegleMetierError("Le valideur ne peut pas être l'auteur de l'étape.")
    elif action == A.ROUVRIR:
        if statut not in (StatutEtape.TERMINEE, StatutEtape.VALIDEE, StatutEtape.A_REVALIDER):
            raise RegleMetierError("Seule une étape terminée ou validée peut être rouverte.")
    elif action == A.NON_APPLICABLE:
        if mission.type != TypeMission.CONSEIL:
            raise RegleMetierError(
                "Seules les missions de conseil peuvent avoir des étapes non applicables."
            )
        if etape.numero in JALONS:
            raise RegleMetierError("Un jalon ne peut pas être marqué non applicable.")
        if etape.numero == 1:
            raise RegleMetierError("L'étape I ne peut pas être marquée non applicable.")
        if statut not in (StatutEtape.A_FAIRE, StatutEtape.EN_COURS):
            raise RegleMetierError("Cette étape ne peut pas être marquée non applicable.")
    elif action == A.RETABLIR and statut != StatutEtape.NON_APPLICABLE:
        raise RegleMetierError("Seule une étape non applicable peut être rétablie.")


def _role_permet(action: str, etape: EtapeMission, mission: Mission, user: User) -> bool:
    """Droits de D4 (rôle global, rôle dans la mission, déclaration levée)."""
    if action == A.DEMARRER:
        return acces.peut_contribuer(user, mission)
    if action in (A.TERMINER, A.NON_APPLICABLE, A.RETABLIR):
        return acces.est_chef(user, mission) and acces.declaration_levee(user, mission)
    if action in (A.VALIDER, A.RENVOYER):
        return acces.peut_valider_jalon(user, mission, etape.numero)
    if action == A.ROUVRIR:
        if user.role == Role.RAI:
            return True
        return (
            etape.numero != 18
            and acces.est_superviseur(user, mission)
            and acces.declaration_levee(user, mission)
        )
    if action == A.PLANIFIER:
        return user.role == Role.RAI or (
            acces.est_chef(user, mission) and acces.declaration_levee(user, mission)
        )
    return False


def actions_possibles(etape: EtapeMission, user: User) -> list[str]:
    """Actions que `user` peut exécuter sur l'étape ; sert aussi de garde dans les vues."""
    mission = Mission.objects.get(pk=etape.mission_id)
    possibles: list[str] = []
    for action in ActionEtape:
        try:
            _verifier_etat(action, etape, mission, user)
        except RegleMetierError:
            continue
        if _role_permet(action, etape, mission, user):
            possibles.append(action.value)
    return possibles


def _exiger_role(action: str, etape: EtapeMission, mission: Mission, user: User) -> None:
    if _role_permet(action, etape, mission, user):
        return
    if acces.est_intervenant(user, mission) and not acces.declaration_levee(user, mission):
        raise PermissionDenied(MSG_DECLARATION)
    raise PermissionDenied(MSG_DROIT)


def _motif(motif: str) -> str:
    motif = motif.strip()
    if not motif:
        raise refuser(MSG_MOTIF, motif=MSG_MOTIF)
    return motif


# --------------------------------------------------------------------------- transitions


def _ouvrir(etape: EtapeMission, action: str, user: User) -> tuple[Mission, EtapeMission]:
    """Verrouille la mission puis l'étape, vérifie les règles d'état puis les droits."""
    mission = verrouiller_mission(etape.mission_id)
    frais = relire(etape)
    _verifier_etat(action, frais, mission, user)
    _exiger_role(action, frais, mission, user)
    return mission, frais


def _journaliser(etape: EtapeMission, type_: str, *, by: User, motif: str, avant: str) -> None:
    with actor_scope(by):
        EvenementEtape.journaliser(etape, type_, par=by, motif=motif, statut_avant=avant)


def _aujourd_hui() -> Any:
    return timezone.localdate()


@transaction.atomic
def demarrer_etape(etape: EtapeMission, *, by: User) -> EtapeMission:
    mission, etape = _ouvrir(etape, A.DEMARRER, by)
    if etape.numero >= 2:
        noms = declarations_en_attente(mission.pk)
        if noms:
            message = f"Déclarations d'indépendance en attente : {', '.join(noms)}."
            raise refuser(message, declarations=message)
    avant = etape.statut
    etape.demarrer()
    if etape.date_debut_reelle is None:
        etape.date_debut_reelle = _aujourd_hui()
    enregistrer(etape, by=by)
    _journaliser(etape, TypeEvenementEtape.DEMARREE, by=by, motif="", avant=avant)
    return etape


@transaction.atomic
def terminer_etape(etape: EtapeMission, *, by: User) -> EtapeMission:
    mission, etape = _ouvrir(etape, A.TERMINER, by)
    manquants = livrables_manquants(etape)
    if manquants:
        raise RegleMetierError("Livrables manquants.", {"livrables": manquants})
    avant = etape.statut
    etape.terminer()
    etape.terminee_par = by
    etape.date_fin_reelle = _aujourd_hui()
    enregistrer(etape, by=by)
    _journaliser(etape, TypeEvenementEtape.TERMINEE, by=by, motif="", avant=avant)
    avancer_phase(mission, by=by)
    return etape


@transaction.atomic
def valider_etape(etape: EtapeMission, *, by: User) -> EtapeMission:
    mission, etape = _ouvrir(etape, A.VALIDER, by)
    avant = etape.statut
    etape.valider()
    etape.validee_par = by
    etape.validee_le = timezone.now()
    enregistrer(etape, by=by)
    _journaliser(etape, TypeEvenementEtape.VALIDEE, by=by, motif="", avant=avant)
    avancer_phase(mission, by=by)
    return etape


@transaction.atomic
def renvoyer_etape(etape: EtapeMission, *, motif: str, by: User) -> EtapeMission:
    motif = _motif(motif)
    _, etape = _ouvrir(etape, A.RENVOYER, by)
    avant = etape.statut
    etape.renvoyer()
    enregistrer(etape, by=by)
    _journaliser(etape, TypeEvenementEtape.RENVOYEE, by=by, motif=motif, avant=avant)
    return etape


@transaction.atomic
def rouvrir_etape(etape: EtapeMission, *, motif: str, by: User) -> EtapeMission:
    motif = _motif(motif)
    mission, etape = _ouvrir(etape, A.ROUVRIR, by)
    avant = etape.statut
    etape.rouvrir()
    etape.date_fin_reelle = None
    etape.validee_par = None
    etape.validee_le = None
    enregistrer(etape, by=by)
    _journaliser(etape, TypeEvenementEtape.ROUVERTE, by=by, motif=motif, avant=avant)
    validees = EtapeMission.objects.select_for_update().filter(
        mission=mission, numero__gt=etape.numero, statut=StatutEtape.VALIDEE
    )
    for autre in validees.order_by("numero"):
        avant_autre = autre.statut
        autre.a_revalider()
        enregistrer(autre, by=by)
        _journaliser(
            autre,
            TypeEvenementEtape.A_REVALIDER,
            by=by,
            motif=f"Étape {romain(etape.numero)} rouverte : {motif}",
            avant=avant_autre,
        )
    return etape


@transaction.atomic
def marquer_non_applicable(etape: EtapeMission, *, motif: str, by: User) -> EtapeMission:
    motif = _motif(motif)
    _, etape = _ouvrir(etape, A.NON_APPLICABLE, by)
    avant = etape.statut
    etape.non_applicable()
    etape.motif_non_applicable = motif
    enregistrer(etape, by=by)
    _journaliser(etape, TypeEvenementEtape.NON_APPLICABLE, by=by, motif=motif, avant=avant)
    avancer_phase(verrouiller_mission(etape.mission_id), by=by)
    return etape


@transaction.atomic
def retablir_etape(etape: EtapeMission, *, by: User) -> EtapeMission:
    _, etape = _ouvrir(etape, A.RETABLIR, by)
    avant = etape.statut
    etape.retablir()
    etape.motif_non_applicable = ""
    enregistrer(etape, by=by)
    _journaliser(etape, TypeEvenementEtape.RETABLIE, by=by, motif="", avant=avant)
    return etape


@transaction.atomic
def planifier_etape(etape: EtapeMission, *, by: User, **changes: Any) -> EtapeMission:
    """Dates prévues et charges (D12) ; l'état de l'étape n'est pas modifié."""
    _, etape = _ouvrir(etape, A.PLANIFIER, by)
    appliquer(etape, changes, _CHAMPS_PLANIFIABLES)
    erreurs: dict[str, list[str]] = {}
    debut, fin = etape.date_debut_prevue, etape.date_fin_prevue
    if debut is not None and fin is not None and fin < debut:
        erreurs["date_fin_prevue"] = [
            "La date de fin prévue doit être postérieure ou égale à la date de début prévue."
        ]
    for champ in ("charge_prevue_jours", "charge_reelle_jours"):
        valeur = getattr(etape, champ)
        if valeur is not None and Decimal(valeur) < 0:
            erreurs[champ] = ["La charge ne peut pas être négative."]
    if erreurs:
        raise RegleMetierError("Données invalides.", erreurs)
    enregistrer(etape, by=by)
    return etape


# --------------------------------------------------------------------------- phases (D2)


def _phase_terminee(statuts: dict[int, str], phase: Phase) -> bool:
    numeros = ETAPES_DE_PHASE[phase]
    if any(statuts.get(n) not in CLOSES for n in numeros):
        return False
    if statuts.get(JALON_DE_PHASE[phase]) != StatutEtape.VALIDEE:
        return False
    return not any(statuts.get(n) in BLOQUANTS for n in range(1, numeros[-1] + 1))


@transaction.atomic
def avancer_phase(mission: Mission, *, by: User) -> bool:
    """Passe la mission à la phase suivante quand la dernière condition est remplie (D2)."""
    verrouillee = verrouiller_mission(mission)
    statuts: dict[int, str] = dict(
        EtapeMission.objects.filter(mission=verrouillee).values_list("numero", "statut")
    )
    cible = {
        StatutMission.EN_PLANIFICATION: (Phase.PLANIFICATION, StatutMission.EN_ACCOMPLISSEMENT),
        StatutMission.EN_ACCOMPLISSEMENT: (Phase.ACCOMPLISSEMENT, StatutMission.EN_COMMUNICATION),
    }.get(verrouillee.statut)
    if cible is None or not _phase_terminee(statuts, cible[0]):
        return False
    verrouillee.statut = cible[1]
    verrouillee.updated_by = by
    with actor_scope(by):
        verrouillee.save(update_fields=["statut", "updated_by", "updated_at"])
    avancer_phase(verrouillee, by=by)
    return True
