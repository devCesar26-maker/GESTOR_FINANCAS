"""
Camada de views do app Clientes.

ViewSet de CRUD com paginação (configuração global), filtros via
django-filter e busca livre (SearchFilter). Apenas orquestração — nenhuma
lógica de negócio deve morar aqui.
"""
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Cliente
from .serializers import ClienteSerializer


class ClienteFilter(django_filters.FilterSet):
    """Filtros de clientes: nome/documento por trecho + campos exatos."""

    nome = django_filters.CharFilter(field_name="nome", lookup_expr="icontains")
    documento = django_filters.CharFilter(
        field_name="documento", lookup_expr="icontains"
    )

    class Meta:
        model = Cliente
        fields = ("nome", "documento", "papel", "tipo_pessoa", "ativo")


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_class = ClienteFilter
    search_fields = ("nome", "documento", "email", "telefone")