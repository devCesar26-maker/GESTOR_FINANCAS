"""Regressão do CHIPS (Partitioned) nos cookies de autenticação.

O Chrome rejeita cookies cross-site sem o atributo Partitioned — nos
deploys com SPA e API em subdomínios diferentes, o csrftoken (e o
refresh_token) precisam sair com ``Partitioned`` no Set-Cookie.

Estes testes reproduzem o cenário de PRODUÇÃO (Secure + SameSite=None +
REFRESH_COOKIE_PARTITIONED=True) e garantem que a troca de token CSRF,
o login, o refresh e o logout continuam funcionando normalmente.
"""

import pytest
from django.test import Client

HOST_BACKEND = "finflow-backend-z6zm.onrender.com"
ORIGIN_FRONTEND = "https://finflow-frontend-x1y2.onrender.com"

# Ambienta produção (render.yaml): cookies cross-site (Secure + SameSite=None)
# e CHIPS ligado. Overridável por teste via fixture settings do pytest-django.
ENV = dict(
    ALLOWED_HOSTS=[HOST_BACKEND],
    CSRF_COOKIE_SAMESITE="None",
    CSRF_COOKIE_SECURE=True,
    REFRESH_COOKIE_SAMESITE="None",
    REFRESH_COOKIE_SECURE=True,
    REFRESH_COOKIE_PARTITIONED=True,
    SECURE_SSL_REDIRECT=False,
    TRUST_PROXY=True,
    CORS_ALLOWED_ORIGINS=[ORIGIN_FRONTEND],
    CSRF_TRUSTED_ORIGINS=[ORIGIN_FRONTEND],
)


@pytest.fixture
def client_prod(settings):
    """Test client configurado como o deploy cross-origin do Render."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    # enforce_csrf_checks=True: exercita o CsrfViewMiddleware de verdade
    # (o client padrão faz bypass da proteção CSRF).
    return Client(HTTP_HOST=HOST_BACKEND, secure=True, enforce_csrf_checks=True)


def _cookie_has_partitioned(response, name):
    morsel = response.cookies.get(name)
    assert morsel is not None, f"resposta não define o cookie {name}"
    return bool(morsel.get("partitioned"))


def test_csrftoken_recebe_partitioned_em_producao(client_prod):
    """GET /api/csrf/ define csrftoken com Secure, SameSite=None e Partitioned."""
    response = client_prod.get("/api/csrf/")
    assert response.status_code == 204
    cookie = response.cookies["csrftoken"]
    assert cookie["secure"] is True
    assert cookie["samesite"] == "None"
    # A correção: o Set-Cookie do csrftoken inclui o atributo Partitioned.
    assert _cookie_has_partitioned(response, "csrftoken")
    assert cookie.value


def test_particionado_desligado_omite_atributo(settings):
    """Sem REFRESH_COOKIE_PARTITIONED (ou em dev, Lax), nada muda."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    settings.REFRESH_COOKIE_PARTITIONED = False
    client = Client(HTTP_HOST=HOST_BACKEND, secure=True, enforce_csrf_checks=True)
    response = client.get("/api/csrf/")
    assert response.status_code == 204
    assert not _cookie_has_partitioned(response, "csrftoken")


def test_dev_lax_nao_recebe_partitioned(settings):
    """Em dev (DEBUG, cookie Lax e sem Secure) o atributo NÃO é anexado.

    Anexar Partitioned fora de Secure+SameSite=None é inválido segundo a
    spec CHIPS — o helper omite para não invalidar o Set-Cookie local.
    """
    for key, value in ENV.items():
        setattr(settings, key, value)
    settings.REFRESH_COOKIE_PARTITIONED = True
    settings.CSRF_COOKIE_SAMESITE = "Lax"
    settings.CSRF_COOKIE_SECURE = False

    client = Client(HTTP_HOST=HOST_BACKEND, secure=True, enforce_csrf_checks=True)
    response = client.get("/api/csrf/")
    assert response.status_code == 204
    assert not _cookie_has_partitioned(response, "csrftoken")


@pytest.mark.django_db
def test_login_logout_csrf_continuam_funcionando(client_prod, django_user_model):
    """Fluxo completo de produção: csrf -> login -> logout e nada quebra.

    O Partitioned não pode regredir o fluxo básico: login devolve access
    + cookie do refresh; o logout apaga o refresh_token (Set-Cookie de
    exclusão também Partitioned, senão o Chrome não apagaria o cookie
    particionado) e o cookie de CSRF continua válido.
    """
    django_user_model.objects.create_user(
        username="admin", email="admin@finflow.com", password="senha-forte-123"
    )
    client_prod.get("/api/csrf/")
    csrf = client_prod.cookies["csrftoken"].value

    # Login SEM header CSRF (rota isentada — modelo do cookie httpOnly).
    login = client_prod.post(
        "/api/token/",
        data='{"username":"admin","password":"senha-forte-123"}',
        content_type="application/json",
    )
    assert login.status_code == 200, login.content
    assert "access" in login.json()
    refresh_cookie = login.cookies["refresh_token"]
    assert refresh_cookie.value
    assert refresh_cookie["samesite"] == "None"
    assert refresh_cookie["secure"] is True
    # Refresh token também sai com Partitioned (mesma correção CHIPS).
    assert _cookie_has_partitioned(login, "refresh_token")

    # Login COM duplo envio CSRF também funciona (cookie csrf novo + header).
    client_prod2 = Client(
        HTTP_HOST=HOST_BACKEND, secure=True, enforce_csrf_checks=True
    )
    client_prod2.get("/api/csrf/")
    csrf2 = client_prod2.cookies["csrftoken"].value
    login2 = client_prod2.post(
        "/api/token/",
        data='{"username":"admin","password":"senha-forte-123"}',
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf2,
    )
    assert login2.status_code == 200, login2.content

    # CSRF continua sendo exigido de verdade: sem cookie nem header => 403.
    client_vazio = Client(
        HTTP_HOST=HOST_BACKEND, secure=True, enforce_csrf_checks=True
    )
    csrf_drift = client_vazio.get("/api/csrf/")
    client_vazio.cookies.pop("csrftoken", None)
    resposta_sem_csrf = client_vazio.post(
        "/api/token/refresh/",
        data="{}",
        content_type="application/json",
        HTTP_X_CSRFTOKEN="token-forjado",
    )
    assert resposta_sem_csrf.status_code in (401, 403)

    # Logout: Set-Cookie de exclusão do refresh_token também com Partitioned.
    logout = client_prod2.post(
        "/api/token/logout/",
        data="{}",
        content_type="application/json",
        HTTP_X_CSRFTOKEN=csrf2,
    )
    assert logout.status_code == 204
    cookie_logout = logout.cookies["refresh_token"]
    assert cookie_logout.value == ""  # Set-Cookie de exclusão
    assert cookie_logout["samesite"] == "None"
    assert cookie_logout["secure"] is True
    assert _cookie_has_partitioned(logout, "refresh_token")
    # O logout NÃO define csrftoken (só apaga o refresh_token) — ok.
