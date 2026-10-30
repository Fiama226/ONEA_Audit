from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("reports", views.RapportViewSet, basename="report")
router.register("draft-reports", views.RapportProvisoireViewSet, basename="draft-report")
router.register(
    "draft-report-responses", views.ReponseRapportViewSet, basename="draft-report-response"
)
router.register("report-recipients", views.DestinataireViewSet, basename="report-recipient")

urlpatterns = router.urls
