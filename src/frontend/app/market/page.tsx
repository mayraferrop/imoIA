"use client";

import { useEffect, useState, useCallback } from "react";
import { formatEUR } from "@/lib/utils";
import { supabaseGet } from "@/lib/supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

/* ------------------------------------------------------------------ */
/*  Tipos locais                                                       */
/* ------------------------------------------------------------------ */

interface MarketOverview {
  casafari_search_access?: boolean;
  casafari_configured?: boolean;
  comparables_cached?: number;
  valuations_total?: number;
  alerts_active?: number;
  zones_monitored?: number;
  comparables_casafari?: number;
  comparables_ine?: number;
}

interface MarketAlert {
  id: string;
  alert_name: string;
  alert_type: string;
  districts?: string[];
  property_types?: string[];
  price_max?: number;
  is_active?: boolean;
  total_triggers?: number;
}

interface Comparable {
  municipality?: string;
  parish?: string;
  property_type?: string;
  bedrooms?: number;
  listing_price?: number;
  price_per_m2?: number;
  gross_area_m2?: number;
  condition?: string;
  comparison_type?: string;
}

interface ComparablesResult {
  comparables: Comparable[];
  stats?: {
    count?: number;
    median_price_m2?: number;
    min_price_m2?: number;
    max_price_m2?: number;
  };
}

interface ValuationResult {
  estimated_value?: number;
  estimated_value_low?: number;
  estimated_value_high?: number;
  confidence_score?: number;
  estimated_price_per_m2?: number;
  comparables_count?: number;
}

interface INEResult {
  municipality?: string;
  price_m2?: number;
  quarter?: string;
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

/* ------------------------------------------------------------------ */
/*  Componentes reutilizáveis                                          */
/* ------------------------------------------------------------------ */

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-bold text-slate-900 mt-1">{value}</p>
    </div>
  );
}

function Field({
  name,
  label,
  placeholder,
  type = "text",
  defaultValue,
  children,
}: {
  name: string;
  label: string;
  placeholder?: string;
  type?: string;
  defaultValue?: string | number;
  children?: React.ReactNode;
}) {
  if (children) {
    return (
      <div>
        <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
        {children}
      </div>
    );
  }
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      <input
        name={name}
        type={type}
        placeholder={placeholder}
        defaultValue={defaultValue}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
      />
    </div>
  );
}

