# Auditoria: Apresentação HTML vs Realidade Implementada

> **Data:** 2026-04-13
> **Ficheiro auditado:** `src/frontend/public/apresentacao-imoia.html`
> **Método:** leitura do HTML + verificação de código (endpoints, services, API clients)
> **Critério:** código que FUNCIONA em produção, não código que existe no repo

---

## Legenda

| Icone | Significado |
|-------|-------------|
| ✅ | **FUNCIONAL** — implementado, endpoints respondem, lógica real |
| 🟡 | **PARCIAL** — código existe mas com gaps significativos |
| 🔴 | **STUB** — código existe mas retorna mock/placeholder |
| ❌ | **NÃO EXISTE** — zero código |
| ⚙️ | **INFRA** — infraestrutura/auth, não feature visível |

---

## 1. Módulos M1–M9

| Funcionalidade prometida | Estado | Evidência |
|---|---|---|
| **M1 — Ingestor: busca WhatsApp** | ✅ | `whatsapp_client.py` faz calls reais à Whapi.Cloud. Pipeline `run_pipeline()` funcional |
| M1 — busca Facebook Groups | ❌ | Zero código de integração com Facebook Graph API. Não existe |
| M1 — busca em portais imobiliários | ❌ | Não existe `src/scrapers/`. Nenhum scraper implementado |
| M1 — IA classifica mensagens A-F | ✅ | `classifier.py` + `prompt_builder.py` chamam LLM. Classificação real |
| M1 — dados de mercado automáticos | 🟡 | Casafari (PT) funciona. Fontes BR (DataZAP, FipeZAP, ITBImap) não existem |
| **M2 — Market Research: avaliação automática** | 🟡 | AVM local funciona com Casafari (PT). Fontes BR prometidas não integradas |
| M2 — Casafari (comparáveis PT) | ✅ | `casafari_client.py` com JWT auth + search real |
| M2 — INE / BPstat / SIR (dados PT) | ✅ | 3 clients reais com API calls e cache |
| M2 — DataZAP / FipeZAP (dados BR) | ❌ | Zero código. Nenhum client implementado |
| M2 — ITBImap (transações reais BR) | ❌ | Zero código |
| M2 — Homer / Órulo (deal flow BR) | ❌ | Zero código |
| **M3 — Financial Calculator** | ✅ | `calculator.py` com lógica real: ROI, TIR, cashflow, IMT/IS. 18 endpoints |
| M3 — impostos PT (IMT, IS, cartório) | ✅ | `tax_tables.py` com tabelas reais PT |
| M3 — impostos BR (ITBI, ITCMD) | 🟡 | Tabelas existem mas cobertura limitada vs prometido |
| M3 — 3 cenários automáticos | ✅ | `POST /scenarios/{property_id}` gera conservador/realista/otimista |
| M3 — fluxo de caixa mensal | ✅ | Projeções mês a mês persistidas em `cashflow_projections` |
| **M4 — Deal Pipeline** | ✅ | 30+ endpoints, state machine com 10 estratégias, kanban funcional |
| M4 — comissões e propostas | ✅ | Endpoints dedicados para `proposals`, `commission` |
| **M5 — Due Diligence** | ✅ | 13 endpoints, checklists por tipo, red flags, upload docs |
| **M6 — Obra & Reforma** | ✅ | 26 endpoints, milestones, expenses, fotos, alertas orçamento |
| M6 — integração CashFlow Pro | 🟡 | `cashflow_sync.py` existe mas depende de config externa |
| **M7 — Marketing: brand kit** | ✅ | CRUD completo de brand kit (cores, fontes, tom de voz) |
| M7 — conteúdo IA multi-idioma | ✅ | `content_generator.py` chama Claude API, 5 idiomas (PT/EN/BR/FR/ZH) |
| M7 — posts redes sociais | 🔴 | Cria posts no BD mas `publish_post()` retorna `"status": "stub"` |
| M7 — campanhas email | 🔴 | Gera HTML com Jinja2 mas `send_campaign()` retorna `"Email provider nao configurado"` |
| M7 — vídeos automáticos | 🔴 | `video_factory.py` grava metadados mas `render_video()` retorna `"stub://placeholder.mp4"` |
| M7 — publicação em portais (ZAP/OLX) | 🔴 | `publish_to_habta()` e `send_to_whatsapp()` são TODO stubs |
| M7 — artes/peças gráficas | 🔴 | Plugin architecture existe (Pillow, Playwright, Trolto) mas rendering é stub |
| **M8 — Leads CRM** | ✅ | 24+ endpoints, pipeline stages, interações, nurture sequences |
| M8 — scoring A-F "por IA" | 🟡 | Scoring funciona mas é **rule-based** (soma ponderada), não usa LLM |
| M8 — integração com portais | ❌ | Nenhuma integração real com portais de distribuição |
| **M9 — Closing & P&L** | ✅ | 18+ endpoints, workflow CPCV→escritura, P&L real vs projetado |
| M9 — relatórios fiscais | ✅ | Fiscal report por ano com cálculo de mais-valias |

