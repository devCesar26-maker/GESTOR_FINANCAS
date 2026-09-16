"""Testes do app Faturamento e Relatórios."""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status

from apps.faturamento.exceptions import FaturaEstadoInvalidoError
from apps.faturamento.models import CobrancaRecorrente, Fatura, Periodicidade, StatusFatura, TipoFatura
from apps.faturamento import services

FATURAS_URL = "/api/faturas/"
COBRANCAS_URL = "/api/cobrancas-recorrentes/"
FLUXO_CAIXA_URL = "/api/relatorios/fluxo-caixa/"

def comprovante_pdf():
    """Novo arquivo a cada chamada (SimpleUploadedFile é consumido ao enviar)."""
    return SimpleUploadedFile(
        "comprovante.pdf", b"%PDF-1.4 teste", content_type="application/pdf"
    )


@pytest.fixture
def fatura_pendente(cliente, user):
    return Fatura.objects.create(
        numero="FAT-001",
        cliente=cliente,
        descricao="Serviço TI",
        tipo=TipoFatura.A_RECEBER,
        valor=Decimal("1000.00"),
        status=StatusFatura.PENDENTE,
        vencimento=timezone.localdate(),
        owner=user,
    )


@pytest.fixture
def cobranca_recorrente(cliente, user):
    return CobrancaRecorrente.objects.create(
        cliente=cliente,
        descricao="Assinatura Mensal",
        tipo=TipoFatura.A_RECEBER,
        valor=Decimal("200.00"),
        periodicidade=Periodicidade.MENSAL,
        dia_vencimento=10,
        proxima_cobranca=timezone.localdate(),
        ativa=True,
        owner=user,
    )


# ---------------------------------------------------------------------------
# Testes de Services Isolados
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_service_pagar_fatura_sucesso(fatura_pendente):
    res = services.pagar_fatura(fatura_pendente, comprovante=comprovante_pdf())
    assert res.status == StatusFatura.PAGA
    assert res.data_pagamento is not None
    assert res.comprovante is not None


@pytest.mark.django_db
def test_service_pagar_fatura_ja_paga_erro(fatura_pendente):
    services.pagar_fatura(fatura_pendente, comprovante=comprovante_pdf())
    with pytest.raises(FaturaEstadoInvalidoError):
        services.pagar_fatura(fatura_pendente, comprovante=comprovante_pdf())


@pytest.mark.django_db
def test_service_pagar_fatura_cancelada_erro(fatura_pendente):
    services.cancelar_fatura(fatura_pendente)
    with pytest.raises(FaturaEstadoInvalidoError):
        services.pagar_fatura(fatura_pendente, comprovante=comprovante_pdf())


@pytest.mark.django_db
def test_service_pagar_fatura_exige_comprovante(fatura_pendente):
    """Chamar o serviço sem comprovante levanta ValueError (dupla camada)."""
    with pytest.raises(ValueError):
        services.pagar_fatura(fatura_pendente)


@pytest.mark.django_db
def test_service_cancelar_fatura_sucesso(fatura_pendente):
    res = services.cancelar_fatura(fatura_pendente)
    assert res.status == StatusFatura.CANCELADA


@pytest.mark.django_db
def test_service_cancelar_fatura_ja_paga_erro(fatura_pendente):
    services.pagar_fatura(fatura_pendente, comprovante=comprovante_pdf())
    with pytest.raises(FaturaEstadoInvalidoError):
        services.cancelar_fatura(fatura_pendente)


@pytest.mark.django_db
def test_service_marcar_faturas_vencidas(cliente, user):
    ontem = timezone.localdate() - timedelta(days=1)
    Fatura.objects.create(
        numero="FAT-VENCIDA",
        cliente=cliente,
        valor=Decimal("500.00"),
        status=StatusFatura.PENDENTE,
        vencimento=ontem,
        owner=user,
    )
    qtd = services.marcar_faturas_vencidas()
    assert qtd == 1
    assert Fatura.objects.get(numero="FAT-VENCIDA").status == StatusFatura.VENCIDA


@pytest.mark.django_db
def test_service_processar_cobrancas_recorrentes_e_idempotencia(cobranca_recorrente):
    faturas = services.processar_cobrancas_recorrentes()
    assert len(faturas) == 1
    assert faturas[0].valor == Decimal("200.00")

    # Segunda execução no mesmo dia não deve criar nova fatura (idempotente)
    faturas_repetidas = services.processar_cobrancas_recorrentes()
    assert len(faturas_repetidas) == 0


