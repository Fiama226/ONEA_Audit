from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("directions", views.DirectionViewSet, basename="direction")
router.register("processes", views.ProcessusViewSet, basename="process")
router.register("auditable-objects", views.ObjetAuditableViewSet, basename="auditable-object")
router.register("risk-maps", views.CartographieVersionViewSet, basename="risk-map")
router.register("risks", views.RisqueViewSet, basename="risk")

urlpatterns = router.urls
