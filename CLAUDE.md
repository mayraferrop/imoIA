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

## 🏗️ Arquitetura e Stack

- **Runtime:** Node.js (gerenciado via NVM)
- **Linguagem:** TypeScript
- **WhatsApp:** Whapi.cloud (REST API)
- **IDE:** Antigravity
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

> Adicionar novas entradas aqui quando decisões técnicas relevantes forem tomadas.
