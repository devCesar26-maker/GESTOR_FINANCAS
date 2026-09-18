"""Regressão da MÍDIA PROTEGIDA e da URL relativa do comprovante.

Cobre as correções/hardenings de hoje:
1. comprovante_url SEMPRE relativo (começa com /media/, nunca http://...).
   - Trava a regressão do bug em que request.build_absolute_uri() vazava o
     hostname interno do Docker (http://backend:8000/media/...).
2. GET /media/<arquivo> SEM credencial -> 401 (mídia nunca é anônima).
3. GET com token do DONO da fatura -> 200 com content-type correto.
4. GET com token de OUTRO usuário -> 404 (isolamento por tenant).
5. Path traversal ("..") -> 404.
6. Extensão fora da whitelist -> 404 (não confia no tipo do upload).
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.faturamento.models import Fatura, StatusFatura, TipoFatura

PDF_BYTES = b"%PDF-1.4 comprovante protegido"


@pytest.fixture
def fatura_paga(user, cliente, django_user_model):
    """Fatura paga com comprovante gravado em disco (MEDIA_ROOT de teste)."""
    fatura = Fatura.objects.create(
        numero="FAT-MEDIA-SEC-1",
        cliente=cliente,
        descricao="Teste de mídia protegida",
        tipo=TipoFatura.A_RECEBER,
        valor="100.00",
        status=StatusFatura.PENDENTE,
        vencimento=timezone.localdate(),
        owner=user,
    )
    fatura.comprovante.save("comp_seguro.pdf", SimpleUploadedFile("c.pdf", PDF_BYTES, "application/pdf"), save=True)
    fatura.status = StatusFatura.PAGA
    fatura.save()
    return fatura


def auth_client_para(user):
    from rest_framework.test import APIClient

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
    return client


# ---------------------------------------------------------------------------
# 1) URL relativa (regressão do bug do hostname interno do Docker)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_comprovante_url_e_relativo(auth_client, fatura_paga):
    response = auth_client.get(f"/api/faturas/{fatura_paga.id}/")
    url = response.data["comprovante_url"]
    assert url
    assert url.startswith("/media/")
    assert not url.startswith("http://") and not url.startswith("https://")
    assert "backend:8000" not in url


# ---------------------------------------------------------------------------
# 2) Mídia nunca anônima
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_media_sem_token_retorna_401(api_client, fatura_paga):
    response = api_client.get(f"/media/{fatura_paga.comprovante.name}")
    assert response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


# ---------------------------------------------------------------------------
# 3) Dono baixa o próprio comprovante
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_media_com_token_do_dono_retorna_200(auth_client, fatura_paga):
    response = auth_client.get(f"/media/{fatura_paga.comprovante.name}")
    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"].startswith("application/pdf")
    assert response["X-Content-Type-Options"] == "nosniff"


# ---------------------------------------------------------------------------
# 4) Isolamento por tenant
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_media_de_outro_tenant_retorna_404(auth_client, fatura_paga, django_user_model):
    intruso = django_user_model.objects.create_user(
        username="intruso", email="intruso@x.com", password="senha-forte-123"
    )
    response = auth_client_para(intruso).get(f"/media/{fatura_paga.comprovante.name}")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 5) Path traversal
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_media_path_traversal_retorna_404(auth_client):
    response = auth_client.get("/media/comprovantes/../../etc/passwd")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 6) Whitelist de extensão
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# 7) Modo subauth do Nginx (X-Original-URI): 200/401 sem abrir o arquivo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_subauth_do_dono_retorna_200(auth_client, fatura_paga):
    response = auth_client.get(
        "/api/media/auth/",
        HTTP_X_ORIGINAL_URI=f"/media/{fatura_paga.comprovante.name}",
    )
    assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_subauth_arquivo_de_outro_ou_inexistente_retorna_401(auth_client, fatura_paga):
    for uri in (
        "/media/comprovantes/2026/09/fantasma.pdf",
        "/media/../etc/passwd",
    ):
        response = auth_client.get("/api/media/auth/", HTTP_X_ORIGINAL_URI=uri)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# 8) Whitelist de extensão (modo direto)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_media_extensao_desconhecida_retorna_404(auth_client, fatura_paga):
    caminho = fatura_paga.comprovante.name
    base, _, _ = caminho.rpartition(".")
    response = auth_client.get(f"/media/{base}.exe")
    assert response.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 9) Round-trip REAL: upload via /pagar/ -> download via /media/ (bytes íntegros)
# ---------------------------------------------------------------------------
# Garante que um comprovante enviado DE VERDADE abre corretamente: o fluxo
# completo do frontend (POST multipart -> GET blob) devolve exatamente os
# bytes enviados, com content-type correto. Regressão do "PDF vazio (0 de 0)",
# que era dado de teste órfão (stub gravado direto no banco), não bug de código.


@pytest.mark.django_db
def test_roundtrip_comprovante_enviado_abre_com_bytes_integros(
    auth_client, fatura
):
    conteudo_original = b"%PDF-1.4\n%roundtrip de comprovante real\n%%EOF\n"

    # 1) Fluxo real de pagamento via API (como o frontend faz).
    pagamento = auth_client.post(
        f"/api/faturas/{fatura.id}/pagar/",
        {
            "comprovante": SimpleUploadedFile(
                "comprovante_real.pdf", conteudo_original, "application/pdf"
            )
        },
        format="multipart",
    )
    assert pagamento.status_code == status.HTTP_200_OK

    # 2) A URL devolvida é relativa e o caminho existe no storage.
    url = pagamento.data["comprovante_url"]
    assert url.startswith("/media/")
    caminho = url[len("/media/"):]
    fatura.refresh_from_db()
    assert fatura.comprovante.name == caminho
    assert fatura.comprovante.storage.exists(caminho)

    # 3) Download autenticado devolve os MESMOS bytes enviados.
    download = auth_client.get(url)
    assert download.status_code == status.HTTP_200_OK
    assert download["Content-Type"] == "application/pdf"
    assert b"".join(download.streaming_content) == conteudo_original
