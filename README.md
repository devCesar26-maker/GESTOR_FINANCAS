# FinFlow

**FinFlow** é uma plataforma web de **gestão financeira para pequenos negócios**, que cobre o ciclo completo do dia a dia financeiro:

- **Clientes e fornecedores** — cadastro PF/PJ, busca textual, papel (cliente, fornecedor ou ambos), lembretes por cliente e atalho direto para conversa no WhatsApp.
- **Contas a pagar e a receber** — faturas com status (pendente, paga, vencida, cancelada), vencimento, categoria e comprovante obrigatório no pagamento.
- **Cobranças recorrentes** — geração automática de faturas por periodicidade (mensal, trimestral...).
- **Lembretes de cobrança por e-mail** — régua automática de vencimento (10, 5, 1 dia(s) antes e no dia) em tom corporativo, com dados de pagamento/PIX.
- **Relatórios e DRE** — fluxo de caixa por período, DRE por categoria e exportação em CSV e PDF.
- **Multi-tenancy** — cada gestor vê apenas seus próprios clientes, faturas e relatórios, com isolamento garantido em testes automatizados.
- **Segurança** — JWT com refresh em cookie httpOnly, comprovantes protegidos por autenticação, sanitização anti-XSS, rate limiting e headers de segurança.

| Camada   | Tecnologia                                                         |
| -------- | ------------------------------------------------------------------ |
| Backend  | Django 5 + Django REST Framework + SimpleJWT                       |
| Banco    | PostgreSQL 16                                                      |
| Jobs     | Celery + Redis (faturas recorrentes, vencidos, lembretes, e-mails) |
| API Docs | drf-spectacular (OpenAPI 3 / Swagger / ReDoc)                      |
| Frontend | React 19 + Vite + React Router + Axios + Recharts                  |
| Testes   | pytest + pytest-django (backend) · Vitest (frontend)              |
| Infra    | Docker Compose — dev e produção (nginx + gunicorn)              |

---

## Aplicação ao vivo

> 🔗 _(link será adicionado após o deploy em produção)_

---

## Arquitetura

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  frontend   │ ──► │  backend     │ ──► │  postgres   │
│  (React)    │     │  (Django)    │     └─────────────┘
└─────────────┘     └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌─────────────┐
                    │  celery      │ ──► │  redis      │
                    │  worker+beat │     └─────────────┘
                    └──────────────┘
```

Em produção, o nginx na frente do stack responde por estáticos do frontend,
faz proxy de `/api/`, `/admin/` e `/static/` para o backend (gunicorn) e
protege `/media/` com o endpoint interno de autenticação (`/media-auth/`),
de forma que **comprovantes nunca são servidos sem sessão válida**.

### Arquitetura em camadas (backend)

Cada app Django segue a mesma separação de responsabilidades:

```
HTTP → urls → views (orquestração) → serializers (validação/representação)
                                        ↓
                                 services (regras de negócio)
                                        ↓
                                   models (dados) → PostgreSQL
