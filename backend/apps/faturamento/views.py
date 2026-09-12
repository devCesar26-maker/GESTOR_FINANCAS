"""Views e ViewSets do app Faturamento."""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from . import services
from .models import CobrancaRecorrente, Fatura
from .serializers import CobrancaRecorrenteSerializer, FaturaSerializer


class FaturaViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD e ações de faturas."""

    serializer_class = FaturaSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["cliente", "tipo", "status"]
    search_fields = ["numero", "descricao"]
    ordering_fields = ["vencimento", "valor", "created_at"]

    def get_queryset(self):
        """Multi-tenancy: vale para todas as actions, inclusive pagar/cancelar."""
        return Fatura.objects.select_related("cliente").filter(
            owner=self.request.user
        )

    def perform_create(self, serializer):
        """Owner é sempre o usuário autenticado — nunca vem do payload."""
        serializer.save(owner=self.request.user)

    @action(detail=True, methods=["post"])
    def pagar(self, request, pk=None):
        """Action POST /api/faturas/{id}/pagar/."""
        fatura = self.get_object()
        fatura_paga = services.pagar_fatura(fatura)
        return Response(self.get_serializer(fatura_paga).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def cancelar(self, request, pk=None):
        """Action POST /api/faturas/{id}/cancelar/."""
        fatura = self.get_object()
        fatura_cancelada = services.cancelar_fatura(fatura)
        return Response(self.get_serializer(fatura_cancelada).data, status=status.HTTP_200_OK)


class CobrancaRecorrenteViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD de cobranças recorrentes."""

    serializer_class = CobrancaRecorrenteSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["cliente", "tipo", "periodicidade", "ativa"]
    search_fields = ["descricao"]
    ordering_fields = ["proxima_cobranca", "valor", "created_at"]

    def get_queryset(self):
        """Multi-tenancy: cada usuário acessa apenas suas cobranças."""
        return CobrancaRecorrente.objects.select_related("cliente").filter(
            owner=self.request.user
        )

    def perform_create(self, serializer):
        """Owner é sempre o usuário autenticado — nunca vem do payload."""
        serializer.save(owner=self.request.user)