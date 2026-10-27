import importlib
from collections.abc import Callable, Iterator
from types import ModuleType

import pytest
from django.test import Client, override_settings
from django.urls import Resolver404, resolve

import config.urls


@pytest.fixture
def reload_urls() -> Iterator[Callable[[], ModuleType]]:
    yield lambda: importlib.reload(config.urls)
    importlib.reload(config.urls)


def test_admin_is_mounted_by_default_under_test_settings() -> None:
    assert Client().get("/admin/login/").status_code == 200


def test_admin_is_not_mounted_when_disabled(reload_urls: Callable[[], ModuleType]) -> None:
    with override_settings(DJANGO_ADMIN_ENABLED=False):
        module = reload_urls()
        with pytest.raises(Resolver404):
            resolve("/admin/login/", urlconf=module.__name__)
        # API routes stay available
        assert resolve("/api/v1/health/", urlconf=module.__name__)
