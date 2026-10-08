"""Login JWT aceita username OU e-mail (TokenObtainPairEmailSerializer)."""
import pytest


def _csrf(api_client):
    api_client.get("/api/csrf/")
    return api_client.cookies["csrftoken"].value


@pytest.mark.django_db
def test_login_aceita_username_e_email(api_client, user):
    csrf = _csrf(api_client)

    r_user = api_client.post(
        "/api/token/",
        {"username": user.username, "password": "senha-forte-123"},
        format="json", HTTP_X_CSRFTOKEN=csrf,
    )
    assert r_user.status_code == 200, r_user.data
    assert "access" in r_user.data

    r_email = api_client.post(
        "/api/token/",
        {"username": user.email, "password": "senha-forte-123"},
        format="json", HTTP_X_CSRFTOKEN=csrf,
    )
    assert r_email.status_code == 200, r_email.data
    assert "access" in r_email.data


@pytest.mark.django_db
def test_login_email_case_insensitive(api_client, user):
    """E-mail digitado com caixa diferente também autentica (iexact)."""
    csrf = _csrf(api_client)

    r = api_client.post(
        "/api/token/",
        {"username": user.email.upper(), "password": "senha-forte-123"},
        format="json", HTTP_X_CSRFTOKEN=csrf,
    )
    assert r.status_code == 200, r.data
    assert "access" in r.data


@pytest.mark.django_db
def test_login_email_senha_errada_rejeitado(api_client, user):
    """E-mail resolvido, mas senha errada segue dando 401 (sem bypass)."""
    csrf = _csrf(api_client)

    r = api_client.post(
        "/api/token/",
        {"username": user.email, "password": "senha-errada-123"},
        format="json", HTTP_X_CSRFTOKEN=csrf,
    )
    assert r.status_code == 401, r.data


@pytest.mark.django_db
def test_login_email_inexistente_rejeitado(api_client, user):
    """E-mail sem conta correspondente: tratado como username → 401."""
    csrf = _csrf(api_client)

    r = api_client.post(
        "/api/token/",
        {"username": "ninguem@finflow.com", "password": "senha-forte-123"},
        format="json", HTTP_X_CSRFTOKEN=csrf,
    )
    assert r.status_code == 401, r.data
