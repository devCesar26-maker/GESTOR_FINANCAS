# FinFlow 💸

API e interface de **gestão financeira para pequenos negócios**: contas a
pagar/receber, faturamento e cobranças recorrentes.

| Camada         | Tecnologia                                            |
| -------------- | ----------------------------------------------------- |
| Backend        | Django 5 + Django REST Framework + SimpleJWT          |
| Banco          | PostgreSQL                                            |
| Jobs           | Celery + Redis (faturas recorrentes, lembretes)       |
| Documentação | drf-spectacular (OpenAPI / Swagger)                   |
| Frontend       | React 19 + Vite + React Router + Axios + Recharts     |
| Testes         | pytest + pytest-django                                |
| Infra          | Docker Compose (backend, frontend, db, redis, worker) |

---

## Arquitetura

O backend segue **arquitetura em camadas** dentro de cada app:

```
HTTP → urls → views (orquestração) → serializers (validação/representação)
                                        ↓
                                 services (regras de negócio)
                                        ↓
                                   models (dados) → PostgreSQL
```

- **models** — representação dos dados e constraints de integridade. Sem regras de negócio.
- **serializers** — validação de entrada e representação de saída da API.
- **services** — regras de negócio puras e testáveis (ex.: `pagar_fatura`, `gerar_cobranca_recorrente`). Chamadas de service são reutilizáveis por views, tasks do Celery e testes.
- **views/viewsets** — apenas orquestração HTTP; nunca contêm lógica de negócio.

### Apps Django

| App             | Responsabilidade                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------ |
| `clientes`    | CRUD de clientes e fornecedores                                                                  |
| `faturamento` | `Fatura` (status: pendente, paga, vencida, cancelada) e `CobrancaRecorrente` (periodicidade) |
| `relatorios`  | Agregações de leitura, ex.: fluxo de caixa por período (sem models próprios)                 |

### Jobs assíncronos (Celery)

A geração automática de faturas de cobranças recorrentes, a marcação de
faturas vencidas e os lembretes de vencimento serão implementados como
*tasks* em `apps/<app>/tasks.py`, agendadas com Celery Beat.

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  frontend   │ ──► │  backend     │ ──► │  postgres   │
│  (React)    │     │  (Django)    │     └─────────────┘
└─────────────┘     └──────┬───────┘
                           │
                    ┌──────▼───────┐     ┌─────────────┐
                    │  celery      │ ──► │  redis      │
                    │  worker      │     └─────────────┘
                    └──────────────┘
```

### Estrutura de pastas

```
.
├── backend/
│   ├── finflow/            # projeto Django (settings, urls, celery)
│   ├── apps/
│   │   ├── clientes/       # models, serializers, services, views
│   │   ├── faturamento/
│   │   └── relatorios/
│   ├── tests/              # testes pytest-django
│   ├── manage.py
│   ├── requirements.txt
│   ├── .env.example
│   ├── Dockerfile
│   └── entrypoint.sh       # aplica migrações antes de subir
├── frontend/
│   ├── src/
│   │   ├── api/client.js   # axios com interceptor de JWT
│   │   ├── pages/          # Login, Dashboard, Clientes, Faturas
│   │   └── App.jsx         # rotas protegidas
│   ├── package.json
│   ├── vite.config.js      # proxy /api → backend
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

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

### Celery (jobs assíncronos)

Em outro terminal:

```bash
cd backend
source .venv/bin/activate
celery -A finflow worker -l info
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

## Como rodar com Docker Compose

Com apenas um comando sobe **db, redis, backend, worker e frontend**:

```bash
docker compose up --build
```

| Serviço   | URL                                          |
| ---------- | -------------------------------------------- |
| Frontend   | http://localhost:5173                        |
| Backend    | http://localhost:8000                        |
| Swagger UI | http://localhost:8000/api/schema/swagger-ui/ |
| Admin      | http://localhost:8000/admin                  |

Para parar:

```bash
docker compose down
# para apagar também o volume do banco:
docker compose down -v
```

> O código é montado como volume nos containers, então alterações em
> `backend/` e `frontend/` são refletidas em tempo real.

---

## Como rodar os testes

Os testes usam **SQLite em memória** por padrão (rápido, sem precisar de
PostgreSQL) — o `pytest.ini` aponta para `finflow.settings_test`.

```bash
cd backend
source .venv/bin/activate   # ou use a venv FINANCAS/
pytest
```

Para rodar os testes contra o PostgreSQL do docker-compose (substituindo o
settings de teste):

```bash
cd backend
DJANGO_SETTINGS_MODULE=finflow.settings \
DB_ENGINE=django.db.backends.postgresql \
DB_NAME=finflow DB_USER=finflow DB_PASSWORD=finflow DB_HOST=localhost \
pytest
```

---

## Documentação da API

- **Swagger UI:** http://localhost:8000/api/schema/swagger-ui/
- **ReDoc:** http://localhost:8000/api/schema/redoc/
- **Schema OpenAPI (JSON):** http://localhost:8000/api/schema/

### Endpoints

| Método | Endpoint                                      | Descrição                         |
| ------- | --------------------------------------------- | ----------------------------------- |
| POST    | `/api/token/`                               | Login (obtém access/refresh JWT)   |
| POST    | `/api/token/refresh/`                       | Renova o access token               |
| ...     | `/api/clientes/`                            | CRUD de clientes/fornecedores       |
| ...     | `/api/faturas/`                             | CRUD de faturas (filtro por status) |
| POST    | `/api/faturas/{id}/pagar/`                  | Marca fatura como paga              |
| GET     | `/api/relatorios/fluxo-caixa/?inicio=&fim=` | Fluxo de caixa por período         |

Os CRUDs, endpoints e telas do frontend são construídos **app por app** —
veja o roadmap abaixo.

---

## Roadmap (construção por app)

1. ✅ Scaffold: estrutura, models, docker-compose, README
2. ⏳ App `clientes`: serializers, services, viewsets, rotas e testes
3. ⏳ App `faturamento`: `pagar_fatura`, `gerar_cobranca_recorrente`, viewsets e testes
4. ⏳ App `relatorios`: serviço de fluxo de caixa e endpoint
5. ⏳ Celery: tasks de cobranças recorrentes, vencimento e lembretes
6. ⏳ Frontend: login, dashboard com gráfico, clientes, faturas
