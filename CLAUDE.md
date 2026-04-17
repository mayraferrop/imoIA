# CLAUDE.md — imoIA
> Este arquivo define o comportamento padrão do Claude Code neste projeto.
> Leia este arquivo integralmente antes de qualquer ação.

---

## 🧠 Contexto do Projeto

**imoIA** é uma plataforma de inteligência imobiliária com automação via WhatsApp, scraping de imóveis, CRM de leads e dashboard — voltada para o mercado de investidores brasileiros em Portugal.

**Objetivo central:** capturar leads via SEO/conteúdo → qualificar via WhatsApp (Whapi) → converter em clientes HABTA / Iron Capitals.

**Módulos ativos:**
- Whapi / WhatsApp (mensagens, webhooks, automação)
- Scraping de imóveis (coleta de dados de portais)
- CRM / Leads (pipeline, qualificação, histórico)
- Dashboard / Frontend (visualização e gestão)

---

## 🎯 Estado Actual das Fases

| Fase | Estado | Notas |
|------|--------|-------|
| **Fase 1** — Fundação (BD, backend base, frontend base) | ✅ **CONCLUÍDA** | Supabase migration, modelos v2, 11 módulos M0-M9 |
| **Fase 2A** — Activação de Autenticação | ✅ **CONCLUÍDA** (Abr/2026) | Dia 1 backend + Dia 2 frontend + Dia 3 PV-D (8/8 testes passaram) |
| **Fase 2B** — SSO (Google / Microsoft) | ⏸️ PENDENTE (futuro) | Adiado |
| **Fase 3** — Cleanup (remover Streamlit, legacy refs, update README) | ⏸️ PENDENTE (adiado) | Prioridade baixa — adiado por frente comercial urgente (piloto Santos/BR) |

**Fase 2A — Detalhe da validação PV-D (Abr/2026):**
- Teste 1: Redirect sem sessão ✅
- Teste 2: Login real com magic link (PKCE) ✅
- Teste 3: Navegação em todas as 11 páginas com Authorization header ✅
- Teste 4: Logout limpo (cookies + localStorage) ✅
- Teste 5: Re-login após logout ✅
- Teste 6: API rejeita sem auth (401/403/200 consistentes) ✅
- Teste 7: Isolamento por organização (multi-tenant em 4 endpoints) ✅
- Teste 8: Refresh automático de token ✅

**Próximas prioridades (pós Fase 2A):**
1. Frente comercial urgente — apresentação a cliente piloto em Santos/Brasil
2. Fase 3 cleanup (adiado)
3. Fase 2B SSO (futuro)

---

## 🏗️ Arquitetura e Stack

- **Runtime:** Node.js (gerenciado via NVM)
- **Linguagem:** TypeScript (frontend), Python (backend)
- **Base de dados:** Supabase PostgreSQL (via pooler, transaction mode)
- **ORM:** SQLAlchemy 2.0 (backend) + PostgREST (frontend/REST)
- **WhatsApp:** Whapi.cloud (REST API)
- **Deploy:** Render (backend), Vercel (frontend)
- **Versionamento:** Git / GitHub (branch principal: `main`)

---

## 👥 Time de Agentes — Definição e Responsabilidades

Quando receber instruções para trabalhar em paralelo, monte este time automaticamente.
**Nunca use subagentes.** Use instâncias paralelas do Claude Code.

---

### 🔵 Agente 1 — Arquiteto (Mapeador)
**Quando ativar:** início de qualquer nova tarefa complexa ou quando o projeto evoluiu significativamente.

**Responsabilidades:**
- Mapear estrutura completa de arquivos e pastas
- Identificar módulos, rotas, serviços, controllers e integrações
- Documentar dependências externas (package.json, APIs, variáveis de ambiente)
- Produzir relatório de estrutura antes que os outros agentes comecem

**Output esperado:** lista de arquivos relevantes + mapa de dependências

---

### 🟡 Agente 2 — Whapi / WhatsApp Specialist
**Quando ativar:** qualquer tarefa relacionada a mensagens, webhooks, status de conversa.

**Responsabilidades:**
- Manter e depurar a integração com a API Whapi
- Gerir funcionalidades: envio, recebimento, marcar como lida, arquivar, resposta automática
- Monitorar mudanças na API do Whapi (endpoints, headers, payloads)
- Garantir que webhooks estejam recebendo e processando corretamente

