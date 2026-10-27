import pytest
from auditlog.models import LogEntry
from django.apps import apps

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


@pytest.mark.django_db
def test_all_objects_includes_deleted(user: User) -> None:
    Exemple.objects.create(nom="vivant")
    mort = Exemple.objects.create(nom="mort")
    mort.soft_delete(by=user)
    assert Exemple.objects.count() == 1
    assert Exemple.all_objects.count() == 2
