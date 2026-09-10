"""Serializers para Fatura e CobrancaRecorrente."""
from rest_framework import serializers
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