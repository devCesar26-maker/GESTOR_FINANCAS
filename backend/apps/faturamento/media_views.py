"""Serviço PROTEGIDO de arquivos de mídia (comprovantes de pagamento).

Regras de segurança implementadas aqui:
1. Autenticação JWT obrigatória (IsAuthenticated) — nunca sirva mídia anônima.
2. Multi-tenancy: o arquivo só é servido se pertencer a uma Fatura do
   request.user (o dono do arquivo). Outros tenants recebem 404.
3. Path traversal bloqueado (".." rejeitado + caminho validado contra o DB).
4. Content-Type por whitelist de extensão (pdf/jpeg/png/webp) — o tipo
   informado no upload nunca é confiado.
5. X-Content-Type-Options: nosniff para evitar sniffing no navegador.

Modos de operação:
- Direto (dev sem Nginx / chamadas autenticadas do frontend):
  GET /media/comprovantes/2026/09/comp_x.pdf com Bearer token.
- Subauth do Nginx (produção): o Nginx repassa X-Original-URI via auth_request
  e a view apenas VALIDA (200 ou 401, sem abrir o arquivo); o próprio Nginx
  serve o arquivo do disco depois do 200.
"""
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Fatura

# Extensões permitidas — espelha as aceitas no upload (ver serializers.py).
MEDIA_CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class MediaProtegidaView(APIView):
    """Download autenticado e isolado por tenant dos comprovantes."""

    permission_classes = [IsAuthenticated]

    def _resposta_falha(self, request):
        """Falha de acesso: 401 no modo subauth (o Nginx bloqueia o cliente
        com base nesse código); 404 no modo direto (não revela existência)."""
        if request.headers.get("X-Original-URI"):
            return Response(status=401)
        raise Http404

    def _resolver_caminho(self, request, caminho_url: str) -> str:
        """Caminho relativo a MEDIA_ROOT vindo da URL ou do X-Original-URI."""
        original_uri = request.headers.get("X-Original-URI")
        if original_uri:
            caminho_url = original_uri.split("?", 1)[0]
            prefixo = settings.MEDIA_URL  # "/media/"
            if caminho_url.startswith(prefixo):
                caminho_url = caminho_url[len(prefixo) :]
        return (caminho_url or "").strip().lstrip("/")

    def get(self, request, caminho_url: str = ""):
        modo_subauth = request.headers.get("X-Original-URI") is not None
        caminho = self._resolver_caminho(request, caminho_url)

        # Path traversal e caminhos vazios são rejeitados de cara.
        if not caminho or ".." in Path(caminho).parts:
            return self._resposta_falha(request)

        # Multi-tenancy: o arquivo precisa pertencer a uma fatura do usuário.
        pertence_ao_tenant = Fatura.objects.filter(
            owner=request.user, comprovante=caminho
        ).exists()
        if not pertence_ao_tenant:
            return self._resposta_falha(request)

        # Modo subauth (auth_request do Nginx): valida e responde 200 sem ler
        # o arquivo — quem serve o arquivo é o próprio Nginx, depois do 200.
        if modo_subauth:
            return Response(status=200)

        arquivo = Path(settings.MEDIA_ROOT) / caminho
        # Defesa em profundidade: o caminho final não pode escapar de MEDIA_ROOT.
        try:
            arquivo.resolve().relative_to(Path(settings.MEDIA_ROOT).resolve())
        except ValueError:
            return self._resposta_falha(request)

        if not arquivo.is_file():
            return self._resposta_falha(request)

        content_type = MEDIA_CONTENT_TYPES.get(arquivo.suffix.lower())
        if content_type is None:
            # Extensão fora da whitelist: não confiamos no que foi enviado.
            return self._resposta_falha(request)

        response = FileResponse(arquivo.open("rb"), content_type=content_type)
        response["Content-Disposition"] = f'inline; filename="{arquivo.name}"'
        response["X-Content-Type-Options"] = "nosniff"
        return response
