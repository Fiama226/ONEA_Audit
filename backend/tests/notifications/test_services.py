import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import SuppressionPhysiqueInterditeError
from apps.notifications.exceptions import NotificationImmuableError
from apps.notifications.models import Notification, TypeNotification
from apps.notifications.services import (
    marquer_lue,
    marquer_toutes_lues,
    nombre_non_lues,
    notifier,
)
from apps.users.models import Role, User
from tests.factories import MissionFactory, make_user

from .factories import creer_notification

pytestmark = pytest.mark.django_db

ARGS = {
    "type": TypeNotification.RELANCE,
    "titre": "Relance",
    "message": "Une action arrive à échéance.",
    "lien": "/recommandations/actions/abc",
}


def test_notifier_ignore_les_comptes_desactives() -> None:
    actif = make_user(Role.AUDITE)
    desactive = make_user(Role.AUDITE, desactive_le=timezone.now())
    inactif = make_user(Role.AUDITE, is_active=False)
    assert notifier([actif, desactive, inactif, actif], **ARGS) == 1
    assert Notification.objects.get().destinataire == actif


def test_notifier_dedoublonne_par_cle() -> None:
    u = make_user(Role.AUDITE)
    assert notifier([u], cle="relance:1", **ARGS) == 1
    assert notifier([u], cle="relance:1", **ARGS) == 0
    assert Notification.objects.count() == 1
    assert notifier([u], cle="relance:2", **ARGS) == 1


def test_sans_cle_pas_de_dedoublonnage_et_cle_par_destinataire() -> None:
    a, b = make_user(Role.AUDITE), make_user(Role.AUDITE)
    assert notifier([a], **ARGS) == 1
    assert notifier([a], **ARGS) == 1
    assert notifier([a, b], cle="k", **ARGS) == 2


def test_cle_liberee_par_suppression_logique() -> None:
    u = make_user(Role.AUDITE)
    notifier([u], cle="k", **ARGS)
    Notification.objects.get().soft_delete(u)
    assert notifier([u], cle="k", **ARGS) == 1


def test_notifier_lie_l_objet() -> None:
    u = make_user(Role.AUDITE)
    mission = MissionFactory()
    notifier([u], objet=mission, **ARGS)
    n = Notification.objects.get()
    assert n.object_id == mission.pk
    assert n.content_type is not None


@pytest.mark.parametrize("lien", ["http://x.test", "recommandations", "//evil.test", "/\\evil", ""])
def test_lien_relatif_obligatoire_en_base(lien: str) -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        creer_notification(lien=lien)


def test_lien_racine_accepte() -> None:
    creer_notification(lien="/")


def test_objet_incomplet_refuse_en_base() -> None:
    with pytest.raises(IntegrityError), transaction.atomic():
        creer_notification(object_id="00000000-0000-0000-0000-000000000001")


def test_marquer_lue_par_un_autre_refuse() -> None:
    n = creer_notification()
    with pytest.raises(PermissionDenied):
        marquer_lue(n, by=make_user(Role.RAI))
    n.refresh_from_db()
    assert n.lue_le is None


def test_marquer_lue_par_le_destinataire() -> None:
    n = creer_notification()
    marquer_lue(n, by=n.destinataire)
    n.refresh_from_db()
    assert n.lue_le is not None
    assert n.updated_by == n.destinataire
    premiere = n.lue_le
    marquer_lue(n, by=n.destinataire)  # idempotent
    n.refresh_from_db()
    assert n.lue_le == premiere


def test_marquer_toutes_lues_renvoie_le_nombre() -> None:
    u, autre = make_user(Role.AUDITE), make_user(Role.AUDITE)
    for _ in range(3):
        creer_notification(destinataire=u)
    autrui_n = creer_notification(destinataire=autre)
    assert nombre_non_lues(u) == 3
    assert marquer_toutes_lues(u) == 3
    assert marquer_toutes_lues(u) == 0
    assert nombre_non_lues(u) == 0
    assert nombre_non_lues(autre) == 1
    autrui_n.refresh_from_db()
    assert autrui_n.lue_le is None


def test_aucune_fuite_entre_utilisateurs() -> None:
    a, b = make_user(Role.AUDITE), make_user(Role.AUDITE)
    creer_notification(destinataire=a)
    assert nombre_non_lues(b) == 0
    assert marquer_toutes_lues(b) == 0
    assert Notification.objects.filter(destinataire=a, lue_le__isnull=True).count() == 1


def test_update_et_bulk_limites_aux_champs_d_etat() -> None:
    n = creer_notification()
    with pytest.raises(NotificationImmuableError):
        Notification.objects.filter(pk=n.pk).update(message="x")
    with pytest.raises(NotificationImmuableError):
        Notification.all_objects.filter(pk=n.pk).update(destinataire=make_user())
    n.message = "x"
    with pytest.raises(NotificationImmuableError):
        Notification.objects.bulk_update([n], ["message"])
    with pytest.raises(NotificationImmuableError):
        n.save()
    with pytest.raises(NotificationImmuableError):
        n.save(update_fields=["titre"])
    with pytest.raises(NotificationImmuableError):
        Notification.objects.bulk_create(
            [n], update_conflicts=True, update_fields=["titre"], unique_fields=["id"]
        )
    assert Notification.objects.filter(pk=n.pk).update(lue_le=timezone.now()) == 1


def test_suppression_physique_interdite() -> None:
    n = creer_notification()
    with pytest.raises(SuppressionPhysiqueInterditeError):
        n.delete()
    with pytest.raises(SuppressionPhysiqueInterditeError):
        Notification.objects.all().delete()


def test_piste_d_audit() -> None:
    from auditlog.models import LogEntry

    n = creer_notification()
    marquer_lue(n, by=n.destinataire)
    entrees = LogEntry.objects.get_for_object(n)
    assert entrees.count() == 2
    assert entrees.first().actor == n.destinataire  # type: ignore[union-attr]


def test_related_name() -> None:
    u: User = make_user(Role.AUDITE)
    creer_notification(destinataire=u)
    assert u.notifications.count() == 1  # type: ignore[attr-defined]
