"""Camada de services do app Faturamento."""
from datetime import date, timedelta
import calendar
from django.db import transaction
from django.utils import timezone

from .exceptions import FaturaEstadoInvalidoError
from .models import CobrancaRecorrente, Fatura, Periodicidade, StatusFatura


def pagar_fatura(fatura: Fatura) -> Fatura:
    """Registra pagamento da fatura se estiver em estado válido."""
    if fatura.status == StatusFatura.PAGA:
        raise FaturaEstadoInvalidoError("A fatura já está paga.")
    if fatura.status == StatusFatura.CANCELADA:
        raise FaturaEstadoInvalidoError("Não é possível pagar uma fatura cancelada.")

    fatura.status = StatusFatura.PAGA
    fatura.data_pagamento = timezone.now()
    fatura.save(update_fields=["status", "data_pagamento", "updated_at"])
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


def marcar_faturas_vencidas() -> int:
    """Marca faturas pendentes com vencimento anterior a hoje como vencidas."""
    hoje = timezone.localdate()
    return Fatura.objects.filter(
        status=StatusFatura.PENDENTE,
        vencimento__lt=hoje
    ).update(status=StatusFatura.VENCIDA, updated_at=timezone.now())


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
def processar_cobrancas_recorrentes() -> list[Fatura]:
    """Gera faturas idempotentes para cobranças recorrentes devidas."""
    hoje = timezone.localdate()
    cobrancas = CobrancaRecorrente.objects.select_for_update().filter(
        ativa=True,
        proxima_cobranca__lte=hoje
    )

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