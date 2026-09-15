"""Middleware de segurança a nível de aplicação do FinFlow.

Mitigação básica de DoS (limite de payload) e anti-clickjacking (CSP).
Não é proteção contra DDoS real — isso exige infraestructura (WAF/CDN),
ver README.
"""

from django.conf import settings
from django.http import HttpResponse


class MaxBodySizeMiddleware:
    """Rejeita payloads maiores que MAX_BODY_SIZE_BYTES com 413.

    Aplica-se ao caso JSON (a API do FinFlow é JSON puro): o Django só
    limita por padrão multipart/form-data (DATA_UPLOAD_MAX_MEMORY_SIZE),
    não corpos JSON. Limitação conhecida: depende do header
    Content-Length; clientes com transfer-encoding chunked exigem limite
    no proxy (nginx) — documentado no README.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.max_size = getattr(settings, "MAX_BODY_SIZE_BYTES", 1024 * 1024)

    def __call__(self, request):
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.META.get("CONTENT_LENGTH")
            if content_length and content_length.isdigit():
                if int(content_length) > self.max_size:
                    return HttpResponse(
                        "Payload excede o limite permitido.",
                        status=413,
                        content_type="text/plain",
                    )
        return self.get_response(request)


class CSPFrameAncestorsMiddleware:
    """Adiciona Content-Security-Policy: frame-ancestors 'none' a toda resposta.

    Complementa X-Frame-Options: DENY (Django) contra clickjacking.
    Mantemos a CSP mínima de propósito: uma CSP completa com style-src
    rompe o frontend, que usa estilos inline (documentado no README).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = "frame-ancestors 'none'"
        return response