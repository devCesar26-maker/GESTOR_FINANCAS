"""
Rotas raiz do projeto FinFlow.

Rotas de API por app são incluídas via apps.<app>.urls — cada app declara
apenas suas próprias rotas, mantendo o roteamento descentralizado.
"""
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from apps.usuarios.views import (
    LogoutView,
    TokenObtainPairCookieView,
    TokenRefreshCookieView,
    csrf_token_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    # Autenticação JWT (login com rate limit: 5/min por IP). O refresh
    # token viaja num cookie httpOnly — nunca no body da resposta.
    path("api/token/", TokenObtainPairCookieView.as_view(), name="token_obtain_pair"),
    path(
        "api/token/refresh/",
        TokenRefreshCookieView.as_view(),
        name="token_refresh",
    ),
    path("api/token/logout/", LogoutView.as_view(), name="token_logout"),
    # Define o cookie csrftoken para o duplo envio CSRF (login/refresh).
    path("api/csrf/", csrf_token_view, name="csrf_token"),
    # Documentação OpenAPI/Swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/schema/swagger-ui/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/schema/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # Apps
    path("api/", include("apps.usuarios.urls")),
    path("api/", include("apps.clientes.urls")),
    path("api/", include("apps.faturamento.urls")),
    path("api/relatorios/", include("apps.relatorios.urls")),
]