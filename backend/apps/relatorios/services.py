"""Camada de services do app Relatorios."""
from decimal import Decimal
from django.db.models import Sum
from apps.faturamento.models import Fatura, StatusFatura, TipoFatura


def gerar_fluxo_caixa(inicio=None, fim=None) -> dict:
    """Calcula o resumo financeiro (entradas, saídas e saldos) para um período."""
    qs = Fatura.objects.exclude(status=StatusFatura.CANCELADA)
    if inicio:
        qs = qs.filter(vencimento__gte=inicio)
    if fim:
        qs = qs.filter(vencimento__lte=fim)

    def _somar(tipo: str, status=None) -> Decimal:
        sub_qs = qs.filter(tipo=tipo)
        if status:
            sub_qs = sub_qs.filter(status=status)
        return sub_qs.aggregate(total=Sum("valor"))["total"] or Decimal("0.00")

    total_a_receber = _somar(TipoFatura.A_RECEBER)
    total_a_pagar = _somar(TipoFatura.A_PAGAR)
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