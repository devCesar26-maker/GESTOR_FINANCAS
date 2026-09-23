"""Camada de services do app Faturamento."""
from datetime import date, timedelta
import calendar
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum
from django.template.loader import render_to_string
from django.utils import timezone

from .exceptions import FaturaEstadoInvalidoError
from .models import (
    CategoriaFinanceira,
    CobrancaRecorrente,
    Fatura,
    Periodicidade,
    StatusFatura,
    TipoFatura,
)

logger = logging.getLogger(__name__)


def pagar_fatura(fatura: Fatura, comprovante=None) -> Fatura:
    """Registra pagamento da fatura se estiver em estado válido.

    O comprovante de pagamento é OBRIGATÓRIO para registrar o pagamento.
    A exigência é aplicada em duas camadas: a view rejeita requests sem
    arquivo com 400 (antes de tocar no banco) e este serviço levanta
    ValueError caso seja chamado sem arquivo — nunca existe fatura paga
    sem comprovante vinculado.
    """
    if comprovante is None:
        raise ValueError("O comprovante de pagamento é obrigatório.")
    if fatura.status == StatusFatura.PAGA:
        raise FaturaEstadoInvalidoError("A fatura já está paga.")
    if fatura.status == StatusFatura.CANCELADA:
        raise FaturaEstadoInvalidoError("Não é possível pagar uma fatura cancelada.")

    fatura.status = StatusFatura.PAGA
    fatura.data_pagamento = timezone.now()
    fatura.comprovante = comprovante
    fatura.save(
        update_fields=["status", "data_pagamento", "comprovante", "updated_at"]
    )
    return fatura


def cancelar_fatura(fatura: Fatura) -> Fatura:
    """Cancela a fatura se estiver em estado válido."""
    if fatura.status == StatusFatura.PAGA:
        raise FaturaEstadoInvalidoError("Não é possível cancelar uma fatura já paga.")
    if fatura.status == StatusFatura.CANCELADA:
        raise FaturaEstadoInvalidoError("A fatura já está cancelada.")

    fatura.status = StatusFatura.CANCELADA
    fatura.save(update_fields=["status", "updated_at"])
    return fatura


def marcar_faturas_vencidas(owner=None) -> int:
    """Marca faturas pendentes com vencimento anterior a hoje como vencidas.

    Com owner informado, restringe ao usuário; sem owner, atua sobre todo o banco
    (comportamento da task agendada do Celery, que roda fora de um request).
    """
    hoje = timezone.localdate()
    qs = Fatura.objects.filter(status=StatusFatura.PENDENTE, vencimento__lt=hoje)
    if owner is not None:
        qs = qs.filter(owner=owner)
    return qs.update(status=StatusFatura.VENCIDA, updated_at=timezone.now())


def _calcular_proxima_data(data_ref: date, periodicidade: str, dia_vencimento: int) -> date:
    """Calcula a próxima data de cobrança com base na periodicidade."""
    if periodicidade == Periodicidade.SEMANAL:
        return data_ref + timedelta(days=7)
    elif periodicidade == Periodicidade.QUINZENAL:
        return data_ref + timedelta(days=15)
    
    # Para frequências mensais/anuais
    meses_adicionar = {
        Periodicidade.MENSAL: 1,
        Periodicidade.TRIMESTRAL: 3,
        Periodicidade.SEMESTRAL: 6,
        Periodicidade.ANUAL: 12,
    }.get(periodicidade, 1)

    ano = data_ref.year + (data_ref.month + meses_adicionar - 1) // 12
    mes = (data_ref.month + meses_adicionar - 1) % 12 + 1
    
    # Ajusta o dia para não exceder o último dia do mês
    max_dias = calendar.monthrange(ano, mes)[1]
    dia = min(dia_vencimento, max_dias)
    return date(ano, mes, dia)


