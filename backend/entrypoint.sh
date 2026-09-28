#!/bin/sh
set -e

echo "[entrypoint] Esperando o banco de dados..."
python scripts/wait_for_db.py --timeout "${DB_WAIT_TIMEOUT:-60}"

echo "[entrypoint] Aplicando migrações..."
python manage.py migrate --noinput

if [ "\({DEBUG:-}" = "true" ] || [ "\){DEBUG:-}" = "True" ]; then
    echo "[entrypoint] Garantindo superusuário de dev..."
    if [ -f "scripts/ensure_dev_superuser.py" ]; then
        python manage.py shell < scripts/ensure_dev_superuser.py
    fi
fi

if [ "\({RUN_EMBEDDED_CELERY:-}" = "true" ] || [ "\){RUN_EMBEDDED_CELERY:-}" = "True" ]; then
    echo "[entrypoint] Iniciando Celery worker (Modo Solo) e Beat em segundo plano..."
    
    # -P solo evita a criação de múltiplos processos pelo Celery
    celery -A finflow worker -l info -P solo &
    CELERY_WORKER_PID=$!

    celery -A finflow beat -l info &
    CELERY_BEAT_PID=$!

    sleep 3

    if ! kill -0 "$CELERY_WORKER_PID" 2>/dev/null; then
        echo "[entrypoint] ERRO: celery worker morreu na inicialização." >&2
        exit 1
    fi

    if ! kill -0 "$CELERY_BEAT_PID" 2>/dev/null; then
        echo "[entrypoint] ERRO: celery beat morreu na inicialização." >&2
        exit 1
    fi
fi

exec "$@"