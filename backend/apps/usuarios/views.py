"""Views do app Usuarios."""
import logging

from drf_spectacular.utils import extend_schema
from rest_framework import generics, permissions, status
from rest_framework.response import Response

from .serializers import RegistroResponseSerializer, RegistroSerializer

logger = logging.getLogger(__name__)


class RegistroAPIView(generics.CreateAPIView):
    """Cria uma nova conta de usuário (endpoint público).

    Diferente de todos os demais endpoints da API, não exige autenticação.
    """

    serializer_class = RegistroSerializer
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Autenticação"],
        summary="Registrar novo usuário",
        description=(
            "Cria uma conta com nome, e-mail e senha. A senha é validada pelas "
            "regras do Django (mínimo de 8 caracteres, não inteiramente numérica, etc.). "
            "E-mail deve ser único."
        ),
        request=RegistroSerializer,
        responses={201: RegistroResponseSerializer},
        auth=[],
    )
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # E-mail de boas-vindas: assíncrono (Celery) e isolado — uma falha
        # de broker/disparo NUNCA quebra a criação da conta.
        try:
            from .tasks import task_enviar_email_boas_vindas

            task_enviar_email_boas_vindas.delay(user.pk)
        except Exception:
            logger.exception(
                "Falha ao disparar e-mail de boas-vindas do usuário %s", user.pk
            )

        return Response(
            RegistroResponseSerializer(user).data
            | {"detail": "Conta criada com sucesso. Faça login para obter o token."},
            status=status.HTTP_201_CREATED,
        )