```

- **models** — representação dos dados e constraints de integridade (unicidade de documento por gestor, unicidade de número de fatura por gestor). Sem regras de negócio.
- **serializers** — validação de entrada e representação de saída da API, incluindo sanitização anti-XSS e regras de mascaramento LGPD.
- **services** — regras de negócio puras e testáveis (`pagar_fatura`, `processar_cobrancas_recorrentes`, `enviar_lembretes_vencimento`...). São chamadas por views, tasks do Celery e testes.
- **views/viewsets** — apenas orquestração HTTP; nunca contêm lógica de negócio.

### Apps Django

| App             | Responsabilidade                                                                                                              |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `clientes`    | CRUD de clientes/fornecedores, busca textual, mascaramento LGPD do documento na listagem, e-mail de boas-vindas ao cadastro   |
| `usuarios`    | Registro de gestores, e-mail de boas-vindas                                                                                   |
| `faturamento` | `Fatura` (pagar com comprovante, cancelar, categorias), `CobrancaRecorrente`, DRE, exportações, lembretes de vencimento |
| `relatorios`  | Agregações de leitura — fluxo de caixa por período (sem models próprios)                                                 |

### Regras de negócio principais

- **Multi-tenancy por `owner`** — todo dado pertence a um gestor; unicidade de documento e de número de fatura vale **dentro de cada gestor** (constraints no banco).
- **Pagamento de fatura** — exige **comprovante obrigatório** (PDF/JPEG/PNG/WEBP, máx. 5 MB, com validação de magic bytes); a URL do comprovante é relativa e só abre com token válido (`/api/media/...`).
- **Mascaramento LGPD** — a listagem de clientes devolve o documento mascarado (`529.***.***-25`); a edição com o valor mascarado **preserva o original** da base.
- **Lembretes idempotentes** — cada janela da régua (10/5/1/0 dias) envia uma única vez por fatura; a data de envio só é gravada após o sucesso do `send`.
- **Fluxo de caixa** — "A receber"/"A pagar" somam pendentes + vencidas (em aberto); canceladas ficam de fora.

### Jobs assíncronos (Celery Beat)

| Task                                     | Agendamento   | O que faz                                                             |
| ---------------------------------------- | ------------- | --------------------------------------------------------------------- |
| `task_processar_cobrancas_recorrentes` | diário 00:00 | Gera faturas das cobranças recorrentes devidas                       |
| `task_marcar_faturas_vencidas`         | diário 00:00 | Marca pendentes com vencimento ultrapassado como vencidas             |
| `task_enviar_lembretes_vencimento`     | diário 08:00 | Régua de e-mails: preventivo (10d), formal (5d/1d) e vencimento (0d) |
| `task_enviar_email_cadastro_cliente`   | on-demand     | E-mail de boas-vindas ao cadastrar cliente                            |
| `task_enviar_email_boas_vindas`        | on-demand     | E-mail de boas-vindas ao registrar gestor                             |

Timezone dos agendamentos: `America/Sao_Paulo`. O envio de e-mails usa a Brevo
(django-anymail) quando `BREVO_API_KEY` está definida; sem chave, cai no backend
de console (nada parte de verdade em dev).

### Régua de lembretes de vencimento

| Janela               | Template                | Tom                                                         |
| -------------------- | ----------------------- | ----------------------------------------------------------- |
| 10 dias antes        | `lembrete_previo`     | Preventivo amigável — "ainda há tempo hábil"            |
| 5 dias e 1 dia antes | `lembrete_proximo`    | Notificação formal de vencimento próximo                 |
| No dia (0 dias)      | `lembrete_vencimento` | Aviso de vencimento com instrução de envio do comprovante |

Todos os e-mails incluem: nome do cliente, número da fatura, valor (R$),
vencimento, descrição e **dados para pagamento** (chave PIX quando configurada —
ver [Variáveis de ambiente](#variáveis-de-ambiente)).

### Estrutura de pastas

```
.
├── backend/
│   ├── finflow/            # projeto Django (settings, urls, celery)
│   ├── apps/
│   │   ├── clientes/       # models, serializers, services, views, tasks
│   │   ├── faturamento/
│   │   ├── relatorios/
│   │   └── usuarios/
│   ├── templates/          # templates de e-mail por app (faturamento/emails/)
│   ├── tests/              # testes pytest-django (16 módulos)
│   ├── scripts/            # ensure_dev_superuser.py
│   ├── manage.py
│   ├── requirements.txt
│   ├── pytest.ini          # settings_test (SQLite em memória)
│   ├── Dockerfile / Dockerfile.prod
│   └── entrypoint.sh       # aplica migrações antes de subir
├── frontend/
│   ├── src/
│   │   ├── api/client.js   # axios: access token em memória + silent refresh
│   │   ├── components/     # Layout (navbar/rotas), ConfirmDialog
│   │   ├── pages/          # Login, Registro, Dashboard, Clientes, Faturas
│   │   ├── utils/          # telefone (máscara), whatsapp (link wa.me)
│   │   └── App.jsx         # rotas protegidas
│   ├── package.json
│   ├── vite.config.js      # proxy /api → backend
│   ├── Dockerfile / Dockerfile.prod
│   └── styles.css          # tema próprio (sem Tailwind)
├── deploy/nginx.conf       # proxy reverso de produção
├── docker-compose.yml      # dev: backend, frontend, db, redis, worker, beat
├── docker-compose.prod.yml # produção: gunicorn + nginx + worker + beat
└── README.md
```

### Frontend (visão geral)

- **Autenticação** — o access token JWT vive **apenas em memória** (nunca em `localStorage`); o refresh token viaja em cookie `httpOnly` restrito a `/api/token/refresh/`. Ao recarregar a página, a sessão é reidratada por *silent refresh*; ao sair, há modal de confirmação antes de invalidar a sessão no backend.
- **Dashboard** — fluxo de caixa (a receber/a pagar em aberto), gráfico de entradas/saídas e DRE visual por categoria (receitas × despesas) com legendas detalhadas.
- **Faturas** — tabela com filtros (status, tipo, categoria), busca, ações em linha (WhatsApp, Receber/Pagar com upload de comprovante, Editar, Cancelar, Comprovante), exportações e link do WhatsApp por fatura.
- **Clientes** — CRUD com busca textual server-side, máscara de telefone, WhatsApp em um clique e exclusão com confirmação.

---

## Como rodar localmente

### Pré-requisitos

- Python 3.11+
- Node.js 20+
- PostgreSQL e Redis rodando (ou use o docker-compose apenas para eles)

### Backend

```bash
cd backend

