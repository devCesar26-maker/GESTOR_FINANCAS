"""
Testes do reset de senha por e-mail e do login/cadastro com Google.

Cobre a spec do produto:
- POST /api/auth/password-reset/ — envia link com token único de 1 hora
  (PasswordResetTokenGenerator) SEM revelar se o e-mail existe;
- POST /api/auth/password-reset/confirm/ — valida uid+token e redefine a
  senha (política forte; token de uso único);
- POST /api/auth/google/ — troca id_token do Google por JWTs nativos
  (access no body, refresh no cookie httpOnly).
"""
import base64

import pytest
from django.test import override_settings
from rest_framework import status

from apps.usuarios.views import REFRESH_COOKIE_NAME

RESET_URL = "/api/auth/password-reset/"
RESET_CONFIRM_URL = "/api/auth/password-reset/confirm/"
GOOGLE_URL = "/api/auth/google/"
TOKEN_URL = "/api/token/"

SENHA_NOVA = "Senha-Nova-456!"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _solicitar_reset(api_client, email="admin@finflow.com"):
    return api_client.post(RESET_URL, {"email": email}, format="json")


def _extrair_uid_token(html: str) -> tuple[str, str]:
    """Extrai (uid, token) do link contido no e-mail HTML."""
    inicio = html.index("/redefinir-senha/") + len("/redefinir-senha/")
    fim = html.index('"', inicio)
    partes = html[inicio:fim].split("/")
    assert len(partes) == 2, f"Link inesperado: {html[inicio:fim]}"
    return partes[0], partes[1]


def _uid_de(user) -> str:
    return base64.urlsafe_b64encode(str(user.pk).encode()).decode().rstrip("=")


# ---------------------------------------------------------------------------
# Solicitação de reset (POST /api/auth/password-reset/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_solicitar_reset_envia_email_com_link(api_client, mailoutbox, user):
    response = _solicitar_reset(api_client)

    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.to == [user.email]
    # Assunto + link de redefinição no corpo HTML.
    assert "Redefinição" in email.subject
    html = email.alternatives[0][0]
    assert "/redefinir-senha/" in html
    uid, token = _extrair_uid_token(html)
    # uid decodifica para o pk do usuário.
    import urllib.parse

    from django.utils.http import urlsafe_base64_decode

    assert int(urlsafe_base64_decode(uid)) == user.pk
    assert token  # token não vazio


@pytest.mark.django_db
def test_solicitar_reset_email_inexistente_nao_revela_conta(api_client, mailoutbox):
    """Resposta idêntica (200) com ou sem conta — anti user-enumeration."""
    response = _solicitar_reset(api_client, "fantasma@finflow.com")

    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 0
    assert "detail" in response.data


@pytest.mark.django_db
def test_solicitar_reset_email_invalido_responde_400(api_client, mailoutbox):
    response = _solicitar_reset(api_client, "nao-e-email")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_solicitar_reset_case_insensitive(api_client, mailoutbox, user):
    """E-mail com caixa diferente encontra a conta (lookup iexact)."""
    response = _solicitar_reset(api_client, user.email.upper())

    assert response.status_code == status.HTTP_200_OK
    assert len(mailoutbox) == 1


@pytest.mark.django_db
def test_solicitar_reset_limitado_a_5_por_minuto(api_client, user):
    """Rate limit do scope 'senha': 5/min por IP (anti e-mail bombing)."""
    for _ in range(5):
        response = _solicitar_reset(api_client)
        assert response.status_code == status.HTTP_200_OK

    response = _solicitar_reset(api_client)
    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


# ---------------------------------------------------------------------------
# Confirmação do reset (POST /api/auth/password-reset/confirm/)
# ---------------------------------------------------------------------------


def _criar_token(user) -> tuple[str, str]:
    from django.contrib.auth.tokens import PasswordResetTokenGenerator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = PasswordResetTokenGenerator().make_token(user)
    return uid, token


def _confirmar(api_client, uid, token, password=SENHA_NOVA):
    return api_client.post(
        RESET_CONFIRM_URL,
        {"uid": uid, "token": token, "password": password},
        format="json",
    )


