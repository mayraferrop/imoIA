# Relatório — Fase 2B: Roles, Convites e Google OAuth

> **Período coberto:** 2026-04-10 (Dia 1 roles) → 2026-04-13 (fix invite org activa)
> **Branch:** `fase-2b` (mergeada em `main` em 2026-04-10)
> **Estado actual:** Fase 2B concluída e validada em produção. OAuth Google funcional. UI Admin operacional.

---

## 1. Resumo Executivo

| | |
|---|---|
| **Início** | 2026-04-10 |
| **Fim** | 2026-04-13 (último fix) |
| **Commits** | 7 (4 features + 1 merge + 1 docs + 1 fix) |
| **Ficheiros alterados** | 28 |
| **Linhas** | +3045 / −46 |
| **Testes unitários** | 33 (14 roles + 19 invites) |
| **Testes E2E** | 10/10 API + 7/7 Chrome MCP + 1 OAuth manual |

**Objectivo:** adicionar sistema de roles, convites por email, Google OAuth e UI de administração ao imoIA — permitindo onboarding self-service de novos membros por convite e login com conta Google.

**Estado final:** sistema completo de roles (owner/admin/member), convites com token + email (Resend), login Google OAuth com fluxo de invite, e painel admin para gestão de convites e membros.

---

## 2. Dia 1 — Sistema de Roles (`97500a8`)

### 2.1 O que foi feito
- **Migração 002:** `verify_and_seed_owner.sql` — script idempotente que valida schema da Fase 1 e confirma seed do owner HABTA.
- **Helpers de role:** `src/api/dependencies/roles.py` com 3 funções: `get_user_role_in_org`, `is_user_admin_or_owner`, `is_user_owner`.
- **Dependencies FastAPI:** `require_admin` (403 se não admin/owner) e `require_owner` (403 se não owner).
- **14 testes unitários** com mocks httpx (sem pytest-asyncio).

### 2.2 Decisões técnicas
- **Sem migração de schema:** a coluna `role` já existia desde a Fase 1 (migração 001) com 3 valores (`owner`, `admin`, `member`). Apenas os helpers e dependencies eram necessários.
- **httpx + SERVICE_ROLE_KEY:** mesmo padrão de `auth.py` — consulta PostgREST directamente em vez de SQLAlchemy.
- **Sem modelo SQLAlchemy `OrganizationMember`:** o projecto usa PostgREST directo para esta tabela, consistente com a arquitectura existente.

### 2.3 Estatísticas
- 4 ficheiros, +346 / −0

---

## 3. Dia 2 — Sistema de Convites (`c4edf40`)

### 3.1 O que foi feito
- **Migração 003:** tabela `organization_invites` com RLS + GRANTs (constraint única `org_id + email`).
- **Service layer** (`src/api/services/invites.py`): `create_invite`, `get_invite_by_token`, `accept_invite`, `list_invites`, `revoke_invite`, `send_invite_email`.
- **5 endpoints CRUD:**

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `POST` | `/api/v1/invites` | require_admin | Criar convite + enviar email |
| `GET` | `/api/v1/invites` | require_admin | Listar convites da org |
| `GET` | `/api/v1/invites/validate/{token}` | publico | Validar token |
| `POST` | `/api/v1/invites/{token}/accept` | auth | Aceitar convite |
| `DELETE` | `/api/v1/invites/{invite_id}` | require_admin | Revogar convite |

- **Email Resend:** HTML PT-BR com branding imoIA e link de convite. Graceful degradation se `RESEND_API_KEY` ausente (log warning, invite criado sem email).
- **19 testes unitários** com mocks (0.12s).

### 3.2 Decisões técnicas
- **Resend via httpx directo** (sem SDK) — consistente com o padrão do projecto de evitar SDKs desnecessários.
- **Token via `secrets.token_urlsafe(32)`** — 256 bits de entropia, URL-safe.
- **Expiração de 7 dias** — compromisso entre segurança e conveniência.
- **Router sem `auth_deps` globais** — o endpoint `validate/{token}` é público, necessário para a página de invite.

### 3.3 Estatísticas
- 8 ficheiros, +981 / −0

---

## 4. Dia 3 — Google OAuth + Frontend de Convites (`f1bca5f`)

### 4.1 O que foi feito
- **Botão Google OAuth** na página de login (alternativa ao magic link existente).
- **5 páginas/rotas frontend:**

| Página | Tipo | Descrição |
|--------|------|-----------|
| `/login` | Modificada | Botão "Continuar com Google" + separador "ou" |
| `/invite/[token]` | Nova | Validação do convite + opções Google/magic link |
| `/invite/[token]/accept` | Nova | Aceitar convite após autenticação |
| `/no-access` | Nova | Para users autenticados sem organização |
| `/auth/callback` | Modificada | Suporte `next` param + verificação de org |

- **i18n:** 19 chaves novas em `locales/pt.json` (invite, no_access, Google button).

