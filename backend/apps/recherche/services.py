"""Service de recherche filtré par droits et indexation.

Défense en profondeur : (1) le filtre `visibilite.filtre_pour` est envoyé au moteur ;
(2) chaque identifiant renvoyé est revérifié en base (`Source.visibles`, mêmes requêtes que l'API).
Ce qui est rejeté est retiré du résultat et réindexé. Aucun total n'est jamais renvoyé.
"""

import logging
import unicodedata
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from django.db.models import Q
from rest_framework.exceptions import ValidationError

from apps.missions.models import StatutMission
from apps.users.models import User

from .client import MARQUEUR_DEBUT, MARQUEUR_FIN, Hit, echapper_filtre, moteur
from .exceptions import RechercheIndisponibleError
from .sources import SOURCES, TYPE_MISSION, _perimetre_missions
from .visibilite import filtre_pour

logger = logging.getLogger(__name__)

LONGUEUR_MIN = 2
LONGUEUR_MAX = 200
LIMITE_MAX = 50
LOT_REINDEXATION = 500


@dataclass(frozen=True)
class ResultatRecherche:
    resultats: list[Hit]
    plus: bool
    # Vrai quand le moteur ne répond pas : seules les missions ont été cherchées, en base.
    degrade: bool = False


def nettoyer_requete(q: str) -> str:
    """Retire les caractères de contrôle (dont les marqueurs de surlignage) et les espaces
    superflus."""
    sans_marqueur = str(q).replace(MARQUEUR_DEBUT, "").replace(MARQUEUR_FIN, "")
    sans_controle = "".join(
        " " if unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") else c for c in sans_marqueur
    )
    return " ".join(sans_controle.split())


def _valider(q: str, types: list[str] | None) -> tuple[str, list[str] | None]:
    propre = nettoyer_requete(q)
    if not LONGUEUR_MIN <= len(propre) <= LONGUEUR_MAX:
        raise ValidationError(
            {"q": [f"La recherche doit comporter de {LONGUEUR_MIN} à {LONGUEUR_MAX} caractères."]}
        )
    if types is not None:
        inconnus = sorted(set(types) - set(SOURCES))
        if inconnus:
            raise ValidationError({"types": [f"Type inconnu : {', '.join(inconnus)}."]})
    return propre, types


def _uuid(valeur: str) -> UUID | None:
    try:
        return UUID(valeur)
    except (ValueError, AttributeError):
        return None


def _filtre_types(filtre: str, types: list[str] | None) -> str:
    if types is None:
        return filtre
    liste = ", ".join(f'"{echapper_filtre(t)}"' for t in sorted(set(types)))
    return f"({filtre}) AND type IN [{liste}]"


def _demander_reindexation(rejetes: list[Hit]) -> None:
    from .tasks import indexer_objet

    for hit in rejetes:
        logger.warning("Recherche : résultat %s rejeté par le second filtre.", hit.id)
        try:
            indexer_objet.delay(hit.type, hit.objet_id)
        except Exception:  # noqa: BLE001 — la réconciliation nocturne rattrape
            logger.warning("Recherche : réindexation de %s non planifiée.", hit.id)


def _reverifier(
    user: User, hits: list[Hit], types: list[str] | None
) -> tuple[list[Hit], list[Hit]]:
    """Sépare les hits confirmés en base des hits rejetés (ordre du moteur conservé)."""
    autorises = set(types) if types is not None else set(SOURCES)
    par_type: dict[str, list[UUID]] = {}
    valides: list[tuple[Hit, UUID]] = []
    rejetes: list[Hit] = []
    for hit in hits:
        pk = _uuid(hit.objet_id)
        if hit.type not in autorises or pk is None or hit.id != f"{hit.type}-{pk}":
            rejetes.append(hit)
            continue
        par_type.setdefault(hit.type, []).append(pk)
        valides.append((hit, pk))
    visibles = {t: SOURCES[t].visibles(user, ids) for t, ids in par_type.items()}
    confirmes: list[Hit] = []
    for hit, pk in valides:
        (confirmes if pk in visibles[hit.type] else rejetes).append(hit)
    return confirmes, rejetes


