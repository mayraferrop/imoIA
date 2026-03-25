# ImoIA — Frontend Architecture (Next.js)

## 1. Overview

Migrar o frontend de Streamlit (prototipo) para Next.js 15 (producao), mantendo a API FastAPI intacta.

```
┌─────────────────────────────┐
│  Next.js 15 (Vercel)        │
│  App Router + SSR            │
│  Supabase Auth (SSR)        │
│  Tailwind CSS 4             │
├─────────────────────────────┤
│         HTTPS               │
├─────────────────────────────┤
│  FastAPI (Render)            │
│  200+ endpoints REST         │
│  /api/v1/*                   │
├─────────────────────────────┤
│  Supabase PostgreSQL         │
│  40 tabelas, 9 modulos      │
└─────────────────────────────┘
```

## 2. Stack

| Camada | Tecnologia | Justificacao |
|---|---|---|
| Framework | Next.js 15 (App Router) | SSR, routing, middleware, Vercel deploy nativo |
| Styling | Tailwind CSS 4 | Utility-first, design tokens, dark mode |
| Auth | Supabase Auth (@supabase/ssr) | Ja temos Supabase, zero custo adicional |
| State | Zustand | Leve (2KB), sem boilerplate, persist middleware |
| HTTP | fetch nativo + SWR | Next.js optimiza fetch, SWR para cache/revalidacao |
| Charts | Recharts | Leve, React nativo, substitui Plotly do Streamlit |
| Forms | React Hook Form + Zod | Validacao type-safe, performance |
| Deploy | Vercel (free tier) | 100GB bandwidth, serverless, preview deploys |

## 3. Routing (App Router)

```
app/
├── layout.tsx                    # Shell: sidebar + header + auth guard
├── page.tsx                      # Dashboard overview (/)
├── login/page.tsx                # Auth: login
├── register/page.tsx             # Auth: register
│
├── properties/
│   ├── page.tsx                  # M1: Lista com cards + filtros
│   └── [id]/page.tsx             # M1: Detalhe propriedade
│
├── market/
│   ├── page.tsx                  # M2: Overview mercado
│   ├── comparables/page.tsx      # M2: Pesquisa comparaveis
│   ├── valuation/page.tsx        # M2: Avaliacao AVM
│   └── alerts/page.tsx           # M2: Alertas
│
├── financial/
│   ├── page.tsx                  # M3: Simulador financeiro
│   └── [modelId]/page.tsx        # M3: Detalhe modelo + cash flow
│
├── pipeline/
│   ├── page.tsx                  # M4: Kanban board
│   ├── [dealId]/page.tsx         # M4: Detalhe deal (tabs)
│   └── mediation/page.tsx        # M4: Pipeline mediacao
│
├── due-diligence/
│   └── [dealId]/page.tsx         # M5: Checklist DD
│
├── renovation/
│   ├── page.tsx                  # M6: Lista obras
│   └── [renovationId]/page.tsx   # M6: Detalhe obra + milestones
│
├── marketing/
│   ├── page.tsx                  # M7: Listings + brand kit
│   ├── [listingId]/page.tsx      # M7: Detalhe listing (conteudo, criativos, video)
│   └── social/page.tsx           # M7: Calendario editorial
│
├── leads/
│   ├── page.tsx                  # M8: Lista leads + pipeline
│   └── [leadId]/page.tsx         # M8: Detalhe lead + nurturing
│
└── closing/
    ├── page.tsx                  # M9: Portfolio + P&L
    └── [closingId]/page.tsx      # M9: Processo de fecho
```

## 4. Authentication

### Flow
```
Browser → Next.js Middleware → Supabase Auth → Protected Page
                                    ↓
                              /login (redirect se nao autenticado)
```

### Middleware (middleware.ts)
- Verifica sessao Supabase em TODAS as rotas excepto /login, /register
- Redirige para /login se sessao expirada
- Refresh automatico do token

### Supabase Auth Setup
- `@supabase/ssr` para server-side auth (cookies, nao localStorage)
- `createServerClient()` nos Server Components
- `createBrowserClient()` nos Client Components
- Row Level Security (RLS) no Supabase para multi-tenant futuro

## 5. Data Fetching

### Padrao: Server Components + SWR para interactividade

```typescript
// Server Component (lista inicial — SSR)
async function PropertiesPage() {
  const data = await apiServer.get('/api/v1/properties/')
  return <PropertyList initialData={data} />
}

// Client Component (revalidacao, filtros, paginacao)
'use client'
function PropertyList({ initialData }) {
  const { data } = useSWR('/api/v1/properties/', fetcher, {
    fallbackData: initialData
  })
  return <...>
}
```

