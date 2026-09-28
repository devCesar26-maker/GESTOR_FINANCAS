"""Health check leve para orquestradores (Render healthCheckPath, etc.).

Requisitos do endpoint:
- Responder 200 o mais rápido possível: nenhuma consulta ao banco, sem
  autenticação, sem throttle do DRF (não passa pelo DRF de todo modo,
  pois é uma view Django pura) e sem tocar em staticfiles.
- Sobreviver a Host header arbitrário: o checker pode bater com Host
  inválido (vira handler400) — finflow.health.bad_request responde 200
  apenas em /healthz/ e mantém 400 para todo o resto.
- Se SECURE_SSL_REDIRECT estiver ativo, a rota é isenta do redirect em
  SECURE_REDIRECT_EXEMPT (ver settings) — a checagem chega por HTTP interno.
"""

from django.http import HttpResponse, JsonResponse


def healthz(request):
    return JsonResponse({"status": "ok"})


def bad_request(request, exception=None):
    """handler400: só /healthz/ recebe 200 aqui; o resto segue 400."""
    if request.path.rstrip("/").endswith("healthz"):
        return JsonResponse({"status": "ok"})
    return HttpResponse("Bad Request", status=400)
