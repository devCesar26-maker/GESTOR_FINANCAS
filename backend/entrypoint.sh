#!/bin/sh
set -e

echo "Aplicando migrações..."
python manage.py migrate --noinput

echo "Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo "Garantindo superusuário de dev..."
python manage.py shell < scripts/ensure_dev_superuser.py

exec "$@"