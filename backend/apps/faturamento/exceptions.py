from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


class FaturaEstadoInvalidoError(Exception):
    """Exceção de domínio lançada quando uma fatura está em estado incompatível com a operação."""
    def __init__(self, message: str = "Operação não permitida para o estado atual da fatura."):
        self.message = message
        super().__init__(message)


def custom_exception_handler(exc, context):
    if isinstance(exc, FaturaEstadoInvalidoError):
        return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
    return exception_handler(exc, context)
