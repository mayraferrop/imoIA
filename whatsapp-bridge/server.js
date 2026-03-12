/**
 * ImoScout WhatsApp Bridge
 *
 * Servidor Express local que expoe a API do WhatsApp via Baileys.
 * O Python (ImoScout) chama http://localhost:3000 em vez de Whapi.Cloud.
 *
 * Endpoints:
 *   GET  /status           — estado da conexao + QR code
 *   GET  /groups            — listar grupos
 *   GET  /messages/:groupId — mensagens de um grupo
 *   PATCH /groups/:groupId  — arquivar grupo
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

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_DIR = path.join(__dirname, "auth_state");
const MSG_STORE_FILE = path.join(__dirname, "messages.json");

// Logger do Baileys (silent por defeito, usar BAILEYS_LOG=debug para diagnostico)
const logger = pino({ level: process.env.BAILEYS_LOG || "silent" });

// Buffer de mensagens em memoria (groupId -> array de mensagens)
const messageStore = {};
const MAX_MESSAGES_PER_GROUP = 500;

// Carregar mensagens guardadas
if (fs.existsSync(MSG_STORE_FILE)) {
  try {
    const saved = JSON.parse(fs.readFileSync(MSG_STORE_FILE, "utf-8"));
    Object.assign(messageStore, saved);
    console.log(`Mensagens carregadas: ${Object.keys(saved).length} grupos`);
  } catch {
    console.log("Ficheiro de mensagens corrompido, a comecar do zero.");
  }
}

// Guardar mensagens a cada 60 segundos
setInterval(() => {
  try {
    fs.writeFileSync(MSG_STORE_FILE, JSON.stringify(messageStore), "utf-8");
  } catch (err) {
    console.error("Erro ao guardar mensagens:", err.message);
  }
}, 60_000);

// Estado global
let sock = null;
let qrCode = null;
let connectionStatus = "disconnected";

/**
 * Extrai conteudo de texto e tipo de uma mensagem Baileys.
 */
function extractContent(msg) {
  const m = msg.message;
  if (!m) return { content: "", type: "unknown" };

  if (m.conversation) {
    return { content: m.conversation, type: "text" };
  }
  if (m.extendedTextMessage?.text) {
    return { content: m.extendedTextMessage.text, type: "text" };
  }
  if (m.imageMessage?.caption) {
    return { content: m.imageMessage.caption, type: "image" };
  }
  if (m.videoMessage?.caption) {
    return { content: m.videoMessage.caption, type: "video" };
  }
  if (m.documentMessage) return { content: "", type: "document" };
  if (m.stickerMessage) return { content: "", type: "sticker" };
  if (m.reactionMessage) return { content: "", type: "reaction" };
  if (m.protocolMessage) return { content: "", type: "protocol" };

  return { content: "", type: "unknown" };
}

/**
 * Converte timestamp do Baileys para numero unix.
 */
function getTimestamp(msg) {
  const ts = msg.messageTimestamp;
  if (!ts) return 0;
  if (typeof ts === "object") return ts.low || 0;
  return Number(ts);
}

/**
 * Normaliza uma mensagem Baileys para o formato da API.
 */
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

