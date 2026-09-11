"""Camada de serializers do app Clientes."""
import re
from rest_framework import serializers

from .models import Cliente, TipoPessoa
from .validators import validar_cnpj, validar_cpf


class ClienteSerializer(serializers.ModelSerializer):
    """Serializer completo utilizado para detalhes, criação e edição de cliente."""

    class Meta:
        model = Cliente
        fields = (
            "id",
            "nome",
            "papel",
            "tipo_pessoa",
            "documento",
            "email",
            "telefone",
            "endereco",
            "ativo",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_documento(self, value):
        value = (value or "").strip() or None
        if value is None:
            return value
        queryset = Cliente.objects.all()
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(documento=value).exists():
            raise serializers.ValidationError(
                "Já existe um cliente com este documento."
            )
        return value

    def validate(self, attrs):
        documento = attrs.get(
            "documento", self.instance.documento if self.instance else None
        )
        tipo_pessoa = attrs.get(
            "tipo_pessoa",
            self.instance.tipo_pessoa if self.instance else TipoPessoa.FISICA,
        )
        if documento:
            if tipo_pessoa == TipoPessoa.FISICA:
                valido = validar_cpf(documento)
            elif tipo_pessoa == TipoPessoa.JURIDICA:
                valido = validar_cnpj(documento)
            else:
                valido = False
            if not valido:
                raise serializers.ValidationError(
                    {
                        "documento": (
                            "Documento inválido para o tipo de pessoa informado. "
                            "Informe um CPF válido (pessoa física) ou um CNPJ "
                            "válido (pessoa jurídica)."
                        )
                    }
                )
        return attrs


# Alias para detalhe
ClienteDetailSerializer = ClienteSerializer


class ClienteListSerializer(ClienteSerializer):
    """Serializer para listagem com documento mascarado por razões de LGPD."""

    documento = serializers.SerializerMethodField()

    def get_documento(self, obj: Cliente) -> str | None:
        if not obj.documento:
            return None
        doc = re.sub(r"\D", "", obj.documento)
        if len(doc) == 11:
            # CPF: 529.***.***-25
            return f"{doc[:3]}.***.***-{doc[-2:]}"
        elif len(doc) == 14:
            # CNPJ: **.***.247/0001-**
            return f"**.***.{doc[5:8]}/{doc[8:12]}-**"
        return obj.documento