# Pós-Cleanup Fase 2A — Ações Manuais Pendentes

Estas ações NÃO podem ser automatizadas porque envolvem estado vivo
em serviços externos. Só a Mayara pode executá-las.

## 1. Apagar serviço `imoia-dashboard` no Render

**O quê:** O serviço `imoia-dashboard` ainda existe no dashboard do Render,
embora o código do Streamlit já tenha sido removido do repositório
(bloco removido do `render.yaml`, `Dockerfile.streamlit` eliminado,
pasta `src/dashboard/` eliminada na sub-tarefa 5.1 do cleanup Fase 2A).
É necessário apagar manualmente.

**Porquê não foi automático:** Serviços vivos no Render são estado
operacional, não código. Só tu tens acesso ao dashboard Render.

**Estado observado durante o cleanup:** `https://imoia-dashboard.onrender.com`
retornou HTTP 404 na rota raiz — o serviço pode estar suspended/sleeping
ou com rota raiz que não responde. Confirma o estado real no dashboard.

**Como fazer:**
1. Vai a https://dashboard.render.com
2. Login na tua conta
3. Na lista de serviços, encontra `imoia-dashboard`
4. Clica no serviço
5. Vai a **Settings** (menu lateral)
6. Scroll até ao fim → **Delete Service**
7. Confirma a eliminação (vai pedir para digitar o nome do serviço)

**Urgência:** Baixa. Pode esperar dias ou semanas. Sem consequências
imediatas além de ocupar um slot no plano Render.

---

## 2. Confirmar que `imoia-api` continua saudável após o cleanup

**O quê:** O `render.yaml` foi alterado na sub-tarefa 5.1 para remover
o bloco `imoia-dashboard`. O serviço `imoia-api` permanece mas convém
verificar que o próximo deploy não é afectado.

**Como fazer:**
1. No dashboard Render, abre o serviço `imoia-api`
2. Verifica que o último deploy está `Live`
3. Faz `curl https://imoia.onrender.com/health` e confirma `200 OK`
4. Se fizeres merge do branch `fase-2a-cleanup` para `main`, acompanha
   o próximo deploy para confirmar que arranca sem erros (as dependências
   `streamlit` e `plotly` foram removidas do `pyproject.toml` e
   `requirements.txt`, o `pip install` deve ficar mais leve)

**Urgência:** Média — verificar imediatamente após merge.

---

## 3. Arquivar / revisar documento `docs/architecture/frontend-nextjs.md`

**O quê:** Este documento descreve a migração Streamlit → Next.js.
Contém referências a Streamlit como documentação histórica do processo
de migração.

**Porquê não foi automático:** É conteúdo narrativo histórico, não é
código. Tem valor documental (registo de decisões de arquitectura).
A decisão de manter/arquivar/reescrever é editorial.

**Opções:**
- **(a)** Manter como está — registo histórico da migração
- **(b)** Mover para `docs/historical/` e adicionar nota no topo:
  *"Documento histórico — cleanup Fase 2A 5.1 concluiu a descontinuação
  do Streamlit em 2026-04-09"*
- **(c)** Reescrever focando apenas na arquitectura Next.js actual

**Urgência:** Baixa. Pode ser feito na sub-tarefa 5.3 (README update)
ou mais tarde.
