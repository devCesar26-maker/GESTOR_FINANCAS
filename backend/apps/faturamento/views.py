"""Views e ViewSets do app Faturamento."""
import csv
from datetime import datetime

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters import rest_framework as df_filters
from django_filters.rest_framework import DjangoFilterBackend

from . import services
from .models import (
    CategoriaFinanceira,
    CobrancaRecorrente,
    Fatura,
    StatusFatura,
    TipoFatura,
)
from .serializers import (
    CategoriaFinanceiraSerializer,
    CobrancaRecorrenteSerializer,
    FaturaSerializer,
)


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


class FaturaFilter(df_filters.FilterSet):
    """Filtros avançados de faturas (todos via ORM do django-filter).

    Sem SQL bruta: django-filter monta lookups parameterizados. O intervalo
    de datas aceita ISO (AAAA-MM-DD); datas inválidas viram 400 do DRF.
    """

    vencimento_apos = df_filters.DateFilter(
        field_name="vencimento", lookup_expr="gte"
    )
    vencimento_ate = df_filters.DateFilter(
        field_name="vencimento", lookup_expr="lte"
    )
    # Busca textual por número ou descrição (ORM, sem raw SQL).
    busca = df_filters.CharFilter(method="filter_busca")

    class Meta:
        model = Fatura
        fields = ["cliente", "tipo", "status", "categoria"]

    def filter_busca(self, queryset, name, value):
        from django.db.models import Q

        return queryset.filter(
            Q(numero__icontains=value) | Q(descricao__icontains=value)
        )


class FaturaViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD e ações de faturas."""

    serializer_class = FaturaSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = FaturaFilter
    search_fields = ["numero", "descricao"]
    ordering_fields = ["vencimento", "valor", "created_at"]

    def get_queryset(self):
        """Multi-tenancy: vale para todas as actions, inclusive pagar/cancelar.

        select_related('cliente', 'categoria') elimina o N+1 em list/retrieve:
        uma única query busca faturas + cliente + categoria (JOIN no SQL).
        """
        return Fatura.objects.select_related("cliente", "categoria").filter(
            owner=self.request.user
        )

    def perform_create(self, serializer):
        """Owner é sempre o usuário autenticado — nunca vem do payload."""
        serializer.save(owner=self.request.user)

    def _fatura_editavel(self, fatura: Fatura) -> str | None:
        """Regra: faturas PAGAS são imutáveis (somente leitura).

        Vencidas também são bloqueadas para edição de dados (o status muda
        apenas pelas actions próprias pagar/cancelar). Retorna mensagem de
        erro ou None se editável.
        """
        if fatura.status == StatusFatura.PAGA:
            return "Faturas pagas não podem ser editadas."
        if fatura.status == StatusFatura.VENCIDA:
            return "Faturas vencidas não podem ser editadas. Cancele-as ou registre o pagamento."
        return None

    def update(self, request, *args, **kwargs):
        """PUT/PATCH bloqueado para faturas pagas (409 Conflict)."""
        fatura = self.get_object()
        erro = self._fatura_editavel(fatura)
        if erro:
            return Response({"detail": erro}, status=status.HTTP_409_CONFLICT)
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """PATCH bloqueado para faturas pagas (409 Conflict)."""
        fatura = self.get_object()
        erro = self._fatura_editavel(fatura)
        if erro:
            return Response({"detail": erro}, status=status.HTTP_409_CONFLICT)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """DELETE bloqueado para faturas pagas (409 Conflict)."""
        fatura = self.get_object()
        erro = self._fatura_editavel(fatura)
        if erro:
            return Response({"detail": erro}, status=status.HTTP_409_CONFLICT)
        return super().destroy(request, *args, **kwargs)

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


class CategoriaFinanceiraViewSet(viewsets.ModelViewSet):
    """CRUD do catálogo de categorias (centros de custo) do usuário."""

    serializer_class = CategoriaFinanceiraSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["nome"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self):
        """Multi-tenancy: cada usuário acessa apenas suas categorias."""
        return CategoriaFinanceira.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def list(self, request, *args, **kwargs):
        """Na primeira listagem, semeia o catálogo padrão (idempotente)."""
        if not CategoriaFinanceira.objects.filter(owner=request.user).exists():
            CategoriaFinanceira.criar_categorias_padrao(request.user)
        return super().list(request, *args, **kwargs)


class CobrancaRecorrenteViewSet(viewsets.ModelViewSet):
    """ViewSet para CRUD de cobranças recorrentes."""

    serializer_class = CobrancaRecorrenteSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["cliente", "tipo", "periodicidade", "ativa", "categoria"]
    search_fields = ["descricao"]
    ordering_fields = ["proxima_cobranca", "valor", "created_at"]

    def get_queryset(self):
        """Multi-tenancy: cada usuário acessa apenas suas cobranças."""
        return CobrancaRecorrente.objects.select_related("cliente", "categoria").filter(
            owner=self.request.user
        )

    def perform_create(self, serializer):
        """Owner é sempre o usuário autenticado — nunca vem do payload."""
        serializer.save(owner=self.request.user)


# ---------------------------------------------------------------------------
# Exportação de relatórios (CSV/Excel/PDF) — faturas e DRE simplificado
# ---------------------------------------------------------------------------


def _fmt_moeda(valor) -> str:
    """Formata Decimal como moeda BRL (sem dependências externas)."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _responder_csv(nome_arquivo: str, linhas: list[list], *, delimiter=";") -> HttpResponse:
    """Monta a resposta CSV com BOM UTF-8 (Excel abre acentos corretamente)."""
    resposta = HttpResponse(content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'
    escritor = csv.writer(resposta, delimiter=delimiter)
    escritor.writerows(linhas)
    return resposta


def _responder_pdf(nome_arquivo: str, titulo: str, linhas: list[list], *, paisagem: bool = False) -> HttpResponse:
    """PDF via_reportlab (dependência leve, sem binários de sistema).

    linhas: primeira lista é o cabeçalho, demais são dados. Última linha
    pode começar com ("__TOTAL__", ...) para sair em negrito.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    resposta = HttpResponse(content_type="application/pdf")
    resposta["Content-Disposition"] = f'attachment; filename="{nome_arquivo}"'

    pagesize = landscape(A4) if paisagem else A4
    doc = SimpleDocTemplate(
        resposta,
        pagesize=pagesize,
        topMargin=36,
        bottomMargin=36,
        leftMargin=36,
        rightMargin=36,
    )
    estilos = getSampleStyleSheet()
    elementos = [
        Paragraph(titulo, estilos["Title"]),
        Spacer(1, 6),
        Paragraph(
            f"Emitido em {datetime.now().strftime('%d/%m/%Y %H:%M')} — FinFlow",
            estilos["Normal"],
        ),
        Spacer(1, 12),
    ]

    if linhas:
        cabecalho = [str(c) for c in linhas[0]]
        corpo = []
        estilo_total_idx = []
        for i, linha in enumerate(linhas[1:], start=1):
            if linha and linha[0] == "__TOTAL__":
                estilo_total_idx.append(i)
                corpo.append([str(c) for c in linha[1:]])
            else:
                corpo.append([str(c) for c in linha])

        tabela = Table([cabecalho] + corpo, repeatRows=1)
        estilo = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f3d3e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5d1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f7f5")]),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        for idx in estilo_total_idx:
            estilo.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#e2efea")))
            estilo.append(("FONTNAME", (0, idx), (-1, idx), "Helvetica-Bold"))
        tabela.setStyle(TableStyle(estilo))
        elementos.append(tabela)
    else:
        elementos.append(Paragraph("Nenhum registro no período.", estilos["Normal"]))

    doc.build(elementos)
    return resposta


class FaturasExportView(APIView):
    """GET /api/faturas/exportar/?formato=csv|excel|pdf

    Exporta o EXTRATO de faturas do usuário, honrando os mesmos filtros do
    list endpoint (status, tipo, datas, cliente, categoria, busca, search).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        formato = (request.query_params.get("formato") or "csv").lower()

        queryset = (
            Fatura.objects.select_related("cliente", "categoria")
            .filter(owner=request.user)
            .order_by("vencimento", "numero")
        )
        filtro = FaturaFilter(
            data=request.query_params, queryset=queryset, request=request
        )
        queryset = filtro.qs
        busca = request.query_params.get("search")
        if busca:
            queryset = queryset.filter(
                Q(numero__icontains=busca) | Q(descricao__icontains=busca)
            )

        rotulo_status = dict(StatusFatura.choices)
        rotulo_tipo = dict(TipoFatura.choices)

        if formato == "pdf":
            linhas = [
                [
                    "Número", "Cliente/Fornecedor", "Categoria", "Tipo", "Status",
                    "Vencimento", "Valor", "Descrição",
                ]
            ]
            for f in queryset:
                linhas.append(
                    [
                        f.numero,
                        f.cliente.nome,
                        f.categoria.nome if f.categoria else "—",
                        rotulo_tipo.get(f.tipo, f.tipo),
                        rotulo_status.get(f.status, f.status),
                        f.vencimento.strftime("%d/%m/%Y"),
                        _fmt_moeda(f.valor),
                        f.descricao or "—",
                    ]
                )
            return _responder_pdf(
                "faturas.pdf", "Extrato de Faturas — FinFlow", linhas, paisagem=True
            )

        # CSV e Excel: mesmo formato (Excel abre CSV com BOM + ;).
        linhas = [
            [
                "Número", "Cliente/Fornecedor", "Categoria", "Tipo", "Status",
                "Vencimento", "Valor", "Descrição",
            ]
        ]
        for f in queryset:
            linhas.append(
                [
                    f.numero,
                    f.cliente.nome,
                    f.categoria.nome if f.categoria else "",
                    rotulo_tipo.get(f.tipo, f.tipo),
                    rotulo_status.get(f.status, f.status),
                    f.vencimento.strftime("%d/%m/%Y"),
                    str(f.valor),
                    f.descricao or "",
                ]
            )
        nome = "faturas.csv" if formato == "csv" else "faturas-excel.csv"
        return _responder_csv(nome, linhas)


class DreView(APIView):
    """GET /api/relatorios/dre/?inicio=&fim=

    DRE simplificado: receitas e despesas por categoria, com totais e
    resultado. Somente faturas efetivadas (pagas) entram no DRE.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        inicio = request.query_params.get("inicio")
        fim = request.query_params.get("fim")
        dados = services.gerar_dre(inicio=inicio, fim=fim, owner=request.user)
        return Response(dados, status=status.HTTP_200_OK)


class DreExportView(APIView):
    """GET /api/relatorios/dre/exportar/?formato=csv|excel|pdf&inicio=&fim="""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        formato = (request.query_params.get("formato") or "csv").lower()
        inicio = request.query_params.get("inicio")
        fim = request.query_params.get("fim")
        dados = services.gerar_dre(inicio=inicio, fim=fim, owner=request.user)

        periodo_titulo = (
            f"Período: {inicio} a {fim}" if inicio or fim else "Período: completo"
        )

        if formato == "pdf":
            linhas = [["Grupo", "Categoria", "Valor"]]
            for grupo, rotulo in (("receitas", "Receitas"), ("despesas", "Despesas (-)")):
                for item in dados[grupo]:
                    linhas.append([rotulo, item["categoria"], item["total"]])
            linhas.append(["__TOTAL__", "Receita Bruta Total", dados["total_receitas"]])
            linhas.append(["__TOTAL__", "(=) Resultado do Período", dados["resultado"]])
            return _responder_pdf(
                "dre.pdf", f"DRE Simplificado — FinFlow — {periodo_titulo}", linhas
            )

        linhas = [["Grupo", "Categoria", "Valor"]]
        for grupo, rotulo in (("receitas", "Receitas"), ("despesas", "Despesas (-)")):
            for item in dados[grupo]:
                linhas.append([rotulo, item["categoria"], str(item["total"])])
        linhas.append(["Total", "Receita Bruta Total", str(dados["total_receitas"])])
        linhas.append(["Total", "(-) Despesa Bruta Total", str(dados["total_despesas"])])
        linhas.append(["Total", "(=) Resultado do Período", str(dados["resultado"])])
        nome = "dre.csv" if formato == "csv" else "dre-excel.csv"
        return _responder_csv(nome, linhas)
