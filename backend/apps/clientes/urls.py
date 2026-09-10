"""
Rotas do app Clientes.

CRUD de clientes/fornecedores servido em /api/clientes/ via router.
"""
from rest_framework.routers import DefaultRouter

from .views import ClienteViewSet

router = DefaultRouter()
router.register("clientes", ClienteViewSet, basename="cliente")

urlpatterns = router.urls