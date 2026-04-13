# TODOs Fase 3 — Cleanup e Consolidacao

## Duplicacao no M7 Creative Engine

O modulo M7 marketing tem **3 sistemas sobrepostos** para geracao de criativos:

| Sistema | Ficheiro | Estado |
|---------|----------|--------|
| **CreativeService** | `src/modules/m7_marketing/creative_service.py` | **ACTIVO** — motor principal, Pillow + Playwright |
| CreativeStudio | `src/modules/m7_marketing/creative_studio.py` | Legacy — HTML templates, nao usado em producao |
| PluginRegistry | `src/modules/m7_marketing/plugin_registry.py` | Legacy — sistema de plugins, nao integrado |

### Accao recomendada

1. **Manter** `CreativeService` como unico motor de criativos
2. **Remover** `CreativeStudio` e `PluginRegistry` (ou marcar como deprecated)
3. **Consolidar** templates HTML em `templates/` para uso exclusivo do Playwright render dentro de `CreativeService`

---

## Templates Pillow implementados (Dia 3)

| Template | Dimensoes | Estado |
|----------|-----------|--------|
| ig_post | 1080x1080 | Pillow real |
| ig_story | 1080x1920 | Pillow real |
| fb_post | 1200x630 | Pillow real |
| property_card | 1080x1350 | Pillow real |
| whatsapp_card | 800x600 | Reutiliza layout generico |
| flyer (PDF) | A4 794x1123 | ReportLab / Playwright |

---

## Outros TODOs

- [ ] Centralizar provider LLM (Claude) — actualmente `m8_leads/service.py` cria cliente proprio; considerar `src/shared/llm_provider.py`
- [ ] Adicionar fontes custom (Montserrat TTF) ao repo para consistencia entre ambientes
- [ ] Considerar Supabase Storage para criativos em producao (actualmente filesystem local)
- [ ] Remover Streamlit refs residuais (Fase 3 original — adiado)
- [ ] Update README com stack actual pos-Fase 2A
