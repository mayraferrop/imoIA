"use client";

import { useEffect, useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

/* ------------------------------------------------------------------ */
/*  Tipos locais                                                       */
/* ------------------------------------------------------------------ */

interface Deal {
  id: string;
  title?: string;
  status?: string;
  property_id?: string;
}

interface DDItem {
  id: string;
  item_name: string;
  category: string;
  status: string;
  is_required?: boolean;
  description?: string;
  red_flag?: boolean;
  red_flag_severity?: string;
  red_flag_description?: string;
  document_url?: string;
}

interface DDChecklist {
  total_items: number;
  completed: number;
  pending: number;
  red_flags: number;
  progress_pct: number;
  estimated_cost?: number;
  items_by_category?: Record<string, DDItem[]>;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

async function api<T = any>(path: string, opts?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...opts,
    });
    if (!res.ok) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : ({} as T);
  } catch {
    return null;
  }
}

const STATUS_ICONS: Record<string, string> = {
  pendente: "[ ]",
  em_curso: "[~]",
  obtido: "[ok]",
  problema: "[!]",
  na: "[-]",
};

const STATUS_COLORS: Record<string, string> = {
  pendente: "bg-slate-100 text-slate-600",
  em_curso: "bg-blue-100 text-blue-700",
  obtido: "bg-green-100 text-green-700",
  problema: "bg-amber-100 text-amber-700",
  na: "bg-slate-100 text-slate-400",
};

const SEVERITY_COLORS: Record<string, string> = {
  low: "text-yellow-600",
  medium: "text-orange-500",
  high: "text-red-500",
  critical: "text-red-700",
};

const CATEGORY_LABELS: Record<string, string> = {
  registos: "Registos",
  fiscal: "Fiscal",
  licenciamento: "Licenciamento",
  condominio: "Condominio",
  servicos: "Servicos",
  urbano: "Urbanismo",
  tecnico: "Tecnico",
  judicial: "Judicial",
  trabalhista: "Trabalhista",
};

const STATUS_OPTIONS = ["pendente", "em_curso", "obtido", "problema", "na"];

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */

export default function DueDiligencePage() {
  const [deals, setDeals] = useState<Deal[]>([]);
  const [selectedDealId, setSelectedDealId] = useState<string | null>(null);
  const [checklist, setChecklist] = useState<DDChecklist | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);

  /* --- Load deals --- */
  useEffect(() => {
    (async () => {
      const data = await api<{ items: Deal[] }>("/api/v1/deals?limit=50");
      if (data?.items) {
        const active = data.items.filter(
          (d) => d.status !== "descartado" && d.status !== "fechado"
        );
        setDeals(active);
      }
    })();
  }, []);

  /* --- Load checklist when deal selected --- */
  const loadChecklist = useCallback(async (dealId: string) => {
    setLoading(true);
    const data = await api<DDChecklist>(
      `/api/v1/due-diligence/deals/${dealId}/checklist`
    );
    setChecklist(data);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (selectedDealId) loadChecklist(selectedDealId);
  }, [selectedDealId, loadChecklist]);

  /* --- Update item status --- */
  async function handleStatusChange(itemId: string, newStatus: string) {
    await api(`/api/v1/due-diligence/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ status: newStatus }),
    });
    if (selectedDealId) loadChecklist(selectedDealId);
  }

  /* --- Generate checklist --- */
  async function handleGenerate() {
    if (!selectedDealId) return;
    setGenerating(true);
    await api(`/api/v1/due-diligence/deals/${selectedDealId}/generate`, {
      method: "POST",
    });
    await loadChecklist(selectedDealId);
    setGenerating(false);
  }

  /* --- Add red flag --- */
  async function handleAddRedFlag(itemId: string) {
    const description = prompt("Descricao da red flag:");
    if (!description) return;
    const severity = prompt("Severidade (low, medium, high, critical):", "medium");
    await api(`/api/v1/due-diligence/items/${itemId}/red-flag`, {
      method: "POST",
      body: JSON.stringify({
        red_flag: true,
        red_flag_description: description,
        red_flag_severity: severity || "medium",
      }),
    });
    if (selectedDealId) loadChecklist(selectedDealId);
  }

  /* --- Resolve red flag --- */
  async function handleResolveRedFlag(itemId: string) {
    await api(`/api/v1/due-diligence/items/${itemId}`, {
      method: "PATCH",
      body: JSON.stringify({ red_flag: false, red_flag_description: null }),
    });
    if (selectedDealId) loadChecklist(selectedDealId);
  }

  /* --- Upload document --- */
  async function handleUpload(itemId: string) {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf,.jpg,.jpeg,.png,.doc,.docx";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await fetch(
          `${API_BASE}/api/v1/due-diligence/items/${itemId}/upload`,
          { method: "POST", body: formData }
        );
        if (res.ok && selectedDealId) loadChecklist(selectedDealId);
      } catch {
        // ignore
      }
    };
    input.click();
  }

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  const categories = checklist?.items_by_category ?? {};
  const hasItems = checklist && checklist.total_items > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">M5 — Due Diligence</h1>
        <p className="text-sm text-slate-500 mt-1">
          Checklists, red flags e documentos por deal
        </p>
      </div>

      {/* No deals */}
      {deals.length === 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
          <h3 className="text-lg font-semibold text-slate-600">Sem deals activos</h3>
          <p className="text-sm text-slate-400 mt-1">
            Cria um deal no M4 — Deal Pipeline para iniciar due diligence.
          </p>
        </div>
      )}

      {/* Deal selector */}
      {deals.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Seleccionar deal ({deals.length} activos)
          </label>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {deals.map((d) => (
              <button
                key={d.id}
                onClick={() => setSelectedDealId(d.id)}
                className={`text-left px-4 py-3 rounded-lg border transition-colors ${
                  selectedDealId === d.id
                    ? "border-teal-700 bg-teal-50 ring-1 ring-teal-700"
                    : "border-slate-200 hover:border-slate-300 bg-white"
                }`}
              >
                <p className="text-sm font-medium text-slate-900 truncate">
                  {d.title || `Deal #${d.id.slice(0, 8)}`}
                </p>
                <p className="text-xs text-slate-500 mt-0.5">{d.status ?? "—"}</p>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && selectedDealId && (
        <div className="bg-white rounded-xl border border-slate-200 p-8 text-center">
          <p className="text-sm text-slate-500">A carregar checklist...</p>
        </div>
      )}

      {/* Checklist content */}
      {selectedDealId && !loading && (
        <>
          {/* KPIs */}
          {hasItems && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs text-slate-500">Progresso</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {checklist!.progress_pct.toFixed(0)}%
                  </p>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs text-slate-500">Obtidos</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {checklist!.completed}/{checklist!.total_items}
                  </p>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs text-slate-500">Pendentes</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {checklist!.pending}
                  </p>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs text-slate-500">Red Flags</p>
                  <p className={`text-xl font-bold mt-1 ${checklist!.red_flags > 0 ? "text-red-600" : "text-slate-900"}`}>
                    {checklist!.red_flags}
                  </p>
                </div>
                <div className="bg-white rounded-xl border border-slate-200 p-4">
                  <p className="text-xs text-slate-500">Custo estimado</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {checklist!.estimated_cost != null
                      ? new Intl.NumberFormat("pt-PT", {
                          style: "currency",
                          currency: "EUR",
                          maximumFractionDigits: 0,
                        }).format(checklist!.estimated_cost)
                      : "—"}
                  </p>
                </div>
              </div>

              {/* Progress bar */}
              <div className="bg-white rounded-xl border border-slate-200 p-4">
                <div className="w-full bg-slate-200 rounded-full h-3">
                  <div
                    className="bg-teal-700 h-3 rounded-full transition-all"
                    style={{ width: `${Math.min(checklist!.progress_pct, 100)}%` }}
                  />
                </div>
              </div>

              {/* Items by category */}
              <div className="space-y-4">
                {Object.entries(categories).map(([catKey, catItems]) => {
                  const doneCount = catItems.filter(
                    (i) => i.status === "obtido" || i.status === "na"
                  ).length;
                  const catLabel = CATEGORY_LABELS[catKey] ?? catKey.charAt(0).toUpperCase() + catKey.slice(1);

                  return (
                    <details
                      key={catKey}
                      className="bg-white rounded-xl border border-slate-200 overflow-hidden group"
                    >
                      <summary className="px-6 py-4 cursor-pointer flex items-center justify-between hover:bg-slate-50">
                        <span className="font-medium text-slate-900">
                          {catLabel}
                        </span>
                        <span className="text-sm text-slate-500">
                          {doneCount}/{catItems.length}
                        </span>
                      </summary>
                      <div className="border-t border-slate-100 divide-y divide-slate-50">
                        {catItems.map((item) => (
                          <div
                            key={item.id}
                            className="px-6 py-4 flex items-start gap-4"
                          >
                            {/* Status badge */}
                            <span
                              className={`flex-shrink-0 mt-0.5 px-2 py-0.5 rounded text-xs font-medium ${
                                STATUS_COLORS[item.status] ?? STATUS_COLORS.pendente
                              }`}
                            >
                              {STATUS_ICONS[item.status] ?? "?"} {item.status}
                            </span>

                            {/* Item info */}
                            <div className="flex-1 min-w-0">
                              <p className="text-sm font-medium text-slate-900">
                                {item.item_name}
                                {item.is_required && (
                                  <span className="text-red-500 ml-1">*</span>
                                )}
                              </p>
                              {item.description && (
                                <p className="text-xs text-slate-500 mt-0.5 line-clamp-2">
                                  {item.description}
                                </p>
                              )}
                              {/* Red flag */}
                              {item.red_flag && (
                                <div className="mt-2 flex items-center gap-2">
                                  <span
                                    className={`text-xs font-bold ${
                                      SEVERITY_COLORS[item.red_flag_severity ?? "medium"]
                                    }`}
                                  >
                                    [{(item.red_flag_severity ?? "medium").toUpperCase()}]
                                  </span>
                                  <span className="text-xs text-slate-700">
                                    {item.red_flag_description}
                                  </span>
                                  <button
                                    onClick={() => handleResolveRedFlag(item.id)}
                                    className="text-xs text-green-600 hover:text-green-700 font-medium ml-2"
                                  >
                                    Resolver
                                  </button>
                                </div>
                              )}
                              {/* Document link */}
                              {item.document_url && (
                                <a
                                  href={`${API_BASE}${item.document_url}`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-teal-700 hover:text-teal-800 mt-1 inline-block"
                                >
                                  Ver documento
                                </a>
                              )}
                            </div>

                            {/* Actions */}
                            <div className="flex-shrink-0 flex items-center gap-2">
                              {/* Status selector */}
                              <select
                                value={item.status}
                                onChange={(e) =>
                                  handleStatusChange(item.id, e.target.value)
                                }
                                className="text-xs border border-slate-300 rounded-lg px-2 py-1.5 bg-white focus:ring-1 focus:ring-teal-500 outline-none"
                              >
                                {STATUS_OPTIONS.map((s) => (
                                  <option key={s} value={s}>
                                    {s}
                                  </option>
                                ))}
                              </select>

                              {/* Upload button */}
                              {!item.document_url &&
                                item.status !== "obtido" &&
                                item.status !== "na" && (
                                  <button
                                    onClick={() => handleUpload(item.id)}
                                    className="text-xs text-teal-700 hover:text-teal-800 font-medium"
                                  >
                                    Upload
                                  </button>
                                )}

                              {/* Red flag button */}
                              {!item.red_flag && (
                                <button
                                  onClick={() => handleAddRedFlag(item.id)}
                                  className="text-xs text-red-500 hover:text-red-600 font-medium"
                                  title="Adicionar red flag"
                                >
                                  Flag
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                  );
                })}
              </div>
            </div>
          )}

          {/* No checklist — generate */}
          {!hasItems && !loading && (
            <div className="bg-white rounded-xl border border-slate-200 p-12 text-center">
              <h3 className="text-lg font-semibold text-slate-600">
                Sem checklist de due diligence
              </h3>
              <p className="text-sm text-slate-400 mt-1 mb-6">
                O checklist e gerado automaticamente quando o deal avanca para o estado
                &ldquo;Due Diligence&rdquo;. Pode tambem gerar manualmente.
              </p>
              <button
                onClick={handleGenerate}
                disabled={generating}
                className="bg-teal-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
              >
                {generating ? "A gerar..." : "Gerar checklist"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