def _login(api_client, username, password):
    api_client.get("/api/csrf/")
    csrf = api_client.cookies["csrftoken"].value
    return api_client.post(
        TOKEN_URL,
        {"username": username, "password": password},
        format="json",
        HTTP_X_CSRFTOKEN=csrf,
    )


@pytest.mark.django_db
def test_reset_confirm_redefine_senha_e_permite_login(api_client, user):
    uid, token = _criar_token(user)

    response = _confirmar(api_client, uid, token)

    assert response.status_code == status.HTTP_200_OK
    # A senha antiga não serve mais; a nova loga via JWT.
    user.refresh_from_db()
    assert user.check_password(SENHA_NOVA)
    login = _login(api_client, user.username, SENHA_NOVA)
    assert login.status_code == status.HTTP_200_OK
    assert "access" in login.data


@pytest.mark.django_db
def test_reset_confirm_token_e_de_uso_unico(api_client, user):
    uid, token = _criar_token(user)

    primeira = _confirmar(api_client, uid, token)
    assert primeira.status_code == status.HTTP_200_OK

    # Mesmo token não serve de novo (a hash da senha mudou).
    segunda = _confirmar(api_client, uid, token, "Outra-Senha-789!")
    assert segunda.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_reset_confirm_rejeita_token_invalido(api_client, user):
    uid, _token = _criar_token(user)

    response = _confirmar(api_client, uid, "token-falso")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    user.refresh_from_db()
    assert not user.check_password(SENHA_NOVA)


@pytest.mark.django_db
def test_reset_confirm_rejeita_uid_invalido(api_client, user):
    response = _confirmar(api_client, "!!!nao-base64!!!", "qualquer-token")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_reset_confirm_rejeita_senha_fraca(api_client, user):
    uid, token = _criar_token(user)

    response = _confirmar(api_client, uid, token, "fraca123")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "password" in response.data
    # Senha permanece a antiga.
    user.refresh_from_db()
    assert not user.check_password("fraca123")


