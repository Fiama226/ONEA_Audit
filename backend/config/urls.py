from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.users.account_urls")),
    path("api/v1/", include("apps.referentiel.urls")),
    path("api/v1/", include("apps.missions.urls")),
    path("api/v1/", include("apps.programmation.urls")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

# /admin/ is opt-in in production (DJANGO_ADMIN_ENABLED=true); on by default in dev/test.
if settings.DJANGO_ADMIN_ENABLED:
    urlpatterns.insert(0, path("admin/", admin.site.urls))
