from django.contrib import admin

from .models import CobrancaRecorrente, Fatura


@admin.register(Fatura)
class FaturaAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "tipo", "valor", "status", "vencimento")
    list_filter = ("status", "tipo")
    search_fields = ("numero", "cliente__nome", "descricao")
    date_hierarchy = "vencimento"


@admin.register(CobrancaRecorrente)
class CobrancaRecorrenteAdmin(admin.ModelAdmin):
    list_display = (
        "descricao",
        "cliente",
        "valor",
        "periodicidade",
        "proxima_cobranca",
        "ativa",
    )
    list_filter = ("periodicidade", "ativa")
    search_fields = ("descricao", "cliente__nome")