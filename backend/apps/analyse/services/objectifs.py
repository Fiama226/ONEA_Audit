"""Objectifs d'audit de l'étape VII (D9 du plan du lot 5)."""

from typing import Any

from django.db import transaction
from django.db.models import Max

from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.missions.models import Mission
from apps.missions.services.travaux import verrouiller_travaux
from apps.users.models import User

from .. import gardes
from ..models import LigneMARC, MotifNonTest, ObjectifAudit

MSG_ETAPE_VII = "Commencez l'étape VII pour sélectionner les objectifs d'audit."
PREFIXE_LIBELLE = "S'assurer de l'efficacité et de l'efficience du contrôle : "
_MODIFIABLES = {"libelle", "retenu", "motif_non_test", "justification"}


def ouvrir_ecriture(mission: Mission) -> Mission:
    """Verrouille la mission puis exige VII active et VI validée (transaction requise)."""
    verrouillee = verrouiller_travaux(mission)
    gardes.exiger_actives(verrouillee.pk, une_de=(7,), message=MSG_ETAPE_VII)
    gardes.exiger_vi_validee(verrouillee.pk)
    return verrouillee


def _libelle_par_defaut(ligne: LigneMARC) -> str:
    return PREFIXE_LIBELLE + (ligne.controle_existant or ligne.controle_attendu)[:300]


def _prochain_numero(mission: Mission) -> int:
    # Les objectifs retirés comptent : un numéro n'est jamais réattribué.
    maximum = ObjectifAudit.all_objects.filter(mission=mission).aggregate(m=Max("numero"))["m"]
    return (maximum or 0) + 1


def _creer(mission: Mission, ligne: LigneMARC, libelle: str, by: User) -> ObjectifAudit:
    objectif = ObjectifAudit(
        mission=mission,
        ligne_marc=ligne,
        numero=_prochain_numero(mission),
        libelle=libelle,
        retenu=True,
    )
    enregistrer(objectif, by=by, creation=True)
    return objectif


@transaction.atomic
def initialiser_objectifs(mission: Mission, *, by: User) -> list[ObjectifAudit]:
    mission = ouvrir_ecriture(mission)
    pourvues = ObjectifAudit.objects.filter(mission=mission).values("ligne_marc_id")
    lignes = (
        LigneMARC.objects.filter(mission=mission, cle=True)
        .exclude(pk__in=pourvues)
        .order_by("ordre", "created_at")
    )
    return [_creer(mission, ligne, _libelle_par_defaut(ligne), by) for ligne in lignes]


@transaction.atomic
def ajouter_objectif(
    mission: Mission, *, ligne_marc: LigneMARC, by: User, libelle: str = ""
) -> ObjectifAudit:
    mission = ouvrir_ecriture(mission)
    ligne = LigneMARC.objects.filter(pk=ligne_marc.pk, mission=mission).first()
    if ligne is None:
        message = "Cette ligne n'appartient pas à la mission."
        raise refuser(message, ligne_marc=message)
    if not ligne.cle:
        message = "Seul un contrôle clé porte un objectif d'audit."
        raise refuser(message, ligne_marc=message)
    if ObjectifAudit.objects.filter(mission=mission, ligne_marc=ligne).exists():
        message = "Ce contrôle porte déjà un objectif d'audit."
        raise refuser(message, ligne_marc=message)
    return _creer(mission, ligne, libelle.strip() or _libelle_par_defaut(ligne), by)


@transaction.atomic
def modifier_objectif(objectif: ObjectifAudit, *, by: User, **changes: Any) -> ObjectifAudit:
    ouvrir_ecriture(objectif.mission)
    objectif = relire(objectif)
    appliquer(objectif, changes, _MODIFIABLES)
    objectif.libelle = objectif.libelle.strip()
    if not objectif.libelle:
        message = "Le libellé est obligatoire."
        raise refuser(message, libelle=message)
    if objectif.retenu:
        objectif.motif_non_test = ""
        objectif.justification = ""
    else:
        erreurs: dict[str, str] = {}
        if not objectif.motif_non_test:
            erreurs["motif_non_test"] = "Le motif est obligatoire pour un contrôle non testé."
        elif objectif.motif_non_test not in MotifNonTest.values:
            erreurs["motif_non_test"] = "Motif inconnu."
        if not objectif.justification.strip():
            erreurs["justification"] = "La justification est obligatoire."
        if erreurs:
            raise refuser("Données invalides.", **erreurs)
    enregistrer(objectif, by=by)
    return objectif


@transaction.atomic
def retirer_objectif(objectif: ObjectifAudit, *, by: User) -> None:
    ouvrir_ecriture(objectif.mission)
    relire(objectif).soft_delete(by)