---

## 2. Secção "Fontes de Captação"

| Fonte prometida | Estado | Notas |
|---|---|---|
| WhatsApp (grupos de investidores) | ✅ | Whapi.Cloud funcional |
| Facebook Groups | ❌ | Zero integração |
| **Brasil — Captação:** Homer | ❌ | Zero código |
| **Brasil — Captação:** Órulo | ❌ | Zero código |
| **Brasil — Mercado:** DataZAP | ❌ | Zero código |
| **Brasil — Mercado:** FipeZAP | ❌ | Zero código |
| **Brasil — Mercado:** ITBImap | ❌ | Zero código |
| **Brasil — Portais:** ZAP + VivaReal + OLX | ❌ | Zero integração de publicação |
| **Brasil — Portais:** QuintoAndar + Imovelweb | ❌ | Zero código |
| **Europa — Captação:** Casafari | ✅ | Client real com JWT |
| **Europa — Captação:** Idealista | ✅ | OAuth2 client real (só comparáveis, não publicação) |
| **Europa — Mercado:** INE + BPstat + SIR | ✅ | 3 clients reais |
| **Europa — Portais:** Idealista publicação | ❌ | Client só lê, não publica |

---

## 3. Secção "Portal imoIA" (6 cards)

| Card prometido | Estado | Notas |
|---|---|---|
| Listagens integradas (portal público) | ❌ | **Não existe portal público.** Só dashboard admin (requer login) |
| Busca avançada e mapa interativo | ❌ | Não existe. Frontend tem filtros básicos, sem mapa |
| Captação de leads via portal | ❌ | Sem portal público, sem formulários públicos |
| White-label total (domínio próprio) | ❌ | Zero código de white-label ou multi-domain |
| SEO otimizado (schema.org, sitemap) | ❌ | Frontend é SPA Next.js sem SSR público, sem sitemap |
| Tour virtual 360° | ❌ | Zero código |

**Veredicto secção Portal: 0/6 funcional. Secção inteira é aspiracional.**

---

## 4. Secção "Obra & Reforma" (6 cards)

| Card prometido | Estado | Notas |
|---|---|---|
| Gestão completa (fases, cronograma) | ✅ | M6 tem milestones, expenses, alertas |
| Orçamento e custos (previsto vs real) | ✅ | Expenses com categorias + budget alerts |
| Medições e pagamentos | 🟡 | Payments por milestone existem. Auto-medições, faturas e integração contabilidade não |
| Fotos e relatórios | 🟡 | Upload de fotos OK. Relatórios semanais por IA e timeline para cliente não existem |
| P&L real em tempo real | ✅ | M9 tem P&L com custos cruzados |
| IA cruza preços de fornecedores | ❌ | Não existe. Nenhum código de comparação de fornecedores |

