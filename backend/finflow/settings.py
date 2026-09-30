"""
Configurações do projeto FinFlow.

Toda configuração sensível (banco, redis, chaves) é lida de variáveis de
ambiente, com valores padrão adequados para desenvolvimento local. Um
arquivo .env (veja .env.example) é carregado automaticamente quando existe.
"""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-change-me-em-producao")
DEBUG = env_bool("DEBUG", default=False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", default="localhost,127.0.0.1")

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Terceiros
    "rest_framework",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "anymail",
    # Apps do FinFlow
    "apps.usuarios",
    "apps.clientes",
    "apps.faturamento",
    "apps.relatorios",
]

CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "")
if CLOUDINARY_CLOUD_NAME:
    INSTALLED_APPS.insert(0, "cloudinary_storage")
    INSTALLED_APPS.insert(1, "cloudinary")

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "finflow.middleware.MaxBodySizeMiddleware",
    "finflow.middleware.CSPFrameAncestorsMiddleware",
    "finflow.middleware.ServerHeaderMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "finflow.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "finflow.wsgi.application"
ASGI_APPLICATION = "finflow.asgi.application"

# ---------------------------------------------------------------------------
# Banco de dados (PostgreSQL por padrão; SQLite permitido para testes)
# ---------------------------------------------------------------------------
# Provedores gerenciados (Supabase, Heroku, Render) expõem a conexão numa
# única variável DATABASE_URL. O parser abaixo extrai credenciais e opções
# sem dependência externa (equivale ao dj-database-url para os casos usados):
#   postgresql://postgres.<ref>:<senha>@aws-0-<regiao>.pooler.supabase.com:6543/postgres?sslmode=require
# Na porta 6543 (PgBouncer do Supabase em modo TRANSACTION) cursores
# server-side do ORM são desabilitados — named cursors quebram em transações
# com pooling. Query params (ex.: sslmode) viram OPTIONS do backend.
def database_from_url(url: str) -> dict:
    from urllib.parse import parse_qsl, unquote, urlparse

    parsed = urlparse(url)
    if parsed.scheme.startswith("postgres"):
        engine = "django.db.backends.postgresql"
    elif parsed.scheme == "sqlite":
        engine = "django.db.backends.sqlite3"
    else:
        raise ValueError(f"Esquema de banco não suportado: {parsed.scheme!r}")

    if engine == "django.db.backends.sqlite3":
        return {"ENGINE": engine, "NAME": unquote(parsed.path.lstrip("/"))}

    options = dict(parse_qsl(parsed.query))
    db = {
        "ENGINE": engine,
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username or ""),
        "PASSWORD": unquote(parsed.password or ""),
        "HOST": parsed.hostname or "",
        "PORT": str(parsed.port or ""),
        "OPTIONS": options,
    }
    if (parsed.port or 0) == 6543:
        db["DISABLE_SERVER_SIDE_CURSORS"] = True
    return db


if os.getenv("DATABASE_URL"):
    # Deploy com banco gerenciado (Supabase no Render): a URL manda.
    DATABASES = {"default": database_from_url(os.environ["DATABASE_URL"])}
else:
    # Desenvolvimento local / docker-compose: credenciais separadas.
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.postgresql"),
            "NAME": os.getenv("DB_NAME", "FINANCEIRO"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", "CESAR26"),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }

# ---------------------------------------------------------------------------
# Autenticação / Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.faturamento.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/minute",
        "user": "100/minute",
        # Anti força bruta / criação de contas em massa: 5 tentativas por
        # minuto por IP nos endpoints públicos de autenticação.
        "login": "5/minute",
        "registro": "5/minute",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    # Política própria do FinFlow: 8+ caracteres com maiúscula, minúscula,
    # número e caractere especial. Valida apenas na CRIAÇÃO de conta — o
    # login (JWT) nunca revalida força de senha.
    {"NAME": "apps.usuarios.validators.SenhaForteValidator"},
]

# ---------------------------------------------------------------------------
# Documentação da API (drf-spectacular / OpenAPI)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "FinFlow API",
    "DESCRIPTION": (
        "API de gestão financeira para pequenos negócios: contas a "
        "pagar/receber, faturamento e cobranças recorrentes."
    ),
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = False