# 1. Ambiente virtual (ou reutilize a venv FINANCAS/ existente)
python -m venv .venv
source .venv/bin/activate

# 2. Dependências
pip install -r requirements.txt

# 3. Variáveis de ambiente
cp .env.example .env   # ajuste DB_* se necessário

# 4. Migrações e servidor
python manage.py migrate
python manage.py runserver
```

Servidor em http://localhost:8000 — documentação em
http://localhost:8000/api/schema/swagger-ui/.

### Credenciais de desenvolvimento

O login em `/api/token/` usa um superusuário criado automaticamente a partir
das variáveis `DJANGO_SUPERUSER_USERNAME`, `DJANGO_SUPERUSER_EMAIL` e
`DJANGO_SUPERUSER_PASSWORD`, definidas no seu `.env` local (veja
`.env.example` para os valores padrão de desenvolvimento).

Ele é criado/restaurado automaticamente pelo `backend/scripts/ensure_dev_superuser.py`
(ao subir via Docker) ou manualmente com:

```bash
cd backend
python manage.py shell < scripts/ensure_dev_superuser.py
```

> ⚠️ **Em produção**, defina credenciais fortes e únicas via variável de
> ambiente no painel do provedor de hospedagem — nunca reutilize as do
> `.env.example` — ou remova esse passo do `entrypoint.sh` e crie o
> superusuário manualmente uma única vez.

### Celery (jobs assíncronos)

Em outro terminal (o *beat* é o agendador que dispara as tasks da tabela acima):

```bash
cd backend
source .venv/bin/activate
celery -A finflow worker -l info
celery -A finflow beat -l info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend em http://localhost:5173. O Vite faz proxy de `/api/*` para o
backend (em http://localhost:8000 por padrão, configurável via
`VITE_PROXY_TARGET`).

---

## Variáveis de ambiente

Configuração 100% por ambiente — nada sensível no código. Principais variáveis
(backend):

| Variável                                                                               | Padrão                            | Descrição                                                        |
| --------------------------------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------------------ |
| `SECRET_KEY`                                                                          | `dev-only-change-me-em-producao` | Chave do Django (**troque em produção**)                   |
| `DEBUG`                                                                               | `false`                          | Em produção deixe`false`                                       |
| `ALLOWED_HOSTS`                                                                       | `localhost,127.0.0.1`            | Hosts separados por vírgula                                       |
| `DB_ENGINE` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL local                   | Conexão com o banco                                               |
| `BREVO_API_KEY`                                                                       | *(vazio)*                        | Com a chave, e-mails partem via Brevo; sem ela, backend de console |
| `DEFAULT_FROM_EMAIL`                                                                  | `FinFlow <...>`                  | Remetente dos e-mails transacionais                                |
| `FINFLOW_CHAVE_PIX`                                                                   | *(vazio)*                        | Chave PIX exibida nos lembretes de cobrança                       |
| `FINFLOW_FAVORECIDO_PIX`                                                              | *(vazio)*                        | Nome do favorecido PIX nos lembretes                               |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`                                       | `redis://localhost:6379/0`       | Broker/resultados do Celery                                        |
| `REDIS_URL`                                                                           | `redis://localhost:6379/1`       | Cache/throttling                                                   |
| `CORS_ALLOWED_ORIGINS`                                                                | `http://localhost:5173`          | Origens autorizadas (vírgula)                                     |
| `SECURE_SSL_REDIRECT` etc.                                                            | `not DEBUG`                      | Headers de segurança (HSTS, cookies secure)                       |

Frontend:

| Variável             | Padrão                   | Descrição                             |
| --------------------- | ------------------------- | --------------------------------------- |
| `VITE_PROXY_TARGET` | `http://localhost:8000` | Destino do proxy`/api` do Vite em dev |

