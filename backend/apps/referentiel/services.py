"""Services métier du référentiel : gardes, numérotation, gel, copie, matrice, comparaison."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.users.models import User

from .exceptions import CartographieFigeeError
from .models import (
    CartographieVersion,
    Direction,
    NatureObjet,
    ObjetAuditable,
    Processus,
    Risque,
    StatutCartographie,
    TypeEntite,
)
from .scoring import niveau_pour_score, priorite_par_defaut

MSG_CODE_IMMUABLE = "Le code ne peut pas être modifié après création."

_CHAMPS_DIRECTION = {"libelle", "parent"}
_CHAMPS_PROCESSUS = {"libelle", "famille", "ordre", "directions"}
_CHAMPS_OBJET = {"libelle", "description", "ordre", "parent"}
_CHAMPS_RISQUE = {
    "libelle",
    "description",
    "probabilite",
    "impact",
    "objet_auditable",
    "priorite",
    "vulnerabilite",
    "reponse",
    "objectif_controle",
    "dispositif_controle",
}
_DETAILS_RISQUE = {
    "description",
    "vulnerabilite",
    "reponse",
    "objectif_controle",
    "dispositif_controle",
}


# --------------------------------------------------------------------------- helpers


def _refuser(message: str, **errors: str) -> RegleMetierError:
    return RegleMetierError(message, {champ: [msg] for champ, msg in errors.items()})


def _enregistrer(obj: Any, *, by: User, creation: bool = False) -> None:
    """Valide (validateurs, unicités, contraintes) puis sauvegarde en traçant l'acteur."""
    if creation:
        obj.created_by = by
    obj.updated_by = by
    try:
        obj.full_clean()
    except ValidationError as e:
        erreurs = dict(e.message_dict)
        if any("_code_unique" in m for m in erreurs.get("__all__", [])):
            erreurs = {k: v for k, v in erreurs.items() if k != "__all__"}
            erreurs["code"] = ["Ce code est déjà utilisé."]
        raise RegleMetierError("Données invalides.", erreurs) from e
    with actor_scope(by):
        obj.save()


def _appliquer(obj: Any, changes: dict[str, Any], autorises: set[str]) -> None:
    inconnus = set(changes) - autorises
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    for champ, valeur in changes.items():
        if champ != "directions":
            setattr(obj, champ, valeur)


def _verifier_code_immuable(obj: Any, changes: dict[str, Any]) -> None:
    if "code" in changes:
        if changes.pop("code") != obj.code:
            raise _refuser(MSG_CODE_IMMUABLE, code=MSG_CODE_IMMUABLE)


def _verrouiller_version(version: CartographieVersion) -> CartographieVersion:
    """Relit la version sous verrou de ligne ; refuse si elle est validée."""
    locked = CartographieVersion.objects.select_for_update().get(pk=version.pk)
    if locked.statut == StatutCartographie.VALIDEE:
        raise CartographieFigeeError(locked.annee)
    return locked


# --------------------------------------------------------------------------- directions


def _valider_parent_direction(type_: str, parent: Direction | None) -> None:
    if type_ == TypeEntite.DEPARTEMENT:
        if parent is None or parent.type != TypeEntite.DIRECTION or parent.deleted_at is not None:
            msg = "Un département doit être rattaché à une direction."
            raise _refuser(msg, parent=msg)
    elif parent is not None:
        msg = "Une direction ne peut pas avoir de parent."
        raise _refuser(msg, parent=msg)


@transaction.atomic
def creer_direction(
    *, code: str, libelle: str, type: str, parent: Direction | None = None, by: User
) -> Direction:
    _valider_parent_direction(type, parent)
    direction = Direction(code=code, libelle=libelle, type=type, parent=parent)
    _enregistrer(direction, by=by, creation=True)
    return direction


@transaction.atomic
def modifier_direction(direction: Direction, *, by: User, **changes: Any) -> Direction:
    _verifier_code_immuable(direction, changes)
    if "type" in changes:
        if changes.pop("type") != direction.type:
            msg = "Le type ne peut pas être modifié après création."
            raise _refuser(msg, type=msg)
    _appliquer(direction, changes, _CHAMPS_DIRECTION)
    _valider_parent_direction(direction.type, direction.parent)
    _enregistrer(direction, by=by)
    return direction


