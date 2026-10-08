"""Testes de regressão do deploy no Render.

Cobrem exatamente o cenário que derrubava o deploy com "Timed Out":
o Render bate no health check com o host real do serviço (que leva
sufixo aleatório, ex. finflow-backend-z6zm.onrender.com) e o frontend
chama a API de uma origem com sufixo diferente — qualquer 400
(DisallowedHost) ou 403 (CSRF/CORS) mata o deploy.

Cobrem também o CSRF CROSS-ORIGIN: a SPA não consegue ler o cookie
csrftoken do domínio da API (Same-Origin Policy), então o duplo envio
clássico é impossível — o backend aceita a dupla chave X-CSRFSecret +
cookie (ver apps.usuarios.views).
"""
import pytest
from django.test import Client

# Hosts/origens que simulam o ambiente real do Render (sufixos aleatórios
# propositadamente DIFERENTES entre backend e frontend).
HOST_BACKEND = "finflow-backend-z6zm.onrender.com"
ORIGIN_FRONTEND = "https://finflow-frontend-x1y2.onrender.com"

ENV = dict(
    # Lista: ALLOWED_HOSTS precisa ser iterável de padrões (nas settings de
    # produção env_list() já converte a variável de ambiente em lista).
    ALLOWED_HOSTS=[HOST_BACKEND],
    # Política SEGURA (lista exata, sem wildcard): apenas a origem real do
    # frontend (via fromService no render.yaml) e do próprio backend. LISTA
    # (não string): em produção env_list() já divide a env var — o corsheaders
    # itera os itens, e uma string aqui viraria iteração caractere a caractere.
    CORS_ALLOWED_ORIGINS=[
        "https://finflow-frontend-x1y2.onrender.com",
        f"https://{HOST_BACKEND}",
    ],
    CSRF_TRUSTED_ORIGINS=[
        "https://finflow-frontend-x1y2.onrender.com",
        f"https://{HOST_BACKEND}",
    ],
    SECURE_SSL_REDIRECT=False,
    TRUST_PROXY=True,
    # Deploy cross-origin (render.yaml): cookies só viajam no XHR com
    # SameSite=None, e por HTTPS (Secure=True nos cookies).
    CSRF_COOKIE_SAMESITE="None",
    CSRF_COOKIE_SECURE=True,
)

# Origem CO-TENANT: outro app gratuito hospedado na MESMA plataforma — NÃO
# está na lista de origens e NÃO deve receber Access-Control-Allow-Origin
# nem conseguir ler o X-CSRFSecret (com credenciais + regex amplo, poderia;
# ver comentário do CORS_ALLOWED_ORIGIN_REGEXES em finflow/settings.py).
ORIGIN_COTENANT = "https://app-maliciosa-x9k7.onrender.com"


def _client(enforce_csrf=False):
    # secure=True: requisições como https (igual à borda do Render).
    # enforce_csrf: exigir o duplo envio de verdade (Client padrão BYPASSA o
    # CsrfViewMiddleware com enforce_csrf_checks=False).
    return Client(HTTP_HOST=HOST_BACKEND, secure=True, enforce_csrf_checks=enforce_csrf)


def test_healthz_com_host_real_do_render(settings):
    """O health check do Render responde 200 com o host real (com sufixo)."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    response = _client().get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_csrf_view_expõe_segredo_no_header_e_cookie_na_resposta(settings):
    """GET /api/csrf/ devolve o segredo CSRF no header X-CSRFSecret."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    response = _client().get("/api/csrf/")
    assert response.status_code == 204
    # Segredo cru (32 chars) exposto no header de resposta; a SPA cross-origin
    # só consegue lê-lo porque o CORS autoriza (CORS_EXPOSE_HEADERS).
    assert len(response["X-CSRFSecret"]) == 32
    # O cookie também vai no Set-Cookie: em Django 5.1+ ele guarda o próprio
    # segredo cru (32 chars); até a 5.0 guardava o token mascarado (64).
    cookie = response.cookies["csrftoken"]
    assert len(cookie.value) in (32, 64)
    # SameSite None no deploy cross-origin (cookies só viajam em XHR com
    # SameSite=None); Secure presente porque a requisição é https.
    assert cookie["samesite"] == "None"
    assert cookie["secure"] is True


