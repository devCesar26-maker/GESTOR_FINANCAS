"""
Tests do fluxo híbrido de tokens (decisão de arquitetura aprovada).

- Access token: em memória no frontend (nunca localStorage).
- Refresh token: cookie httpOnly (Secure, SameSite=Strict) setado pelo
  backend nas respostas de /api/token/ e /api/token/refresh/ — NUNCA
  aparece no body nem é enviado manualmente pelo frontend.
- CSRF de duplo envio (cookie csrftoken + header X-CSRFToken) obrigatório
  em login e refresh, já que usam cookie de credencial.
"""

import pytest
from rest_framework import status

from apps.usuarios.views import REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH

TOKEN_URL = "/api/token/"
REFRESH_URL = "/api/token/refresh/"
LOGOUT_URL = "/api/token/logout/"
CSRF_URL = "/api/csrf/"

SENHA = "Senha-Forte-123!"


def _obtener_csrf(api_client):
    """GET /api/csrf/ (define o cookie csrftoken) e devolve o token."""
    api_client.get(CSRF_URL)
    return api_client.cookies["csrftoken"].value


def _login(api_client, username="admin", password=SENHA):
    csrf = _obtener_csrf(api_client)
    return api_client.post(
        TOKEN_URL,
        {"username": username, "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )


@pytest.fixture
def usuario(django_user_model):
    return django_user_model.objects.create_user(
        username="admin", email="admin@finflow.com", password=SENHA
    )


# ---------------------------------------------------------------------------
# Cookie httpOnly do refresh token
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_devuelve_solo_access_y_setea_cookie_httponly(api_client, usuario):
    login = _login(api_client)

    assert login.status_code == status.HTTP_200_OK
    # O refresh NUNCA viaja no body: só o access chega ao JavaScript.
    assert "access" in login.data
    assert "refresh" not in login.data

    cookie = login.cookies[REFRESH_COOKIE_NAME]
    assert cookie.value  # el token está no cookie
    assert cookie["httponly"] is True  # JS não pode lerlo (anti-XSS)
    assert cookie["samesite"] == "Lax"  # SameSite=Lax
    assert cookie["path"] == REFRESH_COOKIE_PATH  # menor privilégio
    assert int(cookie["max-age"]) == 7 * 24 * 3600  # 7 días


@pytest.mark.django_db
def test_refresh_lee_el_cookie_sin_body(api_client, usuario):
    login = _login(api_client)
    assert login.cookies[REFRESH_COOKIE_NAME].value
    csrf = api_client.cookies["csrftoken"].value

    # Body vazio: o refresh token chega exclusivamente via cookie.
    response = api_client.post(REFRESH_URL, {}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data


@pytest.mark.django_db
def test_refresh_sin_cookie_devuelve_401(api_client, usuario):
    csrf = _obtener_csrf(api_client)

    response = api_client.post(REFRESH_URL, {}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_refresh_con_cookie_invalido_devuelve_401(api_client, usuario):
    csrf = _obtener_csrf(api_client)
    api_client.cookies[REFRESH_COOKIE_NAME] = "token-invalido"

    response = api_client.post(REFRESH_URL, {}, format="json", HTTP_X_CSRFTOKEN=csrf)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# ---------------------------------------------------------------------------
# CSRF obrigatório em login e refresh (cookie de credencial)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_login_sin_csrf_devuelve_403(csrf_client, usuario):
    """Sem X-CSRFToken → 403 (duplo envio CSRF).

    Usa csrf_client: o padrão do APIClient (enforce_csrf_checks=False)
    FAZ BYPASS do CsrfViewMiddleware — com api_client este teste nunca
    exercitava a proteção de verdade.
    """
    response = csrf_client.post(
        TOKEN_URL,
        {"username": "admin", "password": SENHA},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_refresh_sin_csrf_devuelve_403(csrf_client, usuario):
    """Refresh sem X-CSRFToken → 403, com enforcement real de CSRF."""
    _login(csrf_client)  # deja o cookie de refresh no client
    response = csrf_client.post(REFRESH_URL, {}, format="json")
    assert response.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Logout (única forma de limpiar o cookie httpOnly desde o frontend)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_logout_limpa_el_cookie(api_client, usuario):
    _login(api_client)

    response = api_client.post(LOGOUT_URL)

    assert response.status_code == status.HTTP_204_NO_CONTENT
    cookie = response.cookies[REFRESH_COOKIE_NAME]
    assert cookie["path"] == REFRESH_COOKIE_PATH
    assert int(cookie["max-age"]) == 0  # cookie expirado: navegador o borra