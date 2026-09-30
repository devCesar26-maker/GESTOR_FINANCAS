"""Adapters do django-allauth para o FinFlow.

O FinFlow NÃO usa os fluxos de sessão/forms do allauth: ele entra como
camada de validação do id_token do Google (Google Identity Services já
verifica a posse do e-mail). Este adapter customiza os dois pontos onde o
comportamento padrão não serve ao FinFlow:

1) Associação determinística de contas: um e-mail Google que já existe
   como usuário LOCAL (registrado por senha) é VINCULADO à conta existente
   — nunca cria duplicata. O mecanismo nativo
   (SOCIALACCOUNT_EMAIL_AUTHENTICATION) seria perigoso aqui: para e-mails
   sem registro de verificação (EmailAddress), o allauth APAGA a senha do
   usuário ao logar (wipe_password) — quebraria o login por senha de todos
   os usuários antigos. Aqui a associação é feita manualmente por e-mail
   (case-insensitive), sem tocar na senha.

2) Criação de usuário: o username local segue o padrão do FinFlow
   (o próprio e-mail, como em RegistroSerializer) e a conta nasce SEM
   senha (unusable) — quem logou pelo Google pode definir uma senha depois
   pelo fluxo de "reset de senha".
"""

from allauth.account.utils import user_email
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from rest_framework.exceptions import ValidationError as DRFValidationError


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Adapter social com associação manual por e-mail (sem wipe de senha)."""

    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)
        if sociallogin.is_existing:
            # Já é uma conta social conhecida (SocialAccount no banco).
            return

        email = (user_email(sociallogin.user) or "").strip().lower()
        if not email:
            return

        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Conta local existente (criada por senha ou Google anterior):
        # vincula o SocialAccount ao usuário — sem duplicar conta e SEM
        # alterar a senha (o Google já provou a posse do e-mail).
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            sociallogin.user = user
            sociallogin.save(request, connect=True)
            return

        # E-mail existe mas a conta está desativada: NÃO criar nova conta
        # (daria IntegrityError de e-mail único) — rejeita com 400.
        if User.objects.filter(email__iexact=email).exists():
            raise DRFValidationError("Esta conta está desativada.")

    def save_user(self, request, sociallogin, form=None):
        """Criação de conta nova via Google.

        - username = e-mail (padrão FinFlow; e-mails são únicos).
        - SEM senha: unusable password (login exclusivamente via Google até
          que o usuário defina uma senha pelo reset).
        """
        u = sociallogin.user
        u.set_unusable_password()
        u.username = (u.email or "").strip().lower()
        sociallogin.save(request)
        return u
