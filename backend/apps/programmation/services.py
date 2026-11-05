"""Services métier du programme annuel : création, cohérence référentielle, numérotation,
validation et gel. Toute écriture commence par le verrouillage du programme."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q, Sum
from django.http import Http404
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire
from apps.gouvernance import regles_gouvernance
from apps.notifications.models import TypeNotification
from apps.notifications.services import notifier
from apps.referentiel.models import Direction, ObjetAuditable, Processus
from apps.users.models import Role, User

from .exceptions import ProgrammeFigeError
from .models import (
    ApprobationProgramme,
    LigneProgramme,
    NiveauApprobation,
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


def _verrouiller_programme(programme: ProgrammeAnnuel) -> ProgrammeAnnuel:
    """Relit le programme sous verrou de ligne ; refuse s'il est validé."""
    locked = ProgrammeAnnuel.objects.select_for_update().filter(pk=programme.pk).first()
    if locked is None:
        raise Http404("Non trouvé.")
    if locked.statut == StatutProgramme.VALIDE:
        raise ProgrammeFigeError(locked.annee)
    return locked


def _msg_annee_prise(annee: int) -> str:
    return f"Un programme annuel existe déjà pour l'année {annee}."


def _refuser_champs_non_modifiables(changes: dict[str, Any], autorises: set[str]) -> None:
    """Refus explicite (422) plutôt qu'une ValueError (500) pour un champ non modifiable."""
    erreurs = {
        champ: ["Ce champ ne peut pas être modifié."] for champ in changes if champ not in autorises
    }
    if erreurs:
        raise RegleMetierError("Données invalides.", erreurs)


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
        if "programme_annee_unique_actif" not in str(e):
            raise
        msg = _msg_annee_prise(annee)
        raise refuser(msg, annee=msg) from e
    return programme


@transaction.atomic
def modifier_programme(programme: ProgrammeAnnuel, *, by: User, **changes: Any) -> ProgrammeAnnuel:
    locked = _verrouiller_programme(programme)
    if "annee" in changes:
        if changes.pop("annee") != locked.annee:
            raise refuser(MSG_ANNEE_IMMUABLE, annee=MSG_ANNEE_IMMUABLE)
    _refuser_champs_non_modifiables(changes, _CHAMPS_PROGRAMME)
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
        msg = "Un programme sans mission prévue ne peut pas être validé."
        raise RegleMetierError(msg, {"non_field_errors": [msg]})
    locked.valider()
    locked.valide_le = timezone.now()
    locked.valide_par = by
    locked.updated_by = by
    with actor_scope(by):
        locked.save()
    _notifier_approbation_attendue(locked)
    return locked


# --------------------------------------------------------------------------- approbation

MSG_APPROBATION_DROIT = (
    "Seul le DG enregistre l'approbation du programme (la sienne et celle du Conseil)."
)
MSG_APPROBATION_BROUILLON = "Le programme doit d'abord être validé par le RAI."
MSG_APPROBATION_AUCUNE = (
    "Les règles de gouvernance ne prévoient pas d'approbation du programme annuel."
)
MSG_APPROBATION_CONSEIL_NON_PREVUE = (
    "Les règles de gouvernance ne prévoient pas l'approbation du Conseil."
)
MSG_APPROBATION_DG_DABORD = "Enregistrez d'abord l'approbation de la Direction générale."
MSG_APPROBATION_DEJA = "Cette approbation est déjà enregistrée."
MSG_APPROBATION_REFERENCE = "Indiquez la référence de la délibération du Conseil."
MSG_APPROBATION_DATE = "La date de la décision ne peut pas être dans le futur."


def niveaux_requis(approbateur: str | None = None) -> list[str]:
    """Niveaux d'approbation exigés par la règle de gouvernance (dans l'ordre)."""
    if approbateur is None:
        approbateur = regles_gouvernance.program_approval()["approver"]
    niveaux: dict[str, list[str]] = {
        "NONE": [],
        "DG": [NiveauApprobation.DG],
        "DG_AND_BOARD": [NiveauApprobation.DG, NiveauApprobation.BOARD],
    }
    return niveaux[approbateur]


def etat_approbation(programme: ProgrammeAnnuel) -> dict[str, Any]:
    """État d'approbation du programme selon la règle courante (lue au moment de l'appel)."""
    approbateur = regles_gouvernance.program_approval()["approver"]
    requis = niveaux_requis(approbateur)
    # `approbations` préchargées par la vue de liste (requêtes bornées), sinon lues ici.
    approbations = sorted(programme.approbations.all(), key=lambda a: a.approuve_le)
    obtenus = {a.niveau for a in approbations}
    manquantes = [n for n in requis if n not in obtenus]
    valide = programme.statut == StatutProgramme.VALIDE
    return {
        "approbateur": approbateur,
        "requise": bool(requis),
        "approuve": valide and not manquantes,
        "manquantes": [str(n) for n in manquantes] if valide else [str(n) for n in requis],
        "approbations": [
            {
                "niveau": a.niveau,
                "niveau_libelle": a.get_niveau_display(),
                "approuve_par": a.approuve_par,
                "approuve_le": a.approuve_le,
                "date_decision": a.date_decision,
                "reference": a.reference,
                "commentaire": a.commentaire,
            }
            for a in approbations
        ],
    }