/**
 * Inicia a conexao com o WhatsApp via Baileys.
 */
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

  // Capturar mensagens recebidas e guardar no buffer
  sock.ev.on("messages.upsert", ({ messages: msgs, type }) => {
    let count = 0;
    for (const msg of msgs) {
      const groupId = msg.key?.remoteJid;
      if (!groupId || !groupId.endsWith("@g.us")) continue;

      if (!messageStore[groupId]) {
        messageStore[groupId] = [];
      }

      // Evitar duplicados (pelo id da mensagem)
      const msgId = msg.key?.id;
      if (msgId && messageStore[groupId].some((m) => m.key?.id === msgId)) {
        continue;
      }

      messageStore[groupId].push(msg);
      count++;

      // Limitar tamanho do buffer
      if (messageStore[groupId].length > MAX_MESSAGES_PER_GROUP) {
        messageStore[groupId] = messageStore[groupId].slice(
          -MAX_MESSAGES_PER_GROUP
        );
      }
    }
    if (count > 0) {
      console.log(`[messages.upsert] +${count} mensagens de grupo (type: ${type})`);
    }
  });

  // Capturar historico sincronizado pelo WhatsApp
  sock.ev.on("messaging-history.set", ({ messages: msgs, isLatest }) => {
    let count = 0;
    for (const msg of (msgs || [])) {
      const groupId = msg.key?.remoteJid;
      if (!groupId || !groupId.endsWith("@g.us")) continue;

      if (!messageStore[groupId]) {
        messageStore[groupId] = [];
      }

      const msgId = msg.key?.id;
      if (msgId && messageStore[groupId].some((m) => m.key?.id === msgId)) {
        continue;
      }

      messageStore[groupId].push(msg);
      count++;

      if (messageStore[groupId].length > MAX_MESSAGES_PER_GROUP) {
        messageStore[groupId] = messageStore[groupId].slice(
          -MAX_MESSAGES_PER_GROUP
        );
      }
    }
    console.log(`[history.set] +${count} mensagens de grupo sincronizadas (isLatest: ${isLatest})`);
  });

  // Eventos de conexao
  sock.ev.on("connection.update", async (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      qrCode = qr;
      connectionStatus = "waiting_qr";
      console.log("\n");
      console.log("=".repeat(50));
      console.log("  SCAN DO QR CODE NO WHATSAPP");
      console.log("  Ou aceda a http://localhost:3000/status");
      console.log("=".repeat(50));

      // Mostrar QR no terminal
      try {
        const qrcodeTerminal = await import("qrcode-terminal");
        qrcodeTerminal.default.generate(qr, { small: true });
      } catch {
        console.log("QR Code:", qr);
      }
    }

    if (connection === "close") {
      connectionStatus = "disconnected";
      qrCode = null;

      const reason = new Boom(lastDisconnect?.error)?.output?.statusCode;

      if (reason === DisconnectReason.loggedOut) {
        console.log("Sessao terminada. Apague a pasta auth_state e reinicie.");
        // Limpar auth state
        if (fs.existsSync(AUTH_DIR)) {
          fs.rmSync(AUTH_DIR, { recursive: true });
        }
        process.exit(1);
      }

      // Reconnect automatico
      console.log("Conexao perdida. A reconectar em 3 segundos...");
      setTimeout(startWhatsApp, 3000);
    }

    if (connection === "open") {
      connectionStatus = "connected";
      qrCode = null;
      console.log("\n");
      console.log("=".repeat(50));
      console.log("  WhatsApp conectado com sucesso!");
      console.log("  API disponivel em http://localhost:3000");
      console.log("=".repeat(50));
      console.log("\n");
    }
  });

  // Guardar credenciais quando atualizadas
  sock.ev.on("creds.update", saveCreds);
}

// ---------------------------------------------------------------------------
// Express API
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json());

// CORS para o Streamlit
app.use((req, res, next) => {
  res.header("Access-Control-Allow-Origin", "*");
  res.header("Access-Control-Allow-Methods", "GET, PATCH, POST, OPTIONS");
  res.header("Access-Control-Allow-Headers", "Content-Type, Authorization");
  if (req.method === "OPTIONS") return res.sendStatus(200);
  next();
});

/**
 * GET /status
 * Estado da conexao e QR code (se disponivel).
 */
app.get("/status", (req, res) => {
  res.json({
    status: connectionStatus,
    qr: qrCode,
    connected: connectionStatus === "connected",
    user: sock?.user
      ? {
          id: sock.user.id,
          name: sock.user.name || sock.user.verifiedName || "N/A",
        }
      : null,
  });
});

/**
 * GET /groups
 * Lista todos os grupos do WhatsApp.
 */
app.get("/groups", async (req, res) => {
  if (connectionStatus !== "connected") {
    return res.status(503).json({ error: "WhatsApp nao conectado" });
  }

  try {
    const groups = await sock.groupFetchAllParticipating();
    const groupList = Object.values(groups).map((g) => ({
      id: g.id,
      name: g.subject || "Sem nome",
      participants: g.participants?.length || 0,
      creation: g.creation,
      desc: g.desc || "",
    }));

    res.json({ groups: groupList, count: groupList.length });
  } catch (err) {
    console.error("Erro ao listar grupos:", err.message);
    res.status(500).json({ error: err.message });
  }
});

/**
 * GET /messages/:groupId
 * Busca mensagens de um grupo a partir do buffer local.
 * Query params:
 *   - count: numero maximo de mensagens (default 100)
 *   - since: timestamp unix (segundos) para filtrar mensagens mais recentes
 */
