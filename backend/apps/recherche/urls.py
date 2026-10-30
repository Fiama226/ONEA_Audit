from django.urls import path

from . import views

urlpatterns = [path("search/", views.RechercheView.as_view(), name="search")]
