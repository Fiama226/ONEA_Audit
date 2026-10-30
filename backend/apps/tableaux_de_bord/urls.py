from django.urls import path

from . import views

urlpatterns = [
    path("dashboards/rai/", views.TableauRaiView.as_view(), name="dashboard-rai"),
    path("dashboards/auditor/", views.TableauAuditeurView.as_view(), name="dashboard-auditor"),
    path("dashboards/auditee/", views.TableauAuditeView.as_view(), name="dashboard-auditee"),
    path("dashboards/dg/", views.TableauDgView.as_view(), name="dashboard-dg"),
    path(
        "dashboards/implementation-rates/export/",
        views.TauxExportView.as_view(),
        name="dashboard-rates-export",
    ),
]
