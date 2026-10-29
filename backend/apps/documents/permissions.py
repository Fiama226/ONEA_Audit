"""Accès à l'API des documents : rôles (403), visibilité des missions (404), droits du fournisseur.

Gabarits et formats de numérotation : lecture ADMIN et RAI, écriture ADMIN. Documents de mission :
ADMIN et DG sont refusés (403, lot 3 D4) ; le droit de lire ou de générer vient du fournisseur du
type de document (`registre.Fournisseur`).
"""

from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.http import Http404
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.core.handlers import FORBIDDEN
from apps.missions.models import Mission
from apps.missions.permissions import mission_visible
from apps.users.models import Role, User
from apps.users.permissions import HasRole

from .models import Document
from .moteur.registre import Fournisseur
from .moteur.registre import type_document as type_enregistre

ROLES_DOCUMENTS: tuple[str, ...] = (Role.RAI, Role.AUDITEUR, Role.AUDITE)
LecteurAdminRai = HasRole(Role.ADMIN, Role.RAI)
EcrivainAdmin = HasRole(Role.ADMIN)
LecteurRai = HasRole(Role.RAI)


class DocumentAccessPermission(BasePermission):
    """Documents de mission : RAI, AUDITEUR et AUDITE ; ADMIN et DG sont refusés (403)."""

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and isinstance(user, User)
            and user.role in ROLES_DOCUMENTS
        )


def fournisseur_de(code: str) -> Fournisseur:
    return type_enregistre(code).fournisseur


def objet_de(document: Document) -> Any:
    """Objet source d'un document (404 s'il a disparu)."""
    try:
        return fournisseur_de(document.type_document).objet(document.object_id)
    except ObjectDoesNotExist as exc:
        raise Http404 from exc


def exiger_consultation(user: User, document: Document) -> None:
    """403 quand le fournisseur refuse la lecture d'un document d'une mission visible."""
    objet = objet_de(document)
    if not fournisseur_de(document.type_document).peut_consulter(user, objet):
        raise PermissionDenied(FORBIDDEN)


def peut_generer(user: User, document: Document) -> bool:
    return fournisseur_de(document.type_document).peut_generer(user, objet_de(document))


def mission_du_parametre(user: User, brut: Any) -> Mission:
    """Mission visible pour l'utilisateur, sinon 404."""
    return mission_visible(user, brut)
