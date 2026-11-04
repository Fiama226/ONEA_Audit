from django.urls import path

from . import auth_views

urlpatterns = [
    path("auth/login/", auth_views.ConnexionView.as_view(), name="auth-login"),
    path("auth/login/otp/", auth_views.ConnexionCodeView.as_view(), name="auth-login-otp"),
    path("auth/logout/", auth_views.DeconnexionView.as_view(), name="auth-logout"),
    path("auth/session/", auth_views.SessionView.as_view(), name="auth-session"),
    path("auth/csrf/", auth_views.JetonCsrfView.as_view(), name="auth-csrf"),
    path(
        "auth/password/forgot/",
        auth_views.MotDePasseOublieView.as_view(),
        name="auth-password-forgot",
    ),
    path(
        "auth/password/reset/",
        auth_views.ReinitialisationView.as_view(),
        name="auth-password-reset",
    ),
    path(
        "auth/password/change/",
        auth_views.ChangementMotDePasseView.as_view(),
        name="auth-password-change",
    ),
    path(
        "auth/otp/enable/code/",
        auth_views.DemandeCodeActivationOtpView.as_view(),
        name="auth-otp-enable-code",
    ),
    path("auth/otp/enable/", auth_views.ActivationOtpView.as_view(), name="auth-otp-enable"),
    path("auth/otp/disable/", auth_views.DesactivationOtpView.as_view(), name="auth-otp-disable"),
]
