from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("signature-settings", views.ParametreSignatureViewSet, basename="signature-setting")

urlpatterns = router.urls
