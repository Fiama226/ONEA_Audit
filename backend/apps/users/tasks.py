import logging

from celery import shared_task
from django.db.models import F

from .keycloak_admin import KeycloakIndisponible, KeycloakNonConfigure
from .keycloak_sync import synchroniser_avec_resultat
from .models import KeycloakSyncStatut, User

logger = logging.getLogger(__name__)


@shared_task(name="users.synchroniser_comptes_keycloak")  # type: ignore[untyped-decorator]
def synchroniser_comptes_keycloak(limit: int = 50) -> int:
    """Retry the pending / failed Keycloak syncs, oldest attempt first.

    Stops at the first `KeycloakIndisponible` (or missing configuration): the other
    accounts would fail the same way. Returns the number of accounts processed.
    """
    ids = list(
        User.objects.filter(
            keycloak_id__isnull=False,
            keycloak_sync_statut__in=(KeycloakSyncStatut.EN_ATTENTE, KeycloakSyncStatut.ECHEC),
        )
        .order_by(F("keycloak_sync_le").asc(nulls_first=True), "pk")
        .values_list("pk", flat=True)[:limit]
    )
    traites = 0
    for compte_id in ids:
        _, erreur = synchroniser_avec_resultat(compte_id, by=None)
        traites += 1
        if isinstance(erreur, KeycloakIndisponible | KeycloakNonConfigure):
            logger.warning("Keycloak sync batch interrupted after %s account(s)", traites)
            break
    return traites
