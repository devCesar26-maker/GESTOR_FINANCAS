"""Serializers do app Usuarios (registro, reset de senha, Google OAuth)."""

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


# ---------------------------------------------------------------------------
# Login JWT (SimpleJWT) com e-mail OU username
# ---------------------------------------------------------------------------

# Aproximação suficiente para decidir se o valor digitado parece um e-mail.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class TokenObtainPairEmailSerializer(TokenObtainPairSerializer):
    """TokenObtainPairSerializer que aceita e-mail no campo `username`.

    O ModelBackend do Django autentica APENAS pelo username — quando o
    frontend envia o e-mail no campo de login, o authenticate() falha e o
    endpoint /api/token/ responde 401. Aqui, ANTES de validar as
    credenciais, um valor que pareça e-mail é resolvido para o username da
    conta correspondente (match case-insensitive), e a validação padrão do
    SimpleJWT segue com as credenciais corretas. Se o valor não parece um
    e-mail (ou não existe conta com esse e-mail), segue como username —
    comportamento idêntico ao padrão do SimpleJWT.
    """

    def validate(self, attrs: dict) -> dict:
        username = attrs.get(self.username_field) or ""
        if _EMAIL_RE.match(username.strip()):
            candidato = (
                User.objects.filter(
                    email__iexact=username.strip(), is_active=True
                ).values_list("username", flat=True).first()
            )
            if candidato:
                attrs = dict(attrs)
                attrs[self.username_field] = candidato
        return super().validate(attrs)


class RegistroSerializer(serializers.ModelSerializer):
    """Cria uma conta a partir de nome, e-mail e senha.

    - A senha passa pelas validações do Django (validate_password).
    - O username é o próprio e-mail; e-mail é único (case-insensitive).
    """

    nome = serializers.CharField(write_only=True, max_length=150)

    class Meta:
        model = User
        fields = ["nome", "email", "password"]
        extra_kwargs = {
            "password": {"write_only": True, "style": {"input_type": "password"}},
            "email": {"required": True, "allow_blank": False},
        }

    def validate_email(self, value: str) -> str:
        if User.objects.filter(email__iexact=value.strip()).exists():
            raise serializers.ValidationError("Já existe uma conta com este e-mail.")
        return value.strip().lower()

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def create(self, validated_data: dict) -> User:
        nome = validated_data.pop("nome")
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            first_name=nome,
        )


class RegistroResponseSerializer(serializers.Serializer):
    """Resposta do registro (dados públicos da conta criada)."""

    id = serializers.IntegerField(read_only=True)
    nome = serializers.CharField(read_only=True, source="first_name")
    email = serializers.EmailField(read_only=True)
    detail = serializers.CharField(read_only=True)


# ---------------------------------------------------------------------------
# Reset de senha por e-mail
# ---------------------------------------------------------------------------


class PasswordResetRequestSerializer(serializers.Serializer):
    """Corpo do POST /api/auth/password/reset/: apenas o e-mail."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Corpo do POST /api/auth/password/reset/confirm/: uid, token e senha.

    O par (uid, token) é gerado pelo PasswordResetTokenGenerator do Django
    (token único de 1 hora, invalidado se a senha mudar ou ao logar). A
    nova senha (new_password) passa pela política SenhaForteValidator
    (settings).
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_new_password(self, value: str) -> str:
        validate_password(value)
        return value