---

## Como rodar com Docker Compose

### Desenvolvimento

Com apenas um comando sobe **db, redis, backend, worker, beat e frontend**
(com código montado como volume — alterações refletem em tempo real):

```bash
docker compose up --build
```

| Serviço   | URL                                          |
| ---------- | -------------------------------------------- |
| Frontend   | http://localhost:5173                        |
| Backend    | http://localhost:8000                        |
| Swagger UI | http://localhost:8000/api/schema/swagger-ui/ |
| Admin      | http://localhost:8000/admin                  |

### Produção

O `docker-compose.prod.yml` usa as imagens `Dockerfile.prod` (sem volume de
código) com **gunicorn**, **worker + beat dedicados** e o **nginx** na frente
fazendo proxy reverso, servindo estáticos e protegendo `/media/`:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Para parar:

```bash
docker compose down
# para apagar também o volume do banco:
docker compose down -v
```

---

## Testes

### Backend (pytest, 204 testes)

Os testes usam **SQLite em memória** por padrão (rápido, sem precisar de
PostgreSQL) — o `pytest.ini` aponta para `finflow.settings_test`. E-mails são
capturados por backend de teste (nada sai de verdade).

```bash
cd backend
source .venv/bin/activate
pytest
```

Para rodar contra o PostgreSQL do docker-compose:

```bash
cd backend
DJANGO_SETTINGS_MODULE=finflow.settings \
DB_ENGINE=django.db.backends.postgresql \
DB_NAME=finflow DB_USER=finflow DB_PASSWORD=finflow DB_HOST=localhost \
pytest
```

Cobertura destacável (módulos em `backend/tests/`):

| Módulo                                                                       | Cobre                                                             |
| ----------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `test_faturamento.py`                                                       | CRUD de faturas, pagar/cancelar, cobranças recorrentes           |
| `test_multitenancy.py`                                                      | Isolamento entre gestores em todos os endpoints                   |
| `test_lembretes.py`                                                         | Régua de e-mails (janelas, idempotência, PIX, tom por régua)   |
| `test_comprovante_pagamento.py` / `test_media_protegida.py`               | Upload válido, magic bytes, acesso com/sem token, path traversal |
| `test_clientes.py` / `test_telefone_cliente.py` / `test_sanitizacao.py` | CRUD, mascaramento LGPD, telefone BR, sanitização XSS           |
| `test_fluxo_caixa.py` / `test_categorias_dre_export.py`                   | Semântica do fluxo de caixa e DRE + exportações                |
| `test_auth_cookies.py` / `test_senha_forte.py`                            | Login/refresh/logout com cookie httpOnly + CSRF                   |
| `test_seguridad.py`                                                         | SQL injection, XSS, clickjacking, throttling (429), payload (413) |

### Frontend (Vitest)

```bash
cd frontend
npm test        # vitest run
npm run build   # build de produção
```

29 testes cobrem utilitários (máscara de telefone, link WhatsApp), escape XSS
e a geometria dos gráficos do Dashboard.

---

## Segurança (hardening)

Auditoria por categoria de ataque + correções + testes automatizados:

- `backend/tests/test_seguridad.py` — um teste por categoria (backend)
- `frontend/src/xss_escape.test.jsx` — escape XSS do React (frontend)

| Categoria         | Estado                                                                                                                                        |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| SQL Injection     | ORM parametrizado (sem`.raw()`/`.extra()`/cursor manual) — testes com payloads clássicos                                                |
| XSS               | React escapa por padrão; sem`dangerouslySetInnerHTML`; sanitização de entrada nos serializers — testes de armazenamento literal         |
| Autenticação    | JWT com access token em memória no frontend e**refresh em cookie httpOnly** restrito a `/api/token/refresh/`, com CSRF (duplo envio) |
| CSRF              | Login/refresh exigem cookie`csrftoken` (duplo envio); API lê apenas `Authorization`                                                      |
| Command Injection | Sem`os.system`/`subprocess`/`shell=True` — sem superfície de ataque                                                                   |
| Clickjacking      | `X-Frame-Options: DENY` + CSP `frame-ancestors 'none'` — testes de headers                                                               |
| Token Hijacking   | Access token não persistido; refresh httpOnly; HTTPS obrigatório em produção                                                              |
| Rate Limiting     | Throttling DRF: anon 20/min, user 100/min; login/registro 5/min por IP — teste 429                                                           |
| Payload / DDoS    | Limite de payload 1 MB (413) +`DATA_UPLOAD_MAX_MEMORY_SIZE`; DDoS real exige infraestrutura                                                 |
| Comprovantes      | `/media/` exige autenticação; nginx valida sessão via `/media-auth/` antes de servir                                                   |