def _norm_origin(origem: str) -> str:
    """Normaliza uma origem para o formato esquema://host que o CORS exige.

    O fromService property: host do Render devolve só o domínio (sem
    "https://") — sem esta normalização uma lista explícita de origens
    NUNCA casaria e a SPA ficaria sem Access-Control-Allow-Origin.
    """
    origem = origem.strip().rstrip("/")
    if origem and not origem.startswith(("http://", "https://")):
        # Render só serve HTTPS.
        origem = f"https://{origem}"
    host_part = origem.split("://")[-1]
    if host_part and "." not in host_part and "localhost" not in host_part:
        origem = f"{origem}.onrender.com"
    return origem


CORS_ALLOWED_ORIGINS = [
    _norm_origin(item)
    for item in env_list("CORS_ALLOWED_ORIGINS", default="http://localhost:5173")
    + env_list("CORS_ALLOWED_ORIGINS_EXTRA", default="")
    if _norm_origin(item)
]
# Deduplica preservando a ordem (backend e frontend podem coincidir).
CORS_ALLOWED_ORIGINS = list(dict.fromkeys(CORS_ALLOWED_ORIGINS))

# CORS por REGEX: ESCAPE-HATCH para quando os hosts exatos ainda não são
# conhecidos (primeiro deploy via Blueprint, renames). NÃO use em produção
# estável: '^https://[a-z0-9-]+\\.onrender\\.com$' autoriza QUALQUER
# subdomínio do Render — com CORS_ALLOW_CREDENTIALS um co-tenant malicioso
# (app gratuita no mesmo PaaS) poderia ler respostas autenticadas dos seus
# usuários. Lista exata em CORS_ALLOWED_ORIGINS >> regex ampla.
CORS_ALLOWED_ORIGIN_REGEXES = env_list(
    "CORS_ALLOWED_ORIGIN_REGEXES", default=""
)
# O refresh token viaja num cookie: se SPA e API estivessem em origens
# distintas, o navegador exige credenciais explícitas para enviá-las.
CORS_ALLOW_CREDENTIALS = True

# O fallback CSRF cross-origin usa um header próprio: X-CSRFSecret (a SPA
# não consegue ler o cookie da API em outro subdomínio; ver
# apps.usuarios.views). O default do django-cors-headers já inclui
# "x-csrftoken", mas não "x-csrfsecret" — e o GET /api/csrf/ devolve o
# segredo NESTE header de resposta: precisa estar em CORS_EXPOSE_HEADERS
# para o JS da SPA (origem diferente) conseguir lê-lo.
from corsheaders.defaults import default_headers

CORS_ALLOW_HEADERS = list(default_headers) + ["x-csrfsecret"]
CORS_EXPOSE_HEADERS = ["x-csrfsecret"]

# ---------------------------------------------------------------------------
# E-mail (django-anymail)
# ---------------------------------------------------------------------------
# Com BREVO_API_KEY definida, o envio vai pela API da Brevo; sem a chave
# (desenvolvimento/testes), cai no backend de console — nada parte de
# verdade por acidente.
BREVO_API_KEY = os.getenv("BREVO_API_KEY", "")
if BREVO_API_KEY:
    EMAIL_BACKEND = "anymail.backends.brevo.EmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

ANYMAIL = {"BREVO_API_KEY": BREVO_API_KEY}
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", "FinFlow <projetodefinancas34@gmail.com>"
)

# Dados de pagamento incluídos no corpo dos lembretes de cobrança (réguas
# 10/5/1/0 dias). A chave PIX é lida do ambiente; sem ela, o e-mail informa
# que os dados bancários podem ser solicitados respondendo à mensagem.
DADOS_PAGAMENTO = {
    "chave_pix": os.getenv("FINFLOW_CHAVE_PIX", ""),
    "favorecido": os.getenv("FINFLOW_FAVORECIDO_PIX", ""),
}

# Lembretes de vencimento: janelas de disparo em dias antes do vencimento.
# Prévios em 10/5/1 dias + aviso no dia do vencimento (0). A grafia legada
# "LEMRETE" é mantida nas variáveis já existentes.
LEMRETE_JANELAS_DIAS = [10, 5, 1]
LEMRETE_DIAS_ANTES = env_int("LEMRETE_DIAS_ANTES", 3)  # DEPRECIADO (compat legado)

