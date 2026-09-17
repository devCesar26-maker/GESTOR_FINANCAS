"""Regressão da validação de telefone do cliente (validate_telefone).

Telefone é opcional; quando informado, precisa ser DDD + 8 ou 9 dígitos
(10/11 no total), com ou sem máscara, ou com DDI 55 (12/13 dígitos).
Inválidos retornam 400 com mensagem clara.
"""

import pytest
from rest_framework import status

from apps.clientes.models import Papel, TipoPessoa

CLIENTES_URL = "/api/clientes/"

BASE = {
    "nome": "Cliente Telefone",
    "email": "telefone@x.com",
    "documento": "52998224725",
    "tipo_pessoa": "pf",
}


def payload(**overrides):
    dados = {**BASE}
    dados.update(overrides)
    return dados


# ---------------------------------------------------------------------------
# Válidos (201)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefone",
    [
        "(11) 98765-4321",
        "1134567890",
        "+55 21 98765-4321",
        "551134567890",
    ],
)
def test_telefones_validos_sao_aceitos(auth_client, telefone):
    response = auth_client.post(CLIENTES_URL, payload(telefone=telefone), format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["telefone"] == telefone


@pytest.mark.django_db
def test_telefone_vazio_continua_opcional(auth_client):
    response = auth_client.post(CLIENTES_URL, payload(telefone=""), format="json")
    assert response.status_code == status.HTTP_201_CREATED


# ---------------------------------------------------------------------------
# Inválidos (400)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "telefone",
    [
        "123",                       # curto demais
        "999999999",                 # 9 dígitos, sem DDD
        "119876543211234",           # longo demais
        "(11) 8000-0",               # 7 dígitos
    ],
)
def test_telefones_invalidos_retornam_400(auth_client, telefone):
    response = auth_client.post(CLIENTES_URL, payload(telefone=telefone), format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Telefone inválido" in response.data["telefone"][0]


@pytest.mark.django_db
def test_telefone_com_letras_retorna_400(auth_client):
    response = auth_client.post(CLIENTES_URL, payload(telefone="abc"), format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Edição
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_edicao_pode_limpar_telefone(auth_client, cliente):
    response = auth_client.patch(
        f"{CLIENTES_URL}{cliente.id}/", {"telefone": ""}, format="json"
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.data["telefone"] == ""
