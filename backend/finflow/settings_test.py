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

# Tasks Celery rodam inline (eager): .delay() executa na hora, sem broker/worker,
# permitindo assertar os e-mails enviados via fixture mailoutbox do pytest-django.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = False