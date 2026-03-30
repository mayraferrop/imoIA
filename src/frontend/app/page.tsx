"use client";

import { useState, useEffect } from "react";
import { formatEUR, GRADE_COLORS } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://jurzdyncaxkgvcatyfdu.supabase.co";
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp1cnpkeW5jYXhrZ3ZjYXR5ZmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNzM2MDcsImV4cCI6MjA4OTk0OTYwN30.2DCCWcrhdwBLMxJ9hUbYkhOBQIgE_aD2jGNaZlAhO5k";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

const GRADE_ORDER = ["A", "B", "C", "D", "F"];
const SUPA_HEADERS = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
};

interface Property {
  id: string;
  source: string;
  source_opportunity_id?: number;
  district?: string;
  municipality: string;
  parish?: string;
  property_type?: string;
  typology?: string;
  gross_area_m2?: number;
  asking_price?: number;
  condition?: string;
  status?: string;
  created_at: string;
  // Enriched from opportunities table
  deal_grade?: string;
  deal_score?: number;
  confidence?: number;
  opportunity_type?: string;
}

interface Opportunity {
  id: number;
  deal_grade?: string;
  deal_score?: number;
  confidence?: number;
  opportunity_type?: string;
  municipality?: string;
  district?: string;
  price_mentioned?: number;
  area_m2?: number;
  is_opportunity?: boolean;
}

interface DealStats {
  total_active?: number;
  total_pipeline_value?: number;
  total_completed?: number;
}

async function fetchSupabaseProperties(): Promise<Property[]> {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/properties?select=id,source,source_opportunity_id,district,municipality,parish,property_type,typology,gross_area_m2,asking_price,condition,status,created_at&order=created_at.desc`,
    { headers: SUPA_HEADERS }
  );
  if (!res.ok) throw new Error("Supabase fetch failed");
  return res.json();
}

async function fetchSupabaseOpportunities(): Promise<Opportunity[]> {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/opportunities?select=id,deal_grade,deal_score,confidence,opportunity_type,municipality,district,price_mentioned,area_m2,is_opportunity&is_opportunity=eq.true&order=deal_score.desc.nullslast`,
    { headers: SUPA_HEADERS }
  );
  if (!res.ok) return [];
  return res.json();
}

async function fetchDealStats(): Promise<DealStats> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const res = await fetch(`${API_BASE}/api/v1/deals/stats`, {
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) return {};
    return res.json();
  } catch {
    return {};
  }
}

function enrichProperties(properties: Property[], opportunities: Opportunity[]): Property[] {
  const oppMap = new Map<number, Opportunity>();
  for (const opp of opportunities) {
    oppMap.set(opp.id, opp);
  }
  return properties.map((p) => {
    if (p.source_opportunity_id && oppMap.has(p.source_opportunity_id)) {
      const opp = oppMap.get(p.source_opportunity_id)!;
      return {
        ...p,
        deal_grade: opp.deal_grade,
        deal_score: opp.deal_score,
        confidence: opp.confidence,
        opportunity_type: opp.opportunity_type,
      };
    }
    return p;
  });
}

