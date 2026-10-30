"""Sources indexées (R14) : document de l'index, second filtre en base et dépendants.

Chaque type indexé déclare :
- `document(objet)` : le document de l'index, ou `None` quand l'objet ne doit pas (ou plus) y être
  (supprimé, mission en brouillon, document sans version prête) ;
- `visibles(user, ids)` : le sous-ensemble de `ids` que `user` a le droit de lire, calculé en base
  avec les mêmes requêtes que l'API. C'est le second filtre : il est seul à faire foi ;
- `dependants(objet)` : les objets dont le document change quand `objet` change.

Aucun contenu de fichier ni contexte JSON de document n'est indexé (R14).
"""

import builtins
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.conf import settings
from django.db.models import Model, QuerySet
from django.http import Http404

from apps.constats.models import Constat, Recommandation, StatutConstat
from apps.constats.permissions import REPONDABLES, constats_lisibles
from apps.core.exceptions import RegleMetierError
from apps.documents.models import Document, DocumentVersion, StatutGeneration
from apps.documents.moteur.registre import type_document
from apps.documents.permissions import fournisseur_de, objet_de
from apps.missions.acces import missions_visibles
from apps.missions.models import Mission, StatutMission
from apps.suivi.droits import missions_suivi_visibles, suivis_visibles
from apps.suivi.models import SuiviAction
from apps.suivi.sources import CODE_DOCUMENT_RAPPORT
from apps.users.models import Role, User

logger = logging.getLogger(__name__)

AUDIENCE_EQUIPE = "EQUIPE"
AUDIENCE_AUDITE = "AUDITE"
AUDIENCE_DG = "DG"
LONGUEUR_FAIT_CONSTATE = 1000

TYPE_MISSION = "MISSION"
TYPE_CONSTAT = "CONSTAT"
TYPE_RECOMMANDATION = "RECOMMANDATION"
TYPE_ACTION = "ACTION"
TYPE_DOCUMENT = "DOCUMENT"


@dataclass(frozen=True)
class Source:
    type: str
    modele: builtins.type[Model]
    document: Callable[[Any], dict[str, Any] | None]
    visibles: Callable[[User, list[UUID]], set[UUID]]
    dependants: Callable[[Any], list[tuple[str, UUID]]]


# ------------------------------------------------------------------------------ communs


def _document(
    type_: str,
    objet: Any,
    *,
    mission: Mission,
    reference: str,
    titre: str,
    sous_titre: str,
    texte: str,
    audience: list[str],
    date: Any,
) -> dict[str, Any]:
    return {
        "id": f"{type_}-{objet.pk}",
        "type": type_,
        "objet_id": str(objet.pk),
        "mission_id": str(mission.pk),
        "mission_reference": mission.reference,
        "reference": reference,
        "titre": titre,
        "sous_titre": sous_titre,
        "texte": texte,
        "audience": audience,
        "annee": mission.annee,
        "date": date.date().isoformat() if hasattr(date, "date") else str(date),
    }


def _mission_indexable(mission: Mission) -> bool:
    return mission.deleted_at is None and mission.statut != StatutMission.BROUILLON


def _perimetre_missions(user: User) -> QuerySet[Mission]:
    """Missions dont `user` peut lire des objets : DG sur les missions diffusées, les autres sur
    leurs missions visibles ; ADMIN et rôles inconnus : aucune."""
    if user.role == Role.DG:
        return missions_suivi_visibles(user)
    if user.role in (Role.RAI, Role.AUDITEUR, Role.AUDITE):
        return missions_visibles(user)
    return Mission.objects.none()


def _ids(qs: QuerySet[Any]) -> set[UUID]:
    return set(qs.values_list("pk", flat=True))


# ------------------------------------------------------------------------------- MISSION


def _document_mission(mission: Mission) -> dict[str, Any] | None:
    if not _mission_indexable(mission):
        return None
    entites = [e.libelle for e in mission.entites.order_by("code")]
    processus = [p.code for p in mission.processus.order_by("code")]
    return _document(
        TYPE_MISSION,
        mission,
        mission=mission,
        reference=mission.reference,
        titre=mission.titre,
        sous_titre=", ".join(entites),
        texte=" ".join([*entites, *processus]),
        audience=[AUDIENCE_EQUIPE, AUDIENCE_AUDITE, AUDIENCE_DG],
        date=mission.updated_at,
    )


