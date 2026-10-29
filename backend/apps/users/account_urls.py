from rest_framework.routers import SimpleRouter

from . import account_views

router = SimpleRouter()
router.register("user-accounts", account_views.UserAccountViewSet, basename="user-account")

urlpatterns = router.urls