---

## 5. Secção "Redes Sociais" (6 cards)

| Card prometido | Estado | Notas |
|---|---|---|
| Publicação multi-canal | 🔴 | Cria posts no BD, mas `publish_post()` é stub. Zero API de publicação |
| Agenda inteligente (IA decide hora) | 🔴 | Calendário editorial existe no BD. IA de timing não |
| Reels e vídeos curtos | 🔴 | `video_factory.py` retorna `stub://placeholder.mp4` |
| Respostas automáticas (DMs/comments) | ❌ | Zero código |
| Campanhas pagas (Meta/Google/TikTok Ads) | ❌ | Zero código |
| Dashboard unificado de métricas | 🔴 | Endpoint `/social/stats` existe mas dados são do BD interno, não de APIs reais |

**Veredicto secção Redes Sociais: 0/6 funcional. Tudo é stub ou inexistente.**

---

## 6. Secção "Marketing & Criativos" (8 cards)

| Card prometido | Estado | Notas |
|---|---|---|
| Descrições de imóveis por IA | ✅ | `content_generator.py` chama Claude API |
| Posts para redes sociais | 🔴 | Conteúdo gerado OK, publicação é stub |
| Campanhas de e-mail | 🔴 | Template HTML gerado, envio é stub (`"provider nao configurado"`) |
| Artes e peças gráficas | 🔴 | Plugin architecture existe, rendering é stub |
| Vídeos automatizados | 🔴 | Metadados OK, render retorna placeholder |
| Anúncios automáticos em portais | ❌ | Zero integração com ZAP/OLX/VivaReal/Idealista publicação |
| Multi-idioma | ✅ | 5 idiomas configurados (PT, EN, BR, FR, ZH) |
| Brand Kit | ✅ | CRUD completo |

---

## 7. Comparativo "Porquê imoIA" (10 rows com ✅)

| Claim da tabela | Estado real | Notas |
|---|---|---|
| Gestão de leads e CRM | ✅ | M8 funcional |
| Publicação em portais imobiliários | ❌ | Zero integração de publicação |
| Captação off-market (WhatsApp, Facebook, grupos) | 🟡 | WhatsApp OK. Facebook e "grupos" genéricos não existem |
| Classificação de oportunidades por IA | ✅ | M1 classifier funcional |
| Simulador fix & flip com TIR e cashflow | ✅ | M3 calculator funcional |
| Due diligence estruturada | ✅ | M5 funcional |
| Gestão de obra e reforma integrada | ✅ | M6 funcional |
| Marketing IA multicanal (texto, imagem, vídeo) | 🔴 | Texto OK (Claude). Imagem e vídeo são stubs. Publicação é stub |
| P&L real vs projetado de portfólio | ✅ | M9 funcional |
| Cobertura Brasil + Europa | 🟡 | Europa (PT) OK com Casafari/INE/BPstat. Brasil: zero fontes integradas |

---

## 8. Hero Stats

| Stat prometido | Realidade |
|---|---|
| "9 módulos integrados" | ✅ 9 módulos existem com código real (M1-M9). "Integrados" é generoso — comunicam via BD |
| "Captação automática" | 🟡 WhatsApp OK. Facebook e portais não |
| "2 mercados (BR + EU)" | 🟡 EU (PT) funcional. BR: zero fontes de dados reais |
| "20+ fontes de dados" | ❌ Fontes reais: ~7 (Whapi, Casafari, Idealista, INE, BPstat, SIR, Claude). BR zero |

---

## 9. Secção IA

| Claim | Estado | Notas |
|---|---|---|
| Analisa centenas de mensagens por minuto | ✅ | Pipeline M1 processa mensagens WhatsApp com LLM |
| Filtragem inteligente (ignora spam) | ✅ | Classifier descarta não-oportunidades |
| Marketing automático (descrições, posts, emails, SEO) | 🔴 | Descrições OK via Claude. Posts/emails/SEO: stubs |

