"""
Validação de documentos brasileiros (CPF e CNPJ).

Validação estrutural (quantidade de dígitos + dígitos verificadores) sem
dependências externas — suficiente para o formato básico exigido pelo app
Clientes. Se no futuro for necessário validar contra a Receita Federal,
troque por validate-docbr em services.py.
"""
import re


def _apenas_digitos(valor: str) -> str:
    return re.sub(r"\D", "", valor or "")


def _digito_verificador_cpf(digitos: str) -> int:
    soma = sum(
        int(d) * peso for d, peso in zip(digitos, range(len(digitos) + 1, 1, -1))
    )
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cpf(cpf: str) -> bool:
    """Valida a estrutura de um CPF (11 dígitos + dígitos verificadores)."""
    cpf = _apenas_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    return all(
        int(cpf[pos]) == _digito_verificador_cpf(cpf[:pos]) for pos in (9, 10)
    )


_PESOS_CNPJ = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _digito_verificador_cnpj(digitos: str) -> int:
    pesos = (6,) + _PESOS_CNPJ if len(digitos) == 13 else _PESOS_CNPJ
    soma = sum(int(d) * peso for d, peso in zip(digitos, pesos))
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def validar_cnpj(cnpj: str) -> bool:
    """Valida a estrutura de um CNPJ (14 dígitos + dígitos verificadores)."""
    cnpj = _apenas_digitos(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    return all(
        int(cnpj[pos]) == _digito_verificador_cnpj(cnpj[:pos]) for pos in (12, 13)
    )