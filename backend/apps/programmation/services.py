"""Services métier du programme annuel : création, cohérence référentielle, numérotation,
validation et gel. Toute écriture commence par le verrouillage du programme."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q, Sum
from django.http import Http404
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.referentiel.models import Direction, ObjetAuditable, Processus
from apps.users.models import User

from .exceptions import ProgrammeFigeError
from .models import (
    LigneProgramme,
    ProgrammeAnnuel,
    StatutProgramme,
    TypeIntervention,
)

_CHAMPS_PROGRAMME = {"libelle", "commentaire"}
_CHAMPS_LIGNE = {
    "titre",
    "type",
    "processus",
    "objet_auditable",
    "entites",
    "debut_prevu",
    "fin_prevue",
    "charge_prevue_jours",
    "justification",
}

MSG_ANNEE_IMMUABLE = "L'année d'un programme ne peut pas être modifiée."
MSG_PROGRAMME_IMMUABLE = "Une mission prévue ne peut pas changer de programme."


def _verrouiller_programme(programme: ProgrammeAnnuel | Any) -> ProgrammeAnnuel:
    """Relit le programme sous verrou de ligne ; refuse s'il est validé."""
    locked = ProgrammeAnnuel.objects.select_for_update().filter(pk=programme.pk).first()
    if locked is None:
        raise Http404("Non trouvé.")
    if locked.statut == StatutProgramme.VALIDE:
        raise ProgrammeFigeError(locked.annee)
    return locked


def _msg_annee_prise(annee: int) -> str:
    return f"Un programme annuel existe déjà pour l'année {annee}."


# --------------------------------------------------------------------------- programmes


@transaction.atomic
def creer_programme(
    *, annee: int, libelle: str = "", commentaire: str = "", by: User
) -> ProgrammeAnnuel:
    if not 2000 <= annee <= 2100:
        msg = "L'année doit être comprise entre 2000 et 2100."
        raise refuser(msg, annee=msg)
    programme = ProgrammeAnnuel(
        annee=annee,
        libelle=libelle or f"Programme annuel d'audit interne {annee}",
        commentaire=commentaire,
    )

    def controle() -> None:
        if ProgrammeAnnuel.objects.filter(annee=annee).exists():
            msg = _msg_annee_prise(annee)
            raise refuser(msg, annee=msg)

    try:
        enregistrer(programme, by=by, creation=True, controle=controle)
    except IntegrityError as e:  # course sur l'unicité de l'année
        msg = _msg_annee_prise(annee)
        raise refuser(msg, annee=msg) from e
    return programme


@transaction.atomic
def modifier_programme(programme: ProgrammeAnnuel, *, by: User, **changes: Any) -> ProgrammeAnnuel:
    locked = _verrouiller_programme(programme)
    if "annee" in changes:
        if changes.pop("annee") != locked.annee:
            raise refuser(MSG_ANNEE_IMMUABLE, annee=MSG_ANNEE_IMMUABLE)
    appliquer(locked, changes, _CHAMPS_PROGRAMME)
    enregistrer(locked, by=by)
    return locked


@transaction.atomic
def supprimer_programme(programme: ProgrammeAnnuel, *, by: User) -> None:
    locked = _verrouiller_programme(programme)
    for une_ligne in LigneProgramme.objects.filter(programme=locked):
        une_ligne.soft_delete(by)
    locked.soft_delete(by)


@transaction.atomic
def valider_programme(programme: ProgrammeAnnuel, *, by: User) -> ProgrammeAnnuel:
    locked = _verrouiller_programme(programme)
    if not LigneProgramme.objects.filter(programme=locked).exists():
        raise RegleMetierError("Un programme sans mission prévue ne peut pas être validé.")
    locked.valider()
    locked.valide_le = timezone.now()
    locked.valide_par = by
    locked.updated_by = by
    with actor_scope(by):
        locked.save()
    return locked


# --------------------------------------------------------------------------- lignes


def _verifier_processus(processus: Processus, erreurs: dict[str, list[str]]) -> Processus | None:
    fresh = Processus.objects.select_for_update(no_key=True).filter(pk=processus.pk).first()
    if fresh is None:
        erreurs["processus"] = ["Ce processus n'existe plus dans le référentiel."]
    return fresh


def _verifier_objet(objet: ObjetAuditable, erreurs: dict[str, list[str]]) -> ObjetAuditable | None:
    fresh = ObjetAuditable.objects.select_for_update(no_key=True).filter(pk=objet.pk).first()
    if fresh is None:
        erreurs["objet_auditable"] = ["Cet objet auditable n'existe plus dans le référentiel."]
    return fresh


def _verifier_entites(
    entites: Iterable[Direction], erreurs: dict[str, list[str]]
) -> list[Direction]:
    demandees = list(entites)
    actives = {
        d.pk: d
        for d in Direction.objects.select_for_update(no_key=True).filter(
            pk__in=[d.pk for d in demandees]
        )
    }
    manquantes = [d.code for d in demandees if d.pk not in actives]
    if manquantes:
        erreurs["entites"] = [
            f"L'entité {code} n'existe plus dans le référentiel." for code in manquantes
        ]
    return list(actives.values())


