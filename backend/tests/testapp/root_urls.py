"""Root URLconf for settings.test: the project routes plus test-only routes."""

from django.urls import include, path

from config.urls import urlpatterns as project_urlpatterns

urlpatterns = [
    *project_urlpatterns,
    path("api/v1/_test/", include("tests.testapp.urls")),
]
