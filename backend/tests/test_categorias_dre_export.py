"""
Testes das novas funcionalidades: categorização financeira (centros de
custo), DRE simplificado, exportações CSV/PDF, filtros avançados e
bloqueio de edição de faturas pagas.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework import status

from apps.faturamento import services
from apps.faturamento.models import (
    CategoriaFinanceira,
    Fatura,
    StatusFatura,
    TipoFatura,
)

FATURAS_URL = "/api/faturas/"
CATEGORIAS_URL = "/api/categorias/"
DRE_URL = "/api/relatorios/dre/"
EXPORT_URL = "/api/faturas/exportar/"
DRE_EXPORT_URL = "/api/relatorios/dre/exportar/"


@pytest.fixture
def cat_receita(user):
    return CategoriaFinanceira.objects.create(
        nome="Vendas de Serviços",
        natureza=CategoriaFinanceira.Natureza.RECEITA,
        owner=user,
    )


@pytest.fixture
def cat_despesa(user):
    return CategoriaFinanceira.objects.create(
        nome="Aluguel",
        natureza=CategoriaFinanceira.Natureza.DESPESA,
        owner=user,
    )


def _criar_fatura(cliente, user, *, numero, tipo, valor, vencimento, status, categoria=None):
    return Fatura.objects.create(
        numero=numero,
        cliente=cliente,
        tipo=tipo,
        valor=Decimal(valor),
        status=status,
        vencimento=vencimento,
        categoria=categoria,
        owner=user,
    )


# ---------------------------------------------------------------------------
# CRUD de categorias
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_categorias_lista_semeia_padrao(auth_client):
    """A primeira listagem semeia o catálogo padrão do usuário."""
    response = auth_client.get(CATEGORIAS_URL)
    assert response.status_code == status.HTTP_200_OK
    nomes = {c["nome"] for c in response.data["results"]}
    assert "Aluguel" in nomes
    assert "Salários" in nomes
    assert "Vendas de Serviços" in nomes
    assert "Impostos" in nomes
    # Idempotente: segunda chamada não duplica
    response2 = auth_client.get(CATEGORIAS_URL)
    assert len(response2.data["results"]) == len(response.data["results"])


@pytest.mark.django_db
def test_criar_categoria_endpoint(auth_client):
    response = auth_client.post(
        CATEGORIAS_URL,
        {"nome": "Marketing", "natureza": "despesa"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nome"] == "Marketing"


@pytest.mark.django_db
def test_categoria_sanitiza_xss(auth_client):
    """Payload com tags HTML é limpo antes de gravar (anti-XSS)."""
    response = auth_client.post(
        CATEGORIAS_URL,
        {"nome": "<b>Tech</b><script>alert(1)</script>", "natureza": "despesa"},
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert "<" not in response.data["nome"]
    assert response.data["nome"] == "Techalert(1)"


@pytest.mark.django_db
def test_categoria_nome_duplicado_mesmo_owner_rejeitado(auth_client, user):
    CategoriaFinanceira.objects.create(nome="TI", owner=user)
    response = auth_client.post(CATEGORIAS_URL, {"nome": "ti"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_categoria_multitenancy_404(auth_client, django_user_model):
    outro = django_user_model.objects.create_user(
        username="outro2", email="outro2@x.com", password="senha-outro-123"
    )
    alheia = CategoriaFinanceira.objects.create(nome="Secreta", owner=outro)
    response = auth_client.get(f"{CATEGORIAS_URL}{alheia.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Fatura com categoria + validações
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_criar_fatura_com_categoria(auth_client, cliente, cat_receita):
    response = auth_client.post(
        FATURAS_URL,
        {
            "numero": "FAT-CAT-1",
            "cliente": cliente.id,
            "tipo": "a_receber",
            "valor": "100.00",
            "vencimento": str(timezone.localdate()),
            "categoria": cat_receita.id,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["categoria"] == cat_receita.id
    assert response.data["categoria_nome"] == "Vendas de Serviços"


@pytest.mark.django_db
def test_fatura_categoria_de_outro_owner_rejeitada(auth_client, cliente, django_user_model):
    outro = django_user_model.objects.create_user(
        username="outro3", email="outro3@x.com", password="senha-outro-123"
    )
    alheia = CategoriaFinanceira.objects.create(nome="Alheia", owner=outro)
    response = auth_client.post(
        FATURAS_URL,
        {
            "numero": "FAT-CAT-2",
            "cliente": cliente.id,
            "tipo": "a_receber",
            "valor": "100.00",
            "vencimento": str(timezone.localdate()),
            "categoria": alheia.id,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Bloqueio de edição de faturas pagas / vencidas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_patch_fatura_paga_bloqueado_409(auth_client, fatura, cliente, cat_receita):
    fatura.status = StatusFatura.PAGA
    fatura.save()
    response = auth_client.patch(
        f"{FATURAS_URL}{fatura.id}/",
        {"descricao": "tentativa"},
        format="json",
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    fatura.refresh_from_db()
    assert fatura.descricao != "tentativa"


@pytest.mark.django_db
def test_put_fatura_paga_bloqueado_409(auth_client, fatura):
    fatura.status = StatusFatura.PAGA
    fatura.save()
    response = auth_client.put(
        f"{FATURAS_URL}{fatura.id}/",
        {
            "numero": fatura.numero,
            "cliente": fatura.cliente_id,
            "tipo": fatura.tipo,
            "valor": "999.00",
            "vencimento": str(fatura.vencimento),
        },
        format="json",
    )
    assert response.status_code == status.HTTP_409_CONFLICT
    fatura.refresh_from_db()
    assert Decimal(str(fatura.valor)) == Decimal("1500.00")


@pytest.mark.django_db
def test_delete_fatura_paga_bloqueado_409(auth_client, fatura):
    fatura.status = StatusFatura.PAGA
    fatura.save()
    response = auth_client.delete(f"{FATURAS_URL}{fatura.id}/")
    assert response.status_code == status.HTTP_409_CONFLICT
    assert Fatura.objects.filter(pk=fatura.pk).exists()


@pytest.mark.django_db
def test_editar_fatura_pendente_permitted(auth_client, fatura, cat_receita):
    response = auth_client.patch(
        f"{FATURAS_URL}{fatura.id}/",
        {"descricao": "Descrição nova", "categoria": cat_receita.id},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK
    fatura.refresh_from_db()
    assert fatura.descricao == "Descrição nova"
    assert fatura.categoria_id == cat_receita.id


# ---------------------------------------------------------------------------
# Filtros avançados (datas, status, tipo, busca)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_filtro_intervalo_de_datas(auth_client, cliente, user):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="F-D1", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje - timedelta(days=10), status=StatusFatura.PENDENTE)
    _criar_fatura(cliente, user, numero="F-D2", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje + timedelta(days=10), status=StatusFatura.PENDENTE)

    response = auth_client.get(
        FATURAS_URL,
        {
            "vencimento_apos": str(hoje - timedelta(days=5)),
            "vencimento_ate": str(hoje + timedelta(days=5)),
        },
    )
    assert response.status_code == status.HTTP_200_OK
    numeros = {f["numero"] for f in response.data["results"]}
    assert numeros == set()  # ambas fora do intervalo


@pytest.mark.django_db
def test_filtro_status_e_tipo(auth_client, cliente, user):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="F-P1", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PENDENTE)
    _criar_fatura(cliente, user, numero="F-G1", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PAGA)
    _criar_fatura(cliente, user, numero="F-AP", tipo=TipoFatura.A_PAGAR,
                  valor="10", vencimento=hoje, status=StatusFatura.PENDENTE)

    response = auth_client.get(FATURAS_URL, {"status": "paga"})
    assert {f["numero"] for f in response.data["results"]} == {"F-G1"}

    response = auth_client.get(FATURAS_URL, {"tipo": "a_pagar"})
    assert {f["numero"] for f in response.data["results"]} == {"F-AP"}


@pytest.mark.django_db
def test_filtro_busca_e_search(auth_client, cliente, user):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="F-XYZ-1", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PENDENTE)
    _criar_fatura(cliente, user, numero="F-ABC-2", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PENDENTE)

    response = auth_client.get(FATURAS_URL, {"busca": "xyz"})
    assert {f["numero"] for f in response.data["results"]} == {"F-XYZ-1"}

    response = auth_client.get(FATURAS_URL, {"search": "ABC"})
    assert {f["numero"] for f in response.data["results"]} == {"F-ABC-2"}


@pytest.mark.django_db
def test_filtro_categoria(auth_client, cliente, user, cat_receita, cat_despesa):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="F-CAT-A", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PENDENTE,
                  categoria=cat_receita)
    _criar_fatura(cliente, user, numero="F-CAT-B", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PENDENTE,
                  categoria=cat_despesa)

    response = auth_client.get(FATURAS_URL, {"categoria": cat_receita.id})
    assert {f["numero"] for f in response.data["results"]} == {"F-CAT-A"}


@pytest.mark.django_db
def test_filtro_data_invalida_rejeitada_400(auth_client):
    response = auth_client.get(FATURAS_URL, {"vencimento_apos": "nao-e-data"})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# DRE simplificado
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_dre_agrupa_por_categoria(auth_client, cliente, user, cat_receita, cat_despesa):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="D-R1", tipo=TipoFatura.A_RECEBER,
                  valor="1000", vencimento=hoje, status=StatusFatura.PAGA,
                  categoria=cat_receita)
    _criar_fatura(cliente, user, numero="D-R2", tipo=TipoFatura.A_RECEBER,
                  valor="500", vencimento=hoje, status=StatusFatura.PAGA,
                  categoria=cat_receita)
    _criar_fatura(cliente, user, numero="D-D1", tipo=TipoFatura.A_PAGAR,
                  valor="300", vencimento=hoje, status=StatusFatura.PAGA,
                  categoria=cat_despesa)
    # Pendente e cancelada NÃO entram no DRE (regime de caixa)
    _criar_fatura(cliente, user, numero="D-P", tipo=TipoFatura.A_RECEBER,
                  valor="999", vencimento=hoje, status=StatusFatura.PENDENTE)
    _criar_fatura(cliente, user, numero="D-C", tipo=TipoFatura.A_RECEBER,
                  valor="999", vencimento=hoje, status=StatusFatura.CANCELADA)

    response = auth_client.get(DRE_URL)
    assert response.status_code == status.HTTP_200_OK
    assert Decimal(str(response.data["total_receitas"])) == Decimal("1500")
    assert Decimal(str(response.data["total_despesas"])) == Decimal("300")
    assert Decimal(str(response.data["resultado"])) == Decimal("1200")

    receita = next(
        r for r in response.data["receitas"] if r["categoria"] == "Vendas de Serviços"
    )
    assert Decimal(str(receita["total"])) == Decimal("1500")


@pytest.mark.django_db
def test_dre_multitenancy(auth_client, cliente, django_user_model):
    """Faturas de outro usuário não entram no DRE."""
    outro = django_user_model.objects.create_user(
        username="outro4", email="outro4@x.com", password="senha-outro-123"
    )
    hoje = timezone.localdate()
    _criar_fatura(cliente, outro, numero="D-OUTRO", tipo=TipoFatura.A_RECEBER,
                  valor="5000", vencimento=hoje, status=StatusFatura.PAGA)

    response = auth_client.get(DRE_URL)
    assert Decimal(str(response.data["total_receitas"])) == Decimal("0")


@pytest.mark.django_db
def test_dre_sem_autenticacao_401(api_client):
    assert api_client.get(DRE_URL).status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Exportações (CSV/Excel/PDF) — faturas e DRE
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_exportar_faturas_csv(auth_client, cliente, user, cat_receita):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="E-1", tipo=TipoFatura.A_RECEBER,
                  valor="150.50", vencimento=hoje, status=StatusFatura.PAGA,
                  categoria=cat_receita)

    response = auth_client.get(EXPORT_URL, {"formato": "csv"})
    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith("text/csv")
    assert "faturas.csv" in response["Content-Disposition"]

    corpo = response.content.decode("utf-8-sig")
    assert "Número" in corpo
    assert "E-1" in corpo
    assert "Vendas de Serviços" in corpo
    assert "Paga" in corpo


@pytest.mark.django_db
def test_exportar_faturas_excel_alias(auth_client):
    response = auth_client.get(EXPORT_URL, {"formato": "excel"})
    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith("text/csv")
    assert "faturas-excel.csv" in response["Content-Disposition"]


@pytest.mark.django_db
def test_exportar_faturas_pdf(auth_client, cliente, user):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="E-PDF", tipo=TipoFatura.A_RECEBER,
                  valor="99.90", vencimento=hoje, status=StatusFatura.PENDENTE)

    response = auth_client.get(EXPORT_URL, {"formato": "pdf"})
    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF")
    assert "faturas.pdf" in response["Content-Disposition"]


@pytest.mark.django_db
def test_exportar_faturas_respeita_filtros(auth_client, cliente, user):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="E-S1", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PAGA)
    _criar_fatura(cliente, user, numero="E-S2", tipo=TipoFatura.A_RECEBER,
                  valor="10", vencimento=hoje, status=StatusFatura.PENDENTE)

    response = auth_client.get(EXPORT_URL, {"formato": "csv", "status": "paga"})
    corpo = response.content.decode("utf-8-sig")
    assert "E-S1" in corpo
    assert "E-S2" not in corpo


@pytest.mark.django_db
def test_exportar_dre_csv_e_pdf(auth_client, cliente, user, cat_receita):
    hoje = timezone.localdate()
    _criar_fatura(cliente, user, numero="ED-1", tipo=TipoFatura.A_RECEBER,
                  valor="700", vencimento=hoje, status=StatusFatura.PAGA,
                  categoria=cat_receita)

    response = auth_client.get(DRE_EXPORT_URL, {"formato": "csv"})
    assert response.status_code == status.HTTP_200_OK
    corpo = response.content.decode("utf-8-sig")
    assert "Vendas de Serviços" in corpo
    assert "Resultado do Período" in corpo

    response = auth_client.get(DRE_EXPORT_URL, {"formato": "pdf"})
    assert response.status_code == status.HTTP_200_OK
    assert response.content.startswith(b"%PDF")


@pytest.mark.django_db
def test_exportar_sem_autenticacao_401(api_client):
    assert api_client.get(EXPORT_URL).status_code == status.HTTP_401_UNAUTHORIZED
    assert api_client.get(DRE_EXPORT_URL).status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# Cobrança recorrente herda categoria
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_processar_cobrancas_herda_categoria(cliente, user, cat_despesa):
    from apps.faturamento.models import CobrancaRecorrente, Periodicidade

    cobranca = CobrancaRecorrente.objects.create(
        cliente=cliente,
        descricao="Aluguel mensal",
        tipo=TipoFatura.A_PAGAR,
        valor=Decimal("1200"),
        periodicidade=Periodicidade.MENSAL,
        dia_vencimento=10,
        proxima_cobranca=timezone.localdate(),
        categoria=cat_despesa,
        owner=user,
    )
    faturas = services.processar_cobrancas_recorrentes()
    assert len(faturas) == 1
    assert faturas[0].categoria_id == cat_despesa.id
    assert cobranca.categoria_id == cat_despesa.id
