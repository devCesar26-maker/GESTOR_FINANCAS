"""Compat de cookies: atributos que o Django (5.2) ainda não suporta.

_PARTITIONED_ (CHIPS, "Cookies Having Independent Partitioned State"):
    O Chrome passa a rejeitar cookies cross-site sem o atributo
    ``Partitioned`` (aviso do DevTools: "será rejeitado em breve por ser
    estrangeiro e não ter o atributo Partitioned"). Duas limitações
    contornadas aqui:
      1) HttpResponse.set_cookie() do Django 5.2 não tem parâmetro para o
         atributo;
      2) o http.cookies.Morsel do Python valida atributos contra uma
         allowlist rígida (Morsel._reserved) e levanta
         CookieError("Invalid attribute 'partitioned'") — nem o parser
         (BaseCookie.load) nem o __setitem__ aceitam o atributo.
    Solução: registrar ``partitioned`` em Morsel._reserved/_flags UMA vez,
    no import deste módulo. Depois disso ``morsel["partitioned"] = True``
    funciona normalmente e o OutputString() do valor serializado pelo
    WSGI/ASGI handler do Django (response.cookies) inclui ``Partitioned``.

Pré-condição da spec CHIPS: o cookie precisa ser Secure + SameSite=None.
Em contexto same-site (dev/docker-compose, cookie Lax), anexar Partitioned
seria inválido — o helper NÃO anexa nesses casos, mantendo o comportamento
local intacto (login/refresh em dev continuam como antes).
"""

from http.cookies import Morsel

from django.conf import settings

# --- Registro do atributo 'partitioned' na allowlist do http.cookies -------
# UMA vez por processo (idempotente): sem isto, morsel["partitioned"] levanta
# CookieError e o parser rejeitaria o valor inteiro (KeyError vazio).
if "partitioned" not in Morsel._reserved:
    Morsel._reserved = {**Morsel._reserved, "partitioned": "Partitioned"}
    Morsel._flags = Morsel._flags | {"partitioned"}

# Cookies alvo do aviso do DevTools (mesmo conjunto em views e aqui).
_COOKIES_PARTITIONED = ("refresh_token", "csrftoken")


def _adicionar_partitioned(response, cookie_name):
    """Anexa ``Partitioned`` ao Set-Cookie de ``cookie_name`` na resposta.

    Idempotente: se o atributo já está presente, não faz nada.
    """
    morsel = response.cookies.get(cookie_name)
    if morsel is None:
        return
    if morsel.get("partitioned"):
        return  # já anexado
    # Pré-condições CHIPS: Secure + SameSite=None. Em dev (cookie Lax)
    # não anexa — evita invalidar o Set-Cookie e quebrar o login local.
    if not morsel["secure"] or (morsel["samesite"] or "").lower() != "none":
        return
    morsel["partitioned"] = True


def _anexar_partitioned_em_todos(response):
    """Anexa Partitioned aos cookies alvo presentes na resposta.

    Idempotente e tolerante a ausências: só age sobre os cookies que a
    resposta de fato define (ex.: logout define APENAS o Set-Cookie de
    exclusão do refresh_token; a resposta de refresh seta só o csrftoken
    quando o token precisa rodar).
    """
    for nome in _COOKIES_PARTITIONED:
        _adicionar_partitioned(response, nome)


class PartitionedCookiesMiddleware:
    """Anexa Partitioned aos cookies refresh_token e csrftoken na resposta.

    IMPORTANTE (ordem de middleware): process_response executa em ordem
    REVERSA — de baixo para cima na lista MIDDLEWARE. Como na settings.py
    este middleware fica ANTES (acima) do CsrfViewMiddleware, na fase de
    resposta ele roda DEPOIS — quando o csrftoken (escrito pelo
    set_cookie() nativo do CSRF middleware) já está em response.cookies.
    Errar essa ordem era o motivo de csrftoken sair sem Partitioned: com o
    middleware abaixo do de CSRF, ele rodava ANTES na resposta e o cookie
    ainda não existia (o refresh_token não sofria porque a view usa
    _set_refresh_cookie, chamando o helper direto).

    Habilitado por REFRESH_COOKIE_PARTITIONED; desligado em dev (DEBUG,
    cookie Lax — atributo seria inválido naquele contexto).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if getattr(settings, "REFRESH_COOKIE_PARTITIONED", False):
            _anexar_partitioned_em_todos(response)
        return response
