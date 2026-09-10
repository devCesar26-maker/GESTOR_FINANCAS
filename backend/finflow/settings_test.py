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