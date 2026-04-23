"use client";

import React, { useState, useEffect, useCallback } from "react";
import useSWR, { mutate as globalMutate } from "swr";
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

import { apiGet, API_BASE, getAuthHeaders } from "@/lib/api";

const PROPERTIES_KEY = "/api/v1/properties/?limit=200";
const STATS_KEY = "/api/v1/ingest/stats";
const GROUPS_KEY = "/api/v1/ingest/groups";

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

interface GroupRow {
  id: number;
  whatsapp_group_id?: string;
  name: string;
  is_active: boolean;
  messages: number;
  opportunities: number;
  last_processed_at?: string | null;
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


export default function PropertiesPage() {
  const { data: propsResp, isLoading: propsLoading } = useSWR<{ items: Property[]; total: number } | null>(PROPERTIES_KEY);
  const { data: stats } = useSWR<IngestStats | null>(STATS_KEY);
  const { data: groupRows, mutate: mutateGroups } = useSWR<GroupRow[] | null>(GROUPS_KEY);
  const properties = propsResp?.items ?? [];
  const total = propsResp?.total ?? 0;
  const loading = propsLoading;
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState("");
  type PipelineGroupLog = {
    grupo: string;
    grupo_id: string;
    mensagens_buscadas: number;
    mensagens_filtradas: number;
    oportunidades: number;
    arquivado: boolean | null;
    unread_before?: number;
    unread_after?: number | null;
    archived_before?: boolean;
    archived_after?: boolean | null;
    estado?: string;
    erro?: string | null;
  };
  const [groupLogs, setGroupLogs] = useState<PipelineGroupLog[]>([]);
  const [showGroupLogs, setShowGroupLogs] = useState(false);
  const [showGroups, setShowGroups] = useState(false);
  const [groupFilter, setGroupFilter] = useState<"all" | "active" | "inactive">("all");
  const [groupSearch, setGroupSearch] = useState("");
  const [togglingIds, setTogglingIds] = useState<Set<number>>(new Set());
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
    await Promise.all([
      globalMutate(PROPERTIES_KEY),
      globalMutate(STATS_KEY),
      globalMutate(GROUPS_KEY),
    ]);
  }, []);

  const toggleGroupActive = useCallback(
    async (id: number, next: boolean) => {
      setTogglingIds((prev) => {
        const s = new Set(prev);
        s.add(id);
        return s;
      });
      try {
        const headers = await getAuthHeaders();
        const res = await fetch(`${API_BASE}/api/v1/ingest/groups/${id}`, {
          method: "PATCH",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({ is_active: next }),
        });
        if (!res.ok) {
          const txt = await res.text().catch(() => "");
          throw new Error(`HTTP ${res.status} ${txt}`);
        }
        await Promise.all([mutateGroups(), globalMutate(STATS_KEY)]);
      } catch (err) {
        setActionMsg(`Erro ao actualizar grupo: ${(err as Error).message}`);
      } finally {
        setTogglingIds((prev) => {
          const s = new Set(prev);
          s.delete(id);
          return s;
        });
      }
    },
    [mutateGroups]
  );

  // Recupera o resultado do último pipeline (se estado=done) para mostrar tabela após navegar
  const fetchLastPipelineResult = useCallback(async () => {
    try {
      const data = await apiGet<{
        status?: string;
        groups_processed?: number;
        messages_fetched?: number;
        opportunities_found?: number;
        groups_to_archive?: number;
        groups_archived?: number;
        errors?: string[];
        group_logs?: PipelineGroupLog[];
      }>("/api/v1/ingest/status");
      if (!data || data.status !== "done") return;
      const erros = data.errors?.length ? ` | ${data.errors.length} erro(s)` : "";
      const archived = data.groups_to_archive
        ? ` | ${data.groups_archived ?? 0}/${data.groups_to_archive} marcados como lidos`
        : "";
      setTriggerMsg(
        `Último pipeline: ${data.groups_processed ?? 0} grupos, ${data.messages_fetched ?? 0} mensagens, ${data.opportunities_found ?? 0} oportunidades${archived}${erros}`
      );
      if (Array.isArray(data.group_logs) && data.group_logs.length > 0) {
        setGroupLogs(data.group_logs);
      }
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchLastPipelineResult();
  }, [fetchLastPipelineResult]);

  // Quando o tab volta a ficar visivel, refaz status — evita banner preso
  // porque o Chrome suspende setInterval em tabs em background.
  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        fetchLastPipelineResult();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [fetchLastPipelineResult]);

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

  // Poll em background — não bloqueia a interface
  const pollRef = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const idleCountRef = React.useRef<number>(0);
  function startBackgroundPoll() {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const c = new AbortController();
        const t = setTimeout(() => c.abort(), 10000);
        const headers = await getAuthHeaders();
        const res = await fetch(`${API_BASE}/api/v1/ingest/status`, { headers, signal: c.signal });
        clearTimeout(t);
        if (!res.ok) return;
        const data = await res.json();

        if (data.status === "done") {
          const erros = data.errors?.length ? ` | ${data.errors.length} erro(s)` : "";
          const archived = data.groups_to_archive
            ? ` | ${data.groups_archived ?? 0}/${data.groups_to_archive} marcados como lidos`
            : "";
          setTriggerMsg(
            `Pipeline concluido: ${data.groups_processed ?? 0} grupos, ${data.messages_fetched ?? 0} mensagens, ${data.opportunities_found ?? 0} oportunidades${archived}${erros}`
          );
          if (Array.isArray(data.group_logs)) {
            setGroupLogs(data.group_logs);
            setShowGroupLogs(true);
          }
          setTriggerLoading(false);
          fetchData();
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
          return;
        }
        if (data.status === "error") {
          setTriggerMsg(`Erro no pipeline: ${data.errors?.[0] ?? "erro desconhecido"}`);
          setTriggerLoading(false);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
          return;
        }
        if (data.status === "idle") {
          // Pipeline voltou a idle — já terminou (sem transitar por "done")
          idleCountRef.current = (idleCountRef.current ?? 0) + 1;
          if (idleCountRef.current >= 2) {
            setTriggerMsg("Pipeline concluído (sem novos dados processados).");
            setTriggerLoading(false);
            fetchData();
            if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
            idleCountRef.current = 0;
          }
          return;
        }
        if (data.status === "running") {
          const elapsed = data.started_at
            ? Math.round((Date.now() - new Date(data.started_at).getTime()) / 1000)
            : 0;
          const groups = data.groups_processed || 0;
          const msgs = data.messages_fetched || 0;
          const opps = data.opportunities_found || 0;
          const progress = groups > 0
            ? ` | ${groups} grupos, ${msgs} msgs, ${opps} oportunidades`
            : "";
          setTriggerMsg(`Pipeline a correr... (${elapsed}s${progress})`);
        }
      } catch {
        // falha de rede — continuar a tentar
      }
    }, 10000); // poll a cada 10s
  }

  // Cleanup interval on unmount
  React.useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  async function wakeAndTrigger(): Promise<boolean> {
    // Passo 1: Acordar servidor (health check com retry)
    for (let attempt = 0; attempt < 6; attempt++) {
      try {
        setTriggerMsg(`A acordar servidor... (tentativa ${attempt + 1}/6)`);
        const c = new AbortController();
        const t = setTimeout(() => c.abort(), 30000);
        const res = await fetch(`${API_BASE}/health`, { signal: c.signal });
        clearTimeout(t);
        if (res.ok) break;
      } catch {
        if (attempt < 5) await new Promise((r) => setTimeout(r, 5000));
      }
    }

    // Passo 2: Disparar pipeline
    try {
      setTriggerMsg("Servidor acordado. A disparar pipeline...");
      const c = new AbortController();
      const t = setTimeout(() => c.abort(), 15000);
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/ingest/trigger`, { method: "POST", headers, signal: c.signal });
      clearTimeout(t);
      if (res.ok) {
        const data = await res.json();
        return data.status === "started" || data.status === "already_running";
      }
    } catch {
      // fallback
    }
    return false;
  }

  async function handleTriggerPipeline() {
    idleCountRef.current = 0;
    setTriggerLoading(true);
    const triggered = await wakeAndTrigger();
    if (triggered) {
      setTriggerMsg("Pipeline iniciado. A correr em background — pode continuar a usar o site.");
    } else {
      setTriggerMsg("Nao foi possivel contactar o servidor. Tente novamente em 1 minuto.");
      setTriggerLoading(false);
      return;
    }
    startBackgroundPoll();
  }

  async function handleReprocess() {
    setTriggerLoading(true);
    setTriggerMsg("A preparar reprocessamento...");
    try {
      // Passo 1: Preparar lista de grupos
      const reprocessHeaders = await getAuthHeaders();
      const initRes = await fetch(`${API_BASE}/api/v1/ingest/reprocess?days=10`, { method: "POST", headers: reprocessHeaders });
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

        const batchHeaders = await getAuthHeaders();
        const batchRes = await fetch(`${API_BASE}/api/v1/ingest/reprocess/batch?batch_size=10`, { method: "POST", headers: batchHeaders });
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
    // Localização
    if (fd.get("municipality")) body.municipality = fd.get("municipality");
    if (fd.get("district")) body.district = fd.get("district");
    if (fd.get("parish")) body.parish = fd.get("parish");
    if (fd.get("address")) body.address = fd.get("address");
    if (fd.get("postal_code")) body.postal_code = fd.get("postal_code");
    // Características
    if (fd.get("property_type")) body.property_type = fd.get("property_type");
    if (fd.get("typology")) body.typology = fd.get("typology");
    if (fd.get("asking_price")) body.asking_price = Number(fd.get("asking_price"));
    if (fd.get("gross_area_m2")) body.gross_area_m2 = Number(fd.get("gross_area_m2"));
    if (fd.get("bedrooms")) body.bedrooms = Number(fd.get("bedrooms"));
    if (fd.get("bathrooms")) body.bathrooms = Number(fd.get("bathrooms"));
    if (fd.get("floor")) body.floor = Number(fd.get("floor"));
    if (fd.get("construction_year")) body.construction_year = Number(fd.get("construction_year"));
    if (fd.get("condition")) body.condition = fd.get("condition");
    if (fd.get("energy_certificate")) body.energy_certificate = fd.get("energy_certificate");
    body.has_elevator = fd.get("has_elevator") === "on";
    body.has_parking = fd.get("has_parking") === "on";
    body.is_off_market = fd.get("is_off_market") === "on";
    // Contacto + notas
    if (fd.get("contact_name")) body.contact_name = fd.get("contact_name");
    if (fd.get("contact_phone")) body.contact_phone = fd.get("contact_phone");
    if (fd.get("contact_email")) body.contact_email = fd.get("contact_email");
    if (fd.get("notes")) body.notes = fd.get("notes");

    try {
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/properties/`, {
        method: "POST",
        headers,
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
      const headers = await getAuthHeaders();
      const res = await fetch(`${API_BASE}/api/v1/properties/${propertyId}`, {
        method: "PATCH",
        headers,
        body: JSON.stringify({ status: newStatus }),
      });
      if (res.ok) {
        setActionMsg(`Estado alterado para "${STATUS_LABELS[newStatus] || newStatus}"`);
        globalMutate(PROPERTIES_KEY);
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
          {groupLogs.length > 0 && (
            <button
              onClick={() => setShowGroupLogs(!showGroupLogs)}
              className="ml-3 underline text-xs"
            >
              {showGroupLogs ? "ocultar detalhe" : "ver detalhe por grupo"}
            </button>
          )}
        </div>
      )}
      {showGroupLogs && groupLogs.length > 0 && (
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">
              Detalhe por grupo ({groupLogs.length})
            </span>
            <button
              onClick={() => setShowGroupLogs(false)}
              className="text-xs text-slate-500 hover:text-slate-700"
            >
              fechar
            </button>
          </div>
          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-50 sticky top-0">
                <tr className="text-left text-slate-600">
                  <th className="px-3 py-2 font-medium">Grupo</th>
                  <th className="px-3 py-2 font-medium text-right">Msgs lidas</th>
                  <th className="px-3 py-2 font-medium text-right">Filtradas</th>
                  <th className="px-3 py-2 font-medium text-right">Opps</th>
                  <th className="px-3 py-2 font-medium text-center">Unread (antes → depois)</th>
                  <th className="px-3 py-2 font-medium text-center">Arquivado (antes → depois)</th>
                  <th className="px-3 py-2 font-medium text-center">Archive API</th>
                  <th className="px-3 py-2 font-medium">Estado</th>
                </tr>
              </thead>
              <tbody>
                {groupLogs.map((gl, i) => {
                  const ub = gl.unread_before ?? 0;
                  const ua = gl.unread_after;
                  const ab = gl.archived_before ?? false;
                  const aa = gl.archived_after;
                  const unreadChanged = ua != null && ua !== ub;
                  const archivedChanged = aa != null && aa !== ab;
                  return (
                  <tr key={`${gl.grupo_id}-${i}`} className="border-t border-slate-100 hover:bg-slate-50">
                    <td className="px-3 py-1.5 text-slate-800 truncate max-w-xs" title={gl.grupo}>{gl.grupo}</td>
                    <td className="px-3 py-1.5 text-right text-slate-600">{gl.mensagens_buscadas ?? 0}</td>
                    <td className="px-3 py-1.5 text-right text-slate-600">{gl.mensagens_filtradas ?? 0}</td>
                    <td className="px-3 py-1.5 text-right font-medium text-teal-700">{gl.oportunidades ?? 0}</td>
                    <td className="px-3 py-1.5 text-center text-slate-600">
                      <span className={unreadChanged ? "font-medium text-teal-700" : ""}>
                        {ub} → {ua ?? "—"}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      <span className={archivedChanged ? "font-medium text-teal-700" : "text-slate-600"}>
                        {ab ? "sim" : "não"} → {aa == null ? "—" : (aa ? "sim" : "não")}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-center">
                      {gl.arquivado === true ? (
                        <span className="text-green-600">✓</span>
                      ) : gl.arquivado === false ? (
                        <span className="text-red-600">✗</span>
                      ) : (
                        <span className="text-slate-300">—</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 text-slate-500">
                      {gl.erro ? <span className="text-red-600">{gl.erro}</span> : gl.estado ?? "ok"}
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Grupos Monitorizados — toggle is_active */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <button
          type="button"
          onClick={() => setShowGroups((v) => !v)}
          className="w-full px-4 py-3 border-b border-slate-200 flex items-center justify-between hover:bg-slate-50"
        >
          <span className="text-sm font-medium text-slate-700">
            Grupos Monitorizados
            {groupRows && (
              <span className="ml-2 text-xs text-slate-500">
                ({groupRows.filter((g) => g.is_active).length} activos / {groupRows.length} total)
              </span>
            )}
          </span>
          <span className="text-xs text-slate-500">{showGroups ? "ocultar" : "mostrar"}</span>
        </button>
        {showGroups && (
          <div>
            <div className="px-4 py-3 border-b border-slate-200 flex flex-wrap items-center gap-2">
              <input
                type="text"
                placeholder="Filtrar por nome..."
                value={groupSearch}
                onChange={(e) => setGroupSearch(e.target.value)}
                className="flex-1 min-w-[200px] px-3 py-1.5 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500"
              />
              <div className="inline-flex rounded-lg border border-slate-300 overflow-hidden text-xs">
                {(["all", "active", "inactive"] as const).map((k) => (
                  <button
                    key={k}
                    type="button"
                    onClick={() => setGroupFilter(k)}
                    className={`px-3 py-1.5 ${
                      groupFilter === k
                        ? "bg-teal-600 text-white"
                        : "bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {k === "all" ? "Todos" : k === "active" ? "Activos" : "Inactivos"}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              {!groupRows ? (
                <div className="px-4 py-6 text-center text-sm text-slate-500">A carregar...</div>
              ) : (
                <table className="w-full text-xs">
                  <thead className="bg-slate-50 sticky top-0">
                    <tr className="text-left text-slate-600">
                      <th className="px-3 py-2 font-medium">Grupo</th>
                      <th className="px-3 py-2 font-medium text-right">Msgs</th>
                      <th className="px-3 py-2 font-medium text-right">Opps</th>
                      <th className="px-3 py-2 font-medium">Último</th>
                      <th className="px-3 py-2 font-medium text-center">Activo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {groupRows
                      .filter((g) => {
                        if (groupFilter === "active" && !g.is_active) return false;
                        if (groupFilter === "inactive" && g.is_active) return false;
                        if (groupSearch.trim()) {
                          return (g.name || "").toLowerCase().includes(groupSearch.trim().toLowerCase());
                        }
                        return true;
                      })
                      .map((g) => {
                        const toggling = togglingIds.has(g.id);
                        const last = g.last_processed_at
                          ? new Date(g.last_processed_at).toLocaleString("pt-PT", {
                              day: "2-digit",
                              month: "2-digit",
                              hour: "2-digit",
                              minute: "2-digit",
                            })
                          : "—";
                        return (
                          <tr
                            key={g.id}
                            className={`border-t border-slate-100 hover:bg-slate-50 ${
                              !g.is_active ? "opacity-60" : ""
                            }`}
                          >
                            <td className="px-3 py-1.5 text-slate-800 truncate max-w-md" title={g.name}>
                              {g.name || <span className="text-slate-400">sem nome</span>}
                            </td>
                            <td className="px-3 py-1.5 text-right text-slate-600">{g.messages}</td>
                            <td className="px-3 py-1.5 text-right text-teal-700 font-medium">
                              {g.opportunities}
                            </td>
                            <td className="px-3 py-1.5 text-slate-500">{last}</td>
                            <td className="px-3 py-1.5 text-center">
                              <button
                                type="button"
                                disabled={toggling}
                                onClick={() => toggleGroupActive(g.id, !g.is_active)}
                                className={`relative inline-flex h-5 w-10 items-center rounded-full transition-colors ${
                                  g.is_active ? "bg-teal-600" : "bg-slate-300"
                                } ${toggling ? "opacity-50 cursor-wait" : "cursor-pointer"}`}
                                aria-label={g.is_active ? "Desactivar grupo" : "Activar grupo"}
                              >
                                <span
                                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                    g.is_active ? "translate-x-5" : "translate-x-1"
                                  }`}
                                />
                              </button>
                            </td>
                          </tr>
                        );
                      })}
                  </tbody>
                </table>
              )}
            </div>
            <div className="px-4 py-2 border-t border-slate-200 bg-slate-50 text-xs text-slate-500">
              Grupos inactivos não são processados pelo pipeline (sem fetch, sem archive).
            </div>
          </div>
        )}
      </div>

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
          <form onSubmit={handleCreateProperty} className="space-y-6">
            {/* Localização */}
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Localização</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <FormField name="municipality" label="Concelho" placeholder="Lisboa" type="text" />
                <FormField name="district" label="Distrito" placeholder="Lisboa" type="text" />
                <FormField name="parish" label="Freguesia" placeholder="Arroios" type="text" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="md:col-span-2">
                  <FormField name="address" label="Morada" placeholder="Rua António Maria Cardoso, 15" type="text" />
                </div>
                <FormField name="postal_code" label="Código Postal" placeholder="1200-026" type="text" />
              </div>
            </div>

            {/* Características */}
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Características</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
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
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <FormField name="gross_area_m2" label="Área bruta (m²)" placeholder="80" type="number" />
                <FormField name="bedrooms" label="Quartos" placeholder="2" type="number" />
                <FormField name="bathrooms" label="Casas de banho" placeholder="1" type="number" />
                <FormField name="floor" label="Andar" placeholder="3" type="number" />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <FormField name="construction_year" label="Ano construção" placeholder="1998" type="number" />
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
                    <option value="ruina">Ruína</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    Certificado energético
                  </label>
                  <select
                    name="energy_certificate"
                    className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-teal-500 focus:border-teal-500 outline-none bg-white"
                  >
                    <option value="">Selecionar</option>
                    {["A+", "A", "B", "B-", "C", "D", "E", "F", "G"].map((g) => (
                      <option key={g} value={g}>{g}</option>
                    ))}
                    <option value="isento">Isento</option>
                  </select>
                </div>
              </div>
              <div className="flex flex-wrap gap-6">
                <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" name="has_elevator" className="w-4 h-4 text-teal-600 rounded" />
                  Elevador
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" name="has_parking" className="w-4 h-4 text-teal-600 rounded" />
                  Estacionamento
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-slate-700">
                  <input type="checkbox" name="is_off_market" className="w-4 h-4 text-teal-600 rounded" />
                  Off-market
                </label>
              </div>
            </div>

            {/* Contacto */}
            <div>
              <h3 className="text-sm font-semibold text-slate-700 mb-3">Contacto do proprietário</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <FormField name="contact_name" label="Nome" placeholder="Nome" type="text" />
                <FormField name="contact_phone" label="Telefone" placeholder="+351..." type="text" />
                <FormField name="contact_email" label="Email" placeholder="nome@exemplo.pt" type="email" />
              </div>
            </div>

            {/* Notas */}
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
