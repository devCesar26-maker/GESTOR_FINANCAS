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


class CategoriaFinanceira(models.Model):
    """Centro de custo/receita: agrupa faturas para o DRE e o Dashboard.

    Cada owner mantém seu próprio catálogo (multi-tenancy); a lista inicial
    de sugestões vem de CATEGORIAS_PADRAO. A aparência no gráfico (cor e
    agrupamento receita/despesa) é derivada daqui.
    """

    class Natureza(models.TextChoices):
        RECEITA = "receita", "Receita"
        DESPESA = "despesa", "Despesa"

    CATEGORIAS_PADRAO = [
        # (nome, natureza)
        ("Vendas de Serviços", Natureza.RECEITA),
        ("Vendas de Produtos", Natureza.RECEITA),
        ("Outras Receitas", Natureza.RECEITA),
        ("Aluguel", Natureza.DESPESA),
        ("Salários", Natureza.DESPESA),
        ("Infraestrutura", Natureza.DESPESA),
        ("Impostos", Natureza.DESPESA),
        ("Outras Despesas", Natureza.DESPESA),
    ]

    nome = models.CharField("nome", max_length=100)
    natureza = models.CharField(
        "natureza",
        max_length=20,
        choices=Natureza.choices,
        default=Natureza.DESPESA,
        help_text="Define se a categoria agrupa receitas ou despesas no DRE.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="categorias_financeiras",
        verbose_name="dono",
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "categoria financeira"
        verbose_name_plural = "categorias financeiras"
        ordering = ["nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "nome"],
                name="uniq_categoria_owner_nome",
            ),
        ]

    def __str__(self) -> str:
        return self.nome

    @classmethod
    def criar_categorias_padrao(cls, owner) -> None:
        """Semeia o catálogo padrão de categorias para um owner (idempotente)."""
        cls.objects.bulk_create(
            [
                cls(owner=owner, nome=nome, natureza=natureza)
                for nome, natureza in cls.CATEGORIAS_PADRAO
            ],
            ignore_conflicts=True,
        )


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
    # Comprovante de pagamento (OBRIGATÓRIO no ato de pagar — validado na
    # view/action `pagar`, não aqui, para não quebrar faturas antigas).
    # Aceito apenas PDF/JPEG/PNG/WEBP com até 5MB (ver services._validar_arquivo).
    comprovante = models.FileField(
        "comprovante",
        upload_to="comprovantes/%Y/%m/",
        blank=True,
        null=True,
    )
    # Controle de idempotência dos lembretes de vencimento (Fase 3):
    # gravados após o envio; None = lembrete ainda não enviado.
    lembrete_previo_enviado_em = models.DateTimeField(
        "lembrete prévio enviado em", blank=True, null=True
    )
    lembrete_vencimento_enviado_em = models.DateTimeField(
        "lembrete de vencimento enviado em", blank=True, null=True
    )
    # Categorização financeira (centros de custo): NULL = "Sem categoria".
    categoria = models.ForeignKey(
        "faturamento.CategoriaFinanceira",
        on_delete=models.SET_NULL,
        related_name="faturas",
        verbose_name="categoria",
        blank=True,
        null=True,
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
    # Categorização financeira (centros de custo): herdada pela fatura gerada.
    categoria = models.ForeignKey(
        "faturamento.CategoriaFinanceira",
        on_delete=models.SET_NULL,
        related_name="cobrancas_recorrentes",
        verbose_name="categoria",
        blank=True,
        null=True,
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