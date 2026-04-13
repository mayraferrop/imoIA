# TODOs herdados da Fase 2B

> Actualizado: 2026-04-13
> Contexto: itens identificados durante a Fase 2B que foram adiados por decisão consciente.

---

## 1. RLS — organization_invites

- **Owner da tabela:** `imoia_app`
- **RLS:** activada
- **Policy actual:** apenas `imoia_app_all` (ALL para role `imoia_app`)
- **Policy `invites_select_own_org`:** NÃO criada
- **Bloqueio:** SQL Editor do Supabase não tem permissões para alterar owner. A policy usa `auth.uid()`, que requer role `authenticated`/`anon` (não `imoia_app`).
- **Plano:** aplicar quando se fizer refactor de `supabase_rest.py` para JWT (item 3 abaixo). Até lá, o backend usa `SERVICE_ROLE_KEY` que bypassa RLS — sem risco funcional.
- **Workaround actual:** backend usa `SERVICE_ROLE_KEY` em todas as queries PostgREST. RLS é bypassed.

---

## 2. DNS warning aws-1-eu-west-1.pooler.supabase.com

- **Sintoma:** `WARNING: (psycopg2.OperationalError) could not translate host name "aws-1-eu-west-1.pooler.supabase.com" to address: Temporary failure in name resolution` nos logs do Render durante startup.
- **Causa raiz:** DNS resolver do container Docker não está pronto quando o SQLAlchemy faz `init_db()` na primeira tentativa de conexão.
- **Host correcto?** Sim — `aws-1-eu-west-1.pooler.supabase.com` resolve correctamente (2 IPs EU-West, TCP OK em 0.2s).
- **Impacto:** zero funcional. Warning nos logs, app arranca normalmente via `pool_pre_ping=True`.
- **Mitigação com Starter:** upgrade de Free para Starter elimina cold starts. Warning só ocorre em redeploys (não em cada request).
- **Fix possível (adiado):** retry loop no `init_db()` de `src/database/db.py` com backoff de 2-3 tentativas. Não prioritário.

---

## 3. Refactor supabase_rest.py para JWT do utilizador

- **Estado:** sub-tarefa futura, não iniciada.
- **O que é:** migrar queries PostgREST de `SERVICE_ROLE_KEY` (bypassa RLS) para JWT do utilizador autenticado (respeita RLS).
- **Benefício:** defense in depth — mesmo que o backend tenha um bug, o RLS impede acesso cruzado entre organizações.
- **Bloqueia:** aplicação da policy `invites_select_own_org` (item 1) e hardening de RLS em geral.
- **Estimativa:** 15+ ficheiros tocados (`src/api/services/*.py`, `src/api/dependencies/*.py`).
- **Pré-requisito:** todas as policies RLS para `authenticated` role devem estar criadas e testadas antes de migrar.

---

## 4. Apagar serviço imoia-dashboard no Render

- **Estado:** pendente (acção manual no dashboard Render).
- **Contexto:** serviço Streamlit descontinuado na Fase 3 cleanup. Código removido em `8cfd0d1`, mas o serviço Render ainda existe.
- **Instruções:** Dashboard Render → Services → imoia-dashboard → Settings → Delete Service.
- **Risco:** zero — código já foi removido, serviço não está a ser usado.

---

## 5. Org "Personal" auto-criada para novos users

- **Sintoma:** quando um user aceita um invite, o trigger `handle_new_user` cria automaticamente uma org "Personal". O user fica com 2 orgs (Personal + org convidada).
- **Fix parcial:** commit `5cd1cbd` garante que a org convidada é seleccionada como activa após aceitar invite.
- **Decisão pendente:** manter a org Personal (pode ser útil para funcionalidades futuras) ou desactivar o trigger para users que chegam via invite.
- **Prioridade:** baixa — o fix parcial resolve o problema de UX imediato.
