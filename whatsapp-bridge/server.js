/**
 * imoIA WhatsApp Bridge (Baileys)
 *
 * Substitui Whapi.cloud — conecta ao WhatsApp como device (não companion),
 * portanto archive/mark-as-read sincronizam 100% com o telemóvel primário.
 *
 * Endpoints consumidos por src/modules/m1_ingestor/whatsapp_client.py:
 *   GET  /status             — estado da conexão + QR code
 *   GET  /groups             — listar grupos ativos
 *   GET  /messages/:groupId  — mensagens de um grupo (?count=N&since=unix_ts)
 *   PATCH /groups/:groupId   — marcar como lido (buffer + fallback chatModify)
 *
 * Endpoints de operação:
 *   GET  /qr                 — QR code HTML renderizado (para pair via browser)
 *   GET  /healthz            — healthcheck
 *   POST /resync             — força resync do app state
 *   POST /logout             — desliga sessão
 *
 * Auth:
 *   Endpoints aceitam header `Authorization: Bearer <BRIDGE_TOKEN>` se a env
 *   BRIDGE_TOKEN estiver definida. /qr, /status, /healthz ficam sempre abertos
 *   para permitir pairing inicial e monitorização.
 *
 * Persistência:
 *   DATA_DIR (default: ./data) contém auth_state/ e messages.json.
 *   Em produção deve apontar para volume persistente (ex: /data no Fly.io).
 */

import makeWASocket, {
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  Browsers,
} from "@whiskeysockets/baileys";
import express from "express";
import pino from "pino";
import { Boom } from "@hapi/boom";
import path from "path";
import { fileURLToPath } from "url";
import fs from "fs";
import QRCode from "qrcode";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const DATA_DIR = process.env.DATA_DIR || path.join(__dirname, "data");
const AUTH_DIR = path.join(DATA_DIR, "auth_state");
const MSG_STORE_FILE = path.join(DATA_DIR, "messages.json");
const BRIDGE_TOKEN = process.env.BRIDGE_TOKEN || "";
const PORT = Number(process.env.PORT || process.env.BRIDGE_PORT || 3000);
const MAX_MESSAGES_PER_GROUP = Number(process.env.MAX_MESSAGES_PER_GROUP || 500);

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const logger = pino({ level: process.env.BAILEYS_LOG || "silent" });

const messageStore = {};
if (fs.existsSync(MSG_STORE_FILE)) {
  try {
    const saved = JSON.parse(fs.readFileSync(MSG_STORE_FILE, "utf-8"));
    Object.assign(messageStore, saved);
    console.log(`[boot] Mensagens carregadas: ${Object.keys(saved).length} grupos`);
  } catch {
    console.log("[boot] messages.json corrompido, a começar do zero.");
  }
}

function persistMessageStore() {
  const tmp = `${MSG_STORE_FILE}.tmp`;
  try {
    fs.writeFileSync(tmp, JSON.stringify(messageStore), "utf-8");
    fs.renameSync(tmp, MSG_STORE_FILE);
  } catch (err) {
    console.error("[persist] Erro ao gravar mensagens:", err.message);
    try { fs.existsSync(tmp) && fs.unlinkSync(tmp); } catch {}
  }
}

setInterval(persistMessageStore, 60_000);

for (const sig of ["SIGTERM", "SIGINT"]) {
  process.on(sig, () => {
    console.log(`[${sig}] a gravar messages.json antes de sair...`);
    persistMessageStore();
    process.exit(0);
  });
}

let sock = null;
let qrCode = null;
let connectionStatus = "disconnected";
const groupsCache = {};

function extractContent(msg) {
  const m = msg.message;
  if (!m) return { content: "", type: "unknown" };
  if (m.conversation) return { content: m.conversation, type: "text" };
  if (m.extendedTextMessage?.text) return { content: m.extendedTextMessage.text, type: "text" };
  if (m.imageMessage?.caption) return { content: m.imageMessage.caption, type: "image" };
  if (m.videoMessage?.caption) return { content: m.videoMessage.caption, type: "video" };
  if (m.documentMessage) return { content: "", type: "document" };
  if (m.stickerMessage) return { content: "", type: "sticker" };
  if (m.reactionMessage) return { content: "", type: "reaction" };
  if (m.protocolMessage) return { content: "", type: "protocol" };
  return { content: "", type: "unknown" };
}

