/**
 * Storage SQLite para mensagens do bridge.
 *
 * Substitui messages.json (objecto em memoria + persist a cada 60s) por
 * gravacao transaccional e imediata. Elimina janela de perda de ate 60s
 * quando o processo cai entre writes.
 *
 * Schema:
 *   messages(group_id, msg_id, ts, from_me, raw) — PK (group_id, msg_id)
 *   meta(key, value)                              — contadores e flags
 *
 * API compativel com o hook existente:
 *   saveMessage(msg)            — insere (ou ignora se duplicado)
 *   getMessages(groupId, sinceTs, count) — devolve ordenadas asc
 *   getKeysForMarkRead(groupId) — keys de mensagens nao-proprias
 *   countByGroup()              — map groupId -> count (para boot log)
 *   migrateFromJson(jsonPath)   — importa messages.json legado (one-shot)
 */

import Database from "better-sqlite3";
import fs from "fs";
import path from "path";

let db = null;

export function initStore(dbPath) {
  const dir = path.dirname(dbPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

  db = new Database(dbPath);
  db.pragma("journal_mode = WAL");
  db.pragma("synchronous = NORMAL");
  db.pragma("foreign_keys = ON");

  db.exec(`
    CREATE TABLE IF NOT EXISTS messages (
      group_id   TEXT    NOT NULL,
      msg_id     TEXT    NOT NULL,
      ts         INTEGER NOT NULL,
      from_me    INTEGER NOT NULL DEFAULT 0,
      raw        TEXT    NOT NULL,
      PRIMARY KEY (group_id, msg_id)
    );
    CREATE INDEX IF NOT EXISTS idx_messages_group_ts
      ON messages(group_id, ts DESC);

    CREATE TABLE IF NOT EXISTS meta (
      key   TEXT PRIMARY KEY,
      value TEXT
    );
  `);

  return db;
}

function getTs(msg) {
  const ts = msg.messageTimestamp;
  if (!ts) return 0;
  if (typeof ts === "object") return ts.low || 0;
  return Number(ts);
}

const _insertStmt = () =>
  db.prepare(`
    INSERT OR IGNORE INTO messages (group_id, msg_id, ts, from_me, raw)
    VALUES (@group_id, @msg_id, @ts, @from_me, @raw)
  `);

export function saveMessage(msg) {
  const groupId = msg.key?.remoteJid;
  const msgId = msg.key?.id;
  if (!groupId || !msgId || !groupId.endsWith("@g.us")) return false;

  const row = {
    group_id: groupId,
    msg_id: msgId,
    ts: getTs(msg),
    from_me: msg.key?.fromMe ? 1 : 0,
    raw: JSON.stringify(msg),
  };
  const info = _insertStmt().run(row);
  return info.changes > 0;
}

export function saveMessagesBatch(msgs) {
  const stmt = _insertStmt();
  const tx = db.transaction((items) => {
    let n = 0;
    for (const m of items) {
      const groupId = m.key?.remoteJid;
      const msgId = m.key?.id;
      if (!groupId || !msgId || !groupId.endsWith("@g.us")) continue;
      const info = stmt.run({
        group_id: groupId,
        msg_id: msgId,
        ts: getTs(m),
        from_me: m.key?.fromMe ? 1 : 0,
        raw: JSON.stringify(m),
      });
      if (info.changes > 0) n++;
    }
    return n;
  });
  return tx(msgs);
}

const _queryStmt = () =>
  db.prepare(`
    SELECT raw FROM messages
    WHERE group_id = ? AND ts >= ?
    ORDER BY ts ASC
    LIMIT ?
  `);

export function getMessages(groupId, sinceTs, count) {
  const rows = _queryStmt().all(groupId, sinceTs || 0, count || 100);
  return rows.map((r) => JSON.parse(r.raw));
}

const _keysStmt = () =>
  db.prepare(`
    SELECT raw FROM messages
    WHERE group_id = ? AND from_me = 0
    ORDER BY ts DESC
    LIMIT ?
  `);

export function getKeysForMarkRead(groupId, limit = 500) {
  const rows = _keysStmt().all(groupId, limit);
  return rows
    .map((r) => JSON.parse(r.raw))
    .filter((m) => m.key && m.key.id && m.key.remoteJid)
    .map((m) => ({
      remoteJid: m.key.remoteJid,
      id: m.key.id,
      participant: m.key.participant,
      fromMe: false,
    }));
}

export function countByGroup() {
  const rows = db.prepare(`
    SELECT group_id, COUNT(*) as n FROM messages GROUP BY group_id
  `).all();
  return rows.reduce((acc, r) => { acc[r.group_id] = r.n; return acc; }, {});
}

export function totalCount() {
  const row = db.prepare("SELECT COUNT(*) as n FROM messages").get();
  return row?.n || 0;
}

export function pruneGroup(groupId, keepLast) {
  const stmt = db.prepare(`
    DELETE FROM messages
    WHERE group_id = ? AND msg_id NOT IN (
      SELECT msg_id FROM messages
      WHERE group_id = ?
      ORDER BY ts DESC
      LIMIT ?
    )
  `);
  const info = stmt.run(groupId, groupId, keepLast);
  return info.changes;
}

export function migrateFromJson(jsonPath) {
  if (!fs.existsSync(jsonPath)) return { migrated: 0, skipped: "no_file" };
  const already = db.prepare("SELECT value FROM meta WHERE key = 'migrated_from_json'").get();
  if (already) return { migrated: 0, skipped: "already_migrated" };

  let raw;
  try {
    raw = JSON.parse(fs.readFileSync(jsonPath, "utf-8"));
  } catch (e) {
    return { migrated: 0, skipped: `parse_error: ${e.message}` };
  }

  let total = 0;
  for (const [groupId, msgs] of Object.entries(raw)) {
    if (!Array.isArray(msgs)) continue;
    total += saveMessagesBatch(msgs);
  }

  db.prepare("INSERT INTO meta (key, value) VALUES (?, ?)")
    .run("migrated_from_json", new Date().toISOString());

  return { migrated: total };
}

export function close() {
  if (db) { db.close(); db = null; }
}
