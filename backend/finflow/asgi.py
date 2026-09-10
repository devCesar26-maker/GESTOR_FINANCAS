"""Configuração ASGI para o projeto FinFlow."""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finflow.settings")

application = get_asgi_application()