@transaction.atomic
def supprimer_direction(direction: Direction, *, by: User) -> None:
    if (
        Processus.objects.filter(directions=direction).exists()
        or Direction.objects.filter(parent=direction).exists()
    ):
        raise RegleMetierError(
            "Cette direction est rattachée à un processus ou porte des départements actifs."
        )
    direction.soft_delete(by)


# --------------------------------------------------------------------------- processus


@transaction.atomic
def creer_processus(
    *,
    code: str,
    libelle: str,
    famille: str,
    ordre: int = 0,
    directions: Iterable[Direction] = (),
    by: User,
) -> Processus:
    processus = Processus(code=code, libelle=libelle, famille=famille, ordre=ordre)
    _enregistrer(processus, by=by, creation=True)
    with actor_scope(by):
        processus.directions.set(list(directions))
    return processus


@transaction.atomic
def modifier_processus(processus: Processus, *, by: User, **changes: Any) -> Processus:
    _verifier_code_immuable(processus, changes)
    _appliquer(processus, changes, _CHAMPS_PROCESSUS)
    _enregistrer(processus, by=by)
    if "directions" in changes:
        with actor_scope(by):
            processus.directions.set(list(changes["directions"]))
    return processus


@transaction.atomic
def supprimer_processus(processus: Processus, *, by: User) -> None:
    if (
        Risque.objects.filter(processus=processus).exists()
        or ObjetAuditable.objects.filter(processus=processus).exists()
    ):
        raise RegleMetierError(
            "Ce processus porte des risques ou des objets auditables actifs : "
            "supprimez-les d'abord."
        )
    processus.soft_delete(by)


# --------------------------------------------------------------------------- objets auditables


def _valider_parent_objet(nature: str, processus: Processus, parent: ObjetAuditable | None) -> None:
    if nature == NatureObjet.OPERATION:
        if (
            parent is None
            or parent.deleted_at is not None
            or parent.nature != NatureObjet.DOMAINE
            or parent.processus_id != processus.pk
        ):
            msg = "Une opération doit être rattachée à un domaine du même processus."
            raise _refuser(msg, parent=msg)
    elif parent is not None:
        msg = "Un domaine ne peut pas avoir de parent."
        raise _refuser(msg, parent=msg)


@transaction.atomic
def creer_objet(
    *,
    processus: Processus,
    nature: str,
    libelle: str,
    parent: ObjetAuditable | None = None,
    description: str = "",
    ordre: int = 0,
    by: User,
) -> ObjetAuditable:
    _valider_parent_objet(nature, processus, parent)
    objet = ObjetAuditable(
        processus=processus,
        nature=nature,
        libelle=libelle,
        parent=parent,
        description=description,
        ordre=ordre,
    )
    _enregistrer(objet, by=by, creation=True)
    return objet


@transaction.atomic
def modifier_objet(objet: ObjetAuditable, *, by: User, **changes: Any) -> ObjetAuditable:
    for champ in ("processus", "nature"):
        if champ in changes:
            if changes.pop(champ) != getattr(objet, champ):
                msg = "Le processus et la nature ne peuvent pas être modifiés."
                raise _refuser(msg, **{champ: msg})
    _appliquer(objet, changes, _CHAMPS_OBJET)
    _valider_parent_objet(objet.nature, objet.processus, objet.parent)
    _enregistrer(objet, by=by)
    return objet


@transaction.atomic
def supprimer_objet(objet: ObjetAuditable, *, by: User) -> None:
    if (
        ObjetAuditable.objects.filter(parent=objet).exists()
        or Risque.objects.filter(objet_auditable=objet).exists()
    ):
        raise RegleMetierError(
            "Cet objet auditable porte des opérations ou des risques actifs : "
            "supprimez-les d'abord."
        )
    objet.soft_delete(by)


# --------------------------------------------------------------------------- versions


def version_courante() -> CartographieVersion | None:
    """Dernière cartographie validée."""
    return (
        CartographieVersion.objects.filter(statut=StatutCartographie.VALIDEE)
        .order_by("-annee")
        .first()
    )