@pytest.mark.django_db
def test_reset_confirm_campo_faltante_responde_400(api_client, user):
    response = api_client.post(RESET_CONFIRM_URL, {"uid": "x"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Login/Cadastro com Google (POST /api/auth/google/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_google_sem_config_responde_503(api_client):
    """Sem GOOGLE_CLIENT_ID configurado, endpoint responde 503 claro."""
    response = api_client.post(GOOGLE_URL, {"id_token": "abc"}, format="json")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


@override_settings(GOOGLE_CLIENT_ID="test-client-id", GOOGLE_CLIENT_SECRET="secret")
@pytest.mark.django_db
def test_google_sem_id_token_responde_400(api_client):
    response = api_client.post(GOOGLE_URL, {}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "id_token" in response.data


@override_settings(GOOGLE_CLIENT_ID="test-client-id", GOOGLE_CLIENT_SECRET="secret")
@pytest.mark.django_db
def test_google_id_token_invalido_responde_400(api_client, monkeypatch):
    """Token que falha na validação (assinatura/audience) vira 400 claro."""

    def _token_invalido(self, request, token):
        from django.core.exceptions import ValidationError

        raise ValidationError("invalid_token")

    from allauth.socialaccount.providers.google.provider import GoogleProvider

    monkeypatch.setattr(GoogleProvider, "verify_token", _token_invalido)

    response = api_client.post(GOOGLE_URL, {"id_token": "token-lixo"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


@override_settings(GOOGLE_CLIENT_ID="test-client-id", GOOGLE_CLIENT_SECRET="secret")
@pytest.mark.django_db
def test_google_login_usuario_existente_vincula_sem_duplicar(api_client, user, monkeypatch):
    """Usuário local (por senha) com o mesmo e-mail é VINCULADO, não duplicado.

    O contrato do login social é idêntico ao login JWT: access no body,
    refresh NUNCA no body (cookie httpOnly com o mesmo nome/path).
    """

    def _verifica(self, request, token):
        from django.contrib.auth import get_user_model

        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount, SocialLogin

        login = SocialLogin()
        login.provider = self  # GoogleProvider (como em sociallogin_from_response)
        login.account = SocialAccount(
            provider="google", uid="google-uid-123", extra_data={}
        )
        # Instância NÃO salva com o e-mail do usuário local (como o Google
        # entrega) — a associação com a conta existente é papel do adapter.
        login.user = get_user_model()(
            username=user.email, email=user.email, first_name="Admin"
        )
        login.email_addresses = [
            EmailAddress(email=user.email, verified=True, primary=True)
        ]
        return login

    from allauth.socialaccount.providers.google.provider import GoogleProvider

    monkeypatch.setattr(GoogleProvider, "verify_token", _verifica)

    response = api_client.post(GOOGLE_URL, {"id_token": "ok"}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    assert "refresh" not in response.data
    # Cookie httpOnly do refresh: mesmo contrato do login por senha.
    cookie = response.cookies[REFRESH_COOKIE_NAME]
    assert cookie.value
    assert cookie["httponly"] is True
    # NÃO criou usuário duplicado com o mesmo e-mail.
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert User.objects.filter(email__iexact=user.email).count() == 1
    # Senha original PRESERVADA (o wipe de senha do allauth nunca deve rodar).
    user.refresh_from_db()
    assert user.has_usable_password()
    # SocialAccount vinculado ao usuário local.
    from allauth.socialaccount.models import SocialAccount

    assert SocialAccount.objects.filter(provider="google", user=user).exists()


@override_settings(GOOGLE_CLIENT_ID="test-client-id", GOOGLE_CLIENT_SECRET="secret")
@pytest.mark.django_db
def test_google_cria_conta_para_email_novo(api_client, monkeypatch):
    """E-mail novo: cria a conta (username = e-mail, sem senha) e loga."""
    from django.contrib.auth import get_user_model

    User = get_user_model()

    def _verifica(self, request, token):
        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount, SocialLogin

        login = SocialLogin()
        login.provider = self
        login.account = SocialAccount(
            provider="google", uid="google-uid-novo", extra_data={}
        )
        login.user = User(
            username="novo@gmail.com", email="novo@gmail.com", first_name="Novo"
        )
        login.email_addresses = [
            EmailAddress(email="novo@gmail.com", verified=True, primary=True)
        ]
        return login

    from allauth.socialaccount.providers.google.provider import GoogleProvider

    monkeypatch.setattr(GoogleProvider, "verify_token", _verifica)

    response = api_client.post(GOOGLE_URL, {"id_token": "ok"}, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert "access" in response.data
    user = User.objects.get(email__iexact="novo@gmail.com")
    assert user.username == "novo@gmail.com"  # padrão FinFlow
    # Sem senha: login exclusivo via Google até definir uma pelo reset.
    assert not user.has_usable_password()


@override_settings(GOOGLE_CLIENT_ID="test-client-id", GOOGLE_CLIENT_SECRET="secret")
@pytest.mark.django_db
def test_google_conta_desativada_nao_cria_duplicata(api_client, django_user_model, monkeypatch):
    """E-mail de conta INATIVA: rejeita em vez de criar segunda conta."""
    django_user_model.objects.create_user(
        username="morto@finflow.com",
        email="morto@finflow.com",
        password="Senha-X-123!",
        is_active=False,
    )

    def _verifica(self, request, token):
        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount, SocialLogin

        User = django_user_model
        login = SocialLogin()
        login.provider = self
        login.account = SocialAccount(provider="google", uid="u-x", extra_data={})
        login.user = User(
            username="morto@finflow.com", email="morto@finflow.com"
        )
        login.email_addresses = [
            EmailAddress(email="morto@finflow.com", verified=True, primary=True)
        ]
        return login

    from allauth.socialaccount.providers.google.provider import GoogleProvider

    monkeypatch.setattr(GoogleProvider, "verify_token", _verifica)

    response = api_client.post(GOOGLE_URL, {"id_token": "ok"}, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    from django.contrib.auth import get_user_model

    User = get_user_model()
    assert User.objects.filter(email__iexact="morto@finflow.com").count() == 1
