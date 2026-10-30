"""Paramètres de signature : lecture ADMIN et RAI, écriture ADMIN seul."""

from apps.users.models import Role
from apps.users.permissions import HasRole

LecteurAdminRai = HasRole(Role.ADMIN, Role.RAI)
EcrivainAdmin = HasRole(Role.ADMIN)
