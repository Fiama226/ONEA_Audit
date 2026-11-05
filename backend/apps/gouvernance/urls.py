from django.urls import path

from . import views

urlpatterns = [
    path("governance-rules/", views.RegleGouvernanceListeView.as_view(), name="governance-rules"),
    path(
        "governance-rules/<str:cle>/",
        views.RegleGouvernanceDetailView.as_view(),
        name="governance-rule",
    ),
]