function Select({
  name,
  label,
  options,
  defaultValue,
}: {
  name: string;
  label: string;
  options: { value: string; label: string }[];
  defaultValue?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      <select
        name={name}
        defaultValue={defaultValue}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none bg-white"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function Badge({
  children,
  variant = "info",
}: {
  children: React.ReactNode;
  variant?: "success" | "warning" | "error" | "info";
}) {
  const colors = {
    success: "bg-green-100 text-green-700",
    warning: "bg-amber-100 text-amber-700",
    error: "bg-red-100 text-red-700",
    info: "bg-slate-100 text-slate-700",
  };
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${colors[variant]}`}>
      {children}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Tabs                                                               */
/* ------------------------------------------------------------------ */

const TABS = [
  { id: "comparables", label: "Comparáveis" },
  { id: "valuation", label: "Avaliação AVM" },
  { id: "alerts", label: "Alertas" },
  { id: "ine", label: "Dados INE" },
] as const;

type TabId = (typeof TABS)[number]["id"];

/* ================================================================== */
/*  PAGE                                                               */
/* ================================================================== */

export default function MarketPage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("comparables");
  const [loading, setLoading] = useState(false);

  // Comparables
  const [comparables, setComparables] = useState<Comparable[]>([]);
  const [compStats, setCompStats] = useState<ComparablesResult["stats"] | null>(null);

  // Valuation
  const [valuation, setValuation] = useState<ValuationResult | null>(null);

  // Alerts
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);

  // INE
  const [ineResult, setIneResult] = useState<INEResult | null>(null);

  /* --- Load overview + alerts on mount --- */
  const loadData = useCallback(async () => {
    // PRIMARY: Load alerts from Supabase (instant, no cold start)
    const supaAlerts = await supabaseGet<MarketAlert>("market_alerts", "select=*&order=created_at.desc");

    if (supaAlerts.length > 0) {
      setAlerts(supaAlerts);
      // Build a basic overview from Supabase data
      const activeAlerts = supaAlerts.filter((a) => a.is_active !== false);
      setOverview((prev) => ({
        ...prev,
        alerts_active: activeAlerts.length,
      }));
    }

    // Also try to get full overview from FastAPI (has CASAFARI status etc.)
    const ov = await api<MarketOverview>("/api/v1/market/overview");
    if (ov) setOverview(ov);

    // FALLBACK: If Supabase returned nothing, try FastAPI for alerts
    if (supaAlerts.length === 0) {
      const al = await api<MarketAlert[]>("/api/v1/market/alerts");
      if (al) setAlerts(Array.isArray(al) ? al : []);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  /* --- Comparables search (always FastAPI — needs CASAFARI) --- */
  async function handleSearchComparables(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const result = await api<ComparablesResult>("/api/v1/market/comparables/search", {
      method: "POST",
      body: JSON.stringify({
        municipality: fd.get("municipality") || "Lisboa",
        property_type: fd.get("property_type") || "apartamento",
        bedrooms: Number(fd.get("bedrooms") || 2),
        area_m2: Number(fd.get("area_m2") || 80),
        max_results: Number(fd.get("max_results") || 20),
        months_back: Number(fd.get("months_back") || 12),
      }),
    });
    if (result) {
      setComparables(result.comparables ?? []);
      setCompStats(result.stats ?? null);
    }
    setLoading(false);
  }

  /* --- Valuation (always FastAPI — needs CASAFARI) --- */
  async function handleValuate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const result = await api<ValuationResult>("/api/v1/market/valuate", {
      method: "POST",
      body: JSON.stringify({
        municipality: fd.get("v_municipality") || "Lisboa",
        property_type: fd.get("v_property_type") || "apartamento",
        bedrooms: Number(fd.get("v_bedrooms") || 2),
        gross_area_m2: Number(fd.get("v_area") || 80),
        condition: fd.get("v_condition") || "usado",
      }),
    });
    if (result) setValuation(result);
    setLoading(false);
  }

  /* --- Create alert (FastAPI — needs business logic) --- */
  async function handleCreateAlert(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const districts = (fd.get("al_districts") as string)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const propertyTypes = (fd.get("al_property_types") as string)
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const priceMax = Number(fd.get("al_price_max") || 0);

    await api("/api/v1/market/alerts", {
      method: "POST",
      body: JSON.stringify({
        alert_name: fd.get("al_name"),
        alert_type: fd.get("al_type"),
        districts,
        property_types: propertyTypes,
        price_max: priceMax > 0 ? priceMax : null,
      }),
    });
    e.currentTarget.reset();
    await loadData();
    setLoading(false);
  }

  /* --- Delete alert (FastAPI) --- */
  async function handleDeleteAlert(id: string) {
    await api(`/api/v1/market/alerts/${id}`, { method: "DELETE" });
    setConfirmDelete(null);
    await loadData();
  }

  /* --- Check alerts (FastAPI — needs CASAFARI) --- */
  async function handleCheckAlerts() {
    setLoading(true);
    await api("/api/v1/market/alerts/check", { method: "POST" });
    await loadData();
    setLoading(false);
  }

  /* --- INE (FastAPI — external API call) --- */
  async function handleINE(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    const fd = new FormData(e.currentTarget);
    const mun = fd.get("ine_municipality") || "Lisboa";
    const result = await api<INEResult>(`/api/v1/market/ine/housing-prices?municipality=${mun}`);
    if (result) setIneResult(result);
    setLoading(false);
  }

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */

  const propertyTypeOptions = [
    { value: "apartamento", label: "Apartamento" },
    { value: "moradia", label: "Moradia" },
    { value: "terreno", label: "Terreno" },
    { value: "predio", label: "Prédio" },
    { value: "armazem", label: "Armazém" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-slate-900">M2 — Pesquisa de Mercado</h1>
        <p className="text-sm text-slate-500 mt-1">
          Comparáveis, avaliações AVM, alertas e dados INE
        </p>
      </div>

      {/* CASAFARI status */}
      {overview && (
        <div
          className={`rounded-lg px-4 py-3 text-sm font-medium ${
            overview.casafari_search_access
              ? "bg-green-50 text-green-700 border border-green-200"
              : overview.casafari_configured
              ? "bg-amber-50 text-amber-700 border border-amber-200"
              : "bg-slate-50 text-slate-600 border border-slate-200"
          }`}
        >
          {overview.casafari_search_access
            ? "CASAFARI API activa — pesquisa de comparáveis em tempo real."
            : overview.casafari_configured
            ? "CASAFARI: login OK mas sem acesso a pesquisa (HTTP 402). A usar dados INE como alternativa."
            : "CASAFARI não configurada. Dados INE disponíveis."}
        </div>
      )}

      {/* KPIs */}
      {overview && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard label="Comparáveis em cache" value={overview.comparables_cached ?? 0} />
          <StatCard label="Avaliações feitas" value={overview.valuations_total ?? 0} />
          <StatCard label="Alertas activos" value={overview.alerts_active ?? 0} />
          <StatCard label="Zonas monitorizadas" value={overview.zones_monitored ?? 0} />
          <StatCard
            label="Fontes (CASAFARI / INE)"
            value={`${overview.comparables_casafari ?? 0} / ${overview.comparables_ine ?? 0}`}
          />
        </div>
      )}

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-1 -mb-px">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? "border-teal-700 text-teal-700"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* ============================================================ */}
      {/*  TAB: Comparáveis                                             */}
      {/* ============================================================ */}
      {activeTab === "comparables" && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Pesquisar comparáveis</h2>
            <form onSubmit={handleSearchComparables} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Field name="municipality" label="Município" placeholder="Lisboa" defaultValue="Lisboa" />
                <Select name="property_type" label="Tipo" options={propertyTypeOptions} defaultValue="apartamento" />
                <Field name="bedrooms" label="Quartos" type="number" placeholder="2" defaultValue={2} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Field name="area_m2" label="Área m2" type="number" placeholder="80" defaultValue={80} />
                <Field name="max_results" label="Max resultados" type="number" placeholder="20" defaultValue={20} />
                <Field name="months_back" label="Meses atrás" type="number" placeholder="12" defaultValue={12} />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="bg-teal-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
              >
                {loading ? "A pesquisar..." : "Pesquisar"}
              </button>
            </form>
          </div>

          {/* Stats */}
          {compStats && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatCard label="Total" value={compStats.count ?? 0} />
              <StatCard label="Mediana EUR/m2" value={compStats.median_price_m2?.toLocaleString("pt-PT") ?? "—"} />
              <StatCard label="Min EUR/m2" value={compStats.min_price_m2?.toLocaleString("pt-PT") ?? "—"} />
              <StatCard label="Max EUR/m2" value={compStats.max_price_m2?.toLocaleString("pt-PT") ?? "—"} />
            </div>
          )}

          {/* Comparables table */}
          {comparables.length > 0 && (
            <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-slate-600">
                    <tr>
                      <th className="text-left px-4 py-3 font-medium">Município</th>
                      <th className="text-left px-4 py-3 font-medium">Freguesia</th>
                      <th className="text-left px-4 py-3 font-medium">Tipo</th>
                      <th className="text-right px-4 py-3 font-medium">Quartos</th>
                      <th className="text-right px-4 py-3 font-medium">Preço</th>
                      <th className="text-right px-4 py-3 font-medium">EUR/m2</th>
                      <th className="text-right px-4 py-3 font-medium">Área m2</th>
                      <th className="text-left px-4 py-3 font-medium">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {comparables.map((c, i) => (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-3">{c.municipality ?? "—"}</td>
                        <td className="px-4 py-3">{c.parish ?? "—"}</td>
                        <td className="px-4 py-3">{c.property_type ?? "—"}</td>
                        <td className="px-4 py-3 text-right">{c.bedrooms ?? "—"}</td>
                        <td className="px-4 py-3 text-right">{c.listing_price ? formatEUR(c.listing_price) : "—"}</td>
                        <td className="px-4 py-3 text-right">
                          {c.price_per_m2 ? c.price_per_m2.toLocaleString("pt-PT") : "—"}
                        </td>
                        <td className="px-4 py-3 text-right">
                          {c.gross_area_m2 ? `${c.gross_area_m2.toFixed(0)}` : "—"}
                        </td>
                        <td className="px-4 py-3">{c.condition ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/*  TAB: Avaliação AVM                                           */}
      {/* ============================================================ */}
      {activeTab === "valuation" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Avaliação AVM</h2>
            <form onSubmit={handleValuate} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Field name="v_municipality" label="Município" placeholder="Lisboa" defaultValue="Lisboa" />
                <Select name="v_property_type" label="Tipo" options={propertyTypeOptions} defaultValue="apartamento" />
                <Field name="v_bedrooms" label="Quartos" type="number" placeholder="2" defaultValue={2} />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field name="v_area" label="Área m2" type="number" placeholder="80" defaultValue={80} />
                <Select
                  name="v_condition"
                  label="Estado"
                  options={[
                    { value: "usado", label: "Usado" },
                    { value: "renovado", label: "Renovado" },
                    { value: "novo", label: "Novo" },
                    { value: "para_renovar", label: "Para renovar" },
                  ]}
                  defaultValue="usado"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="bg-teal-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
              >
                {loading ? "A avaliar..." : "Avaliar"}
              </button>
            </form>
          </div>

          {valuation && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <h2 className="text-lg font-semibold mb-4">Resultado</h2>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500">Valor estimado</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {valuation.estimated_value ? formatEUR(valuation.estimated_value) : "—"}
                  </p>
                </div>
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500">EUR/m2</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {valuation.estimated_price_per_m2?.toLocaleString("pt-PT") ?? "—"}
                  </p>
                </div>
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500">Confiança</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {valuation.confidence_score != null ? `${valuation.confidence_score.toFixed(0)}%` : "—"}
                  </p>
                </div>
                <div className="bg-slate-50 rounded-lg p-4">
                  <p className="text-xs text-slate-500">Comparáveis usados</p>
                  <p className="text-xl font-bold text-slate-900 mt-1">
                    {valuation.comparables_count ?? "—"}
                  </p>
                </div>
              </div>
              {valuation.estimated_value_low && valuation.estimated_value_high && (
                <div className="mt-4 bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-sm text-blue-700">
                  Intervalo: {formatEUR(valuation.estimated_value_low)} — {formatEUR(valuation.estimated_value_high)}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ============================================================ */}
      {/*  TAB: Alertas                                                 */}
      {/* ============================================================ */}
      {activeTab === "alerts" && (
        <div className="space-y-6">
          {/* Create alert form */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold mb-4">Novo alerta</h2>
            <form onSubmit={handleCreateAlert} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Field name="al_name" label="Nome" placeholder="Apartamentos Lisboa abaixo mercado" />
                <Select
                  name="al_type"
                  label="Tipo"
                  options={[
                    { value: "new_listing", label: "Novo anúncio" },
                    { value: "price_drop", label: "Descida de preço" },
                    { value: "below_market", label: "Abaixo mercado" },
                  ]}
                  defaultValue="new_listing"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Field
                  name="al_districts"
                  label="Distritos (separados por vírgula)"
                  placeholder="Lisboa, Porto, Setúbal"
                />
                <Field
                  name="al_property_types"
                  label="Tipos imóvel (separados por vírgula)"
                  placeholder="apartamento, moradia"
                />
                <Field name="al_price_max" label="Preço máximo EUR" type="number" placeholder="0" defaultValue={0} />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="bg-teal-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
              >
                {loading ? "A criar..." : "Criar alerta"}
              </button>
            </form>
          </div>

          {/* Alerts list */}
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Alertas activos</h2>
              <button
                onClick={handleCheckAlerts}
                disabled={loading}
                className="text-sm text-teal-700 hover:text-teal-800 font-medium disabled:opacity-50"
              >
                Verificar agora
              </button>
            </div>

            {alerts.length === 0 ? (
              <p className="text-sm text-slate-500">Nenhum alerta. Cria um acima.</p>
            ) : (
              <div className="space-y-3">
                {alerts.map((a) => (
                  <div
                    key={a.id}
                    className="flex items-center justify-between border border-slate-100 rounded-lg px-4 py-3"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span
                          className={`w-2 h-2 rounded-full flex-shrink-0 ${
                            a.is_active ? "bg-green-500" : "bg-slate-300"
                          }`}
                        />
                        <span className="font-medium text-sm text-slate-900 truncate">
                          {a.alert_name}
                        </span>
                        <Badge>{a.alert_type}</Badge>
                      </div>
                      <p className="text-xs text-slate-500 mt-1 ml-4">
                        {a.districts?.join(", ") || "Todas as zonas"} — Disparou{" "}
                        {a.total_triggers ?? 0}x
                      </p>
                    </div>
                    <div className="flex-shrink-0 ml-4">
                      {confirmDelete === a.id ? (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleDeleteAlert(a.id)}
                            className="text-xs bg-red-600 text-white px-3 py-1.5 rounded-lg hover:bg-red-700"
                          >
                            Confirmar
                          </button>
                          <button
                            onClick={() => setConfirmDelete(null)}
                            className="text-xs bg-slate-200 text-slate-700 px-3 py-1.5 rounded-lg hover:bg-slate-300"
                          >
                            Cancelar
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDelete(a.id)}
                          className="text-xs text-red-600 hover:text-red-700 font-medium"
                        >
                          Apagar
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/*  TAB: Dados INE                                               */}
      {/* ============================================================ */}
      {activeTab === "ine" && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-lg font-semibold mb-1">Preços medianos INE</h2>
            <p className="text-sm text-slate-500 mb-4">
              Instituto Nacional de Estatística — sem API key.
            </p>
            <form onSubmit={handleINE} className="flex gap-4 items-end">
              <div className="flex-1">
                <Field name="ine_municipality" label="Município" placeholder="Lisboa" defaultValue="Lisboa" />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="bg-teal-700 text-white px-6 py-2.5 rounded-lg font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
              >
                {loading ? "A consultar..." : "Consultar"}
              </button>
            </form>
          </div>

          {ineResult && (
            <div className="bg-white rounded-xl border border-slate-200 p-6">
              <p className="text-xs text-slate-500">
                Mediana {ineResult.municipality}
                {ineResult.quarter && ` — Período: ${ineResult.quarter}`} | Fonte: INE
              </p>
              <p className="text-3xl font-bold text-slate-900 mt-2">
                {ineResult.price_m2?.toLocaleString("pt-PT") ?? "—"} EUR/m2
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
