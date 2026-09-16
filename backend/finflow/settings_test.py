"""
Configuração usada apenas pelos testes (pytest).

Os testes rodam contra SQLite em memória — rápido e sem depender de um
PostgreSQL local. Para rodar os testes contra o PostgreSQL do
docker-compose, exporte DB_ENGINE/DB_NAME/etc. e use o settings padrão:
    DJANGO_SETTINGS_MODULE=finflow.settings pytest
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Nunca envia e-mail de verdade nos testes; captura em django.core.mail.outbox.
EMAIL_BACKEND = "anymail.backends.test.EmailBackend"

# HTTPS é assunto de produção: nos testes tudo corre por http (o test
# client não usa https por padrão e SECURE_SSL_REDIRECT rompería tudo).
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
REFRESH_COOKIE_SECURE = False

# Throttling: en prod usa Redis (ver settings.CACHES); en tests, cache em
# memoria — rápido e sem depender de um Redis local. O conftest limpa o
# cache entre testes para que os rate limits não vazem entre testes.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# Tasks Celery rodam inline (eager): .delay() executa na hora, sem broker/worker,
# permitindo assertar os e-mails enviados via fixture mailoutbox do pytest-django.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False

# Uploads (comprovantes) nos testes: grava em diretório temporário e limpa
# ao final da sessão — nada de media/ poluído no repositório.
import tempfile as _tempfile

MEDIA_ROOT = _tempfile.mkdtemp(prefix="finflow-test-media-")