### API Client (lib/api.ts)
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL // https://imoia.onrender.com

// Server-side (sem CORS, directo)
export const apiServer = {
  get: (path: string) => fetch(`${API_BASE}${path}`).then(r => r.json()),
  post: (path: string, body: any) => fetch(`${API_BASE}${path}`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body)
  }).then(r => r.json()),
}

// Client-side (SWR fetcher)
export const fetcher = (path: string) =>
  fetch(`${API_BASE}${path}`).then(r => r.json())
```

### CORS no FastAPI
Adicionar ao main.py:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://imoia.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 6. Component Architecture

### Layout hierarquico
```
RootLayout (app/layout.tsx)
├── AuthGuard (redirect se nao auth)
├── Sidebar (modulos M1-M9, estado activo)
├── Header (user avatar, search, notifications)
└── {children} (conteudo da pagina)
```

### Componentes partilhados (components/ui/)
| Componente | Uso |
|---|---|
| Button | Accoes primarias/secundarias |
| Card | Property cards, deal cards, lead cards |
| Badge | Grades (A-F), estados, tipos |
| DataTable | Listas com sort/filter/paginate |
| EmptyState | Quando nao ha dados |
| MetricCard | KPIs no dashboard |
| Modal | Confirmacoes, formularios |
| Tabs | Detalhe de deals, listings |
| KanbanBoard | M4 pipeline |
| GaugeChart | Go/No-Go M3 |

### Componentes por modulo (components/{module}/)
Cada modulo tem componentes proprios que consomem os endpoints da API.

## 7. State Management

### Zustand Store
```typescript
// stores/app-store.ts
interface AppStore {
  // Auth
  user: User | null
  setUser: (user: User | null) => void

  // UI
  sidebarOpen: boolean
  toggleSidebar: () => void

  // Filtros globais (persistidos)
  filters: { municipality?: string; minPrice?: number; maxPrice?: number }
  setFilters: (f: Partial<Filters>) => void
}
```

### Regra: SWR para server state, Zustand para UI state
- Dados da API → SWR (cache, revalidacao, optimistic updates)
- Estado de UI → Zustand (sidebar, modals, filtros)

## 8. Pages — Mapeamento Streamlit → Next.js

| Streamlit Tab | Next.js Route | Prioridade | Complexidade |
|---|---|---|---|
| M1 Ingestor | /properties | P0 | Media |
| M3 Financeiro | /financial | P0 | Alta (simulador) |
| M4 Pipeline | /pipeline | P0 | Alta (kanban) |
| Dashboard | / | P0 | Media |
| M2 Mercado | /market | P1 | Media |
| M8 Leads | /leads | P1 | Media |
| M7 Marketing | /marketing | P2 | Alta (criativos) |
| M5 Due Diligence | /due-diligence | P2 | Baixa |
| M6 Obra | /renovation | P2 | Media |
| M9 Fecho | /closing | P3 | Media |

## 9. Environment Variables

### Next.js (.env.local)
```
NEXT_PUBLIC_API_URL=https://imoia.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://jurzdyncaxkgvcatyfdu.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

### Vercel (Environment Variables)
Mesmo conteudo, configurado no painel Vercel.

## 10. Deploy

### Vercel (Frontend)
- Conectar repo GitHub `mayraferrop/imoIA`
- Root directory: `src/frontend`
- Framework: Next.js (auto-detect)
- Build command: `npm run build`
- Output: `.next/`

### Render (API) — sem alteracoes
- Ja deployado em https://imoia.onrender.com
- Unica alteracao: adicionar CORS middleware

## 11. Decisoes Arquitecturais

| Decisao | Escolha | Alternativa rejeitada | Razao |
|---|---|---|---|
| Framework | Next.js 15 | Remix, Nuxt | Ecossistema Vercel, SSR nativo, maior comunidade |
| Styling | Tailwind CSS | CSS Modules, Styled Components | Velocity de desenvolvimento, design system rapido |
| Auth | Supabase Auth | NextAuth, Clerk | Ja temos Supabase, zero custo, RLS nativo |
| State | Zustand | Redux, Jotai | Simplicidade, 2KB, sem boilerplate |
| Data fetch | SWR | React Query, tRPC | Mais leve, integra com Next.js fetch cache |
| Charts | Recharts | Plotly.js, Chart.js | React nativo, SSR-friendly, bundle menor |
| Deploy | Vercel free | Netlify, Cloudflare Pages | Next.js nativo, preview deploys, analytics |
