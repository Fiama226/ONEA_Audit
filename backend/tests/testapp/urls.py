from django.urls import path

from . import views

urlpatterns = [
    path("regle-metier/", views.regle_metier),
    path("regle-metier-simple/", views.regle_metier_simple),
    path("validation/", views.validation),
    path("validation-plate/", views.validation_plate),
]
