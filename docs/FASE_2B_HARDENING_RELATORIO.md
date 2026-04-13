# Relatório — Fase 2B Hardening

> **Data:** 2026-04-10
> **Branch:** `fase-2b-hardening` (mergeada em `main`)
> **Estado:** Hardening concluído. 4 sub-tarefas executadas.

---

## 1. Resumo Executivo

| | |
|---|---|
| **Sub-tarefas** | 4 (todas concluídas) |
| **Ficheiros alterados** | 20 |
| **Policies RLS criadas** | 4 (organization_invites) |
| **Testes** | 33/33 verdes |

**Objectivo:** fortalecer segurança e operações da Fase 2B — migrar services para JWT, aplicar RLS em invites, documentar monitorização, fechar TODOs.

---

## 2. Sub-tarefa 1 — Refactor JWT Incremental

### O que foi feito
- **`auth.py`**: guarda raw JWT em `current_user_token` contextvar após validação JWKS.
- **`supabase_rest.py`**: contextvar `current_user_token` criado. `_headers()` mantém SERVICE_ROLE_KEY (FIXME para migração futura dos 13 ficheiros restantes).
- **`roles.py`**: `get_user_role_in_org()` usa JWT do utilizador com fallback SERVICE_ROLE_KEY.
- **`members.py`**: nova função `_jwt_or_supa_headers()` — queries a `organization_members` usam JWT; `_get_user_email()` mantém SERVICE_ROLE_KEY (admin API).
- **`invites.py`**: FIXME adicionado (depende de accept_invite que precisa SERVICE_ROLE_KEY porque o user ainda não é membro).
- **13 ficheiros**: marcados com `FIXME(jwt-refactor)` para migração futura.

### Decisão técnica
Abordagem incremental: migrar apenas os 3 services da Fase 2B que já têm policies `authenticated` nas suas tabelas. Os 13 ficheiros restantes continuam com SERVICE_ROLE_KEY até que TODAS as tabelas tenham policies.

### Estatísticas
- 18 ficheiros, +86 / −15

---

## 3. Sub-tarefa 2 — RLS Policies em organization_invites

### O que foi feito
4 policies RLS criadas na tabela `organization_invites`:

| Policy | Operação | Quem |
|--------|----------|------|
| `invites_select_own_org` | SELECT | Membros da org (`authenticated`) |
| `invites_insert_admin` | INSERT | Admin/owner da org |
| `invites_update_admin` | UPDATE | Admin/owner da org |
| `invites_delete_admin` | DELETE | Admin/owner da org |

### Decisão técnica
- Usou `current_setting('request.jwt.claims', true)::json->>'sub'` em vez de `auth.uid()` — o role `imoia_app` não tem USAGE no schema `auth`.
- Equivalente funcional: ambos extraem o `sub` (user_id) do JWT.
- Migração 003 actualizada com as policies (idempotente, IF NOT EXISTS).

### Nota sobre accept_invite
`accept_invite()` mantém SERVICE_ROLE_KEY porque o user que aceita o convite ainda **não é membro** da org — as policies SELECT/UPDATE bloqueariam o acesso.

### Estatísticas
- 2 ficheiros, +80 / −30

---

## 4. Sub-tarefa 3 — Documentação de Monitorização

### O que foi feito
- Criado `docs/MONITORIZACAO.md` com instruções para UptimeRobot (backend + frontend).
- Monitors recomendados: `https://imoia.onrender.com/health` e `https://imoia.vercel.app`.
- Alertas: email + Slack/Discord opcional.

### Estatísticas
- 1 ficheiro, +47

---

## 5. Sub-tarefa 4 — Fecho de TODOs

### Itens fechados
| # | Item | Estado |
|---|------|--------|
| 1 | RLS organization_invites | ✅ Resolvido (4 policies) |
| 3 | JWT refactor supabase_rest.py | ✅ Parcialmente resolvido (3/16 services migrados) |

### Itens que permanecem abertos
| # | Item | Prioridade | Motivo |
|---|------|-----------|--------|
| 2 | DNS warning pooler | Baixa | Zero impacto funcional, mitigado pelo Render Starter |
| 4 | Apagar imoia-dashboard no Render | Baixa | Acção manual no dashboard |
| 5 | Org "Personal" auto-criada | Baixa | Fix parcial resolve UX imediato |

---

## 6. Commits

| Commit | Tipo | Descrição |
|--------|------|-----------|
| Sub-tarefa 1 | refactor | JWT incremental + FIXME markers |
| Sub-tarefa 2 | feat | 4 policies RLS em organization_invites |
| Sub-tarefa 3 | docs | Guia de monitorização UptimeRobot |
| Sub-tarefa 4 | docs | Fecho de TODOs + relatório de hardening |

---

## 7. Estado de Segurança Pós-Hardening

| Camada | Estado |
|--------|--------|
| JWT JWKS (auth.py) | ✅ Validação via chave pública ECC P-256 |
| Multi-tenant (org filter) | ✅ `current_org_id` contextvar + `_org_filter()` fail-closed |
| RLS organizations | ✅ 4 policies `authenticated` (Fase 1) |
| RLS organization_members | ✅ 4 policies `authenticated` (Fase 1) |
| RLS organization_invites | ✅ 4 policies `authenticated` (hardening) |
| JWT em roles/members | ✅ Migrado (hardening) |
| JWT em invites | ⚠️ SERVICE_ROLE_KEY (accept_invite precisa) |
| JWT nos 13 services restantes | ⏸️ Pendente (FIXME markers colocados) |

---

*Relatório gerado em 2026-04-10. Hardening Fase 2B concluído.*
