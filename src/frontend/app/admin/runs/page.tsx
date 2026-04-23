"use client";

import { useState } from "react";
import useSWR from "swr";
import { useAuth } from "@/lib/auth-context";
import { API_BASE, getAuthHeaders } from "@/lib/api";

const RUNS_KEY = "/api/v1/ingest/runs?limit=50";

interface PipelineRunSummary {
  id: number;
  started_at: string;
  finished_at: string;
  duration_sec: number;
  messages_fetched: number;
  messages_filtered: number;
  opportunities_found: number;
  groups_processed: number;
  groups_with_unread: number;
  groups_archived: number;
  groups_to_archive: number;
  errors_count: number;
  phases_duration: Record<string, number> | null;
  trigger_source: string | null;
  created_at: string;
}

interface GroupLog {
  grupo: string;
  grupo_id: string;
  processado_em: string;
  mensagens_buscadas: number;
  mensagens_filtradas: number;
  oportunidades: number;
  estado?: string;
  erro?: string | null;
  unread_before?: number;
  unread_after?: number | null;
}

interface PipelineRunDetail extends PipelineRunSummary {
  errors: string[] | null;
  group_logs: GroupLog[] | null;
}

const fetcher = async (url: string) => {
  const headers = await getAuthHeaders();
  const res = await fetch(`${API_BASE}${url}`, { headers });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("pt-PT", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatDuration(sec: number): string {
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}m ${s}s`;
}

function triggerBadge(source: string | null): { label: string; cls: string } {
  switch (source) {
    case "cron":
      return { label: "Cron", cls: "bg-indigo-100 text-indigo-800" };
    case "api":
      return { label: "API", cls: "bg-teal-100 text-teal-800" };
    case "manual":
      return { label: "Manual", cls: "bg-amber-100 text-amber-800" };
    default:
      return { label: source ?? "—", cls: "bg-slate-100 text-slate-600" };
  }
}

export default function PipelineRunsPage() {
  const { activeOrg } = useAuth();
  const isAdmin = activeOrg?.role === "admin" || activeOrg?.role === "owner";

  const { data: runs, error, isLoading, mutate } = useSWR<PipelineRunSummary[]>(
    isAdmin ? RUNS_KEY : null,
    fetcher,
    { refreshInterval: 30_000 }
  );

  const [selectedId, setSelectedId] = useState<number | null>(null);
  const { data: detail, isLoading: detailLoading } = useSWR<PipelineRunDetail>(
    selectedId ? `/api/v1/ingest/runs/${selectedId}` : null,
    fetcher
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

  return (
    <div className="p-6 max-w-7xl">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-slate-900 mb-1">
            Execucoes do Pipeline
          </h1>
          <p className="text-sm text-slate-500">
            Historico das ultimas 50 execucoes do pipeline M1. Actualiza
            automaticamente a cada 30s.
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

      {isLoading && (
        <div className="p-8 text-center text-sm text-slate-500">
          A carregar...
        </div>
      )}

      {runs && runs.length === 0 && (
        <div className="p-8 text-center bg-white border border-slate-200 rounded-lg">
          <p className="text-sm text-slate-500">
            Nenhuma execucao registada ainda. O pipeline vai gravar aqui
            assim que correr.
          </p>
        </div>
      )}

      {runs && runs.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Inicio</th>
                <th className="text-left px-4 py-3 font-medium text-slate-600">Trigger</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Duracao</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Mensagens</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Oportunidades</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Grupos unread</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Mark-as-read</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600">Erros</th>
                <th className="text-right px-4 py-3 font-medium text-slate-600"></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => {
                const badge = triggerBadge(r.trigger_source);
                return (
                  <tr
                    key={r.id}
                    className="border-b border-slate-100 hover:bg-slate-50 transition-colors cursor-pointer"
                    onClick={() => setSelectedId(r.id)}
                  >
                    <td className="px-4 py-3 text-slate-700">{formatDate(r.started_at)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${badge.cls}`}>
                        {badge.label}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">{formatDuration(r.duration_sec)}</td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {r.messages_fetched}
                      {r.messages_filtered > 0 && (
                        <span className="text-xs text-slate-400 ml-1">({r.messages_filtered})</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right font-medium text-slate-900">{r.opportunities_found}</td>
                    <td className="px-4 py-3 text-right text-slate-700">{r.groups_with_unread}</td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      {r.groups_archived}
                      {r.groups_to_archive > 0 && (
                        <span className="text-xs text-slate-400">/{r.groups_to_archive}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {r.errors_count > 0 ? (
                        <span className="inline-block px-2 py-0.5 bg-red-100 text-red-800 rounded text-xs font-medium">
                          {r.errors_count}
                        </span>
                      ) : (
                        <span className="text-slate-400">0</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="text-teal-600 text-xs">detalhes →</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Drawer de detalhe */}
      {selectedId && (
        <div
          className="fixed inset-0 bg-black/40 z-40"
          onClick={() => setSelectedId(null)}
        >
          <div
            className="absolute right-0 top-0 bottom-0 w-full max-w-2xl bg-white shadow-xl overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6 border-b border-slate-200 flex items-start justify-between sticky top-0 bg-white z-10">
              <div>
                <h2 className="text-lg font-bold text-slate-900">
                  Execucao #{selectedId}
                </h2>
                {detail && (
                  <p className="text-xs text-slate-500 mt-1">
                    {formatDate(detail.started_at)} → {formatDate(detail.finished_at)}
                  </p>
                )}
              </div>
              <button
                onClick={() => setSelectedId(null)}
                className="text-slate-400 hover:text-slate-900 text-xl leading-none"
              >
                ×
              </button>
            </div>

            {detailLoading && (
              <div className="p-6 text-sm text-slate-500">A carregar detalhe...</div>
            )}

            {detail && (
              <div className="p-6 space-y-6">
                {/* Metricas gerais */}
                <div className="grid grid-cols-2 gap-3">
                  <Metric label="Duracao total" value={formatDuration(detail.duration_sec)} />
                  <Metric label="Trigger" value={triggerBadge(detail.trigger_source).label} />
                  <Metric label="Mensagens buscadas" value={String(detail.messages_fetched)} />
                  <Metric label="Mensagens apos filtro" value={String(detail.messages_filtered)} />
                  <Metric label="Oportunidades" value={String(detail.opportunities_found)} highlight />
                  <Metric label="Grupos processados" value={String(detail.groups_processed)} />
                  <Metric label="Grupos com unread" value={String(detail.groups_with_unread)} />
                  <Metric
                    label="Mark-as-read"
                    value={`${detail.groups_archived}/${detail.groups_to_archive}`}
                  />
                </div>

                {/* Duracao por fase */}
                {detail.phases_duration && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-700 mb-2">
                      Duracao por fase
                    </h3>
                    <div className="space-y-1">
                      {Object.entries(detail.phases_duration).map(([k, v]) => (
                        <div key={k} className="flex justify-between text-sm">
                          <span className="text-slate-600">{k}</span>
                          <span className="font-mono text-slate-900">{Number(v).toFixed(1)}s</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Erros */}
                {detail.errors && detail.errors.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-red-700 mb-2">
                      Erros ({detail.errors.length})
                    </h3>
                    <ul className="space-y-1 bg-red-50 border border-red-200 rounded-lg p-3">
                      {detail.errors.map((e, i) => (
                        <li key={i} className="text-xs text-red-700 font-mono break-all">
                          {e}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Group logs */}
                {detail.group_logs && detail.group_logs.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-slate-700 mb-2">
                      Grupos processados ({detail.group_logs.length})
                    </h3>
                    <div className="border border-slate-200 rounded-lg overflow-hidden">
                      <table className="w-full text-xs">
                        <thead className="bg-slate-50">
                          <tr>
                            <th className="text-left px-3 py-2 font-medium text-slate-600">Grupo</th>
                            <th className="text-right px-3 py-2 font-medium text-slate-600">Msgs</th>
                            <th className="text-right px-3 py-2 font-medium text-slate-600">Filtradas</th>
                            <th className="text-right px-3 py-2 font-medium text-slate-600">Opps</th>
                            <th className="text-left px-3 py-2 font-medium text-slate-600">Estado</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.group_logs
                            .filter((g) => g.mensagens_buscadas > 0 || g.erro)
                            .slice(0, 100)
                            .map((g, i) => (
                              <tr key={i} className="border-t border-slate-100">
                                <td className="px-3 py-2 text-slate-700 truncate max-w-[200px]" title={g.grupo}>
                                  {g.grupo}
                                </td>
                                <td className="px-3 py-2 text-right text-slate-700">{g.mensagens_buscadas}</td>
                                <td className="px-3 py-2 text-right text-slate-700">{g.mensagens_filtradas}</td>
                                <td className="px-3 py-2 text-right font-medium text-slate-900">{g.oportunidades}</td>
                                <td className="px-3 py-2">
                                  {g.erro ? (
                                    <span className="text-red-600" title={g.erro}>
                                      erro
                                    </span>
                                  ) : (
                                    <span className="text-slate-500">{g.estado || "ok"}</span>
                                  )}
                                </td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div className="border border-slate-200 rounded-lg p-3">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-lg font-semibold ${highlight ? "text-teal-700" : "text-slate-900"}`}>
        {value}
      </p>
    </div>
  );
}