app.get("/messages/:groupId", async (req, res) => {
  if (connectionStatus !== "connected") {
    return res.status(503).json({ error: "WhatsApp nao conectado" });
  }

  const { groupId } = req.params;
  const count = parseInt(req.query.count) || 100;
  const sinceTs = parseInt(req.query.since) || 0;

  try {
    const stored = messageStore[groupId] || [];

    const messages = stored
      .filter((m) => getTimestamp(m) >= sinceTs)
      .slice(-count)
      .map(normalizeMessage);

    res.json({
      messages,
      count: messages.length,
      group_id: groupId,
    });
  } catch (err) {
    console.error("Erro ao buscar mensagens:", err.message);
    res.status(500).json({ error: err.message });
  }
});

/**
 * PATCH /groups/:groupId
 * Marcar como lido e arquivar grupo.
 * Body: { "archive": true }
 *
 * Usa readMessages (protocolo direto) para marcar como lido.
 * Usa chatModify para archive (requer app state sync keys).
 */
app.patch("/groups/:groupId", async (req, res) => {
  if (connectionStatus !== "connected") {
    return res.status(503).json({ error: "WhatsApp nao conectado" });
  }

  const { groupId } = req.params;
  const { archive } = req.body;
  const results = { markedRead: false, archived: false };

  try {
    const stored = messageStore[groupId] || [];

    // Marcar TODAS as mensagens como lidas via sendReceipts (protocolo direto)
    // Agrupar por participant para enviar receipts em batch
    const unreadMsgs = stored.filter((m) => m.key && !m.key.fromMe && m.key.id && m.key.remoteJid);

    if (unreadMsgs.length > 0) {
      // Agrupar mensagens por participant
      const byParticipant = {};
      for (const m of unreadMsgs) {
        const participant = m.key.participant || "";
        if (!byParticipant[participant]) byParticipant[participant] = [];
        byParticipant[participant].push(m.key.id);
      }

      let readCount = 0;
      for (const [participant, msgIds] of Object.entries(byParticipant)) {
        try {
          // Enviar 'read' diretamente (nao 'read-self') para garantir que limpa badges
          await sock.sendReceipt(groupId, participant || undefined, msgIds, "read");
          readCount += msgIds.length;
        } catch (err) {
          // Tentar com read-self como fallback
          try {
            await sock.sendReceipt(groupId, participant || undefined, msgIds, "read-self");
            readCount += msgIds.length;
          } catch (err2) {
            console.error(`[markRead] Erro ${groupId} participant=${participant}:`, err2.message);
          }
        }
      }

      if (readCount > 0) {
        results.markedRead = true;
        console.log(`[markRead] ${readCount} msgs lidas em ${groupId}`);
      }
    }

    // Tentar arquivar via chatModify (pode falhar se sync keys corrompidas)
    if (archive) {
      const lastMsg = stored.length > 0 ? stored[stored.length - 1] : null;
      if (lastMsg && lastMsg.key?.id && lastMsg.key?.remoteJid && lastMsg.messageTimestamp) {
        try {
          await sock.chatModify(
            { archive: true, lastMessages: [{ key: lastMsg.key, messageTimestamp: lastMsg.messageTimestamp }] },
            groupId
          );
          results.archived = true;
          console.log(`[archive] ${groupId} arquivado`);
        } catch (archErr) {
          // App state sync pode estar corrompido - nao bloquear
          console.log(`[archive] ${groupId} falhou (app state): ${archErr.message?.slice(0, 80)}`);
        }
      }
    }

    res.json({ success: true, ...results });
  } catch (err) {
    console.error("Erro geral ao processar grupo:", err.message);
    res.status(500).json({ error: err.message, partial: results });
  }
});

/**
 * POST /resync
 * Forca resincronizacao do app state com o WhatsApp.
 */
app.post("/resync", async (req, res) => {
  if (connectionStatus !== "connected") {
    return res.status(503).json({ error: "WhatsApp nao conectado" });
  }

  try {
    console.log("[resync] A forcar resincronizacao do app state...");
    await sock.resyncAppState(["regular_high", "regular_low", "critical_block", "critical_unblock_low"], false);
    console.log("[resync] Resincronizacao concluida");
    res.json({ success: true });
  } catch (err) {
    console.error("[resync] Erro:", err.message);
    res.json({ success: false, error: err.message });
  }
});

/**
 * POST /debug/read/:groupId
 * Debug: tenta multiplas abordagens para marcar como lido/arquivar.
 */
