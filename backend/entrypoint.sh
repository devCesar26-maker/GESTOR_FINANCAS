#!/bin/sh
# Entrypoint de produção do FinFlow (Render Free: 1 container = tudo).
#
# Sequência: espera o Postgres → migra → sobe Celery (worker solo + beat) em
# background → valida que ambos estão vivos (kill -0) → entrega o PID 1 ao
# Gunicorn (CMD). Falha de boot do Celery aborta o container (exit 1): é
# melhor que o Render reinicie com banco/redis íntegros do que servir uma
# API sem tarefas agendadas.
set -e

echo "[entrypoint] Esperando o banco de dados..."
if [ -f scripts/wait_for_db.py ]; then
    python scripts/wait_for_db.py --timeout "${DB_WAIT_TIMEOUT:-60}"
else
    echo "[entrypoint] AVISO: scripts/wait_for_db.py não existe — seguindo."
fi

echo "[entrypoint] Aplicando migrações..."
python manage.py migrate --noinput

# Superuser de dev (somente DEBUG=true; no docker-compose local).
if [ "${DEBUG:-}" = "true" ] || [ "${DEBUG:-}" = "True" ]; then
    if [ -f scripts/ensure_dev_superuser.py ]; then
        echo "[entrypoint] Garantindo superusuário de dev..."
        python manage.py shell < scripts/ensure_dev_superuser.py
    fi
fi

if [ "${RUN_EMBEDDED_CELERY:-}" = "true" ] || [ "${RUN_EMBEDDED_CELERY:-}" = "True" ]; then
    echo "[entrypoint] Iniciando Celery worker (modo solo) e beat em segundo plano..."

    # -P solo: sem pool de processos — essencial para caber em 512 MB.
    celery -A finflow worker -l info -P solo &
    CELERY_WORKER_PID=$!

    celery -A finflow beat -l info &
    CELERY_BEAT_PID=$!

    # Dá um tempo para os processos passarem pela inicialização (imports,
    # conexão com o broker) antes de validar.
    sleep 3

    if ! kill -0 "$CELERY_WORKER_PID" 2>/dev/null; then
        echo "[entrypoint] ERRO: celery worker morreu na inicialização." >&2
        exit 1
    fi

    if ! kill -0 "$CELERY_BEAT_PID" 2>/dev/null; then
        echo "[entrypoint] ERRO: celery beat morreu na inicialização." >&2
        exit 1
    fi

    echo "[entrypoint] Celery OK (worker pid=${CELERY_WORKER_PID}, beat pid=${CELERY_BEAT_PID})."
fi

echo "[entrypoint] Repassando o PID 1 ao Gunicorn..."
exec "$@"