@transaction.atomic
def creer_version(
    *,
    annee: int,
    libelle: str,
    commentaire: str = "",
    source: CartographieVersion | None = None,
    by: User,
) -> CartographieVersion:
    msg = f"Une cartographie existe déjà pour l'année {annee}."
    if CartographieVersion.objects.filter(annee=annee).exists():
        raise _refuser(msg, annee=msg)
    version = CartographieVersion(
        annee=annee, libelle=libelle, commentaire=commentaire, source=source
    )
    try:
        with transaction.atomic():
            _enregistrer(version, by=by, creation=True)
    except IntegrityError as e:  # course sur l'unicité de l'année
        raise _refuser(msg, annee=msg) from e
    if source is not None:
        _copier_risques(source, version, by=by)
    return version


def _copier_risques(source: CartographieVersion, cible: CartographieVersion, *, by: User) -> None:
    risques = Risque.objects.filter(version=source).select_related("objet_auditable")
    for r in risques.order_by("numero"):
        objet = r.objet_auditable
        copie = Risque(
            version=cible,
            processus_id=r.processus_id,
            objet_auditable=objet if objet is not None and objet.deleted_at is None else None,
            numero=r.numero,
            rang=r.rang,
            code=r.code,
            libelle=r.libelle,
            description=r.description,
            probabilite=r.probabilite,
            impact=r.impact,
            vulnerabilite=r.vulnerabilite,
            reponse=r.reponse,
            priorite=r.priorite,
            objectif_controle=r.objectif_controle,
            dispositif_controle=r.dispositif_controle,
            created_by=by,
            updated_by=by,
        )
        with actor_scope(by):
            copie.save()


@transaction.atomic
def modifier_version(
    version: CartographieVersion, *, by: User, **changes: Any
) -> CartographieVersion:
    inconnus = set(changes) - {"libelle", "commentaire"}
    if inconnus:
        raise ValueError(f"Champs non modifiables : {sorted(inconnus)}")
    locked = _verrouiller_version(version)
    for champ, valeur in changes.items():
        setattr(locked, champ, valeur)
    _enregistrer(locked, by=by)
    return locked


@transaction.atomic
def supprimer_version(version: CartographieVersion, *, by: User) -> None:
    locked = _verrouiller_version(version)
    for risque in Risque.objects.filter(version=locked):
        risque.soft_delete(by)
    locked.soft_delete(by)


@transaction.atomic
def valider_version(version: CartographieVersion, *, by: User) -> CartographieVersion:
    locked = _verrouiller_version(version)
    if not Risque.objects.filter(version=locked).exists():
        raise RegleMetierError("Une cartographie sans risque ne peut pas être validée.")
    locked.valider()
    locked.validee_le = timezone.now()
    locked.validee_par = by
    locked.updated_by = by
    with actor_scope(by):
        locked.save()
    return locked


# --------------------------------------------------------------------------- risques


def _verifier_notes(probabilite: int, impact: int) -> None:
    erreurs = {}
    if not isinstance(probabilite, int) or not 1 <= probabilite <= 5:
        erreurs["probabilite"] = ["La probabilité doit être comprise entre 1 et 5."]
    if not isinstance(impact, int) or not 1 <= impact <= 5:
        erreurs["impact"] = ["L'impact doit être compris entre 1 et 5."]
    if erreurs:
        raise RegleMetierError("Données invalides.", erreurs)


def _verifier_objet(processus: Processus, objet: ObjetAuditable | None) -> None:
    if objet is not None and objet.processus_id != processus.pk:
        msg = "L'objet auditable doit appartenir au processus du risque."
        raise _refuser(msg, objet_auditable=msg)


@transaction.atomic
def creer_risque(
    *,
    version: CartographieVersion,
    processus: Processus,
    libelle: str,
    probabilite: int,
    impact: int,
    objet_auditable: ObjetAuditable | None = None,
    priorite: int | None = None,
    by: User,
    **details: Any,
) -> Risque:
    inconnus = set(details) - _DETAILS_RISQUE
    if inconnus:
        raise ValueError(f"Champs inconnus : {sorted(inconnus)}")
    _verifier_notes(probabilite, impact)
    _verifier_objet(processus, objet_auditable)
    locked = _verrouiller_version(version)  # sérialise numérotation et validation

    numero = (Risque.all_objects.filter(version=locked).aggregate(m=Max("numero"))["m"] or 0) + 1
    rang = (
        Risque.all_objects.filter(version=locked, processus=processus).aggregate(m=Max("rang"))["m"]
        or 0
    ) + 1
    if priorite is None:
        priorite = priorite_par_defaut(niveau_pour_score(probabilite * impact))
    risque = Risque(
        version=locked,
        processus=processus,
        objet_auditable=objet_auditable,
        numero=numero,
        rang=rang,
        code=f"{numero}-{processus.code}-R{rang}",
        libelle=libelle,
        probabilite=probabilite,
        impact=impact,
        priorite=priorite,
        **details,
    )
    _enregistrer(risque, by=by, creation=True)
    risque.refresh_from_db()
    return risque


