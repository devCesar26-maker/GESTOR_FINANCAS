"""
Testes da política de senha forte (registro) e sua exclusividade.

A validação de força vale APENAS na criação de conta via API de registro.
O login (JWT /api/token/) NUNCA revalida força — um usuário criado com
senha fraca (ex.: contas antigas ou fixtures) continua conseguindo logar.
"""

import pytest
from rest_framework import status

REGISTRO_URL = "/api/auth/registro/"
TOKEN_URL = "/api/token/"

SENHA_FORTE = "Senha-Forte-123!"


@pytest.mark.django_db
def test_registro_aceita_senha_forte(api_client):
    response = api_client.post(
        REGISTRO_URL,
        {"nome": "Forte", "email": "forte@finflow.com", "password": SENHA_FORTE},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.parametrize(
    "senha_fraca",
    [
        "curta-1!",           # menos de 8 caracteres
        "tudo-minusculo-1!",  # sem maiúscula
        "TUDO-MAIUSCULO-1!",  # sem minúscula
        "Sem-Numeros-Aqui!",  # sem número
        "SemEspecial123",     # sem caractere especial
    ],
)
@pytest.mark.django_db
def test_registro_rejeita_senhas_fracas(api_client, senha_fraca):
    response = api_client.post(
        REGISTRO_URL,
        {"nome": "Fraco", "email": "fraco@finflow.com", "password": senha_fraca},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data


@pytest.mark.django_db
def test_login_nao_revalida_forca_de_senha(api_client, django_user_model):
    """Usuário antigo com senha fraca continua conseguindo logar (JWT)."""
    django_user_model.objects.create_user(
        username="antigo@finflow.com",
        email="antigo@finflow.com",
        password="senha-antiga-fraca",  # não cumpre a política atual
    )
    # O login exige duplo envio CSRF desde que o refresh viaja num cookie.
    api_client.get("/api/csrf/")
    csrf = api_client.cookies["csrftoken"].value
    response = api_client.post(
        TOKEN_URL,
        {"username": "antigo@finflow.com", "password": "senha-antiga-fraca"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