def _visibles_missions(user: User, ids: list[UUID]) -> set[UUID]:
    return _ids(_perimetre_missions(user).filter(pk__in=ids))


# ------------------------------------------------------------------ CONSTAT, RECOMMANDATION


def _audience_constat(constat: Constat) -> list[str]:
    # Comme l'API (`constats_lisibles`) : l'audité et le DG ne lisent que les constats soumis ou
    # validés ; un constat renvoyé repasse donc en audience d'équipe.
    if constat.statut in (StatutConstat.SOUMIS, StatutConstat.VALIDE):
        return [AUDIENCE_EQUIPE, AUDIENCE_AUDITE, AUDIENCE_DG]
    return [AUDIENCE_EQUIPE]


def _constat_indexable(constat: Constat) -> bool:
    return constat.deleted_at is None and _mission_indexable(constat.mission)


def _document_constat(constat: Constat) -> dict[str, Any] | None:
    if not _constat_indexable(constat):
        return None
    return _document(
        TYPE_CONSTAT,
        constat,
        mission=constat.mission,
        reference=constat.reference,
        titre=constat.titre or constat.reference,
        sous_titre=constat.entite.libelle if constat.entite_id else "",
        texte=constat.fait_constate[:LONGUEUR_FAIT_CONSTATE],
        audience=_audience_constat(constat),
        date=constat.updated_at,
    )


def _document_recommandation(reco: Recommandation) -> dict[str, Any] | None:
    constat = reco.constat
    if reco.deleted_at is not None or not _constat_indexable(constat):
        return None
    return _document(
        TYPE_RECOMMANDATION,
        reco,
        mission=constat.mission,
        reference=f"{constat.reference}-{reco.ordre}",
        titre=reco.libelle[:200],
        sous_titre=f"Constat {constat.reference}",
        texte=reco.libelle,
        audience=_audience_constat(constat),
        date=reco.updated_at,
    )


def _constats_lus(user: User) -> QuerySet[Constat]:
    if user.role == Role.DG:
        return Constat.objects.filter(
            mission__in=missions_suivi_visibles(user), statut__in=REPONDABLES
        )
    if user.role in (Role.RAI, Role.AUDITEUR, Role.AUDITE):
        return constats_lisibles(user)
    return Constat.objects.none()


def _visibles_constats(user: User, ids: list[UUID]) -> set[UUID]:
    return _ids(_constats_lus(user).filter(pk__in=ids))


def _visibles_recommandations(user: User, ids: list[UUID]) -> set[UUID]:
    return _ids(Recommandation.objects.filter(pk__in=ids, constat__in=_constats_lus(user)))


def _dependants_constat(constat: Constat) -> list[tuple[str, UUID]]:
    return [
        (TYPE_RECOMMANDATION, pk)
        for pk in Recommandation.objects.filter(constat=constat).values_list("pk", flat=True)
    ]


# ------------------------------------------------------------------------------- ACTION


def _document_action(suivi: SuiviAction) -> dict[str, Any] | None:
    mission = suivi.mission
    if suivi.deleted_at is not None or not _mission_indexable(mission):
        return None
    action = suivi.action
    reco = suivi.recommandation
    responsable = suivi.responsable
    return _document(
        TYPE_ACTION,
        suivi,
        mission=mission,
        reference=f"{reco.constat.reference}-{reco.ordre}",
        titre=action.libelle[:200],
        sous_titre=responsable.nom_complet if responsable is not None else "",
        texte=action.indicateur,
        audience=[AUDIENCE_EQUIPE, AUDIENCE_AUDITE, AUDIENCE_DG],
        date=suivi.updated_at,
    )


def _visibles_actions(user: User, ids: list[UUID]) -> set[UUID]:
    return _ids(suivis_visibles(user).filter(pk__in=ids))


# ----------------------------------------------------------------------------- DOCUMENT


