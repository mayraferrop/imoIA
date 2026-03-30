"use client";

import { useState, useEffect, useCallback } from "react";
import { formatEUR, GRADE_COLORS } from "@/lib/utils";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "https://jurzdyncaxkgvcatyfdu.supabase.co";
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp1cnpkeW5jYXhrZ3ZjYXR5ZmR1Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzQzNzM2MDcsImV4cCI6MjA4OTk0OTYwN30.2DCCWcrhdwBLMxJ9hUbYkhOBQIgE_aD2jGNaZlAhO5k";
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://imoia.onrender.com";

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
  bedrooms?: number;
  condition?: string;
  asking_price?: number;
  status?: string;
  contact_name?: string;
  contact_phone?: string;
  notes?: string;
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
  original_message?: string;
  ai_reasoning?: string;
  location_extracted?: string;
  price_mentioned?: number;
  area_m2?: number;
  property_type?: string;
  status?: string;
  messages?: { group_name?: string };
}

interface IngestStats {
  groups?: { total: number; active: number };
  messages?: number;
  opportunities?: number;
  grade_distribution?: Record<string, number>;
  top_districts?: { district: string; count: number }[];
}

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

const CONDITION_LABELS: Record<string, string> = {
  novo: "Novo",
  renovado: "Renovado",
  usado: "Usado",
  para_renovar: "Para renovar",
  ruina: "Ruína",
};

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

const STATUS_COLORS: Record<string, string> = {
  lead: "#94A3B8",
  oportunidade: "#0F766E",
  analise: "#D97706",
  active: "#16A34A",
  cpcv_compra: "#6366F1",
  arrendamento: "#EC4899",
  marketing_activo: "#14B8A6",
};

const SUPA_HEADERS = {
  apikey: SUPABASE_KEY,
  Authorization: `Bearer ${SUPABASE_KEY}`,
};

