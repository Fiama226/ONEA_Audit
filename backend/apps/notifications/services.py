from collections.abc import Iterable

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.core.audit import actor_scope
from apps.core.models import BaseModel
from apps.users.models import User

from .models import Notification


def notifier(
    destinataires: Iterable[User],
    *,
    type: str,  # noqa: A002
    titre: str,
    message: str,
    lien: str,
    objet: BaseModel | None = None,
    cle: str = "",
) -> int:
    """Crée une notification par destinataire actif ; renvoie le nombre de lignes créées.

    Les comptes inactifs ou désactivés, les doublons de destinataires et les couples
    (destinataire, clé) déjà notifiés sont ignorés.
    """
    uniques = {u.pk: u for u in destinataires if u.is_active and u.desactive_le is None}
    if not uniques:
        return 0
    content_type = ContentType.objects.get_for_model(objet) if objet is not None else None
    lignes = [
        Notification(
            destinataire=u,
            type=type,
            titre=titre,
            message=message,
            lien=lien,
            content_type=content_type,
            object_id=objet.pk if objet is not None else None,
            cle=cle,
        )
        for u in uniques.values()
    ]
    with transaction.atomic():
        Notification.all_objects.bulk_create(lignes, ignore_conflicts=True)
    # Les identifiants sont générés côté client : seules les lignes réellement insérées existent.
    return Notification.all_objects.filter(pk__in=[n.pk for n in lignes]).count()


def marquer_lue(notification: Notification, *, by: User) -> Notification:
    if notification.destinataire_id != by.pk:
        raise PermissionDenied("Cette notification ne vous est pas destinée.")
    if notification.lue_le is None:
        notification.lue_le = timezone.now()
        notification.updated_by = by
        with actor_scope(by):
            notification.save(update_fields=["lue_le", "updated_by", "updated_at"])
    return notification


def marquer_toutes_lues(user: User) -> int:
    maintenant = timezone.now()
    return Notification.objects.filter(destinataire=user, lue_le__isnull=True).update(
        lue_le=maintenant, updated_by=user, updated_at=maintenant
    )


def nombre_non_lues(user: User) -> int:
    return Notification.objects.filter(destinataire=user, lue_le__isnull=True).count()
