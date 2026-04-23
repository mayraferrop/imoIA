# imoIA — Status Atual vs. Apresentação (Roadmap até Lançamento)

> **Objetivo deste ficheiro:** ser a fonte única de verdade sobre o que já está pronto, o que a apresentação comercial promete, e o que falta fazer antes de lançar. Lido no início de cada sessão (referenciado em `CLAUDE.md`).
>
> **Target:** `src/frontend/public/apresentacao-imoia.html` (117k, 2314 linhas — última versão 9/Abril, 14:04)
>
> **Data desta revisão:** 2026-04-23
>
> **Regras de manutenção:**
> - Atualizar após cada sprint ou mudança significativa
> - Cada módulo tem 4 secções: **Target** (o que a apresentação promete), **Atual** (o que existe e funciona), **Gap** (diferença concreta), **Prioridade** (P0 bloqueia lançamento / P1 importante / P2 pós-lançamento)
> - Não inflacionar "Funcional" — se a feature só funciona em happy path mas quebra com dados reais, é "Parcial"

---

## 1. Visão geral — onde estamos

| Camada | Estado | Nota |
|---|---|---|
| Fundação (BD, backend, frontend, auth, multi-tenant) | ✅ Fase 1 + 2A concluídas | 48 tabelas Supabase, RLS, magic link PKCE, X-Organization-Id |
| Deploy produção | ✅ Live | Backend Render, Frontend Vercel (`imoia.vercel.app`), Supabase eu-west-1 |
| Ciclo completo ponta-a-ponta (WhatsApp → oportunidade → deal → closing) | ⚠️ Parcial | M1, M4, M6, M7, M8 funcionais; M2/M9 parciais; **sem dados BR** |
| Pronto para piloto Santos/BR | ❌ Não | Gaps críticos em M2 (dados BR), M3 (impostos BR), M7 (portais BR), M8 (portais BR) |
| Pronto para piloto Portugal | ⚠️ Quase | Pipeline M1 valida, faltam integrações externas estáveis (Casafari/SIR credenciais, M9 completo) |

---

## 2. Módulos — Target vs Atual vs Gap

### M0 — Estratégia de Investimento

**Target (HTML):** Não tem secção dedicada; aparece embutido como "cada oportunidade recebe nota A–F" + "matching com perfil do investidor (Fix & Flip / Buy & Hold / Value-Add / Wholesale / Mediação)".

**Atual:** `/strategy` renderiza 10 estratégias configuráveis; tabelas `investment_strategies` e `classification_signals` preenchidas; classifier usa estratégia para scoring em M1.

**Gap:** Nenhum essencial. Falta UI para criar/editar estratégia custom do tenant (hoje são read-only defaults).

**Prioridade:** P2

---

### M1 — Ingestor (Captação 24/7)

**Target (HTML):**
- Busca ativa em WhatsApp, Facebook, portais imobiliários
- IA filtra spam, stickers, mensagens irrelevantes
- Analisa "centenas de mensagens por minuto"
- Cada oportunidade: grade A–F automática + dados de mercado