@transaction.atomic
def processar_cobrancas_recorrentes(owner=None) -> list[Fatura]:
    """Gera faturas idempotentes para cobranças recorrentes devidas.

    Com owner informado, restringe ao usuário; sem owner, processa todo o banco
    (task agendada do Celery). A fatura gerada herda o dono da cobrança.
    """
    hoje = timezone.localdate()
    cobrancas = CobrancaRecorrente.objects.select_for_update(of=('self',)).select_related("cliente", "categoria", "owner").filter(
        ativa=True,
        proxima_cobranca__lte=hoje
    )
    if owner is not None:
        cobrancas = cobrancas.filter(owner=owner)

    faturas_criadas = []
    for cobranca in cobrancas:
        vencimento = cobranca.proxima_cobranca
        # Formato de número garantindo unicidade e idempotência
        sufixo_data = vencimento.strftime("%Y%m%d")
        numero = f"REC{cobranca.id}-{sufixo_data}"[:20]

        fatura, created = Fatura.objects.get_or_create(
            numero=numero,
            defaults={
                "cliente": cobranca.cliente,
                "descricao": cobranca.descricao,
                "tipo": cobranca.tipo,
                "valor": cobranca.valor,
                "vencimento": vencimento,
                "status": StatusFatura.PENDENTE,
                "categoria": cobranca.categoria,
                "owner": cobranca.owner,
            }
        )

        if created:
            faturas_criadas.append(fatura)

        # Atualiza a cobrança recorrente para o próximo ciclo
        cobranca.ultima_execucao = timezone.now()
        cobranca.proxima_cobranca = _calcular_proxima_data(
            vencimento, cobranca.periodicidade, cobranca.dia_vencimento
        )
        cobranca.save(update_fields=["ultima_execucao", "proxima_cobranca", "updated_at"])

    return faturas_criadas


# ---------------------------------------------------------------------------
# Categorização financeira: DRE simplificado e agrupamento por categoria
# ---------------------------------------------------------------------------


def _rotulo_categoria(categoria) -> str:
    """Rótulo da categoria nos relatórios; None vira "Sem categoria"."""
    return categoria.nome if categoria else "Sem categoria"


def _rotulo_categoria_id(categoria_id, nome) -> str:
    """Rótulo a partir do row da agregação (None = "Sem categoria")."""
    return nome if nome else "Sem categoria"


