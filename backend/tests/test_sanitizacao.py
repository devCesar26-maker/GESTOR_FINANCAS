"""Testes de sanitização (strip de tags HTML) nos serializers.

A regra de XSS continua sendo "guardar texto puro, escapar na saída" —
agora com sanitização ativa na entrada: tags são REMOVIDAS dos campos de
texto antes de salvar (documento/e-mail obrigatórios são validados depois
da limpeza, então marcação no e-mail vira 400, não texto com tags).
"""

import pytest
from rest_framework import status

from apps.clientes.models import Cliente, Papel, TipoPessoa

CLIENTES_URL = "/api/clientes/"
FATURAS_URL = "/api/faturas/"

CPF_VALIDO = "529.982.247-25"
PAYLOAD_XSS = "<script>alert(1)</script>"


def payload_cliente(**kwargs):
    dados = {
        "nome": "Maria Silva",
        "papel": Papel.CLIENTE,
        "tipo_pessoa": TipoPessoa.FISICA,
        "documento": CPF_VALIDO,
        "email": "maria@example.com",
        "telefone": "(11) 99999-0000",
        "ativo": True,
    }
    dados.update(kwargs)
    return dados


@pytest.mark.django_db
def test_cliente_documento_e_email_obrigatorios(auth_client):
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(documento="", email=""), format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "documento" in response.data
    assert "email" in response.data


@pytest.mark.django_db
def test_cliente_sem_documento_rejeitado(auth_client):
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(documento=None), format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "documento" in response.data


@pytest.mark.django_db
def test_telefone_continua_opcional(auth_client):
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(telefone=""), format="json"
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["telefone"] == ""


@pytest.mark.django_db
def test_nome_com_tags_e_sanitizado(auth_client):
    response = auth_client.post(
        CLIENTES_URL,
        payload_cliente(nome=f"  {PAYLOAD_XSS} Maria  "),
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nome"] == "alert(1) Maria"


@pytest.mark.django_db
def test_email_com_tags_e_sanitizado_e_validado(auth_client):
    """Tags removidas; o resultado precisa ser um e-mail válido."""
    response = auth_client.post(
        CLIENTES_URL,
        payload_cliente(email="<b>maria</b>@example.com"),
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["email"] == "maria@example.com"


@pytest.mark.django_db
def test_telefone_com_tags_e_sanitizado(auth_client):
    response = auth_client.post(
        CLIENTES_URL,
        payload_cliente(telefone="(11) <i>99999</i>-0000"),
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["telefone"] == "(11) 99999-0000"


@pytest.mark.django_db
def test_nome_somente_tags_rejeitado(auth_client):
    """Nome que vira string vazia após sanitização → 400."""
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(nome="   "), format="json"
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "nome" in response.data


@pytest.mark.django_db
def test_tags_ofuscadas_com_entidades_e_removidas(auth_client):
    """&lt;script&gt; decodificado e removido (loop de sanitização)."""
    response = auth_client.post(
        CLIENTES_URL,
        payload_cliente(nome="&lt;script&gt;x&lt;/script&gt;Ana"),
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nome"] == "xAna"


@pytest.mark.django_db
def test_fatura_descricao_e_numero_sanitizados(auth_client, user):
    cliente = Cliente.objects.create(
        nome="Ana",
        tipo_pessoa=TipoPessoa.FISICA,
        documento=CPF_VALIDO,
        email="ana@example.com",
        owner=user,
    )
    response = auth_client.post(
        FATURAS_URL,
        {
            "numero": f"<b>FT</b>-XSS-9",
            "cliente": cliente.pk,
            "descricao": f"{PAYLOAD_XSS} Consultoria",
            "valor": "100.00",
            "vencimento": "2026-09-30",
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["numero"] == "FT-XSS-9"
    assert response.data["descricao"] == "alert(1) Consultoria"
