"""
Testes dos e-mails transacionais assíncronos:
- boas-vindas ao gestor no registro (POST /api/auth/registro/);
- notificação de cadastro ao cliente/fornecedor (POST /api/clientes/).

Usam CELERY_TASK_ALWAYS_EAGER (task roda inline no teste) + backend de
teste do Anymail (captura em mailoutbox) — nada sai de verdade. Cobre as
regras da spec: o disparo acontece na criação, independe de
notificacoes_ativas, e uma falha de envio NUNCA impede a criação do
recurso.
"""
from unittest import mock

import pytest
from rest_framework import status

from apps.clientes.models import Cliente

from tests.test_multitenancy import REGISTRO_URL

CLIENTES_URL = "/api/clientes/"

EMAIL_CLIENTE = "contato@empresaexemplo.com"


def payload_cliente(**overrides):
    payload = {
        "nome": "Empresa Exemplo Ltda",
        "papel": "cliente",
        "tipo_pessoa": "pj",
        "email": EMAIL_CLIENTE,
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Notificação de cadastro ao cliente
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_cliente_dispara_notificacao_de_cadastro(auth_client, user, mailoutbox):
    response = auth_client.post(CLIENTES_URL, payload_cliente(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert Cliente.objects.filter(nome="Empresa Exemplo Ltda", owner=user).exists()

    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.to == [EMAIL_CLIENTE]
    # Assunto cita o gestor; corpo cita o cliente e o caráter informativo.
    assert user.username in email.subject
    assert "Empresa Exemplo Ltda" in email.body
    assert "NÃO é uma cobrança" in email.body


@pytest.mark.django_db
def test_notificacao_independe_de_notificacoes_ativas(auth_client, mailoutbox):
    """O e-mail de cadastro é one-shot: dispara mesmo com o toggle desligado."""
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(notificacoes_ativas=False), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_falha_no_envio_nao_impede_criacao_do_cliente(auth_client, user, mailoutbox):
    """SMTP cai no meio do envio: o cliente DEVE ser salvo mesmo assim."""
    with mock.patch(
        "apps.clientes.tasks.send_mail",
        side_effect=Exception("SMTP indisponível"),
    ):
        response = auth_client.post(CLIENTES_URL, payload_cliente(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert Cliente.objects.filter(nome="Empresa Exemplo Ltda", owner=user).exists()
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_cliente_sem_email_nao_dispara_notificacao(auth_client, mailoutbox):
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(email=""), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mailoutbox) == 0


# ---------------------------------------------------------------------------
# Boas-vindas ao gestor
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_registro_dispara_email_de_boas_vindas(api_client, mailoutbox):
    response = api_client.post(
        REGISTRO_URL,
        {
            "nome": "Gestor Teste",
            "email": "gestor@finflow.com",
            "password": "Senha-Teste-123!",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.to == ["gestor@finflow.com"]
    assert "Gestor Teste" in email.subject
    assert "criada com sucesso" in email.body
    assert "Equipe FinFlow" in email.body
