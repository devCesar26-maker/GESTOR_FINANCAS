"""
Modelos do app Clientes.

Camada de dados: apenas representação do domínio (clientes e fornecedores).
Regras de negócio que envolvem esses dados ficam em services.py.
"""
from django.db import models


class Papel(models.TextChoices):
    """Papel do contato no negócio: cliente ou fornecedor."""

    CLIENTE = "cliente", "Cliente"
    FORNECEDOR = "fornecedor", "Fornecedor"


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
    documento = models.CharField(
        "CPF/CNPJ", max_length=20, unique=True, blank=True, null=True
    )
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    endereco = models.CharField("endereço", max_length=255, blank=True)
    ativo = models.BooleanField("ativo", default=True)

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        verbose_name = "cliente"
        verbose_name_plural = "clientes"
        ordering = ["nome"]
        indexes = [
            models.Index(fields=["papel", "ativo"], name="cli_papel_ativo_idx"),
        ]

    def __str__(self) -> str:
        return self.nome