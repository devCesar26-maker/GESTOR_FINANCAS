"""Views do app Usuarios."""
import logging
from functools import wraps

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import _unmask_cipher_token, get_token
from django.utils.crypto import constant_time_compare
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import (
    csrf_protect,
    ensure_csrf_cookie,
)
from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import RegistroResponseSerializer, RegistroSerializer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cookie do refresh token (httpOnly, Secure, SameSite=Strict)
# ---------------------------------------------------------------------------
REFRESH_COOKIE_NAME = "refresh_token"
# Path restringido: o cookie só viaja ao endpoint de refresh — nunca a
# outras rotas da API (menor privilégio para cookies).
REFRESH_COOKIE_PATH = "/api/token/refresh/"
REFRESH_COOKIE_MAX_AGE = int(
    settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()
)


def _set_refresh_cookie(response, refresh_token):
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=REFRESH_COOKIE_MAX_AGE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=True,
        # Deploy Render: SPA e API em subdomínios diferentes = contexto
        # cross-site — o cookie só é guardado/enviado no XHR com SameSite=None.
        # Em dev (mesma origem via proxy Vite) o padrão é Lax (ver settings).
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


# ---------------------------------------------------------------------------
# CSRF (duplo envio: cookie + header X-CSRFToken)
# ---------------------------------------------------------------------------
def csrf_failure_json(request, reason=""):
    """Vista de falha CSRF com resposta JSON (a API é consumida por JS)."""
    return JsonResponse(
        {"detail": "CSRF falhou: token ausente ou inválido."}, status=403
    )


# ---------------------------------------------------------------------------
# CSRF cross-origin (deploy Render: SPA e API em subdomínios DIFERENTES)
# ---------------------------------------------------------------------------
# O cookie csrftoken vive no domínio da API e o JavaScript da SPA (outro
# subdomínio) NÃO consegue lê-lo — é a Same-Origin Policy impedindo um
# atacante de roubar o token. Como o duplo envio clássico fica impossível,
# adotamos um fallback em DUPLA CHAVE (synchronizer token clássico):
#   1) GET /api/csrf/ devolve o segredo CSRF cru no header de resposta
#      X-CSRFSecret (exposto à SPA via CORS_EXPOSE_HEADERS — ver settings);
#   2) a SPA guarda o segredo e o envia no header X-CSRFSecret;
#   3) aqui, o segredo do header é comparado (em tempo constante) com o
#      cookie csrftoken: saber o segredo prova que a origem já recebeu uma
#      resposta legítima desta API — e o cookie nunca é exposto a outras
#      origens (CORS + Same-Origin Policy). Mesma origem, o fluxo clássico
#      (cookie + X-CSRFToken) segue valendo e este fallback é ignorado.
CSRF_SECRET_HEADER = "HTTP_X_CSRFSECRET"


def _aplicar_csrf_fallback_cross_origin(request) -> None:
    """Valida a dupla chave X-CSRFSecret + cookie csrftoken (cross-origin).

    Válida: marca a request para o CsrfViewMiddleware NÃO rejeitá-la (mesma
    mecânica do APIClient do DRF). O par cookie/segredo vale enquanto o
    cookie csrftoken for válido — mesma longevidade do duplo envio clássico,
    em que o JS reenvia o MESMO valor do cookie a cada escrita. O segredo
    não é de uso único: o process_request do csrf_protect relê o cookie
    depois desta função, então rotação aqui seria sobrescrita sem efeito.
    Inválida/ausente: não faz NADA — o middleware segue o fluxo normal
    (403 JSON em CSRF_FAILURE_VIEW), inclusive para o fluxo same-origin.
    """
    segredo = (request.META.get(CSRF_SECRET_HEADER) or "").strip()
    cookie = request.COOKIES.get(settings.CSRF_COOKIE_NAME) or ""
    if not segredo or not cookie:
        return

    # Compat entre versões do Django: em 5.1+ o cookie guarda o SEGREDO cru
    # (32 chars); até a 5.0, guardava o token MASCARADO (máscara+cifra, 64
    # chars) — desmascarar revela o segredo. A comparação em tempo constante
    # prova que a origem já recebeu uma resposta legítima desta API.
    if len(segredo) != 32:
        return
    if len(cookie) == 64:
        cookie = _unmask_cipher_token(cookie)
    elif len(cookie) != 32:
        return
    if not constant_time_compare(cookie, segredo):
        return

    request._dont_enforce_csrf_checks = True


def csrf_fallback_cross_origin(method):
    """Decorator: valida a dupla chave ANTES do csrf_protect decorar o POST.

    Os decorators executam de fora para dentro: este precisa ficar ACIMA de
    @method_decorator(csrf_protect) na pilha, ou a validação clássica roda
    primeiro e rejeitaria (403) uma escrita cross-origin legítima.
    """

    @wraps(method)
    def wrapper(self, request, *args, **kwargs):
        _aplicar_csrf_fallback_cross_origin(request)
        return method(self, request, *args, **kwargs)

    return wrapper


