"""
Testes do app Clientes.

Cobrem: criação de cliente válido (PF e PJ), validação de documento
(formato CPF/CNPJ + unicidade), mascaramento LGPD na listagem vs detalhe,
tentativa de exclusão com faturas (409 Conflict), CRUD dos endpoints e o bloqueio de acesso
sem autenticação (401).
"""
import pytest
from rest_framework import status

from apps.clientes.models import Cliente, Papel, TipoPessoa
from apps.faturamento.models import Fatura

URL = "/api/clientes/"

CPF_VALIDO = "529.982.247-25"
CNPJ_VALIDO = "11.222.333/0001-81"


def payload_cliente(**kwargs):
    dados = {
        "nome": "Maria Silva",
        "papel": Papel.CLIENTE,
        "tipo_pessoa": TipoPessoa.FISICA,
        "documento": CPF_VALIDO,
        "email": "maria@example.com",
        "telefone": "(11) 99999-0000",
        "endereco": "Rua das Flores, 123",
        "ativo": True,
    }
    dados.update(kwargs)
    return dados


# ---------------------------------------------------------------------------
# Criação e validação de documento
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_cliente_valido(auth_client):
    response = auth_client.post(URL, payload_cliente(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nome"] == "Maria Silva"
    assert response.data["documento"] == CPF_VALIDO
    assert response.data["ativo"] is True
    assert Cliente.objects.filter(documento=CPF_VALIDO).exists()


@pytest.mark.django_db
def test_criar_cliente_juridico_valido(auth_client):
    response = auth_client.post(
        URL,
        payload_cliente(
            nome="Empresa ABC Ltda",
            papel=Papel.FORNECEDOR,
            tipo_pessoa=TipoPessoa.JURIDICA,
            documento=CNPJ_VALIDO,
        ),
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Cliente.objects.filter(documento=CNPJ_VALIDO).exists()


@pytest.mark.django_db
def test_documento_duplicado_e_rejeitado(auth_client):
    auth_client.post(URL, payload_cliente(), format="json")

    response = auth_client.post(URL, payload_cliente(), format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "documento" in response.data


@pytest.mark.django_db
def test_documento_com_formato_invalido_e_rejeitado(auth_client):
    response = auth_client.post(
        URL, payload_cliente(documento="123.456.789-00"), format="json"
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "documento" in response.data


@pytest.mark.django_db
def test_documento_incompativel_com_tipo_pessoa_e_rejeitado(auth_client):
    # CNPJ válido enviado para uma pessoa física
    response = auth_client.post(
        URL,
        payload_cliente(tipo_pessoa=TipoPessoa.FISICA, documento=CNPJ_VALIDO),
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "documento" in response.data


# ---------------------------------------------------------------------------
# Mascaramento LGPD (Listagem vs Detalhe)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_mascaramento_documento_lgpd(auth_client):
    c = Cliente.objects.create(
        nome="Cliente LGPD", tipo_pessoa=TipoPessoa.FISICA, documento=CPF_VALIDO
    )

    # Listagem -> Documento deve estar mascarado (529.***.***-25)
    list_res = auth_client.get(URL)
    assert list_res.status_code == status.HTTP_200_OK
    assert list_res.data["results"][0]["documento"] == "529.***.***-25"

    # Detalhe -> Documento deve vir completo
    detail_res = auth_client.get(f"{URL}{c.id}/")
    assert detail_res.status_code == status.HTTP_200_OK
    assert detail_res.data["documento"] == CPF_VALIDO


# ---------------------------------------------------------------------------
# CRUD dos endpoints
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_listar_clientes_paginado(auth_client):
    Cliente.objects.create(nome="Ana", tipo_pessoa=TipoPessoa.FISICA)
    Cliente.objects.create(nome="Bruno", tipo_pessoa=TipoPessoa.FISICA)

    response = auth_client.get(URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_atualizar_cliente(auth_client):
    cliente = Cliente.objects.create(
        nome="Ana", tipo_pessoa=TipoPessoa.FISICA, documento=CPF_VALIDO
    )

    response = auth_client.patch(
        f"{URL}{cliente.pk}/", {"nome": "Ana Souza"}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    cliente.refresh_from_db()
    assert cliente.nome == "Ana Souza"


@pytest.mark.django_db
def test_deletar_cliente(auth_client):
    cliente = Cliente.objects.create(nome="Ana", tipo_pessoa=TipoPessoa.FISICA)

    response = auth_client.delete(f"{URL}{cliente.pk}/")

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Cliente.objects.filter(pk=cliente.pk).exists()


@pytest.mark.django_db
def test_deletar_cliente_com_faturas_retorna_409_conflito(auth_client):
    cliente = Cliente.objects.create(nome="Ana", tipo_pessoa=TipoPessoa.FISICA)
    Fatura.objects.create(
        numero="FAT-PROT-1",
        cliente=cliente,
        valor="100.00",
        vencimento="2026-09-30",
    )

    response = auth_client.delete(f"{URL}{cliente.pk}/")

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "Não é possível excluir cliente com faturas vinculadas." in response.data["detail"]


# ---------------------------------------------------------------------------
# Filtros e busca
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_filtrar_por_nome(auth_client):
    Cliente.objects.create(nome="Ana Paula", tipo_pessoa=TipoPessoa.FISICA)
    Cliente.objects.create(nome="Bruno", tipo_pessoa=TipoPessoa.FISICA)

    response = auth_client.get(URL, {"nome": "ana"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["nome"] == "Ana Paula"


@pytest.mark.django_db
def test_filtrar_por_documento(auth_client):
    Cliente.objects.create(
        nome="Ana", tipo_pessoa=TipoPessoa.FISICA, documento=CPF_VALIDO
    )
    Cliente.objects.create(nome="Bruno", tipo_pessoa=TipoPessoa.FISICA)

    response = auth_client.get(URL, {"documento": "529.982"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1


@pytest.mark.django_db
def test_buscar_por_termo(auth_client):
    Cliente.objects.create(nome="Ana Paula", tipo_pessoa=TipoPessoa.FISICA)
    Cliente.objects.create(nome="Bruno", tipo_pessoa=TipoPessoa.FISICA)

    response = auth_client.get(URL, {"search": "paula"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["nome"] == "Ana Paula"


# ---------------------------------------------------------------------------
# Acesso sem autenticação (401)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_listar_sem_autenticacao_retorna_401(api_client):
    response = api_client.get(URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_criar_sem_autenticacao_retorna_401(api_client):
    response = api_client.post(URL, payload_cliente(), format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_atualizar_sem_autenticacao_retorna_401(api_client):
    cliente = Cliente.objects.create(nome="Ana", tipo_pessoa=TipoPessoa.FISICA)
    response = api_client.patch(f"{URL}{cliente.pk}/", {"nome": "X"}, format="json")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_deletar_sem_autenticacao_retorna_401(api_client):
    cliente = Cliente.objects.create(nome="Ana", tipo_pessoa=TipoPessoa.FISICA)
    response = api_client.delete(f"{URL}{cliente.pk}/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED