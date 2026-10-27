from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("audit-log", views.AuditLogViewSet, basename="audit-log")

urlpatterns = [
    path("health/", views.health, name="health"),
    *router.urls,
]
