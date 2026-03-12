# ImoScout — Detector de Oportunidades Imobiliárias via WhatsApp

## Visão Geral
Sistema Python que monitoriza grupos de WhatsApp Business, usa Claude Haiku para detetar
oportunidades imobiliárias em Portugal, enriquece com dados de mercado (INE + Idealista),
e apresenta resultados num dashboard Streamlit.

## Stack
- Python 3.11+ | SQLite + SQLAlchemy 2.0 | Streamlit
- Whapi.Cloud (WhatsApp API) | Anthropic API (Claude Haiku 4.5) | INE API | Idealista API

## Comandos
- `python -m src.pipeline.run` — corre o pipeline completo
- `streamlit run src/dashboard/app.py` — lança o dashboard
- `pytest tests/` — corre os testes

## Convenções
- Todo o código Python com type hints obrigatórios
- Docstrings em português de Portugal (Google style)
- Logging com loguru (nunca print)
- Mensagens de UI e análise de IA em português de Portugal
- Nomes de variáveis/funções em inglês (snake_case)
- Nunca commitar .env, auth/ ou dados pessoais
- SQLAlchemy 2.0 syntax (select(), Session com context manager)

## Contratos Entre Módulos (CRÍTICO — todos os teammates devem respeitar)

### Modelos de Dados (src/database/models.py)
- **Message**: id, whatsapp_message_id, group_id, group_name, sender_id, sender_name, content, message_type, media_url, timestamp, processed, created_at
- **Opportunity**: id, message_id (FK), is_opportunity, confidence, opportunity_type, property_type, location_extracted, parish, municipality, district, price_mentioned, area_m2, bedrooms, ai_reasoning, original_message, status, created_at
- **MarketData**: id, opportunity_id (FK), ine_median_price_m2, ine_quarter, idealista_avg_price_m2, idealista_listings_count, idealista_comparable_urls, estimated_market_value, estimated_monthly_rent, gross_yield_pct, net_yield_pct, price_vs_market_pct, imt_estimate, stamp_duty_estimate, total_acquisition_cost, notes, created_at
- **Group**: id, whatsapp_group_id, name, is_active, last_processed_at, message_count, opportunity_count, created_at

### Interfaces Partilhadas
- `WhatsAppClient.fetch_unread_messages(group_id: str, since: datetime) → list[dict]`
- `WhatsAppClient.list_active_groups() → list[dict]`
- `WhatsAppClient.archive_group(group_id: str) → bool`
- `OpportunityClassifier.classify_batch(messages: list[dict]) → list[OpportunityResult]`
- `INEClient.get_median_price(municipality: str) → dict | None`
- `IdealistaClient.search_comparables(location: str, property_type: str, area_m2: float) → dict | None`
- `YieldCalculator.calculate(purchase_price: float, monthly_rent: float, municipality: str) → YieldResult`
- `run_pipeline() → PipelineResult`

### Tipos Partilhados (dataclasses)
```python
@dataclass
class OpportunityResult:
    message_index: int
    is_opportunity: bool
    confidence: float
    opportunity_type: str | None
    property_type: str | None
    location: str | None
    parish: str | None
    municipality: str | None
    district: str | None
    price: float | None
    area_m2: float | None
    bedrooms: int | None
    reasoning: str

@dataclass
class YieldResult:
    gross_yield_pct: float
    net_yield_pct: float
    imt: float
    stamp_duty: float
    annual_costs: float
    total_acquisition_cost: float

@dataclass
class PipelineResult:
    messages_fetched: int
    opportunities_found: int
    groups_processed: int
    errors: list[str]
```

## Estrutura de Ficheiros e Ownership

| Ficheiro | Owner |
|---|---|
| CLAUDE.md, pyproject.toml, .env.example, src/config.py | Team Lead |
| src/database/models.py, src/database/db.py | Team Lead |
| src/whatsapp/client.py | Ingestor |
| src/pipeline/run.py | Ingestor |
| scripts/setup_cron.sh | Ingestor |
| tests/test_whatsapp.py, tests/test_pipeline.py | Ingestor |
| src/analyzer/classifier.py, src/analyzer/prompts.py | Analista |
| src/market/ine.py, src/market/idealista.py, src/market/yield_calculator.py | Analista |
| tests/test_classifier.py, tests/test_market.py | Analista |
| src/dashboard/app.py | Dashboard |
| tests/test_dashboard.py | Dashboard |

## Dados de Teste
```json
[
  {"index": 0, "text": "Bom dia a todos!", "group": "Consultores Lisboa"},
  {"index": 1, "text": "T2 em Sacavém, 85m2, remodelado, 3º andar com elevador. Preço: 195.000€. Contactar João 912345678", "group": "Partilhas AML"},
  {"index": 2, "text": "URGENTE - Casal em processo de divórcio precisa vender T3 em Almada, Pragal. 110m2, vista rio. Querem despachar rápido. 180.000€ negociáveis. Não está nos portais.", "group": "Off Market Sul"},
  {"index": 3, "text": "Alguém conhece bom canalizador na zona de Sintra?", "group": "Consultores Lisboa"},
  {"index": 4, "text": "Prédio inteiro em Mouraria, Lisboa. 4 frações, 2 devolutas. Proprietário idoso quer vender tudo junto. 650.000€. Potencial de reabilitação enorme. DM para mais info.", "group": "Investidores PT"},
  {"index": 5, "text": "Oferta de crédito habitação — taxas desde 2.1%. Simulação gratuita. Contacte-nos!", "group": "Partilhas AML"},
  {"index": 6, "text": "Off-market: Moradia T4 em Cascais, São Domingos de Rana. 200m2 + jardim 500m2. Herança, família quer resolver rápido. 420.000€. Exclusivo, não partilhar.", "group": "Off Market Cascais"},
  {"index": 7, "text": "Terreno rústico 5000m2 em Mafra com viabilidade para 3 moradias conforme PU. 150.000€. Alvará em fase de aprovação.", "group": "Investidores PT"}
]
```

### Resultados Esperados
- Mensagens 0, 3, 5 → NÃO são oportunidades
- Mensagens 1, 2, 4, 6, 7 → SÃO oportunidades
- Mensagens 2 e 6 → confiança mais alta (urgentes + off-market)
- Mensagem 4 → confiança alta (prédio inteiro, reabilitação)

## Setup
1. `cp .env.example .env` e preencher com as chaves
2. `pip install -e .`
3. `python -m src.pipeline.run` para testar
4. `streamlit run src/dashboard/app.py` para o dashboard
5. `bash scripts/setup_cron.sh` para agendar execução diária
