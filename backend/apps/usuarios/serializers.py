"""Serializer de registro de usuário."""

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

User = get_user_model()


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