### HTTPS obrigatório em produção

Com `DEBUG=False` (produção), `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`
e `CSRF_COOKIE_SECURE` são `True` por padrão (override explícito via
variáveis de ambiente). O docker-compose de desenvolvimento define
`DEBUG=true` explicitamente, mantendo HTTP local.

### Rate limiting

- Global: `anon` 20 req/min, `user` 100 req/min (`AnonRateThrottle`/`UserRateThrottle`).
- Login (`/api/token/`) e registro (`/api/auth/registro/`): **5 tentativas por
  minuto por IP** (`ScopedRateThrottle`) — mitiga força bruta de senha e
  criação de contas em massa.

### Limites de payload e DDoS

- `MAX_BODY_SIZE_BYTES` (padrão 1 MB) → 413 para payloads maiores
  (middleware `MaxBodySizeMiddleware`).
- **Proteção completa contra DDoS não é responsabilidade do código Django**:
  exige camada de infraestrutura (ex.: Cloudflare/WAF + CDN) na frente do
  domínio em produção. Este projeto mitiga a nível de aplicação (throttling
  + payload); não afirma estar "protegido contra DDoS" sem essa camada.

### Limitações conhecidas

- CSP mínima (só `frame-ancestors`): uma CSP completa (`style-src`/`script-src`)
  rompe o frontend, que usa estilos inline.
- Limite de payload depende do header `Content-Length`;
  `transfer-encoding: chunked` exige limite no proxy (nginx).
- MITM e DDoS não são testáveis via pytest — mitigam-se com infraestrutura
  (HTTPS/HSTS, WAF/CDN), não com lógica de aplicação.

---

## Documentação da API

- **Swagger UI:** http://localhost:8000/api/schema/swagger-ui/
- **ReDoc:** http://localhost:8000/api/schema/redoc/
- **Schema OpenAPI (JSON):** http://localhost:8000/api/schema/

### Endpoints principais

| Método              | Endpoint                                         | Descrição                                                             |
| -------------------- | ------------------------------------------------ | ----------------------------------------------------------------------- |
| POST                 | `/api/token/`                                  | Login (access no body, refresh em cookie httpOnly)                      |
| POST                 | `/api/token/refresh/`                          | Renova o access token (lê o cookie)                                    |
| POST                 | `/api/token/logout/`                           | Invalida o refresh e limpa o cookie                                     |
| GET                  | `/api/csrf/`                                   | Define o cookie`csrftoken` (duplo envio)                              |
| POST                 | `/api/auth/registro/`                          | Registro de gestor (com e-mail de boas-vindas)                          |
| GET/POST             | `/api/clientes/`                               | Lista (busca`?search=`) e cria clientes/fornecedores                  |
| GET/PUT/PATCH/DELETE | `/api/clientes/{id}/`                          | Detalhe/edição/exclusão (DELETE bloqueia com faturas: 409)           |
| GET/POST             | `/api/faturas/`                                | Lista (filtros`?status=`, `?tipo=`, `?categoria=`) e cria faturas |
| POST                 | `/api/faturas/{id}/pagar/`                     | Registra pagamento (**comprovante obrigatório**)                 |
| POST                 | `/api/faturas/{id}/cancelar/`                  | Cancela a fatura                                                        |
| GET                  | `/api/faturas/exportar/?formato=csv\|excel\|pdf` | Extrato de faturas                                                      |
| GET/POST             | `/api/categorias/`                             | Categorias financeiras (DRE)                                            |
| GET/POST             | `/api/cobrancas-recorrentes/`                  | Cobranças recorrentes por periodicidade                                |
| GET                  | `/api/relatorios/fluxo-caixa/?inicio=&fim=`    | Fluxo de caixa por período                                             |
| GET                  | `/api/relatorios/dre/?inicio=&fim=`            | DRE por categoria                                                       |
| GET                  | `/api/relatorios/dre/exportar/?formato=...`    | DRE em CSV/Excel/PDF                                                    |
| GET                  | `/api/media/{caminho}`                         | Comprovantes (exige token de acesso válido)                            |

---

## Licença

Consulte o arquivo [LICENSE](LICENSE).
