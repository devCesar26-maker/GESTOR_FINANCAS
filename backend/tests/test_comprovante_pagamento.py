"""Testes da regra de negócio: COMPROVANTE DE PAGAMENTO OBRIGATÓRIO.

Cobrem: rejeição sem arquivo (400), tipos aceitos/rejeitados (PDF, JPEG,
PNG, WEBP e inválidos), limite de 5MB, validação de conteúdo real
(magic bytes), vínculo do arquivo na fatura e comprovante_url na resposta.
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status

from apps.faturamento.models import Fatura, StatusFatura, TipoFatura

FATURAS_URL = "/api/faturas/"

PDF_BYTES = b"%PDF-1.4 conteudo de teste"
PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"0" * 16
JPG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 16


def comprovante(nome="comprovante.pdf", conteudo=PDF_BYTES, tipo="application/pdf"):
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


@pytest.fixture
def fatura_pendente(cliente, user):
    return Fatura.objects.create(
        numero="FAT-COMP-1",
        cliente=cliente,
        descricao="Serviço com comprovante",
        tipo=TipoFatura.A_RECEBER,
        valor="800.00",
        status=StatusFatura.PENDENTE,
        vencimento=timezone.localdate(),
        owner=user,
    )


# ---------------------------------------------------------------------------
# Comprovante obrigatório
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pagar_sem_comprovante_retorna_400(auth_client, fatura_pendente):
    response = auth_client.post(f"{FATURAS_URL}{fatura_pendente.id}/pagar/")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "comprovante" in response.data
    assert "obrigatório" in response.data["comprovante"][0]
    fatura_pendente.refresh_from_db()
    assert fatura_pendente.status == StatusFatura.PENDENTE
    assert not fatura_pendente.comprovante


@pytest.mark.django_db
def test_pagar_com_comprovante_retorna_200_e_vincula_arquivo(
    auth_client, fatura_pendente
):
    response = auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {"comprovante": comprovante()},
        format="multipart",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["status"] == StatusFatura.PAGA
    assert response.data["comprovante_url"]
    fatura_pendente.refresh_from_db()
    assert fatura_pendente.comprovante
    assert fatura_pendente.comprovante.name.startswith("comprovantes/")
    assert fatura_pendente.data_pagamento is not None


# ---------------------------------------------------------------------------
# Tipos de arquivo e tamanho
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nome,conteudo,tipo",
    [
        ("c.pdf", PDF_BYTES, "application/pdf"),
        ("c.jpg", JPG_BYTES, "image/jpeg"),
        ("c.png", PNG_BYTES, "image/png"),
        ("c.webp", b"RIFF\x00\x00\x00\x00WEBPVP8 ", "image/webp"),
    ],
)
@pytest.mark.django_db
def test_pagar_aceita_tipos_permitidos(
    auth_client, fatura_pendente, nome, conteudo, tipo
):
    response = auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {"comprovante": comprovante(nome, conteudo, tipo)},
        format="multipart",
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_pagar_rejeita_tipo_nao_permitido(auth_client, fatura_pendente):
    response = auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {
            "comprovante": comprovante(
                "arquivo.txt", b"texto simples", "text/plain"
            )
        },
        format="multipart",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Tipo de arquivo não permitido" in response.data["comprovante"][0]


@pytest.mark.django_db
def test_pagar_rejeita_arquivo_acima_de_5mb(auth_client, fatura_pendente):
    grande = comprovante("grande.pdf", b"%PDF-1.4 " + b"0" * (5 * 1024 * 1024))
    response = auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {"comprovante": grande},
        format="multipart",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "5 MB" in response.data["comprovante"][0]


@pytest.mark.django_db
def test_pagar_rejeita_conteudo_falsificado(auth_client, fatura_pendente):
    """MIME declarado como PDF, mas conteúdo não é PDF → 400."""
    response = auth_client.post(
        f"{FATURAS_URL}{fatura_pendente.id}/pagar/",
        {
            "comprovante": comprovante(
                "falso.pdf", b"NAO E UM PDF", "application/pdf"
            )
        },
        format="multipart",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "não corresponde" in response.data["comprovante"][0]


# ---------------------------------------------------------------------------
# Multi-tenancy da action
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_pagar_fatura_de_outro_owner_retorna_404(user):
    from rest_framework.test import APIClient

    from apps.clientes.models import Cliente, Papel, TipoPessoa

    outro_user = type(user).objects.create_user(
        username="outro", email="outro@finflow.com", password="senha-outro-123"
    )
    cliente_dele = Cliente.objects.create(
        nome="Cliente do Outro",
        papel=Papel.CLIENTE,
        tipo_pessoa=TipoPessoa.JURIDICA,
        documento="11.222.333/0001-81",
        email="cliente@outro.com",
        owner=outro_user,
    )
    fatura_dele = Fatura.objects.create(
        numero="FAT-OUTRO-1",
        cliente=cliente_dele,
        valor="100.00",
        vencimento=timezone.localdate(),
        owner=outro_user,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    response = client.post(
        f"{FATURAS_URL}{fatura_dele.id}/pagar/",
        {"comprovante": comprovante()},
        format="multipart",
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    fatura_dele.refresh_from_db()
    assert fatura_dele.status == StatusFatura.PENDENTE
