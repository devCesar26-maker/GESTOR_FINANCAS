"""Testes da semântica das métricas de fluxo de caixa.

Comportamento esperado (regra de negócio):
- "Total a Receber"/"Total a Pagar" somam APENAS faturas PENDENTES —
  o valor DIMINUI conforme as faturas são pagas.
- "Total Recebido"/"Total Pago" somam APENAS faturas PAGAS —
  o valor AUMENTA conforme as faturas são pagas.
"""

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.faturamento.models import Fatura, StatusFatura, TipoFatura
from apps.faturamento import services as faturamento_services
from apps.relatorios import services


def _criar_fatura(numero, cliente, user, tipo, valor):
    return Fatura.objects.create(
        numero=numero,
        cliente=cliente,
        tipo=tipo,
        valor=Decimal(valor),
        status=StatusFatura.PENDENTE,
        vencimento=timezone.localdate(),
        owner=user,
    )


def _pagar(fatura):
    """Paga pela API de serviço real (comprovante é obrigatório)."""
    comprovante = SimpleUploadedFile("comp.pdf", b"%PDF-1.4\n%teste\n", content_type="application/pdf")
    faturamento_services.pagar_fatura(fatura, comprovante=comprovante)


@pytest.mark.django_db
def test_total_a_receber_diminui_ao_receber(user, cliente, fatura):
    """Duas a_receber pendentes; ao pagar uma, 'a receber' cai e 'recebido' sobe."""
    _criar_fatura("FT-2026-0002", cliente, user, TipoFatura.A_RECEBER, "250.00")

    antes = services.gerar_fluxo_caixa(owner=user)
    assert antes["total_a_receber"] == Decimal("1750.00")  # 1500 (fixture) + 250
    assert antes["total_recebido"] == Decimal("0.00")

    _pagar(fatura)  # paga a fatura de 1500.00

    depois = services.gerar_fluxo_caixa(owner=user)
    assert depois["total_a_receber"] == Decimal("250.00")  # caiu 1500.00
    assert depois["total_recebido"] == Decimal("1500.00")  # subiu 1500.00


@pytest.mark.django_db
def test_total_a_pagar_diminui_ao_pagar(user, cliente, fatura):
    """Mesma lógica simétrica para contas a pagar."""
    fatura_pagar = _criar_fatura("FT-2026-0003", cliente, user, TipoFatura.A_PAGAR, "400.00")
    _criar_fatura("FT-2026-0004", cliente, user, TipoFatura.A_PAGAR, "100.00")

    antes = services.gerar_fluxo_caixa(owner=user)
    assert antes["total_a_pagar"] == Decimal("500.00")
    assert antes["total_pago"] == Decimal("0.00")

    _pagar(fatura_pagar)  # paga a de 400.00

    depois = services.gerar_fluxo_caixa(owner=user)
    assert depois["total_a_pagar"] == Decimal("100.00")  # caiu 400.00
    assert depois["total_pago"] == Decimal("400.00")  # subiu 400.00


@pytest.mark.django_db
def test_vencida_continua_em_aberto(user, cliente, fatura):
    """Vencida não foi quitada: segue somando em 'a receber', não em 'recebido'."""
    Fatura.objects.filter(pk=fatura.pk).update(status=StatusFatura.VENCIDA)

    dados = services.gerar_fluxo_caixa(owner=user)
    assert dados["total_a_receber"] == Decimal("1500.00")
    assert dados["total_recebido"] == Decimal("0.00")


@pytest.mark.django_db
def test_cancelada_nao_conta_em_nenhuma_metrica(user, cliente, fatura):
    """Cancelada sai de ambos os lados do fluxo."""
    Fatura.objects.filter(pk=fatura.pk).update(status=StatusFatura.CANCELADA)

    dados = services.gerar_fluxo_caixa(owner=user)
    assert dados["total_a_receber"] == Decimal("0.00")
    assert dados["total_recebido"] == Decimal("0.00")
