"""Forces et faiblesses apparentes (D8) : lignes liées à la MARC et lignes manuelles."""

from typing import Any

from django.db import transaction

from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import Mission
from apps.missions.services.travaux import verrouiller_travaux
from apps.users.models import User

from ..models import ForceFaiblesse, LigneMARC

MSG_LIEE = "Cette ligne suit la matrice MARC : modifiez la ligne MARC."
_LIBELLE_MAX = 500
_MODIFIABLES_LIEE = {"libelle", "consequence", "commentaire", "ordre"}
_MODIFIABLES_MANUELLE = _MODIFIABLES_LIEE | {"type", "processus"}


def libelle_automatique(ligne: LigneMARC) -> str:
    """Libellé initial : contrôle existant, ou « Absence de contrôle : {objectif, 200 car.} »."""
    if ligne.controle_existant.strip():
        return ligne.controle_existant.strip()[:_LIBELLE_MAX]
    return f"Absence de contrôle : {ligne.objectif_controle.strip()[:200]}"


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


@transaction.atomic
def ajouter_force_faiblesse(
    mission: Mission,
    *,
    type: str,
    libelle: str,
    by: User,
    **champs: Any,  # noqa: A002
) -> ForceFaiblesse:
    mission = verrouiller_travaux(mission)
    ff = ForceFaiblesse(mission=mission, type=type, libelle=libelle.strip())
    appliquer(ff, champs, {"consequence", "commentaire", "ordre", "processus"})
    enregistrer(ff, by=by, creation=True)
    return ff


@transaction.atomic
def modifier_force_faiblesse(ff: ForceFaiblesse, *, by: User, **changes: Any) -> ForceFaiblesse:
    verrouiller_travaux(ff.mission)
    ff = relire(ff)
    if ff.ligne_marc_id is not None and "type" in changes:
        raise refuser(MSG_LIEE, type=MSG_LIEE)
    if "libelle" in changes:
        changes["libelle"] = str(changes["libelle"]).strip()
    appliquer(ff, changes, _MODIFIABLES_LIEE if ff.ligne_marc_id else _MODIFIABLES_MANUELLE)
    enregistrer(ff, by=by)
    return ff


@transaction.atomic
def retirer_force_faiblesse(ff: ForceFaiblesse, *, by: User) -> None:
    verrouiller_travaux(ff.mission)
    ff = relire(ff)
    if ff.ligne_marc_id is not None:
        raise refuser(MSG_LIEE)
    ff.soft_delete(by)