### 4.2 Decisões técnicas

#### Token via URL params (não sessionStorage)
O `redirectTo` do Supabase OAuth passa por server-side route (`/auth/callback/route.ts`), que não tem acesso a `sessionStorage`. Solução: token do invite viaja como query param `next=/invite/{token}/accept`.

#### Anti open-redirect no callback
Validação `next.startsWith("/") && !next.startsWith("//")` — bloqueia redirects para URLs externas (ex: `//evil.com`).

#### Verificação de org no callback
Após `exchangeCodeForSession`, o callback consulta `organization_members` via Supabase server client. Se o user não pertence a nenhuma org e não tem `next` param, redireciona para `/no-access`.

### 4.3 Estatísticas
- 6 ficheiros, +436 / −6

---

## 5. Dia 4 — UI Admin (`ec099b0`)

### 5.1 O que foi feito
- **Página `/admin/invites`:** formulário de criação (email + role) + tabela com status badges (pending/accepted/revoked/expired) + botão revogar.
- **Página `/admin/members`:** tabela com role badges (owner=purple, admin=blue, member=slate) + dropdown de mudança de role.
- **2 endpoints backend:**

| Método | Path | Auth | Descrição |
|--------|------|------|-----------|
| `GET` | `/api/v1/members` | require_admin | Listar membros da org |
| `PATCH` | `/api/v1/members/{user_id}/role` | require_admin | Mudar role |

- **Validações de segurança:** owner não pode ser despromovido, self-change bloqueado, apenas roles `admin`/`member` aceites.
- **Sidebar:** secção "Admin" condicional, visível apenas para admin/owner.
- **Middleware:** `/invite` adicionado a `PUBLIC_PATHS`.

### 5.2 Estatísticas
- 9 ficheiros, +669 / −1

---

## 6. Merge e Validação

### 6.1 Merge (`1355ac1`)
Branch `fase-2b` mergeada em `main` com 18 ficheiros, +1763 / −6.

### 6.2 Testes E2E — API (10/10)

| # | Teste | Resultado |
|---|-------|-----------|
| 1 | Criar invite (admin) | 201 |
| 2 | Validar token (publico) | 200 + org name + role |
| 3 | Listar invites (admin) | 200 + 1 invite pending |
| 4 | Aceitar invite (auth) | 200 + membership criado |
| 5 | Invite aceite nao e reutilizavel | 400 |
| 6 | Revogar invite (admin) | 200/204 |
| 7 | Invite revogado nao e validavel | 400/404 |
| 8 | Non-admin nao pode criar invite | 403 |
| 9 | Frontend build OK | exit 0 |
| 10 | Google OAuth endpoint configurado | Supabase retorna redirect URL |

Todos executados contra API local com JWT real gerado via `admin/generate_link` + `auth/v1/verify`.

### 6.3 Testes E2E — Chrome MCP (7/7)

| # | Teste | URL | Resultado |
|---|-------|-----|-----------|
| A | Invite valido | `/invite/{token}` | Org HABTA, role member, botoes Google + email |
| B | Token invalido | `/invite/token-invalido` | "Convite invalido" + link voltar |
| C | Login com redirect | `/login` | Middleware redireciona para / (esperado para user autenticado) |
| D | No-access | `/no-access` | "Sem acesso" + mensagem + botao Sair |
| E | Admin invites | `/admin/invites` | Formulario + tabela + invite de teste visivel |
| F | Admin members | `/admin/members` | Tabela com owner (voce) + role badge |
| G | Cleanup invite | Supabase directo | Invite revogado com sucesso |

### 6.4 Teste OAuth Manual (1/1)
- **User:** `mayaraferrop@gmail.com` (conta Google real)
- **Fluxo:** invite criado → URL enviada → login Google em janela privada → invite aceite automaticamente → membership criado na HABTA
- **Resultado:** Login e invite aceites com sucesso. Dados visíveis após troca de org.
- **Bug encontrado:** org activa era "Personal" em vez da convidada (ver secção 7.1).

---

## 7. Bugs Encontrados e Corrigidos

### 7.1 Org activa errada após aceitar invite (`5cd1cbd`)
- **Sintoma:** após aceitar invite via Google OAuth, o dashboard mostrava dados vazios.
- **Causa raiz:** user novo tinha 2 orgs (Personal auto-criada + HABTA do invite). O `restoreActiveOrg` seleccionava a primeira da lista (Personal, sem dados). A página `accept` não guardava a `organization_id` no localStorage.
- **Fix:** após `resp.ok` no accept, guardar `data.organization_id` em `localStorage("imoia_active_org_id")` antes de redirecionar.
- **Impacto:** 4 linhas adicionadas em `accept/page.tsx`.

---

## 8. Issues Operacionais Resolvidas

