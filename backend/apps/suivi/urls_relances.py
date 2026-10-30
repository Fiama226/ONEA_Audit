from rest_framework.routers import SimpleRouter

from . import views_relances

router = SimpleRouter()
router.register("reminders", views_relances.RelanceViewSet, basename="reminder")

urlpatterns = router.urls