function getTimestamp(msg) {
  const ts = msg.messageTimestamp;
  if (!ts) return 0;
  if (typeof ts === "object") return ts.low || 0;
  return Number(ts);
}

function normalizeMessage(msg) {
  const { content, type } = extractContent(msg);
  return {
    id: msg.key?.id || "",
    from: msg.key?.participant || msg.key?.remoteJid || "",
    pushName: msg.pushName || "",
    timestamp: getTimestamp(msg),
    type,
    body: content,
  };
}

async function startWhatsApp() {
  const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
  const { version } = await fetchLatestBaileysVersion();

  sock = makeWASocket({
    version,
    logger,
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    browser: Browsers.macOS("Desktop"),
    generateHighQualityLinkPreview: false,
    syncFullHistory: true,
  });

  sock.ev.on("messages.upsert", ({ messages: msgs, type }) => {
    let count = 0;
    for (const msg of msgs) {
      const groupId = msg.key?.remoteJid;
      if (!groupId || !groupId.endsWith("@g.us")) continue;
      if (!messageStore[groupId]) messageStore[groupId] = [];
      const msgId = msg.key?.id;
      if (msgId && messageStore[groupId].some((m) => m.key?.id === msgId)) continue;
      messageStore[groupId].push(msg);
      count++;
      if (messageStore[groupId].length > MAX_MESSAGES_PER_GROUP) {
        messageStore[groupId] = messageStore[groupId].slice(-MAX_MESSAGES_PER_GROUP);
      }
    }
    if (count > 0) console.log(`[upsert] +${count} (${type})`);
  });

  sock.ev.on("messaging-history.set", ({ messages: msgs, isLatest }) => {
    let count = 0;
    for (const msg of msgs || []) {
      const groupId = msg.key?.remoteJid;
      if (!groupId || !groupId.endsWith("@g.us")) continue;
      if (!messageStore[groupId]) messageStore[groupId] = [];
      const msgId = msg.key?.id;
      if (msgId && messageStore[groupId].some((m) => m.key?.id === msgId)) continue;
      messageStore[groupId].push(msg);
      count++;
      if (messageStore[groupId].length > MAX_MESSAGES_PER_GROUP) {
        messageStore[groupId] = messageStore[groupId].slice(-MAX_MESSAGES_PER_GROUP);
      }
    }
    if (count > 0) console.log(`[history] +${count} (latest=${isLatest})`);
  });

  sock.ev.on("chats.upsert", (chats) => {
    for (const c of chats) if (c.id?.endsWith("@g.us")) groupsCache[c.id] = c;
  });
  sock.ev.on("chats.update", (updates) => {
    for (const u of updates) {
      if (u.id?.endsWith("@g.us")) groupsCache[u.id] = { ...(groupsCache[u.id] || {}), ...u };
    }
  });

  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrCode = qr;
      connectionStatus = "waiting_qr";
      console.log("\n" + "=".repeat(50));
      console.log("  WhatsApp: abrir /qr no browser para escanear");
      console.log("=".repeat(50));
      try {
        const qrcodeTerminal = await import("qrcode-terminal");
        qrcodeTerminal.default.generate(qr, { small: true });
      } catch {
        console.log("QR:", qr);
      }
    }

    if (connection === "close") {
      connectionStatus = "disconnected";
      qrCode = null;
      const reason = new Boom(lastDisconnect?.error)?.output?.statusCode;
      if (reason === DisconnectReason.loggedOut) {
        console.log("[conn] Logged out. A apagar auth_state e reiniciar.");
        if (fs.existsSync(AUTH_DIR)) fs.rmSync(AUTH_DIR, { recursive: true });
        process.exit(1);
      }
      console.log("[conn] Perdido. Reconectar em 3s...");
      setTimeout(startWhatsApp, 3000);
    }

    if (connection === "open") {
      connectionStatus = "connected";
      qrCode = null;
      console.log("\n[conn] WhatsApp conectado. API pronta.\n");
    }
  });

  sock.ev.on("creds.update", saveCreds);
}

