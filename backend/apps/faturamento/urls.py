"""Rotas do app Faturamento."""
from rest_framework.routers import DefaultRouter
from .views import CobrancaRecorrenteViewSet, FaturaViewSet

router = DefaultRouter()
router.register("faturas", FaturaViewSet, basename="fatura")
router.register("cobrancas-recorrentes", CobrancaRecorrenteViewSet, basename="cobranca-recorrente")

urlpatterns = router.urls