### 8.1 Render free tier deploy flaky
- **Problema:** deploy do commit `ec099b0` falhou com `build_failed`. Logs expirados (>7 dias no free tier).
- **Diagnóstico:** reprodução local bem-sucedida (pip install, imports, startup OK). Consulta à API Render revelou 3 de 4 deploys recentes falhados (incluindo commits docs-only). Padrão de falha intermitente no free tier.
- **Resolução:** re-deploy via API com `clearCache: true` → sucesso.

### 8.2 Vercel alias desactualizado 16 dias (`8c4b391`)
- **Problema:** `imoia.vercel.app` apontava para deploy de 16 dias atrás. Aliases auto-atribuidos eram `imo-ia.vercel.app` (nome do projecto).
- **Causa raiz:** alias manual criado com `vercel alias set` — atado a deploy especifico, não auto-actualiza.
- **Resolução:**
  1. Projecto Vercel renomeado de `imo-ia` para `imoia` via API.
  2. `imoia.vercel.app` adicionado como domain do projecto (auto-actualiza a cada deploy).
  3. Domain antigo `imo-ia.vercel.app` removido.
  4. CLAUDE.md actualizado.

### 8.3 URL do backend Render
- **Descoberta:** durante testes, confirmado que a URL correcta do backend e `https://imoia.onrender.com` (sem `-backend`). Frontend ja usava a URL correcta. Render API confirmou nome do servico e URL.

---

## 9. TODOs Pendentes (Herdados)

| # | Item | Prioridade | Origem |
|---|------|-----------|--------|
| 1 | Refactor `supabase_rest.py` para usar JWT do utilizador em vez de `SERVICE_ROLE_KEY` | Media | Dia 1 (defense in depth via RLS) |
| 2 | Aplicar policy `invites_select_own_org` no Supabase Dashboard | Media | Dia 2 (usa `auth.uid()`, precisa de ser aplicada manualmente) |
| 3 | DNS warning `aws-1-eu-west-1.pooler.supabase.com` | Baixa | Fase 1 (funciona, sem impacto) |
| 4 | Render free tier sleep (50s wake-up) — decisao pendente sobre upgrade | Media | Operacional |
| 5 | Apagar servico `imoia-dashboard` no Render | Baixa | Fase 3 cleanup (manual no dashboard) |
| 6 | Org "Personal" auto-criada para novos users — avaliar se desejavel | Baixa | Dia 3 (trigger `handle_new_user` cria org automaticamente) |

---

## 10. Proximas Fases Possiveis

### 10.1 Fase 2C — MFA + Microsoft OAuth
- MFA opcional para clientes corporativos (TOTP via Supabase Auth).
- Microsoft OAuth para empresas que usam Azure AD.
- Estimativa: 2-3 dias, sem urgencia definida.

### 10.2 RLS Hardening
- Migrar backend de `SERVICE_ROLE_KEY` para JWT do utilizador em queries PostgREST.
- Aplicar policies RLS pendentes (invites, etc.).
- Testar isolamento multi-tenant com 2+ organizacoes reais.

### 10.3 Self-service de Organizacoes
- Hoje a criacao de orgs e via SQL ou trigger automatico.
- Endpoint proprio para auto-onboarding quando tivermos registo aberto.

### 10.4 Auditoria e Monitoring
- Log de logins (quem, de onde, quando).
- Device tracking / suspicious login alerts.
- Dashboard de actividade por org.

---

## 11. Commits-chave

| Commit | Data | Tipo | Descrição |
|--------|------|------|-----------|
| `97500a8` | 2026-04-10 | feat | Dia 1: sistema de roles + helpers + dependencies |
| `c4edf40` | 2026-04-10 | feat | Dia 2: sistema de convites + 5 endpoints + email Resend |
| `f1bca5f` | 2026-04-10 | feat | Dia 3: Google OAuth + 5 paginas frontend |
| `1355ac1` | 2026-04-10 | merge | Merge fase-2b → main (Dias 1-3) |
| `ec099b0` | 2026-04-10 | feat | Dia 4: UI admin invites + members |
| `8c4b391` | 2026-04-10 | docs | Fix alias Vercel (projecto renomeado) |
| `5cd1cbd` | 2026-04-13 | fix | Seleccionar org convidada como activa apos aceitar |

---

## 12. Sistemas Externos

- **Supabase:** auth (Google OAuth provider configurado), pooler `aws-1-eu-west-1.pooler.supabase.com:6543`
- **Render:** servico `imoIA` em `https://imoia.onrender.com` (backend, Docker, free tier)
- **Vercel:** projecto `imoia` (team `mayraferrops-projects`), domain `imoia.vercel.app` (auto-actualiza)
- **Resend:** email de convites (graceful degradation se key ausente)
- **Google Cloud Console:** OAuth client configurado com redirect para `supabase.co/auth/v1/callback`

---

*Relatório gerado em 2026-04-13. Fase 2B concluída e validada em produção.*
