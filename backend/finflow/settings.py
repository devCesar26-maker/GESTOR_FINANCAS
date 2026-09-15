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
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS", default="http://localhost:5173"
)
# O refresh token viaja num cookie: si SPA e API estivessem em origens
# distintas, o navegador exige credenciales explícitas para enviarlas.
CORS_ALLOW_CREDENTIALS = True

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

# Lembrete: grafia "LEMRETE" mantida conforme especificação do projeto.
LEMRETE_DIAS_ANTES = env_int("LEMRETE_DIAS_ANTES", 3)

# ---------------------------------------------------------------------------
# Cache (Redis) — usado pelo throttling do DRF
# ---------------------------------------------------------------------------
# Com LocMemCache (padrão do Django) cada worker de Gunicorn teria sua
# própria contabilidade de rate limit, esvaziando a proteção. Redis é
# compartido entre workers: a contagem por IP/usuario é real. Usa a mesma
# instância Redis do stack (Celery), na DB 1 (a 0 é do broker).
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
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

# Doble envío CSRF: o frontend (vite :5173) envia o header X-CSRFToken nas
# rotas de token. Em produção frontend+API são mesma origem (whitenoise);
# em dev o proxy do vite faz o Origin diferir do Host do backend.
CSRF_TRUSTED_ORIGINS = env_list(
    "CSRF_TRUSTED_ORIGINS", default="http://localhost:5173"
)

# 403 CSRF em formato JSON (a API é consumida por JS, não por formulários).
CSRF_FAILURE_VIEW = "apps.usuarios.views.csrf_failure_json"

# Limite de payload da API (JSON): mitigação básica de DoS a nível de
# aplicação. Proteção real contra DDoS exige infraestructura (WAF/CDN) —
# ver README. DATA_UPLOAD_MAX_MEMORY_SIZE cobre multipart/form-data;
# o middleware MaxBodySizeMiddleware cobre corpos JSON.
MAX_BODY_SIZE_BYTES = env_int("MAX_BODY_SIZE_BYTES", 1024 * 1024)  # 1 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_BODY_SIZE_BYTES