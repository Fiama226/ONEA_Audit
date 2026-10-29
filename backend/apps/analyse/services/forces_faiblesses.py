"""Forces et faiblesses apparentes (D8) : lignes liées à la MARC et lignes manuelles."""

from typing import Any

from django.db import transaction

from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import Mission
from apps.missions.services.travaux import verrouiller_travaux
from apps.users.models import User

from ..gardes import exiger_actives
from ..models import ForceFaiblesse, LigneMARC

MSG_FENETRE = "Commencez l'étape V pour constituer le référentiel d'audit."
MSG_LIEE = "Cette ligne suit la matrice MARC : modifiez la ligne MARC."
_LIBELLE_MAX = 500


def verrouiller_fenetre(mission: Mission) -> Mission:
    """Verrouille la mission et exige V ou VI en cours (D4) ; 422 sinon."""
    mission = verrouiller_travaux(mission)
    exiger_actives(mission.pk, une_de=(5, 6), message=MSG_FENETRE)
    return mission


_MODIFIABLES_LIEE = {"libelle", "consequence", "commentaire", "ordre"}
_MODIFIABLES_MANUELLE = _MODIFIABLES_LIEE | {"type", "processus"}


def libelle_automatique(ligne: LigneMARC) -> str:
    """Libellé initial : contrôle existant, ou « Absence de contrôle : {objectif, 200 car.} »."""
    if ligne.controle_existant.strip():
        return ligne.controle_existant.strip()[:_LIBELLE_MAX]
    objectif = ligne.objectif_controle.strip()[:200]
    return f"Absence de contrôle : {objectif}" if objectif else "Absence de contrôle"


@transaction.atomic
def synchroniser(
    ligne: LigneMARC, *, by: User, libelle_precedent: str | None = None
) -> ForceFaiblesse | None:
    """Aligne la ligne liée sur l'évaluation de `ligne` (créée, mise à jour ou retirée).

    `libelle_precedent` : libellé automatique d'avant la modification ; un libellé reformulé
    par l'équipe (différent) est conservé.
    """
    existante: ForceFaiblesse | None = (
        ForceFaiblesse.objects.select_for_update().filter(ligne_marc=ligne).first()
    )
    appreciation = ligne.appreciation
    if appreciation is None:
        if existante is not None:
            existante.soft_delete(by)
        return None
    libelle = libelle_automatique(ligne)
    if existante is None:
        ff = ForceFaiblesse(
            mission_id=ligne.mission_id,
            ligne_marc=ligne,
            type=appreciation,
            processus_id=ligne.risque.processus_id,
            libelle=libelle,
            ordre=ligne.ordre,
        )
        enregistrer(ff, by=by, creation=True)
        return ff
    existante.type = appreciation
    if libelle_precedent is not None and existante.libelle == libelle_precedent:
        existante.libelle = libelle
    enregistrer(existante, by=by)
    return existante


def _controler_processus(mission: Mission, processus: Any) -> None:
    if processus is not None and not mission.processus.filter(pk=processus.pk).exists():
        message = "Le processus doit être un processus de la mission."
        raise refuser(message, processus=message)


@transaction.atomic
def ajouter_force_faiblesse(
    mission: Mission,
    *,
    type: str,
    libelle: str,
    by: User,
    **champs: Any,  # noqa: A002
) -> ForceFaiblesse:
    mission = verrouiller_fenetre(mission)
    ff = ForceFaiblesse(mission=mission, type=type, libelle=libelle.strip())
    _controler_processus(mission, champs.get("processus"))
    appliquer(ff, champs, {"consequence", "commentaire", "ordre", "processus"})
    enregistrer(ff, by=by, creation=True)
    return ff


@transaction.atomic
def modifier_force_faiblesse(ff: ForceFaiblesse, *, by: User, **changes: Any) -> ForceFaiblesse:
    verrouiller_fenetre(ff.mission)
    ff = relire(ff)
    if ff.ligne_marc_id is not None and "type" in changes:
        raise refuser(MSG_LIEE, type=MSG_LIEE)
    if "libelle" in changes:
        changes["libelle"] = str(changes["libelle"]).strip()
    _controler_processus(ff.mission, changes.get("processus"))
    appliquer(ff, changes, _MODIFIABLES_LIEE if ff.ligne_marc_id else _MODIFIABLES_MANUELLE)
    enregistrer(ff, by=by)
    return ff


@transaction.atomic
def retirer_force_faiblesse(ff: ForceFaiblesse, *, by: User) -> None:
    verrouiller_fenetre(ff.mission)
    ff = relire(ff)
    if ff.ligne_marc_id is not None:
        raise refuser(MSG_LIEE)
    ff.soft_delete(by)
