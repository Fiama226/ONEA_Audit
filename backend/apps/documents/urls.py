from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("document-types", views.TypeDocumentViewSet, basename="document-type")
router.register("templates", views.GabaritViewSet, basename="template")
router.register("numbering-formats", views.FormatNumerotationViewSet, basename="numbering-format")
router.register("documents", views.DocumentViewSet, basename="document")
router.register("document-versions", views.VersionViewSet, basename="document-version")

urlpatterns = router.urls
