"""Views do app Relatorios."""
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services


class FluxoCaixaView(APIView):
    """Endpoint para geração do relatório de fluxo de caixa."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        inicio = request.query_params.get("inicio")
        fim = request.query_params.get("fim")
        dados = services.gerar_fluxo_caixa(inicio=inicio, fim=fim)
        return Response(dados, status=status.HTTP_200_OK)