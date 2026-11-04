from django.conf import settings
from django.contrib import admin
from django.http import Http404, HttpRequest, HttpResponse
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.schema import SchemaAccess
from apps.users.admin_login import ConnexionAdminForm
from apps.users.authentication import SessionAuthentication401

# API docs: same authentication as the API (session opened by /api/v1/auth/login/).
# Access: SERVE_PERMISSIONS (IsAdminUser in production).
_SCHEMA_ACCESS = {
    "authentication_classes": [SessionAuthentication401],
    "permission_classes": [SchemaAccess],
}

urlpatterns = [
    path("api/v1/", include("apps.core.urls")),
    path("api/v1/", include("apps.users.auth_urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.users.account_urls")),
    path("api/v1/", include("apps.referentiel.urls")),
    path("api/v1/", include("apps.missions.urls")),
    path("api/v1/", include("apps.programmation.urls")),
    path("api/v1/", include("apps.documents.urls")),
    path("api/v1/", include("apps.analyse.urls")),
    path("api/v1/", include("apps.accomplissement.urls")),
    path("api/v1/", include("apps.constats.urls")),
    path("api/v1/", include("apps.signatures.urls")),
    path("api/v1/", include("apps.recommandations.urls")),
    path("api/v1/", include("apps.communication.urls")),
    path("api/v1/", include("apps.suivi.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.suivi.urls_relances")),
    path("api/v1/", include("apps.tableaux_de_bord.urls")),
    path("api/v1/", include("apps.recherche.urls")),
    path("api/schema/", SpectacularAPIView.as_view(**_SCHEMA_ACCESS), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema", **_SCHEMA_ACCESS),
        name="docs",
    ),
]


def _changement_mot_de_passe_admin_ferme(request: HttpRequest) -> HttpResponse:
    """AUTH-09: the admin page re-checks the old password without counting failures and
    keeps the pending codes; a password changes through the application only."""
    raise Http404


# /admin/ is opt-in in production (DJANGO_ADMIN_ENABLED=true); on by default in dev/test.
if settings.DJANGO_ADMIN_ENABLED:
    # The admin login goes through the API login checks (lockout, expiry, no OTP bypass).
    admin.site.login_form = ConnexionAdminForm
    urlpatterns.insert(0, path("admin/", admin.site.urls))
    urlpatterns.insert(0, re_path(r"^admin/password_change/", _changement_mot_de_passe_admin_ferme))

handler404 = "apps.core.views.erreur_404"
handler500 = "apps.core.views.erreur_500"
