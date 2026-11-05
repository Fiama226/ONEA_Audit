from django.urls import path

from . import views

urlpatterns = [
    path("governance-rules/", views.RegleGouvernanceListeView.as_view(), name="governance-rules"),
    path(
        "governance-rules/<str:cle>/",
        views.RegleGouvernanceDetailView.as_view(),
        name="governance-rule",
    ),
    path(
        "auditee-response-waivers/",
        views.DerogationsReponseAuditeView.as_view(),
        name="auditee-response-waivers",
    ),
    path(
        "auditee-response-waivers/<uuid:etape_id>/waive/",
        views.DerogerView.as_view(),
        name="auditee-response-waive",
    ),
]