async function fetchSupabaseProperties(): Promise<Property[]> {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/properties?select=id,source,source_opportunity_id,district,municipality,parish,property_type,typology,gross_area_m2,bedrooms,condition,asking_price,status,contact_name,contact_phone,notes,created_at&order=created_at.desc&limit=200`,
    { headers: SUPA_HEADERS }
  );
  if (!res.ok) throw new Error("Supabase fetch failed");
  return res.json();
}

async function fetchSupabaseOpportunities(): Promise<Opportunity[]> {
  const res = await fetch(
    `${SUPABASE_URL}/rest/v1/opportunities?select=id,deal_grade,deal_score,confidence,opportunity_type,original_message,ai_reasoning,location_extracted,price_mentioned,area_m2,property_type,status,messages(group_name)&is_opportunity=eq.true`,
    { headers: SUPA_HEADERS }
  );
  if (!res.ok) return [];
  return res.json();
}

function enrichProperties(properties: Property[], opportunities: Opportunity[]): Property[] {
  const oppMap = new Map<number, Opportunity>();
  for (const opp of opportunities) oppMap.set(opp.id, opp);
  return properties.map((p) => {
    if (p.source_opportunity_id && oppMap.has(p.source_opportunity_id)) {
      const opp = oppMap.get(p.source_opportunity_id)!;
      return { ...p, deal_grade: opp.deal_grade, deal_score: opp.deal_score, confidence: opp.confidence, opportunity_type: opp.opportunity_type, _opp: opp } as any;
    }
    return p;
  });
}

export default function PropertiesPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [stats, setStats] = useState<IngestStats | null>(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<"supabase" | "fastapi">("supabase");
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState("");
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createMsg, setCreateMsg] = useState("");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState("");

  // Filters
  const [filterMunicipality, setFilterMunicipality] = useState("");
  const [filterType, setFilterType] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [filterGrade, setFilterGrade] = useState("");
  const [filterMinPrice, setFilterMinPrice] = useState("");
  const [filterMaxPrice, setFilterMaxPrice] = useState("");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      let props: Property[] = [];
      try {
        const [rawProps, opps] = await Promise.all([
          fetchSupabaseProperties(),
          fetchSupabaseOpportunities(),
        ]);
        props = enrichProperties(rawProps, opps);
        setDataSource("supabase");
        setTotal(props.length);
      } catch {
        try {
          const c = new AbortController();
          const t = setTimeout(() => c.abort(), 8000);
          const propsRes = await fetch(`${API_BASE}/api/v1/properties/?limit=200`, { signal: c.signal });
          clearTimeout(t);
          if (propsRes.ok) {
            const data = await propsRes.json();
            props = data.items ?? [];
            setTotal(data.total ?? 0);
          }
          setDataSource("fastapi");
        } catch {
          setDataSource("fastapi");
        }
      }
      setProperties(props);

      try {
        const c = new AbortController();
        const t = setTimeout(() => c.abort(), 8000);
        const statsRes = await fetch(`${API_BASE}/api/v1/ingest/stats`, { signal: c.signal });
        clearTimeout(t);
        if (statsRes.ok) {
          setStats(await statsRes.json());
        }
      } catch {
        // Stats unavailable
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Client-side filtering (exclui descartados por default)
  const filtered = properties.filter((p) => {
    if (filterMunicipality && !p.municipality?.toLowerCase().includes(filterMunicipality.toLowerCase())) return false;
    if (filterType && p.property_type !== filterType) return false;
    if (filterStatus) {
      if (p.status !== filterStatus) return false;
    } else {
      if (p.status === "descartado") return false;
    }
    if (filterGrade && p.deal_grade !== filterGrade) return false;
    if (filterMinPrice && (p.asking_price ?? 0) < Number(filterMinPrice)) return false;
    if (filterMaxPrice && (p.asking_price ?? 0) > Number(filterMaxPrice)) return false;
    return true;
  });

  async function pollPipelineStatus() {
    const MAX_POLLS = 300; // 300 x 2s = 10 minutos max
    for (let i = 0; i < MAX_POLLS; i++) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const res = await fetch(`${API_BASE}/api/v1/ingest/status`);
        if (!res.ok) continue;
        const data = await res.json();

        if (data.status === "done") {
          const erros = data.errors?.length ? ` | ${data.errors.length} erro(s)` : "";
          setTriggerMsg(
            `Pipeline concluído: ${data.groups_processed ?? 0} grupos, ${data.messages_fetched ?? 0} mensagens, ${data.opportunities_found ?? 0} oportunidades${erros}`
          );
          fetchData();
          return;
        }
        if (data.status === "error") {
          setTriggerMsg(`Erro no pipeline: ${data.errors?.[0] ?? "erro desconhecido"}`);
          return;
        }
        // ainda running — mostrar progresso
        const elapsed = data.started_at
          ? Math.round((Date.now() - new Date(data.started_at).getTime()) / 1000)
          : i * 2;
        const groups = data.groups_processed || 0;
        const msgs = data.messages_fetched || 0;
        const opps = data.opportunities_found || 0;
        const progress = groups > 0
          ? ` | ${groups} grupos, ${msgs} msgs, ${opps} oportunidades`
          : "";
        setTriggerMsg(`Pipeline a correr... (${elapsed}s${progress})`);
      } catch {
        // falha de rede no poll — continuar a tentar
      }
    }
    setTriggerMsg("Pipeline demorou demasiado. Verifique os logs do servidor.");
  }

  async function handleTriggerPipeline() {
    setTriggerLoading(true);
    setTriggerMsg("A iniciar pipeline...");
    try {
      const res = await fetch(`${API_BASE}/api/v1/ingest/trigger`, { method: "POST" });
      if (!res.ok) {
        const detail = await res.text().catch(() => "");
        setTriggerMsg(`Erro ao disparar pipeline. ${detail}`);
        setTriggerLoading(false);
        return;
      }
      const data = await res.json();
      if (data.status === "already_running") {
        setTriggerMsg("Pipeline já está a correr. A acompanhar...");
      } else {
        setTriggerMsg("Pipeline iniciado. A acompanhar...");
      }
      await pollPipelineStatus();
    } catch {
      setTriggerMsg("Erro de comunicação com a API (offline?).");
    } finally {
      setTriggerLoading(false);
    }
  }

  async function handleReprocess() {
    setTriggerLoading(true);
    setTriggerMsg("A preparar reprocessamento...");
    try {
      // Passo 1: Preparar lista de grupos
      const initRes = await fetch(`${API_BASE}/api/v1/ingest/reprocess?days=10`, { method: "POST" });
      if (!initRes.ok) {
        const detail = await initRes.text().catch(() => "");
        setTriggerMsg(`Erro ao preparar reprocessamento. ${detail}`);
        setTriggerLoading(false);
        return;
      }
      const initData = await initRes.json();
      const totalGroups = initData.total_groups || 0;
      if (totalGroups === 0) {
        setTriggerMsg("Nenhum grupo com actividade nos ultimos 10 dias.");
        setTriggerLoading(false);
        return;
      }

      // Passo 2: Processar em batches de 10 grupos
      let done = false;
      let totalMsgs = 0;
      let totalOpps = 0;
      let groupsDone = 0;
      let batchNum = 0;

      while (!done) {
        batchNum++;
        setTriggerMsg(
          `A reprocessar... batch ${batchNum} | ${groupsDone}/${totalGroups} grupos | ${totalMsgs} msgs | ${totalOpps} oportunidades`
        );

        const batchRes = await fetch(`${API_BASE}/api/v1/ingest/reprocess/batch?batch_size=10`, { method: "POST" });
        if (!batchRes.ok) {
          setTriggerMsg(`Erro no batch ${batchNum}. A tentar continuar...`);
          break;
        }
        const batchData = await batchRes.json();
        done = batchData.done;
        totalMsgs = batchData.messages_fetched || 0;
        totalOpps = batchData.opportunities_found || 0;
        groupsDone = batchData.groups_processed || 0;
      }

      setTriggerMsg(
        `Reprocessamento concluido: ${groupsDone} grupos, ${totalMsgs} mensagens, ${totalOpps} oportunidades`
      );
      fetchData();
    } catch {
      setTriggerMsg("Erro de comunicacao com a API (offline?).");
    } finally {
      setTriggerLoading(false);
    }
  }

  async function handleCreateProperty(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setCreateLoading(true);
    setCreateMsg("");
    const fd = new FormData(e.currentTarget);
    const body: Record<string, any> = {};
    if (fd.get("municipality")) body.municipality = fd.get("municipality");
    if (fd.get("district")) body.district = fd.get("district");
    if (fd.get("parish")) body.parish = fd.get("parish");
    if (fd.get("property_type")) body.property_type = fd.get("property_type");
    if (fd.get("typology")) body.typology = fd.get("typology");
    if (fd.get("asking_price")) body.asking_price = Number(fd.get("asking_price"));
    if (fd.get("gross_area_m2")) body.gross_area_m2 = Number(fd.get("gross_area_m2"));
    if (fd.get("bedrooms")) body.bedrooms = Number(fd.get("bedrooms"));
    if (fd.get("condition")) body.condition = fd.get("condition");
    if (fd.get("notes")) body.notes = fd.get("notes");
    if (fd.get("contact_name")) body.contact_name = fd.get("contact_name");
    if (fd.get("contact_phone")) body.contact_phone = fd.get("contact_phone");

    try {
      const res = await fetch(`${API_BASE}/api/v1/properties/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setCreateMsg("Propriedade criada com sucesso!");
        setShowCreateForm(false);
        (e.target as HTMLFormElement).reset();
        fetchData();
      } else {
        setCreateMsg("Erro ao criar propriedade.");
      }
    } catch {
      setCreateMsg("Erro de comunicação.");
    } finally {
      setCreateLoading(false);
    }
  }

  async function handleStatusChange(propertyId: string, newStatus: string) {
    setActionMsg("");
    try {
      const res = await fetch(`${API_BASE}/api/v1/properties/${propertyId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        setActionMsg(`Estado alterado para "${STATUS_LABELS[newStatus] || newStatus}"`);
        // Update local state
        setProperties((prev) =>
          prev.map((p) => (p.id === propertyId ? { ...p, status: newStatus } : p))
        );
      } else {
        setActionMsg("Erro ao alterar estado.");
      }
    } catch {
      setActionMsg("Erro de comunicação com a API.");
    }
  }

  // Stats from API or computed
  const totalGroups = stats?.groups?.total ?? 0;
  const activeGroups = stats?.groups?.active ?? 0;
  const totalMsgs = stats?.messages ?? 0;
  const totalOpps = stats?.opportunities ?? properties.length;
  const conversion = totalMsgs > 0 ? ((totalOpps / totalMsgs) * 100).toFixed(1) : "0.0";

  // Grade distribution — enriched properties first, fallback to API stats
  const GRADE_ORDER = ["A", "B", "C", "D", "F"];
  const computedGrades: Record<string, number> = {};
  properties.forEach((p) => {
    if (p.deal_grade && GRADE_ORDER.includes(p.deal_grade)) {
      computedGrades[p.deal_grade] = (computedGrades[p.deal_grade] || 0) + 1;
    }
  });
  const hasComputedGrades = Object.keys(computedGrades).length > 0;
  const gradeDistFromApi = stats?.grade_distribution ?? {};
  const hasApiGrades = Object.keys(gradeDistFromApi).length > 0;
  const gradeDist = hasComputedGrades ? computedGrades : gradeDistFromApi;
  const gradeChartData = GRADE_ORDER.filter((g) => gradeDist[g])
    .map((g) => ({
      grade: g,
      count: gradeDist[g] || 0,
      color: GRADE_COLORS[g] || GRADE_COLORS.D,
    }));

  // Unique values for filters
  const municipalities = [...new Set(properties.map((p) => p.municipality).filter(Boolean))].sort();
  const propertyTypes = [...new Set(properties.map((p) => p.property_type).filter(Boolean))].sort();
  const statuses = [...new Set(properties.map((p) => p.status).filter((s): s is string => !!s))].sort();

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">M1 — Propriedades</h1>
          <p className="text-sm text-slate-500 mt-1">
            {total} propriedades no sistema
            <span className="ml-2 text-xs text-slate-400">
              ({dataSource === "supabase" ? "Supabase" : "FastAPI"})
            </span>
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            className="px-4 py-2.5 bg-white border border-slate-300 text-slate-700 rounded-lg text-sm font-medium hover:bg-slate-50 transition-colors"
          >
            + Nova propriedade
          </button>
          <button
            onClick={handleTriggerPipeline}
            disabled={triggerLoading}
            className="px-4 py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
          >
            {triggerLoading ? "A executar..." : "Rodar pipeline"}
          </button>
        </div>
      </div>

      {/* Messages */}
      {triggerMsg && (
        <div className={`px-4 py-3 rounded-lg text-sm ${triggerMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {triggerMsg}
        </div>
      )}
      {createMsg && (
        <div className={`px-4 py-3 rounded-lg text-sm ${createMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {createMsg}
        </div>
      )}

      {/* Stats KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Grupos" value={String(totalGroups)} sub={`${activeGroups} activos`} />
        <StatCard label="Mensagens" value={totalMsgs.toLocaleString("pt-PT")} />
        <StatCard label="Oportunidades" value={String(totalOpps)} />
        <StatCard label="Taxa conversão" value={`${conversion}%`} />
      </div>

      {/* Grade distribution from API stats (legacy data only) */}
      {gradeChartData.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-sm font-semibold text-slate-700 mb-4">Distribuição por Deal Grade</h2>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={gradeChartData} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
              <XAxis dataKey="grade" tick={{ fontSize: 13, fontWeight: 700 }} />
              <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
              <Tooltip
                formatter={(value: number) => [value, "Propriedades"]}
                contentStyle={{ borderRadius: 8, border: "1px solid #e2e8f0" }}
              />
              <Bar dataKey="count" radius={[6, 6, 0, 0]} maxBarSize={60}>
                {gradeChartData.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Create property form */}
      {showCreateForm && (
        <div className="bg-white rounded-xl border border-slate-200 p-6">
          <h2 className="text-lg font-semibold text-slate-900 mb-4">Nova propriedade</h2>
          <form onSubmit={handleCreateProperty} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField name="municipality" label="Concelho" placeholder="Lisboa" type="text" />
              <FormField name="district" label="Distrito" placeholder="Lisboa" type="text" />
              <FormField name="parish" label="Freguesia" placeholder="Arroios" type="text" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Tipo de imóvel</label>
                <select
                  name="property_type"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none bg-white"
                >
                  <option value="">Selecionar</option>
                  <option value="apartamento">Apartamento</option>
                  <option value="moradia">Moradia</option>
                  <option value="terreno">Terreno</option>
                  <option value="predio">Prédio</option>
                  <option value="armazem">Armazém</option>
                </select>
              </div>
              <FormField name="typology" label="Tipologia" placeholder="T2" type="text" />
              <FormField name="asking_price" label="Preço pedido (EUR)" placeholder="150000" type="number" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <FormField name="gross_area_m2" label="Área bruta (m²)" placeholder="80" type="number" />
              <FormField name="bedrooms" label="Quartos" placeholder="2" type="number" />
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Estado</label>
                <select
                  name="condition"
                  className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none bg-white"
                >
                  <option value="">Selecionar</option>
                  <option value="usado">Usado</option>
                  <option value="renovado">Renovado</option>
                  <option value="novo">Novo</option>
                  <option value="para_renovar">Para renovar</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField name="contact_name" label="Contacto" placeholder="Nome" type="text" />
              <FormField name="contact_phone" label="Telefone" placeholder="+351..." type="text" />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Notas</label>
              <textarea
                name="notes"
                rows={2}
                className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
                placeholder="Notas sobre a propriedade..."
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={createLoading}
                className="px-6 py-2.5 bg-teal-700 text-white rounded-lg text-sm font-medium hover:bg-teal-800 disabled:opacity-50 transition-colors"
              >
                {createLoading ? "A criar..." : "Criar propriedade"}
              </button>
              <button
                type="button"
                onClick={() => setShowCreateForm(false)}
                className="px-6 py-2.5 bg-slate-100 text-slate-600 rounded-lg text-sm font-medium hover:bg-slate-200 transition-colors"
              >
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Concelho</label>
            <select
              value={filterMunicipality}
              onChange={(e) => setFilterMunicipality(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todos</option>
              {municipalities.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Tipo</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todos</option>
              {propertyTypes.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Estado</label>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todos</option>
              {statuses.map((s) => (
                <option key={s} value={s}>{STATUS_LABELS[s] || s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Grade</label>
            <select
              value={filterGrade}
              onChange={(e) => setFilterGrade(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white outline-none focus:ring-2 focus:ring-teal-500"
            >
              <option value="">Todos</option>
              {["A", "B", "C", "D", "F"].map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Preço min</label>
            <input
              type="number"
              value={filterMinPrice}
              onChange={(e) => setFilterMinPrice(e.target.value)}
              placeholder="0"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">Preço max</label>
            <input
              type="number"
              value={filterMaxPrice}
              onChange={(e) => setFilterMaxPrice(e.target.value)}
              placeholder="999999"
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-teal-500"
            />
          </div>
        </div>
      </div>

      {/* Property count */}
      <p className="text-xs text-slate-400">{filtered.length} propriedade(s) encontrada(s)</p>

      {/* Action message */}
      {actionMsg && (
        <div className={`px-4 py-3 rounded-lg text-sm ${actionMsg.includes("Erro") ? "bg-red-50 text-red-700" : "bg-green-50 text-green-700"}`}>
          {actionMsg}
        </div>
      )}

      {/* Property cards */}
      {loading ? (
        <div className="text-center py-16 text-slate-400">A carregar...</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((p) => {
            const statusColor = STATUS_COLORS[p.status ?? "lead"] ?? "#94A3B8";
            const pricePerM2 = p.asking_price && p.gross_area_m2
              ? Math.round(p.asking_price / p.gross_area_m2)
              : null;
            const opp = (p as any)._opp as Opportunity | undefined;
            const isExpanded = expandedId === p.id;
            return (
              <div
                key={p.id}
                className={`bg-white rounded-xl border overflow-hidden transition-shadow ${isExpanded ? "border-teal-300 shadow-lg col-span-1 md:col-span-2 lg:col-span-3" : "border-slate-200 hover:shadow-md"}`}
                style={{ borderLeftWidth: 4, borderLeftColor: statusColor }}
              >
                <div
                  className="p-5 cursor-pointer"
                  onClick={() => setExpandedId(isExpanded ? null : p.id)}
                >
                  {/* Header */}
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="font-semibold text-slate-900">{p.municipality || "Sem concelho"}</h3>
                      {p.parish && <p className="text-xs text-slate-500">{p.parish}</p>}
                    </div>
                    <div className="flex items-center gap-1.5">
                      {p.deal_grade && (
                        <span
                          className="text-xs font-bold px-2 py-1 rounded-md text-white"
                          style={{ backgroundColor: GRADE_COLORS[p.deal_grade] ?? GRADE_COLORS.D }}
                        >
                          {p.deal_grade}
                          {p.deal_score != null && ` ${p.deal_score}`}
                        </span>
                      )}
                      {p.status && (
                        <span
                          className="text-xs font-medium px-2 py-1 rounded-md text-white"
                          style={{ backgroundColor: statusColor }}
                        >
                          {STATUS_LABELS[p.status] || p.status}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Specs line */}
                  <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                    {p.opportunity_type && (
                      <span className="bg-amber-50 text-amber-700 px-2 py-0.5 rounded">
                        {OPP_TYPE_LABELS[p.opportunity_type] || p.opportunity_type}
                      </span>
                    )}
                    {p.property_type && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{p.property_type}</span>
                    )}
                    {p.typology && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{p.typology}</span>
                    )}
                    {p.gross_area_m2 && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{p.gross_area_m2} m2</span>
                    )}
                    {p.bedrooms != null && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">{p.bedrooms} quartos</span>
                    )}
                    {p.condition && (
                      <span className="bg-slate-100 px-2 py-0.5 rounded">
                        {CONDITION_LABELS[p.condition] || p.condition}
                      </span>
                    )}
                    {p.confidence != null && (
                      <span className="bg-blue-50 text-blue-700 px-2 py-0.5 rounded">
                        Conf. {(p.confidence * 100).toFixed(0)}%
                      </span>
                    )}
                    {pricePerM2 != null && (
                      <span className="bg-teal-50 text-teal-700 px-2 py-0.5 rounded">
                        {formatEUR(pricePerM2)}/m2
                      </span>
                    )}
                  </div>

                  {/* Price + expand hint */}
                  <div className="mt-4 flex items-center justify-between">
                    <p className="text-lg font-bold text-teal-700">{formatEUR(p.asking_price)}</p>
                    <span className="text-xs text-slate-400">{isExpanded ? "Fechar" : "Ver detalhe"}</span>
                  </div>
                </div>

                {/* Expanded detail panel */}
                {isExpanded && (
                  <div className="border-t border-slate-200 p-5 space-y-4 bg-slate-50">
                    {/* Property info grid */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                      <div>
                        <p className="text-xs text-slate-500">Distrito</p>
                        <p className="font-medium text-slate-900">{p.district || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Concelho</p>
                        <p className="font-medium text-slate-900">{p.municipality || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Preço pedido</p>
                        <p className="font-medium text-teal-700">{formatEUR(p.asking_price)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Preço/m²</p>
                        <p className="font-medium text-slate-900">{pricePerM2 ? formatEUR(pricePerM2) : "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Área</p>
                        <p className="font-medium text-slate-900">{p.gross_area_m2 ? `${p.gross_area_m2} m2` : "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Tipo</p>
                        <p className="font-medium text-slate-900">{p.property_type || "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Quartos</p>
                        <p className="font-medium text-slate-900">{p.bedrooms ?? "—"}</p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-500">Fonte</p>
                        <p className="font-medium text-slate-900">{p.source || "—"}</p>
                      </div>
                    </div>

                    {/* Contact info */}
                    {(p.contact_name || p.contact_phone) && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Contacto</p>
                        <p className="text-sm text-slate-900">{p.contact_name || "—"} {p.contact_phone ? `| ${p.contact_phone}` : ""}</p>
                      </div>
                    )}

                    {/* Notes */}
                    {p.notes && (
                      <div className="bg-white rounded-lg p-3 border border-slate-200">
                        <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Notas</p>
                        <p className="text-sm text-slate-700 whitespace-pre-wrap">{p.notes}</p>
                      </div>
                    )}

                    {/* WhatsApp group origin */}
                    {opp?.messages?.group_name && (
                      <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                        <p className="text-xs font-semibold text-slate-500 uppercase mb-1">Grupo de origem</p>
                        <p className="text-sm text-slate-700 font-medium">{opp.messages.group_name}</p>
                      </div>
                    )}

                    {/* Original WhatsApp message */}
                    {opp?.original_message && (
                      <div className="bg-green-50 rounded-lg p-3 border border-green-200">
                        <p className="text-xs font-semibold text-green-700 uppercase mb-1">Mensagem original (WhatsApp)</p>
                        <p className="text-sm text-green-900 whitespace-pre-wrap">{opp.original_message}</p>
                      </div>
                    )}

                    {/* AI Analysis */}
                    {opp?.ai_reasoning && (
                      <div className="bg-blue-50 rounded-lg p-3 border border-blue-200">
                        <p className="text-xs font-semibold text-blue-700 uppercase mb-1">Análise IA</p>
                        <p className="text-sm text-blue-900 whitespace-pre-wrap">{opp.ai_reasoning}</p>
                      </div>
                    )}

                    {/* Location extracted */}
                    {opp?.location_extracted && (
                      <div className="text-sm text-slate-600">
                        <span className="font-medium">Localização extraída:</span> {opp.location_extracted}
                      </div>
                    )}

                    {/* Action buttons */}
                    <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-200">
                      <button
                        onClick={(e) => { e.stopPropagation(); handleStatusChange(p.id, "analise"); }}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                      >
                        Analisar
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleStatusChange(p.id, "contacted"); }}
                        className="px-4 py-2 bg-teal-600 text-white rounded-lg text-sm font-medium hover:bg-teal-700 transition-colors"
                      >
                        Contactar
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleStatusChange(p.id, "negotiating"); }}
                        className="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm font-medium hover:bg-amber-700 transition-colors"
                      >
                        Negociar
                      </button>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleStatusChange(p.id, "descartado"); }}
                        className="px-4 py-2 bg-red-500 text-white rounded-lg text-sm font-medium hover:bg-red-600 transition-colors"
                      >
                        Descartar
                      </button>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {!loading && filtered.length === 0 && (
        <div className="text-center py-16 text-slate-400">
          <p className="text-lg">Sem propriedades</p>
          <p className="text-sm mt-1">Ajuste os filtros ou adicione propriedades via API</p>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-4">
      <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
      <p className="text-2xl font-bold text-slate-900 mt-1">{value}</p>
      {sub && <p className="text-xs text-teal-600 mt-0.5">{sub}</p>}
    </div>
  );
}

function FormField({
  name,
  label,
  placeholder,
  type = "text",
}: {
  name: string;
  label: string;
  placeholder: string;
  type?: string;
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-700 mb-1">{label}</label>
      <input
        name={name}
        type={type}
        placeholder={placeholder}
        className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none"
      />
    </div>
  );
}
