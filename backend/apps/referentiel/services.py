"""Services métier du référentiel : gardes, numérotation, gel, copie, matrice, comparaison."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, connection, transaction
from django.db.models import Max
from django.http import Http404
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.exceptions import RegleMetierError
from apps.core.services import appliquer, enregistrer, refuser, relire, verrouiller_actif
from apps.users.models import User

from .exceptions import CartographieFigeeError
from .models import (
    CartographieVersion,
    Direction,
    NatureObjet,
    NiveauRisque,
    ObjetAuditable,
    Processus,
    Risque,
    StatutCartographie,
    TypeEntite,
)
from .scoring import niveau_pour_score, priorite_par_defaut

MSG_CODE_IMMUABLE = "Le code ne peut pas être modifié après création."
MSG_CODE_PRIS = "Ce code est déjà utilisé."

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


def _enregistrer(obj: Any, *, by: User, creation: bool = False) -> None:
    """Enregistrement du socle + unicité du code (Direction, Processus)."""
    code_unique = isinstance(obj, Direction | Processus)

    def controle() -> None:
        if type(obj).objects.filter(code=obj.code).exclude(pk=obj.pk).exists():
            raise refuser("Données invalides.", code=MSG_CODE_PRIS)

    try:
        enregistrer(obj, by=by, creation=creation, controle=controle if code_unique else None)
    except IntegrityError as e:
        if code_unique:  # course sur l'unicité du code
            raise refuser("Données invalides.", code=MSG_CODE_PRIS) from e
        raise


def _appliquer(obj: Any, changes: dict[str, Any], autorises: set[str]) -> None:
    appliquer(obj, changes, autorises, m2m=frozenset({"directions"}))


def _verifier_code_immuable(obj: Any, changes: dict[str, Any]) -> None:
    if "code" in changes:
        if changes.pop("code") != obj.code:
            raise refuser(MSG_CODE_IMMUABLE, code=MSG_CODE_IMMUABLE)


MSG_UTILISE_PAR_VALIDEE = (
    "{cible} est utilisé par une cartographie validée (figée) : il ne peut pas être supprimé."
)

# Verrou consultatif unique : `numero` est global, donc toute création de risque est sérialisée.
_VERROU_NUMEROTATION = 0x4F4E4541  # « ONEA »


def _verrouiller_numerotation() -> None:
    with connection.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(%s)", [_VERROU_NUMEROTATION])


def _verrouiller_version(version: CartographieVersion | Any) -> CartographieVersion:
    """Relit la version sous verrou de ligne ; refuse si elle est validée.

    Accepte une version ou son identifiant.
    """
    pk: Any = getattr(version, "pk", version)
    try:
        locked = CartographieVersion.objects.select_for_update().get(pk=pk)
    except ObjectDoesNotExist as e:
        raise Http404("Non trouvé.") from e
    if locked.statut == StatutCartographie.VALIDEE:
        raise CartographieFigeeError(locked.annee)
    return locked


# --------------------------------------------------------------------------- directions


def _valider_parent_direction(type_: str, parent: Direction | None) -> None:
    if type_ == TypeEntite.DEPARTEMENT:
        if parent is None or parent.type != TypeEntite.DIRECTION or parent.deleted_at is not None:
            msg = "Un département doit être rattaché à une direction."
            raise refuser(msg, parent=msg)
    elif parent is not None:
        msg = "Une direction ne peut pas avoir de parent."
        raise refuser(msg, parent=msg)


@transaction.atomic
def creer_direction(
    *, code: str, libelle: str, type: str, parent: Direction | None = None, by: User
) -> Direction:
    if parent is not None:
        parent = verrouiller_actif(parent, "parent")
    _valider_parent_direction(type, parent)
    direction = Direction(code=code, libelle=libelle, type=type, parent=parent)
    _enregistrer(direction, by=by, creation=True)
    return direction


@transaction.atomic
def modifier_direction(direction: Direction, *, by: User, **changes: Any) -> Direction:
    direction = relire(direction)
    _verifier_code_immuable(direction, changes)
    if "type" in changes:
        if changes.pop("type") != direction.type:
            msg = "Le type ne peut pas être modifié après création."
            raise refuser(msg, type=msg)
    if changes.get("parent") is not None:
        changes["parent"] = verrouiller_actif(changes["parent"], "parent")
    _appliquer(direction, changes, _CHAMPS_DIRECTION)
    _valider_parent_direction(direction.type, direction.parent)
    _enregistrer(direction, by=by)
    return direction


@transaction.atomic
def supprimer_direction(direction: Direction, *, by: User) -> None:
    direction = relire(direction)
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
    cibles = _verrouiller_directions(directions)
    processus = Processus(code=code, libelle=libelle, famille=famille, ordre=ordre)
    _enregistrer(processus, by=by, creation=True)
    with actor_scope(by):
        processus.directions.set(cibles)
    return processus


def _verrouiller_directions(directions: Iterable[Direction]) -> list[Direction]:
    # ordre des clés stable : évite les verrous croisés entre deux transactions
    return [verrouiller_actif(d, "directions") for d in sorted(set(directions), key=lambda d: d.pk)]


@transaction.atomic
def modifier_processus(processus: Processus, *, by: User, **changes: Any) -> Processus:
    processus = relire(processus)
    _verifier_code_immuable(processus, changes)
    cibles = _verrouiller_directions(changes["directions"]) if "directions" in changes else None
    _appliquer(processus, changes, _CHAMPS_PROCESSUS)
    _enregistrer(processus, by=by)
    if cibles is not None:
        with actor_scope(by):
            processus.directions.set(cibles)
    return processus


@transaction.atomic
def supprimer_processus(processus: Processus, *, by: User) -> None:
    processus = relire(processus)
    if Risque.objects.filter(
        processus=processus, version__statut=StatutCartographie.VALIDEE
    ).exists():
        raise RegleMetierError(MSG_UTILISE_PAR_VALIDEE.format(cible="Ce processus"))
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
            raise refuser(msg, parent=msg)
    elif parent is not None:
        msg = "Un domaine ne peut pas avoir de parent."
        raise refuser(msg, parent=msg)


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
    processus = verrouiller_actif(processus, "processus")
    if parent is not None:
        parent = verrouiller_actif(parent, "parent")
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
    objet = relire(objet)
    if changes.get("parent") is not None:
        changes["parent"] = verrouiller_actif(changes["parent"], "parent")
    for champ in ("processus", "nature"):
        if champ in changes:
            if changes.pop(champ) != getattr(objet, champ):
                msg = "Le processus et la nature ne peuvent pas être modifiés."
                raise refuser(msg, **{champ: msg})
    _appliquer(objet, changes, _CHAMPS_OBJET)
    _valider_parent_objet(objet.nature, objet.processus, objet.parent)
    _enregistrer(objet, by=by)
    return objet


@transaction.atomic
def supprimer_objet(objet: ObjetAuditable, *, by: User) -> None:
    objet = relire(objet)
    if Risque.objects.filter(
        objet_auditable=objet, version__statut=StatutCartographie.VALIDEE
    ).exists():
        raise RegleMetierError(MSG_UTILISE_PAR_VALIDEE.format(cible="Cet objet auditable"))
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
    if not 2000 <= annee <= 2100:
        msg = "L'année doit être comprise entre 2000 et 2100."
        raise refuser(msg, annee=msg)
    if source is not None:
        # source relue sous verrou : la copie ne part que d'une cartographie validée active
        courante = (
            CartographieVersion.objects.select_for_update(no_key=True).filter(pk=source.pk).first()
        )
        if courante is None or courante.statut != StatutCartographie.VALIDEE:
            msg = "La cartographie source doit être validée."
            raise refuser(msg, source=msg)
    msg = f"Une cartographie existe déjà pour l'année {annee}."
    if CartographieVersion.objects.filter(annee=annee).exists():
        raise refuser(msg, annee=msg)
    version = CartographieVersion(
        annee=annee, libelle=libelle, commentaire=commentaire, source=source
    )
    try:
        with transaction.atomic():
            _enregistrer(version, by=by, creation=True)
    except IntegrityError as e:  # course sur l'unicité de l'année
        raise refuser(msg, annee=msg) from e
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
        raise refuser(msg, objet_auditable=msg)


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
    locked = _verrouiller_version(version)  # sérialise numérotation et validation
    processus = verrouiller_actif(processus, "processus")
    if objet_auditable is not None:
        objet_auditable = verrouiller_actif(objet_auditable, "objet_auditable")
    _verifier_objet(processus, objet_auditable)

    # Un même code désigne le même risque dans toutes les cartographies (D3) : numéros jamais
    # réutilisés sur l'ensemble des cartographies (supprimés inclus), sous verrou consultatif.
    _verrouiller_numerotation()
    tous = Risque.all_objects.all()
    numero = (tous.aggregate(m=Max("numero"))["m"] or 0) + 1
    rang = (tous.filter(processus=processus).aggregate(m=Max("rang"))["m"] or 0) + 1
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
    _verrouiller_version(risque.version_id)
    risque = relire(risque)  # ligne fraîche : une instance périmée n'écrase rien
    if "code" in changes:
        _verifier_code_immuable(risque, changes)
    if "processus" in changes:
        if getattr(changes.pop("processus"), "pk", None) != risque.processus_id:
            msg = "Le processus d'un risque ne peut pas être modifié."
            raise refuser(msg, processus=msg)
    if changes.get("objet_auditable") is not None:
        changes["objet_auditable"] = verrouiller_actif(
            changes["objet_auditable"], "objet_auditable"
        )
    _appliquer(risque, changes, _CHAMPS_RISQUE)
    _verifier_notes(risque.probabilite, risque.impact)
    _verifier_objet(risque.processus, risque.objet_auditable)
    _enregistrer(risque, by=by)
    risque.refresh_from_db()
    return risque


@transaction.atomic
def supprimer_risque(risque: Risque, *, by: User) -> None:
    _verrouiller_version(risque.version_id)
    relire(risque).soft_delete(by)


# --------------------------------------------------------------------------- matrice


@dataclass(frozen=True)
class CelluleMatrice:
    probabilite: int
    impact: int
    score: int
    niveau: str
    nombre: int
    codes: list[str]


def matrice_de(lignes: Iterable[tuple[int, int, str]]) -> list[CelluleMatrice]:
    """Matrice 5x5 (probabilité 5 -> 1, impact 1 -> 5) de lignes (probabilité, impact, code).

    Les codes d'une case gardent l'ordre reçu.
    """
    groupes: dict[tuple[int, int], list[str]] = defaultdict(list)
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


def matrice(version: CartographieVersion) -> list[CelluleMatrice]:
    """Matrice 5x5 d'une cartographie, en une seule requête."""
    return matrice_de(
        Risque.objects.filter(version=version)
        .order_by("numero")
        .values_list("probabilite", "impact", "code")
    )


@dataclass(frozen=True)
class ResumeMatrice:
    version: CartographieVersion
    total: int
    par_niveau: dict[str, int]
    cellules: list[CelluleMatrice]


def resume_matrice(version: CartographieVersion) -> ResumeMatrice:
    """Matrice 5x5 avec total et répartition par niveau (FAIBLE / MOYEN / ELEVE)."""
    cellules = matrice(version)
    par_niveau = {n.value: 0 for n in NiveauRisque}
    for c in cellules:
        par_niveau[c.niveau] += c.nombre
    return ResumeMatrice(
        version=version,
        total=sum(par_niveau.values()),
        par_niveau=par_niveau,
        cellules=cellules,
    )


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
