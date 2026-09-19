"""
Testes do papel "ambos" (cliente E fornecedor) no cadastro de contatos.

Cobre a decisão de negócio: uma entidade pode ser cliente E fornecedor do
mesmo gestor ao mesmo tempo. Nesse caso ela pode aparecer em faturas de
qualquer tipo (a_receber OU a_pagar) — não existe vínculo entre o papel do
cliente e o tipo da fatura.
"""
import pytest
from rest_framework import status

from apps.clientes.models import Cliente, Papel, TipoPessoa
from apps.faturamento.models import CobrancaRecorrente, Fatura, TipoFatura

URL = "/api/clientes/"

CPF_VALIDO = "529.982.247-25"
CNPJ_VALIDO = "11.222.333/0001-81"


def payload_cliente(**kwargs):
    dados = {
        "nome": "Gráfica Central Ltda",
        "papel": Papel.AMBOS,
        "tipo_pessoa": TipoPessoa.JURIDICA,
        "documento": CNPJ_VALIDO,
        "email": "contato@graficacentral.com.br",
        "telefone": "(11) 3333-0000",
        "ativo": True,
    }
    dados.update(kwargs)
    return dados


# ---------------------------------------------------------------------------
# Criação e edição via API
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_cliente_com_papel_ambos(auth_client):
    """POST /api/clientes/ com papel='ambos' é aceito e persistido."""
    response = auth_client.post(URL, payload_cliente(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["papel"] == Papel.AMBOS
    cliente = Cliente.objects.get(documento=CNPJ_VALIDO)
    assert cliente.papel == Papel.AMBOS
    assert cliente.get_papel_display() == "Cliente/Fornecedor"


@pytest.mark.django_db
def test_editar_cliente_para_papel_ambos(auth_client, user):
    """Um contato 'cliente' pode ser promovido para 'ambos' via PATCH."""
    cliente = Cliente.objects.create(
        nome="Maria Silva",
        papel=Papel.CLIENTE,
        tipo_pessoa=TipoPessoa.FISICA,
        documento=CPF_VALIDO,
        owner=user,
    )

    response = auth_client.patch(
        f"{URL}{cliente.pk}/", {"papel": Papel.AMBOS}, format="json"
    )

    assert response.status_code == status.HTTP_200_OK
    cliente.refresh_from_db()
    assert cliente.papel == Papel.AMBOS


# ---------------------------------------------------------------------------
# Faturas: mesmo cliente 'ambos' em a_receber E a_pagar
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cliente_ambos_em_fatura_a_receber_e_a_pagar(auth_client, user):
    """O mesmo cliente papel='ambos' referencia faturas dos dois tipos."""
    response = auth_client.post(URL, payload_cliente(), format="json")
    assert response.status_code == status.HTTP_201_CREATED
    cliente_id = response.data["id"]

    fatura_receber = auth_client.post(
        "/api/faturas/",
        {
            "numero": "FT-2026-0100",
            "cliente": cliente_id,
            "descricao": "Venda de material gráfico",
            "tipo": TipoFatura.A_RECEBER,
            "valor": "1500.00",
            "vencimento": "2026-10-30",
        },
        format="json",
    )
    fatura_pagar = auth_client.post(
        "/api/faturas/",
        {
            "numero": "FT-2026-0101",
            "cliente": cliente_id,
            "descricao": "Serviço de impressão contratado",
            "tipo": TipoFatura.A_PAGAR,
            "valor": "800.00",
            "vencimento": "2026-10-15",
        },
        format="json",
    )

    assert fatura_receber.status_code == status.HTTP_201_CREATED
    assert fatura_pagar.status_code == status.HTTP_201_CREATED
    assert Fatura.objects.filter(cliente_id=cliente_id).count() == 2
    assert set(
        Fatura.objects.filter(cliente_id=cliente_id).values_list("tipo", flat=True)
    ) == {TipoFatura.A_RECEBER, TipoFatura.A_PAGAR}


@pytest.mark.django_db
def test_cliente_ambos_aceita_cobranca_recorrente(auth_client, user):
    """Cobranças recorrentes também aceitam cliente com papel='ambos'."""
    response = auth_client.post(URL, payload_cliente(), format="json")
    cliente_id = response.data["id"]

    cobranca = auth_client.post(
        "/api/cobrancas-recorrentes/",
        {
            "cliente": cliente_id,
            "descricao": "Aluguel de equipamento",
            "tipo": TipoFatura.A_RECEBER,
            "valor": "200.00",
            "periodicidade": "mensal",
            "dia_vencimento": 10,
            "proxima_cobranca": "2026-10-10",
        },
        format="json",
    )

    assert cobranca.status_code == status.HTTP_201_CREATED
    assert CobrancaRecorrente.objects.filter(cliente_id=cliente_id).exists()


@pytest.mark.django_db
def test_cliente_ambos_pode_ser_excluido_sem_faturas(auth_client, user):
    """Regra de exclusão (409 só com faturas) vale igual para papel='ambos'."""
    response = auth_client.post(URL, payload_cliente(), format="json")
    cliente_id = response.data["id"]

    delete = auth_client.delete(f"{URL}{cliente_id}/")

    assert delete.status_code == status.HTTP_204_NO_CONTENT


# ---------------------------------------------------------------------------
# Filtro semântico por papel
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_filtro_papel_ambos_aparece_em_cliente_e_fornecedor(auth_client, user):
    """?papel=cliente e ?papel=fornecedor incluem quem tem papel='ambos'."""
    Cliente.objects.create(
        nome="Só Cliente", papel=Papel.CLIENTE, tipo_pessoa=TipoPessoa.FISICA, owner=user
    )
    Cliente.objects.create(
        nome="Só Fornecedor",
        papel=Papel.FORNECEDOR,
        tipo_pessoa=TipoPessoa.FISICA,
        owner=user,
    )
    Cliente.objects.create(
        nome="Cliente e Fornecedor",
        papel=Papel.AMBOS,
        tipo_pessoa=TipoPessoa.FISICA,
        owner=user,
    )

    resposta_cliente = auth_client.get(URL, {"papel": "cliente"})
    resposta_fornecedor = auth_client.get(URL, {"papel": "fornecedor"})
    resposta_ambos = auth_client.get(URL, {"papel": "ambos"})

    nomes_cliente = {r["nome"] for r in resposta_cliente.data["results"]}
    nomes_fornecedor = {r["nome"] for r in resposta_fornecedor.data["results"]}

    assert nomes_cliente == {"Só Cliente", "Cliente e Fornecedor"}
    assert nomes_fornecedor == {"Só Fornecedor", "Cliente e Fornecedor"}
    assert [r["nome"] for r in resposta_ambos.data["results"]] == [
        "Cliente e Fornecedor"
    ]


@pytest.mark.django_db
def test_filtro_papel_valor_invalido_retorna_lista_vazia(auth_client, user):
    """Valor desconhecido mantém o comportamento do filtro exato: nada."""
    Cliente.objects.create(
        nome="Qualquer", papel=Papel.AMBOS, tipo_pessoa=TipoPessoa.FISICA, owner=user
    )

    response = auth_client.get(URL, {"papel": "nao-existe"})

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 0
