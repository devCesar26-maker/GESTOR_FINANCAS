"""
Modelos do app Faturamento.

Camada de dados: Fatura e CobrancaRecorrente representam o domínio de
faturamento. Regras de negócio (pagar fatura, gerar cobrança recorrente,
marcar vencidas) ficam em services.py — os models expõem apenas dados e
propriedades de leitura puras.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class TipoFatura(models.TextChoices):
    A_RECEBER = "a_receber", "A receber"
    A_PAGAR = "a_pagar", "A pagar"


class StatusFatura(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    PAGA = "paga", "Paga"
    VENCIDA = "vencida", "Vencida"
    CANCELADA = "cancelada", "Cancelada"


class Periodicidade(models.TextChoices):
    SEMANAL = "semanal", "Semanal"
    QUINZENAL = "quinzenal", "Quinzenal"
    MENSAL = "mensal", "Mensal"
    TRIMESTRAL = "trimestral", "Trimestral"
    SEMESTRAL = "semestral", "Semestral"
    ANUAL = "anual", "Anual"


class Fatura(models.Model):
    """Conta a pagar ou a receber vinculada a um cliente/fornecedor."""

    # NOTA (multi-tenancy): o numero NÃO é único globalmente — dois gestores
    # independentes podem ter faturas com o mesmo número (ex.: FAT-2026-001).
    # A unicidade vale apenas DENTRO de cada owner (constraint composta no Meta).
    numero = models.CharField("número", max_length=20)
    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="faturas",
        verbose_name="cliente",
    )
    descricao = models.CharField("descrição", max_length=255, blank=True)
    tipo = models.CharField(
        "tipo",
        max_length=20,
        choices=TipoFatura.choices,
        default=TipoFatura.A_RECEBER,
    )
    valor = models.DecimalField("valor", max_digits=14, decimal_places=2)
    status = models.CharField(
        "status",
        max_length=20,
        choices=StatusFatura.choices,
        default=StatusFatura.PENDENTE,
    )
    vencimento = models.DateField("vencimento")
    data_pagamento = models.DateTimeField(
        "data de pagamento", blank=True, null=True
    )
    # Controle de idempotência dos lembretes de vencimento (Fase 3):
    # gravados após o envio; None = lembrete ainda não enviado.
    lembrete_previo_enviado_em = models.DateTimeField(
        "lembrete prévio enviado em", blank=True, null=True
    )
    lembrete_vencimento_enviado_em = models.DateTimeField(
        "lembrete de vencimento enviado em", blank=True, null=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="faturas",
        verbose_name="dono",
    )

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "fatura"
        verbose_name_plural = "faturas"
        ordering = ["-vencimento"]
        indexes = [
            models.Index(
                fields=["tipo", "status", "vencimento"],
                name="fat_tipo_status_venc",
            ),
            models.Index(fields=["status", "vencimento"], name="fat_status_venc_idx"),
        ]
        constraints = [
            # Mesmo número só se repete entre owners diferentes, nunca duas
            # vezes na carteira do mesmo gestor.
            models.UniqueConstraint(
                fields=["owner", "numero"],
                name="uniq_fatura_owner_numero",
            ),
            models.CheckConstraint(
                condition=models.Q(valor__gte=0),
                name="fatura_valor_positivo",
                violation_error_message="O valor da fatura não pode ser negativo.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.numero} — {self.cliente} — R$ {self.valor}"

    @property
    def esta_vencida(self) -> bool:
        """Leitura pura: pendente com vencimento no passado.

        A *transição* de status para VENCIDA é responsabilidade da camada
        de services (e da task periódica do Celery), não deste property.
        """
        return (
            self.status == StatusFatura.PENDENTE
            and self.vencimento < timezone.localdate()
        )


class CobrancaRecorrente(models.Model):
    """Regra de geração automática de faturas em intervalos regulares."""

    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="cobrancas_recorrentes",
        verbose_name="cliente",
    )
    descricao = models.CharField("descrição", max_length=255)
    tipo = models.CharField(
        "tipo",
        max_length=20,
        choices=TipoFatura.choices,
        default=TipoFatura.A_RECEBER,
    )
    valor = models.DecimalField("valor", max_digits=14, decimal_places=2)
    periodicidade = models.CharField(
        "periodicidade",
        max_length=20,
        choices=Periodicidade.choices,
    )
    dia_vencimento = models.PositiveSmallIntegerField(
        "dia de vencimento (1 a 31)",
        default=1,
        help_text="Dia do mês em que a fatura vence.",
    )
    proxima_cobranca = models.DateField("próxima cobrança")
    ativa = models.BooleanField("ativa", default=True)
    ultima_execucao = models.DateTimeField(
        "última execução", blank=True, null=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cobrancas_recorrentes",
        verbose_name="dono",
    )

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "cobrança recorrente"
        verbose_name_plural = "cobranças recorrentes"
        ordering = ["-proxima_cobranca"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(dia_vencimento__gte=1)
                & models.Q(dia_vencimento__lte=31),
                name="cobranca_dia_vencimento_valido",
                violation_error_message="O dia de vencimento deve estar entre 1 e 31.",
            ),
            models.CheckConstraint(
                condition=models.Q(valor__gte=0),
                name="cobranca_valor_positivo",
                violation_error_message="O valor da cobrança não pode ser negativo.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.descricao} — {self.cliente} — {self.periodicidade}"