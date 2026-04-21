# imoIA WhatsApp Bridge

Ponte WhatsApp baseada em [Baileys](https://github.com/WhiskeySockets/Baileys) que substitui a Whapi.cloud. Conecta-se como um **device** (via QR code), não como companion — portanto `archive` e `mark-as-read` sincronizam 100% com o telemóvel primário.

## Endpoints

Consumidos por `src/modules/m1_ingestor/whatsapp_client.py` (com `backend=baileys`):

| Método | Path | Função |
|---|---|---|
| `GET` | `/status` | Estado da conexão + QR |
| `GET` | `/qr` | QR code renderizado em HTML (para scan via browser) |
| `GET` | `/groups` | Listar grupos ativos |
| `GET` | `/messages/:groupId` | Mensagens em buffer (`?count=N&since=unix_ts`) |
| `PATCH` | `/groups/:groupId` | Marcar read + archive (body: `{"archive": true}`) |
| `POST` | `/resync` | Forçar resync do app state |
| `POST` | `/logout` | Desligar sessão |
| `GET` | `/healthz` | Healthcheck |

## Env vars

| Var | Default | Descrição |
|---|---|---|
| `DATA_DIR` | `./data` | Pasta para `auth_state/` e `messages.json`. Em produção: volume persistente (`/data`). |
| `BRIDGE_TOKEN` | (vazio) | Se definido, `/groups`, `/messages`, `PATCH /groups`, `/resync`, `/logout` exigem `Authorization: Bearer <token>`. `/qr`, `/status`, `/healthz` ficam sempre abertos. |
| `PORT` | `3000` | Porta HTTP. |
| `BAILEYS_LOG` | `silent` | Nível de log do Baileys (`silent`, `info`, `debug`). |
| `MAX_MESSAGES_PER_GROUP` | `500` | Limite do buffer por grupo. |

## Deploy no Fly.io

Requisitos: `flyctl` instalado, conta Fly.io.

```bash
cd whatsapp-bridge

# Primeira vez:
fly launch --no-deploy        # aceitar nome "imoia-whatsapp-bridge", região "mad"
fly volumes create bridge_data --size 1 --region mad
fly secrets set BRIDGE_TOKEN="$(openssl rand -hex 32)"
fly deploy

# Logs em tempo real:
fly logs

# Scan do QR:
# Abrir https://imoia-whatsapp-bridge.fly.dev/qr no browser
# Ou obter QR string: fly logs | grep -A20 "SCAN"
```

## Deploy local (dev)

```bash
cd whatsapp-bridge
npm install
node server.js
# Abrir http://localhost:3000/qr para scan
```

## Apontar backend imoIA para o bridge

No Render (env vars do backend):

```
WHATSAPP_API_BASE=https://imoia-whatsapp-bridge.fly.dev
WHATSAPP_API_TOKEN=<BRIDGE_TOKEN>
# Remover WHAPI_TOKEN (ou deixar vazio) — o client detecta baileys via URL
```

O `whatsapp_client.py` detecta o backend automaticamente pelo `base_url`: se contém `localhost`/`127.0.0.1`, usa `baileys`. Para URL pública do Fly.io, configurar explicitamente em `config.py` ou adaptar a detecção.

## Estado do buffer de mensagens

O bridge mantém um buffer **em memória** (até 500 msgs/grupo) persistido para `messages.json` a cada 60s. Ao reiniciar:

1. Carrega `messages.json` do volume.
2. Reconecta ao WhatsApp.
3. Baileys sincroniza histórico novo (`syncFullHistory: true`).

**Se o volume perder dados** (ex.: volume não montado), é necessário re-parear via QR e aguardar sync completa (pode demorar ~10min para muitos grupos).

## Troubleshooting

- **`/status` retorna `status: "disconnected"` continuamente**: volume não está montado ou `auth_state/` ficheiros corrompidos. Logar `fly ssh console`, verificar `ls /data/auth_state/`.
- **QR expira em loop**: scan dentro de ~60s. Se não der, recarregar `/qr`.
- **`archive` retorna `archived: false`**: app state sync pode estar desalinhado. Chamar `POST /resync` e tentar novamente. Se persistir, remover `/data/auth_state/` e re-parear.
- **Logs vazios**: `BAILEYS_LOG=info` para debug.
