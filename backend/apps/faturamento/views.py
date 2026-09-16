"""Views e ViewSets do app Faturamento."""
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from . import services
from .models import CobrancaRecorrente, Fatura
from .serializers import CobrancaRecorrenteSerializer, FaturaSerializer


# Tipos MIME aceitos para o comprovante de pagamento (regra de negócio).
_COMPROVANTE_MIMES_PERMITIDOS = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def _validar_arquivo(comprovante: UploadedFile) -> str | None:
    """Valida o comprovante de pagamento. Retorna mensagem de erro ou None.

    Regras: apenas PDF, JPEG, PNG e WEBP, com no máximo 5MB. Checa o MIME
    reportado pelo upload E a assinatura binária (magic bytes) — o MIME do
    cliente é manipulável, a assinatura não (para esses formatos).
    """
    mime = (comprovante.content_type or "").lower().split(";")[0].strip()
    if mime not in _COMPROVANTE_MIMES_PERMITIDOS:
        return (
            "Tipo de arquivo não permitido. Envie um comprovante em PDF, "
            "JPEG, PNG ou WEBP."
        )

    limite = getattr(settings, "COMPROVANTE_MAX_BYTES", 5 * 1024 * 1024)
    if comprovante.size > limite:
        mb = limite / (1024 * 1024)
        return f"O comprovante excede o tamanho máximo de {mb:g} MB."

    # Assinatura binária (magic bytes) — defesa em profundidade contra
    # extensão/MIME falsificado no cliente. Verificação ESTRITA: o conteúdo
    # precisa bater com o MIME declarado, senão é rejeitado.
    cabecalho = comprovante.read(16)
    comprovante.seek(0)
    if mime == "image/webp":
        # WEBP: container RIFF com "WEBP" nos bytes 8-11.
        conteudo_valido = cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP"
    else:
        assinaturas = {
            "application/pdf": (b"%PDF",),
            "image/jpeg": (b"\xff\xd8\xff",),
            "image/png": (b"\x89PNG\r\n\x1a\n",),
        }
        prefixos = assinaturas.get(mime, ())
        conteudo_valido = bool(prefixos) and cabecalho.startswith(prefixos)
    if not conteudo_valido:
        return (
            "O conteúdo do arquivo não corresponde ao tipo informado. Envie um "
            "comprovante válido em PDF, JPEG, PNG ou WEBP."
        )
    return None


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

    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def pagar(self, request, pk=None):
        """Action POST /api/faturas/{id}/pagar/ (multipart/form-data).

        O COMPROVANTE DE PAGAMENTO É OBRIGATÓRIO: sem o arquivo, a request
        é rejeitada com 400 antes de qualquer mutação. Tipos aceitos:
        PDF, JPEG, PNG e WEBP, com até 5MB (ver _validar_arquivo).
        """
        fatura = self.get_object()

        comprovante = request.FILES.get("comprovante")
        if comprovante is None:
            return Response(
                {"comprovante": ["O comprovante de pagamento é obrigatório."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        erro = _validar_arquivo(comprovante)
        if erro:
            return Response(
                {"comprovante": [erro]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            fatura_paga = services.pagar_fatura(fatura, comprovante=comprovante)
        except services.FaturaEstadoInvalidoError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
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