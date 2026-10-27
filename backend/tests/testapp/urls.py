from django.urls import path

from . import views

urlpatterns = [
    path("regle-metier/", views.regle_metier),
    path("regle-metier-simple/", views.regle_metier_simple),
    path("validation/", views.validation),
    path("validation-plate/", views.validation_plate),
    path("exemples/<uuid:pk>/", views.exemple_detail),
    path("interdit/", views.interdit),
    path("interdit-drf/", views.interdit_drf),
]