@transaction.atomic
def modifier_risque(risque: Risque, *, by: User, **changes: Any) -> Risque:
    if "code" in changes:
        _verifier_code_immuable(risque, changes)
    if "processus" in changes:
        if changes.pop("processus") != risque.processus:
            msg = "Le processus d'un risque ne peut pas être modifié."
            raise _refuser(msg, processus=msg)
    _verrouiller_version(risque.version)
    _appliquer(risque, changes, _CHAMPS_RISQUE)
    _verifier_notes(risque.probabilite, risque.impact)
    _verifier_objet(risque.processus, risque.objet_auditable)
    _enregistrer(risque, by=by)
    risque.refresh_from_db()
    return risque


@transaction.atomic
def supprimer_risque(risque: Risque, *, by: User) -> None:
    _verrouiller_version(risque.version)
    risque.soft_delete(by)


# --------------------------------------------------------------------------- matrice


@dataclass(frozen=True)
class CelluleMatrice:
    probabilite: int
    impact: int
    score: int
    niveau: str
    nombre: int
    codes: list[str]


def matrice(version: CartographieVersion) -> list[CelluleMatrice]:
    """Matrice 5x5 (probabilité 5 -> 1, impact 1 -> 5) en une seule requête."""
    groupes: dict[tuple[int, int], list[str]] = defaultdict(list)
    lignes = (
        Risque.objects.filter(version=version)
        .order_by("numero")
        .values_list("probabilite", "impact", "code")
    )
    for p, i, code in lignes:
        groupes[(p, i)].append(code)
    return [
        CelluleMatrice(
            probabilite=p,
            impact=i,
            score=p * i,
            niveau=niveau_pour_score(p * i).value,
            nombre=len(groupes[(p, i)]),
            codes=list(groupes[(p, i)]),
        )
        for p in range(5, 0, -1)
        for i in range(1, 6)
    ]


# --------------------------------------------------------------------------- comparaison


@dataclass
class RisqueModifie:
    code: str
    changements: dict[str, tuple[str | None, str | None]]


@dataclass
class Comparaison:
    ajoutes: list[Risque]
    retires: list[Risque]
    modifies: list[RisqueModifie]


_CHAMPS_COMPARES = (
    "libelle",
    "description",
    "probabilite",
    "impact",
    "score",
    "niveau",
    "vulnerabilite",
    "reponse",
    "priorite",
    "objectif_controle",
    "dispositif_controle",
)


def _valeur(risque: Risque, champ: str) -> str | None:
    if champ == "objet_auditable":
        return risque.objet_auditable.libelle if risque.objet_auditable else None
    valeur = getattr(risque, champ)
    return None if valeur is None else str(valeur)


def comparer_versions(reference: CartographieVersion, cible: CartographieVersion) -> Comparaison:
    def charger(v: CartographieVersion) -> dict[str, Risque]:
        qs = Risque.objects.filter(version=v).select_related("objet_auditable")
        return {r.code: r for r in qs.order_by("numero")}

    ref, cib = charger(reference), charger(cible)
    modifies: list[RisqueModifie] = []
    for code, avant in ref.items():
        apres = cib.get(code)
        if apres is None:
            continue
        changements = {
            champ: (_valeur(avant, champ), _valeur(apres, champ))
            for champ in (*_CHAMPS_COMPARES, "objet_auditable")
            if _valeur(avant, champ) != _valeur(apres, champ)
        }
        if changements:
            modifies.append(RisqueModifie(code=code, changements=changements))
    return Comparaison(
        ajoutes=[r for c, r in cib.items() if c not in ref],
        retires=[r for c, r in ref.items() if c not in cib],
        modifies=modifies,
    )
