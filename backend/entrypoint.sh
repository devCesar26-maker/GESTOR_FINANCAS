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

exec "$@"