# ---------------------------------------------------------------------------
# Cache (Redis) — usado pelo throttling do DRF
# ---------------------------------------------------------------------------
# Com LocMemCache (padrão do Django) cada worker de Gunicorn teria sua
# própria contabilidade de rate limit, esvaziando a proteção. Redis é
# compartido entre workers: a contagem por IP/usuario é real. Usa a mesma
# instância Redis do stack (Celery), na DB 1 (a 0 é do broker).
# Sem REDIS_URL explícita, reutiliza o broker do Celery (deploy Render +
# Upstash: uma única instância para tudo). O docker-compose de dev define
# REDIS_URL=redis://redis:6379/1 (DB separada do broker). Lê a ENV direto
# (e não a variável CELERY_BROKER_URL) porque esta seção do arquivo executa
# ANTES da seção de Celery.
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("CELERY_BROKER_URL") or "redis://localhost:6379/1"

from urllib.parse import parse_qsl as _parse_qsl, urlencode as _urlencode, urlsplit as _urlsplit, urlunsplit as _urlunsplit

def _normalizar_redis_url(url: str) -> str:
    """Sanitiza URLs de Redis/Upstash copiadas "na mão" para o painel.

    Dois problemas reais de deploy (Render + Upstash) que derrubam TODO POST
    com 500 (o cache do rate-limit do DRF toca o Redis antes de qualquer
    view de escrita):
      1) Barra dupla/sobrando no fim (ex.: ...:6379//) — o Celery tolera, o
         RedisCache do Django não;
      2) rediss:// SEM ssl_cert_reqs — redis-py de versões intermediárias
         levanta "A rediss:// URL must have parameter ssl_cert_reqs".
    Normalização: colapsa o path vazio para "/", preserva o número de DB
    (ex.: /1 do compose de dev) e injeta ssl_cert_reqs=CERT_REQUIRED em
    rediss:// quando ausente (Upstash exige TLS verificado).
    """
    if not url:
        return url
    partes = _urlsplit(url.strip())
    path = partes.path
    # Barra(s) sobrando de copy-paste ("//" ou "/") colapsam para "/" (db 0);
    # path vazio é preservado como está — a URL correta do painel sai intacta.
    if path == "//":
        path = "/"
    query = dict(_parse_qsl(partes.query, keep_blank_values=True))
    if partes.scheme == "rediss" and "ssl_cert_reqs" not in query:
        query["ssl_cert_reqs"] = "required"
    return _urlunsplit(
        (partes.scheme, partes.netloc, path, _urlencode(query), partes.fragment)
    )


REDIS_URL = _normalizar_redis_url(REDIS_URL)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = _normalizar_redis_url(
    os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
)
# SEM esta normalização, um CELERY_RESULT_BACKEND separado no painel (com a
# URL antiga) derruba o cadastro: o RegistroAPIView faz .delay() do e-mail de
# boas-vindas e o RedisBackend do Celery levanta ValueError ao construir —
# 500 na view inteira, mesmo com broker e cache já corrigidos.
CELERY_RESULT_BACKEND = _normalizar_redis_url(
    os.getenv("CELERY_RESULT_BACKEND") or CELERY_BROKER_URL
)
# Sem CELERY_RESULT_BACKEND explícito, reaproveita o broker (mesma instância
# Redis — ex.: Upstash Free expõe uma única URL): resultados ficam em chaves
# celery-task-meta-* na mesma DB, sem colisão com as filas do broker.
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND") or CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "America/Sao_Paulo"
CELERY_TASK_TRACK_STARTED = True

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    "processar-cobrancas-recorrentes-diario": {
        "task": "apps.faturamento.tasks.task_processar_cobrancas_recorrentes",
        "schedule": crontab(hour=0, minute=0),
    },
    "marcar-faturas-vencidas-diario": {
        "task": "apps.faturamento.tasks.task_marcar_faturas_vencidas",
        "schedule": crontab(hour=0, minute=0),
    },
    "enviar-lembretes-vencimento-diario": {
        "task": "apps.faturamento.tasks.task_enviar_lembretes_vencimento",
        "schedule": crontab(hour=8, minute=0),
    },
}

# ---------------------------------------------------------------------------
# Internacionalização / estáticos
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Uploads de usuário (comprovantes de pagamento de faturas).
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

if CLOUDINARY_CLOUD_NAME:
    CLOUDINARY_STORAGE = {
        "CLOUD_NAME": CLOUDINARY_CLOUD_NAME,
        "API_KEY": os.getenv("CLOUDINARY_API_KEY", ""),
        "API_SECRET": os.getenv("CLOUDINARY_API_SECRET", ""),
    }
    DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

