# imoia-creatives — Cloudflare Worker

Renderiza criativos M7 (property cards, listing photos, social posts) via `@vercel/og` (Satori).

## Arquitectura

```
Python backend (Render) ──POST /render (X-Worker-Secret)──▶ Worker ──▶ Satori ──▶ PNG
                                                               ▲
                                                        Templates JSX em src/templates/
```

## Desenvolvimento local

```bash
cd worker-creatives
npm install
npm run dev                      # wrangler dev em http://localhost:8787
```

Para testar com auth em local, criar `.dev.vars`:
```
CREATIVES_SECRET=dev-secret-123
```

## Deploy

1. Login: `npx wrangler login`
2. Secret de produção: `npx wrangler secret put CREATIVES_SECRET`
3. Deploy: `npm run deploy`

URL pública fica algo como `https://imoia-creatives.<subdomain>.workers.dev`.

## Payload esperado

```json
{
  "template": "property_card",
  "brand": { "brand_name": "HABTA", "primary_color": "#1a3e5c", "logo_white_url": "..." },
  "listing": { "title": "T2 Estrela", "price_eur": 425000, "primary_image_url": "..." }
}
```

Template define dimensões via `TEMPLATE_SPECS` em `src/types.ts`.

## Templates suportados

| Template | Dimensão | Uso |
|---|---|---|
| `property_card` | 1080×1350 | IG feed 4:5, pitch deck |
| `listing_main` | 1200×900 | Idealista, Imovirtual, SAPO, OLX |
| `fb_post` | 1200×630 | Facebook feed (em breve) |
| `fb_carousel_card` | 1080×1080 | FB carousel (em breve) |
| `ig_post` | 1080×1080 | IG feed 1:1 (em breve) |
| `ig_story` | 1080×1920 | IG/FB story (em breve) |
| `linkedin_post` | 1200×627 | LinkedIn feed (em breve) |
| `linkedin_square` | 1200×1200 | LinkedIn square (em breve) |
