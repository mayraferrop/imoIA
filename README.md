# ImoIA

A primeira plataforma end-to-end com IA que cobre todo o ciclo do
negócio imobiliário — da captação ao lucro. Para profissionais e
investidores imobiliários no Brasil e na Europa.

---

## Arquitectura

- **Backend:** FastAPI + Python 3.9+ sobre PostgreSQL (Supabase)
- **Frontend:** Next.js 15 + React 19 + TypeScript + Tailwind CSS 4
- **Auth:** Supabase Auth com Magic Link PKCE (JWKS no backend)
- **Database:** PostgreSQL com Row-Level Security multi-tenant
- **ORM:** SQLAlchemy 2.0 (backend) + PostgREST (frontend/REST)
- **Workers:** Celery + Redis (broker/backend)
- **LLM:** Anthropic Claude (classificação e geração de conteúdo)
- **SMTP:** Resend (`noreply@mail.ironcapitals.com`)
- **WhatsApp:** Whapi.cloud (REST) + bridge Baileys local opcional
- **Deploy:** Render (backend `imoia-api`) + Vercel (frontend `imoia.vercel.app`)

---

## Módulos

| Código | Nome | Descrição | Prefix API |
|---|---|---|---|
| **M1** | Ingestor | Classificação de oportunidades com Claude Haiku, captação via WhatsApp/portais | `/api/v1/ingest`, `/api/v1/properties` |
| **M2** | Pesquisa de Mercado | Comparáveis, avaliações e stats de zona (CASAFARI + INE) | `/api/v1/market` |
| **M3** | Motor Financeiro | Simulador fix & flip com TIR, cashflow e persistência | `/api/v1/financial` |
| **M4** | Deal Pipeline | Gestão do ciclo de vida de negócios (kanban por estratégia) | `/api/v1/deals` |
| **M5** | Due Diligence | Checklists automáticas de documentos e verificações | `/api/v1/due-diligence` |
| **M6** | Gestão de Obra | Orçamento, prazos e sync com Cash Flow Pro | `/api/v1/renovations` |
| **M7** | Marketing Engine | Conteúdo multicanal, creative studio e social media via IA | `/api/v1/marketing` |
| **M8** | CRM de Leads | Pipeline kanban, scoring, nurturing e sync habta.eu | `/api/v1/leads` |
| **M9** | Fecho + P&L | Closing workflow, P&L comparativo, portfolio e relatório fiscal | `/api/v1/closing`, `/api/v1/portfolio` |
| — | Documents | Router partilhado de gestão documental | `/api/v1/documents` |
| — | Strategies | Estratégias de investimento (buy & hold, fix & flip, etc.) | `/api/v1/strategies` |

---

## Setup Local

### Pré-requisitos
- Python 3.9+
- Node.js 20+ (gerido via NVM recomendado)
- Redis local (para Celery worker) — opcional em dev
- Conta Supabase + projecto PostgreSQL activo

### Backend

```bash
# Clonar e criar venv
git clone <repo-url> imoIA
cd imoIA
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -r requirements.txt

# Configurar variáveis de ambiente (ver secção abaixo)
cp .env.example .env
# Edita .env com os valores reais

# Correr FastAPI
uvicorn src.main:app --reload --port 8000

# (Opcional) Correr worker Celery
celery -A src.worker worker --loglevel=info
```

### Frontend

```bash
cd src/frontend
npm install

# Configurar variáveis de ambiente (ver secção abaixo)
cp .env.local.example .env.local
# Edita .env.local com os valores reais do teu projecto Supabase

# Correr em dev
npm run dev
# Acessar http://localhost:3000
```

---

## Variáveis de Ambiente

### Backend (`.env` na raiz)

**Base de dados e autenticação:**
- `DATABASE_URL` — String de conexão PostgreSQL (Supabase pooler, transaction mode, porta 6543)
- `SUPABASE_URL` — URL do projecto Supabase
- `SUPABASE_ANON_KEY` — Chave pública (para validação JWT)
- `SUPABASE_SERVICE_ROLE_KEY` — Chave de serviço (bypass RLS, uso restrito a scripts admin)

**LLM e IA:**
- `ANTHROPIC_API_KEY` — Claude API (classificação M1, marketing M7)

**WhatsApp e ingestão (M1):**
- `WHAPI_TOKEN` — Token Whapi.cloud

**Pesquisa de mercado (M2):**
- `CASAFARI_API_TOKEN` — Token API CASAFARI
- `CASAFARI_USERNAME`, `CASAFARI_PASSWORD` — Credenciais JWT CASAFARI
- `CASAFARI_BASE_URL` — Default: `https://api.casafari.com`
- `MARKET_CACHE_DAYS_COMPARABLES` — Default: `7`
- `MARKET_CACHE_DAYS_ZONE_STATS` — Default: `30`
- `MARKET_CACHE_DAYS_VALUATION` — Default: `14`
- `IDEALISTA_CLIENT_ID`, `IDEALISTA_CLIENT_SECRET` — OAuth Idealista (opcional)
- `SIR_USERNAME`, `SIR_PASSWORD` — Sistema Informação Registos (opcional)
- `INFOCASA_USERNAME`, `INFOCASA_PASSWORD` — Infocasa (opcional)

