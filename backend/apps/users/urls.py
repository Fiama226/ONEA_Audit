from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import MeView, TutorielView, UtilisateurViewSet

router = SimpleRouter()
router.register("users", UtilisateurViewSet, basename="user")

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("me/tutoriel/", TutorielView.as_view(), name="me-tutoriel"),
    *router.urls,
]
