from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("audit-plans", views.ProgrammeAnnuelViewSet, basename="audit-plan")
router.register("audit-plan-lines", views.LigneProgrammeViewSet, basename="audit-plan-line")

urlpatterns = router.urls