def gerar_dre(inicio=None, fim=None, owner=None) -> dict:
    """DRE simplificado: receitas e despesas (faturas pagas) por categoria.

    Somente faturas PAGAS entram no DRE (regime de caixa). Canceladas e
    pendentes/vencidas ficam de fora. Multi-tenancy: com owner, restrito ao
    usuário; agregação feita 100% via ORM (values + annotate/Sum).
    """
    qs = Fatura.objects.filter(status=StatusFatura.PAGA).select_related("categoria")
    if owner is not None:
        qs = qs.filter(owner=owner)
    if inicio:
        qs = qs.filter(vencimento__gte=inicio)
    if fim:
        qs = qs.filter(vencimento__lte=fim)

    # Duas agregações SQL (GROUP BY) via ORM — nenhuma query bruta.
    receitas = (
        qs.filter(tipo=TipoFatura.A_RECEBER)
        .values("categoria", "categoria__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )
    despesas = (
        qs.filter(tipo=TipoFatura.A_PAGAR)
        .values("categoria", "categoria__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    )

    receitas_lista = [
        {
            "categoria_id": linha["categoria"],
            "categoria": _rotulo_categoria_id(linha["categoria"], linha["categoria__nome"]),
            "total": linha["total"] or 0,
        }
        for linha in receitas
    ]
    despesas_lista = [
        {
            "categoria_id": linha["categoria"],
            "categoria": _rotulo_categoria_id(linha["categoria"], linha["categoria__nome"]),
            "total": linha["total"] or 0,
        }
        for linha in despesas
    ]

    total_receitas = sum((item["total"] for item in receitas_lista), start=0)
    total_despesas = sum((item["total"] for item in despesas_lista), start=0)

    return {
        "periodo": {
            "inicio": str(inicio) if inicio else None,
            "fim": str(fim) if fim else None,
        },
        "receitas": receitas_lista,
        "despesas": despesas_lista,
        "total_receitas": total_receitas,
        "total_despesas": total_despesas,
        "resultado": total_receitas - total_despesas,
    }


def resumo_por_categoria(inicio=None, fim=None, owner=None) -> dict:
    """Agregação de faturas (pagas) por categoria para o gráfico do Dashboard.

    Delega ao DRE e devolve a mesma forma consumida pelo frontend: grupos
    receitas/despesas com totais por categoria (ORM puro, sem N+1).
    """
    return gerar_dre(inicio=inicio, fim=fim, owner=owner)


# ---------------------------------------------------------------------------
# Lembretes de vencimento por e-mail (Fase 3)
# ---------------------------------------------------------------------------


def _assinatura_do_dono(fatura: Fatura) -> str:
    """Nome do usuário dono da fatura, usado como assinatura do e-mail."""
    dono = fatura.owner
    if dono is None:
        return ""
    return dono.get_full_name() or dono.get_username()


def _dados_pagamento() -> dict:
    """Dados de pagamento (PIX) incluídos nos lembretes, via settings.

    Sobrescrevível nos testes com ``override_settings``.
    """
    return getattr(settings, "DADOS_PAGAMENTO", {}) or {}


def _bloco_pagamento(fatura: Fatura) -> str:
    """Monta o bloco "Dados para pagamento" do corpo do e-mail.

    Inclui a chave PIX quando configurada (settings.DADOS_PAGAMENTO, via
    variáveis de ambiente FINFLOW_CHAVE_PIX/FINFLOW_FAVORECIDO_PIX); sem
    chave configurada, orienta o destinatário a solicitar os dados ao
    respondendo a mensagem.
    """
    dados = _dados_pagamento()
    chave_pix = (dados.get("chave_pix") or "").strip()
    favorecido = (dados.get("favorecido") or "").strip()

    linhas = ["Dados para pagamento:"]
    if chave_pix:
        linhas.append(f"  Chave PIX: {chave_pix}")
        if favorecido:
            linhas.append(f"  Favorecido: {favorecido}")
    else:
        linhas.append(
            "  A chave PIX e os dados bancários podem ser solicitados "
            "respondendo a este e-mail."
        )
    linhas.append(
        "  Após o pagamento, envie o comprovante por este canal ou "
        "pelo painel FinFlow."
    )
    return "\n".join(linhas)


def _enviar_lembrete(fatura: Fatura, *, dias_ate_vencimento: int) -> None:
    """Envia o e-mail do lembrete e grava a data de envio na fatura.

    A data só é gravada DEPOIS de um envio bem-sucedido — se o send falhar,
    a exceção propaga sem registro, e a próxima execução tenta de novo.

    Tom corporativo por janela da régua de vencimento:
      - 10 dias: lembrete preventivo amigável;
      - 5 e 1 dia(s): notificação formal de vencimento próximo;
      - 0 dias (vence hoje): aviso de vencimento com instrução clara de
        envio do comprovante.
    """
    vence_hoje = dias_ate_vencimento <= 0
    contexto = {
        "cliente_nome": fatura.cliente.nome,
        "numero": fatura.numero,
        "valor": fatura.valor,
        "vencimento": fatura.vencimento.strftime("%d/%m/%Y"),
        "descricao": fatura.descricao or "—",
        "dias": dias_ate_vencimento,
        "remetente": _assinatura_do_dono(fatura),
        "dados_pagamento": _bloco_pagamento(fatura),
    }
    if vence_hoje:
        assunto_tmpl = "faturamento/emails/lembrete_vencimento_assunto.txt"
        corpo_tmpl = "faturamento/emails/lembrete_vencimento.txt"
        campo = "lembrete_vencimento_enviado_em"
    elif dias_ate_vencimento >= 10:
        # Janela preventiva (10 dias): template amigável.
        assunto_tmpl = "faturamento/emails/lembrete_previo_assunto.txt"
        corpo_tmpl = "faturamento/emails/lembrete_previo.txt"
        campo = "lembrete_previo_enviado_em"
    else:
        # Janelas formais (5 e 1 dias): template de vencimento próximo.
        assunto_tmpl = "faturamento/emails/lembrete_proximo_assunto.txt"
        corpo_tmpl = "faturamento/emails/lembrete_proximo.txt"
        campo = "lembrete_previo_enviado_em"

    assunto = render_to_string(assunto_tmpl, contexto).strip()
    corpo = render_to_string(corpo_tmpl, contexto).strip()

    send_mail(
        subject=assunto,
        message=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[fatura.cliente.email],
        fail_silently=False,
    )

    setattr(fatura, campo, timezone.now())
    fatura.save(update_fields=[campo, "updated_at"])


# Janelas de disparo dos lembretes prévios, em dias antes do vencimento.
# A janela 0 (vencimento no dia) usa o campo/template próprios de "vence hoje".
LEMBRETES_JANELAS_DIAS = (10, 5, 1)


def enviar_lembretes_vencimento(owner=None, hoje=None) -> dict:
    """Envia lembretes de vencimento por e-mail (Fase 3 — janelas expandidas).

    Regras, todas exigindo fatura A_RECEBER, status PENDENTE, cliente com
    notificacoes_ativas=True e e-mail preenchido:

      a) vencimento em 10, 5 ou 1 dia(s) e lembrete_previo_enviado_em ainda
         None → aviso prévio daquela janela;
      b) vencimento hoje (0 dias) e lembrete_vencimento_enviado_em ainda
         None → aviso de vencimento no dia.

    Gravar a data só após o envio garante idempotência: rodar o job duas
    vezes no mesmo dia não duplica o e-mail — e cada janela envia uma única
    vez por fatura (10d, 5d, 1d e 0d são disparos distintos).

    Com owner informado, restringe ao usuário; sem owner, atua sobre todo
    o banco (comportamento da task agendada do Celery).
    """
    hoje = hoje or timezone.localdate()

    base = (
        Fatura.objects.filter(
            tipo=TipoFatura.A_RECEBER,
            status=StatusFatura.PENDENTE,
            cliente__notificacoes_ativas=True,
        )
        .exclude(cliente__email="")
        .select_related("cliente", "owner")
    )
    if owner is not None:
        base = base.filter(owner=owner)

    enviados_previos = 0
    enviados_hoje = 0
    falhas = 0

    # Janelas prévias: 10, 5 e 1 dia(s) antes do vencimento.
    for dias in LEMBRETES_JANELAS_DIAS:
        alvo = hoje + timedelta(days=dias)
        elegiveis = list(
            base.filter(
                vencimento=alvo, lembrete_previo_enviado_em__isnull=True
            )
        )
        for fatura in elegiveis:
            try:
                _enviar_lembrete(fatura, dias_ate_vencimento=dias)
                enviados_previos += 1
            except Exception:
                logger.exception(
                    "Falha ao enviar lembrete prévio (%d dias) da fatura %s",
                    dias,
                    fatura.numero,
                )
                falhas += 1

    # Janela 0: vencimento no dia de hoje.
    de_hoje = list(
        base.filter(vencimento=hoje, lembrete_vencimento_enviado_em__isnull=True)
    )
    for fatura in de_hoje:
        try:
            _enviar_lembrete(fatura, dias_ate_vencimento=0)
            enviados_hoje += 1
        except Exception:
            logger.exception(
                "Falha ao enviar lembrete de vencimento da fatura %s",
                fatura.numero,
            )
            falhas += 1

    return {
        "lembretes_previos_enviados": enviados_previos,
        "lembretes_vencimento_enviados": enviados_hoje,
        "falhas": falhas,
    }