import pytest
from auditlog.models import LogEntry
from django.apps import apps
from django.utils import timezone

from apps.core.exceptions import SuppressionPhysiqueInterditeError
from apps.core.gardes_sql import maintenance
from apps.core.models import BaseModel
from apps.users.models import User
from tests.testapp.models import Exemple


def test_soft_delete_hides_from_default_manager(user: User) -> None:
    e = Exemple.objects.create(nom="a", created_by=user)
    e.soft_delete(by=user)
    assert not Exemple.objects.filter(pk=e.pk).exists()
    assert Exemple.all_objects.filter(pk=e.pk).exists()
    assert LogEntry.objects.get_for_object(e).count() >= 2


def test_soft_delete_sets_metadata(user: User) -> None:
    e = Exemple.objects.create(nom="a", created_by=user)
    e.soft_delete(by=user)
    e.refresh_from_db()
    assert e.deleted_at is not None
    assert e.updated_by == user


def test_base_model_defaults(user: User) -> None:
    e = Exemple.objects.create(nom="a", created_by=user)
    assert e.pk is not None
    assert str(e.pk).count("-") == 4  # UUID
    assert e.created_at is not None
    assert e.updated_at is not None
    assert e.deleted_at is None


def test_base_model_is_abstract() -> None:
    assert BaseModel._meta.abstract
    assert not any(m is BaseModel for m in apps.get_models())


def test_all_objects_includes_deleted(user: User) -> None:
    Exemple.objects.create(nom="vivant")
    mort = Exemple.objects.create(nom="mort")
    mort.soft_delete(by=user)
    assert Exemple.objects.count() == 1
    assert Exemple.all_objects.count() == 2


def test_soft_delete_logs_actor_and_deleted_at(user: User) -> None:
    e = Exemple.objects.create(nom="a")
    before = LogEntry.objects.get_for_object(e).count()
    e.soft_delete(by=user)
    entries = LogEntry.objects.get_for_object(e)
    assert entries.count() == before + 1
    suppression = [
        x for x in entries if x.action == LogEntry.Action.UPDATE and "deleted_at" in x.changes_dict
    ]
    assert len(suppression) == 1
    assert suppression[0].actor == user


def test_soft_delete_audit_independant_de_l_egalite_d_horodatage(user: User) -> None:
    """Horloge Windows ~15,6 ms : création et suppression peuvent partager le même instant."""
    e = Exemple.objects.create(nom="a")
    e.soft_delete(by=user)
    instant = timezone.now()
    with maintenance():
        LogEntry.objects.get_for_object(e).update(timestamp=instant)
    entries = LogEntry.objects.get_for_object(e)
    assert entries.values("timestamp").distinct().count() == 1
    suppression = [
        x for x in entries if x.action == LogEntry.Action.UPDATE and "deleted_at" in x.changes_dict
    ]
    assert len(suppression) == 1
    assert suppression[0].actor == user
    assert entries.order_by("-timestamp", "-pk").first() == suppression[0]


def test_soft_delete_twice_is_noop(user: User) -> None:
    e = Exemple.objects.create(nom="a")
    e.soft_delete(by=user)
    first = Exemple.all_objects.get(pk=e.pk).deleted_at
    count = LogEntry.objects.get_for_object(e).count()
    e.soft_delete(by=user)
    assert Exemple.all_objects.get(pk=e.pk).deleted_at == first
    assert LogEntry.objects.get_for_object(e).count() == count


def test_instance_delete_forbidden(user: User) -> None:
    e = Exemple.objects.create(nom="a")
    with pytest.raises(SuppressionPhysiqueInterditeError, match="soft_delete"):
        e.delete()
    assert Exemple.all_objects.filter(pk=e.pk).exists()


def test_queryset_delete_forbidden(user: User) -> None:
    Exemple.objects.create(nom="a")
    with pytest.raises(SuppressionPhysiqueInterditeError):
        Exemple.objects.all().delete()
    with pytest.raises(SuppressionPhysiqueInterditeError):
        Exemple.all_objects.all().delete()
    assert Exemple.all_objects.count() == 1


def test_hard_delete_escape_hatch(user: User) -> None:
    e = Exemple.objects.create(nom="a")
    e.hard_delete()
    assert not Exemple.all_objects.filter(pk=e.pk).exists()