# ---------------------------------------------------------------------------
# Testes de Endpoints DRF
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_fatura_endpoint(auth_client, cliente):
    payload = {
        "numero": "FAT-API-1",
        "cliente": cliente.id,
        "descricao": "Venda de equipamento",
        "tipo": TipoFatura.A_RECEBER,
        "valor": "3000.00",
        "vencimento": str(timezone.localdate()),
    }
    response = auth_client.post(FATURAS_URL, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["status"] == StatusFatura.PENDENTE


@pytest.mark.django_db
def test_status_read_only_no_patch(auth_client, fatura_pendente):
    # Tentar mudar status diretamente por PATCH deve ser ignorado
    response = auth_client.patch(
        f"{FATURAS_URL}{fatura_pendente.id}/",
        {"status": StatusFatura.PAGA},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    fatura_pendente.refresh_from_db()
    assert fatura_pendente.status == StatusFatura.PENDENTE


@pytest.mark.django_db
def test_endpoint_pagar_fatura_sucesso(auth_client, fatura_pendente):
    response = auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {"comprovante": comprovante_pdf()},
        format="multipart",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == StatusFatura.PAGA
    fatura_pendente.refresh_from_db()
    assert fatura_pendente.comprovante  # comprovante ficou vinculado


@pytest.mark.django_db
def test_endpoint_pagar_sem_comprovante_rejeitado_400(auth_client, fatura_pendente):
    """Regra de negócio: o comprovante de pagamento é OBRIGATÓRIO."""
    response = auth_client.post(f"{FATURAS_URL}{fatura_pendente.id}/pagar/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "comprovante" in response.data
    fatura_pendente.refresh_from_db()
    assert fatura_pendente.status == StatusFatura.PENDENTE


@pytest.mark.django_db
def test_endpoint_pagar_conflito_409_mesmo_com_comprovante(auth_client, fatura_pendente):
    """Fatura paga: o erro passa a ser 409 (estado), mesmo com comprovante válido."""
    auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {"comprovante": comprovante_pdf()},
        format="multipart",
    )
    response = auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {"comprovante": comprovante_pdf()},
        format="multipart",
    )
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_endpoint_cancelar_fatura_sucesso(auth_client, fatura_pendente):
    response = auth_client.post(f"{FATURAS_URL}{fatura_pendente.id}/cancelar/")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == StatusFatura.CANCELADA


@pytest.mark.django_db
def test_endpoint_cancelar_fatura_conflito_409(auth_client, fatura_pendente):
    auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {"comprovante": comprovante_pdf()},
        format="multipart",
    )
    # Cancelar fatura já paga -> 409 Conflict
    response = auth_client.post(f"{FATURAS_URL}{fatura_pendente.id}/cancelar/")
    assert response.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_crud_cobranca_recorrente(auth_client, cliente):
    payload = {
        "cliente": cliente.id,
        "descricao": "Manutenção",
        "tipo": TipoFatura.A_RECEBER,
        "valor": "500.00",
        "periodicidade": Periodicidade.MENSAL,
        "dia_vencimento": 5,
        "proxima_cobranca": str(timezone.localdate()),
        "ativa": True,
    }
    response = auth_client.post(COBRANCAS_URL, payload, format="json")
    assert response.status_code == status.HTTP_201_CREATED

    cob_id = response.data["id"]
    get_res = auth_client.get(f"{COBRANCAS_URL}{cob_id}/")
    assert get_res.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_endpoint_relatorio_fluxo_caixa(auth_client, user, cliente):
    Fatura.objects.create(
        numero="FAT-R1",
        cliente=cliente,
        tipo=TipoFatura.A_RECEBER,
        valor=Decimal("1000.00"),
        status=StatusFatura.PAGA,
        vencimento=timezone.localdate(),
        owner=user,
    )
    Fatura.objects.create(
        numero="FAT-P1",
        cliente=cliente,
        tipo=TipoFatura.A_PAGAR,
        valor=Decimal("400.00"),
        status=StatusFatura.PAGA,
        vencimento=timezone.localdate(),
        owner=user,
    )

    response = auth_client.get(FLUXO_CAIXA_URL)
    assert response.status_code == status.HTTP_200_OK
    assert Decimal(str(response.data["total_recebido"])) == Decimal("1000.00")
    assert Decimal(str(response.data["total_pago"])) == Decimal("400.00")
    assert Decimal(str(response.data["saldo_realizado"])) == Decimal("600.00")


# ---------------------------------------------------------------------------
# Testes de Autenticação (401)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_faturas_sem_autenticacao_retorna_401(api_client):
    response = api_client.get(FATURAS_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_relatorios_sem_autenticacao_retorna_401(api_client):
    response = api_client.get(FLUXO_CAIXA_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
