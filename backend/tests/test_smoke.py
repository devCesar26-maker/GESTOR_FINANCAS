"""
Testes smoke do scaffold: validam que os models criam corretamente e que
as constraints básicas estão ativas. As regras de negócio (services) e os
endpoints terão cobertura dedicada app a app nas próximas etapas.
"""
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.clientes.models import Cliente, Papel, TipoPessoa
from apps.faturamento.models import (
    CobrancaRecorrente,
    Fatura,
    Periodicidade,
    StatusFatura,
)


@pytest.mark.django_db
def test_criar_cliente(cliente):
    assert cliente.pk is not None
    assert cliente.papel == Papel.CLIENTE
    assert cliente.tipo_pessoa == TipoPessoa.JURIDICA
    assert str(cliente) == cliente.nome


@pytest.mark.django_db
def test_documento_cliente_e_unico(user):
    Cliente.objects.create(nome="Empresa A", documento="12.345.678/0001-90", owner=user)
    with pytest.raises(Exception):
        Cliente.objects.create(nome="Empresa B", documento="12.345.678/0001-90", owner=user)


@pytest.mark.django_db
def test_criar_fatura(fatura):
    assert fatura.pk is not None
    assert fatura.status == StatusFatura.PENDENTE
    # DecimalField converte o valor ao ler do banco
    fatura_db = Fatura.objects.get(pk=fatura.pk)
    assert fatura_db.valor == Decimal("1500.00")
    assert "FT-2026-0001" in str(fatura)


@pytest.mark.django_db
def test_fatura_nao_aceita_valor_negativo(cliente):
    with pytest.raises(ValidationError):
        Fatura(
            numero="FT-2026-0002",
            cliente=cliente,
            valor="-10.00",
            vencimento="2026-10-01",
        ).full_clean()


@pytest.mark.django_db
def test_criar_cobranca_recorrente(cliente, user):
    cobranca = CobrancaRecorrente.objects.create(
        cliente=cliente,
        descricao="Mensalidade",
        valor="250.00",
        periodicidade=Periodicidade.MENSAL,
        dia_vencimento=10,
        proxima_cobranca="2026-10-10",
        owner=user,
    )
    assert cobranca.ativa is True
    assert cobranca.dia_vencimento == 10


@pytest.mark.django_db
def test_cobranca_rejeita_dia_vencimento_invalido(cliente):
    with pytest.raises(ValidationError):
        CobrancaRecorrente(
            cliente=cliente,
            descricao="Mensalidade",
            periodicidade=Periodicidade.MENSAL,
            dia_vencimento=32,
            proxima_cobranca="2026-10-10",
        ).full_clean()