**Atual:**
- WhatsApp via Baileys bridge (companion mode, SQLite local, buffer 5000/grupo)
- Pipeline 5-fase + DLQ com backoff exponencial (F1–F5 concluídas 2026-04-23)
- Classifier Claude Haiku com prompt rigoroso para fix-and-flip
- Scoring via `deal_scorer.py` (regra 70%, yield, MAO)
- Cron Render 5×/dia (08/11/14/17/20 UTC)
- Admin UI: `/admin/runs`, `/admin/dlq`
- **Portais PT (scraper M1)** — Imovirtual ✅ funcional (parser via `__NEXT_DATA__`, 4 buscas default: apartamento+moradia × Lisboa+Porto). Idealista dormant (DataDome bloqueia — reactivar com API paga). Filtro obrigatório por estratégia activa no `OpportunityClassifier`. Cron `imoia-scraper-cron` 1x/dia às 07 UTC. Migration 007 aplicada (Sprint 1 #2, 2026-04-23)

**Gap:**
1. **Facebook**: prometido mas não existe scraper/integração
2. **Portais BR (ZAP, OLX, VivaReal)**: zero — bloqueador para Santos
3. **"Centenas de msgs/minuto"**: hoje batch de 500 msgs/run, 5 runs/dia. Real é ~50-150/dia total. Não é falso mas não é "centenas por minuto" de forma sustentada

**Prioridade:**
- Facebook captação: **P2** (pós-lançamento)
- Portais BR captação: **P0** para piloto Santos
- WhatsApp PT: ✅ pronto
- Portais PT captação: ✅ pronto (Imovirtual)

---

### M2 — Pesquisa de Mercado

**Target (HTML):**
- Avaliações automáticas (AVM)
- Preços reais de transação
- Deal flow e lançamentos
- Integrações: **DataZAP, FipeZAP, ITBImap, Homer, Órulo** (tudo brasileiro)

**Atual:**
- Router `/api/v1/market/*` com ~15 endpoints
- Clientes implementados: `casafari_client.py`, `sir_client.py`, `ine_client.py`, `bpstat_client.py` (tudo PT)
- Cache 7-30 dias
- UI `/market` com gráficos zona/distrito

**Gap:**
1. **DataZAP, FipeZAP, ITBImap, Homer, Órulo**: zero integração (0% para BR)
2. Credenciais SIR/Casafari precisam estar ativas em produção (ver env vars Render)
3. UI mostra só PT — não tem switcher país

**Prioridade:**
- Integrações BR (DataZAP/FipeZAP/ITBImap): **P0** para piloto Santos
- Homer/Órulo (deal flow BR): **P1**
- Validar Casafari/SIR em prod: **P0** (PT)

---

### M3 — Motor Financeiro

**Target (HTML):**
- 3 cenários (conservador/realista/otimista)
- MAO (70/65/60% ARV)
- ROI, TIR, yield, cash flow mês-a-mês
- Todos os impostos: ITBI, ITCMD, cartório (BR)

**Atual:**
- Router com 8 endpoints (`/scenarios`, `/mao`, `/floor-price`, `/quick-imt`, etc.)
- `calculator.py` + `tax_tables.py` com IMT PT, imposto de selo PT
- UI `/financial` funcional com simulação multi-cenário
- Cashflow projection em BD

**Gap:**
1. **Impostos BR**: não há ITBI (transferência), ITCMD (herança), cartório — apenas IMT PT
2. Alguns endpoints usam SERVICE_ROLE_KEY em vez do JWT do user (FIXME herdado)

**Prioridade:**
- Tabelas fiscais BR: **P0** para piloto Santos
- FIXME auth: **P1**

---

### M4 — Deal Pipeline (Kanban)

**Target (HTML):**
- Kanban visual com estratégia variável (Mediação / Fix&Flip / Buy&Hold / Value-Add / Wholesale / Temporada)
- Fluxo: Triagem → Análise → Proposta → Compromisso → Escritura → Venda
- Controle de comissões, velocidade dos deals

**Atual:**
- Router com ~20 endpoints
- State machine com 8-10 estados + transições validadas + histórico
- Sub-recursos: tasks, visits, proposals, commissions, rentals
- UI `/pipeline` funcional

**Gap:**
1. **Visualização "velocidade de deals"** (métrica de tempo médio por estágio) — estrutura existe em BD mas não há widget na UI
2. Estratégias BR específicas (ex: "Temporada" = short-stay Airbnb) precisam de estado adequado

**Prioridade:** P1 (funcional para lançamento, tuning pós)

---

### M5 — Due Diligence

**Target (HTML):**
- Checklists por tipo de imóvel
- Controle de certidões, alvarás, documentação
- Pipeline **bloqueia até tudo verificado**
- Alertas de risco

**Atual:**
- Router com ~10 endpoints
- Templates PT / BR / ES (`templates.py`)
- Endpoint `/can-proceed` valida bloqueio
- UI `/due-diligence` funcional
- Docs em Supabase Storage

**Gap:**
1. **Templates BR**: existe stub mas precisa revisão com advogado BR (certidão de ônus, matrícula actualizada, ITBI pago, etc.)
2. **Alertas automáticos**: não há jobs que correm e avisam quando certidão vai expirar

**Prioridade:**
- Templates BR revistos: **P0** para piloto Santos
- Alertas expiração: **P2**

---

### M6 — Gestão de Obra

**Target (HTML):**
- Orçamento por rubrica
- Pagamentos por milestone
- Alertas de desvio (prazo/orçamento)
- Fotos antes/durante/depois
- Para construtora: medições automáticas, aprovações em cadeia, integração contabilidade, custo/margem por unidade

**Atual:**
- Router com ~10 endpoints
- Milestones auto-gerados
- Despesas sincronizadas com M3 (`cashflow_sync.py`)
- Fotos em Supabase Storage com signed URLs
- UI `/renovation` funcional

**Gap:**
1. **Alertas de desvio automáticos**: só visual, não envia notificação
2. **Vertente construtora** (multi-unidades, medições, aprovações em cadeia): não existe — é funcionalidade separada

**Prioridade:**
- Alertas: **P2**
- Vertente construtora: **P2** (fora do scope lançamento)

---

### M7 — Marketing Engine

**Target (HTML):**
- Brand Kit (cores, fontes, tom)
- Conteúdo 4 idiomas (PT, EN, FR, mandarim)
- Posts sociais, descrições, email campaigns
- Vídeos gerados automaticamente
- Publicação automática em **ZAP, OLX, VivaReal, Idealista**
- Gestão de anúncios Meta/Google/TikTok com IA
- Otimização horário de publicação

**Atual:**
- Brand Kit em Supabase Storage (logos + cores + tom)
- Listings e criativos em BD + Storage
- Geração IA multilingue (5 idiomas: PT/EN/ES/FR/DE — **falta mandarim**)
- `creative_studio.py` + `html_renderer.py` (Cloudflare Worker + workers-og) para renderizar criativos
- Email campaigns, social media accounts/posts modelados
- UI `/marketing` + `/marketing/[listing_id]` funcional

**Gap:**
1. **Publicação automática em portais** (ZAP, OLX, VivaReal, Idealista): zero — só gera conteúdo, não publica
2. **Mandarim**: não há
3. **Gestão de anúncios Meta/Google/TikTok**: não há integração com APIs de Ads — é uma promessa totalmente aberta
4. **Vídeos automáticos** (Reels/Stories): mencionado mas não implementado
5. **Publicação social media real** (Instagram/Facebook/TikTok): tabelas existem mas não há OAuth + posting real

**Prioridade:**
- Publicação portais BR (ZAP, OLX, VivaReal): **P0** para piloto Santos
- Publicação portais PT (Idealista, Imovirtual): **P1**
- Social media posting (IG/FB mínimo): **P1**
- Mandarim: **P2**
- Ads Meta/Google: **P2** (promessa ambiciosa, pós-lançamento)
- Vídeos: **P2**

---

### M8 — Leads CRM

**Target (HTML):**
- Grade A–F automática por lead
- Pipeline novo → contatado → qualificado → visita → proposta → ganho
- Integração com portais imobiliários
- Rastreio de origem (qual canal trouxe melhor lead)
- Respostas automáticas com tom da marca
- Habta.eu mencionado para PT

**Atual:**
- Router com ~15 endpoints
- Scoring + matching com deals
- Interactions (call/email/meeting)
- Sync Habta.eu funcional
- UI `/leads` funcional

**Gap:**
1. **Captura de leads via portais**: não há webhook/integração com ZAP, OLX, Idealista etc.
2. **Respostas automáticas IA**: não existe — é promessa aberta
3. **Rastreio de origem**: campo existe mas não há attribution pipeline

**Prioridade:**
- Captura portais BR: **P0** para piloto Santos
- Captura portais PT: **P1**
- Respostas IA automáticas: **P1** (pode ser simples em v1: template + variables)
- Attribution: **P2**

---

### M9 — Fecho + P&L

**Target (HTML):**
- Workflow Compromisso → Escritura → Registo
- Lucro real vs projetado
- Impostos automáticos
- P&L por empreendimento, margem por unidade
- Relatórios fiscais

**Atual:**
- Router com ~12 endpoints
- `closing_service.py` + `pnl_service.py`
- UI `/closing` parcial
- Tabelas `closing_processes`, `deal_pnl`

**Gap:**
1. **Workflow de documentos** (upload + estado por documento) incompleto
2. **Relatórios fiscais exportáveis** (PDF/Excel): não existe
3. **P&L por empreendimento (multi-unidades)**: estrutura só suporta 1 deal = 1 propriedade
4. **Integração contabilidade**: não existe

**Prioridade:**
- Workflow docs: **P1**
- Relatórios PDF: **P1**
- Multi-unidades: **P2** (vertente construtora)

---

## 3. Roadmap sequenciado até lançamento

Ordenado por bloqueio de piloto comercial Santos/BR (prioridade do user) e depois PT.

### Sprint 1 — "Piloto PT pronto" (P0 PT)

1. ✅ **Validar credenciais Casafari/SIR em produção** (concluído 2026-04-23) — todos os 4 endpoints testados no UI com dados reais:
   - `/comparables/search` → 20 imóveis Lisboa, mediana 5430 €/m², min 3567, max 7983
   - `/valuate` (AVM híbrido) → 434 400 € estimado, 85% confiança, 20 comparáveis usados, intervalo 369k–499k
   - `/sir/search` → 5436 €/m², 8761 fogos vendidos (2026-03, Confidencial Imobiliário)
   - `/bpstat/index` → índice 280.2 (base 2015=100), +180%, novos 221.2, existentes 303.2 (Banco de Portugal)
   - **Bugs encontrados e corrigidos:** 4 models M2 (MarketComparable, PropertyValuation, MarketZoneStats, MarketAlert) não tinham `organization_id` → INSERTs falhavam com 503 `IntegrityError NotNullViolation` (commits 9eba71e + 157e792)
2. **M1 captação portais PT** — scraper básico Idealista/Imovirtual (listings novos + alterações de preço)
3. **M8 ingestão leads via email/form PT** — webhook público para receber leads de formulários do site do mediador
4. **M9 completar workflow de documentos** — upload + estado por documento
5. **M7 publicação em Idealista** (mínimo viável: POST API + validação)

### Sprint 2 — "Piloto BR pronto" (P0 BR)

1. **M2 integração DataZAP + FipeZAP** — dados de avaliação BR
2. **M3 tabelas fiscais BR** — ITBI, ITCMD, custos cartoriais por estado (começar SP)
3. **M5 templates due diligence BR** — revistos (matrícula, ônus, IPTU, etc.)
4. **M1 scraping ZAP/OLX/VivaReal** — captação BR
5. **M7 publicação ZAP/VivaReal** — API ou scraping assistido
6. **M8 captura leads portais BR** — webhooks
7. **Switcher de país** no UI (PT/BR) — afeta tabelas fiscais, templates DD, moeda

### Sprint 3 — "Polish lançamento"

1. **M4 widget velocidade de deals** no dashboard
2. **M5 alertas de expiração de certidões** (job + notificação)
3. **M8 respostas automáticas IA** (v1 simples com templates)
4. **M9 relatórios fiscais PDF exportáveis**
5. **M7 publicação Instagram/Facebook** (mínimo viável)
6. **Landing page** com pricing (a definir) + signup

### Pós-lançamento (P2)

- M1 Facebook captação
- M7 ads Meta/Google/TikTok geridos por IA
- M7 vídeos automáticos (Reels/Stories)
- M7 mandarim
- M6 vertente construtora (multi-unidades)
- M9 integração contabilidade
- Fase 2B SSO Google/Microsoft
- Fase 3 cleanup Streamlit

---

## 4. Decisões em aberto (precisam de input do utilizador)

| Tema | Pergunta | Impacto |
|---|---|---|
| Pricing | Qual o modelo? SaaS mensal? Por consultor? Por volume de leads? | Landing page + sistema de billing |
| Piloto Santos | Quem é o cliente? Que portais BR usam? | Prioridade dos scrapers BR |
| Portais PT para scraping | Idealista v3.5 tem limits; Imovirtual precisa scraping. Autorização explícita? | Risco legal / rate limits |
| Meta/Google Ads | Temos acesso a APIs business? Orçamento para testar? | M7 ads realistas ou só placeholder |
| Multi-país UI | Tenant escolhe país na signup ou detectado por org? | UX Sprint 2 |
| Vertente "construtora" | In-scope para lançamento ou v2? | Se in-scope, Sprint 3 fica sobrecarregado |

---

## 5. Apresentação vs. realidade — onde ser honesto

A apresentação atual tem promessas que **não estão implementadas**:

- "Captação 24/7 em WhatsApp + Facebook + portais" → só WhatsApp hoje
- "Análise de centenas de msgs/minuto" → ~50-150/dia em volume real
- "Publicação automática em ZAP/OLX/VivaReal/Idealista" → zero
- "Anúncios geridos por IA em Meta/Google/TikTok" → zero
- "Conteúdo em mandarim" → zero
- "Portal web próprio com tour 360°" → não existe
- "Dados BR: DataZAP, FipeZAP, ITBImap" → zero

**Antes de apresentar a cliente piloto**, decidir:
- (a) **Cortar da apresentação** o que não está pronto (mais honesto)
- (b) **Marcar como "em breve"** com ETAs realistas
- (c) **Implementar mínimo viável** das features mais vendáveis antes da apresentação

Sugestão default: **(b)** para P2, **(c)** para P0 que bloqueiam o caso de uso do piloto.

---

## 6. Histórico de alterações a este doc

| Data | O quê |
|---|---|
| 2026-04-23 | Criação inicial pós-Fase 2A, F1-F5 M1 e bug fix `_save_results` |
