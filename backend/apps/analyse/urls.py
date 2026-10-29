from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(
    "analysis-questionnaires", views.QuestionnaireViewSet, basename="analysis-questionnaire"
)
router.register("analysis-questions", views.QuestionViewSet, basename="analysis-question")
router.register(
    "process-descriptions", views.DescriptionProcessusViewSet, basename="process-description"
)
router.register("segregation-grids", views.GrilleSeparationViewSet, basename="segregation-grid")
router.register("marc-lines", views.LigneMARCViewSet, basename="marc-line")
router.register("strengths-weaknesses", views.ForceFaiblesseViewSet, basename="strength-weakness")
router.register("audit-frameworks", views.ReferentielAuditViewSet, basename="audit-framework")
router.register("audit-objectives", views.ObjectifAuditViewSet, basename="audit-objective")
router.register(
    "orientation-reports", views.RapportOrientationViewSet, basename="orientation-report"
)

urlpatterns = router.urls
