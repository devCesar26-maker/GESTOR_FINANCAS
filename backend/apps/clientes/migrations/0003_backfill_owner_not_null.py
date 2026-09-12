"""Backfill do owner (registros antigos → superusuário designado) + NOT NULL.

Fase 1 (multi-tenancy), aprovado pelo usuário:
- Registros existentes sem dono passam a pertencer ao superusuário de
  administração (o usado para testar/logar no sistema).
- O campo owner torna-se obrigatório (NOT NULL), refletindo o comportamento
  da API, onde todo registro criado recebe o usuário autenticado como dono.

O usuário-alvo do backfill é escolhido nesta ordem:
1. username em DJANGO_SUPERUSER_USERNAME (padrão: "admin") — superusuário ou não;
2. primeiro superusuário ativo do banco;
3. primeiro superusuário do banco.
Se houver registros sem dono e nenhum usuário candidato, a migração falha
explicitamente (não deixa dados órfãos silenciosamente).
"""

import os

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_owner(apps, schema_editor):
    Usuario = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Cliente = apps.get_model("clientes", "Cliente")

    sem_dono = Cliente.objects.filter(owner__isnull=True)
    if not sem_dono.exists():
        return

    username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
    alvo = (
        Usuario.objects.filter(username=username, is_superuser=True).first()
        or Usuario.objects.filter(username=username).first()
        or Usuario.objects.filter(is_superuser=True, is_active=True)
        .order_by("pk")
        .first()
        or Usuario.objects.filter(is_superuser=True).order_by("pk").first()
    )
    if alvo is None:
        raise ValueError(
            "Backfill de owner: há clientes sem dono, mas nenhum usuário "
            f"candidato foi encontrado (username={username!r}). Crie o "
            "superusuário antes de aplicar esta migração."
        )
    sem_dono.update(owner=alvo)


class Migration(migrations.Migration):

    dependencies = [
        ("clientes", "0002_cliente_owner"),
    ]

    operations = [
        migrations.RunPython(backfill_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="cliente",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="clientes",
                to=settings.AUTH_USER_MODEL,
                verbose_name="dono",
            ),
        ),
    ]
