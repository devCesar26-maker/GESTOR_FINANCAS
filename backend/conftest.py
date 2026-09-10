"""
Configuração global do pytest.

O banco dos testes é definido em finflow/settings_test.py (SQLite em
memória por padrão). Para rodar os testes contra o PostgreSQL do
docker-compose:
    DJANGO_SETTINGS_MODULE=finflow.settings pytest
"""