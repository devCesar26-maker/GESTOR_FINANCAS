"""
Garante que um superusuário padrão de desenvolvimento exista.

Idempotente: cria o usuário 'admin' se ele não existir, reativa-o e
restaura a senha se a credencial deixou de funcionar. Nunca remove
is_staff/is_superuser de usuários existentes.

Uso:
    python manage.py shell < scripts/ensure_dev_superuser.py
ou via entrypoint do Docker:
    python manage.py shell < scripts/ensure_dev_superuser.py
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finflow.settings")
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402

USERNAME = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
EMAIL = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@finflow.com")
PASSWORD = os.getenv("DJANGO_SUPERUSER_PASSWORD", "senha-forte-123")

User = get_user_model()

user, created = User.objects.get_or_create(
    username=USERNAME,
    defaults={"email": EMAIL, "is_staff": True, "is_superuser": True},
)
if created:
    user.set_password(PASSWORD)
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f"✔ Superusuário de dev criado: {USERNAME} / {PASSWORD}")
else:
    changed = []
    # Apenas fortalece a conta: reativa e restaura acesso, nunca rebaixa.
    if not user.is_active:
        user.is_active = True
        changed.append("is_active=True")
    if not user.is_staff:
        user.is_staff = True
        changed.append("is_staff=True")
    if not user.is_superuser:
        user.is_superuser = True
        changed.append("is_superuser=True")
    if changed:
        user.save(update_fields=["is_active", "is_staff", "is_superuser"])
        print(f"✔ Conta {USERNAME} reativada ({', '.join(changed)}).")
    if not user.check_password(PASSWORD):
        user.set_password(PASSWORD)
        user.save(update_fields=["password"])
        print(f"✔ Senha de dev restaurada para {USERNAME} / {PASSWORD}")
    if not changed and user.check_password(PASSWORD):
        print(f"✔ Superusuário de dev já OK: {USERNAME}")
