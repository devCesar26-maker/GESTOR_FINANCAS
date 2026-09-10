"""Tarefas periódicas do Celery para o app Faturamento."""
from celery import shared_task
from . import services


@shared_task
def task_processar_cobrancas_recorrentes():
    """Gera faturas automáticas para cobranças recorrentes devidas."""
    faturas = services.processar_cobrancas_recorrentes()
    return f"{len(faturas)} faturas geradas a partir de cobranças recorrentes."


@shared_task
def task_marcar_faturas_vencidas():
    """Marca faturas pendentes com vencimento ultrapassado como vencidas."""
    qtd = services.marcar_faturas_vencidas()
    return f"{qtd} faturas marcadas como vencidas."
