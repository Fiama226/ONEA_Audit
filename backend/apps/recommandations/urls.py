from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("corrective-actions", views.ActionViewSet, basename="corrective-action")
router.register("risk-acceptances", views.AcceptationViewSet, basename="risk-acceptance")
router.register(
    "action-plan-commitments", views.EngagementViewSet, basename="action-plan-commitment"
)
router.register("action-plans", views.PlanActionsViewSet, basename="action-plan")

urlpatterns = router.urls
