from django.contrib import admin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "documento", "tipo_pessoa", "papel", "ativo")
    list_filter = ("papel", "tipo_pessoa", "ativo")
    search_fields = ("nome", "documento", "email", "telefone")