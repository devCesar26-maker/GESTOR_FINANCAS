from django.contrib import admin

from .models import CategoriaFinanceira, CobrancaRecorrente, Fatura


@admin.register(Fatura)
class FaturaAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "categoria", "tipo", "valor", "status", "vencimento")
    list_filter = ("status", "tipo", "categoria")
    search_fields = ("numero", "cliente__nome", "descricao")
    date_hierarchy = "vencimento"


@admin.register(CobrancaRecorrente)
class CobrancaRecorrenteAdmin(admin.ModelAdmin):
    list_display = (
        "descricao",
        "cliente",
        "categoria",
        "valor",
        "periodicidade",
        "proxima_cobranca",
        "ativa",
    )
    list_filter = ("periodicidade", "ativa", "categoria")
    search_fields = ("descricao", "cliente__nome")


@admin.register(CategoriaFinanceira)
class CategoriaFinanceiraAdmin(admin.ModelAdmin):
    list_display = ("nome", "natureza", "owner")
    list_filter = ("natureza",)
    search_fields = ("nome",)
