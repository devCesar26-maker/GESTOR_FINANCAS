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

    def validate_numero(self, value):
        """Unicidade do número por owner (multi-tenancy).

        Dois gestores independentes podem ter faturas com o mesmo número;
        o mesmo gestor, não. A constraint composta (owner, numero) garante
        isso no banco; aqui devolvemos um 400 amigável em vez de estouro de
        IntegrityError (a validação automática do DRF só cobre updates).
        """
        queryset = Fatura.objects.filter(owner=self.context["request"].user)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(numero=value).exists():
            raise serializers.ValidationError(
                "Já existe uma fatura com este número no seu cadastro."
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