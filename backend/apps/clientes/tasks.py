"""Tasks do app Clientes (notificação de cadastro ao cliente/fornecedor)."""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task
def task_enviar_email_cadastro_cliente(cliente_id: int) -> str:
    """Notifica o cliente/fornecedor de que foi cadastrado na plataforma.

    E-mail ÚNICO e informativo (transparência de dados), INDEPENDENTE do
    campo notificacoes_ativas — que controla apenas os lembretes
    recorrentes de vencimento (Fase 3). Dispara sempre na criação do
    cliente. One-shot: falha de envio é logada e não reenvia.
    """
    from .models import Cliente

    cliente = Cliente.objects.select_related("owner").filter(pk=cliente_id).first()
    if cliente is None or not cliente.email:
        return "Cliente não encontrado ou sem e-mail; notificação não enviada."

    owner = cliente.owner
    contexto = {
        "cliente_nome": cliente.nome,
        "gestor": (owner.get_full_name() or owner.username).strip(),
        "papel_label": cliente.get_papel_display(),  # "Cliente" ou "Fornecedor"
    }
    assunto = render_to_string(
        "clientes/emails/cadastro_cliente_assunto.txt", contexto
    ).strip()
    corpo = render_to_string("clientes/emails/cadastro_cliente.txt", contexto)

    try:
        send_mail(
            subject=assunto,
            message=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[cliente.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Falha ao enviar notificação de cadastro do cliente %s", cliente.pk
        )
        return f"Falha ao notificar cadastro do cliente {cliente.pk}."
    return f"Notificação de cadastro enviada para {cliente.email}."
