from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
# Les instantanés d'abord : `work-programs/snapshots/` ne doit jamais être lu comme un `{id}`.
router.register(
    "work-programs/snapshots", views.InstantaneViewSet, basename="work-program-snapshot"
)
router.register("work-programs", views.ProgrammeViewSet, basename="work-program")
router.register("planned-tests", views.TestPrevuViewSet, basename="planned-test")
router.register("test-sheets", views.FicheViewSet, basename="test-sheet")
router.register("evidence", views.PieceViewSet, basename="evidence")
router.register(
    "test-results-agreements", views.AccordResultatsViewSet, basename="test-results-agreement"
)

urlpatterns = router.urls