def _repli_missions(user: User, q: str, limite: int) -> ResultatRecherche:
    """Moteur indisponible : recherche des missions visibles (référence, titre) directement en base.

    Mode dégradé : mêmes droits que l'API (`_perimetre_missions`), brouillons exclus comme dans
    l'index ; les autres types (constats, documents...) ne sont pas cherchés.
    """
    missions = (
        _perimetre_missions(user)
        .exclude(statut=StatutMission.BROUILLON)
        .filter(Q(reference__icontains=q) | Q(titre__icontains=q))
        .order_by("-updated_at", "pk")[: limite + 1]
    )
    hits = [
        Hit(
            id=f"{TYPE_MISSION}-{m.pk}",
            type=TYPE_MISSION,
            objet_id=str(m.pk),
            mission_id=str(m.pk),
            titre=m.titre,
            sous_titre=m.reference,
            extrait="",
        )
        for m in missions
    ]
    return ResultatRecherche(hits[:limite], len(hits) > limite, degrade=True)


def rechercher(
    user: User, q: str, *, types: list[str] | None = None, limite: int = 20
) -> ResultatRecherche:
    propre, types = _valider(q, types)
    limite = max(1, min(int(limite), LIMITE_MAX))
    filtre = filtre_pour(user)
    if filtre is None:
        return ResultatRecherche([], False)
    try:
        hits = moteur().rechercher(propre, filtre=_filtre_types(filtre, types), limite=limite + 1)
    except RechercheIndisponibleError:
        if types is not None and TYPE_MISSION not in types:
            raise
        return _repli_missions(user, propre, limite)
    confirmes, rejetes = _reverifier(user, hits, types)
    if rejetes:
        _demander_reindexation(rejetes)
    return ResultatRecherche(confirmes[:limite], len(confirmes) > limite)


# ---------------------------------------------------------------------------- indexation


def indexer_objet_maintenant(type_: str, pk: str) -> None:
    """Indexe l'objet, ou le retire de l'index s'il est absent, supprimé ou non indexable."""
    source = SOURCES.get(type_)
    cle = _uuid(pk)
    if source is None or cle is None:
        logger.warning("Recherche : objet à indexer inconnu (%s, %s).", type_, pk)
        return
    objet = source.modele.objects.filter(pk=cle).first()  # type: ignore[attr-defined]
    document = source.document(objet) if objet is not None else None
    if document is None:
        moteur().retirer([f"{type_}-{cle}"])
    else:
        moteur().indexer([document])


def reconcilier_index(type_: str | None = None) -> int:
    """Réindexe tout (ou un type) par lots ; sans type, l'index est d'abord vidé.

    Renvoie le nombre de documents indexés.
    """
    if type_ is not None and type_ not in SOURCES:
        raise ValueError(f"Type inconnu : {type_}.")
    m = moteur()
    if type_ is None:
        m.vider()
    total = 0
    for source in SOURCES.values():
        if type_ not in (None, source.type):
            continue
        lot: list[dict[str, Any]] = []
        a_retirer: list[str] = []
        qs = source.modele.objects.order_by("pk")  # type: ignore[attr-defined]
        for objet in qs.iterator(chunk_size=LOT_REINDEXATION):
            document = source.document(objet)
            if document is None:
                a_retirer.append(f"{source.type}-{objet.pk}")
                continue
            lot.append(document)
            if len(lot) >= LOT_REINDEXATION:
                m.indexer(lot)
                total += len(lot)
                lot = []
        if lot:
            m.indexer(lot)
            total += len(lot)
        if a_retirer and type_ is not None:
            for debut in range(0, len(a_retirer), LOT_REINDEXATION):
                m.retirer(a_retirer[debut : debut + LOT_REINDEXATION])
    return total
