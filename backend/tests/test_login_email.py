"""Login JWT aceita username OU e-mail (ACCOUNT_AUTHENTICATION_METHOD)."""
import pytest

@pytest.mark.django_db
def test_login_aceita_username_e_email(api_client, user):
    from django.conf import settings
    assert settings.AUTHENTICATION_BACKENDS[0] == "django.contrib.auth.backends.ModelBackend"
    assert "allauth.account.auth_backends.AuthenticationBackend" in settings.AUTHENTICATION_BACKENDS

    api_client.get("/api/csrf/")
    csrf = api_client.cookies["csrftoken"].value

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