@pytest.mark.django_db
def test_csrf_aceita_origem_com_sufixo(settings):
    """O frontend com sufixo aleatório passa no CSRF_TRUSTED_ORIGINS."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    response = _client().post(
        "/api/token/",
        data='{"username":"x","password":"y"}',
        content_type="application/json",
        HTTP_ORIGIN=ORIGIN_FRONTEND,
        HTTP_X_CSRFTOKEN="token-inexistente",
    )
    # 401 (credenciais erradas) = CSRF aceite; 403 = origem rejeitada.
    assert response.status_code == 401


def test_preflight_cors_de_origem_com_sufixo(settings):
    """Preflight da origem EXATA do frontend recebe Allow-Origin + credenciais."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    response = _client().options(
        "/api/token/",
        HTTP_ORIGIN=ORIGIN_FRONTEND,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
    )
    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == ORIGIN_FRONTEND
    assert response["Access-Control-Allow-Credentials"] == "true"


def test_cors_nao_autoriza_co_tenant_da_plataforma(settings):
    """Origem co-tenant (outro app no Render) NÃO recebe Allow-Origin.

    Sem CORS, o navegador bloqueia a leitura de QUALQUER resposta — inclusive
    do header X-CSRFSecret exposto no GET /api/csrf/ (CORS_EXPOSE_HEADERS só
    vale para origens autorizadas). É isso que mantém o fallback CSRF
    cross-origin seguro contra outros apps da plataforma.
    """
    for key, value in ENV.items():
        setattr(settings, key, value)
    response = _client().options(
        "/api/token/",
        HTTP_ORIGIN=ORIGIN_COTENANT,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
    )
    assert response.status_code == 200
    assert not response.has_header("Access-Control-Allow-Origin")


