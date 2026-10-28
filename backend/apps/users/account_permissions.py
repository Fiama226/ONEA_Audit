"""Account administration is reserved to the ADMIN role."""

from .permissions import IsAdmin

AccountAdminPermission = IsAdmin
