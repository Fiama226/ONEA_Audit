from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("follow-up/actions", views.SuiviActionViewSet, basename="follow-up-action")
router.register(
    "follow-up/recommendations",
    views.RecommandationSuiviViewSet,
    basename="follow-up-recommendation",
)
router.register("follow-up/evidence", views.PreuveViewSet, basename="follow-up-evidence")
router.register(
    "follow-up/extension-requests",
    views.DemandeReportViewSet,
    basename="follow-up-extension-request",
)
router.register("follow-up/missions", views.MissionSuiviViewSet, basename="follow-up-mission")

urlpatterns = router.urls
