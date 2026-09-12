"""Camada de views do app Clientes."""
import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Cliente
from .serializers import ClienteDetailSerializer, ClienteListSerializer


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
    filter_backends = (DjangoFilterBackend, filters.SearchFilter)
    filterset_class = ClienteFilter
    search_fields = ("nome", "documento", "email", "telefone")

    def get_queryset(self):
        """Multi-tenancy: cada usuário acessa apenas seus clientes/fornecedores.

        Vale para todas as actions (list, retrieve, update, destroy), pois
        get_object() consulta este queryset — registro de outro usuário => 404.
        """
        return Cliente.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        """Owner é sempre o usuário autenticado — nunca vem do payload."""
        serializer.save(owner=self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return ClienteListSerializer
        return ClienteDetailSerializer