def csrf_token_view(request):
    """GET público: define o cookie csrftoken para o duplo envio CSRF.

    O frontend lee o cookie (NÃO é httpOnly — ver CSRF_COOKIE_HTTPONLY no
    settings) e o envia no header X-CSRFToken nas rotas /api/token/*.

    Sem get_token() aqui NENHUM cookie é setado: @ensure_csrf_cookie só
    afeta views que renderizam template com {% csrf_token %} (e o test
    client não o lê). get_token(request) gera o token e injeta
    Set-Cookie: csrftoken=... na resposta.

    Deploy CROSS-ORIGIN (Render: SPA e API em subdomínios diferentes): o JS
    da SPA não consegue ler o cookie do domínio da API (Same-Origin Policy)
    — o duplo envio clássico seria impossível. Por isso a resposta devolve
    também o segredo CSRF cru no header X-CSRFSecret (exposto via
    CORS_EXPOSE_HEADERS); a SPA o envia no header X-CSRFSecret e o backend
    autentica a escrita pela dupla chave segredo+cookie (ver
    _aplicar_csrf_fallback_cross_origin). Mesma origem (dev/proxy Vite):
    fluxo idêntico ao de antes, sem header extra.
    """
    response = HttpResponse(status=status.HTTP_204_NO_CONTENT)
    get_token(request)  # gera (se necessário) e seta o cookie csrftoken
    # O segredo cru vive em request.META["CSRF_COOKIE"]: em Django 5.1+ é ele
    # o valor do cookie (32 chars); até a 5.0 o cookie guardava o token
    # mascarado (64) e o segredo vinha de _unmask_cipher_token. Só é exposto
    # a quem já recebeu UMA resposta legítima desta API — e a SPA
    # cross-origin não consegue lê-lo do cookie, daí o header (o CORS
    # restringe QUEM lê esta resposta).
    segredo = request.META.get("CSRF_COOKIE") or ""
    if len(segredo) == 64:
        segredo = _unmask_cipher_token(segredo)
    if segredo:
        response["X-CSRFSecret"] = segredo
    return response


class TokenObtainPairThrottledView(TokenObtainPairView):
    """Login com rate limit agressivo (anti força bruta): 5/min por IP.

    O ScopedRateThrottle usa o scope "login" (ver DEFAULT_THROTTLE_RATES
    no settings) e, como o usuário ainda não está autenticado, identifica
    por IP.
    """

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"


class TokenObtainPairCookieView(TokenObtainPairThrottledView):
    """Login JWT: devolve SOLO o access token no body; o refresh token viaja
    num cookie httpOnly (Secure, SameSite=Strict), fora do alcance do
    JavaScript. Protegido com CSRF (duplo envio).
    """

    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @csrf_fallback_cross_origin
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        refresh = serializer.validated_data.pop("refresh")
        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        _set_refresh_cookie(response, refresh)
        return response


class TokenRefreshCookieView(TokenRefreshView):
    """Renova o access token lendo o refresh token do cookie httpOnly.

    O frontend nunca envia o refresh token manualmente: o navegador o
    adjunta automaticamente ao POST /api/token/refresh/. Protegido com
    CSRF (duplo envio).
    """

    @method_decorator(ensure_csrf_cookie)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    @csrf_fallback_cross_origin
    @method_decorator(csrf_protect)
    def post(self, request, *args, **kwargs):
        refresh = request.COOKIES.get(REFRESH_COOKIE_NAME)
        if not refresh:
            return Response(
                {"detail": "Refresh token ausente. Faça login novamente."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])

        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        # Se ROTATE_REFRESH_TOKENS estivesse ativo, o novo refresh chega na
        # resposta — renovamos também o cookie.
        novo_refresh = serializer.validated_data.pop("refresh", None)
        _set_refresh_cookie(response, novo_refresh or refresh)
        return response


class LogoutView(APIView):
    """Encerra a sessão: o backend limpa o cookie httpOnly do refresh token.

    Sem proteção CSRF a propósito: forzar um logout alheio é inofensivo, e
    exigir CSRF aqui poderia deixar um cookie órfano se o cookie csrftoken
    expirou. O refresh token não é blacklistado (a app de blacklist não
    está instalada); expira por si só em 7 dias.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
        return response


class RegistroAPIView(generics.CreateAPIView):
    """Cria uma nova conta de usuário (endpoint público).

    Diferente de todos os demais endpoints da API, não exige autenticação.
    """

    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "registro"

    @extend_schema(
        tags=["Autenticação"],
        summary="Registrar novo usuário",
        description=(
            "Cria uma conta com nome, e-mail e senha. A senha é validada pelas "
            "regras do Django (mínimo de 8 caracteres, não inteiramente numérica, etc.). "
            "E-mail deve ser único."
        ),
        request=RegistroSerializer,
        responses={201: RegistroResponseSerializer},
        auth=[],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # E-mail de boas-vindas: assíncrono (Celery) e isolado — uma falha
        # de broker/disparo NUNCA quebra a criação da conta.
        try:
            from .tasks import task_enviar_email_boas_vindas

            task_enviar_email_boas_vindas.delay(user.pk)
        except Exception:
            logger.exception(
                "Falha ao disparar e-mail de boas-vindas do usuário %s", user.pk
            )

        return Response(
            RegistroResponseSerializer(user).data
            | {"detail": "Conta criada com sucesso. Faça login para obter o token."},
            status=status.HTTP_201_CREATED,
        )