from django.urls import path

from . import auth_views

urlpatterns = [
    path("auth/login/", auth_views.ConnexionView.as_view(), name="auth-login"),
    path("auth/login/otp/", auth_views.ConnexionCodeView.as_view(), name="auth-login-otp"),
    path("auth/logout/", auth_views.DeconnexionView.as_view(), name="auth-logout"),
    path("auth/session/", auth_views.SessionView.as_view(), name="auth-session"),
    path("auth/csrf/", auth_views.JetonCsrfView.as_view(), name="auth-csrf"),
]
