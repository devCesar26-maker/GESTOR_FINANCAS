"""
Testes dos lembretes de vencimento por e-mail (Fase 3).

Usam o backend de teste (configurado em settings_test como
anymail.backends.test.EmailBackend, capturado via fixture mailoutbox)
— nenhum e-mail real é enviado. Cobrem as regras da spec: envio quando a
condição é satisfeita, idempotência no mesmo dia, fatura paga/cancelada
não recebe, cliente com notificacoes_ativas=False não recebe.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.conf import settings
from django.utils import timezone

from apps.clientes.models import Cliente, Papel
from apps.faturamento import services
from apps.faturamento.models import Fatura, StatusFatura, TipoFatura

HOJE = timezone.localdate()
DIAS = getattr(settings, "LEMRETE_DIAS_ANTES", 3)
ZERADO = {
    "lembretes_previos_enviados": 0,
    "lembretes_vencimento_enviados": 0,
    "falhas": 0,
}


def _criar_fatura(
    cliente,
    owner,
    *,
    numero="FAT-LEM-1",
    vencimento=HOJE,
    status=StatusFatura.PENDENTE,
    tipo=TipoFatura.A_RECEBER,
):
    return Fatura.objects.create(
        numero=numero,
        cliente=cliente,
        tipo=tipo,
        valor=Decimal("350.00"),
        descricao="Consultoria mensal",
        status=status,
        vencimento=vencimento,
        owner=owner,
    )


@pytest.fixture
def cliente_com_email(user):
    return Cliente.objects.create(
        nome="Maria Cliente",
        papel=Papel.CLIENTE,
        email="maria@cliente.com",
        owner=user,
    )


@pytest.fixture
def fatura_vence_em_3_dias(cliente_com_email, user):
    return _criar_fatura(
        cliente_com_email,
        user,
        numero="FAT-LEM-PREV",
        vencimento=HOJE + timedelta(days=DIAS),
    )


@pytest.fixture
def fatura_vence_hoje(cliente_com_email, user):
    return _criar_fatura(cliente_com_email, user, numero="FAT-LEM-HOJE", vencimento=HOJE)


# ---------------------------------------------------------------------------
# Envio quando a condição é satisfeita
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_envia_lembrete_previo(mailoutbox, fatura_vence_em_3_dias):
    resultado = services.enviar_lembretes_vencimento()

    assert resultado["lembretes_previos_enviados"] == 1
    assert len(mailoutbox) == 1

    email = mailoutbox[0]
    assert email.to == ["maria@cliente.com"]
    assert f"FAT-LEM-PREV vence em {DIAS} dias" in email.subject
    # DecimalField é localizado pelo Django (pt-BR): vírgula como separador decimal.
    assert "R$ 350,00" in email.body
    assert "Maria Cliente" in email.body
    # Assinatura com o nome do dono da fatura
    assert fatura_vence_em_3_dias.owner.get_username() in email.body


@pytest.mark.django_db
def test_envia_lembrete_de_vencimento_hoje(mailoutbox, fatura_vence_hoje):
    resultado = services.enviar_lembretes_vencimento()

    assert resultado["lembretes_vencimento_enviados"] == 1
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.to == ["maria@cliente.com"]
    assert fatura_vence_hoje.numero in email.subject


@pytest.mark.django_db
def test_data_de_envio_gravada_apos_sucesso(fatura_vence_em_3_dias, fatura_vence_hoje):
    services.enviar_lembretes_vencimento()

    fatura_vence_em_3_dias.refresh_from_db()
    fatura_vence_hoje.refresh_from_db()
    assert fatura_vence_em_3_dias.lembrete_previo_enviado_em is not None
    assert fatura_vence_hoje.lembrete_vencimento_enviado_em is not None


# ---------------------------------------------------------------------------
# Idempotência: rodar duas vezes no mesmo dia não duplica
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rodar_duas_vezes_nao_duplica_envio(
    mailoutbox, fatura_vence_em_3_dias, fatura_vence_hoje
):
    primeiro = services.enviar_lembretes_vencimento()
    assert primeiro["lembretes_previos_enviados"] == 1
    assert primeiro["lembretes_vencimento_enviados"] == 1
    assert len(mailoutbox) == 2

    segundo = services.enviar_lembretes_vencimento()
    assert segundo == ZERADO
    assert len(mailoutbox) == 2  # nada novo foi enviado


@pytest.mark.django_db
def test_lembrete_enviado_via_task_celery(mailoutbox, fatura_vence_hoje):
    from apps.faturamento.tasks import task_enviar_lembretes_vencimento

    task_enviar_lembretes_vencimento()
    assert len(mailoutbox) == 1


# ---------------------------------------------------------------------------
# Fatura paga / cancelada / vencida não recebe
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status", [StatusFatura.PAGA, StatusFatura.CANCELADA, StatusFatura.VENCIDA]
)
def test_fatura_nao_pendente_nao_recebe_lembrete(
    mailoutbox, cliente_com_email, user, status
):
    _criar_fatura(
        cliente_com_email, user, numero=f"FAT-{status}", status=status
    )
    resultado = services.enviar_lembretes_vencimento()
    assert resultado == ZERADO
    assert len(mailoutbox) == 0


# ---------------------------------------------------------------------------
# Cliente com notificacoes_ativas=False nunca recebe
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_cliente_sem_notificacoes_nao_recebe(mailoutbox, user):
    cliente = Cliente.objects.create(
        nome="Sem Lembretes",
        papel=Papel.CLIENTE,
        email="sem@lembrete.com",
        notificacoes_ativas=False,
        owner=user,
    )
    _criar_fatura(cliente, user, numero="FAT-SEM-NOTIF", vencimento=HOJE)
    _criar_fatura(
        cliente,
        user,
        numero="FAT-SEM-NOTIF-PREV",
        vencimento=HOJE + timedelta(days=DIAS),
    )

    resultado = services.enviar_lembretes_vencimento()
    assert resultado == ZERADO
    assert len(mailoutbox) == 0


# ---------------------------------------------------------------------------
# Outras salvaguardas
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_fatura_a_pagar_nao_gera_lembrete(mailoutbox, cliente_com_email, user):
    """Escopo aprovado: lembretes apenas para faturas a_receber."""
    _criar_fatura(
        cliente_com_email,
        user,
        numero="FAT-A-PAGAR",
        vencimento=HOJE,
        tipo=TipoFatura.A_PAGAR,
    )
    resultado = services.enviar_lembretes_vencimento()
    assert resultado == ZERADO
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_cliente_sem_email_e_pulado(mailoutbox, user):
    cliente = Cliente.objects.create(nome="Sem Email", owner=user)  # email=""
    _criar_fatura(cliente, user, numero="FAT-SEM-EMAIL", vencimento=HOJE)
    resultado = services.enviar_lembretes_vencimento()
    assert resultado == ZERADO
    assert len(mailoutbox) == 0


@pytest.mark.django_db
def test_owner_scoped_nao_envia_lembrete_de_outro_usuario(
    mailoutbox, django_user_model, user
):
    """Com owner informado (ex.: execução por usuário), ignora faturas alheias."""
    outro = django_user_model.objects.create_user(
        username="outro@finflow.com",
        email="outro@finflow.com",
        password="senha-outro-123",
    )
    cliente_do_outro = Cliente.objects.create(
        nome="Cliente do Outro", email="outro-cliente@x.com", owner=outro
    )
    _criar_fatura(cliente_do_outro, outro, numero="FAT-OUTRO", vencimento=HOJE)

    resultado = services.enviar_lembretes_vencimento(owner=user)
    assert resultado == ZERADO
    assert len(mailoutbox) == 0

    # Sem restrição de owner (task agendada), a fatura é elegível...
    resultado_todos = services.enviar_lembretes_vencimento()
    assert resultado_todos["lembretes_vencimento_enviados"] == 1
    assert mailoutbox[0].to == ["outro-cliente@x.com"]
