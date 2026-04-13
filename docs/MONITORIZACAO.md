# Monitorização — imoIA

> Actualizado: 2026-04-10

---

## 1. UptimeRobot — Monitorização de Uptime

### 1.1 O que monitorizar

| Monitor | URL | Tipo | Intervalo |
|---------|-----|------|-----------|
| Backend API | `https://imoia.onrender.com/health` | HTTP(s) | 5 min |
| Frontend | `https://imoia.vercel.app` | HTTP(s) | 5 min |

### 1.2 Configuração

1. Criar conta em [uptimerobot.com](https://uptimerobot.com) (plano gratuito: 50 monitors, 5 min intervalo).
2. **New Monitor** → tipo **HTTP(s)**.
3. URL: `https://imoia.onrender.com/health` (backend) ou `https://imoia.vercel.app` (frontend).
4. Intervalo: **5 minutos**.
5. Alert Contacts: adicionar email do responsavel.

### 1.3 Notas

- O plano Render Starter eliminou cold starts — o backend responde em <1s.
- O endpoint `/health` retorna `200 OK` com status do Supabase REST.
- UptimeRobot gratuito suporta ate 50 monitors com intervalo minimo de 5 min.
- Para alertas Slack/Discord, configurar webhook em Alert Contacts.

---

## 2. Alertas Recomendados

| Cenario | Accao |
|---------|-------|
| Backend down >5 min | Email + Slack (se configurado) |
| Frontend 5xx | Email |
| SSL expira em <14 dias | UptimeRobot detecta automaticamente |

---

## 3. Metricas Futuras (nao implementado)

- Latencia P95 por endpoint (requer APM — ex: Sentry, Datadog)
- Taxa de erro por rota (requer logging estruturado)
- Uso de BD (Supabase Dashboard → Database → Health)
