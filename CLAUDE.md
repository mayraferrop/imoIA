# ImoIA

Plataforma de gestao de investimento imobiliario fix and flip. Dados historicos do ImoScout (167 grupos WhatsApp, 119 oportunidades) foram migrados para a tabela `properties`.

## Arquitectura

O sistema tem 9 modulos. M1-M8 activos, M9 futuro:

- **M1 — Propriedades** (ACTIVO): gestao central de propriedades via API REST
- **M2 — Analista de mercado** (ACTIVO): CASAFARI API + INE, comparaveis, avaliacoes AVM, alertas
- **M3 — Motor financeiro** (ACTIVO): custos aquisicao, obra, financiamento, mais-valias PT/BR, ROI, MAO, go/no-go
- **M4 — Deal pipeline** (ACTIVO): propostas, CPCV, negociacao, maquina de estados
- **M5 — Due diligence** (ACTIVO): checklists, documentos
- **M6 — Gestao de obra** (ACTIVO): orcamento, cronograma, fornecedores, sync Cash Flow Pro
- **M7 — Marketing** (ACTIVO): anuncios multi-plataforma, IA content, email, video, social
- **M8 — CRM de leads** (ACTIVO): compradores, scoring, nurturing
- M9 — Fecho + P&L (FUTURO): ROI real vs estimado

## Stack

- Backend: FastAPI
- BD: SQLite (actual) → PostgreSQL/Supabase (planeado)
- IA: Claude Haiku 4.5 via Anthropic SDK
- Dashboard: Streamlit
- Filas: Celery + Redis (opcional)

## Como correr

```bash
# API FastAPI
uvicorn src.main:app --reload --port 8000

# Dashboard Streamlit
streamlit run src/dashboard/app.py

# Celery worker (opcional)
celery -A src.worker worker --loglevel=info

# Testes
pytest tests/
```

## Convencoes

- Logging: loguru (zero prints)
- Documentacao e docstrings: portugues de Portugal (PT-PT)
- Nomes de variaveis/funcoes: ingles (convencao Python)
- Type hints: obrigatorios em funcoes publicas
- BD actual: SQLite sincrona (src/database/db.py)
- Modelos legacy: src/database/models.py (tabelas historicas, READ-ONLY)
- Modelos activos: src/database/models_v2.py (tabela central: properties)
- Nunca commitar .env, auth/ ou dados pessoais
- SQLAlchemy 2.0 syntax (select(), Session com context manager)

## Tabelas legacy (models.py — READ-ONLY)

Dados historicos do ImoScout. Nao modificar, nao adicionar colunas.

- **groups**: grupos WhatsApp monitorizados (169 registos)
- **messages**: mensagens recebidas (2880 registos)
- **opportunities**: oportunidades detectadas por IA (119 reais, migradas para properties)
- **market_data**: dados de mercado associados (95 registos)

## Tabelas activas (models_v2.py)

- **tenants** — multi-tenant (prepara SaaS)
- **users** — utilizadores com role (investor, partner, analyst, admin)
- **properties** — TABELA CENTRAL (141 registos: 119 migradas + 22 manuais)
- **market_comparables**, **property_valuations**, **market_zone_stats**, **market_alerts** (M2)
- **financial_models** (M3), **deals**, **deal_state_history**, **proposals** (M4)
- **due_diligence_items** (M5), **renovations**, **renovation_expenses** (M6)
- **listings**, **listing_creatives**, **listing_contents** (M7)
- **leads**, **lead_interactions** (M8)
- **transactions**, **deal_pnl** (M9)
- **calendar_events**, **documents**, **notifications** (transversais)

## Estrutura de modulos

Cada modulo segue o padrao: `router.py` (endpoints) → `service.py` (logica) → `schemas.py` (validacao)

```
src/
  api/              # Endpoints base (health, ingestor retrocompat, properties)
  modules/
    m2_market/      # CASAFARI + INE + alertas
    m3_financial/   # Calculo financeiro, fiscalidade PT/BR
    m4_deal_pipeline/  # Maquina de estados de deals
    m5_due_diligence/  # Checklists e documentos
    m6_renovation/     # Gestao de obra + sync externo
    m7_marketing/      # Multi-plataforma + plugins rendering
    m8_leads/          # CRM de compradores
  shared/           # deps, exceptions, document storage
  database/         # models.py (legacy RO), models_v2.py (activo), db.py
  dashboard/        # Streamlit frontend
  config.py         # Configuracao centralizada
  main.py           # FastAPI app
  worker.py         # Celery tasks
```

## M2 — Analista de Mercado (ACTIVO)

### Endpoints M2
- POST /api/v1/market/comparables/search — pesquisar comparaveis
- GET /api/v1/market/deals/{deal_id}/comparables — comparaveis para um deal
- POST /api/v1/market/valuate — avaliacao AVM de imovel
- POST /api/v1/market/deals/{deal_id}/valuate — avaliar deal
- GET /api/v1/market/deals/{deal_id}/arv — estimar ARV (fix and flip)
- GET /api/v1/market/zones/stats — estatisticas de zona
- POST /api/v1/market/alerts — criar alerta de mercado
- GET /api/v1/market/alerts — listar alertas
- DELETE /api/v1/market/alerts/{id} — remover alerta
- POST /api/v1/market/alerts/check — verificar alertas (manual)
- GET /api/v1/market/ine/housing-prices — precos medianos INE (gratuito)
- GET /api/v1/market/overview — overview para dashboard

### CASAFARI API (endpoints reais)
- POST /login — autenticacao JWT (username/password)
- POST /api/v1/references/locations — resolver nome → location_id
- POST /api/v1/listing-alerts/search — pesquisa ad-hoc de listagens (CORE)
- POST /api/v1/listing-alerts/feeds — criar feeds de alertas
- GET /api/v1/listing-alerts/feeds/{id} — obter alertas de um feed
- GET /api/v1/properties/search/{property_id} — detalhe completo
- Auth: Token API ou JWT Bearer

### Ficheiros M2
- src/modules/m2_market/casafari_client.py — cliente CASAFARI API v1 (endpoints reais)
- src/modules/m2_market/ine_client.py — cliente INE (precos medianos habitacao)
- src/modules/m2_market/service.py — MarketService (comparaveis, AVM, alertas)
- src/modules/m2_market/schemas.py — validacao Pydantic
- src/modules/m2_market/router.py — endpoints FastAPI

## M3 — Motor Financeiro (ACTIVO)

### Endpoints M3
- POST /api/v1/financial/ — modelo financeiro completo
- POST /api/v1/financial/scenarios/{property_id} — 3 cenarios automaticos
- GET /api/v1/financial/{model_id} — obter modelo
- GET /api/v1/financial/property/{property_id} — listar modelos
- POST /api/v1/financial/mao — regra dos 70%
- POST /api/v1/financial/floor-price — preco minimo de venda
- POST /api/v1/financial/quick-imt — calculo rapido de IMT/IS
- GET /api/v1/financial/{model_id}/cash-flow — fluxo de caixa mensal

### Parametros fiscais
- Portugal: IMT OE2026 (Lei 73-A/2025), IS 0,8%, mais-valias 50% + IRS progressivo
- Brasil: ITBI 3%, IR ganho capital 15-22,5%

### Ficheiros M3
- src/modules/m3_financial/tax_tables.py — tabelas fiscais (actualizar anualmente)
- src/modules/m3_financial/calculator.py — motor de calculo (FinancialCalculator)
- src/modules/m3_financial/service.py — logica de negocio (FinancialService)
- src/modules/m3_financial/schemas.py — validacao Pydantic
- src/modules/m3_financial/router.py — endpoints FastAPI

## Contratos Entre Modulos

### Interfaces M2 (Pesquisa de Mercado)
- `MarketService.find_comparables(municipality, property_type, ...) → dict`
- `MarketService.valuate_property(municipality, area_m2, ...) → dict`
- `MarketService.estimate_arv(deal_id) → dict`
- `MarketService.get_arv_for_financial_model(deal_id) → float | None`
- `MarketService.get_comparables_for_pricing(deal_id) → dict`
- `CasafariClient.search_listings(location_ids, types, ...) → dict`
- `CasafariClient.resolve_location(name) → int | None`
- `CasafariClient.get_property_detail(property_id) → dict`
- `INEClient.get_median_price(municipality) → dict | None`

### API REST
- `GET /health` — health check
- `GET /api/v1/ingest/opportunities` — listar propriedades (retrocompatibilidade)
- `GET /api/v1/ingest/stats` — estatisticas
- `GET /api/v1/properties/` — listar properties
- `POST /api/v1/properties/` — criar property manual
- `GET /api/v1/properties/{id}` — detalhe
- `PATCH /api/v1/properties/{id}` — actualizar

## Setup
1. `cp .env.example .env` e preencher com as chaves
2. `pip install -e .`
3. `uvicorn src.main:app --reload --port 8000` para a API
4. `streamlit run src/dashboard/app.py` para o dashboard