// ---------------------------------------------------------------------------
// Express API
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json());

app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Methods", "GET, PATCH, POST, OPTIONS");
  res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");
  if (req.method === "OPTIONS") return res.sendStatus(200);
  next();
});

function requireAuth(req, res, next) {
  if (!BRIDGE_TOKEN) return next();
  const header = req.headers.authorization || "";
  const provided = header.replace(/^Bearer\s+/i, "").trim();
  if (provided === BRIDGE_TOKEN) return next();
  return res.status(401).json({ error: "unauthorized" });
}

function requireConnected(req, res, next) {
  if (connectionStatus !== "connected") {
    return res.status(503).json({ error: "whatsapp_not_connected", status: connectionStatus });
  }
  next();
}

app.get("/healthz", (req, res) => {
  res.json({ ok: true, status: connectionStatus });
});

app.get("/status", (req, res) => {
  res.json({
    status: connectionStatus,
    connected: connectionStatus === "connected",
    qr: qrCode,
    user: sock?.user
      ? { id: sock.user.id, name: sock.user.name || sock.user.verifiedName || "N/A" }
      : null,
  });
});

app.get("/qr", async (req, res) => {
  if (connectionStatus === "connected") {
    return res.send(`<!doctype html><html><body style="font-family:system-ui;padding:40px;text-align:center">
      <h1>WhatsApp conectado</h1>
      <p>Utilizador: <strong>${sock?.user?.id || "?"}</strong></p>
      <p>Nenhum QR code necessário.</p>
    </body></html>`);
  }
  if (!qrCode) {
    return res.send(`<!doctype html><html><head><meta http-equiv="refresh" content="2"></head>
      <body style="font-family:system-ui;padding:40px;text-align:center">
        <h1>A aguardar QR...</h1>
        <p>Estado: ${connectionStatus}</p>
      </body></html>`);
  }
  try {
    const dataUrl = await QRCode.toDataURL(qrCode, { errorCorrectionLevel: "M", width: 400 });
    res.send(`<!doctype html><html><head><meta http-equiv="refresh" content="15"></head>
      <body style="font-family:system-ui;padding:40px;text-align:center">
        <h1>Escaneia no WhatsApp</h1>
        <p>Abre WhatsApp → Definições → Dispositivos ligados → Ligar dispositivo</p>
        <img src="${dataUrl}" alt="QR" style="margin:20px auto;border:1px solid #ccc;padding:10px"/>
        <p style="color:#888">QR expira em ~60s. Página recarrega em 15s.</p>
      </body></html>`);
  } catch (err) {
    res.status(500).send(`Erro ao renderizar QR: ${err.message}`);
  }
});