**Contexto crítico da API Whapi:**
- Endpoint base: verificar sempre em `.env` ou config
- Autenticação: Bearer token no header `Authorization`
- Arquivar mensagem: confirmar endpoint atual (houve mudança no lado do Whapi em março/2026)
- Marcar como lida: verificar se o `message_id` está no formato correto

**Regra:** Sempre testar com `curl` ou Postman antes de commitar qualquer mudança na integração.

---

### 🟠 Agente 3 — CRM / Leads Manager
**Quando ativar:** tarefas de gestão de leads, qualificação, funis, status de contatos.

**Responsabilidades:**
- Estrutura e manipulação do pipeline de leads
- Regras de qualificação (lead quente/frio, origem, comportamento)
- Filtros e segmentações por perfil de investidor
- Integrações com fontes de entrada (formulários, SEO, scraping)

---

### 🔴 Agente 4 — Bug Investigator
**Quando ativar:** qualquer bug reportado ou comportamento inesperado.

**Responsabilidades:**
- Reproduzir o bug com base na descrição
- Rastrear o histórico Git para identificar quando o bug foi introduzido
- Cruzar código atual com documentação da API/biblioteca afetada
- Propor fix com código pronto, não apenas descrição do problema

**Protocolo:**
1. Ler os últimos 10 commits relevantes ao módulo afetado
2. Identificar o último estado funcional
3. Propor correção mínima (menor mudança possível para resolver)
4. Nunca refatorar enquanto depura — um problema de cada vez

---

### 🟣 Agente 5 — Scraping Specialist
**Quando ativar:** tarefas de coleta de dados de portais imobiliários (Idealista, Imovirtual, OLX, etc.).

**Responsabilidades:**
- Manter e evoluir os scrapers existentes
- Gerir rate limiting e rotação de headers para evitar bloqueios
- Normalizar dados coletados para o schema interno do imoIA
- Monitorar mudanças de estrutura HTML/API nos portais-alvo
- Persistência dos dados scrapeados (deduplicação, atualização)

**Regras:**
- Sempre respeitar `robots.txt` e limites de requisição dos portais
- Nunca fazer scraping em loop sem delay configurável
- Dados brutos → transformação → persistência: pipeline em 3 etapas separadas
- Logar falhas de scraping sem interromper o processo completo

---

### ⚪ Agente 6 — Dashboard / Frontend
**Quando ativar:** qualquer tarefa de UI, visualizações, componentes, ou rotas de frontend.

**Responsabilidades:**
- Componentes de visualização do pipeline de leads
- Tabelas e filtros de imóveis scrapeados
- Interface de gestão de conversas WhatsApp
- Integrações frontend → API backend do imoIA

**Stack frontend:**
- Verificar na primeira execução se é React/Next.js ou outro framework
- Manter consistência de estilos com o sistema de design existente
- Não introduzir bibliotecas UI novas sem avaliar o que já está em uso

---

### 🟤 Agente 7 — QA / Testes
**Quando ativar:** antes de qualquer commit em produção.

**Responsabilidades:**
- Verificar se o código novo não quebra funcionalidades existentes
- Rodar testes existentes e reportar falhas
- Escrever testes para funcionalidades novas se não existirem
- Validar integrações externas (Whapi, etc.) com dados reais de teste

**Regra de ouro:** Testes passam → commit. Nunca o contrário.

---

## 📋 Regras Globais de Comportamento

### Git
- **Formato de commit:** `tipo(módulo): descrição curta` — ex: `fix(whapi): corrigir endpoint de arquivar`
- **Tipos aceitos:** `feat`, `fix`, `refactor`, `docs`, `test`, `chore`
- **Nunca** commitar código quebrado, mesmo como WIP sem marcação clara
- Push sempre após commit confirmado: `git push origin main`

### Código
- **TypeScript strict mode** — sem `any` sem justificativa
- Variáveis sensíveis **sempre** em `.env`, nunca hardcoded
- Funções com mais de 30 linhas devem ser quebradas
- Comentários em **português** para lógica de negócio

### Comunicação
- Sempre responder em **português**
- Sínteses ao final de cada tarefa complexa no formato:
  ```
  ✅ O que foi feito
  ⚠️ O que ficou pendente
  🔜 Próximo passo sugerido
  ```

