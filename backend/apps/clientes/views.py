"""Camada de views do app Clientes."""
import logging

import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, viewsets

from .models import Cliente, Papel
from .serializers import ClienteDetailSerializer, ClienteListSerializer

logger = logging.getLogger(__name__)


class ClienteFilter(django_filters.FilterSet):
    """Filtros de clientes: nome/documento por trecho + campos exatos.

    O filtro `papel` é SEMÂNTICO: um cliente registrado com papel="ambos"
    aparece tanto em ?papel=cliente quanto em ?papel=fornecedor (ele exerce
    os dois papéis). ?papel=ambos traz apenas quem foi registrado com esse
    valor; qualquer outro valor não reconhecido devolve lista vazia.
    """

    nome = django_filters.CharFilter(field_name="nome", lookup_expr="icontains")
    documento = django_filters.CharFilter(
        field_name="documento", lookup_expr="icontains"
    )
    papel = django_filters.CharFilter(method="filtrar_papel")

    def filtrar_papel(self, queryset, name, value):
        value = (value or "").strip().lower()
        if not value:
            return queryset
        if value == Papel.AMBOS:
            return queryset.filter(papel=Papel.AMBOS)
        if value in (Papel.CLIENTE, Papel.FORNECEDOR):
            return queryset.filter(papel__in=[value, Papel.AMBOS])
        # Valor inválido: mantém o comportamento do filtro exato anterior —
        # não existe cliente com esse papel, logo lista vazia.
        return queryset.none()

    class Meta:
        model = Cliente
        fields = ("nome", "documento", "tipo_pessoa", "ativo")


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