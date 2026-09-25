#!/bin/sh
set -e

echo "Aplicando migrações..."
python manage.py migrate --noinput

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Executa a criação do superusuário APENAS em ambiente de desenvolvimento
if [ "$DEBUG" = "true" ] || [ "$DEBUG" = "True" ]; then
    echo "Garantindo superusuário de dev..."
    if [ -f "scripts/ensure_dev_superuser.py" ]; then
        python manage.py shell < scripts/ensure_dev_superuser.py
    fi
fi

# Se ativado (ex: Render Free tier de container único), inicia Celery Worker e Beat em background
if [ "$RUN_EMBEDDED_CELERY" = "true" ] || [ "$RUN_EMBEDDED_CELERY" = "True" ]; then
    echo "Iniciando Celery Worker e Beat em segundo plano no mesmo container..."
    celery -A finflow worker -l info --concurrency=2 &
    celery -A finflow beat -l info &
fi

exec "$@"