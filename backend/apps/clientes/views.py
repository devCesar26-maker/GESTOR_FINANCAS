"""Camada de views do app Clientes."""
import logging

import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Cliente
from .serializers import ClienteDetailSerializer, ClienteListSerializer

logger = logging.getLogger(__name__)


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
        cliente = serializer.save(owner=self.request.user)

        # Notificação de cadastro ao cliente/fornecedor: e-mail ÚNICO e
        # informativo, independente de notificacoes_ativas (que controla
        # apenas os lembretes recorrentes de vencimento). Assíncrono (Celery)
        # e isolado — falha de broker/disparo NUNCA quebra a criação.
        try:
            from .tasks import task_enviar_email_cadastro_cliente

            task_enviar_email_cadastro_cliente.delay(cliente.pk)
        except Exception:
            logger.exception(
                "Falha ao disparar notificação de cadastro do cliente %s",
                cliente.pk,
            )

    def get_serializer_class(self):
        if self.action == "list":
            return ClienteListSerializer
        return ClienteDetailSerializer