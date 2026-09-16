"""Serializers para Fatura e CobrancaRecorrente."""
import html
import re

from rest_framework import serializers

from apps.clientes.models import Cliente
from .models import CobrancaRecorrente, Fatura


def _strip_tags(valor):
    """Remove tags HTML de uma string (mitigação de XSS).

    Usa apenas a stdlib: html.unescape decodifica entidades (&lt;b&gt; -> <b>)
    e o regex remove qualquer marcação <...>, repetindo até não restarem
    tags (ex.: "&lt;scri<b>pt&gt;" viraria "<script>" após uma passada única).
    """
    if not isinstance(valor, str):
        return valor
    texto = html.unescape(valor)
    padrao_tag = re.compile(r"<[^>]*>")
    while True:
        novo = padrao_tag.sub("", texto)
        if novo == texto:
            break
        texto = html.unescape(novo)
    return texto.strip()


class FaturaSerializer(serializers.ModelSerializer):
    """Serializer do modelo Fatura. Status é strictly read-only."""

    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    comprovante = serializers.FileField(read_only=True, required=False, allow_null=True)
    comprovante_url = serializers.SerializerMethodField()

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
            "comprovante",
            "comprovante_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "data_pagamento",
            "comprovante",
            "comprovante_url",
            "created_at",
            "updated_at",
        ]

    def get_comprovante_url(self, obj: Fatura) -> str | None:
        """URL absoluta do comprovante, se houver (usada pelo ícone 📎)."""
        if not obj.comprovante:
            return None
        request = self.context.get("request")
        if request is not None:
            return request.build_absolute_uri(obj.comprovante.url)
        return obj.comprovante.url

    # Campos de texto livres que recebem strip de tags HTML na entrada.
    CAMPOS_TEXTO_SANITIZADOS = ("numero", "descricao")

    def to_internal_value(self, data):
        """Sanitiza a ENTRADA antes da validação por campo."""
        if hasattr(data, "items"):
            dados = dict(data)
            for campo in self.CAMPOS_TEXTO_SANITIZADOS:
                valor = dados.get(campo)
                if isinstance(valor, str):
                    dados[campo] = _strip_tags(valor)
            data = dados
        return super().to_internal_value(data)

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

    def validate(self, attrs):
        """Sanitização já feita em to_internal_value (entrada)."""
        return attrs


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

    # Campos de texto livres que recebem strip de tags HTML na entrada.
    CAMPOS_TEXTO_SANITIZADOS = ("descricao",)

    def to_internal_value(self, data):
        """Sanitiza a ENTRADA antes da validação por campo."""
        if hasattr(data, "items"):
            dados = dict(data)
            for campo in self.CAMPOS_TEXTO_SANITIZADOS:
                valor = dados.get(campo)
                if isinstance(valor, str):
                    dados[campo] = _strip_tags(valor)
            data = dados
        return super().to_internal_value(data)

    def validate_cliente(self, value: Cliente) -> Cliente:
        """Impede vincular cobrança a cliente de outro usuário (multi-tenancy)."""
        if value.owner_id != self.context["request"].user.pk:
            raise serializers.ValidationError(
                "Cliente não encontrado para este usuário.")
        return value
