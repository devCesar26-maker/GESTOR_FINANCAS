"""Validadores do app Usuarios."""

import re

from django.core.exceptions import ValidationError


class SenhaForteValidator:
    """Exige senha forte: 8+ caracteres, maiúscula, minúscula, número e especial.

    Exclusivo para CRIAÇÃO de contas (registro e criação de superusuário via
    CLI). O login não revalida força de senha — a senha já foi criada antes
    sob esta política.
    """

    def validate(self, password: str, user=None) -> None:
        erros = []
        if len(password) < 8:
            erros.append("A senha deve ter pelo menos 8 caracteres.")
        if not re.search(r"[A-Z]", password):
            erros.append("A senha deve conter ao menos uma letra maiúscula.")
        if not re.search(r"[a-z]", password):
            erros.append("A senha deve conter ao menos uma letra minúscula.")
        if not re.search(r"\d", password):
            erros.append("A senha deve conter ao menos um número.")
        if not re.search(r"[^A-Za-z0-9]", password):
            erros.append("A senha deve conter ao menos um caractere especial.")
        if erros:
            raise ValidationError(erros)

    def get_help_text(self) -> str:
        return (
            "Sua senha deve ter ao menos 8 caracteres, incluindo letra "
            "maiúscula, minúscula, número e caractere especial."
        )