export default function DashboardPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [dealStats, setDealStats] = useState<DealStats>({});
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<"supabase" | "fastapi" | "offline">("supabase");

  useEffect(() => {
    async function load() {
      setLoading(true);

      let props: Property[] = [];
      let opps: Opportunity[] = [];
      try {
        [props, opps] = await Promise.all([
          fetchSupabaseProperties(),
          fetchSupabaseOpportunities(),
        ]);
        props = enrichProperties(props, opps);
        setDataSource("supabase");
      } catch {
        try {
          const controller = new AbortController();
          const timeout = setTimeout(() => controller.abort(), 8000);
          const res = await fetch(`${API_BASE}/api/v1/properties/?limit=500`, {
            signal: controller.signal,
          });
          clearTimeout(timeout);
          if (res.ok) {
            const data = await res.json();
            props = data.items ?? [];
          }
          setDataSource("fastapi");
        } catch {
          setDataSource("offline");
        }
      }
      setProperties(props);
      setOpportunities(opps);

      const stats = await fetchDealStats();
      setDealStats(stats);

      setLoading(false);
    }
    load();
  }, []);

  // --- Computed chart data ---

  // Grade distribution (from enriched properties + standalone opportunities)
  const gradeCounts: Record<string, number> = {};
  // Count from enriched properties
  properties.forEach((p) => {
    if (p.deal_grade) {
      gradeCounts[p.deal_grade] = (gradeCounts[p.deal_grade] || 0) + 1;
    }
  });
  // Add standalone opportunities not linked to properties
  const linkedOppIds = new Set(properties.map((p) => p.source_opportunity_id).filter(Boolean));
  opportunities.forEach((opp) => {
    if (!linkedOppIds.has(opp.id) && opp.deal_grade) {
      gradeCounts[opp.deal_grade] = (gradeCounts[opp.deal_grade] || 0) + 1;
    }
  });
  const gradeData = GRADE_ORDER.filter((g) => gradeCounts[g])
    .map((g) => ({
      grade: g,
      count: gradeCounts[g] || 0,
      color: GRADE_COLORS[g] || GRADE_COLORS.D,
    }));

  // Top 10 municipalities
  const muniCounts: Record<string, number> = {};
  properties.forEach((p) => {
    if (p.municipality) {
      muniCounts[p.municipality] = (muniCounts[p.municipality] || 0) + 1;
    }
  });
  const topMunicipalities = Object.entries(muniCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .map(([name, count]) => ({ name, count }));

  // Opportunity types pie chart
  const OPP_TYPE_LABELS: Record<string, string> = {
    abaixo_mercado: "Abaixo Mercado",
    venda_urgente: "Venda Urgente",
    off_market: "Off-Market",
    reabilitacao: "Reabilitação",
    leilao: "Leilão",
    predio_inteiro: "Prédio Inteiro",
    terreno_viabilidade: "Terreno c/ Viab.",
    yield_alto: "Yield Alto",
    outro: "Outro",
  };
  const PIE_COLORS = ["#0F766E", "#16A34A", "#14B8A6", "#D97706", "#DC2626", "#94A3B8", "#6366F1", "#EC4899", "#F59E0B"];
  const typeCounts: Record<string, number> = {};
  // From enriched properties
  properties.forEach((p) => {
    if (p.opportunity_type) {
      const t = p.opportunity_type;
      typeCounts[t] = (typeCounts[t] || 0) + 1;
    }
  });
  // From standalone opportunities
  opportunities.forEach((opp) => {
    if (!linkedOppIds.has(opp.id) && opp.opportunity_type) {
      const t = opp.opportunity_type;
      typeCounts[t] = (typeCounts[t] || 0) + 1;
    }
  });
  const pieData = Object.entries(typeCounts)
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([type, count]) => ({
      name: OPP_TYPE_LABELS[type] || type,
      value: count,
    }));

  // Pipeline / properties by status
  const STATUS_LABELS: Record<string, string> = {
    lead: "Lead",
    oportunidade: "Oportunidade",
    analise: "Análise",
    active: "Activo",
    contacted: "Contactado",
    negotiating: "Negociação",
    cpcv_compra: "CPCV",
    arrendamento: "Arrendamento",
    marketing_activo: "Marketing",
  };
  const statusCounts: Record<string, number> = {};
  properties.forEach((p) => {
    const s = p.status || "lead";
    statusCounts[s] = (statusCounts[s] || 0) + 1;
  });
  const pipelineData = Object.entries(statusCounts)
    .sort((a, b) => b[1] - a[1])
    .map(([state, count]) => ({ state: STATUS_LABELS[state] || state, count }));

  // Recent 5 properties
  const recentProperties = [...properties]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 5);

  // Total opportunities (enriched properties with grade + standalone opps)
  const totalOpps = properties.filter((p) => p.deal_grade).length +
    opportunities.filter((opp) => !linkedOppIds.has(opp.id)).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-slate-400 text-sm">A carregar dashboard...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">
            Visão geral do portfólio
          </p>
        </div>
        <span
          className={`px-3 py-1 rounded-full text-xs font-medium ${
            dataSource === "supabase"
              ? "bg-teal-50 text-teal-700"
              : dataSource === "fastapi"
              ? "bg-amber-50 text-amber-700"
              : "bg-red-50 text-red-700"
          }`}
        >
          {dataSource === "supabase"
            ? "Supabase"
            : dataSource === "fastapi"
            ? "FastAPI (fallback)"
            : "Offline"}
        </span>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KPICard label="Propriedades" value={String(properties.length)} />
        <KPICard label="Oportunidades" value={String(totalOpps)} />
        <KPICard
          label="Deals Activos"
          value={String(dealStats.total_active ?? 0)}
        />
        <KPICard
          label="Valor Pipeline"
          value={formatEUR(dealStats.total_pipeline_value ?? 0)}
        />
      </div>

      {/* Charts Row 1: Grade Distribution + Top Municipalities */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Grade Distribution Bar Chart */}
        {gradeData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">
              Distribuição por Deal Grade
            </h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={gradeData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                <XAxis dataKey="grade" tick={{ fontSize: 13, fontWeight: 700 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(value: number) => [value, "Oportunidades"]}
                  contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
                <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={60}>
                  {gradeData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Top 10 Municipalities Horizontal Bar Chart */}
        {topMunicipalities.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">
              Top 10 Concelhos
            </h2>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart
                data={topMunicipalities}
                layout="vertical"
                margin={{ top: 8, right: 16, bottom: 8, left: 8 }}
              >
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={120}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  formatter={(value: number) => [value, "Propriedades"]}
                  contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
                <Bar dataKey="count" fill="#0F766E" radius={[0, 6, 6, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Charts Row 2: Opportunity Types Pie + Pipeline Funnel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Opportunity Types Pie Chart */}
        {pieData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">
              Tipos de Oportunidade
            </h2>
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={pieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={3}
                  dataKey="value"
                  label={({ name, percent }) =>
                    `${name} (${(percent * 100).toFixed(0)}%)`
                  }
                  labelLine={false}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number) => [value, "Oportunidades"]}
                  contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Pipeline / Status Distribution */}
        {pipelineData.length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 p-6">
            <h2 className="text-sm font-semibold text-slate-700 mb-4">
              Pipeline por Estado
            </h2>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={pipelineData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
                <XAxis dataKey="state" tick={{ fontSize: 11 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(value: number) => [value, "Propriedades"]}
                  contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
                />
                <Bar dataKey="count" fill="#0F766E" radius={[6, 6, 0, 0]} maxBarSize={60} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      {/* Recent Properties */}
      <div className="bg-white rounded-xl border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">
          Propriedades Recentes
        </h2>
        {recentProperties.length > 0 ? (
          <div className="space-y-3">
            {recentProperties.map((p) => (
              <div
                key={p.id}
                className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0"
              >
                <div>
                  <p className="text-sm font-medium text-slate-900">
                    {p.municipality || "Sem concelho"}
                    {p.parish ? ` — ${p.parish}` : ""}
                  </p>
                  <p className="text-xs text-slate-500">
                    {p.property_type || ""} {p.typology ? `| ${p.typology}` : ""}{" "}
                    {p.gross_area_m2 ? `| ${p.gross_area_m2}m2` : ""}
                  </p>
                </div>
                <div className="text-right flex items-center gap-2">
                  <p className="text-sm font-semibold text-teal-700">
                    {formatEUR(p.asking_price)}
                  </p>
                  {p.deal_grade && (
                    <span
                      className="text-xs font-bold px-2 py-0.5 rounded text-white"
                      style={{
                        backgroundColor:
                          GRADE_COLORS[p.deal_grade] ?? GRADE_COLORS.D,
                      }}
                    >
                      {p.deal_grade}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-400">Sem propriedades</p>
        )}
      </div>
    </div>
  );
}

function KPICard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <p className="text-xs font-medium text-slate-500 uppercase tracking-wide">
        {label}
      </p>
      <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
    </div>
  );
}
