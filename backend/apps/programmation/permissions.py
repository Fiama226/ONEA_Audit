from apps.users.models import Role

LECTURE_PROGRAMME: tuple[str, ...] = (Role.ADMIN, Role.RAI, Role.AUDITEUR, Role.DG)
ECRITURE_PROGRAMME: tuple[str, ...] = (Role.RAI,)
