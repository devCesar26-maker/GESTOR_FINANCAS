"""Fixtures compartilhadas dos testes do FinFlow."""
import pytest
from rest_framework.test import APIClient

from apps.clientes.models import Cliente, Papel, TipoPessoa
from apps.faturamento.models import Fatura, TipoFatura


@pytest.fixture
def api_client():
    """APIClient sem autenticação."""
    return APIClient()


@pytest.fixture
def auth_client(user):
    """APIClient autenticado com JWT forçado (sem passar pela view de login)."""
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def user(django_user_model):
    return django_user_model.objects.create_user(
        username="admin", email="admin@finflow.com", password="senha-forte-123"
    )


@pytest.fixture
def cliente(user):
    return Cliente.objects.create(
        nome="Empresa Exemplo Ltda",
        papel=Papel.CLIENTE,
        tipo_pessoa=TipoPessoa.JURIDICA,
        owner=user,
    )


@pytest.fixture
def fatura(cliente, user):
    return Fatura.objects.create(
        numero="FT-2026-0001",
        cliente=cliente,
        descricao="Serviço de consultoria",
        tipo=TipoFatura.A_RECEBER,
        valor="1500.00",
        vencimento="2026-09-30",
        owner=user,
    )