# Tamanho máximo de cada comprovante enviado em /api/faturas/{id}/pagar/.
COMPROVANTE_MAX_BYTES = 5 * 1024 * 1024  # 5 MB

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Segurança HTTP & Proteção CSRF
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# HSTS: header Strict-Transport-Security em toda resposta HTTPS (auditado:
# já estava configurado — verificado por teste em test_seguridad.py).
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
# El cookie csrftoken NÃO é httpOnly a propósito: o frontend precisa lerlo
# para enviarlo no header X-CSRFToken (doble envío CSRF). El cookie do
# refresh token SÍ é httpOnly (ver apps.usuarios.views).
CSRF_COOKIE_HTTPONLY = False
SESSION_COOKIE_HTTPONLY = True

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "object-src 'none'; "
    "frame-ancestors 'none';"
)

# HTTPS obrigatório em produção: por padrão ativo quando DEBUG=False
# (docker-compose de dev define DEBUG=true explicitamente). Override
# explícito via variáveis de ambiente se necessário.
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)
# Cookie httpOnly do refresh token (ver apps.usuarios.views).
REFRESH_COOKIE_SECURE = env_bool("REFRESH_COOKIE_SECURE", default=not DEBUG)

# SameSite dos cookies de sessão: no deploy Render a SPA e a API ficam em
# subdomínios DIFERENTES (contexto cross-site) — csrftoken e refresh_token
# só são guardados/enviados no XHR com SameSite=None (exige Secure, garantido
# acima quando DEBUG=false). O padrão "Lax" preserva dev/docker-compose
# (mesma origem via proxy do Vite). Django aceita "Lax", "Strict" ou "None".
CSRF_COOKIE_SAMESITE = os.getenv("CSRF_COOKIE_SAMESITE", "Lax")
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "Lax")

# Por trás de proxy que termina TLS (Render, Nginx da borda, etc.) o Django
# recebe HTTP puro: sem este header ele NÃO sabe que o cliente veio por
# HTTPS e o SECURE_SSL_REDIRECT vira um loop infinito de 301 — o deploy
# nunca passa no health check. Confie no header X-Forwarded-Proto APENAS
# quando a variável TRUST_PROXY=1 estiver definida (nunca com o Django
# exposto direto na internet).
TRUST_PROXY = env_bool("TRUST_PROXY", default=False)
if TRUST_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    # Com X-Forwarded-Proto confiável, um request http simples não significa
    # mais "cliente inseguro"; deixe o proxy de borda decidir o redirect.
    SECURE_SSL_REDIRECT = False

# O health check precisa responder 200 mesmo com SECURE_SSL_REDIRECT ativo
# (Render faz a checagem por HTTP interno). Isente-o do redirect.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]

# Doble envío CSRF: o frontend (vite :5173) envia o header X-CSRFToken nas
# rotas de token. Em produção frontend+API são mesma origem (whitenoise);
# em dev o proxy do vite faz o Origin diferir do Host do backend.
# Deploy RENDER: origens EXATAS via fromService (o Render resolve o host
# real — com sufixo aleatório — na criação do Blueprint e mantém em sync nos
# redeploys). Lista fechada = um co-tenant do Render (app maliciosa em
# outro *.onrender.com) NÃO recebe Access-Control-Allow-Origin nem consegue
# ler o header X-CSRFSecret (CORS_EXPOSE_HEADERS) — sem isso, o fallback
# CSRF cross-origin poderia ser burlado por outro app da plataforma.
CSRF_TRUSTED_ORIGINS = [
    _norm_origin(item)
    for item in env_list("CSRF_TRUSTED_ORIGINS", default="http://localhost:5173")
    + env_list("CSRF_TRUSTED_ORIGINS_EXTRA", default="")
    if _norm_origin(item)
]
# Deduplica preservando a ordem.
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(CSRF_TRUSTED_ORIGINS))

# 403 CSRF em formato JSON (a API é consumida por JS, não por formulários).
CSRF_FAILURE_VIEW = "apps.usuarios.views.csrf_failure_json"

# Limite de payload da API (JSON): mitigação básica de DoS a nível de
# aplicação. Proteção real contra DDoS exige infraestructura (WAF/CDN) —
# ver README. DATA_UPLOAD_MAX_MEMORY_SIZE cobre multipart/form-data;
# o middleware MaxBodySizeMiddleware cobre corpos JSON.
MAX_BODY_SIZE_BYTES = env_int("MAX_BODY_SIZE_BYTES", 1024 * 1024)  # 1 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_BODY_SIZE_BYTES