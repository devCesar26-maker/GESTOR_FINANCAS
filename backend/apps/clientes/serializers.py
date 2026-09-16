"""Camada de serializers do app Clientes."""
import html
import re

from rest_framework import serializers

from .models import Cliente, TipoPessoa
from .validators import validar_cnpj, validar_cpf


def _strip_tags(valor):
    """Remove tags HTML de uma string (mitigação de XSS).

    Usa apenas a stdlib: html.unescape decodifica entidades (&lt;b&gt; -> <b>)
    e o regex remove qualquer marcação <...>, repetindo até não restarem
    tags (ex.: "&lt;scri<b>pt&gt;" viraria "<script>" após uma passada única).
    No fim, normaliza espaços e colapsa whitespace.
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
    return re.sub(r"\s+", " ", texto).strip()


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
            "notificacoes_ativas",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            # Regra de negócio: documento e e-mail são OBRIGATÓRIOS;
            # telefone permanece opcional.
            "documento": {"required": True, "allow_null": False},
            "email": {"required": True, "allow_blank": False},
        }

    # Campos de texto livres que recebem strip de tags HTML na entrada.
    CAMPOS_TEXTO_SANITIZADOS = ("nome", "documento", "email", "telefone", "endereco")

    def to_internal_value(self, data):
        """Sanitiza a ENTRADA antes da validação por campo.

        Assim o e-mail, por exemplo, já chega limpo de tags ao EmailField —
        "<b>maria</b>@ex.com" é validado como "maria@ex.com", e não rejeitado
        por conter marcação.
        """
        if hasattr(data, "items"):
            dados = dict(data)
            for campo in self.CAMPOS_TEXTO_SANITIZADOS:
                valor = dados.get(campo)
                if isinstance(valor, str):
                    dados[campo] = _strip_tags(valor)
            data = dados
        return super().to_internal_value(data)

    def validate_documento(self, value):
        value = (value or "").strip() or None
        if value is None:
            raise serializers.ValidationError("O documento (CPF/CNPJ) é obrigatório.")
        # Multi-tenancy: a duplicidade de documento vale apenas dentro do
        # cadastro do próprio gestor (owner). A mesma pessoa/empresa pode ser
        # cliente de vários gestores ao mesmo tempo.
        queryset = Cliente.objects.filter(
            owner=self.context["request"].user
        )
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.filter(documento=value).exists():
            raise serializers.ValidationError(
                "Já existe um cliente com este documento no seu cadastro."
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

        # Sanitização já feita em to_internal_value (antes da validação);
        # aqui apenas a regra de negócio do nome vazio.
        nome = attrs.get("nome")
        if nome is not None and not nome.strip():
            raise serializers.ValidationError(
                {"nome": "O nome não pode ser vazio ou conter apenas espaços."}
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
