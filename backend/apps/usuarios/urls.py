"""Rotas do app Usuarios."""

from django.urls import path

from .views import RegistroAPIView

urlpatterns = [
    path("auth/registro/", RegistroAPIView.as_view(), name="auth-registro"),
]