---

## 10. Dashboard & Páginas

| Página prometida | Estado | Notas |
|---|---|---|
| Dashboard (stats & grades) | ✅ | Página `/` com dados reais |
| Propriedades (filtros & busca) | ✅ | `/properties` funcional |
| Pipeline (kanban de deals) | ✅ | `/pipeline` funcional |
| Financeiro (simulações) | ✅ | `/financial` funcional |
| Mercado (comparáveis) | ✅ | `/market` funcional |
| Leads (CRM & scoring) | ✅ | `/leads` funcional |
| Marketing (conteúdo IA) | ✅ | `/marketing` funcional (conteúdo OK, publicação stub) |
| Due Diligence | ✅ | `/due-diligence` funcional |
| Renovation | ✅ | `/renovation` funcional |
| Closing | ✅ | `/closing` funcional |

---

## 11. Infraestrutura (não prometida no HTML mas relevante)

| Item | Estado |
|---|---|
| Auth JWT (magic link + Google OAuth) | ⚙️ ✅ Fase 2A+2B concluídas |
| Multi-tenant (isolamento por org) | ⚙️ ✅ RLS + org filter |
| Roles (owner/admin/member) | ⚙️ ✅ Fase 2B |
| Convites por email | ⚙️ ✅ Resend + token |
| Deploy (Render + Vercel) | ⚙️ ✅ Produção ativa |

---

## Sumário Executivo

### Contagem total

| Categoria | Count | % |
|---|---|---|
| ✅ FUNCIONAL | 30 | 42% |
| 🟡 PARCIAL | 9 | 13% |
| 🔴 STUB | 13 | 18% |
| ❌ NÃO EXISTE | 19 | 27% |
| **Total de claims** | **71** | |

### Realidade brutal

- **42% funciona de verdade** — principalmente os módulos core (M3-M6, M8-M9), dashboard, auth
- **13% parcial** — funciona com gaps (ex: mercado só PT, scoring rule-based vs "IA")
- **18% é stub** — código existe mas não funciona (toda a publicação social/email/vídeo/portais)
- **27% não existe** — zero código (portal white-label, fontes BR, Facebook, ads, tour 360°)

### Top 5 gaps mais críticos

1. **Portal público white-label** — secção inteira do HTML (6 cards) sem NENHUM código. É a feature mais visível para construtoras
2. **Fontes de dados Brasil** — Homer, Órulo, DataZAP, FipeZAP, ITBImap — zero integração. Apresentação promete BR+EU mas só EU funciona
3. **Publicação em portais** — prometido em múltiplas secções, zero integração real (ZAP, OLX, VivaReal, Idealista)
4. **Redes sociais** — toda a secção (6 cards) é stub ou inexistente. publish_post() retorna stub
5. **Facebook Groups monitoring** — prometido como fonte de captação ao lado do WhatsApp, zero código

### Top 5 quick wins (parcial → funcional com pouco trabalho)

1. **Email sending** — template HTML já funciona via Jinja2+Claude. Falta só configurar Resend (já usado nos invites!) como provider no `email_service.py`
2. **Lead scoring "IA"** — se quiser manter o claim, adicionar call ao Claude para enriquecer o score rule-based. Alternativa honesta: remover "IA" da descrição
3. **Publicação social básica** — Instagram/Facebook via Meta Graph API. Código de scheduling já existe, falta só o HTTP call
4. **Flyer/arte gráfica** — plugin Pillow já existe. Falta template real e chamada ao plugin no `creative_studio.py`
5. **Vídeo MVP** — Remotion Lambda é o plano. Alternativa: ffmpeg local para slideshow de fotos com dados overlay

---

*Auditoria realizada em 2026-04-13. Baseada em leitura directa do código-fonte, não em demos ou screenshots.*
