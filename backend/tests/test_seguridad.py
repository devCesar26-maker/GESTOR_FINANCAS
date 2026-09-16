"""
Testes de segurança (hardening) — um teste por categoria de ataque.

Cada teste documenta o que foi auditado e o que protege. Resumo completo
por categoria (auditado / já seguro / corrigido / limitação conhecida) no
README, seção "Segurança (hardening)".
"""

import pytest
from rest_framework import status

from apps.clientes.models import Cliente, Papel, TipoPessoa
from apps.faturamento.models import Fatura, TipoFatura

CLIENTES_URL = "/api/clientes/"
FATURAS_URL = "/api/faturas/"
TOKEN_URL = "/api/token/"
REGISTRO_URL = "/api/auth/registro/"

CPF_VALIDO = "529.982.247-25"
SENHA_FORTE = "Senha-Forte-123!"

PAYLOAD_XSS = "<script>alert(1)</script>"

PAYLOADS_SQLI = [
    "'; DROP TABLE clientes; --",
    "' OR '1'='1",
    "1 OR 1=1",
    "'; SELECT * FROM auth_user; --",
    '" OR ""="',
]


def payload_cliente(**kwargs):
    dados = {
        "nome": "Maria Silva",
        "papel": Papel.CLIENTE,
        "tipo_pessoa": TipoPessoa.FISICA,
        "documento": CPF_VALIDO,
        "email": "maria@example.com",
        "ativo": True,
    }
    dados.update(kwargs)
    return dados


# ---------------------------------------------------------------------------
# 1. SQL Injection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("payload", PAYLOADS_SQLI)
@pytest.mark.django_db
def test_sqli_en_filtros_no_rompe_ni_executa(auth_client, user, payload):
    """Payloads SQLi nos campos de busca/filtro: 200 com count 0, sem 500.

    Auditoria: não existe .raw()/.extra()/cursor.execute() no projeto —
    todo passa pelo ORM parametrizado do Django. Este teste comprova que
    um payload clássico não rompe a consulta nem altera dados.
    """
    Cliente.objects.create(nome="Ana", tipo_pessoa=TipoPessoa.FISICA, owner=user)

    for campo in ("nome", "documento", "search"):
        response = auth_client.get(CLIENTES_URL, {campo: payload})

        # Resultado vazio ou validação normal — nunca 500 nem erro de BD.
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0

    # Nada foi executado: a tabela segue existindo com os mesmos dados.
    assert Cliente.objects.filter(nome="Ana").exists()


@pytest.mark.django_db
def test_sqli_en_nome_de_creacion_se_guarda_como_texto_literal(auth_client):
    payload = "'; DROP TABLE clientes; --"
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(nome=payload), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Cliente.objects.filter(nome=payload).exists()
    assert Cliente.objects.count() == 1  # nada mais foi criado/borrado


# ---------------------------------------------------------------------------
# 2. XSS (Cross-Site Scripting)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_xss_nome_cliente_e_sanitizado_na_entrada(auth_client):
    """Nome com <script> via API: tags são REMOVIDAS na entrada (strip).

    Auditoria: o frontend React escapa por padrão e os serializers agora
    fazem strip de tags HTML na entrada (_strip_tags com html.unescape +
    regex). Texto residual é guardado literal; JSON nunca executa HTML.
    Teste de render no frontend: frontend/src/xss_escape.test.jsx.
    """
    response = auth_client.post(
        CLIENTES_URL, payload_cliente(nome=PAYLOAD_XSS), format="json"
    )

    assert response.status_code == status.HTTP_201_CREATED
    cliente = Cliente.objects.get(pk=response.data["id"])
    assert cliente.nome == "alert(1)"  # tags removidas, texto residual
    assert response.data["nome"] == "alert(1)"
    assert "<" not in cliente.nome and ">" not in cliente.nome


