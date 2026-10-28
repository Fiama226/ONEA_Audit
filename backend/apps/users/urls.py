from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import MeView, UtilisateurViewSet

router = SimpleRouter()
router.register("users", UtilisateurViewSet, basename="user")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    *router.urls,
]
