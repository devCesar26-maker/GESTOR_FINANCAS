"""Rotas do app Usuarios."""

from django.urls import path

from .views import (
    GoogleLoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistroAPIView,
)

urlpatterns = [
    path("auth/registro/", RegistroAPIView.as_view(), name="auth-registro"),
    # Reset de senha por e-mail (token único de 1 hora).
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    # Login/Cadastro com Google (id_token do Google Identity Services).
    path("auth/google/", GoogleLoginView.as_view(), name="auth-google"),
]
