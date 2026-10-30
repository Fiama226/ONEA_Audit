from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("findings", views.ConstatViewSet, basename="finding")
router.register("finding-responses", views.ReponseViewSet, basename="finding-response")
router.register("recommendations", views.RecommandationViewSet, basename="recommendation")

urlpatterns = router.urls
