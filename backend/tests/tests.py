"""Testes unitários de segurança (OWASP ZAP Remediation).

Valida:
1. Cookie de Refresh Token com HttpOnly=True, Secure=True e SameSite='Lax'.
2. Exclusividade de autenticação via header 'Authorization: Bearer ' ou body POST (sem vazamento em URLs).
3. Presença dos cabeçalhos de segurança HTTP (X-Frame-Options, X-Content-Type-Options, Content-Security-Policy).
4. Sanitização do cabeçalho Server (sem versão exposta do servidor).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


class SecurityRemediationTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.username = "usuario_seguranca"
        self.password = "Senha-Forte-123!"
        self.user = User.objects.create_user(
            username=self.username,
            email="seguranca@finflow.com",
            password=self.password,
        )
        # Obter cookie CSRF inicial
        csrf_res = self.client.get("/api/csrf/")
        self.csrf_token = csrf_res.cookies.get("csrftoken").value

    def test_cookie_refresh_token_httponly_secure_samesite_lax(self):
        """Item 1: Cookie de Refresh Token possui HttpOnly=True, Secure=True e SameSite='Lax'."""
        response = self.client.post(
            "/api/token/",
            {"username": self.username, "password": self.password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("refresh_token", response.cookies)

        cookie = response.cookies["refresh_token"]
        self.assertTrue(cookie["httponly"], "O cookie de refresh token deve possuir HttpOnly=True")
        self.assertTrue(cookie["secure"], "O cookie de refresh token deve possuir Secure=True")
        self.assertEqual(cookie["samesite"], "Lax", "O cookie de refresh token deve possuir SameSite='Lax'")

    def test_token_exclusivamente_por_header_ou_body_sem_vazamento_url(self):
        """Item 2: Tokens de acesso são aceitos exclusivamente por Header Authorization ou POST body."""
        # 1. Sem header Authorization -> 401
        res_no_auth = self.client.get("/api/clientes/")
        self.assertEqual(res_no_auth.status_code, status.HTTP_401_UNAUTHORIZED)

        # 2. Token enviado via Query String -> deve ser IGNORADO e retornar 401
        res_query_token = self.client.get("/api/clientes/?token=fake-token-na-url")
        self.assertEqual(res_query_token.status_code, status.HTTP_401_UNAUTHORIZED)

        # 3. Token correto via Header 'Authorization: Bearer <token>' -> 200 OK
        login_res = self.client.post(
            "/api/token/",
            {"username": self.username, "password": self.password},
            format="json",
            HTTP_X_CSRFTOKEN=self.csrf_token,
        )
        access_token = login_res.data["access"]

        res_bearer = self.client.get(
            "/api/clientes/",
            HTTP_AUTHORIZATION=f"Bearer {access_token}",
        )
        self.assertEqual(res_bearer.status_code, status.HTTP_200_OK)

    def test_cabecalhos_http_de_protecao(self):
        """Item 3: Presença de X-Frame-Options, X-Content-Type-Options e Content-Security-Policy."""
        response = self.client.get("/api/csrf/")

        # Anti-Clickjacking via X-Frame-Options
        self.assertIn("X-Frame-Options", response)
        self.assertEqual(response["X-Frame-Options"], "DENY")

        # Anti MIME-sniffing
        self.assertIn("X-Content-Type-Options", response)
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")

        # Content-Security-Policy (CSP)
        self.assertIn("Content-Security-Policy", response)
        csp = response["Content-Security-Policy"]
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("default-src 'self'", csp)

    def test_sanitizacao_cabecalho_server(self):
        """Item 4: Header Server é sanitizado sem expor versão do servidor/software."""
        response = self.client.get("/api/csrf/")
        self.assertIn("Server", response)
        self.assertNotIn("gunicorn", response["Server"].lower())
        self.assertNotIn("nginx", response["Server"].lower())
        self.assertEqual(response["Server"], "FinFlow")
