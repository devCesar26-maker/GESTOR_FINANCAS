"""Rotas do app Faturamento."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    CategoriaFinanceiraViewSet,
    CobrancaRecorrenteViewSet,
    DreExportView,
    DreView,
    FaturaViewSet,
    FaturasExportView,
)

router = DefaultRouter()
router.register("faturas", FaturaViewSet, basename="fatura")
router.register("categorias", CategoriaFinanceiraViewSet, basename="categoria")
router.register(
    "cobrancas-recorrentes",
    CobrancaRecorrenteViewSet,
    basename="cobranca-recorrente",
)

# Rotas estáticas ANTES do router: sem isto, o DefaultRouter interpreta
# "faturas/exportar/" como detail-route da fatura (pk="exportar") e a
# exportação nunca é alcançada.
urlpatterns = [
    # Exportação de relatórios (CSV/Excel/PDF)
    path("faturas/exportar/", FaturasExportView.as_view(), name="faturas-exportar"),
    # DRE simplificado (JSON + exportação)
    path("relatorios/dre/", DreView.as_view(), name="relatorio-dre"),
    path(
        "relatorios/dre/exportar/",
        DreExportView.as_view(),
        name="relatorio-dre-exportar",
    ),
]

urlpatterns = urlpatterns + router.urls
