#!/bin/sh
# Entry point do container de produção do FinFlow.
#
# Ordem de boot (escolhida para sobreviver ao plano Free do Render):
#   1. Espera tolerante pelo PostgreSQL (até 60s) — evita crash-loop quando
#      o banco está em manutenção/restart na hora do deploy.
#   2. migrate (aplicação incremental) — roda no boot porque o plano Free
#      do Render NÃO suporta preDeployCommand (recurso de plano pago).
#   3. Celery embutido (worker + beat) atrás de RUN_EMBEDDED_CELERY — o
#      render.yaml usa 1 serviço único para caber no Free.
#   4. exec no CMD do Dockerfile (gunicorn) — o PID 1 sempre é o servidor.
set -e

echo "[entrypoint] Esperando o banco de dados..."
python scripts/wait_for_db.py --timeout "${DB_WAIT_TIMEOUT:-60}"

echo "[entrypoint] Aplicando migrações..."
python manage.py migrate --noinput

# Superusuário de DEV: o Dockerfile.prod não o chama; no compose de dev o
# Dockerfile antigo executa este script e cai aqui quando DEBUG=true.
if [ "${DEBUG:-}" = "true" ] || [ "${DEBUG:-}" = "True" ]; then
    echo "[entrypoint] Garantindo superusuário de dev..."
    if [ -f "scripts/ensure_dev_superuser.py" ]; then
        python manage.py shell < scripts/ensure_dev_superuser.py
    fi
fi

# Celery embutido (modo econômico p/ Render Free): worker + beat em
# background. Se qualquer um morrer logo na subida, falha o boot — assim o
# Render não promove um deploy "live" sem tasks agendadas.
if [ "${RUN_EMBEDDED_CELERY:-}" = "true" ] || [ "${RUN_EMBEDDED_CELERY:-}" = "True" ]; then
    echo "[entrypoint] Iniciando Celery worker e beat (modo econômico)..."
    celery -A finflow worker -l info --concurrency=1 &
    CELERY_WORKER_PID=$!
    celery -A finflow beat -l info &
    CELERY_BEAT_PID=$!

    # Morreu na subida? Encerra com erro (deploy não vira live com Celery quebrado).
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

# Executa o comando do container (CMD do Dockerfile) como PID 1: os filhos
# do Celery ficam órfãos para o init do container, que os reaproveita/reap.
exec "$@"
