"""Rotas do app Relatorios."""
from django.urls import path
from .views import FluxoCaixaView

urlpatterns = [
    path("fluxo-caixa/", FluxoCaixaView.as_view(), name="relatorio-fluxo-caixa"),
]