app.get("/groups", requireAuth, requireConnected, async (req, res) => {
  try {
    const groups = await sock.groupFetchAllParticipating();
    const groupList = Object.values(groups).map((g) => {
      const cached = groupsCache[g.id] || {};
      return {
        id: g.id,
        name: g.subject || "Sem nome",
        participants: g.participants?.length || 0,
        creation: g.creation,
        desc: g.desc || "",
        is_archived: cached.archived === true,
        unread: cached.unreadCount ?? null,
      };
    });
    res.json({ groups: groupList, count: groupList.length });
  } catch (err) {
    console.error("[/groups]", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.get("/messages/:groupId", requireAuth, requireConnected, (req, res) => {
  const { groupId } = req.params;
  const count = parseInt(req.query.count) || 100;
  const sinceTs = parseInt(req.query.since) || 0;
  try {
    const stored = messageStore[groupId] || [];
    const messages = stored
      .filter((m) => getTimestamp(m) >= sinceTs)
      .slice(-count)
      .map(normalizeMessage);
    res.json({ messages, count: messages.length, group_id: groupId });
  } catch (err) {
    console.error("[/messages]", err.message);
    res.status(500).json({ error: err.message });
  }
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function chatModifyWithRetry(payload, groupId, maxAttempts = 4) {
  let lastErr;
  let rateLimited = false;
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    try {
      await sock.chatModify(payload, groupId);
      return { ok: true, attempt: attempt + 1 };
    } catch (err) {
      lastErr = err;
      const msg = err.message || "";
      if (msg.includes("rate-overlimit")) {
        rateLimited = true;
        if (attempt < maxAttempts - 1) {
          const backoff = 1500 * Math.pow(2, attempt) + Math.random() * 500;
          await sleep(backoff);
          continue;
        }
      }
      break;
    }
  }
  return { ok: false, error: lastErr?.message?.slice(0, 80), attempts: maxAttempts, rateLimited };
}

async function markGroupRead(groupId) {
  const stored = messageStore[groupId] || [];
  const unreadMsgs = stored.filter(
    (m) => m.key && !m.key.fromMe && m.key.id && m.key.remoteJid && m.key.participant
  );

  let readCount = 0;

  if (unreadMsgs.length > 0) {
    const byParticipant = {};
    for (const m of unreadMsgs) {
      const participant = m.key.participant;
      if (!byParticipant[participant]) byParticipant[participant] = [];
      byParticipant[participant].push(m.key.id);
    }
    for (const [participant, msgIds] of Object.entries(byParticipant)) {
      try {
        await sock.sendReceipt(groupId, participant, msgIds, "read");
        readCount += msgIds.length;
      } catch {
        try {
          await sock.sendReceipt(groupId, participant, msgIds, "read-self");
          readCount += msgIds.length;
        } catch (err2) {
          console.error(`[markRead receipt] ${groupId} p=${participant}: ${err2.message?.slice(0, 80)}`);
        }
      }
    }

    const lastMsgWithParticipant = [...unreadMsgs].reverse().find((m) => m.messageTimestamp);
    if (lastMsgWithParticipant) {
      const r = await chatModifyWithRetry(
        {
          markRead: true,
          lastMessages: [
            {
              key: lastMsgWithParticipant.key,
              messageTimestamp: lastMsgWithParticipant.messageTimestamp,
            },
          ],
        },
        groupId
      );
      if (r.ok) {
        console.log(`[markRead chatModify] ${groupId} OK (buffer, tries=${r.attempt})`);
      } else {
        console.log(`[markRead chatModify fail] ${groupId}: ${r.error}`);
      }
      return { markedRead: readCount > 0, count: readCount, path: "buffer", rateLimited: !r.ok && r.rateLimited };
    }

    return { markedRead: readCount > 0, count: readCount, path: "buffer" };
  }

  const r = await chatModifyWithRetry({ markRead: true }, groupId);
  if (r.ok) {
    console.log(`[markRead fallback] ${groupId} OK (no buffer, tries=${r.attempt})`);
    return { markedRead: true, count: 0, path: "fallback" };
  }
  console.log(`[markRead fallback fail] ${groupId}: ${r.error}`);
  return { markedRead: false, count: 0, path: "fallback_failed", reason: r.error, rateLimited: r.rateLimited };
}

app.patch("/groups/:groupId", requireAuth, requireConnected, async (req, res) => {
  const { groupId } = req.params;
  try {
    const r = await markGroupRead(groupId);
    if (r.markedRead) console.log(`[markRead] ${groupId} (${r.path}, ${r.count} msgs)`);
    res.json({ success: true, markedRead: r.markedRead, count: r.count, path: r.path });
  } catch (err) {
    console.error("[PATCH /groups]", err.message);
    res.status(500).json({ error: err.message });
  }
});

app.post("/resync", requireAuth, requireConnected, async (req, res) => {
  try {
    await sock.resyncAppState(
      ["regular_high", "regular_low", "critical_block", "critical_unblock_low"],
      false
    );
    res.json({ success: true });
  } catch (err) {
    res.json({ success: false, error: err.message });
  }
});

app.post("/logout", requireAuth, async (req, res) => {
  try {
    await sock?.logout();
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`\nimoIA WhatsApp Bridge na porta ${PORT}`);
  console.log(`DATA_DIR=${DATA_DIR}`);
  console.log(`AUTH=${BRIDGE_TOKEN ? "exigido (BRIDGE_TOKEN set)" : "aberto"}`);
  console.log("A iniciar conexão WhatsApp...\n");
  startWhatsApp();
});