### Segurança
- Nunca logar tokens, senhas ou dados de clientes
- Variáveis de ambiente: checar se `.env` está no `.gitignore` antes de qualquer push
- Dados de leads (nome, telefone, email): tratar como PII — não expor em logs

---

## 🔄 Workflow Padrão para Novas Tarefas

```
1. Agente 1 mapeia o estado atual do projeto
2. Agente relevante executa a tarefa
3. Agente 5 (QA) valida
4. Commit com mensagem padronizada
5. Push para main
6. Síntese entregue no terminal
```

---

## 📁 Módulos Principais

| Módulo | Localização (aproximada) | Agente Responsável |
|--------|--------------------------|-------------|
| Whapi Integration | `/src/integrations/whapi/` | Agente 2 |
| Scraping | `/src/scrapers/` | Agente 5 |
| Lead Management | `/src/modules/leads/` | Agente 3 |
| Webhooks | `/src/webhooks/` | Agente 2 |
| Dashboard / Frontend | `/src/frontend/` ou `/client/` | Agente 6 |
| API Routes | `/src/routes/` | Agente 1 |
| Config / Env | `/src/config/` | Agente 1 |

> ⚠️ Ajustar caminhos acima na primeira execução do Agente 1 se estiverem incorretos.

---

## 🚫 O que NÃO fazer

- Não refatorar código que não está quebrado durante uma correção de bug
- Não instalar dependências novas sem checar se já existe alternativa no projeto
- Não alterar `.env.example` sem documentar no commit
- Não usar `console.log` em produção — usar logger estruturado
- Não fazer merge de branch sem testes passando

---

## 📝 Histórico de Decisões Técnicas

| Data | Decisão | Motivo |
|------|---------|--------|
| Mar/2026 | Whapi: endpoint de arquivar atualizado pelo fornecedor | Mudança no lado do Whapi, não bug nosso |
| Mar/2026 | NVM adicionado ao `.zshrc` para persistência | Evitar `command not found: claude` em terminais novos |
| Mar/2026 | Vercel: projecto renomeado `imo-ia` → `imoia` | alias `imoia.vercel.app` agora é domain do projecto (auto-actualiza) |
| Abr/2026 | Migração SQLite → Supabase PostgreSQL concluída | BD principal é Supabase (48 tabelas, pooler aws-1-eu-west-1:6543) |
| Abr/2026 | User `imoia_app` para SQLAlchemy, RLS ativado em todas tabelas | anon=SELECT only, imoia_app=ALL, service_role=bypass |
| Abr/2026 | SQLite removido, DATABASE_URL obrigatório | Sem fallback — PostgreSQL é o único BD suportado |
| Abr/2026 | Backup semanal via cron + scripts/backup_supabase.py | Domingos 3h, exporta JSON para backups/ |
| Abr/2026 | Fase 2A Auth concluída e validada (PV-D 8/8 passou) | Magic link PKCE + middleware SSR + RLS multi-tenant + isolamento por org (X-Organization-Id) |
| Abr/2026 | Supabase Storage adoptado como único sistema de ficheiros (criativos M7, logos brand kit, docs M5) | Endpoint `/documents/{id}/download` com JWT retornava 401 em tags `<img>` (não enviam Authorization). Signed URLs resolvem previews + uploads + escalabilidade numa intervenção estrutural. Substitui filesystem local em `storage/` |

> Adicionar novas entradas aqui quando decisões técnicas relevantes forem tomadas.

---

## 🚀 Deploy do Frontend (Vercel)

**URL de produção:** `https://imoia.vercel.app`

**Projecto Vercel:** `imoia` (team: `mayraferrops-projects`)
- Root Directory configurado como `src/frontend` no dashboard Vercel
- `imoia.vercel.app` é domain do projecto (auto-actualiza a cada deploy de produção)
- Push para `main` activa auto-deploy no Vercel

**Comandos de deploy manual (se necessário):**
```bash
# A partir da raiz do projecto:
vercel --prod --scope mayraferrops-projects --yes --cwd /Users/mayaraferro/Projects/imoIA
```

**IMPORTANTE:**
- Nunca fazer `vercel --prod` de dentro de `src/frontend/` — causa erro de path duplicado
- O alias `imoia.vercel.app` actualiza-se automaticamente (não é necessário `vercel alias set`)
