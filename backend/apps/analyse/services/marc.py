"""Matrice d'analyse des risques et contrôles (MARC, D7)."""

from typing import Any

from django.db import transaction
from django.db.models import Count, Q

from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import Mission, RisqueMission
from apps.missions.services.travaux import verrouiller_travaux
from apps.referentiel.models import NiveauRisque
from apps.users.models import User

from ..models import EvaluationConception, LigneMARC
from . import forces_faiblesses

MSG_RISQUE_AUTRE_MISSION = "Ce risque n'appartient pas à la mission."
MSG_OBJECTIF_ACTIF = "Ce contrôle porte un objectif d'audit : retirez d'abord l'objectif."
MSG_RISQUE_ANALYSE = "Ce risque est analysé dans la matrice MARC : retirez d'abord ses lignes."
MSG_RISQUE_FIXE = "Le risque d'une ligne de la matrice ne peut pas être modifié."
MSG_EVALUATION = "Un contrôle existant doit être décrit pour évaluer sa conception."
MSG_CLE = "Un contrôle clé ne peut pas être absent."

_MODIFIABLES = {
    "objet_auditable",
    "operation",
    "objectif_controle",
    "controle_attendu",
    "controle_existant",
    "commentaire",
    "composante",
    "nature",
    "evaluation",
    "cle",
    "ordre",
}
_PREREMPLISSAGE = (
    ("objectif_controle", "objectif_controle"),
    ("controle_attendu", "dispositif_controle"),
)


def _controler(ligne: LigneMARC) -> None:
    """Règles D7 vérifiées avant la base, avec un message par champ."""
    if (
        ligne.evaluation in (EvaluationConception.ADEQUATE, EvaluationConception.INSUFFISANTE)
        and not ligne.controle_existant.strip()
    ):
        raise refuser(MSG_EVALUATION, controle_existant=MSG_EVALUATION)
    if ligne.cle and ligne.evaluation == EvaluationConception.ABSENTE:
        raise refuser(MSG_CLE, cle=MSG_CLE)


def _prochain_ordre(mission: Mission) -> int:
    dernier = (
        LigneMARC.objects.filter(mission=mission).order_by("-ordre").values_list("ordre", flat=True)
    ).first()
    return 0 if dernier is None else dernier + 1


def _preremplir(ligne: LigneMARC, risque: RisqueMission, fournis: set[str]) -> None:
    source = risque.risque_source
    if source is None:
        return
    if "objet_auditable" not in fournis or ligne.objet_auditable_id is None:
        ligne.objet_auditable_id = source.objet_auditable_id
    for champ, origine in _PREREMPLISSAGE:
        if not getattr(ligne, champ).strip():
            setattr(ligne, champ, getattr(source, origine))


def _creer(mission: Mission, risque: RisqueMission, by: User, champs: dict[str, Any]) -> LigneMARC:
    ligne = LigneMARC(mission=mission, risque=risque)
    appliquer(ligne, champs, _MODIFIABLES)
    _preremplir(ligne, risque, set(champs))
    if "ordre" not in champs:
        ligne.ordre = _prochain_ordre(mission)
    _controler(ligne)
    enregistrer(ligne, by=by, creation=True)
    forces_faiblesses.synchroniser(ligne, by=by)
    return ligne


@transaction.atomic
def ajouter_ligne_marc(
    mission: Mission, *, risque: RisqueMission, by: User, **champs: Any
) -> LigneMARC:
    mission = verrouiller_travaux(mission)
    if not RisqueMission.objects.filter(pk=risque.pk, mission=mission).exists():
        raise refuser(MSG_RISQUE_AUTRE_MISSION, risque=MSG_RISQUE_AUTRE_MISSION)
    return _creer(mission, risque, by, champs)


@transaction.atomic
def initialiser_marc(mission: Mission, *, by: User) -> list[LigneMARC]:
    """Crée une ligne pour chaque risque de la mission qui n'en a pas (idempotent)."""
    mission = verrouiller_travaux(mission)
    couverts = set(LigneMARC.objects.filter(mission=mission).values_list("risque_id", flat=True))
    risques = RisqueMission.objects.filter(mission=mission).select_related("risque_source")
    return [
        _creer(mission, risque, by, {})
        for risque in risques.order_by("created_at", "pk")
        if risque.pk not in couverts
    ]


@transaction.atomic
def modifier_ligne_marc(ligne: LigneMARC, *, by: User, **changes: Any) -> LigneMARC:
    verrouiller_travaux(ligne.mission)
    if "risque" in changes or "risque_id" in changes:
        raise refuser(MSG_RISQUE_FIXE, risque=MSG_RISQUE_FIXE)
    ligne = relire(ligne)
    avant = forces_faiblesses.libelle_automatique(ligne)
    appliquer(ligne, changes, _MODIFIABLES)
    _controler(ligne)
    enregistrer(ligne, by=by)
    forces_faiblesses.synchroniser(ligne, by=by, libelle_precedent=avant)
    return ligne


@transaction.atomic
def retirer_ligne_marc(ligne: LigneMARC, *, by: User) -> None:
    verrouiller_travaux(ligne.mission)
    ligne = relire(ligne)
    if ligne.objectifs_audit.exists():
        raise RegleMetierError(MSG_OBJECTIF_ACTIF)
    for liee in ligne.forces_faiblesses.all():
        liee.soft_delete(by)
    ligne.soft_delete(by)


def garde_retrait_risque(rm: RisqueMission) -> None:
    """Garde de `GARDES_RETRAIT` : un risque porteur de lignes actives ne se retire pas."""
    if LigneMARC.objects.filter(risque=rm).exists():
        raise RegleMetierError(MSG_RISQUE_ANALYSE)


def risques_non_couverts(mission: Mission) -> list[str]:
    """Risques moyens ou élevés sans ligne MARC active (code de cartographie ou « Nouveau : … »)."""
    risques = (
        RisqueMission.objects.filter(
            mission=mission, niveau__in=[NiveauRisque.MOYEN, NiveauRisque.ELEVE]
        )
        .annotate(nb=Count("lignes_marc", filter=Q(lignes_marc__deleted_at__isnull=True)))
        .filter(nb=0)
        .order_by("created_at", "pk")
    )
    return [r.code_source or f"Nouveau : {r.libelle[:40]}" for r in risques]
