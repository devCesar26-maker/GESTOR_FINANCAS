"""Tasks do app Usuarios (e-mail de boas-vindas ao gestor)."""
import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task
def task_enviar_email_boas_vindas(user_id: int) -> str:
    """Envia e-mail de boas-vindas ao gestor recém-registrado.

    E-mail one-shot: erro de envio é logado e NÃO relançado (sem retry do
    Celery) — a conta já foi criada e o login funciona imediatamente; o
    e-mail é apenas informativo e nunca deve reenviar.
    """
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.filter(pk=user_id).first()
    if user is None or not user.email:
        return "Usuário não encontrado ou sem e-mail; boas-vindas não enviada."

    contexto = {
        "nome": (user.get_full_name() or user.username).strip(),
        "email": user.email,
    }
    assunto = render_to_string(
        "usuarios/emails/boas_vindas_assunto.txt", contexto
    ).strip()
    corpo = render_to_string("usuarios/emails/boas_vindas.txt", contexto)

    try:
        send_mail(
            subject=assunto,
            message=corpo,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        logger.exception(
            "Falha ao enviar e-mail de boas-vindas para %s", user.email
        )
        return f"Falha ao enviar boas-vindas para {user.email}."
    return f"Boas-vindas enviada para {user.email}."