def programme_approuve_pour(annee: int | None) -> bool:
    """Programme de l'année validé et approuvé selon la règle (lancement des missions)."""
    if annee is None:
        return False
    programme = ProgrammeAnnuel.objects.filter(annee=annee).first()
    return programme is not None and bool(etat_approbation(programme)["approuve"])


@transaction.atomic
def approuver_programme(
    programme: ProgrammeAnnuel,
    *,
    niveau: str,
    by: User,
    date_decision: date | None = None,
    reference: str = "",
    commentaire: str = "",
) -> ApprobationProgramme:
    if by.role != Role.DG or not by.is_active:
        raise PermissionDenied(MSG_APPROBATION_DROIT)
    locked = ProgrammeAnnuel.objects.select_for_update().filter(pk=programme.pk).first()
    if locked is None:
        raise Http404("Non trouvé.")
    if locked.statut != StatutProgramme.VALIDE:
        raise refuser(MSG_APPROBATION_BROUILLON, statut=MSG_APPROBATION_BROUILLON)
    requis = niveaux_requis()
    if not requis:
        raise refuser(MSG_APPROBATION_AUCUNE, niveau=MSG_APPROBATION_AUCUNE)
    if niveau not in requis:
        raise refuser(MSG_APPROBATION_CONSEIL_NON_PREVUE, niveau=MSG_APPROBATION_CONSEIL_NON_PREVUE)
    obtenus = set(
        ApprobationProgramme.objects.filter(programme=locked).values_list("niveau", flat=True)
    )
    if niveau in obtenus:
        raise refuser(MSG_APPROBATION_DEJA, niveau=MSG_APPROBATION_DEJA)
    if niveau == NiveauApprobation.BOARD and NiveauApprobation.DG not in obtenus:
        raise refuser(MSG_APPROBATION_DG_DABORD, niveau=MSG_APPROBATION_DG_DABORD)
    reference = reference.strip()
    if niveau == NiveauApprobation.BOARD and not reference:
        raise refuser(MSG_APPROBATION_REFERENCE, reference=MSG_APPROBATION_REFERENCE)
    aujourd_hui = timezone.localdate()
    date_decision = date_decision or aujourd_hui
    if date_decision > aujourd_hui:
        raise refuser(MSG_APPROBATION_DATE, date_decision=MSG_APPROBATION_DATE)
    approbation = ApprobationProgramme(
        programme=locked,
        niveau=niveau,
        approuve_par=by,
        approuve_le=timezone.now(),
        date_decision=date_decision,
        reference=reference,
        commentaire=commentaire.strip(),
    )
    enregistrer(approbation, by=by, creation=True)
    return approbation


def _notifier_approbation_attendue(programme: ProgrammeAnnuel) -> None:
    if not niveaux_requis():
        return
    notifier(
        User.objects.filter(role=Role.DG, is_active=True),
        type=TypeNotification.PROGRAMME_A_APPROUVER,
        titre=f"Programme annuel {programme.annee} à approuver",
        message=(
            f"Le RAI a validé le programme annuel {programme.annee}. Les règles de gouvernance "
            "prévoient son approbation avant le lancement des missions."
        ),
        lien=f"/programme-annuel/{programme.pk}",
        objet=programme,
        cle=f"programme-a-approuver:{programme.pk}",
    )


# --------------------------------------------------------------------------- lignes


# Les verrous du référentiel sont posés ici plutôt que par `core.services.verrouiller_actif` :
# celui-ci émet un message générique, alors que les messages exigés sont propres à chaque champ.


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
        for d in Direction.objects.select_for_update(no_key=True)
        .filter(pk__in=[d.pk for d in demandees])
        .order_by("pk")  # ordre de verrou déterministe
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
        with actor_scope(by):
            nouvelle.entites.set(posees)
    return nouvelle


def _verrouiller_ligne(ligne: LigneProgramme) -> tuple[ProgrammeAnnuel, LigneProgramme]:
    """Verrouille le programme d'abord (même ordre que la création), puis la ligne."""
    programme = _verrouiller_programme(ProgrammeAnnuel(pk=ligne.programme_id))
    return programme, relire(ligne)


@transaction.atomic
def modifier_ligne(ligne: LigneProgramme, *, by: User, **changes: Any) -> LigneProgramme:
    """Modifie une mission prévue.

    Décision D6 : une référence (processus, objet auditable, entités) n'est revérifiée dans le
    référentiel que si sa clé figure dans `changes`. Une ligne qui cite un élément supprimé
    depuis reste modifiable, mais renvoyer cette référence (même inchangée) est refusé : le
    client ne doit envoyer que les champs réellement modifiés.
    """
    if "programme" in changes or "programme_id" in changes:
        raise refuser(MSG_PROGRAMME_IMMUABLE, programme=MSG_PROGRAMME_IMMUABLE)
    programme, locked = _verrouiller_ligne(ligne)
    _refuser_champs_non_modifiables(changes, _CHAMPS_LIGNE)
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
        with actor_scope(by):
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
