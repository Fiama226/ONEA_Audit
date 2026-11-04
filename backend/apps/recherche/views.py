"""API de la recherche : droits par rôle, limitation de débit, aucune fuite.

Le filtrage par droits est fait par `services.rechercher` (filtre moteur, puis second filtre en
base). La vue valide `q` et `types`, complète chaque résultat (référence de mission, étape du
document) et ne renvoie jamais de total.
"""

from typing import Any, cast
from uuid import UUID

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import RegleMetierError
from apps.core.schema import ERROR_400, ERROR_429, ERROR_503, ERROR_RESPONSES
from apps.documents.models import Document
from apps.documents.moteur.registre import type_document
from apps.missions.models import Mission
from apps.users.models import User
from apps.users.permissions import HasRole

from . import services
from .client import Hit
from .serializers import (
    RechercheParametresSerializer,
    ReponseRechercheSerializer,
    nettoyer_affichage,
)
from .sources import TYPE_DOCUMENT
from .visibilite import ROLES_RECHERCHE

TAG = "Recherche"
LIMITE = 20


def _uuid(valeur: str | None) -> UUID | None:
    try:
        return UUID(str(valeur))
    except ValueError:
        return None


def _etapes_documents(hits: list[Hit]) -> dict[str, int | None]:
    """Étape du type de document (registre du lot 4), par identifiant d'objet."""
    ids = [pk for h in hits if h.type == TYPE_DOCUMENT and (pk := _uuid(h.objet_id)) is not None]
    if not ids:
        return {}
    etapes: dict[str, int | None] = {}
    for pk, code in Document.objects.filter(pk__in=ids).values_list("pk", "type_document"):
        try:
            etapes[str(pk)] = type_document(code).etape
        except RegleMetierError:
            etapes[str(pk)] = None
    return etapes


def _references_missions(hits: list[Hit]) -> dict[str, str]:
    ids = [pk for h in hits if (pk := _uuid(h.mission_id)) is not None]
    if not ids:
        return {}
    return {
        str(pk): reference
        for pk, reference in Mission.objects.filter(pk__in=ids).values_list("pk", "reference")
    }


def construire_resultats(hits: list[Hit]) -> list[dict[str, Any]]:
    references = _references_missions(hits)
    etapes = _etapes_documents(hits)
    return [
        {
            "type": h.type,
            "objet_id": h.objet_id,
            "mission_id": h.mission_id,
            "mission_reference": references.get(str(h.mission_id), ""),
            "titre": nettoyer_affichage(h.titre, marqueurs=True),
            "sous_titre": nettoyer_affichage(h.sous_titre, marqueurs=False),
            "extrait": nettoyer_affichage(h.extrait, marqueurs=True),
            "etape": etapes.get(h.objet_id) if h.type == TYPE_DOCUMENT else None,
        }
        for h in hits
    ]


class RechercheView(APIView):
    permission_classes = cast(list[type[BasePermission]], [HasRole(*ROLES_RECHERCHE)])
    throttle_scope = "recherche"
    pagination_class = None

    @extend_schema(
        tags=[TAG],
        summary="Recherche globale filtrée par droits",
        description=(
            "Renvoie au plus 20 résultats visibles de l'utilisateur, sans total (`plus` indique "
            "qu'il en reste). Le surlignage est porté par deux caractères de contrôle réservés "
            "(U+0002 début, U+0003 fin). Rôle ADMIN : 403 ; au-delà de 60 requêtes par minute : "
            "429. Moteur indisponible : repli sur les missions en base (`degrade` vrai), ou 503 si "
            "la requête exclut les missions."
        ),
        parameters=[RechercheParametresSerializer],
        responses={
            200: ReponseRechercheSerializer,
            **ERROR_400,
            **ERROR_RESPONSES,
            **ERROR_429,
            **ERROR_503,
        },
    )
    def get(self, request: Request) -> Response:
        parametres = RechercheParametresSerializer(data=request.query_params)
        parametres.is_valid(raise_exception=True)
        resultat = services.rechercher(
            cast(User, request.user),
            parametres.validated_data["q"],
            types=parametres.validated_data.get("types"),
            limite=LIMITE,
        )
        reponse = Response(
            ReponseRechercheSerializer(
                {
                    "resultats": construire_resultats(resultat.resultats),
                    "plus": resultat.plus,
                    "degrade": resultat.degrade,
                }
            ).data
        )
        reponse["Cache-Control"] = "no-store"
        return reponse
