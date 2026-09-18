"""
Testes dos lembretes de vencimento por e-mail (Fase 3 — janelas expandidas).

Usam o backend de teste (configurado em settings_test como
anymail.backends.test.EmailBackend, capturado via fixture mailoutbox)
— nenhum e-mail real é enviado. Cobrem as regras da spec: envio nas
janelas de 10/5/1 dia(s) antes e no dia do vencimento (0), idempotência
no mesmo dia, fatura paga/cancelada não recebe, cliente com
notificacoes_ativas=False não recebe.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.clientes.models import Cliente, Papel
from apps.faturamento import services
from apps.faturamento.models import Fatura, StatusFatura, TipoFatura

HOJE = timezone.localdate()
# Janelas da spec: prévios em 10/5/1 dias + aviso no dia (0).
JANELAS = services.LEMBRETES_JANELAS_DIAS  # (10, 5, 1)
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


def _fatura_vence_em(cliente, owner, dias, numero="FAT-LEM-PREV"):
    return _criar_fatura(
        cliente, owner, numero=numero, vencimento=HOJE + timedelta(days=dias)
    )


# ---------------------------------------------------------------------------
# Envio quando a condição é satisfeita (janelas 10/5/1/0)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("dias", JANELAS)
def test_envia_lembrete_previo_em_cada_janela(mailoutbox, cliente_com_email, user, dias):
    """Cada janela prévia (10, 5 e 1 dias) dispara o e-mail da sua régua.

    Réguas: 10 dias = lembrete preventivo amigável; 5 e 1 dia(s) =
    notificação formal de vencimento próximo (templates distintos).
    """
    _fatura_vence_em(cliente_com_email, user, dias, numero=f"FAT-J{dias}")

    resultado = services.enviar_lembretes_vencimento()

    assert resultado["lembretes_previos_enviados"] == 1
    assert len(mailoutbox) == 1

    email = mailoutbox[0]
    assert email.to == ["maria@cliente.com"]
    if dias >= 10:
        # Régua preventiva (10 dias)
        esperado = f"FAT-J{dias} vence em {dias} dias"
        assert esperado in email.subject
        assert "lembrete preventivo" in email.body
    elif dias == 1:
        # Régua formal (1 dia)
        assert "Vencimento próximo: fatura FAT-J1" in email.subject
        assert "vence amanhã" in email.body
    else:
        # Régua formal (5 dias)
        assert f"Vencimento próximo: fatura FAT-J{dias}" in email.subject
        assert f"em {dias} dias" in email.body
    # DecimalField é localizado pelo Django (pt-BR): vírgula como separador decimal.
    assert "R$ 350,00" in email.body
    assert "Maria Cliente" in email.body
    # Assinatura com o nome do dono da fatura
    assert user.get_username() in email.body


@pytest.mark.django_db
def test_envia_lembrete_de_vencimento_hoje(mailoutbox, cliente_com_email, user):
    _fatura_vence_em(cliente_com_email, user, 0, numero="FAT-LEM-HOJE")

    resultado = services.enviar_lembretes_vencimento()

    assert resultado["lembretes_vencimento_enviados"] == 1
    assert len(mailoutbox) == 1
    email = mailoutbox[0]
    assert email.to == ["maria@cliente.com"]
    assert "FAT-LEM-HOJE" in email.subject


# ---------------------------------------------------------------------------
# Tom corporativo por régua + dados de pagamento (PIX) no corpo
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_corpo_inclui_dados_completos_e_pix(mailoutbox, cliente_com_email, user, settings):
    """Corpo traz nome, fatura, valor R$, vencimento e a chave PIX configurada."""
    settings.DADOS_PAGAMENTO = {
        "chave_pix": "pagamentos@finflow.com",
        "favorecido": "FinFlow LTDA",
    }
    _fatura_vence_em(cliente_com_email, user, 0, numero="FAT-PIX")

    services.enviar_lembretes_vencimento()

    corpo = mailoutbox[0].body
    assert "Maria Cliente" in corpo            # nome do cliente
    assert "FAT-PIX" in corpo                  # número da fatura
    assert "R$ 350,00" in corpo                # valor formatado
    assert "Vencimento:" in corpo              # data de vencimento
    assert "Chave PIX: pagamentos@finflow.com" in corpo
    assert "Favorecido: FinFlow LTDA" in corpo
    assert "comprovante" in corpo.lower()      # instrução de envio


@pytest.mark.django_db
def test_corpo_sem_chave_pix_orienta_solicitar_dados(
    mailoutbox, cliente_com_email, user, settings
):
    """Sem chave PIX configurada, o e-mail orienta a solicitar os dados."""
    settings.DADOS_PAGAMENTO = {"chave_pix": "", "favorecido": ""}
    _fatura_vence_em(cliente_com_email, user, 5, numero="FAT-SEM-PIX")

    services.enviar_lembretes_vencimento()

    corpo = mailoutbox[0].body
    assert "Chave PIX:" not in corpo
    assert "podem ser solicitados" in corpo


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("dias", "trecho"),
    [(10, "lembrete preventivo"), (5, "Solicitamos, por gentileza"), (1, "vence amanhã")],
)
def test_tom_por_regua_de_vencimento(
    mailoutbox, cliente_com_email, user, dias, trecho
):
    """10d preventivo amigável; 5d/1d notificação formal; 0d com comprovante."""
    _fatura_vence_em(cliente_com_email, user, dias, numero=f"FAT-TOM-{dias}")

    services.enviar_lembretes_vencimento()

    assert trecho in mailoutbox[0].body


@pytest.mark.django_db
def test_vencimento_hoje_pede_envio_de_comprovante(
    mailoutbox, cliente_com_email, user
):
    _fatura_vence_em(cliente_com_email, user, 0, numero="FAT-COMPROVANTE")

    services.enviar_lembretes_vencimento()

    corpo = mailoutbox[0].body
    assert "vence HOJE" in corpo
    assert "envio do comprovante" in corpo


@pytest.mark.django_db
def test_todas_janelas_no_mesmo_dia_de_execucao(mailoutbox, cliente_com_email, user):
    """Faturas que caem nas 4 janelas recebem cada uma seu lembrete."""
    for i, dias in enumerate((*JANELAS, 0)):
        _fatura_vence_em(cliente_com_email, user, dias, numero=f"FAT-MULTI-{i}")

    resultado = services.enviar_lembretes_vencimento()

    assert resultado["lembretes_previos_enviados"] == len(JANELAS)
    assert resultado["lembretes_vencimento_enviados"] == 1
    assert len(mailoutbox) == len(JANELAS) + 1


@pytest.mark.django_db
def test_data_de_envio_gravada_apos_sucesso(cliente_com_email, user):
    f_previa = _fatura_vence_em(cliente_com_email, user, 10, numero="FAT-GRava-10")
    f_hoje = _fatura_vence_em(cliente_com_email, user, 0, numero="FAT-GRAVA-0")

    services.enviar_lembretes_vencimento()

    f_previa.refresh_from_db()
    f_hoje.refresh_from_db()
    assert f_previa.lembrete_previo_enviado_em is not None
    assert f_hoje.lembrete_vencimento_enviado_em is not None


# ---------------------------------------------------------------------------
# Idempotência: rodar duas vezes no mesmo dia não duplica
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_rodar_duas_vezes_nao_duplica_envio(mailoutbox, cliente_com_email, user):
    _fatura_vence_em(cliente_com_email, user, 10, numero="FAT-IDEM-10")
    _fatura_vence_em(cliente_com_email, user, 0, numero="FAT-IDEM-0")

    primeiro = services.enviar_lembretes_vencimento()
    assert primeiro["lembretes_previos_enviados"] == 1
    assert primeiro["lembretes_vencimento_enviados"] == 1
    assert len(mailoutbox) == 2

    segundo = services.enviar_lembretes_vencimento()
    assert segundo == ZERADO
    assert len(mailoutbox) == 2  # nada novo foi enviado


@pytest.mark.django_db
def test_lembrete_enviado_via_task_celery(mailoutbox, cliente_com_email, user):
    from apps.faturamento.tasks import task_enviar_lembretes_vencimento

    _fatura_vence_em(cliente_com_email, user, 0, numero="FAT-TASK")
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
    _fatura_vence_em(cliente, user, 0, numero="FAT-SEM-NOTIF")
    _fatura_vence_em(cliente, user, 10, numero="FAT-SEM-NOTIF-PREV")
    _fatura_vence_em(cliente, user, 5, numero="FAT-SEM-NOTIF-PREV5")

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
def test_dias_fora_das_janelas_nao_envia(mailoutbox, cliente_com_email, user):
    """Vencimentos a 2, 4, 9 ou 11 dias NÃO disparam lembrete prévio."""
    for dias in (2, 4, 9, 11):
        _fatura_vence_em(cliente_com_email, user, dias, numero=f"FAT-FORA-{dias}")

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
