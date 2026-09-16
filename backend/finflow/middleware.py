"""Middleware de segurança a nível de aplicação do FinFlow.

Mitigação de DoS (limite de payload), proteção contra Clickjacking (CSP / X-Frame-Options),
remocao/sanitização do cabeçalho Server e adição do Content-Security-Policy.
"""

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
    """Adiciona o cabeçalho Content-Security-Policy (CSP) a todas as respostas HTTP."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        csp_header = getattr(
            settings,
            "CONTENT_SECURITY_POLICY",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; object-src 'none'; frame-ancestors 'none';",
        )
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