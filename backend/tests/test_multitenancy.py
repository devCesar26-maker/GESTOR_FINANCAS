"""
Testes de multi-tenancy (Fase 1).

Cobrem: isolamento de listagem e detalhe entre usuários (404, não 403),
para Cliente, Fatura e CobrancaRecorrente; ignorância de "owner" no payload;
filtro de owner no relatório de fluxo de caixa; e o endpoint público de
registro (criação bem-sucedida e e-mail duplicado rejeitado).
"""

from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status

from apps.clientes.models import Cliente, Papel, TipoPessoa
from apps.faturamento.models import (
    CobrancaRecorrente,
    Fatura,
    Periodicidade,
    StatusFatura,
    TipoFatura,
)

CLIENTES_URL = "/api/clientes/"
FATURAS_URL = "/api/faturas/"
COBRANCAS_URL = "/api/cobrancas-recorrentes/"
FLUXO_CAIXA_URL = "/api/relatorios/fluxo-caixa/"
REGISTRO_URL = "/api/auth/registro/"

CPF_A = "529.982.247-25"
CPF_B = "153.509.490-60"


# ---------------------------------------------------------------------------
# Fixtures: dois usuários com dados próprios
# ---------------------------------------------------------------------------


@pytest.fixture
def user_a(django_user_model):
    return django_user_model.objects.create_user(
        username="a@finflow.com", email="a@finflow.com", password="senha-a-123"
    )


@pytest.fixture
def user_b(django_user_model):
    return django_user_model.objects.create_user(
        username="b@finflow.com", email="b@finflow.com", password="senha-b-123"
    )


@pytest.fixture
def client_a(api_client, user_a):
    api_client.force_authenticate(user=user_a)
    return api_client


@pytest.fixture
def client_b(api_client, user_b):
    api_client.force_authenticate(user=user_b)
    return api_client


@pytest.fixture
def cliente_a(user_a):
    return Cliente.objects.create(
        nome="Cliente de A",
        papel=Papel.CLIENTE,
        tipo_pessoa=TipoPessoa.FISICA,
        documento=CPF_A,
        owner=user_a,
    )


@pytest.fixture
def cliente_b(user_b):
    return Cliente.objects.create(
        nome="Cliente de B",
        papel=Papel.CLIENTE,
        tipo_pessoa=TipoPessoa.FISICA,
        documento=CPF_B,
        owner=user_b,
    )


@pytest.fixture
def fatura_a(cliente_a, user_a):
    return Fatura.objects.create(
        numero="FAT-A-1",
        cliente=cliente_a,
        valor=Decimal("100.00"),
        tipo=TipoFatura.A_RECEBER,
        status=StatusFatura.PENDENTE,
        vencimento=timezone.localdate(),
        owner=user_a,
    )


@pytest.fixture
def fatura_b(cliente_b, user_b):
    return Fatura.objects.create(
        numero="FAT-B-1",
        cliente=cliente_b,
        valor=Decimal("200.00"),
        tipo=TipoFatura.A_RECEBER,
        status=StatusFatura.PENDENTE,
        vencimento=timezone.localdate(),
        owner=user_b,
    )


@pytest.fixture
def cobranca_a(cliente_a, user_a):
    return CobrancaRecorrente.objects.create(
        cliente=cliente_a,
        descricao="Cobrança de A",
        valor=Decimal("50.00"),
        periodicidade=Periodicidade.MENSAL,
        dia_vencimento=10,
        proxima_cobranca=timezone.localdate(),
        owner=user_a,
    )


@pytest.fixture
def cobranca_b(cliente_b, user_b):
    return CobrancaRecorrente.objects.create(
        cliente=cliente_b,
        descricao="Cobrança de B",
        valor=Decimal("60.00"),
        periodicidade=Periodicidade.MENSAL,
        dia_vencimento=10,
        proxima_cobranca=timezone.localdate(),
        owner=user_b,
    )


# ---------------------------------------------------------------------------
# Isolamento — Cliente
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_usuario_a_nao_ve_clientes_de_b(client_a, cliente_b):
    response = client_a.get(CLIENTES_URL)
    assert response.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in response.data["results"]]
    assert cliente_b.id not in ids


@pytest.mark.django_db
def test_detail_cliente_de_outro_usuario_retorna_404(client_a, cliente_b):
    response = client_a.get(f"{CLIENTES_URL}{cliente_b.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_update_cliente_de_outro_usuario_retorna_404(client_a, cliente_b):
    response = client_a.patch(
        f"{CLIENTES_URL}{cliente_b.id}/", {"nome": "Hacked"}, format="json"
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    cliente_b.refresh_from_db()
    assert cliente_b.nome == "Cliente de B"


@pytest.mark.django_db
def test_delete_cliente_de_outro_usuario_retorna_404(client_a, cliente_b):
    response = client_a.delete(f"{CLIENTES_URL}{cliente_b.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert Cliente.objects.filter(pk=cliente_b.pk).exists()


# ---------------------------------------------------------------------------
# Isolamento — Fatura
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_usuario_a_nao_ve_faturas_de_b(client_a, fatura_b):
    response = client_a.get(FATURAS_URL)
    assert response.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in response.data["results"]]
    assert fatura_b.id not in ids


@pytest.mark.django_db
def test_detail_fatura_de_outro_usuario_retorna_404(client_a, fatura_b):
    response = client_a.get(f"{FATURAS_URL}{fatura_b.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_action_pagar_fatura_de_outro_usuario_retorna_404(client_a, fatura_b):
    response = client_a.post(f"{FATURAS_URL}{fatura_b.id}/pagar/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    fatura_b.refresh_from_db()
    assert fatura_b.status == StatusFatura.PENDENTE


@pytest.mark.django_db
def test_action_cancelar_fatura_de_outro_usuario_retorna_404(client_a, fatura_b):
    response = client_a.post(f"{FATURAS_URL}{fatura_b.id}/cancelar/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    fatura_b.refresh_from_db()
    assert fatura_b.status == StatusFatura.PENDENTE


# ---------------------------------------------------------------------------
# Isolamento — CobrancaRecorrente
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_usuario_a_nao_ve_cobrancas_de_b(client_a, cobranca_b):
    response = client_a.get(COBRANCAS_URL)
    assert response.status_code == status.HTTP_200_OK
    ids = [r["id"] for r in response.data["results"]]
    assert cobranca_b.id not in ids


@pytest.mark.django_db
def test_detail_cobranca_de_outro_usuario_retorna_404(client_a, cobranca_b):
    response = client_a.get(f"{COBRANCAS_URL}{cobranca_b.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_delete_cobranca_de_outro_usuario_retorna_404(client_a, cobranca_b):
    response = client_a.delete(f"{COBRANCAS_URL}{cobranca_b.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert CobrancaRecorrente.objects.filter(pk=cobranca_b.pk).exists()


# ---------------------------------------------------------------------------
# Owner nunca vem do payload
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_do_payload_e_ignorado_na_criacao_de_cliente(
    client_a, user_a, user_b
):
    response = client_a.post(
        CLIENTES_URL,
        {
            "nome": "Cliente Injetado",
            "papel": Papel.CLIENTE,
            "tipo_pessoa": TipoPessoa.FISICA,
            "owner": user_b.id,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    cliente = Cliente.objects.get(pk=response.data["id"])
    assert cliente.owner == user_a


@pytest.mark.django_db
def test_owner_do_payload_e_ignorado_na_criacao_de_fatura(
    client_a, user_a, user_b, cliente_a
):
    response = client_a.post(
        FATURAS_URL,
        {
            "numero": "FAT-INJ-1",
            "cliente": cliente_a.id,
            "valor": "10.00",
            "vencimento": str(timezone.localdate()),
            "owner": user_b.id,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    fatura = Fatura.objects.get(pk=response.data["id"])
    assert fatura.owner == user_a


@pytest.mark.django_db
def test_fatura_nao_pode_referenciar_cliente_de_outro_usuario(
    client_a, cliente_b
):
    response = client_a.post(
        FATURAS_URL,
        {
            "numero": "FAT-CROSS-1",
            "cliente": cliente_b.id,
            "valor": "10.00",
            "vencimento": str(timezone.localdate()),
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not Fatura.objects.filter(numero="FAT-CROSS-1").exists()


# ---------------------------------------------------------------------------
# Relatório de fluxo de caixa com filtro de owner
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fluxo_caixa_somente_do_usuario(user_a, cliente_a, fatura_a, user_b, cliente_b):
    # Fatura de B não deve entrar no cálculo de A.
    Fatura.objects.create(
        numero="FAT-B-2",
        cliente=cliente_b,
        valor=Decimal("900.00"),
        tipo=TipoFatura.A_RECEBER,
        status=StatusFatura.PAGA,
        vencimento=timezone.localdate(),
        owner=user_b,
    )

    from apps.relatorios import services

    dados = services.gerar_fluxo_caixa(owner=user_a)
    assert dados["total_a_receber"] == Decimal("100.00")  # apenas fatura_a (pendente)

    dados_b = services.gerar_fluxo_caixa(owner=user_b)
    assert dados_b["total_recebido"] == Decimal("900.00")  # apenas fatura PAGA de B


@pytest.mark.django_db
def test_endpoint_fluxo_caixa_filtrado_por_usuario(
    client_a, user_a, cliente_a, fatura_a, user_b, cliente_b
):
    Fatura.objects.create(
        numero="FAT-B-3",
        cliente=cliente_b,
        valor=Decimal("500.00"),
        tipo=TipoFatura.A_RECEBER,
        status=StatusFatura.PAGA,
        vencimento=timezone.localdate(),
        owner=user_b,
    )

    response = client_a.get(FLUXO_CAIXA_URL)
    assert response.status_code == status.HTTP_200_OK
    # Apenas a fatura pendente de A entra no previsto...
    assert Decimal(str(response.data["total_a_receber"])) == Decimal("100.00")
    # ...e a fatura PAGA de B (500) não vazou para o relatório de A.
    assert Decimal(str(response.data["total_recebido"])) == Decimal("0.00")


# ---------------------------------------------------------------------------
# Endpoint de registro
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_registro_bem_sucedido(api_client, django_user_model):
    response = api_client.post(
        REGISTRO_URL,
        {"nome": "Novo Usuário", "email": "novo@finflow.com", "password": "Senha-Forte-456!"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["email"] == "novo@finflow.com"

    user = django_user_model.objects.get(email="novo@finflow.com")
    assert user.check_password("Senha-Forte-456!")
    assert user.is_active


@pytest.mark.django_db
def test_registro_rejeita_email_duplicado(api_client, django_user_model):
    django_user_model.objects.create_user(
        username="dup@finflow.com", email="dup@finflow.com", password="x-senha-123"
    )
    response = api_client.post(
        REGISTRO_URL,
        {"nome": "Outro", "email": "DUP@finflow.com", "password": "Outra-Senha-789!"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data


@pytest.mark.django_db
def test_registro_rejeita_senha_fraca(api_client):
    response = api_client.post(
        REGISTRO_URL,
        {"nome": "Fracasso", "email": "fraco@finflow.com", "password": "12345678"},
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data


@pytest.mark.django_db
def test_registro_e_publico_sem_autenticacao(api_client):
    # Endpoint público: não retorna 401 como os demais.
    response = api_client.post(
        REGISTRO_URL,
        {"nome": "Anon", "email": "anon@finflow.com", "password": "Senha-Anon-123!"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
