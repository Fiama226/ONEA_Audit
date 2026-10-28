from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("missions", views.MissionViewSet, basename="mission")
router.register("mission-assignments", views.AffectationViewSet, basename="mission-assignment")
router.register(
    "independence-declarations", views.DeclarationViewSet, basename="independence-declaration"
)
router.register("mission-steps", views.EtapeViewSet, basename="mission-step")
router.register("meetings", views.ReunionViewSet, basename="meeting")
router.register("interviews", views.EntretienViewSet, basename="interview")
router.register("mission-risks", views.RisqueMissionViewSet, basename="mission-risk")

urlpatterns = router.urls