def _verifier_ligne(
    ligne: LigneProgramme,
    annee: int,
    *,
    processus: bool,
    objet: bool,
    entites: Iterable[Direction] | None,
) -> list[Direction] | None:
    """Règles communes création/modification ; lève toutes les erreurs par champ d'un coup.

    `processus`/`objet` : vrai si la référence est nouvelle (à revérifier dans le référentiel).
    Retourne les entités actives à poser (None si inchangées).
    """
    erreurs: dict[str, list[str]] = {}
    if processus:
        _verifier_processus(ligne.processus, erreurs)
    if objet and ligne.objet_auditable is not None:
        _verifier_objet(ligne.objet_auditable, erreurs)
    if (
        (processus or objet)
        and ligne.objet_auditable is not None
        and "objet_auditable" not in erreurs
        and ligne.objet_auditable.processus_id != ligne.processus_id
    ):
        erreurs["objet_auditable"] = [
            "L'objet auditable doit appartenir au processus de la mission prévue."
        ]
    posees = _verifier_entites(entites, erreurs) if entites is not None else None
    debut: date = ligne.debut_prevu
    if debut.year != annee:
        erreurs["debut_prevu"] = [f"La mission prévue doit commencer pendant l'année {annee}."]
    if ligne.fin_prevue < debut:
        erreurs["fin_prevue"] = ["La fin prévue doit suivre le début prévu."]
    charge = ligne.charge_prevue_jours
    if charge is not None and charge < 0:
        erreurs["charge_prevue_jours"] = ["La charge prévue ne peut pas être négative."]
    if erreurs:
        raise RegleMetierError("Données invalides.", erreurs)
    return posees


@transaction.atomic
def creer_ligne(
    *,
    programme: ProgrammeAnnuel,
    titre: str,
    type: str,
    processus: Processus,
    debut_prevu: date,
    fin_prevue: date,
    objet_auditable: ObjetAuditable | None = None,
    entites: Iterable[Direction] = (),
    charge_prevue_jours: Decimal | None = None,
    justification: str = "",
    by: User,
) -> LigneProgramme:
    locked = _verrouiller_programme(programme)
    # Numéro jamais réattribué : le maximum inclut les lignes supprimées.
    maximum = LigneProgramme.all_objects.filter(programme=locked).aggregate(m=Max("numero"))["m"]
    nouvelle = LigneProgramme(
        programme=locked,
        numero=(maximum or 0) + 1,
        titre=titre,
        type=type,
        processus=processus,
        objet_auditable=objet_auditable,
        debut_prevu=debut_prevu,
        fin_prevue=fin_prevue,
        charge_prevue_jours=charge_prevue_jours,
        justification=justification,
    )
    posees = _verifier_ligne(
        nouvelle, locked.annee, processus=True, objet=True, entites=list(entites)
    )
    enregistrer(nouvelle, by=by, creation=True)
    if posees:
        nouvelle.entites.set(posees)
    return nouvelle


def _verrouiller_ligne(ligne: LigneProgramme) -> tuple[ProgrammeAnnuel, LigneProgramme]:
    """Verrouille le programme d'abord (même ordre que la création), puis la ligne."""
    programme = _verrouiller_programme(ProgrammeAnnuel(pk=ligne.programme_id))
    return programme, relire(ligne)


@transaction.atomic
def modifier_ligne(ligne: LigneProgramme, *, by: User, **changes: Any) -> LigneProgramme:
    if "programme" in changes or "programme_id" in changes:
        raise refuser(MSG_PROGRAMME_IMMUABLE, programme=MSG_PROGRAMME_IMMUABLE)
    programme, locked = _verrouiller_ligne(ligne)
    entites = changes.get("entites")
    appliquer(locked, changes, _CHAMPS_LIGNE, m2m=frozenset({"entites"}))
    posees = _verifier_ligne(
        locked,
        programme.annee,
        processus="processus" in changes,
        objet="objet_auditable" in changes,
        entites=list(entites) if entites is not None else None,
    )
    enregistrer(locked, by=by)
    if posees is not None:
        locked.entites.set(posees)
    return locked


@transaction.atomic
def supprimer_ligne(ligne: LigneProgramme, *, by: User) -> None:
    _, locked = _verrouiller_ligne(ligne)
    locked.soft_delete(by)


# --------------------------------------------------------------------------- synthèse


@dataclass(frozen=True)
class SyntheseProgramme:
    nb_lignes: int
    charge_totale_jours: Decimal
    par_type: dict[str, int]
    par_trimestre: dict[int, int]


def synthese(programme: ProgrammeAnnuel) -> SyntheseProgramme:
    """Comptes et sommes des lignes actives, en une seule requête agrégée."""
    types = [t.value for t in TypeIntervention]
    agregats: dict[str, Any] = {
        "nb": Count("id"),
        "charge": Sum("charge_prevue_jours"),
    }
    for t in types:
        agregats[f"type_{t}"] = Count("id", filter=Q(type=t))
    for q in range(1, 5):
        mois = range(3 * q - 2, 3 * q + 1)
        agregats[f"trim_{q}"] = Count("id", filter=Q(debut_prevu__month__in=mois))
    res = LigneProgramme.objects.filter(programme=programme).aggregate(**agregats)
    return SyntheseProgramme(
        nb_lignes=res["nb"],
        charge_totale_jours=res["charge"] or Decimal("0"),
        par_type={t: res[f"type_{t}"] for t in types},
        par_trimestre={q: res[f"trim_{q}"] for q in range(1, 5)},
    )
