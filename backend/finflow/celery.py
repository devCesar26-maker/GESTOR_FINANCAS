"""Configuração do Celery para o projeto FinFlow."""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "finflow.settings")

app = Celery("finflow")
app.config_from_object("django.conf:settings", namespace="CELERY")

# Descobre tasks automaticamente em apps/<app>/tasks.py
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")