def test_co_tenant_nao_consegue_ler_o_segredo_csrf(settings):
    """GET /api/csrf/ não expõe o X-CSRFSecret para origem não autorizada."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    response = _client().get("/api/csrf/", HTTP_ORIGIN=ORIGIN_COTENANT)
    assert response.status_code == 204
    assert not response.has_header("Access-Control-Allow-Origin")
    # O header existe na resposta HTTP, mas SEM Access-Control-Allow-Origin o
    # navegador NUNCA o entrega ao JS da origem co-tenant.
    assert response.has_header("X-CSRFSecret")


# ===========================================================================
# CSRF cross-origin: dupla chave X-CSRFSecret + cookie csrftoken
# ===========================================================================


def _segredo_e_cookie():
    """GET /api/csrf/ como o navegador faria: devolve (segredo, cookie)."""
    response = _client().get("/api/csrf/")
    return response["X-CSRFSecret"], response.cookies["csrftoken"].value


@pytest.mark.django_db
def test_login_cross_origin_com_segredo_e_cookie_passa_no_csrf(settings, user):
    """Dupla chave X-CSRFSecret (header) + cookie csrftoken autentica o POST.

    Equivale ao fluxo real da SPA cross-origin: o cookie viaja embutido no
    Client (o navegador o anexaria sozinho) e o segredo vai no header.
    """
    for key, value in ENV.items():
        setattr(settings, key, value)
    segredo, cookie = _segredo_e_cookie()

    client = _client(enforce_csrf=True)
    client.cookies["csrftoken"] = cookie
    response = client.post(
        "/api/token/",
        data=f'{{"username":"{user.username}","password":"senha-forte-123"}}',
        content_type="application/json",
        HTTP_ORIGIN=ORIGIN_FRONTEND,
        HTTP_X_CSRFSECRET=segredo,
    )
    # 200 = CSRF aceite pela dupla chave e credenciais válidas.
    assert response.status_code == 200
    assert "access" in response.json()
    # Sem rotação no POST (o process_request do csrf_protect relê o cookie
    # depois do fallback — rotação aqui seria sobrescrita sem efeito): a
    # resposta não precisa trazer Set-Cookie de csrftoken.
    assert response.status_code == 200


@pytest.mark.django_db
def test_login_cross_origin_com_segredo_errado_nao_bloqueia(settings, user):
    """Segredo errado no login NÃO gera mais 403 CSRF.

    O login não exige mais CSRF (ver TokenObtainPairThrottledView): sem a
    dupla chave válida a request simplesmente segue para a validação de
    credenciais — com credenciais corretas, 200 (não 403 CSRF).
    """
    for key, value in ENV.items():
        setattr(settings, key, value)
    _segredo, cookie = _segredo_e_cookie()

    client = _client(enforce_csrf=True)
    client.cookies["csrftoken"] = cookie
    response = client.post(
        "/api/token/",
        data=f'{{"username":"{user.username}","password":"senha-forte-123"}}',
        content_type="application/json",
        HTTP_ORIGIN=ORIGIN_FRONTEND,
        HTTP_X_CSRFSECRET="A" * 32,
    )
    # CSRF ignorado no login: credenciais válidas autenticam normalmente.
    assert response.status_code == 200
    assert "access" in response.json()


@pytest.mark.django_db
def test_login_cross_origin_sem_cookie_nao_da_403(settings):
    """Login sem cookie csrftoken NÃO gera mais 403 CSRF.

    O login não exige mais CSRF (ver TokenObtainPairThrottledView): sem o
    cookie, a dupla chave não se forma e a request segue para a validação
    de credenciais — com credenciais inválidas, 401 (não 403 CSRF).
    """
    for key, value in ENV.items():
        setattr(settings, key, value)
    segredo, _cookie = _segredo_e_cookie()

    client = _client(enforce_csrf=True)
    response = client.post(  # SEM cookie csrftoken
        "/api/token/",
        data='{"username":"x","password":"y"}',
        content_type="application/json",
        HTTP_ORIGIN=ORIGIN_FRONTEND,
        HTTP_X_CSRFSECRET=segredo,
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_fallback_nao_marca_request_com_segredo_invalido(settings):
    """Segredo inválido não marca a request (o middleware segue o fluxo normal)."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    _segredo, cookie = _segredo_e_cookie()

    from django.test import RequestFactory

    from apps.usuarios.views import _aplicar_csrf_fallback_cross_origin

    request = RequestFactory(HTTP_HOST=HOST_BACKEND).get("/api/csrf/")
    request.COOKIES["csrftoken"] = cookie
    request.META["HTTP_X_CSRFSECRET"] = "Z" * 32

    _aplicar_csrf_fallback_cross_origin(request)

    assert not getattr(request, "_dont_enforce_csrf_checks", False)
    # Sem rotação: o par cookie/segredo continua válido para as escritas.
    assert request.META.get("CSRF_COOKIE", cookie) == cookie


@pytest.mark.django_db
def test_fallback_same_origin_nao_interfere_no_fluxo_classico(settings, user):
    """Sem X-CSRFSecret, a validação clássica (cookie + X-CSRFToken) vale.

    Garante que o fallback não quebrou o duplo envio clássico usado em dev
    (mesma origem via proxy do Vite).
    """
    for key, value in ENV.items():
        setattr(settings, key, value)
    _segredo, cookie = _segredo_e_cookie()

    client = _client(enforce_csrf=True)
    client.cookies["csrftoken"] = cookie
    response = client.post(
        "/api/token/",
        data=f'{{"username":"{user.username}","password":"senha-forte-123"}}',
        content_type="application/json",
        HTTP_X_CSRFTOKEN=cookie,
    )
    assert response.status_code == 200
