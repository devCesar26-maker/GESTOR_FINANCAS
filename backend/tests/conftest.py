"""Fixtures compartilhadas dos testes do FinFlow."""
import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def _limpiar_cache_throttle():
    """Cada teste começa com o cache de throttling limpo.

    DRF usa o cache padrão (LocMemCache) para os rate limits; sem limpá-lo
    entre testes, as tentativas de login/registro de um teste vazam sobre
    o seguinte e causam 429 espúrios.
    """
    yield
    cache.clear()

from apps.clientes.models import Cliente, Papel, TipoPessoa
from apps.faturamento.models import Fatura, TipoFatura


@pytest.fixture
def api_client():
    """APIClient sem autenticação."""
    return APIClient()


@pytest.fixture
def csrf_client():
    """APIClient que EXIGE o duplo envio CSRF de verdade.

    O padrão do APIClient é enforce_csrf_checks=False, que marca a request
    com _dont_enforce_csrf_checks=True e FAZ BYPASS do CsrfViewMiddleware
    (inclusive do decorator csrf_protect aplicado às views de token). Sem
    esta fixture, um teste que espera 403 por CSRF não está testando nada:
    a request simplesmente ignora a proteção.
    """
    return APIClient(enforce_csrf_checks=True)


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