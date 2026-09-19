"""
Modelos do app Clientes.

Camada de dados: apenas representação do domínio (clientes e fornecedores).
Regras de negócio que envolvem esses dados ficam em services.py.
"""
from django.conf import settings
from django.db import models


class Papel(models.TextChoices):
    """Papel do contato no negócio: cliente, fornecedor ou ambos.

    "ambos" cobre a entidade que é cliente E fornecedor do mesmo gestor
    (ex.: uma gráfica que vende material gráfico ao gestor e também
    prestação de serviço a ele). Faturas a_receber E a_pagar podem
    referenciá-la — não há vínculo entre papel do cliente e tipo da fatura.
    """

    CLIENTE = "cliente", "Cliente"
    FORNECEDOR = "fornecedor", "Fornecedor"
    AMBOS = "ambos", "Cliente/Fornecedor"


class TipoPessoa(models.TextChoices):
    """Natureza jurídica da pessoa: física (CPF) ou jurídica (CNPJ)."""

    FISICA = "pf", "Pessoa física"
    JURIDICA = "pj", "Pessoa jurídica"


class Cliente(models.Model):
    """Cliente ou fornecedor da empresa."""

    nome = models.CharField("nome", max_length=200)
    papel = models.CharField(
        "papel",
        max_length=20,
        choices=Papel.choices,
        default=Papel.CLIENTE,
    )
    tipo_pessoa = models.CharField(
        "tipo de pessoa",
        max_length=20,
        choices=TipoPessoa.choices,
        default=TipoPessoa.FISICA,
    )
    # NOTA (multi-tenancy): o documento NÃO é único globalmente — a mesma
    # pessoa/empresa pode ser cliente de vários gestores ao mesmo tempo. A
    # unicidade vale apenas DENTRO de cada owner (constraint composta no Meta).
    documento = models.CharField("CPF/CNPJ", max_length=20, blank=True, null=True)
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    ativo = models.BooleanField("ativo", default=True)
    # Quando False, este cliente/fornecedor NUNCA recebe lembretes
    # automáticos de vencimento, mesmo que as condições de data sejam
    # satisfeitas (Fase 3).
    notificacoes_ativas = models.BooleanField(
        "notificações ativas", default=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clientes",
        verbose_name="dono",
    )

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["papel", "ativo"], name="cli_papel_ativo_idx"),
        ]
        constraints = [
            # Mesmo documento só se repete entre owners diferentes, nunca
            # duas vezes no cadastro do mesmo gestor. Nulls são permitidos
            # (documento é opcional) e não participam da comparação.
            models.UniqueConstraint(
                fields=["owner", "documento"],
                name="uniq_cliente_owner_documento",
            ),
        ]

    def __str__(self) -> str:
        return self.nome