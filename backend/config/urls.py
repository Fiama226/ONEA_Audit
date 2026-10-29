from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.schema import SchemaAccess
from apps.users.authentication import OIDCBearerAuthentication, SessionAuthentication401

# The only API views that accept the Django session (an ADMIN logged in /admin/ reads the
# docs); every real endpoint is bearer-only. Access: SERVE_PERMISSIONS (IsAdminUser in prod).
_SCHEMA_ACCESS = {
    "authentication_classes": [SessionAuthentication401, OIDCBearerAuthentication],
    "permission_classes": [SchemaAccess],
}

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.users.account_urls")),
    path("api/v1/", include("apps.referentiel.urls")),
    path("api/v1/", include("apps.missions.urls")),
    path("api/v1/", include("apps.programmation.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/", include("apps.analyse.urls")),
    path("api/schema/", SpectacularAPIView.as_view(**_SCHEMA_ACCESS), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", **_SCHEMA_ACCESS),
        name="docs",
    ),
]

# /admin/ is opt-in in production (DJANGO_ADMIN_ENABLED=true); on by default in dev/test.
if settings.DJANGO_ADMIN_ENABLED:
    urlpatterns.insert(0, path("admin/", admin.site.urls))
