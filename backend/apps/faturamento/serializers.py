"""Serializers para Fatura e CobrancaRecorrente."""
from rest_framework import serializers

from apps.clientes.models import Cliente
from .models import CobrancaRecorrente, Fatura


class FaturaSerializer(serializers.ModelSerializer):
    """Serializer do modelo Fatura. Status é strictly read-only."""

    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)

    class Meta:
        model = Fatura
        fields = [
            "id",
            "numero",
            "cliente",
            "cliente_nome",
            "descricao",
            "tipo",
            "valor",
            "status",
            "vencimento",
            "data_pagamento",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "status", "data_pagamento", "created_at", "updated_at"]

    def validate_cliente(self, value: Cliente) -> Cliente:
        """Impede vincular fatura a cliente de outro usuário (multi-tenancy)."""
        if value.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError(
                "Cliente não encontrado para este usuário."
            )
        return value


class CobrancaRecorrenteSerializer(serializers.ModelSerializer):
    """Serializer do modelo CobrancaRecorrente."""

    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)

    class Meta:
        model = CobrancaRecorrente
        fields = [
            "id",
            "cliente",
            "cliente_nome",
            "descricao",
            "tipo",
            "valor",
            "periodicidade",
            "dia_vencimento",
            "proxima_cobranca",
            "ativa",
            "ultima_execucao",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "ultima_execucao", "created_at", "updated_at"]

    def validate_cliente(self, value: Cliente) -> Cliente:
        """Impede vincular cobrança a cliente de outro usuário (multi-tenancy)."""
        if value.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError(
                "Cliente não encontrado para este usuário.")
        return value