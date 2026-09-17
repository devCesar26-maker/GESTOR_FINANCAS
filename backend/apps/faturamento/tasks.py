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


@shared_task
def task_enviar_lembretes_vencimento():
    """Envia lembretes de vencimento por e-mail.

    Janelas de disparo em relação ao vencimento: 10 dias antes, 5 dias
    antes, 1 dia antes e no dia do vencimento (0 dias). Cada janela envia
    uma única vez por fatura (idempotência pelos campos lembrete_*_enviado_em).
    """
    resultado = services.enviar_lembretes_vencimento()
    return (
        "Lembretes: {previos} prévios enviados (janelas 10/5/1 dias), "
        "{hoje} de vencimento hoje, {falhas} falha(s).".format(
            previos=resultado["lembretes_previos_enviados"],
            hoje=resultado["lembretes_vencimento_enviados"],
            falhas=resultado["falhas"],
        )
    )