app.post("/debug/read/:groupId", async (req, res) => {
  if (connectionStatus !== "connected") {
    return res.status(503).json({ error: "WhatsApp nao conectado" });
  }

  const { groupId } = req.params;
  const stored = messageStore[groupId] || [];
  const log = [];

  log.push(`Store has ${stored.length} msgs for ${groupId}`);

  if (stored.length === 0) {
    return res.json({ success: false, log, error: "No messages in store" });
  }

  const lastMsg = stored[stored.length - 1];
  log.push(`Last msg key: ${JSON.stringify(lastMsg.key)}`);

  // Approach 1: readMessages with original LID keys
  const unread = stored.filter((m) => m.key && !m.key.fromMe).slice(-5);
  log.push(`--- Approach 1: readMessages with LID keys (${unread.length} msgs) ---`);
  try {
    await sock.readMessages(unread.map((m) => m.key));
    log.push(`  => OK`);
  } catch (err) {
    log.push(`  => ERROR: ${err.message}`);
  }

  // Approach 2: readMessages with phone number keys (participantPn -> participant)
  log.push(`--- Approach 2: readMessages with phone keys ---`);
  const phoneKeys = unread
    .filter((m) => m.key.participantPn)
    .map((m) => ({
      remoteJid: m.key.remoteJid,
      fromMe: m.key.fromMe,
      id: m.key.id,
      participant: m.key.participantPn,
    }));
  log.push(`  Keys with participantPn: ${phoneKeys.length}`);
  if (phoneKeys.length > 0) {
    try {
      await sock.readMessages(phoneKeys);
      log.push(`  => OK`);
    } catch (err) {
      log.push(`  => ERROR: ${err.message}`);
    }
  }

  // Approach 3: sendReceipt directly with phone participant
  log.push(`--- Approach 3: sendReceipt directly ---`);
  const lastUnread = unread[unread.length - 1];
  if (lastUnread) {
    const participant = lastUnread.key.participantPn || lastUnread.key.participant;
    const msgIds = unread.map((m) => m.key.id);
    try {
      await sock.sendReceipt(groupId, participant, msgIds, "read");
      log.push(`  sendReceipt(read) with ${participant} => OK`);
    } catch (err) {
      log.push(`  sendReceipt(read) => ERROR: ${err.message}`);
    }
    try {
      await sock.sendReceipt(groupId, participant, msgIds, "read-self");
      log.push(`  sendReceipt(read-self) with ${participant} => OK`);
    } catch (err) {
      log.push(`  sendReceipt(read-self) => ERROR: ${err.message}`);
    }
  }

  // Approach 4: chatModify markRead
  log.push(`--- Approach 4: chatModify markRead ---`);
  const cleanKey = {
    remoteJid: lastMsg.key.remoteJid,
    fromMe: lastMsg.key.fromMe,
    id: lastMsg.key.id,
    participant: lastMsg.key.participant,
  };
  try {
    await sock.chatModify(
      { markRead: true, lastMessages: [{ key: cleanKey, messageTimestamp: lastMsg.messageTimestamp }] },
      groupId
    );
    log.push(`  => OK`);
  } catch (err) {
    log.push(`  => ERROR: ${err.message}`);
  }

  // Approach 5: chatModify markRead with phone participant
  log.push(`--- Approach 5: chatModify markRead with phone participant ---`);
  if (lastMsg.key.participantPn) {
    const phoneKey = {
      remoteJid: lastMsg.key.remoteJid,
      fromMe: lastMsg.key.fromMe,
      id: lastMsg.key.id,
      participant: lastMsg.key.participantPn,
    };
    try {
      await sock.chatModify(
        { markRead: true, lastMessages: [{ key: phoneKey, messageTimestamp: lastMsg.messageTimestamp }] },
        groupId
      );
      log.push(`  => OK`);
    } catch (err) {
      log.push(`  => ERROR: ${err.message}`);
    }
  } else {
    log.push(`  => SKIP (no participantPn)`);
  }

  // Approach 6: chatModify archive
  log.push(`--- Approach 6: chatModify archive ---`);
  try {
    await sock.chatModify(
      { archive: true, lastMessages: [{ key: cleanKey, messageTimestamp: lastMsg.messageTimestamp }] },
      groupId
    );
    log.push(`  => OK`);
  } catch (err) {
    log.push(`  => ERROR: ${err.message}`);
  }

  res.json({ success: true, log });
});

/**
 * POST /logout
 * Desconecta a sessao do WhatsApp.
 */
app.post("/logout", async (req, res) => {
  try {
    await sock?.logout();
    res.json({ success: true });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------------------------------------------------------------------------
// Iniciar
// ---------------------------------------------------------------------------

const PORT = process.env.BRIDGE_PORT || 3000;

app.listen(PORT, () => {
  console.log(`\nImoScout WhatsApp Bridge a correr na porta ${PORT}`);
  console.log("A iniciar conexao com o WhatsApp...\n");
  startWhatsApp();
});