**Integrações externas:**
- `CASHFLOW_SUPABASE_URL`, `CASHFLOW_SUPABASE_KEY` — Cash Flow Pro (M6)
- `CASHFLOW_COMPANY_ID`, `CASHFLOW_USER_EMAIL`, `CASHFLOW_USER_PASSWORD`
- `HABTA_BASE_URL`, `HABTA_API_KEY` — Sync habta.eu (M8)
- `TROLTO_BASE_URL`, `TROLTO_API_KEY` — Integração Trolto

**Worker Celery:**
- `REDIS_URL` — Broker e result backend (default: `filesystem://`)

**Operacionais:**
- `MIN_CONFIDENCE` — Threshold M1 (default: `0.6`)
- `BATCH_SIZE` — Tamanho batch do pipeline (default: `20`)
- `TIMEZONE` — Default: `Europe/Lisbon`

### Frontend (`src/frontend/.env.local`)

- `NEXT_PUBLIC_SUPABASE_URL` — Mesmo projecto Supabase do backend
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — Anon key Supabase
- `NEXT_PUBLIC_API_URL` — URL do backend FastAPI (default: `https://imoia.onrender.com`)

> ⚠️ O `.env.example` actual na raiz está desactualizado (template genérico legacy). Usa a lista acima como referência até ser corrigido. Ver `docs/FASE_2A_POS_CLEANUP_MANUAL.md`.

---

## Estrutura de Pastas

```
imoIA/
├── CLAUDE.md                      # Instruções do projecto para Claude Code
├── Dockerfile                     # Container backend FastAPI (Render)
├── render.yaml                    # Config deploy Render
├── vercel.json                    # Config deploy Vercel
├── pyproject.toml                 # Dependências Python
├── requirements.txt               # Mirror das deps Python
├── README.md                      # Este ficheiro
│
├── src/
│   ├── main.py                    # FastAPI entrypoint + registo de routers
│   ├── config.py                  # Settings (env vars)
│   ├── worker.py                  # Celery worker
│   ├── api/
│   │   └── dependencies/
│   │       └── auth.py            # JWKS, get_current_user, org context vars
│   ├── database/                  # SQLAlchemy models, session, models_v2
│   ├── modules/
│   │   ├── m1_ingestor/           # Classificação + WhatsApp
│   │   ├── m2_market/             # CASAFARI + INE
│   │   ├── m3_financial/          # Motor fix & flip
│   │   ├── m4_deal_pipeline/      # Kanban de negócios
│   │   ├── m5_due_diligence/      # Checklists
│   │   ├── m6_renovation/         # Obras
│   │   ├── m7_marketing/          # Creative engine
│   │   ├── m8_leads/              # CRM leads
│   │   └── m9_closing/            # Fecho + P&L
│   ├── shared/                    # Utils, document router, deps
│   └── frontend/                  # Next.js 15 app
│       ├── app/                   # Rotas (login, signup, leads, pipeline, ...)
│       ├── components/
│       ├── lib/                   # API client, Supabase client
│       ├── middleware.ts          # Auth SSR (getUser + redirect)
│       └── public/                # Assets estáticos
│
├── scripts/                       # Setup, migrations, backups
├── docs/                          # Arquitectura e relatórios
├── tests/                         # Pytest suite (M1-M9)
├── backups/                       # Exports semanais (cron)
└── whatsapp-bridge/               # Servidor Express Baileys (gateway local)
```

---

## Estado do Projecto

| Fase | Âmbito | Estado |
|---|---|---|
| **Fase 1** | Multi-tenant + RLS (models v2, 48 tabelas, migração SQLite→PostgreSQL) | ✅ CONCLUÍDA |
| **Fase 2A** | Auth standalone (Supabase Auth PKCE + JWKS + middleware SSR + isolamento por org) | ✅ CONCLUÍDA (Abr/2026, PV-D 8/8 passou) |
| **Fase 2B** | SSO + identity provider (Google/Microsoft) | ⏸️ PENDENTE |
| **Fase 3** | Cleanup (remover Streamlit, legacy refs, README) | 🔄 EM EXECUÇÃO (branch `fase-2a-cleanup`) |

---

## Notas Operacionais

- **Deploy backend:** push para `main` dispara auto-deploy Render (`imoia-api`)
- **Deploy frontend:** deploy manual via `vercel --prod` + re-aplicar alias `imoia.vercel.app` (ver secção correspondente em `CLAUDE.md`)
- **Backups:** `scripts/backup_supabase.py` corre via cron semanal (domingos 3h), exporta JSON para `backups/`
- **Observabilidade:** logs estruturados via `loguru`
- **Histórico de decisões técnicas:** ver `CLAUDE.md` secção "Histórico de Decisões Técnicas"
