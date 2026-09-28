"""Testes de regressão do deploy no Render.

Cobrem exatamente o cenário que derrubava o deploy com "Timed Out":
o Render bate no health check com o host real do serviço (que leva
sufixo aleatório, ex. finflow-backend-z6zm.onrender.com) e o frontend
chama a API de uma origem com sufixo diferente — qualquer 400
(DisallowedHost) ou 403 (CSRF/CORS) mata o deploy.
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
    CSRF_TRUSTED_ORIGINS="https://*.onrender.com,https://finflow-backend-z6zm.onrender.com",
    CORS_ALLOWED_ORIGIN_REGEXES=r"^https://[a-z0-9-]+\.onrender\.com$",
    SECURE_SSL_REDIRECT=False,
    TRUST_PROXY=True,
)


def _client():
    # secure=True: requisições como https (igual à borda do Render).
    return Client(HTTP_HOST=HOST_BACKEND, secure=True)


def test_healthz_com_host_real_do_render(settings):
    """O health check do Render responde 200 com o host real (com sufixo)."""
    for key, value in ENV.items():
        setattr(settings, key, value)
    response = _client().get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    """Preflight de origem com sufixo aleatório recebe Allow-Origin."""
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