@pytest.mark.django_db
def test_xss_descricao_fatura_e_sanitizada_na_entrada(auth_client, user):
    cliente = Cliente.objects.create(
        nome="Ana", tipo_pessoa=TipoPessoa.FISICA, owner=user
    )

    response = auth_client.post(
        FATURAS_URL,
        {
            "numero": "FT-XSS-1",
            "cliente": cliente.pk,
            "descricao": PAYLOAD_XSS,
            "tipo": TipoFatura.A_RECEBER,
            "valor": "100.00",
            "vencimento": "2026-09-30",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    fatura = Fatura.objects.get(pk=response.data["id"])
    assert fatura.descricao == "alert(1)"  # tags removidas
    assert "<" not in fatura.descricao and ">" not in fatura.descricao


# ---------------------------------------------------------------------------
# 3. CSRF
# ---------------------------------------------------------------------------


def _obtener_csrf(api_client):
    """GET /api/csrf/ (define o cookie csrftoken) e devolve o token."""
    response = api_client.get("/api/csrf/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    return api_client.cookies["csrftoken"].value


@pytest.mark.django_db
def test_csrf_obligatorio_en_login(csrf_client):
    """Login sem X-CSRFToken → 403 (duplo envio CSRF).

    Desde que o refresh token viaja num cookie httpOnly, o login/refresh
    são endpoints com cookie de credencial — exatamente o que o CSRF
    protege. O frontend obtiene o token via GET /api/csrf/ e o envia no
    header X-CSRFToken. Usa csrf_client (enforce_csrf_checks=True): com o
    client padrão o middleware é bypassado e o teste não prova nada.
    """
    response = csrf_client.post(
        TOKEN_URL,
        {"username": "admin", "password": "senha-errada"},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_csrf_obligatorio_en_refresh(csrf_client):
    """Refresh sem X-CSRFToken → 403 (o cookie de refresh é credencial)."""
    response = csrf_client.post("/api/token/refresh/", {}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_csrf_no_aplica_en_endpoints_con_auth_por_header(auth_client):
    """Endpoints autenticados por header Authorization seguem sem CSRF.

    O CSRF aplica SOLO onde há cookie de credencial (login/refresh). O
    resto da API se autentica com Bearer token no header — não há cookie
    que um atacante possa fazer o navegador enviar automaticamente.
    """
    response = auth_client.post(CLIENTES_URL, payload_cliente(), format="json")
    assert response.status_code == status.HTTP_201_CREATED


# ---------------------------------------------------------------------------
# 5. Clickjacking
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_clickjacking_headers(auth_client):
    """X-Frame-Options: DENY + CSP frame-ancestors 'none' em toda resposta.

    X_FRAME_OPTIONS="DENY" já estava no settings; a CSP é adicionada pelo
    middleware finflow.middleware.CSPFrameAncestorsMiddleware.
    """
    response = auth_client.get(CLIENTES_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response["Content-Security-Policy"]


# ---------------------------------------------------------------------------
# 6b. HSTS (Strict-Transport-Security)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_hsts_header_en_respuestas_https(api_client):
    """HSTS: header Strict-Transport-Security em respostas HTTPS.

    Auditado: SECURE_HSTS_SECONDS / SECURE_HSTS_INCLUDE_SUBDOMAINS /
    SECURE_HSTS_PRELOAD já estavam configurados no settings — este teste
    comprova que o header chega ao cliente. Só se emite sobre HTTPS
    (request.is_secure()); em HTTP não há header.
    """
    response = api_client.get("/api/csrf/", secure=True)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    hsts = response["Strict-Transport-Security"]
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts
    assert "preload" in hsts


# ---------------------------------------------------------------------------
# 7. Rate limiting (anti força bruta / contas em massa)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_throttle_429_na_sexta_tentativa(api_client, django_user_model):
    """6ª tentativa de login em menos de um minuto → 429 Too Many Requests.

    Scope "login" (ScopedRateThrottle, 5/min por IP) aplicado via
    TokenObtainPairThrottledView. O throttle corre ANTES do check CSRF
    (initial() vs post()), por isso as 6 tentativas chegam ao rate limit
    mesmo com CSRF válido.
    """
    django_user_model.objects.create_user(
        username="admin", email="admin@finflow.com", password="senha-forte-123"
    )
    csrf = _obtener_csrf(api_client)

    for _ in range(5):
        response = api_client.post(
            TOKEN_URL,
            {"username": "admin", "password": "senha-errada"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    response = api_client.post(
        TOKEN_URL,
        {"username": "admin", "password": "senha-errada"},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_registro_throttle_429_na_sexta_tentativa(api_client):
    """6ª criação de conta em menos de um minuto → 429 (anti contas em massa)."""
    for i in range(5):
        response = api_client.post(
            REGISTRO_URL,
            {
                "nome": f"Usuário {i}",
                "email": f"usuario{i}@finflow.com",
                "password": SENHA_FORTE,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

    response = api_client.post(
        REGISTRO_URL,
        {
            "nome": "Usuário 6",
            "email": "usuario6@finflow.com",
            "password": SENHA_FORTE,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# ---------------------------------------------------------------------------
# 8. Limite de payload (mitigação básica de DoS)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_payload_grande_rejeitado_413(auth_client):
    """Payload > 1 MB → 413 Request Entity Too Large.

    Middleware MaxBodySizeMiddleware (Content-Length > MAX_BODY_SIZE_BYTES).
    DDoS real exige infraestructura (WAF/CDN) — ver README.
    """
    response = auth_client.post(
        CLIENTES_URL,
        {"nome": "X" * (1024 * 1024 + 100)},
        format="json",
    )

    assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE