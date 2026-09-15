"""Views do app Usuarios."""
import logging

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import (
    csrf_protect,
    ensure_csrf_cookie,
    get_token,
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
        httponly=True,  # JS não pode lerlo: um XSS não rouba o refresh token
        secure=settings.REFRESH_COOKIE_SECURE,
        samesite="Strict",  # nunca viaja em requisições cross-site (CSRF)
    )


# ---------------------------------------------------------------------------
# CSRF (duplo envio: cookie + header X-CSRFToken)
# ---------------------------------------------------------------------------
def csrf_failure_json(request, reason=""):
    """Vista de falha CSRF com resposta JSON (a API é consumida por JS)."""
    return JsonResponse(
        {"detail": "CSRF falhou: token ausente ou inválido."}, status=403
    )


def csrf_token_view(request):
    """GET público: define o cookie csrftoken para o duplo envio CSRF.

    O frontend lee o cookie (NÃO é httpOnly — ver CSRF_COOKIE_HTTPONLY no
    settings) e o envia no header X-CSRFToken nas rotas /api/token/*.

    Sem get_token() aqui NENHUM cookie é setado: @ensure_csrf_cookie só
    afeta views que renderizam template com {% csrf_token %} (e o test
    client não o lê). get_token(request) gera o token e injeta
    Set-Cookie: csrftoken=... na resposta.
    """
    response = HttpResponse(status=status.HTTP_204_NO_CONTENT)
    get_token(request)  # gera (se necessário) e seta o cookie csrftoken
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
        if novo_refresh:
            _set_refresh_cookie(response, novo_refresh)
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