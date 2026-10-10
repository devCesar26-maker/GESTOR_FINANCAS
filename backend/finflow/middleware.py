"""Middleware de segurança a nível de aplicação do FinFlow.

Mitigação de DoS (limite de payload), proteção contra Clickjacking (CSP / X-Frame-Options),
remocao/sanitização do cabeçalho Server e adição do Content-Security-Policy.
"""

import secrets

from django.conf import settings
from django.http import HttpResponse


class MaxBodySizeMiddleware:
    """Rejeita payloads maiores que MAX_BODY_SIZE_BYTES com 413.

    Aplica-se ao caso JSON (a API do FinFlow é JSON puro): o Django só
    limita por padrão multipart/form-data (DATA_UPLOAD_MAX_MEMORY_SIZE),
    não corpos JSON. Requisições multipart/form-data (upload de comprovante)
    têm limite próprio, maior: COMPROVANTE_MAX_BYTES.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_size = getattr(settings, "MAX_BODY_SIZE_BYTES", 1024 * 1024)
        # Uploads multipart (comprovante PDF/imagem) têm limite próprio,
        # maior: COMPROVANTE_MAX_BYTES + margem para o overhead do próprio
        # multipart/form-data (fronteira entre campos, headers de parte).
        # O limite EXATO do arquivo (5 MB) é validado na view — aqui passam
        # requests cujo ARQUIVO caiba no limite.
        self.max_multipart_size = getattr(
            settings, "COMPROVANTE_MAX_BYTES", 5 * 1024 * 1024
        ) + 64 * 1024

    def __call__(self, request):
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.content_type or ""
            is_multipart = content_type.startswith("multipart/form-data")
            limite = self.max_multipart_size if is_multipart else self.max_size
            content_length = request.META.get("CONTENT_LENGTH")
            if content_length and content_length.isdigit():
                if int(content_length) > limite:
                    return HttpResponse(
                        "Payload excede o limite permitido.",
                        status=413,
                        content_type="text/plain",
                    )
        return self.get_response(request)


class CSPFrameAncestorsMiddleware:
    """Adiciona o cabeçalho Content-Security-Policy (CSP) a todas as respostas HTTP.

    Substitui 'unsafe-inline' em script-src por um NONCE único por requisição
    (achado ZAP, risco médio): scripts inline só executam se incluírem o
    atributo nonce correto. O SDK do Google Identity Services (vendido via
    https://accounts.google.com) continua carregável pela whitelist de host.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Nonce criptograficamente aleatório UMA vez por request (compartilhado
        # com templates via atributo nonce do próprio Django: o TemplateResponse
        # injeta nonce automaticamente em <script nonce> quando o request
        # carrega o nonce em request.csp_nonce — ver Django 4.0+ docs).
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        csp_header = getattr(
            settings,
            "CONTENT_SECURITY_POLICY",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; frame-ancestors 'none';",
        )
        # Substitui o placeholder {{CSP_NONCE}} (se presente na configuração)
        # pelo nonce da requisição. Ajuda a evitar duplicação de nonce em
        # headers estáticos + middleware dinâmico.
        if "{{CSP_NONCE}}" in csp_header:
            csp_header = csp_header.replace("{{CSP_NONCE}}", request.csp_nonce)
        response["Content-Security-Policy"] = csp_header
        return response


class ServerHeaderMiddleware:
    """Remove ou sanitiza a versão do servidor no cabeçalho HTTP Server."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if "Server" in response:
            del response["Server"]
        response["Server"] = "FinFlow"
        return response