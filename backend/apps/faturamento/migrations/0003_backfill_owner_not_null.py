"""Backfill do owner (registros antigos → superusuário designado) + NOT NULL.

Mesma estratégia da migração 0003 de clientes: registros de Fatura e
CobrancaRecorrente sem dono passam ao superusuário designado e o campo
owner torna-se obrigatório (NOT NULL).
"""

import os

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_owner(apps, schema_editor):
    Usuario = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Fatura = apps.get_model("faturamento", "Fatura")
    CobrancaRecorrente = apps.get_model("faturamento", "CobrancaRecorrente")

    pendentes = (
        Fatura.objects.filter(owner__isnull=True).exists()
        or CobrancaRecorrente.objects.filter(owner__isnull=True).exists()
    )
    if not pendentes:
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
            "Backfill de owner: há faturas/cobranças sem dono, mas nenhum "
            f"usuário candidato foi encontrado (username={username!r}). "
            "Crie o superusuário antes de aplicar esta migração."
        )
    Fatura.objects.filter(owner__isnull=True).update(owner=alvo)
    CobrancaRecorrente.objects.filter(owner__isnull=True).update(owner=alvo)


class Migration(migrations.Migration):

    dependencies = [
        ("faturamento", "0002_cobrancarecorrente_owner_fatura_owner"),
    ]

    operations = [
        migrations.RunPython(backfill_owner, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="cobrancarecorrente",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="cobrancas_recorrentes",
                to=settings.AUTH_USER_MODEL,
                verbose_name="dono",
            ),
        ),
        migrations.AlterField(
            model_name="fatura",
            name="owner",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="faturas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="dono",
            ),
        ),
    ]