def _rapports_diffuses(ids: list[UUID]) -> set[UUID]:
    """Adaptateur lot 7 : rapports (parmi `ids`) à l'état « diffusé » (y compris remplacé)."""
    from apps.communication.documents import STATUTS_DIFFUSES
    from apps.communication.models import Rapport

    return _ids(Rapport.objects.filter(pk__in=ids, statut__in=STATUTS_DIFFUSES))


def _version_prete(document: Document) -> bool:
    return DocumentVersion.objects.filter(document=document, statut=StatutGeneration.PRETE).exists()


def _document_document(document: Document) -> dict[str, Any] | None:
    mission = document.mission
    if document.deleted_at is not None or not _mission_indexable(mission):
        return None
    if not _version_prete(document):
        return None
    try:
        libelle = type_document(document.type_document).libelle
    except RegleMetierError:
        return None
    audience = [AUDIENCE_EQUIPE]
    if document.type_document in settings.RECHERCHE_TYPES_DOCUMENTS_AUDITE:
        if document.type_document != CODE_DOCUMENT_RAPPORT:
            audience.append(AUDIENCE_AUDITE)
        elif _rapports_diffuses([document.object_id]):
            audience += [AUDIENCE_AUDITE, AUDIENCE_DG]
    return _document(
        TYPE_DOCUMENT,
        document,
        mission=mission,
        reference=document.numero,
        titre=libelle,
        sous_titre=mission.reference,
        texte=f"{document.numero} {libelle} {mission.reference}",
        audience=audience,
        date=document.created_at,
    )


def _visibles_documents(user: User, ids: list[UUID]) -> set[UUID]:
    perimetre = _perimetre_missions(user)
    documents = list(
        Document.objects.filter(pk__in=ids, mission__in=perimetre).select_related("mission")
    )
    if user.role == Role.DG:
        # Le DG ne lit que le rapport diffusé (l'API des documents lui reste fermée).
        diffuses = _rapports_diffuses([d.object_id for d in documents])
        return {
            d.pk
            for d in documents
            if d.type_document == CODE_DOCUMENT_RAPPORT
            and d.object_id in diffuses
            and _version_prete(d)
        }
    visibles: set[UUID] = set()
    for document in documents:
        if user.role == Role.AUDITE and (
            document.type_document not in settings.RECHERCHE_TYPES_DOCUMENTS_AUDITE
        ):
            continue
        if not _version_prete(document):
            continue
        try:
            objet = objet_de(document)
            if fournisseur_de(document.type_document).peut_consulter(user, objet):
                visibles.add(document.pk)
        except (Http404, RegleMetierError):
            continue
    return visibles


# ------------------------------------------------------------------------------ registre


def _aucun(_objet: Any) -> list[tuple[str, UUID]]:
    return []


SOURCES: dict[str, Source] = {
    TYPE_MISSION: Source(TYPE_MISSION, Mission, _document_mission, _visibles_missions, _aucun),
    TYPE_CONSTAT: Source(
        TYPE_CONSTAT, Constat, _document_constat, _visibles_constats, _dependants_constat
    ),
    TYPE_RECOMMANDATION: Source(
        TYPE_RECOMMANDATION,
        Recommandation,
        _document_recommandation,
        _visibles_recommandations,
        _aucun,
    ),
    TYPE_ACTION: Source(TYPE_ACTION, SuiviAction, _document_action, _visibles_actions, _aucun),
    TYPE_DOCUMENT: Source(TYPE_DOCUMENT, Document, _document_document, _visibles_documents, _aucun),
}


def objets_a_reindexer(instance: Model) -> list[tuple[str, UUID]]:
    """Couples (type, pk) à réindexer après l'enregistrement de `instance`."""
    if isinstance(instance, DocumentVersion):
        return [(TYPE_DOCUMENT, instance.document_id)]
    for source in SOURCES.values():
        if type(instance) is source.modele:
            return [(source.type, instance.pk), *source.dependants(instance)]
    return []


MODELES_SURVEILLES: tuple[type[Model], ...] = (
    *(source.modele for source in SOURCES.values()),
    DocumentVersion,
)
