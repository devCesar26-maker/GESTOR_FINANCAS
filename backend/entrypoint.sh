#!/bin/sh
set -e

echo "Aplicando migrações..."
python manage.py migrate --noinput

# Executa a criação do superusuário APENAS em ambiente de desenvolvimento
if [ "\(DEBUG" = "true" ] || [ "\)DEBUG" = "True" ]; then
    echo "Garantindo superusuário de dev..."
    if [ -f "scripts/ensure_dev_superuser.py" ]; then
        python manage.py shell < scripts/ensure_dev_superuser.py
    fi
fi

# Inicia Celery com concorrência reduzida (1 worker) para economizar RAM
if [ "\(RUN_EMBEDDED_CELERY" = "true" ] || [ "\)RUN_EMBEDDED_CELERY" = "True" ]; then
    echo "Iniciando Celery Worker e Beat (Modo Económico) em segundo plano..."
    celery -A finflow worker -l info --concurrency=1 &
    celery -A finflow beat -l info &
fi

exec "$@"