"""Camada de services do app Relatorios."""
from decimal import Decimal
from django.db.models import Sum
from apps.faturamento.models import Fatura, StatusFatura, TipoFatura


def gerar_fluxo_caixa(inicio=None, fim=None, owner=None) -> dict:
    """Calcula o resumo financeiro (entradas, saídas e saldos) para um período.

    Multi-tenancy: com owner informado, calcula apenas sobre as faturas do
    usuário — nunca sobre todos os dados do banco.
    """
    qs = Fatura.objects.exclude(status=StatusFatura.CANCELADA)
    if owner is not None:
        qs = qs.filter(owner=owner)
    if inicio:
        qs = qs.filter(vencimento__gte=inicio)
    if fim:
        qs = qs.filter(vencimento__lte=fim)

    def _somar(tipo: str, status=None) -> Decimal:
        sub_qs = qs.filter(tipo=tipo)
        if status:
            # status pode ser um valor único ou uma lista (usa __in).
            lookup = "status__in" if isinstance(status, (list, tuple)) else "status"
            sub_qs = sub_qs.filter(**{lookup: status})
        return sub_qs.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    # "A receber"/"a pagar" = faturas EM ABERTO: pendentes e vencidas.
    # O valor cai conforme as faturas são pagas, espelhando o aumento de
    # "recebido"/"pago". Vencidas continuam em aberto (a task periódica
    # marcar_faturas_vencidas() move pendente -> vencida; se ficassem de
    # fora, a fatura atrasada simplesmente desapareceria do dashboard).
    _em_aberto = [StatusFatura.PENDENTE, StatusFatura.VENCIDA]
    total_a_receber = _somar(TipoFatura.A_RECEBER, status=_em_aberto)
    total_a_pagar = _somar(TipoFatura.A_PAGAR, status=_em_aberto)
    total_recebido = _somar(TipoFatura.A_RECEBER, status=StatusFatura.PAGA)
    total_pago = _somar(TipoFatura.A_PAGAR, status=StatusFatura.PAGA)

    return {
        "periodo": {
            "inicio": str(inicio) if inicio else None,
            "fim": str(fim) if fim else None,
        },
        "total_a_receber": total_a_receber,
        "total_a_pagar": total_a_pagar,
        "total_recebido": total_recebido,
        "total_pago": total_pago,
        "saldo_previsto": total_a_receber - total_a_pagar,
        "saldo_realizado": total_recebido - total_pago,
    }