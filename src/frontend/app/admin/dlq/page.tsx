"use client";

import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/lib/auth-context";
import { API_BASE, getAuthHeaders } from "@/lib/api";

const DLQ_KEY = "/api/v1/ingest/dlq?limit=200";

interface DLQEntry {
  id: number;
  group_id: string;
  group_name: string | null;
  whatsapp_message_id: string;
  content: string;
  sender_name: string | null;
  message_timestamp: string | null;
  reason: string;
  retry_count: number;
  next_retry_at: string;
  last_error: string | null;
  created_at: string;
}

interface DLQResponse {
  rows: DLQEntry[];
  counts: {
    pending: number;
    exhausted: number;
  };
}

const fetcher = async (url: string) => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}${url}`, { headers });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("pt-PT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelative(iso: string): string {
  const d = new Date(iso).getTime();
  const now = Date.now();
  const diffMs = d - now;
  const mins = Math.round(diffMs / 60_000);
  if (mins < -60) return `ha ${Math.abs(Math.round(mins / 60))}h`;
  if (mins < 0) return `ha ${Math.abs(mins)}m`;
  if (mins < 60) return `em ${mins}m`;
  return `em ${Math.round(mins / 60)}h`;
}

function reasonBadge(reason: string): { label: string; cls: string } {
  switch (reason) {
    case "over_classify_limit":
      return { label: "Overflow", cls: "bg-amber-100 text-amber-800" };
    case "save_failed":
      return { label: "Save falhou", cls: "bg-red-100 text-red-800" };
    default:
      return { label: reason, cls: "bg-slate-100 text-slate-600" };
  }
}

export default function DLQPage() {
  const { activeOrg } = useAuth();
  const isAdmin = activeOrg?.role === "admin" || activeOrg?.role === "owner";
  const [deleting, setDeleting] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);

  const { data, error, isLoading, mutate } = useSWR<DLQResponse>(
    isAdmin ? DLQ_KEY : null,
    fetcher,
    { refreshInterval: 30_000 }
  );

  if (!isAdmin) {
    return (
      <div className="p-8 text-center">
        <p className="text-sm text-slate-500">
          Apenas administradores tem acesso a esta pagina.
        </p>
      </div>
    );
  }

  async function handleDelete(id: number) {
    if (!confirm(`Remover entrada #${id} da DLQ? A mensagem nao volta a ser tentada.`)) return;
    setDeleting(id);
    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/ingest/dlq/${id}`, {
        method: "DELETE",
        headers,
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await mutate();
    } catch (e) {
      alert(`Erro ao remover: ${e}`);
    } finally {
      setDeleting(null);
    }
  }

  return (
    <div className="p-6 max-w-7xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 mb-1">
            Dead-letter Queue
          </h1>
          <p className="text-sm text-slate-500">
            Mensagens que excederam o limite de classificacao ou falharam
            save/classify. Retry automatico com backoff exponencial (15m, 30m,
            60m, 120m, 240m).
          </p>
        </div>
        <button
          onClick={() => mutate()}
          className="px-3 py-1.5 text-sm border border-slate-200 rounded-lg hover:bg-slate-50 transition-colors"
        >
          Atualizar
        </button>
      </div>

      {error && (
        <div className="p-4 mb-4 bg-red-50 border border-red-200 rounded-lg">
          <p className="text-sm text-red-700">
            Erro ao carregar: {String(error.message ?? error)}
          </p>
        </div>
      )}

      {data && (
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div className="border border-slate-200 rounded-lg p-3 bg-white">
            <p className="text-xs text-slate-500 mb-1">Pendentes (retry &lt; 5)</p>
            <p className="text-lg font-semibold text-slate-900">{data.counts.pending}</p>
          </div>
          <div className="border border-slate-200 rounded-lg p-3 bg-white">
            <p className="text-xs text-slate-500 mb-1">Esgotadas (retry &ge; 5)</p>
            <p className="text-lg font-semibold text-red-700">{data.counts.exhausted}</p>
          </div>
        </div>
      )}

      {isLoading && (
        <div className="p-8 text-center text-sm text-slate-500">A carregar...</div>
      )}

      {data && data.rows.length === 0 && (
        <div className="p-8 text-center bg-white border border-slate-200 rounded-lg">
          <p className="text-sm text-slate-500">
            Queue vazia. Nenhuma mensagem em retry — o pipeline esta a
            processar tudo dentro do limite.
          </p>
        </div>
      )}

      {data && data.rows.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Grupo</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Razao</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Tentativas</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Proximo retry</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Criado</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600"></th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => {
                const badge = reasonBadge(r.reason);
                const isOpen = expanded === r.id;
                return (
                  <>
                    <tr
                      key={r.id}
                      className="border-b border-slate-100 hover:bg-slate-50 transition-colors cursor-pointer"
                      onClick={() => setExpanded(isOpen ? null : r.id)}
                    >
                      <td className="px-4 py-3 text-slate-700 truncate max-w-[240px]" title={r.group_name ?? r.group_id}>
                        {r.group_name ?? r.group_id}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${badge.cls}`}>
                          {badge.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right text-slate-700">
                        {r.retry_count}/5
                      </td>
                      <td className="px-4 py-3 text-slate-600 text-xs">
                        {formatRelative(r.next_retry_at)}
                        <span className="text-slate-400 ml-1">
                          ({formatDate(r.next_retry_at)})
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-600 text-xs">
                        {formatDate(r.created_at)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(r.id);
                          }}
                          disabled={deleting === r.id}
                          className="text-xs text-red-600 hover:text-red-800 disabled:opacity-50"
                        >
                          {deleting === r.id ? "..." : "remover"}
                        </button>
                      </td>
                    </tr>
                    {isOpen && (
                      <tr className="bg-slate-50 border-b border-slate-100">
                        <td colSpan={6} className="px-4 py-3">
                          <div className="space-y-2 text-xs">
                            <div>
                              <span className="font-medium text-slate-600">Mensagem:</span>
                              <p className="text-slate-700 mt-1 whitespace-pre-wrap break-words">
                                {r.content || "(vazio)"}
                              </p>
                            </div>
                            <div className="flex gap-4">
                              <div>
                                <span className="font-medium text-slate-600">Sender:</span>{" "}
                                <span className="text-slate-700">{r.sender_name ?? "—"}</span>
                              </div>
                              <div>
                                <span className="font-medium text-slate-600">WA ID:</span>{" "}
                                <span className="text-slate-700 font-mono">{r.whatsapp_message_id}</span>
                              </div>
                              <div>
                                <span className="font-medium text-slate-600">Timestamp msg:</span>{" "}
                                <span className="text-slate-700">{formatDate(r.message_timestamp)}</span>
                              </div>
                            </div>
                            {r.last_error && (
                              <div>
                                <span className="font-medium text-red-700">Ultimo erro:</span>
                                <p className="text-red-700 mt-1 font-mono">{r.last_error}</p>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
